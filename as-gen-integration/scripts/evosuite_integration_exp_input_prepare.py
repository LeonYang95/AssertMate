import json
import os
import tarfile

from loguru import logger
from tqdm import tqdm

from utils.StaticAnalyzer import parseMethods, parseAssertions, parseClassObj
from utils.CodeRetriever import bm25_similarity
defects4j_home = '/Users/yanglin/Documents/Projects/data/defects4j'
d4j_proj_base = f'{defects4j_home}/d4j_projects'
code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
logger.add(f'{code_base}/logs/error.log', level='ERROR', rotation='10 MB', retention='10 days', diagnose=True)

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
    # read inputs
    with open(f'{code_base}/outputs/input_with_bytecode_sig.jsonl', 'r', encoding='utf-8') as f:
        for line in f.readlines():
            inputs.append(json.loads(line.strip()))
    writer = open(f'{code_base}/outputs/evosuite_generation_normal_inputs.jsonl', 'w', encoding='utf-8')

    # for retrieval
    retrieval_instances = {}
    for input in tqdm(inputs, desc='Preparing retrieval instances.'):
        # find test classes
        bug_id = input['extra:project_name'][:-6]
        if bug_id not in retrieval_instances:
            retrieval_instances[bug_id] = set()
        gen_ut_dir = f'{code_base}/outputs/evosuite_outputs/{bug_id}/evosuite-tests'
        focal_method = parseMethods('public class A {' + input['source:source_method_code_format'] + '}')[0]
        test_file = None
        for root, dirs, files in os.walk(gen_ut_dir):
            for file in files:
                if file.endswith('_ESTest.java'):
                    test_file = os.path.join(root, file)
                    break
        if not test_file:
            continue

        # split test classes
        with open(test_file, 'r', encoding='utf-8') as f:
            test_class = f.read()
        test_cls_obj = parseClassObj(test_class)

        # find uts
        uts = parseMethods(test_class, requiredModifier='@Test')
        for ut in uts:
            retrieval_instances[bug_id].add(ut['method_text'])

    logger.info('Finished preparing retrieval instances.')


    for input in tqdm(inputs, desc='Preparing input instances.'):
        # find test classes
        bug_id = input['extra:project_name'][:-6]
        gen_ut_dir = f'{code_base}/outputs/evosuite_outputs/{bug_id}/evosuite-tests'
        focal_method = parseMethods('public class A {' + input['source:source_method_code_format'] + '}')[0]
        test_file = None
        for root, dirs, files in os.walk(gen_ut_dir):
            for file in files:
                if file.endswith('_ESTest.java'):
                    test_file = os.path.join(root, file)
                    break

        if not test_file:
            logger.error(f'No test file found for {bug_id}')
            continue

        # record focal class information
        src_cls_file = input['content:source_class_code_path'].replace('\\', '/')
        src_cls_file = src_cls_file[
                       src_cls_file.find(input['extra:project_name']) + len(input['extra:project_name']):]
        src_cls_file = d4j_proj_base + '/' + bug_id + '/fixed' + src_cls_file
        if not os.path.exists(src_cls_file):
            logger.error(f"Source class file {src_cls_file} not found.")
            continue
        with open(src_cls_file, 'r', encoding='utf-8') as f:
            src_cls_code = f.read()
        src_cls_obj = parseClassObj(src_cls_code)

        # split test classes
        with open(test_file, 'r', encoding='utf-8') as f:
            test_class = f.read()
        test_cls_obj = parseClassObj(test_class)

        # find uts
        uts = parseMethods(test_class, requiredModifier='@Test')
        for ut in uts:
            parsed_assertions = parseAssertions(ut['method_text'])
            retrieved_instance = None
            if bug_id in retrieval_instances:
                max_sim = -1
                for one_ut in retrieval_instances[bug_id]:
                    if hash(one_ut) == hash(ut['method_text']):
                        continue
                    else:
                        sim = bm25_similarity(ut['method_text'], one_ut)
                        if sim > max_sim:
                            retrieved_instance = one_ut
                            max_sim = sim

            if not parsed_assertions:
                logger.warning(f'No valid assertions found for {bug_id}, skipped.')
                continue
            for parsed_assertion in parsed_assertions:
                obj = {
                    'bug_id': bug_id,
                    'version': 'fixed',
                    'focal_method_signature': input['source:source_method_signature'],
                    'focal_method_bytecode_signature': input['bytecode_signature'],
                    'test_file': test_file,
                    'source_file': src_cls_file,
                    'focal_method': focal_method['method_text'],
                    'return_type': focal_method['method_return_type'],
                    'test_case': parsed_assertion['ut'],
                    'parent_test_case': parsed_assertion['parent_ut'],
                    'test_class': {
                        'path': test_file,
                        'imports': test_cls_obj.imports,  # 引用
                        'fields': [str(f) for _, f in test_cls_obj.fields.items()],  # 定义的属性
                        'methods': [m.signature for k, m in test_cls_obj.methods.items()],  # 定义的函数
                        'text': test_class  # 完整的测试类
                    },
                    'focal_class': {
                        'name': src_cls_obj.name,
                        'path': src_cls_file,
                        'superclass': src_cls_obj.superclass,
                        'interface': src_cls_obj.interface,
                        'imports': src_cls_obj.imports,  # 引用
                        'fields': [str(f) for k, f in src_cls_obj.fields.items()],  # 定义的属性
                        'methods': [m.signature for k, m in src_cls_obj.methods.items()],  # 定义的函数
                        'other_methods': [m.short_definition for m in src_cls_obj.public_methods],
                        'fields_dict': dict([(k, str(f)) for k, f in src_cls_obj.fields.items()]),
                        'text': src_cls_code  # 完整的待测类
                    },
                    'retrieved_test_case': retrieved_instance if retrieval_instances else ''
                }
                writer.write(json.dumps(obj, ensure_ascii=False) + '\n')
                pass
    writer.close()
    pass
