import csv
import json

from utils.CodeRetriever import bm25_similarity
from utils.StaticAnalyzer import parseMethods

def csvToDict(file):
    data = []
    with open(file, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            data.append(row)
    return data


if __name__ == '__main__':
    validInputs = []
    idx = 0
    inputData = csvToDict('resources/inputs.csv')
    metaData = csvToDict('resources/meta.csv')
    index = 0
    for input, meta in zip(inputData, metaData):
        retrieveSource = [input['test_prefix'] for i, input in enumerate(inputData) if i !=index]
        if meta['assertion_bug'] != '0':
            if all(validAssertion not in meta['assertion_lbl'] for validAssertion in
                   ['assertEquals', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull']):
                pass
            else:
                retrievedTestCase = ''
                sim = -1
                for oneSource in retrieveSource:
                    curSim = bm25_similarity(input['test_prefix'], oneSource)
                    if curSim > sim:
                        sim = curSim
                        retrievedTestCase = oneSource
                try:
                    validInputs.append({
                        'bug_id':f"{meta['project']}_{meta['bug_num']}",
                        'id': idx,
                        'focal_method_name': parseMethods(f"public class A{{{input['focal_method']}}}")[0]['method_name'],
                        'focal_method': input['focal_method'],
                        'test_case': input['test_prefix'],
                        'expected_assertion': meta['assertion_lbl'],
                        'retrieved_test_case': retrievedTestCase
                    })
                    idx += 1
                except:
                    print(1)
                passp
        index +=1
        pass
    print(len(validInputs))
    assert index == len(inputData)
    with open('resources/evosuite_integration_inputs.jsonl', 'w', encoding='utf-8') as writer:
        for input in validInputs:
            writer.write(json.dumps(input, ensure_ascii=False) + '\n')
    pass
