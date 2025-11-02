import sys

sys.path.extend(['.', '..'])
import os, json
from agents.Generator_Impls import *
from loguru import logger
from utils.file import load_jsonl_file
from utils.postprocessing import extract_assertion_from_response


def load_jsonl_file_as_dict(file_path) -> dict:
    if not os.path.exists(file_path):
        logger.error(f'Target JSONL file {file_path} does not exist.')
        return {}
    else:
        res = {}
        with open(file_path, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                line = line.strip()
                if line == '':
                    continue
                else:
                    d = json.loads(line)
                    res[d['id']] = d['record']
        return res


def load_first_round_jsonl_file_as_dict(file_path) -> dict:
    if not os.path.exists(file_path):
        logger.error(f'Target JSONL file {file_path} does not exist.')
        return {}
    else:
        res = {}
        with open(file_path, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                line = line.strip()
                if line == '':
                    continue
                else:
                    d = json.loads(line)
                    res[d['id']] = pickle.loads(pickle.dumps(d))
        return res


code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
members = [
    'NaiveGenerator',
    'RAGGenerator',
    'FourStepCoTGenerator',
    'AutoCoTGenerator'
]
correct_by_member = {
    'Naive': set(),
    'RAG': set(),
    'FSCoT': set(),
    'AutoCoT': set()
}
if __name__ == '__main__':
    final_correct = 0
    at_least_one_correct = set()
    unanimous_but_wrong = set()
    output_base = os.path.join(code_base, 'results')

    naive_results = load_jsonl_file(
        os.path.join(output_base, 'no_judge-first_round_speak_up-NaiveGenerator-results.jsonl'))

    rag_results = load_jsonl_file(os.path.join(output_base, 'no_judge-first_round_speak_up-RAGGenerator-results.jsonl'))

    fscot_results = load_jsonl_file(
        os.path.join(output_base, 'no_judge-first_round_speak_up-FourStepCoTGenerator-results.jsonl'))

    # autocot_results = load_jsonl_file(
    #     os.path.join(output_base,'no_judge-first_round_speak_up-AutoCoTGenerator-results.jsonl'))
    assert len(naive_results) == len(rag_results) == len(fscot_results)  # == len(autocot_results)
    total = len(naive_results)
    for i in range(len(naive_results)):
        assert naive_results[i]['id'] == rag_results[i]['id'] == fscot_results[i]['id']
        naive_result = naive_results[i]
        rag_result = rag_results[i]
        fscot_result = fscot_results[i]
        # autocot_result = autocot_results[i]
        assert naive_result['id'] == rag_result['id'] == fscot_result['id']
        res_set = set()
        naive_response = extract_assertion_from_response(naive_result['history'][-1]['content'])
        rag_response = extract_assertion_from_response(rag_result['history'][-1]['content'])
        fscot_response = extract_assertion_from_response(fscot_result['history'][-1]['content'])
        # autocot_response  = extract_assertion_from_response(autocot_result['history'][-1]['content'])
        res_set.add(naive_response)
        res_set.add(rag_response)
        res_set.add(fscot_response)
        # res_set.add(autocot_response)
        if len(res_set) == 1:
            # They have reached a unanimous conclusion
            if naive_result['expected_value'] in naive_response:
                final_correct += 1
                at_least_one_correct.add(naive_result['id'])
                correct_by_member['Naive'].add(naive_result['id'])
                correct_by_member['RAG'].add(naive_result['id'])
                correct_by_member['FSCoT'].add(naive_result['id'])
                correct_by_member['AutoCoT'].add(naive_result['id'])
                pass
            else:
                unanimous_but_wrong.add(naive_result['id'])
            pass
        else:
            if any([
                naive_result['expected_value'] in response for response in [
                    naive_response, rag_response, fscot_response  # , autocot_response
                ]
            ]):
                if naive_result['expected_value'] in naive_response:
                    correct_by_member['Naive'].add(naive_result['id'])
                    pass
                if naive_result['expected_value'] in rag_response:
                    correct_by_member['RAG'].add(naive_result['id'])

                    pass
                if naive_result['expected_value'] in fscot_response:
                    correct_by_member['FSCoT'].add(naive_result['id'])
                    pass
                # if naive_result['expected_value'] in autocot_response:
                #     correct_by_member['AutoCoT'].add(naive_result['id'])
                #     pass
                at_least_one_correct.add(naive_result['id'])
                pass
            pass

    still_possible = 0
    naive_results = load_jsonl_file(
        os.path.join(output_base, 'no_judge-debate-NaiveGenerator-results.jsonl'))
    rag_results = load_jsonl_file(os.path.join(output_base, 'no_judge-debate-RAGGenerator-results.jsonl'))
    fscot_results = load_jsonl_file(
        os.path.join(output_base, 'no_judge-debate-FourStepCoTGenerator-results.jsonl'))
    assert len(naive_results) == len(rag_results) == len(fscot_results)
    for i in range(len(naive_results)):
        assert naive_results[i]['id'] == rag_results[i]['id'] == fscot_results[i]['id']
        naive_result = naive_results[i]
        rag_result = rag_results[i]
        fscot_result = fscot_results[i]
        assert naive_result['id'] == rag_result['id'] == fscot_result['id']
        res_set = set()
        naive_response = extract_assertion_from_response(naive_result['history'][-1]['content'])
        rag_response = extract_assertion_from_response(rag_result['history'][-1]['content'])
        fscot_response = extract_assertion_from_response(fscot_result['history'][-1]['content'])
        res_set.add(naive_response)
        res_set.add(rag_response)
        res_set.add(fscot_response)
        if len(res_set) == 1:
            # They have reached a unanimous conclusion
            if naive_result['expected_value'] in naive_response:
                final_correct += 1
                pass
            else:
                unanimous_but_wrong.add(naive_result['id'])
                print(naive_result['id'])
            pass
        else:
            if sum([
                1 if naive_result['expected_value'] in response else 0 for response in [
                    naive_response, rag_response, fscot_response
                ]
            ]) >= 2:

                if naive_result['expected_value'] in naive_response:
                    correct_by_member['Naive'].add(naive_result['id'])
                    pass
                if naive_result['expected_value'] in rag_response:
                    correct_by_member['RAG'].add(naive_result['id'])
                    pass
                if naive_result['expected_value'] in fscot_response:
                    correct_by_member['FSCoT'].add(naive_result['id'])
                    pass

                final_correct += 1
                pass
            elif any([
                naive_result['expected_value'] in response for response in [
                    naive_response, rag_response, fscot_response
                ]
            ]):
                still_possible += 1
                print(f'===Still possible:{naive_result["id"]}===')
            else:
                pass
            pass

    print(f'Final Correct: {final_correct}/{total} ({final_correct / total:.2%})')
    print(f'Still Possible: {still_possible}/{total} ({still_possible / total:.2%})')
    print(f'Unanimous But Wrong: {len(unanimous_but_wrong)}/{total} ({len(unanimous_but_wrong) / total:.2%})')
    print(f'At Least One Correct: {len(at_least_one_correct)}/{total} ({len(at_least_one_correct) / total:.2%})')
    print(f'===Wrong but was originally right:==')
    print('\n'.join(unanimous_but_wrong.intersection(at_least_one_correct)))
    print('===Correct by Members:===')
    print(f'===Naive: {len(correct_by_member["Naive"])}===')
    # print('\n'.join(correct_by_member["Naive"]))

    print(f'===RAG: {len(correct_by_member["RAG"])}===')
    # print('\n'.join(correct_by_member["RAG"]))

    print(f'===FSCoT: {len(correct_by_member["FSCoT"])}===')
    # print('\n'.join(correct_by_member["FSCoT"]))

    # print(f'===AutoCoT: {len(correct_by_member["AutoCoT"])}===')
    # print('\n'.join(correct_by_member["AutoCoT"]))
    from matplotlib_venn import venn3
    import matplotlib.pyplot as plt

    plt.figure()
    venn = venn3((
        correct_by_member['Naive'],
        correct_by_member['RAG'],
        correct_by_member['FSCoT'],
    ), set_labels=('Naive', 'RAG', 'FSCoT'))
    plt.show()
    pass
