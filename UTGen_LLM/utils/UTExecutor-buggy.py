import json
import multiprocessing
import os
import subprocess
import sys

from loguru import logger

sys.path.extend(['.', '..'])

debug = False
code_base = '/Users/yanglin/Documents/Projects/UTGen_LLM'
d4j_project_base = '/Users/yanglin/Documents/Projects/data/defects4j/d4j_projects'


def check_test():
    failed_reason = 'Other-error'
    subprocess.run(f'defects4j test', shell=True,
                   stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    if os.path.exists('failing_tests'):
        with open('failing_tests', 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                if not line.startswith(' '):
                    if 'Assertion' in line:
                        failed_reason = 'Assertion-error'
                        return failed_reason
                        pass
                    pass
                pass
            pass
        return failed_reason
    else:
        return 'Compilation -error'


def check(data, pid):
    global debug
    failed_ones = []
    assertion_identified_bugs = []
    for proj, bugs in data.items():
        if debug:
            bugs = list(bugs)[:2]
        for bug in bugs:
            base = os.path.join(d4j_project_base, proj + f'_{bug}')
            logger.info(f'Bug id {proj}_{bug} checking...')
            os.chdir(base + '/buggy')
            reason = check_test()
            if reason == 'Compilation-error':
                logger.warning(f'Bug id {proj}_{bug} failed compilation, re-checking.')
                os.chdir(base)
                os.removedirs('buggy')
                ret = subprocess.run(f'defects4j checkout -p {proj} -v {bug}b -w buggy', shell=True,
                                     stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                if ret.returncode != 0:
                    logger.error(f'Bug id {proj}_{bug} checkout failed.')
                    failed_ones.append(f'{proj}_{bug}_b')
                else:
                    reason = check_test()
                    logger.warning(f'Bug id {proj}_{bug} re-test: {reason}.')
                    pass
            if reason == 'Assertion-error':
                logger.info('Assertion error detected.')
                assertion_identified_bugs.append(f'{proj}_{bug}')
                pass
            elif reason == 'Other-error':
                logger.info('Other error detected.')
                pass
            else:
                logger.info('Compilation error detected.')
                failed_ones.append(f'{proj}_{bug}')
            pass
        if debug: break
        pass

    with open(os.path.join(code_base, f'outputs/failed_bugs.csv-{pid}'), 'w', encoding='utf-8') as writer:
        writer.write(','.join(failed_ones))
    with open(os.path.join(code_base, f'outputs/assertion_identified_bugs.csv-{pid}'), 'w', encoding='utf-8') as writer:
        writer.write(','.join(assertion_identified_bugs))


if __name__ == '__main__':

    comparison_file = '/Users/yanglin/Documents/Projects/UTGen_LLM/outputs/defects4j_inputs.jsonl'
    comparison_group = []
    with open(comparison_file, 'r', encoding='utf-8') as reader:
        for line in reader.readlines():
            comparison_group.append(json.loads(line.strip()))
    project2bugs = {}
    for instance in comparison_group:
        project, bug_id = instance['bug_id'].split('_')
        if project not in project2bugs:
            project2bugs[project] = set()
        project2bugs[project].add(bug_id)

    num_threads = 5
    num_per_threads = len(project2bugs) // num_threads + 1
    chunks = [
        list(project2bugs.items())[i * num_per_threads:(i + 1) * num_per_threads] for i in range(num_threads)
    ]

    jobs = []
    for id, chunk in enumerate(chunks):
        p = multiprocessing.Process(target=check, args=(dict(chunk), id))
        jobs.append(p)
        p.start()

    for job in jobs:
        job.join()

    valid_bug_ids = []
    all_failed = []
    for i in range(num_threads):
        with open(os.path.join(code_base, f'outputs/failed_bugs.csv-{i}'), 'r', encoding='utf-8') as reader:
            all_failed.extend(reader.read().strip().split(','))
        with open(os.path.join(code_base, f'outputs/assertion_identified_bugs.csv-{i}'), 'r',
                  encoding='utf-8') as reader:
            valid_bug_ids.extend(reader.read().strip().split(','))
        os.remove(os.path.join(code_base, f'outputs/failed_bugs.csv-{i}'))
        os.remove(os.path.join(code_base, f'outputs/assertion_identified_bugs.csv-{i}'))
    with open(os.path.join(code_base, 'outputs/valid_bugs.csv'), 'w', encoding='utf-8') as writer:
        writer.write(','.join(valid_bug_ids))
    with open(os.path.join(code_base, 'outputs/failed_bugs.csv'), 'w', encoding='utf-8') as writer:
        writer.write(','.join(all_failed))
