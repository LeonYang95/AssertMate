import json
import os
import pickle
import sys
from collections import Counter

from tqdm import tqdm

sys.path.extend(['.', '..'])

from configuration import code_base, d4j_proj_base
from utils.UTRunner import Defects4jRunner
from utils.StaticAnalyzer import *
from utils.Preprocess import *
from utils.IOUtils import *
from utils.CodeRetriever import bm25_similarity

if __name__ == '__main__':
    statistics = Counter()
    with open(os.path.join(code_base, 'resources/test_src.json'), 'rb') as reader:
        pathMapping = json.load(reader)

    runner = Defects4jRunner(d4j_proj_base)
    writer = open(os.path.join(code_base, 'outputs/llm_integration_generation_inputs.jsonl'), 'w', encoding='utf-8')
    # 读取输入数据
    inFile = os.path.join(code_base, 'resources/LLMUTGen_example.jsonl')
    inputs = []
    with open(inFile, 'r', encoding='utf-8') as reader:
        for line in reader.readlines():
            inputs.append(json.loads(line.strip()))

    assertGenInputs = []

    # 修改多进程入口
    for input in tqdm(inputs):
        # 找到 bugid 和对应的路径
        bugID = input['bug_id']
        testSourceDir = pathMapping[bugID]['test']
        generatedTestClass = extractTestClass(input['generated_test_class'])
        importsToAdd = getImportsFromFocalClass(input['focal_class']['text'])
        className = parseClassName(generatedTestClass)
        classStr = importsToAdd + '\n' + generatedTestClass
        newTestFile = os.path.join(d4j_proj_base, f'{bugID}/fixed/{testSourceDir}/{className}.java')

        # 写测试类
        writeTestClass(newTestFile, classStr)
        methods = parseMethods(classStr, requiredModifier='@Test')
        statistics['total'] += len(methods)
        # 编译
        compileStatus, compileErrMsgs, compileErrLines = runner.runCompile(bugID, 'fixed')
        if not compileStatus:

            # 根据编译结果进行 refine
            newClassStr, correctedMethods = runner.refineTestClassByErrorLines(classStr, compileErrLines)
            if not correctedMethods:
                continue

            # 再编译
            writeTestClass(newTestFile, newClassStr)
            compileStatus, compileErrMsgs, compileErrLines = runner.runCompile(bugID, 'fixed')
            if not compileStatus:
                # 如果还有问题，那么就去掉这条数据
                continue
            else:
                statistics['compiled'] += len(correctedMethods)
        else:
            newClassStr = classStr
            correctedMethods = methods
            statistics['compiled'] += len(correctedMethods)
        # 运行测试，收集测试结果
        execStatus, execErrMsgs, failingTests = runner.runTest(bugID, 'fixed')
        if execStatus:
            statistics['passed'] += len(correctedMethods)
        else:
            statistics['passed'] += len(correctedMethods) - len(failingTests)

            for failingTest in failingTests:
                # 有测试失败的测试用例，记录为测试断言生成任务的输入
                newInput = pickle.loads(pickle.dumps(input))
                newInput['test_case_signature'] = failingTest
                testCaseName = failingTest.split('::')[1]
                newInput['test_case'] = \
                    [m['method_text'] for m in correctedMethods if m['method_name'] == testCaseName][0]

                # 检索相似的测试用例用作 RAG 的输入
                retrieveSource = [m['method_text'] for m in correctedMethods if m['method_name'] != testCaseName]
                retrievedTestCase = ''
                sim = -1
                for oneSource in retrieveSource:
                    curSim = bm25_similarity(newInput['test_case'], oneSource)
                    if curSim > sim:
                        sim = curSim
                        retrievedTestCase = oneSource
                newInput['retrieved_test_case'] = retrievedTestCase

                newInput['parent_test_case'] = newInput['test_case']
                newInput['test_file'] = newTestFile
                newInput.pop('generated_test_class')
                writer.write(json.dumps(newInput, ensure_ascii=False) + '\n')
    writer.close()
    print(statistics)
    pass
