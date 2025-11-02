import sys

sys.path.extend(['.', '..'])
import os, json
from matplotlib_venn import venn3
import matplotlib.pyplot as plt

from loguru import logger
from utils.postprocessing import extract_assertion_from_response
from utils.file import load_jsonl_file_as_dict

code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
output_base = os.path.join(code_base, 'results')

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


if __name__ == '__main__':
    # Read output files.
    a = load_jsonl_file_as_dict(
        os.path.join(output_base, 'no_judge-first_round_speak_up-NaiveGenerator-results.jsonl'))

    b = load_jsonl_file_as_dict(
        os.path.join(output_base, 'no_judge-first_round_speak_up-RAGGenerator-results.jsonl'))

    c = load_jsonl_file_as_dict(
        os.path.join(output_base, 'no_judge-first_round_speak_up-FourStepCoTGenerator-results.jsonl'))

    # Make sure the number of instances are the same.
    assert len(a) == len(b) == len(c)

    # Collect all instance ids.
    all_instance_ids = list(a.keys())
    accuracy_results, correct_by_member = summary_results(all_instance_ids, {'naive': a, 'rag': b, 'fscot': c})

    # Debate part.
    # debated_naive_results = load_jsonl_file_as_dict(
    #     os.path.join(output_base, 'no_judge-debate-NaiveGenerator-results.jsonl'))
    #
    # debated_rag_results = load_jsonl_file_as_dict(
    #     os.path.join(output_base, 'no_judge-debate-RAGGenerator-results.jsonl'))
    #
    # debated_fscot_results = load_jsonl_file_as_dict(
    #     os.path.join(output_base, 'no_judge-debate-FourStepCoTGenerator-results.jsonl'))
    #
    # debated_instance_ids = [id for id in all_instance_ids if len(accuracy_results[id]['members_corrected']) != 3]
    # debated_accuracy_results, corrected_by_member_after_debate = summary_results(ids=debated_instance_ids,
    #                                                                              response_dict={
    #                                                                                  'naive': debated_naive_results,
    #                                                                                  'rag': debated_rag_results,
    #                                                                                  'fscot': debated_fscot_results
    #                                                                              })

    # Summary
    total = len(all_instance_ids)
    all_corrected = sum([1 for id in all_instance_ids if len(accuracy_results[id]['members_corrected']) == 3])
    all_assertEquals = sum([1 for id in accuracy_results.keys() if accuracy_results[id]['type'] == 'assertEquals'])
    all_assertBoolean = sum([1 for id in accuracy_results.keys() if accuracy_results[id]['type'] == 'assertBoolean'])
    all_assertNullValues = sum([1 for id in accuracy_results.keys() if accuracy_results[id]['type'] == 'assertNullValues'])
    print(f'=== Overall accuracy: {all_corrected}/{total} = {all_corrected / total:.2%}. ===')
    upper_bound = sum([1 for id in all_instance_ids if len(accuracy_results[id]['members_corrected']) != 0])
    print(f'=== Upper bound: {upper_bound}/{total} = {upper_bound / total:.2%}. ===')
    print(f'=== Accuracy by Members (Upper Bound): === ')
    unique_by_members = {
        'Naive': len(
            correct_by_member['Naive']['all'].difference(correct_by_member['RAG']['all']).difference(correct_by_member['FSCoT']['all'])),
        'RAG': len(
            correct_by_member['RAG']['all'].difference(correct_by_member['Naive']['all']).difference(correct_by_member['FSCoT']['all'])),
        'FSCoT': len(
            correct_by_member['FSCoT']['all'].difference(correct_by_member['Naive']['all']).difference(correct_by_member['RAG']['all'])),
    }
    for member, results in correct_by_member.items():
        ids = results['all']
        print(f'== {member}: {len(ids)}/{total} = {len(ids) / total:.2%}, unique: {unique_by_members[member]}')
        print(f"By Assertion Type: ")
        print(f"assertEquals {len(results['assertEquals'])}/{all_assertEquals}")
        print(f"assertBoolean {len(results['assertBoolean'])}/{all_assertBoolean}")
        print(f"assertNullValues {len(results['assertNullValues'])}/{all_assertNullValues}")
        print('== ')
    print(f'============================ ')

    # Drawing pictures for difference analysis.
    # plt.figure()
    # venn = venn3((
    #     correct_by_member['Naive']['all'],
    #     correct_by_member['RAG']['all'],
    #     correct_by_member['FSCoT']['all'],
    # ), set_labels=('Naive', 'RAG', 'FSCoT'))
    # plt.show()

    pass
