import json
import os
import subprocess
import tarfile

from loguru import logger
from tqdm import tqdm

defects4j_home = '/Users/yanglin/Documents/Projects/data/defects4j'
d4j_proj_base = f'{defects4j_home}/d4j_projects'
code_base = os.path.abspath(os.path.dirname(__file__))
# 加载对应项目的src和test的路径
with open(f"{code_base}/resources/test_src.json", "r") as f:
    bug_paths = json.load(f)


def compress_subdirectories(base_dir):
    # 打压缩包
    # 确保base_dir存在
    if not os.path.exists(base_dir):
        print(f"目录 '{base_dir}' 不存在.")
        return

    # 遍历base_dir下的所有子目录
    for root, dirs, files in os.walk(base_dir):
        for dir_name in dirs:
            dir_path = os.path.join(root, f'{dir_name}/evosuite-tests')
            if not os.path.exists(dir_path):
                logger.warning('目录不存在: %s' % dir_path)
                continue
            arcname = os.listdir(dir_path)[0]
            dir_path = os.path.join(dir_path, arcname)
            output_filename = f"{code_base}/outputs/evosuite-test-suites/{'-'.join(dir_name.split('_'))}f-evosuite.1.tar.bz2"

            logger.info(f"正在压缩: {dir_path} 到 {output_filename}...")

            # 使用tarfile压缩目录
            with tarfile.open(output_filename, "w:bz2") as tar:
                tar.add(dir_path, arcname=arcname)
                # tar.add(dir_path)

        # 只遍历一级子目录
        break


if __name__ == '__main__':
    inputs = []
    with open(f"{code_base}/outputs/bytecode_signatures.txt", 'r', encoding="utf-8") as f:
        for line in f.readlines():
            inputs.append(json.loads(line.strip()))
    for input in tqdm(inputs):
        bug_id = input['bug_id']
        signature = input['bytecode_signature']
        split_loc = signature.rfind('.')
        class_name = signature[:split_loc]
        method_name = signature[split_loc + 1:]
        project_base = os.path.join(d4j_proj_base, bug_id)
        class_path = os.path.join(project_base + '/fixed', bug_paths[bug_id]["src_class"])
        output_dir = os.path.join(code_base, f"outputs/evosuite_outputs/{bug_id}")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        os.chdir(output_dir)
        cmd = f'java -jar {code_base}/resources/evosuite-1.1.0.jar -Dtarget_method="{method_name}" --class {class_name} -projectCP {class_path} --criterion branch'
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            logger.error(
                f'{bug_id} failed in generating evosuite test suite. Please refer to the log files for further information.')
            with open(f"{output_dir}/error.log", 'w', encoding='utf-8') as f:
                f.write(res.stderr.decode('utf-8'))
            with open(f"{output_dir}/output.log", 'w', encoding='utf-8') as f:
                f.write(res.stdout.decode('utf-8'))
        else:
            continue

    base_directory = f'{code_base}/outputs/evosuite_outputs'
    compress_subdirectories(base_directory)
    pass
