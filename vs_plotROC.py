#!/usr/bin/env python

from matplotlib import pyplot as plt
import matplotlib
import argparse
import scipy.integrate
import sys
import os
import math


def main():

    title, rocLegends, resultPaths, zoom, \
        knownIDfirst, knownIDlast, \
        ommitIDfirst, ommitIDlast, \
        log, gui = parseArgs()

    # Read the results of each VS and keep only the ligIDs that are common
    # to all of them

    allVsResultsIntersect = intersectResults(resultPaths)
    # print resultPaths

    rocPaths = []
    allTotalLibs = []
    allTotalKnowns = []
    # Calculate ROC curves for each of these (write file + return data)
    for resultPath, vsResult in zip(resultPaths, allVsResultsIntersect):
        vsDir = os.path.dirname(resultPath)
        # print knownIDfirst, knownIDlast, ommitIDfirst, ommitIDlast
        rocPath, totalLib, totalKnown = writeRocFile(vsResult, vsDir,
                                                     knownIDfirst, knownIDlast,
                                                     ommitIDfirst, ommitIDlast)
        print rocPath, totalLib, totalKnown
        rocPaths.append(rocPath)
        allTotalLibs.append(totalLib)
        allTotalKnowns.append(totalKnown)

    # Make sure the total library size and the total number of knowns is the
    # same between all vsResults. Exit and print statement if it isn't
    for totalL in allTotalLibs:
        if totalLib != totalL:
            print "Total library size not mathing between VS experiments"
            sys.exit()

    for totalK in allTotalKnowns:
        if totalKnown != totalK:
            print "Total number of knowns not matching between VS experiments"
            sys.exit()

    # Extract the data from the ROC files
    rocData, perfect, xLim, yLim = extractRocData(rocPaths, rocLegends,
                                                  totalKnown, zoom)

    getAUC_NSQ(rocData, perfect)

    # Plot the values 2 and 3, which correspond to the percentage X and Y
    plot(title, rocData, perfect, xLim, yLim,
         totalLib, totalKnown, gui, log, zoom)

    # Write down the command that was used to exectute this script in a log
    # file, at the location where the script is executed. Also write the
    # current working directory at the time of execution

    cwd = os.getcwd()
    args = " ".join(sys.argv)

    logFile = open("plot.log", "w")
    logFile.write(cwd + "\n")
    logFile.write(args)
    logFile.close()


def parseArgs():
    """
    Parsing and returning arguments
    """

    # Definition of arguments
    descr = "Feed VS result data (however many files), plots ROC curves"
    descr_title = "Provide a title for the graph, also used as filename"
    descr_results = "Provide resultDataFiles.csv and 'legend titles' for" \
        " each curve: 'legend1!' data1.csv 'legend2?' data2.csv" \
        " 'legend4!!' data4.csv"
    descr_zoom = "Give the percent of ranked database to be displayed in the" \
        " zoomed subplot"
    descr_knownIDrange = "Provide the ID range of known actives lig" \
                         "lib (format: 1-514)"
    descr_ommitIDrange = "Provide the ID range of ligands to ommit " \
                         "from the ROC curve data"
    descr_log = "Draw this plot on a log scale for the X axis"
    descr_gui = "Use this flag to display plot: saves to .png by the default"

    # adding arguments to the parser
    parser = argparse.ArgumentParser(description=descr)
    parser.add_argument("title", help=descr_title)
    parser.add_argument("results", help=descr_results, nargs="+")
    parser.add_argument("zoom", help=descr_zoom)
    parser.add_argument("knownIDrange", help=descr_knownIDrange)
    parser.add_argument("ommitIDrange", help=descr_ommitIDrange)
    parser.add_argument("-log", action="store_true", help=descr_log)
    parser.add_argument("-gui", action="store_true", help=descr_gui)

    # parsing args
    args = parser.parse_args()
    title = args.title
    results = args.results
    zoom = float(args.zoom)
    knownIDrange = args.knownIDrange
    knownIDfirst, knownIDlast = knownIDrange.split("-")
    print "kownIDrange", knownIDrange
    ommitIDrange = args.ommitIDrange
    ommitIDfirst, ommitIDlast = ommitIDrange.split("-")
    print "ommitIDrange", ommitIDrange
    log = args.log
    gui = args.gui

    # Extrac the ROC paths and legends from the roc variable
    resultPaths = []
    rocLegends = []
    i = 0
    while i < len(results):
        rocLegends.append(results[i])
        resultPaths.append(results[i + 1])
        i += 2

    return title, rocLegends, resultPaths, zoom, \
        int(knownIDfirst), int(knownIDlast), \
        int(ommitIDfirst), int(ommitIDlast), \
        log, gui


def intersectResults(resultPaths):
    """
    Read in the results provided in .csv format, and figure out the interesect
    between each of those results set based on the ligID. Then return the
    results set containing only the intersect results for each set.
    """

    allVsResults = []
    allLigIDs = []

    # Read results and populate vsResultsRaw
    for resultPath in resultPaths:
        resultFile = open(resultPath, 'r')
        resultLines = resultFile.readlines()
        resultFile.close()

        vsResult = []
        ligIDs = []
        # loop over the vs result lines omitting the first row
        print resultPath, len(resultLines)
        for line in resultLines[1:]:
            ligInfo = line.strip().split(",")
            vsResult.append(ligInfo)
            ligIDs.append(ligInfo[0])

        allVsResults.append(vsResult)
        allLigIDs.append(set(ligIDs))

    # Get the intersection set
    intersectLigID = set.intersection(*allLigIDs)

    allVsResultsIntersect = []
    # Loop over vsResults and keep only the ones present in the intersection
    for resultPath, vsResult in zip(resultPaths, allVsResults):
        print resultPath, len(vsResult)
        vsResultIntersect = []
        for i, ligInfo in enumerate(vsResult):
            if ligInfo[0] in intersectLigID:
                vsResultIntersect.append(ligInfo)
        allVsResultsIntersect.append(vsResultIntersect)

    return allVsResultsIntersect


def writeRocFile(vsResult, vsDir,
                 knownIDfirst, knownIDlast,
                 ommitIDfirst, ommitIDlast):
    """
    Given this VS result, and information about the ID of known actives
    in the library, write in a file the information to plot a ROC curve
    """

    knowns = "knowns_" + str(knownIDfirst) + "-" + str(knownIDlast)
    ommits = "ommits_" + str(ommitIDfirst) + "-" + str(ommitIDlast)

    # Create filename
    rocPath = vsDir + "/roc_" + knowns + "_" + ommits + "_" + vsDir + ".csv"
    print "\t", rocPath
    rocDataFile = open(rocPath, "w")

    # Loop over the results once, in order to check for the actual total number
    # of knowns present in them
    totalKnowns = 0
    for ligInfo in vsResult:
        ligID = int(ligInfo[0])
        if ligID in range(knownIDfirst, knownIDlast + 1):
            totalKnowns += 1

    # Get the total library size
    if ommitIDfirst == 0 or ommitIDlast == 0:
        totalLibrary = len(vsResult)
    else:
        totalLibrary = len(vsResult) - (ommitIDlast - ommitIDfirst + 1)

    print "\nTotal knowns:", totalKnowns
    print "Total library - knowns:", totalLibrary, totalKnowns

    print vsDir, len(vsResult)

    X = 0
    Y = 0
    for ligInfo in vsResult:
        # print ligInfo
        ligID = int(ligInfo[0])

        # Skip if ligID is part of the range that needs to be ommited
        # If the ommit values are '0', then there is no ligand to ommit
        if ommitIDfirst != 0 and \
                ommitIDlast != 0 and \
                ligID in range(ommitIDfirst, ommitIDlast + 1):
            # print "ligand skipped", ligInfo
            continue
        # Otherwise proceed normally
        else:
            # When the sorted ligID corresponds to a known, increase
            # the value of Y by 1
            if ligID in range(knownIDfirst, knownIDlast + 1):
                # print "known ligand", ligInfo
                Y += 1

            # For each ligand in the full VS, increase X and write
            # the X,Y pair to the data file
            X += 1

            # Calculate percentage X and Y
            Xpercent = (X * 100.0) / totalLibrary
            Ypercent = (Y * 100.0) / totalKnowns
            rocDataFile.write(str(X) + "," + str(Y) + "," +
                              str(Xpercent) + "," + str(Ypercent) + "\n")

    rocDataFile.close()

    return rocPath, totalLibrary, totalKnowns


def extractRocData(rocPaths, rocLegends, totalKnown, zoom):
    """
    Read the ROC data files, return the data for plotting
    """

    # Variables that define the x and y limites for the zoomed in subplot
    xLim = 0.0
    yLim = 0.0

    rocData = []

    for rocPath, rocLegend in zip(rocPaths, rocLegends):
        # Read the ROC data file
        rocFile = open(rocPath, "r")
        rocLines = rocFile.readlines()
        rocFile.close()

        print "ROC PATH:", rocPath

        perfect = []
        X = []
        Y = []
        val = 0
        for line in rocLines:
            # Get the data from the file
            ll = line.split(",")
            xPercent = float(ll[2])
            yPercent = float(ll[3])

            # Create the data curve
            X.append(xPercent)
            Y.append(yPercent)

            # Create the perfect curve
            if val < totalKnown:
                val += 1
            perfect.append((val * 100.0) / totalKnown)

            # Create the subplot limits
            if xPercent <= zoom:
                if yLim < yPercent:
                    xLim = xPercent
                    yLim = yPercent

        rocData.append((X, Y, rocLegend))

    return rocData, perfect, xLim, yLim


def getAUC_NSQ(rocData, perfect):
    """
    Calculate AUC and NSQ_AUC for each curve, and return a list with those
    values (corresponds to the order of rocData)
    """

    # aucData = []

    print "perfect=", len(perfect)
    # perfectSq = [math.sqrt(i) for i in perfect]

    for rocDatum in rocData:
        X = rocDatum[0]
        Y = rocDatum[1]
        legend = rocDatum[2]

        Xsq = [math.sqrt(i) for i in X]
        # Ysq = [math.sqrt(i) for i in Y]

        print "X=", len(X)
        print "Y=", len(Y)

        auc = scipy.integrate.trapz(Y, X)
        aucSq = scipy.integrate.trapz(Y, Xsq)
        # auc2 = scipy.integrate.simps(Y, X)

        perf = scipy.integrate.trapz(perfect, X)
        perfSq = scipy.integrate.trapz(perfect, Xsq)
        # perf2 = scipy.integrate.simps(perfect, X)

        rand = scipy.integrate.trapz(X, X)
        randSq = scipy.integrate.trapz(X, Xsq)
        # rand2 = scipy.integrate.simps(X, X)

        print "**************"

        print legend
        print "auc", auc        # , auc2
        print "aucSq", aucSq
        print "perfect", perf   # , perf2
        print "perfectSq", perfSq
        print "rand", rand      # , rand2
        print "randSq", randSq
        print

        nsq_auc = (aucSq - randSq) / (perfSq / randSq)
        nsq_auc_perf = (perfSq - randSq) / (perfSq / randSq)
        nsq_auc_rand = (randSq - randSq) / (perfSq / randSq)

        print "NSQ_AUC:", nsq_auc
        print "NSQ_AUC - perf:", nsq_auc_perf
        print "NSQ_AUC - rand:", nsq_auc_rand

        print "**************"


def plot(title, rocData, perfect, xLim, yLim,
         totalLib, totalKnown, gui, log, zoom):
    """
    Plot the data provided as argument, to draw ROC curves
    """

    # Setting up the figure
    fig = plt.figure(figsize=(13, 12), dpi=100)
    ax = fig.add_subplot(111)
    # Create the ZOOMED graph, if requested
    if zoom != 0.0:
        ax2 = plt.axes([.17, .35, .2, .2])

    # Setting up color scheme
    cm = plt.get_cmap("spectral")
    cNorm = matplotlib.colors.Normalize(vmin=0, vmax=len(rocData))
    scalarMap = matplotlib.cm.ScalarMappable(norm=cNorm, cmap=cm)
    # ax.set_color_cycle([scalarMap.to_rgba(i) for i in range(len(rocData))])

    # Drawing data on the figure
    for i, rocDatum in enumerate(rocData):
        # Set color for crystal structures, and the LDM results have their
        # colors defined by the colormap
        if i == 0:
            color = 'black'
        elif i == 1:
            color = 'grey'
        else:
            color = scalarMap.to_rgba(i)
        X = rocDatum[0]
        Y = rocDatum[1]
        rocLegend = rocDatum[2]

        # Plot this curve
        ax.plot(X, Y, label=rocLegend, linewidth=2, color=color)

        # Plot a blow up of the first X%
        if zoom != 0.0:
            ax2.plot(X, Y, color=color)

    # Plot the RANDOM and PERFECT curves on the zoomed and main graph
    if zoom != 0.0:
        ax2.plot(X, perfect, color="grey")
        ax2.plot(X, X, "--", color="grey")
        ax2.tick_params(axis="both", which="major", labelsize=8)
        ax2.set_title("Zoom of the first " + str(zoom) + "%", fontsize=10)

    # Now plot random and perfect curves, common for all plotted curves
    ax.plot(X, X, "--", color="grey")
    ax.plot(X, perfect, color="grey")

    # Here axis and ticks are improved
    ax.set_xlabel("% of ranked database (total=" + str(totalLib) + ")",
                  fontsize=16)
    ax.set_ylabel("% of known ligands found (total=" + str(totalKnown) + ")",
                  fontsize=16)
    ax.minorticks_on()
    ax.set_title(title, fontsize=18)
    ax.legend(loc="upper left", prop={'size': 12})
    ax.axis('tight')

    if log:
        ax.set_xscale("log")
        # ax.set_xticks([0.1, 1, 10, 100])
        # ax.set_xticklabels([0.1, 1, 10, 100])
        # Setting ZOOMED ax2 graph
        if zoom != 0.0:
            ax2.set_xscale("log")
            ax2.set_xlim([0, zoom])
            ax2.set_ylim([0, yLim])
            # xLimRound = int(xLim * 100) / 100.0
            yLimRound = int(yLim * 100) / 100.0
            ax2.set_yticks([0, yLimRound])
            # ax2.set_xticklabels([])
            # print xLimRound
            # plt.setp(ax2, xlim=(0, zoom), ylim=(0, yLim),
            #         xticks=[0, zoom], yticks=[0, yLimRound])

    if gui:
        plt.show()
    else:
        fileName = title.replace(" ", "_") + ".png"
        plt.savefig(fileName, bbox_inches="tight")


if __name__ == "__main__":
    main()
