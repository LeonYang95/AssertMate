import hashlib
import json
import os
import subprocess
import sys
import pickle

from collections import Counter

from loguru import logger

sys.path.extend(['.', '..'])
from utils.JavaAnalyzer import extract_assertion_from_response, replace_assertion, find_params_in_assertion

boolean_expected_value = ['assertTrue', 'assertFalse']
nullable_expected_value = ['assertNull', 'assertNotNull']
valid_bug_ids = "Closure_144,Closure_80,Closure_142,Closure_169,Closure_66,Closure_56,Compress_15,Compress_40,Compress_16,Compress_6,Compress_11,Compress_47,Compress_42,Compress_13,Codec_4,Chart_20,Chart_12,Chart_11,Chart_16,Chart_8,Chart_15,Cli_32,Cli_19,Cli_18,Cli_17,Math_69,Math_37,Math_99,Math_5,Math_96,Math_11,Math_72,Math_94,Math_6,Math_27,Math_30,Math_57,Math_47,Math_63,Math_74,Math_46,Math_92,Math_15,Time_26,Time_15,Time_17,Time_12,Time_14,Lang_3,Lang_34,Lang_4,Lang_36,Lang_40,Lang_15,Lang_53,Lang_29,Lang_14,Lang_7,Lang_30,Lang_24,Lang_11,Jsoup_58,Jsoup_11,Jsoup_45,Jsoup_73,Jsoup_67,Jsoup_48,Jsoup_65,Jsoup_77,Jsoup_31,Jsoup_3,Jsoup_16,Jsoup_18,Jsoup_4,Jsoup_28,Jsoup_52,Jsoup_76,Jsoup_64,Jsoup_33,Jsoup_20,Jsoup_1,Jsoup_42,Jsoup_15,Jsoup_24,Jsoup_25,Jsoup_61,Jsoup_44,Jsoup_17,Jsoup_69,Jsoup_93,Jsoup_14,Jsoup_38,Jsoup_39,Jsoup_83,Jsoup_35,Jsoup_21,Jsoup_82,Jsoup_9,Jsoup_30,Jsoup_27,Jsoup_2,Jsoup_51,Jsoup_75,Csv_3,Csv_14,Csv_15,Mockito_30,Mockito_26,Mockito_11,Mockito_24,Collections_26,Collections_27".split(
    ',')
d4j_project_base = '/data/yanglin/data/defects4j/d4j_projects'
comparison_file = '/data/yanglin/UTGen_LLM/outputs/defects4j_inputs.jsonl'
comparison_group = []
with open(comparison_file, 'r', encoding='utf-8') as reader:
    for line in reader.readlines():
        obj = json.loads(line.strip())
        obj['test_file'] = obj['test_file'].replace('/Users/yanglin/Documents/Projects','/data/yanglin')
        obj['source_file'] = obj['source_file'].replace('/Users/yanglin/Documents/Projects','/data/yanglin')
        comparison_group.append(obj)


def bug_detect(instances, response_dict):
    global comparison_group, valid_bug_ids
    failed_ids = []
    failed_reasons = Counter()
    for instance in instances:
        comparison_instance = comparison_group[instance.id]
        # assert hashlib.md5(comparison_instance['focal_method'].encode('utf-8')).hexdigest() == instance['focal_method']
        bug_id = comparison_instance['bug_id']
        if bug_id not in valid_bug_ids:
            continue
        if bug_id in ['Mockito_18', 'Mockito_1']:
            continue
        test_case_file = comparison_instance['test_file'].replace('fixed', 'buggy')
        expected_value = instance.expected_value
        # 替换掉原本的测试断言
        generated_assertion = response_dict[instance.id]
        if generated_assertion == '':
            continue
        if expected_value in boolean_expected_value or expected_value in nullable_expected_value:
            new_test_case = instance.test_prefix.replace('<AssertionPlaceHolder>', generated_assertion)
        else:
            new_test_case = replace_assertion(instance.test_prefix, generated_assertion)
            if not new_test_case:
                continue
        new_test_class = comparison_instance['test_class']['text'].replace(comparison_instance['parent_test_case'],
                                                                           new_test_case)
        try:
            logger.info(f'bug id :{bug_id}')
            # backup original test class
            original_test_class = ''
            with open(test_case_file, 'r', encoding='utf-8') as reader:
                original_test_class += reader.read()

            with open(test_case_file, 'w', encoding='utf-8') as writer:
                writer.write(new_test_class)

            os.chdir(os.path.join(d4j_project_base, bug_id, 'buggy'))
            ret = subprocess.run('defects4j test', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            res_output = ret.stdout.decode('utf-8')
            if res_output == 'Failing tests: 0\n':
                pass
            else:
                logger.info('Failed')
                recorded = False
                if os.path.exists('failing_tests'):
                    with open('failing_tests', 'r', encoding='utf-8') as reader:
                        for line in reader.readlines():
                            if not line.startswith(' '):
                                if 'Assertion' in line:
                                    failed_ids.append(instance.id)
                                    failed_reasons['assertion_error'] += 1
                                    recorded = True
                                    break
                        if not recorded:
                            failed_reasons['other'] += 1
                else:
                    failed_reasons['no_failing_test_file'] += 1

        finally:
            # No matter what, write back the original class.
            # write_test_class(bug_id, 'fixed', comparison_instance['test_class']['text'])
            with open(test_case_file, 'w', encoding='utf-8') as writer:
                writer.write(original_test_class)

    logger.info(f'==== Failed Bug ids ====')
    logger.info(f'{failed_ids}')
    logger.info('==== Top5 Failed Reasons====')
    for reason, count in failed_reasons.most_common(5):
        print(reason, count)
    return list(failed_ids)


def cal_pass_rate(instances, response_dict):
    global comparison_group
    corrected_ids = set()
    passed_ids = set()
    passed = 0
    total = 0
    regarded_as_passed = 0
    corrected = 0
    compiled = 0
    for instance in instances:
        total += 1
        comparison_instance = comparison_group[instance.id]
        assert hashlib.md5(comparison_instance['focal_method'].encode('utf-8')).hexdigest() == hashlib.md5(
            instance.focal_method.encode('utf-8')).hexdigest()

        # for v_100 data only
        # assert hashlib.md5(comparison_instance['focal_method'].encode('utf-8')).hexdigest() == instance['focal_method']


        bug_id = comparison_instance['bug_id']

        if bug_id in ['Mockito_18', 'Mockito_1','Mockito_22','Math_100','Mockito_24']:
            total -= 1
            continue

        test_case_file = comparison_instance['test_file']
        expected_value = instance.expected_value
        # 替换掉原本的测试断言
        generated_assertion = extract_assertion_from_response(
            response_dict[instance.id]
            )
        if generated_assertion == '':
            continue
        is_correct = False
        if expected_value in generated_assertion:
            corrected += 1
            is_correct = True
            corrected_ids.add(instance.id)
        if expected_value in boolean_expected_value or expected_value in nullable_expected_value:
            new_test_case = instance.test_prefix.replace('<AssertionPlaceHolder>', generated_assertion)  if instance.test_prefix else comparison_instance['test_prefix'].replace('<AssertionPlaceHolder>', generated_assertion)
        else:
            new_test_case = replace_assertion(instance.test_prefix, generated_assertion) if instance.test_prefix else replace_assertion(comparison_instance['test_prefix'], generated_assertion)
            if not new_test_case:
                continue
        new_test_class = comparison_instance['test_class']['text'].replace(comparison_instance['parent_test_case'],
                                                                           new_test_case)
        try:
            # write_test_class(bug_id, 'fixed', new_test_class)
            logger.info(f'bug id :{bug_id}')
            with open(test_case_file, 'w', encoding='utf-8') as writer:
                writer.write(new_test_class)
            os.chdir(os.path.join(d4j_project_base, bug_id, 'fixed'))
            ret = subprocess.run('defects4j test', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            res_output = ret.stdout.decode('utf-8')
            if res_output == 'Failing tests: 0\n':
                passed += 1
                compiled +=1
                passed_ids.add(instance.id)
                logger.info('Passed')
                if not is_correct and expected_value not in boolean_expected_value and expected_value not in nullable_expected_value:
                    logger.debug(expected_value + ' vs. ' + generated_assertion)
            else:
                logger.info('Failed')
                if ret.returncode == 0:
                    compiled +=1
                if is_correct:
                    if expected_value in boolean_expected_value or expected_value in nullable_expected_value:
                        if generated_assertion.startswith(expected_value):
                            logger.warning(
                                f'The expected assertion generated for {bug_id} is correct, but failed in the test.')
                            regarded_as_passed += 1
                            passed_ids.add(instance.id)
                    else:
                        if '<expected_value>' in generated_assertion:
                            logger.error(
                                f'{bug_id} failed execution because expected value is not replaced. Remove from the correct set.')
                        else:
                            try:
                                params = find_params_in_assertion(generated_assertion)
                                if expected_value in params:
                                    logger.warning(
                                        f'The generated expected value({generated_assertion}) for {bug_id} is correct ({expected_value}), but failed in the test.')
                                    regarded_as_passed += 1
                                    passed_ids.add(instance.id)
                                else:
                                    corrected -= 1
                                    corrected_ids.remove(instance.id)
                                    logger.error(bug_id)
                                    logger.error(
                                        f"The expected value is {expected_value}, but got the generated assertion {generated_assertion}.")
                            except:
                                corrected -= 1
                                corrected_ids.remove(instance.id)
                                logger.error(bug_id)
                                logger.error(
                                    f"The expected value is {expected_value}, but got the generated assertion {generated_assertion}.")
                else:
                    # if ret.returncode == 0:
                    #     print(ret.stdout.decode('utf-8'))
                    # else:
                    #     print(ret.stderr.decode('utf-8'))
                    pass
        finally:
            # No matter what, write back the original class.
            # write_test_class(bug_id, 'fixed', comparison_instance['test_class']['text'])
            with open(test_case_file, 'w', encoding='utf-8') as writer:
                writer.write(comparison_instance['test_class']['text'])
    ret = {}
    ret['accuracy'] = corrected / total
    ret['pass-rate'] = passed / total
    ret['compile-rate'] = compiled/total
    ret['fixed-pass-rate'] = (regarded_as_passed + passed) / total
    ret['corrected-ids'] = list(corrected_ids)
    ret['passed-ids'] = list(passed_ids)
    logger.info(f'Accuracy: {corrected} / {total} = {corrected / total:.2%}')
    logger.info(f'Pass Rate: {passed} / {total} = {passed / total:.2%}')
    logger.info(
        f'Regarded as passed: {passed + regarded_as_passed} / {total}  = {(regarded_as_passed + passed) / total :.2%}')
    logger.info(f'Corrected IDs: {corrected_ids}')
    logger.info(f'Passed IDs: {passed_ids}')
    return ret
    pass


if __name__ == '__main__':
    files = [
        'EditAS-Defects4J-1-outputs.json',
    ]

    with open('/data/yanglin/UTGen_LLM/outputs/baseline/data.pkl','rb') as reader:
        input_instances = pickle.load(reader)
    
    instances = []
    response_dict = {}
    for file in files:
        file = os.path.join('/data/yanglin/UTGen_LLM/outputs/baseline', file)
        with open(file,'r',encoding='utf-8') as reader:
            jsonobj = json.loads(reader.read())
            for one_obj in jsonobj:
                response_dict[one_obj['id']] = '```\n'+one_obj['result']+"\n```\n"
        for item in input_instances:
            _, t_group = item
            inst, _,_,_ = t_group
            instances.append(inst)
        
        record = cal_pass_rate(instances, response_dict)
        failed_instance_ids = bug_detect(instances, response_dict)
        instances_succeeded_in_bug_detect = set(record['passed-ids']).intersection(set(failed_instance_ids))
        detected_bugs = set([comparison_group[id]['bug_id'] for id in instances_succeeded_in_bug_detect])

        ret = {
            'group': file,
            'accuracy': record['accuracy'],
            'compile_rate':record['compile-rate'],
            'pass_rate': record['fixed-pass-rate'],
            'detected_bugs': list(detected_bugs),
            'corrected_ids': record['corrected-ids'],
            'passed_ids': record['passed-ids'],
            'buggy_failed_ids': failed_instance_ids
        }
        dir, file = os.path.split(file)
        file = os.path.splitext(file)[0]

        with open(os.path.join(dir, file + '-res.json'), 'w', encoding='utf-8') as writer:
            writer.write(json.dumps(ret, ensure_ascii=False))
        logger.info(f'File {file} finished.')
        pass
