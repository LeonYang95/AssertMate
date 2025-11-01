import os
import subprocess

from loguru import logger
from tqdm import tqdm


code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
debug = False
projects = [
    'Chart',
    'Cli',
    'Closure',
    'Codec',
    'Collections;',
    'Compress',
    'Csv',
    'Jsoup',
    'Lang',
    'Math',
    'Mockito',
    'Time'
]

exclusions =['Mockito_1']


def summary_bug_detection_results():
    results = []
    identified_bugs = set()
    by_assertions = set()
    with open(os.path.join(code_base, 'outputs/evosuite-execution-reports/origin/bug_detection'), 'r',
              encoding='utf-8') as reader:
        reader.readline()
        for line in reader.readlines():
            results.append(line.strip())

    for line in results:
        project, bug_id, _, _, _, num_failed = line.split(',')
        if num_failed not in ['-', '0']:
            identified_bugs.add(f"{project}_{bug_id[:-1]}")
            logger.info(f'Investigating {project}_{bug_id}')
            log_file = os.path.join(code_base,
                                    f"outputs/evosuite-execution-reports/origin/bug_detection_log/{project}/evosuite/{bug_id.replace('f', 'b')}.1.trigger.log")
            if not os.path.exists(log_file):
                logger.error(f'Log file {log_file} not found')
                continue
            else:
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'junit.framework.AssertionFailedError' in content:
                        by_assertions.add(f"{project}_{bug_id[:-1]}")
                pass

            pass
        else:
            continue
    logger.info(f'Identified {len(identified_bugs)} bugs.')
    logger.info(f"{len(by_assertions)} bugs by assertion errors.")
    logger.info(' '.join(by_assertions))
    logger.info(' '.join(identified_bugs))


# 执行命令
if __name__ == "__main__":
    for project in tqdm(projects):
        cmd = f"run_bug_detection.pl -p {project} -d {code_base}/outputs/evosuite-test-suites -o {code_base}/outputs/evosuite-execution-reports/origin"
        res = subprocess.run(cmd, shell=True)
    summary_bug_detection_results()
