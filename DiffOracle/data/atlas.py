import sys

sys.path.extend(['.', '..'])

import os, json, yaml
from tqdm import tqdm
from dotmap import DotMap
from collections import Counter

from data.base.datasets import *
from utils.java_parsers import *
from entities.instances import Instance


class ATLAS(Dataset):
    def __init__(self, config):
        eval_base = config.atlas.eval
        retrieval_res_file = config.atlas.retrieval_res
        source_base = config.atlas.source
        super().__init__(eval_base, source_base, retrieval_res_file)
        pass

    def _read_input_files(self, in_file):
        lines = []
        with open(in_file, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                line = line.strip()
                if line == '':
                    continue
                lines.append(line)
        return lines

    def load(self, debug=False) -> list:
        assertion_file = os.path.join(self.eval_base, 'assertLines.txt')
        test_method_file = os.path.join(self.eval_base, 'testMethods.txt')
        instances = []
        assertions = self._read_input_files(assertion_file)
        test_methods = self._read_input_files(test_method_file)
        assert len(assertions) == len(test_methods)
        idx = 0
        for assertion, test_method in zip(assertions, test_methods):
            test_prefix, focal_method = test_method.split('"<FocalMethod>"')
            if focal_method.strip() == '':
                continue
            test_case = test_prefix.replace('"<AssertPlaceHolder>"', assertion)
            focal_method_name = parse_method_name(focal_method)
            if not focal_method_name:
                continue
            instances.append(Instance(
                id=idx,
                focal_method=focal_method,
                focal_method_name=focal_method_name,
                test_case=test_case,
                test_prefix=test_prefix,
                assertion=assertion,
            ))
            idx += 1
            pass
        return instances

    def load_ir_source_instances(self):
        assertion_file = os.path.join(self.source_base, 'assertLines.txt')
        test_method_file = os.path.join(self.source_base, 'testMethods.txt')
        instances = {}
        assertions = self._read_input_files(assertion_file)
        test_methods = self._read_input_files(test_method_file)
        assert len(assertions) == len(test_methods)
        idx = 0
        for assertion, test_method in zip(assertions, test_methods):
            test_prefix, focal_method = test_method.split('"<FocalMethod>"')
            test_case = test_prefix.replace('"<AssertPlaceHolder>"', assertion)
            focal_method_name = parse_method_name(focal_method)
            if focal_method_name:
                instances[idx] = Instance(
                    id=idx,
                    focal_method=focal_method,
                    focal_method_name=focal_method_name,
                    test_case=test_case,
                    test_prefix=test_prefix,
                    assertion=assertion,
                )
            idx += 1
            pass
        return instances

    def load_retrieval_mapping(self, top_k=1):
        file = self.retrieval_res_file
        try:
            assert os.path.exists(file) and file.endswith('.jsonl')
        except AssertionError:
            logger.error(f"Retrieval result file {file} does not exist or is not JSONL file, please check.")
            exit(-1)
        results = {}
        with open(file, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                line = line.strip()
                if line == '': continue
                inst = json.loads(line)
                results[inst['tgt_idx']] = inst['src_idx']
                pass
            pass
        return results

    def load_retrieval_data(self, top_k=1):
        """
        Load and process retrieval data for the 'atlas' dataset.

        Args:
            top_k (int, optional): Number of top similar instances to retrieve. Defaults to 1.

        Returns:
            list: A list of dual instances, each containing a retrieved instance and a target group.
        """
        instances = self.load()
        logger.info(f'Loaded {len(instances)} raw instances from methods2test')

        data = self.process_dataset(instances)
        logger.info(f'Processed {len(data)} instances for expected value inference.')

        retrieval_result = self.load_retrieval_mapping(top_k)
        src_idx2inst = self.load_ir_source_instances()
        dual_instances = []
        num_none_instances = 0

        for target_group in data:
            inst, _, _, _ = target_group
            key = inst.id
            if key in retrieval_result:
                retrieved_instance_id = retrieval_result[key]
                if retrieved_instance_id in src_idx2inst.keys():
                    retrieved_data = self.process_one_instance(src_idx2inst[retrieved_instance_id])
                    if not retrieved_data:
                        num_none_instances += 1
                    pass
                else:
                    num_none_instances += 1
                    retrieved_data = None

                dual_instances.append([retrieved_data, target_group])
            else:
                print(1)
                pass
        logger.info(
            f'Filtered {len(dual_instances)} instances after retrieval. In which {num_none_instances} failed to extract valid similar instance.')
        return dual_instances

    def load_one_instance_from_retrieval_data(self, id: str):
        sub_paths = id.split('_')
        target_file = os.path.join(self.source_base, sub_paths[0], id + '.json')
        try:
            assert os.path.exists(target_file)
        except:
            logger.error(f'Target file {target_file} does not exist.')
            exit(-1)
        with open(target_file, 'r', encoding='utf-8') as reader:
            instance = DotMap(json.load(reader))
            instance.id = id
        return instance

    def process_one_instance(self, instance: Instance):
        """
            Process a single instance to extract and process assertions.

            Args:
                instance (Instance): The instance to be processed.

            Returns:
                list or None: A list containing the instance, expected value, raw assertion, and processed assertion
                              if an 'assertEquals' assertion is found and processed successfully. Returns None if no
                              assertions are found or if multiple assertions are found but none are 'assertEquals'.
        """
        assertions = parse_assertions(instance.test_case)

        # Case when there is exactly one assertion
        if len(assertions) == 1:
            assertion_stmt, assertion_node = assertions[0]
            if 'assertEquals' in assertion_stmt:
                expected_value, processed_assertion, raw_assertion = parse_expected_value(node=assertion_node,
                                                                                          log=False)
                if expected_value and processed_assertion:
                    instance.update('expected_value', expected_value)
                    instance.update('processed_assertion', processed_assertion)
                    return [instance, expected_value, raw_assertion, processed_assertion]

        # Case when there are no assertions
        elif len(assertions) == 0:
            return None

        # Case when there are multiple assertions
        else:
            for item in assertions:
                assertion_stmt, assertion_node = item
                if 'assertEquals' in assertion_stmt:
                    expected_value, processed_assertion, raw_assertion = parse_expected_value(node=assertion_node,
                                                                                              log=False)
                    if expected_value and processed_assertion:
                        instance.update('expected_value', expected_value)
                        instance.update('processed_assertion', processed_assertion)
                        return [instance, expected_value, raw_assertion, processed_assertion]
                else:
                    pass

        return None

    def process_dataset(self, instances):
        exclude_reasons = Counter()
        dataset = []
        for instance in tqdm(instances, desc='Processing test prefixes and test oracles'):
            assertions = parse_assertions(instance.test_case)
            try:
                assert len(assertions) == 1
            except AssertionError:
                if 'assertThat' in instance.test_case:
                    exclude_reasons['assertThat'] += 1
                    pass
                else:
                    exclude_reasons['assertion_count_mismatch'] += 1
                    # logger.error(f'Assertion count mismatch: {len(assertions)}, expected to be 1:')
                    # logger.error(instance.test_case)
                continue
            assertion_stmt, assertion_node = assertions[0]
            if 'assertEquals' in assertion_stmt:
                expected_value, processed_assertion, raw_assertion = parse_expected_value(assertion_node)
                if expected_value and processed_assertion:
                    instance.update('expected_value', expected_value)
                    instance.update('processed_assertion', processed_assertion)
                    dataset.append([instance, expected_value, raw_assertion, processed_assertion])
                else:
                    exclude_reasons['expected_value_parsing_failure'] += 1
                continue
            else:
                exclude_reasons['assertion_type_not_equals'] += 1
                continue
            pass
        logger.info(exclude_reasons)
        return dataset


# if __name__ == '__main__':
#     code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
#     with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
#         config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
#     # load(config)
#     ds = Method2Test(config)
#     dual_instances = ds.load_retrieval_data(1)
#     failed = set()
#     failed_err = Counter()
#     verified = set()
#     for _, target_group in tqdm(dual_instances,
#                                 desc=f'Downloading projects'):
#         instance, expected_value, raw_assertion, processed_assertion = target_group
#         repo_id = instance.repository.repo_id
#         if repo_id in verified:
#             continue
#         repo_link = instance.repository.url
#         repo_base = os.path.join(f'/Users/yanglin/Documents/Projects/data/methods2test_projects/{repo_id}')
#         repo_dir = os.path.join(repo_base, repo_link.split('/')[-1])
#
#         if not os.path.exists(repo_base):
#             os.makedirs(repo_base)
#
#         if os.path.exists(repo_dir):
#             pass
#         else:
#             os.chdir(repo_base)
#             logger.info('Cloning...')
#             process = subprocess.Popen(f'git clone {repo_link}.git', shell=True, stdout=subprocess.PIPE,
#                                    stderr=subprocess.PIPE)
#             try:
#
#                 stdout, stderr = process.communicate(timeout=300)
#                 ret_code = process.returncode
#                 if ret_code != 0:
#                     failed.add(repo_id)
#                     failed_err['Repo not found'] += 1
#                     logger.error('Failed')
#                     verified.add(repo_id)
#                     continue
#             except TimeoutExpired:
#                 failed.add(repo_id)
#                 failed_err['Repo clone timeout'] += 1
#                 verified.add(repo_id)
#                 continue
#
#         logger.info('Compiling...')
#         os.chdir(repo_dir)
#         print(os.getcwd())
#         process = subprocess.Popen('mvn compile', shell=True, stdout=subprocess.PIPE,
#                                stderr=subprocess.PIPE)
#         try:
#             stdout, stderr = process.communicate(timeout=300)
#             ret_code = process.returncode
#             if ret_code != 0:
#                 failed.add(repo_id)
#                 failed_err['Repo cannot compile'] += 1
#                 logger.error('Failed')
#                 verified.add(repo_id)
#                 continue
#             verified.add(repo_id)
#             print(1)
#         except TimeoutExpired:
#             failed.add(repo_id)
#             failed_err['Repo compile timeout'] += 1
#             verified.add(repo_id)
#     pass

if __name__ == '__main__':
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    ds = ATLAS(config)
    ds.load_retrieval_data(1)
