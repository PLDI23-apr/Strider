import math
import re, io, copy
from vcd.reader import TokenKind, tokenize, ScopeDecl

def computeUnitLevel(tsUnit, tsPrecision):
    tsUnitMatch = re.match("(\d+)(\w+)", tsUnit)
    tsPrecisionMatch = re.match("(\d+)(\w+)", tsPrecision)
    tsu1, tsu2 = int(tsUnitMatch[1]), tsUnitMatch[2]
    tsp1, tsp2 = int(tsPrecisionMatch[1]), tsPrecisionMatch[2]
    UnifiedUnitToNanoSecond = {"s":1000000, "ms": 1000, "ns": 1, "ps": 0.001, "fs": 0.000001}
    return tsp1 * UnifiedUnitToNanoSecond[tsp2] / (tsu1 * UnifiedUnitToNanoSecond[tsu2])

def mapInstanceToModule(instances, moduleInfo, tmpModule, tmpInstance):
    if tmpModule not in instances: return
    for instance in instances[tmpModule]:
        moduleInfo["{}.{}".format(tmpInstance, instance[1])] = instance[0]
        mapInstanceToModule(instances, moduleInfo, instance[0], "{}.{}".format(tmpInstance, instance[1]))


def getModuleInfo(topModule):
    moduleInfo = {}
    for tmpModule, tmpInstances in topModule.items():
        for tmpInstance in tmpInstances:
            moduleInfo[tmpInstance] = tmpModule
            # mapInstanceToModule(instances, moduleInfo, tmpModule, tmpInstance)
    return moduleInfo

def getTmpSignalValue(time, vcd):
    tmpSignalValue = {}
    for signal, valueList in vcd.items():
        tmpSignalValue[signal] = "x"
        for ts, value in valueList:
            if float(time) >= ts:
                tmpSignalValue[signal] = value
            else:
                break
    return tmpSignalValue

# def getInputSignalValue(prevTime, currentTime, Vcd, mismatchSignals):
#     prevSignalValue = getTmpSignalValue(prevTime, Vcd)
#     currentSignalValue = getTmpSignalValue(currentTime, Vcd)
#     inputSignalValues = {}
#     for ms in mismatchSignals:
#         inputSignalValue = currentSignalValue
#         inputSignalValue[ms] = prevSignalValue[ms]
#         inputSignalValues[ms] = inputSignalValue
#     return inputSignalValues

def getInputSignalValue(prevSimSignalValue, tmpSimSignalValue, mismatchSignals):
    inputSignalValues = {}
    for ms in mismatchSignals:
        inputSignalValue = tmpSimSignalValue
        inputSignalValue[ms] = prevSimSignalValue[ms]
        inputSignalValues[ms] = inputSignalValue
    return inputSignalValues

def getTimeScale(simVcd):
    timeScale = 0
    for _, sValue in simVcd.items():
        st, _ = sValue[-1]
        if timeScale < st:
            timeScale = st
    return math.ceil(timeScale) + 1

def getNearTimeStamp(timeStamp, simVcd):
    timeStamps = [i for i in range(getTimeScale(simVcd))]
    circle = 1
    for k, v in simVcd.items():
        if "clk" in k or "clock" in k:
            timeStamps = [vi[0] for vi in v]
            circle = 2
            break
    index = timeStamps.index(timeStamp)
    preIndex = index - circle if index - circle > 0 else 0
    postIndex = index + circle if index + circle < len(timeStamps) else len(timeStamps) - 1
    return preIndex, postIndex, timeStamps

# def getMismatchSignal(oracleVcd, simVcd):
#     timeStamps = [i for i in range(getTimeScale(simVcd))]
#     for k, v in simVcd.items():
#         if "clk" in k.lower() or "clock" in k.lower():
#             timeStamps = [vi[0] for vi in v]
#             break
#     for ts in timeStamps:
#         ov = getTmpSignalValue(ts, oracleVcd)
#         sv = getTmpSignalValue(ts, simVcd)
#         mismatchSignal = []
#         for signal, simValue in sv.items():
#             oracleValue = ov[signal]
#             if simValue != oracleValue:
#                 mismatchSignal.append(signal)
#         if mismatchSignal != [] and ts != 0:
#             return ts, mismatchSignal
#     return 0, []

def getMismatchSignal(oracleVcdFile, simVcdFile, timeScale):
    oracleScopes, simScopes = [], []
    oracleVarsDict, simVarsDict = {}, {}
    prevOracleVarsChangeDict, prevSimVarsChangeDict = {}, {}
    tmpOracleVarsChangeDict, tmpSimVarsChangeDict = {}, {}
    oracleAttributesDict, simAttributesDict = {}, {}
    currentOracleTimeStamp, currentSimTimeStamp = 0, 0
    oracleTimeStamp, simTimeStamp = 0, 0
    unitLevel = computeUnitLevel(timeScale[0], timeScale[1])

    f1, f2 = open(oracleVcdFile, "r"), open(simVcdFile, "r")
    headFlag = False
    while True:
        token1 = f1.readline()
        token2 = f2.readline()
        if "$timescale" in token1:
            headFlag = True
        if "$end" in token1 and headFlag:
            break
    while True:
        endFlag = True
        for vcdLine in f1:
            endFlag = False
            vcdBytes = vcdLine.encode('utf-8')
            tokens = list(tokenize(io.BytesIO(vcdBytes)))
            # tlist = [i for i in tokens]
            if len(tokens) == 0:continue
            token = tokens[0]
            if token.kind == TokenKind.SCOPE:
                scope = token.data.ident
                oracleScopes.append(scope)
            if token.kind == TokenKind.VAR:
                if len(oracleScopes) <= 1: continue # exclude the signals in testbench
                if token.data.id_code not in oracleVarsDict:
                    oracleVarsDict[token.data.id_code] = []
                oracleVarsDict[token.data.id_code].append("{}.{}".format(".".join(oracleScopes[1:]), token.data.reference))
                oracleAttributesDict["{}.{}".format(".".join(oracleScopes[1:]), token.data.reference)] = {"size":token.data.size, "bit_index":token.data.bit_index}
                prevOracleVarsChangeDict["{}.{}".format(".".join(oracleScopes[1:]), token.data.reference)] = "'b" + token.data.size * "x"
            if token.kind == TokenKind.UPSCOPE:
                oracleScopes.pop(-1)
            if token.kind == TokenKind.CHANGE_TIME:
                currentOracleTimeStamp = oracleTimeStamp
                oracleTimeStamp = token.data
                if oracleTimeStamp != 0: break
            if token.kind == TokenKind.CHANGE_SCALAR or token.kind == TokenKind.CHANGE_VECTOR:
                if token.data.id_code not in oracleVarsDict: continue
                for signal in oracleVarsDict[token.data.id_code]:
                    dataValue = token.data.value
                    if isinstance(token.data.value, int):
                        dataValue = bin(token.data.value)[2:]
                    if oracleAttributesDict[signal]["size"] != len(dataValue):
                        if dataValue == 'x' or dataValue == 'z':
                            tmpOracleVarsChangeDict[signal] = "'b" + oracleAttributesDict[signal]["size"] * dataValue
                        else:
                            tmpOracleVarsChangeDict[signal] = "'b" + dataValue.zfill(oracleAttributesDict[signal]["size"])
                    else:
                        tmpOracleVarsChangeDict[signal] = "'b" + dataValue
        
        for vcdLine in f2:
            endFlag = False
            vcdBytes = vcdLine.encode('utf-8')
            tokens = list(tokenize(io.BytesIO(vcdBytes)))
            # tlist = [i for i in tokens]
            assert len(tokens) <= 1
            if len(tokens) == 0:continue
            token = tokens[0]
            if token.kind == TokenKind.SCOPE:
                scope = token.data.ident
                simScopes.append(scope)
            if token.kind == TokenKind.VAR:
                if len(simScopes) <= 1: continue # exclude the signals in testbench
                if token.data.id_code not in simVarsDict:
                    simVarsDict[token.data.id_code] = []
                simVarsDict[token.data.id_code].append("{}.{}".format(".".join(simScopes[1:]), token.data.reference))
                simAttributesDict["{}.{}".format(".".join(simScopes[1:]), token.data.reference)] = {"size":token.data.size, "bit_index":token.data.bit_index}
                prevSimVarsChangeDict["{}.{}".format(".".join(simScopes[1:]), token.data.reference)] = "'b" + token.data.size * "x"
            if token.kind == TokenKind.UPSCOPE:
                simScopes.pop(-1)
            if token.kind == TokenKind.CHANGE_TIME:
                currentSimTimeStamp = simTimeStamp
                simTimeStamp = token.data
                if simTimeStamp != 0: break
            if token.kind == TokenKind.CHANGE_SCALAR or token.kind == TokenKind.CHANGE_VECTOR:
                if token.data.id_code not in simVarsDict: continue
                for signal in simVarsDict[token.data.id_code]:
                    dataValue = token.data.value
                    if isinstance(token.data.value, int):
                        dataValue = bin(token.data.value)[2:]
                    if simAttributesDict[signal]["size"] != len(dataValue):
                        if dataValue == 'x' or dataValue == 'z':
                            tmpSimVarsChangeDict[signal] = "'b" + simAttributesDict[signal]["size"] * dataValue
                        else:
                            tmpSimVarsChangeDict[signal] = "'b" + dataValue.zfill(simAttributesDict[signal]["size"])
                    else:
                        tmpSimVarsChangeDict[signal] = "'b" + dataValue

        mismatchSignals = []
        if currentOracleTimeStamp != currentSimTimeStamp:
            if currentOracleTimeStamp > currentSimTimeStamp:
                for signal, value in tmpSimVarsChangeDict.items():
                    if value != prevOracleVarsChangeDict[signal]:
                        mismatchSignals.append(signal)
                assert len(mismatchSignals) > 0
                f1.close()
                f2.close()
                return currentSimTimeStamp*unitLevel, mismatchSignals, simAttributesDict, prevSimVarsChangeDict, tmpSimVarsChangeDict, prevOracleVarsChangeDict
            else:
                for signal, value in prevSimVarsChangeDict.items():
                    if value != tmpOracleVarsChangeDict[signal]:
                        mismatchSignals.append(signal)
                assert len(mismatchSignals) > 0
                f1.close()
                f2.close()
                return currentSimTimeStamp*unitLevel, mismatchSignals, simAttributesDict, prevSimVarsChangeDict, prevSimVarsChangeDict, tmpOracleVarsChangeDict
        else:
            for signal, value in tmpSimVarsChangeDict.items():
                if signal in tmpOracleVarsChangeDict and value != tmpOracleVarsChangeDict[signal]:
                    mismatchSignals.append(signal)
            if len(mismatchSignals) > 0:
                f1.close()
                f2.close()
                return currentSimTimeStamp*unitLevel, mismatchSignals, simAttributesDict, prevSimVarsChangeDict, tmpSimVarsChangeDict, tmpOracleVarsChangeDict
        
        prevOracleVarsChangeDict = copy.deepcopy(tmpOracleVarsChangeDict)
        prevSimVarsChangeDict = copy.deepcopy(tmpSimVarsChangeDict)

        if endFlag:
            f1.close()
            f2.close()
            return 0, [], {}, {}, {}