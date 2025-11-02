import sys

sys.path.extend(['.', '..'])
import os
import json
import yaml
import multiprocessing
import random
from dotmap import DotMap
from tqdm import tqdm

from agents.Generator_Impls import NaiveGenerator, RAGGenerator, FourStepCoTGenerator
from agents.base.llm import DeepSeek
from utils.postprocessing import extract_assertion_from_response
from utils.file import load_jsonl_file_as_dict

random.seed(888)

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
    config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
model = DeepSeek(config)

# if debugging mode.
debug = False

def summary_results(ids, response_dict):
    # global accuracy_results, correct_by_member, id, expected_value, member
    naive_results = response_dict['naive']
    rag_results = response_dict['rag']
    fscot_results = response_dict['fscot']
    accuracy_results = {}
    correct_by_member = {

    }

    for id in ids:
        if id not in accuracy_results.keys():
            accuracy_results[id] = {
                "members_corrected": [],
                'type':''
            }
        # specify output instances for each strategy
        naive_result = naive_results[id]
        rag_result = rag_results[id]
        fscot_result = fscot_results[id]

        # make sure all the instances are in the same page.
        assert naive_result['expected_value'] == rag_result['expected_value'] == fscot_result['expected_value']
        expected_value = naive_result['expected_value']

        if expected_value in ['assertTrue', 'assertFalse']:
            accuracy_results[id]['type']= 'assertBoolean'
        elif expected_value in ['assertNull', 'assertNotNull']:
            accuracy_results[id]['type'] = 'assertNullValues'
        else:
            accuracy_results[id]['type']= 'assertEquals'


        # extract assertions
        naive_response = extract_assertion_from_response(naive_result['history'][-1]['content'])
        rag_response = extract_assertion_from_response(rag_result['history'][-1]['content'])
        fscot_response = extract_assertion_from_response(fscot_result['history'][-1]['content'])

        # check if the expected value is in the response
        for m, response in zip(['Naive', 'RAG', 'FSCoT'], [naive_response, rag_response, fscot_response]):
            if m not in correct_by_member.keys():
                correct_by_member[m] = {'all': set(),
                                    'assertEquals': set(),
                                    'assertBoolean': set(),
                                    'assertNullValues': set()}

            if expected_value in response:
                accuracy_results[id]['members_corrected'].append(m)
                correct_by_member[m]['all'].add(id)
                if expected_value in ['assertTrue', 'assertFalse']:
                    correct_by_member[m]['assertBoolean'].add(id)
                elif expected_value in ['assertNull', 'assertNotNull']:
                    correct_by_member[m]['assertNullValues'].add(id)
                else:
                    correct_by_member[m]['assertEquals'].add(id)

            else:
                if (expected_value == 'true' and 'assertTrue' in response) or (
                        expected_value == 'false' and 'assertFalse' in response):
                    accuracy_results[id]['members_corrected'].append(m)
                    correct_by_member[m]['all'].add(id)
                    if expected_value in ['assertTrue', 'assertFalse']:
                        correct_by_member[m]['assertBoolean'].add(id)
                    elif expected_value in ['assertNull', 'assertNotNull']:
                        correct_by_member[m]['assertNullValues'].add(id)
                    else:
                        correct_by_member[m]['assertEquals'].add(id)
                        pass
                    pass
                pass
            pass
        pass
    return accuracy_results, correct_by_member


def discussion(data, pid, output_base):
    global debug
    members = [
        NaiveGenerator(model),
        # CoTGenerator(model),
        RAGGenerator(model),
        # AutoCoTGenerator(model),
        FourStepCoTGenerator(model)
    ]

    if debug:
        data = data[:10]

    record = {}
    for member in members:
        member_id = member.__class__.__name__
        writer = open(os.path.join(output_base, f'no_judge-debate-{member_id}-results-{pid}.jsonl'), 'w',
                      encoding='utf-8')
        if member_id not in record.keys():
            record[member_id] = {}
        for instance in tqdm(data, desc=f'{member_id} is debating'):
            id, focal_method, test_prefix, expected_value, statements, history = instance
            prefix = None
            if expected_value in ['assertTrue','assertFalse','assertNull','assertNotNull']:
                prefix = 'I think the answer should be:\n```java\nassert'
            else:
                prefix = 'I think the answer should be:\n```java\nassertEquals('
            refined_answer = member.debate(
                focal_method=focal_method,
                test_prefix=test_prefix,
                statements=statements,
                history=history,
                prefix=prefix
            )
            writer.write(json.dumps({
                'id': id,
                'focal_method': focal_method,
                'test_prefix': test_prefix,
                'expected_value': expected_value,
                'debated_answer': refined_answer,
                'history': member.history,
            }, ensure_ascii=False) + '\n')
            member.clear_history()
        writer.close()


def record_results(num_process: int):
    second_round_naive_result = os.path.join(output_base, 'no_judge-debate-NaiveGenerator-results.jsonl')
    second_round_naive_result_formatter = os.path.join(output_base,
                                                       'no_judge-debate-NaiveGenerator-results-{}.jsonl')
    _merge_multiprocessing_record_files(num_process, second_round_naive_result,
                                        second_round_naive_result_formatter)

    second_round_rag_result = os.path.join(output_base, 'no_judge-debate-RAGGenerator-results.jsonl')
    second_round_rag_result_formatter = os.path.join(output_base,
                                                     'no_judge-debate-RAGGenerator-results-{}.jsonl')
    _merge_multiprocessing_record_files(num_process, second_round_rag_result,
                                        second_round_rag_result_formatter)
    second_round_rag_result = os.path.join(output_base, 'no_judge-debate-FourStepCoTGenerator-results.jsonl')
    second_round_rag_result_formatter = os.path.join(output_base,
                                                     'no_judge-debate-FourStepCoTGenerator-results-{}.jsonl')
    _merge_multiprocessing_record_files(num_process, second_round_rag_result,
                                        second_round_rag_result_formatter)

    pass


def _merge_multiprocessing_record_files(num_process: int, output_file: str, input_filename_formatter: str):
    with open(output_file, 'w', encoding='utf-8') as writer:
        for pid in range(num_process):
            input_file = input_filename_formatter.format(pid)
            if os.path.exists(input_file):
                with open(input_file, 'r', encoding='utf-8') as reader:
                    for line in reader.readlines():
                        writer.write(line)
                os.remove(input_file)
    pass


if __name__ == '__main__':
    output_base = os.path.join(code_base, 'results')
    a = load_jsonl_file_as_dict(
        os.path.join(output_base, 'no_judge-first_round_speak_up-NaiveGenerator-results.jsonl'))
    b = load_jsonl_file_as_dict(os.path.join(output_base, 'no_judge-first_round_speak_up-RAGGenerator-results.jsonl'))
    c = load_jsonl_file_as_dict(
        os.path.join(output_base, 'no_judge-first_round_speak_up-FourStepCoTGenerator-results.jsonl'))
    assert len(a) == len(b) == len(c)
    all_ids = list(a.keys())
    accuracy_results, _ =summary_results(all_ids, {'naive': a, 'rag': b, 'fscot': c})

    data = []
    agreed = 0
    for id, record in accuracy_results.items():
        if len(record['members_corrected']) == 3:
            agreed +=1
        else:
            naive_result = a[id]
            rag_result = b[id]
            fscot_result = c[id]

            focal_method = naive_result['focal_method']
            test_prefix = naive_result['test_prefix']
            statements = {
                'user1': rag_result['history'][-1]['content'],
                'user2': naive_result['history'][-1]['content'],
                'user3': fscot_result['history'][-1]['content'] + '\n' + fscot_result['history'][-3]['content']
            }
            history = {
                'user1': rag_result['history'],
                'user2': naive_result['history'],
                'user3': fscot_result['history']
            }
            data.append((id, focal_method, test_prefix, naive_result['expected_value'], statements, history))
            pass
    print(f'Agreed: {agreed}, Disagreed: {len(data)}.')
    num_process = 10
    num_per_chunk = len(data) // num_process
    num_per_chunk += 1
    chunks = [data[i * num_per_chunk: (i + 1) * num_per_chunk] for i in range(num_process)]
    assert len(chunks) == num_process

    if debug:
        # discussion(chunks[4], 0, output_base)
        record_results(1)
        pass
    else:
        jobs = []
        for pid, chunk in enumerate(chunks):
            p = multiprocessing.Process(target=discussion, args=(chunk, pid, output_base))
            jobs.append(p)
            p.start()

        for job in jobs:
            job.join()
        record_results(num_process)
    pass
