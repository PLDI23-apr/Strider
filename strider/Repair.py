import os, json, copy
from func_timeout import func_set_timeout
import Config
from utils import FileUtils, StringUtils
from VerilogAnalyzer import VcdAnalyzer, SignalAnalyzer, AstAnalyzer, DataFlowAnalyzer
from Locator.Locator import Locator
from Adapter.Adapter import Adapter

# def groupActions(allMismatchSignals, allActions, allParameterInfos, mismatchSignals):
#     retMismatchSignals, retActions, retParameterInfos = [[]], [[]], [[]]
#     for ms in mismatchSignals:
#         gMismatchSignals, gActions, gParameterInfos = [], [], []
#         for mis, act, par in zip(allMismatchSignals[ms], allActions[ms], allParameterInfos[ms]):
#             eMismatchSignals, eActions, eParameterInfos = copy.deepcopy(retMismatchSignals), copy.deepcopy(retActions), copy.deepcopy(retParameterInfos)
#             for retMis, retAct, retPar in zip(eMismatchSignals, eActions, eParameterInfos):
#                 retMis.append(mis)
#                 retAct.append(act)
#                 retPar.append(par)
#             gMismatchSignals.extend(eMismatchSignals)
#             gActions.extend(eActions)
#             gParameterInfos.extend(eParameterInfos)
#         retMismatchSignals, retActions, retParameterInfos = gMismatchSignals, gActions, gParameterInfos
#     return retMismatchSignals, retActions, retParameterInfos

def groupActions(allMismatchSignals, allActions, allParameterInfos, mismatchSignals):
    retMismatchSignals, retActions, retParameterInfos = [], [], []
    for ms in mismatchSignals:
        for mis, act, par in zip(allMismatchSignals[ms], allActions[ms], allParameterInfos[ms]):
            retMismatchSignals.append([mis])
            retActions.append([act])
            retParameterInfos.append([par])
    return retMismatchSignals, retActions, retParameterInfos

def locate(benchmark, bugInfo, logger):
    srcFiles = bugInfo["src_file"]
    benchmark.updateSrcFiles(srcFiles)

    logger.info("Running simulation.")
    benchmark.test(srcFiles=srcFiles)

    logger.info("Reading oracle and simulation output.")
    oracleSignal, simSignal = benchmark.readSimulationOutput()

    logger.info("processing VCD files.")
    # oracleVcd, simVcd, attributesDict = benchmark.readVcd()
    oracleVcdFile, simVcdFile, timeScale = benchmark.readVcd()

    allTerms, allBindDicts, allParameters = {}, {}, {}
    logger.info("AST parsing.")
    astArgs = {"filelist":srcFiles, "include":bugInfo["include_list"], "define":bugInfo["define_list"]}
    astParser = AstAnalyzer.AstParser(astArgs)
    ast = astParser.getAst()
    # ast.show()
    # modules, instances = AstAnalyzer.getModuleAndInstance(ast)
    
    dfArgs = {"filelist":srcFiles, "include":bugInfo["include_list"], "define":bugInfo["define_list"], "noreorder":False, "nobind":False}
    # for module in modules:
    for module, _ in bugInfo["top_module"].items():
        logger.info("Dataflow analyzing {}.".format(module))
        dfArgs["topmodule"] = module
        dfAnalyzer = DataFlowAnalyzer.DataFlowAnalyzer(dfArgs)
        terms = dfAnalyzer.getTerms()
        bindDicts = dfAnalyzer.getBindDicts()
        parameters = dfAnalyzer.getParameters()
        allTerms.update(terms)
        allBindDicts.update(bindDicts)
        allParameters.update(parameters)
        
    moduleInfo = VcdAnalyzer.getModuleInfo(bugInfo["top_module"])

    timeStamp, mismatchSignals, attributesDict, prevSimSignalValue, tmpSimSignalValue, tmpOracleSignalValue = VcdAnalyzer.getMismatchSignal(oracleVcdFile, simVcdFile, timeScale)
    tmpInputSignalValues = VcdAnalyzer.getInputSignalValue(prevSimSignalValue, tmpSimSignalValue, mismatchSignals)

    logger.info("Locating suspicious df nodes.")
    locator = Locator(timeStamp, mismatchSignals, allBindDicts, allTerms, allParameters, moduleInfo)
    locator.locate(tmpInputSignalValues, tmpOracleSignalValue)
    suspiciousNodeIds = locator.getSpsNodeIds()
    suspiciousLinenos = AstAnalyzer.getSpsLineno(ast, suspiciousNodeIds)
    logger.info("Suspicious Lines: {}".format(suspiciousLinenos))

@func_set_timeout(Config.REPAIR_TIME)
def repair(benchmark, bugInfo, logger):
    candidateSrcFilesList = [bugInfo["src_file"]]
    while len(candidateSrcFilesList) > 0:
        srcFiles = candidateSrcFilesList.pop(0)
        benchmark.updateSrcFiles(srcFiles)

        logger.info("Running simulation.")
        benchmark.test(srcFiles=srcFiles)

        logger.info("Reading oracle and simulation output.")
        oracleSignal, simSignal = benchmark.readSimulationOutput()

        logger.info("processing VCD files.")
        # oracleVcd, simVcd, attributesDict = benchmark.readVcd()
        oracleVcdFile, simVcdFile, timeScale = benchmark.readVcd()

        allTerms, allBindDicts, allParameters = {}, {}, {}
        logger.info("AST parsing.")
        astArgs = {"filelist":srcFiles, "include":bugInfo["include_list"], "define":bugInfo["define_list"]}
        astParser = AstAnalyzer.AstParser(astArgs)
        ast = astParser.getAst()
        # ast.show()
        # modules, instances = AstAnalyzer.getModuleAndInstance(ast)
        fileToModulesMap = AstAnalyzer.mapFileToModule(astArgs)
        
        dfArgs = {"filelist":srcFiles, "include":bugInfo["include_list"], "define":bugInfo["define_list"], "noreorder":False, "nobind":False}
        # for module in modules:
        for module, _ in bugInfo["top_module"].items():
            logger.info("Dataflow analyzing {}.".format(module))
            dfArgs["topmodule"] = module
            dfAnalyzer = DataFlowAnalyzer.DataFlowAnalyzer(dfArgs)
            terms = dfAnalyzer.getTerms()
            bindDicts = dfAnalyzer.getBindDicts()
            parameters = dfAnalyzer.getParameters()
            allTerms.update(terms)
            allBindDicts.update(bindDicts)
            allParameters.update(parameters)
        
        moduleInfo = VcdAnalyzer.getModuleInfo(bugInfo["top_module"])

        # timeStamp, mismatchSignals = SignalAnalyzer.getMismatchSignal(oracleSignal, simSignal)
        # timeStamp, mismatchSignals = VcdAnalyzer.getMismatchSignal(oracleVcd, simVcd)

        # prevIndex, postIndex, timeStamps = VcdAnalyzer.getNearTimeStamp(timeStamp, simVcd)
        # inputIndex = timeStamps.index(timeStamp) - 1 if timeStamps.index(timeStamp) - 1 > 0 else 0
        # tmpInputSignalValues = VcdAnalyzer.getInputSignalValue(timeStamps[inputIndex], timeStamp, simVcd, mismatchSignals)
        # tmpInputSignalValue = VcdAnalyzer.getTmpSignalValue(timeStamps[inputIndex], simVcd)
        # tmpSimSignalValue = VcdAnalyzer.getTmpSignalValue(timeStamp, simVcd)
        # tmpOracleSignalValue = VcdAnalyzer.getTmpSignalValue(timeStamp, oracleVcd)
        timeStamp, mismatchSignals, attributesDict, prevSimSignalValue, tmpSimSignalValue, tmpOracleSignalValue = VcdAnalyzer.getMismatchSignal(oracleVcdFile, simVcdFile, timeScale)
        tmpInputSignalValues = VcdAnalyzer.getInputSignalValue(prevSimSignalValue, tmpSimSignalValue, mismatchSignals)

        logger.info("Locating suspicious df nodes.")
        locator = Locator(timeStamp, mismatchSignals, allBindDicts, allTerms, allParameters, moduleInfo)
        locator.locate(tmpInputSignalValues, tmpOracleSignalValue)

        bindDicts = locator.getBindDicts()
        executedPaths = locator.getExecutedPaths()
        availableTerms = locator.getAvailableTerms()
        availableParameters = locator.getAvailableParameters()
        availableRenameInfo = locator.getAvailableRenameInfo()

        # For validation
        # prevTimeStamp, postTimeStamp = timeStamps[prevIndex], timeStamps[postIndex]
        # prevInputIndex, postInputIndex = prevIndex - 1 if prevIndex - 1 > 0 else 0, postIndex - 1 if postIndex - 1 > 0 else 0
        # prevTmpInputSignalValue = VcdAnalyzer.getInputSignalValue(timeStamps[prevInputIndex], prevTimeStamp, oracleVcd, mismatchSignals)
        # prevTmpOracleSignalValue = VcdAnalyzer.getTmpSignalValue(prevTimeStamp, oracleVcd)
        # postTmpInputSignalValue = VcdAnalyzer.getInputSignalValue(timeStamps[postInputIndex], postTimeStamp, oracleVcd, mismatchSignals)
        # postTmpOracleSignalValue = VcdAnalyzer.getTmpSignalValue(postTimeStamp, oracleVcd)

        logger.info("Repairing suspicious nodes.")
        allMismatchSignals, allActions, allParameterInfos = {}, {}, {}
        for ms, ats, aps, ars, bds, eps in zip(mismatchSignals, availableTerms, availableParameters, availableRenameInfo, bindDicts, executedPaths):
            allMismatchSignals[ms], allActions[ms], allParameterInfos[ms] = [], [], []
            subInstance = ms[:ms.rindex('.')]
            adapter = Adapter()
            msTmpOracleSignalValue, msTmpInputSignalValue = tmpOracleSignalValue[ms], tmpInputSignalValues[ms]
            # msPrevTmpInputSignalValue, msPostTmpInputSignalValue = prevTmpInputSignalValue[ms], postTmpInputSignalValue[ms]
            # msPrevTmpOracleSignalValue, msPostTmpOracleSignalValue= prevTmpOracleSignalValue[ms], postTmpOracleSignalValue[ms]
            for at, ap, ar, bd, ep in zip(ats, aps, ars, bds, eps):
                sbd = copy.deepcopy(bd)
                candidateBindDicts = adapter.synthesize(subInstance, msTmpOracleSignalValue, msTmpInputSignalValue, attributesDict, at, ap, ar, sbd, ep, allBindDicts)
                for cbd in candidateBindDicts:
                    # msPrevTargetSignal, _ = DataFlowAnalyzer.traverseDataflow(subInstance, msPrevTmpInputSignalValue, ap, ar, cbd.tree)
                    # msPostTargetSignal, _ = DataFlowAnalyzer.traverseDataflow(subInstance, msPostTmpInputSignalValue, ap, ar, cbd.tree)
                    # No assign, output is equal to input.
                    # if msPrevTargetSignal == None: msPrevTargetSignal = msPrevTmpInputSignalValue[ms]
                    # if msPostTargetSignal == None: msPostTargetSignal = msPostTmpInputSignalValue[ms]
                    # if (prevTimeStamp == 0 or SignalAnalyzer.equal(msPrevTargetSignal, msPrevTmpOracleSignalValue)):
                    actions = adapter.adaptBindDict(bd, cbd)
                    allMismatchSignals[ms].append((cbd.dest, cbd.lsb, cbd.msb, cbd.ptr))
                    allActions[ms].append(actions)
                    allParameterInfos[ms].append(cbd.parameterinfo)
        groupAllMismatchSignals, groupAllActions, groupAllParameterInfos = groupActions(allMismatchSignals, allActions, allParameterInfos, mismatchSignals)

        for gMismatchSignals, gActions, gParameterInfos in zip(groupAllMismatchSignals, groupAllActions, groupAllParameterInfos):
            adapter.adaptAst(copy.deepcopy(ast), gMismatchSignals, gParameterInfos, gActions, fileToModulesMap)
            logger.info("Generating code.")
            suspiciousFiles, newAsts = adapter.getPatchAst()
            generator = AstAnalyzer.AstGenerator()
            newCodes = []
            try:
                for newAst in newAsts:
                    newCode = generator.visit(newAst)
                    newCodes.append(newCode)
                    logger.info("Validate candidate patched code:\n{}".format(newCode))
                validateFlag, candidateSrcFiles = benchmark.validate(suspiciousFiles, newCodes)
                if validateFlag:
                    bugId = benchmark.getBugId()
                    patchDir = os.path.join(Config.PATCH_DIR, *bugId)
                    for candidateSrcFile in candidateSrcFiles:
                        if Config.WORK_DIR in candidateSrcFile:
                            baseCandidateSrcFile = StringUtils.subString("_can\d{4}", "", os.path.basename(candidateSrcFile))
                            FileUtils.moveFile(candidateSrcFile, os.path.join(patchDir, baseCandidateSrcFile))
                    logger.info("Repair success.")
                    return
                else:
                    # oracleSignal, simSignal = benchmark.readSimulationOutput()
                    # tmpTimeStamp, _ = SignalAnalyzer.getMismatchSignal(oracleSignal, simSignal)
                    tmpTimeStamp = VcdAnalyzer.getMismatchSignal(oracleVcdFile, simVcdFile, timeScale)[0]
                    if int(tmpTimeStamp) > timeStamp:
                        # keep the file
                        logger.info("Keep the modified file.")
                        candidateSrcFilesList.append(candidateSrcFiles)
                    else:
                        logger.info("Repair failed.")
            except Exception as e:
                logger.error(str(e))
                logger.info("AST parse, compile or simulate failed!")
        
        benchmark.removeSimulationFiles()