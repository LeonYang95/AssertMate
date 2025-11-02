import sys

sys.path.extend(['.', '..'])

import os, json, yaml
from tqdm import tqdm
from dotmap import DotMap
from collections import Counter

from data.base.datasets import *
from utils.java_parsers import *
from utils.file import traverse_files
from entities.instances import Instance


class Method2Test(Dataset):
    def __init__(self, config):
        eval_base = config.methods2test.eval
        retrieval_res_file = config.methods2test.retrieval_res
        source_base = config.methods2test.source
        super().__init__(eval_base, source_base, retrieval_res_file)
        pass

    def load(self, debug=False) -> list:
        """
        Load dataset instances from JSON files in the specified directory.

        Args:
            dataset_base (str): The base directory containing the dataset files.
            debug (bool, optional): If True, load only the first file for debugging purposes. Defaults to False.

        Returns:
            list: A list of dataset instances loaded from the JSON files.
        """
        files = traverse_files(self.eval_base, '.json')
        instances = []
        for file in tqdm(files, desc='Loading dataset files'):
            with open(file, 'r', encoding='utf-8') as reader:
                instance = DotMap(json.load(reader))
            if any([nloc < 5 for nloc in
                    [parse_nloc_in_method(instance.focal_method.body)]]):
                continue
            id = file.split(os.path.sep)[-1].split('.')[0]
            instance.id = id
            instances.append(Instance(
                id=id,
                focal_method_name=instance.focal_method.identifier,
                focal_method=instance.focal_method.body,
                test_case=instance.test_case.body,
                test_prefix='',
                assertion='',
                invocations=instance.test_case.invocations,
                test_class_fields=[f.original_string for f in instance.test_class.fields],
                focal_class_fields=[f.original_string for f in instance.focal_class.fields],
                focal_class_methods=[m.full_signature for m in instance.focal_class.methods],
            ))
            if debug: break
        return instances

    def load_retrieval_mapping(self, top_k=1):
        file = self.retrieval_res_file
        try:
            assert os.path.exists(file)
        except AssertionError:
            logger.error(f"Retrieval result file {file} does not exist, please check.")
            exit(-1)
        results = {}
        if file.endswith('jsonl'):
            with open(file, 'r', encoding='utf-8') as reader:
                for line in reader.readlines():
                    line = line.strip()
                    if line == '': continue
                    inst = json.loads(line)
                    for key, mapped_results in inst.items():
                        results[key] = mapped_results[:top_k]
                        pass
                    pass
                pass
        elif file.endswith('json'):
            control_results = {}
            with open(file, 'r', encoding='utf-8') as reader:
                for line in reader.readlines():
                    line = line.strip()
                    if line == '': continue
                    inst = json.loads(line)
                    for key, mapped_results in inst.items():
                        control_results[key] = mapped_results[:top_k]
                        pass
                    pass
                pass
            with open(file, 'r', encoding='utf-8') as reader:
                retrieved_results = json.load(reader)
                for key, res in retrieved_results.items():
                    if len(res) >= 1:
                        results[key] = [{
                            'key': res[0]['id'],
                            'sim': res[0]['sim']
                        }]
                    else:
                        if key in control_results:
                            results[key] = control_results[key]
                        else:
                            results[key] = [{
                                'key': key,
                                'sim': 1.0
                            }]
                    pass
                pass
            pass
        else:
            raise NotImplementedError()

        return results

    def load_retrieval_data(self, top_k=1):
        """
        Load and process retrieval data for the 'methods2test' dataset.

        Args:
            top_k (int, optional): Number of top similar instances to retrieve. Defaults to 1.

        Returns:
            list: A list of dual instances, each containing a retrieved instance and a target group.
        """
        instances = self.load()
        logger.info(f'Loaded {len(instances)} raw instances from methods2test')

        filtered_instances = self.one_assertion_filtering(instances)
        logger.info(f'After one-assertion-filtering, {len(filtered_instances)} instances left.')

        data = self.process_dataset(filtered_instances)
        logger.info(f'Processed {len(data)} instances for expected value inference.')

        retrieval_result = self.load_retrieval_mapping(top_k)
        dual_instances = []
        num_none_instances = 0

        for target_group in data:
            inst, _, _, _ = target_group
            key = inst.id
            if key in retrieval_result:
                retrieved_instance_ids = retrieval_result[key][:top_k]
                for retrieved_inst_id in retrieved_instance_ids:
                    retrieved_key = retrieved_inst_id['key'] if 'key' in retrieved_inst_id else retrieved_inst_id['id']
                    retrieved_inst = self.load_one_instance_from_retrieval_data(retrieved_key)
                    # retrieved_data = self.process_one_instance(retrieved_inst)
                    retrieved_data = (retrieved_inst, '', '', '')
                    if retrieved_data is None:
                        num_none_instances += 1
                    dual_instances.append([retrieved_data, target_group])
            else:
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
            target_file = os.path.join(self.eval_base, sub_paths[0], id + '.json')
            if not os.path.exists(target_file):
                logger.error(f'Target file {target_file} does not exist.')
                exit(-1)
        with open(target_file, 'r', encoding='utf-8') as reader:
            instance = DotMap(json.load(reader))
            instance.id = id

        return Instance(
            id=id,
            focal_method_name=instance.focal_method.identifier,
            focal_method=instance.focal_method.body,
            test_case=instance.test_case.body,
            test_prefix='',
            assertion='',
            invocations=instance.test_case.invocations,
            test_class_fields=[f.original_string for f in instance.test_class.fields],
            focal_class_fields=[f.original_string for f in instance.focal_class.fields],
            focal_class_methods=[m.full_signature for m in instance.focal_class.methods],
        )

    def one_assertion_filtering(self, instances):
        """
        Filter instances to include only those with exactly one assertion.

        Args:
            instances (list): A list of instances to be filtered.

        Returns:
            list: A list of instances that have exactly one assertion.
        """
        filtered_instances = []
        for instance in tqdm(instances, desc='Filtering one-assertion instances'):
            invocations = instance.invocations
            if sum([1 for invocation in invocations if invocation in known_assertions]) == 1:
                filtered_instances.append(instance)
            else:
                continue
        return filtered_instances

    def process_one_instance(self, instance: Instance):
        """
        Process a single instance to extract assertion information.

        Args:
            instance (DotMap): The instance to be processed, containing a test case.

        Returns:
            list or None: A list containing the instance, expected value, raw assertion, and processed assertion
                          if an 'assertEquals' assertion is found and processed successfully. Otherwise, None.
        """
        assertions = parse_assertions(instance.test_case)

        # Case when there is exactly one assertion
        if len(assertions) == 1:
            assertion_stmt, assertion_node = assertions[0]
            if 'assertEquals' in assertion_stmt:
                actual_value, expected_value, processed_assertion, raw_assertion = parse_expected_value(
                    node=assertion_node,
                    log=False)
                if expected_value and processed_assertion:
                    instance.update('expected_value', expected_value)
                    instance.update('processed_assertion', processed_assertion)
                    instance.update('test_prefix', instance.test_case.replace(raw_assertion, processed_assertion))
                    instance.update('assertion', raw_assertion)
                    instance.update('actual_value', actual_value)
                    return [instance, expected_value, raw_assertion, processed_assertion]

        # Case when there are no assertions
        elif len(assertions) == 0:
            return None

        # Case when there are multiple assertions
        else:
            for item in assertions:
                assertion_stmt, assertion_node = item
                if 'assertEquals' in assertion_stmt:
                    actual_value, expected_value, processed_assertion, raw_assertion = parse_expected_value(
                        node=assertion_node,
                        log=False)
                    if expected_value and processed_assertion:
                        instance.update('expected_value', expected_value)
                        instance.update('processed_assertion', processed_assertion)
                        instance.update('test_prefix', instance.test_case.replace(raw_assertion, processed_assertion))
                        instance.update('assertion', raw_assertion)
                        instance.update('actual_value', actual_value)
                        return [instance, expected_value, raw_assertion, processed_assertion]
                else:
                    pass

        return None

    def process_dataset(self, instances: list):
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
                    logger.error(f'Assertion count mismatch: {len(assertions)}, expected to be 1:')
                    logger.error(instance.test_case)
                continue
            assertion_stmt, assertion_node = assertions[0]
            if 'assertEquals' in assertion_stmt:
                actual_value, expected_value, processed_assertion, raw_assertion = parse_expected_value(assertion_node)
                if expected_value and processed_assertion:
                    instance.update('expected_value', expected_value)
                    instance.update('processed_assertion', processed_assertion)
                    instance.update('test_prefix', instance.test_case.replace(raw_assertion, processed_assertion, 1))
                    instance.update('assertion', raw_assertion)
                    instance.update('actual_value', actual_value)
                    dataset.append([instance, expected_value, raw_assertion, processed_assertion])
                pass
            elif 'assertTrue' in assertion_stmt or 'assertFalse' in assertion_stmt:
                expected_value, actual_value, raw_assertion = parse_assert_boolean(assertion_node)
                if expected_value and actual_value:
                    if any([b in raw_assertion for b in ['true', 'false']]):
                        # ignore assertTrue(true) or assertFalse(false)
                        continue
                    instance.update('expected_value', expected_value)
                    instance.update('actual_value', actual_value)
                    instance.update('processed_assertion', raw_assertion)
                    instance.update('test_prefix', instance.test_case.replace(raw_assertion.strip(),
                                                                              f'// Verify if the boolean return value of {actual_value} is as expected.\n<AssertionPlaceHolder>\n\n',
                                                                              1))
                    instance.update('assertion', raw_assertion)
                    dataset.append([instance, expected_value, raw_assertion, ''])
                pass
            elif 'assertNull' in assertion_stmt or 'assertNotNull' in assertion_stmt:
                expected_value, actual_value, raw_assertion = parse_assert_null_values(assertion_node)
                if expected_value and actual_value:
                    if any([b in raw_assertion for b in ['null']]):
                        # ignore assertNull(null)
                        continue
                    instance.update('expected_value', expected_value)
                    instance.update('actual_value', actual_value)
                    instance.update('processed_assertion', raw_assertion)
                    instance.update('test_prefix', instance.test_case.replace(raw_assertion.strip(),
                                                                              f'// Verify if the return value of {actual_value} is null or not.\n<AssertionPlaceHolder>\n\n',
                                                                              1))
                    instance.update('assertion', raw_assertion)
                    dataset.append([instance, expected_value, raw_assertion, ''])
            else:
                exclude_reasons['assertion_type_not_equals'] += 1
                continue
            pass
        logger.info(exclude_reasons)
        return dataset


if __name__ == '__main__':
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    # load(config)
    ds = Method2Test(config)
    dual_instances = ds.load_retrieval_data(1)
    boolean_type = 0
    total = len(dual_instances)
    failed = set()
    failed_err = Counter()
    verified = set()
    for _, target_group in tqdm(dual_instances,
                                desc=f'Downloading projects'):
        instance, expected_value, raw_assertion, processed_assertion = target_group
        if 'assertTrue' in raw_assertion or 'assertFalse' in raw_assertion:
            boolean_type += 1
            assert expected_value in ['assertTrue', 'assertFalse']
        # repo_id = instance.repository.repo_id
        # if repo_id in verified:
        #     continue
        # repo_link = instance.repository.url
        # repo_base = os.path.join(f'/Users/yanglin/Documents/Projects/data/methods2test_projects/{repo_id}')
        # repo_dir = os.path.join(repo_base, repo_link.split('/')[-1])

        # if not os.path.exists(repo_base):
        #     os.makedirs(repo_base)

        # if os.path.exists(repo_dir):
        #     pass
        # else:
        #     os.chdir(repo_base)
        #     logger.info('Cloning...')
        #     process = subprocess.Popen(f'git clone {repo_link}.git', shell=True, stdout=subprocess.PIPE,
        #                                stderr=subprocess.PIPE)
        #     try:

        #         stdout, stderr = process.communicate(timeout=300)
        #         ret_code = process.returncode
        #         if ret_code != 0:
        #             failed.add(repo_id)
        #             failed_err['Repo not found'] += 1
        #             logger.error('Failed')
        #             verified.add(repo_id)
        #             continue
        #     except TimeoutExpired:
        #         failed.add(repo_id)
        #         failed_err['Repo clone timeout'] += 1
        #         verified.add(repo_id)
        #         continue

        # logger.info('Compiling...')
        # os.chdir(repo_dir)
        # print(os.getcwd())
        # process = subprocess.Popen('mvn compile', shell=True, stdout=subprocess.PIPE,
        #                            stderr=subprocess.PIPE)
        # try:
        #     stdout, stderr = process.communicate(timeout=300)
        #     ret_code = process.returncode
        #     if ret_code != 0:
        #         failed.add(repo_id)
        #         failed_err['Repo cannot compile'] += 1
        #         logger.error('Failed')
        #         verified.add(repo_id)
        #         continue
        #     verified.add(repo_id)
        # except TimeoutExpired:
        #     failed.add(repo_id)
        #     failed_err['Repo compile timeout'] += 1
        #     verified.add(repo_id)
    print(boolean_type)
    pass
