import sys

sys.path.extend(['.', '..'])

import os, json, yaml
from tqdm import tqdm
from dotmap import DotMap
from collections import Counter

from data.base.datasets import *
from utils.java_parsers import *
from entities.instances import Instance


class Defects4J(Dataset):
    def __init__(self, config):
        self.input_ut_file = config.defects4j.eval
        self.retrieval_res_file = config.defects4j.retrieval_res
        self.source_ut_file = config.defects4j.source
        super().__init__(self.input_ut_file, self.source_ut_file, self.retrieval_res_file)
        self.retrieved_source = {}
        # self.load_all_uts()
        pass

    def load_all_uts(self):
        with open(self.source_ut_file, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                item = json.loads(line.strip())
                self.retrieved_source[item['bug_id']] = item['uts']

    def load(self, debug=False) -> list:
        idx = 0
        instances = []
        with open(self.input_ut_file, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                instance = json.loads(line.strip())
                instances.append(Instance(
                    bug_id=instance['bug_id'],
                    id=idx,
                    focal_method_name=instance['focal_method_signature'],
                    focal_method=instance['focal_method'],
                    test_case=instance['test_case'],
                    test_prefix='',
                    assertion='',
                    invocations=[],
                    test_class_fields=instance['test_class']['fields'],
                    focal_class_fields=instance['focal_class']['fields'],
                    focal_class_methods=instance['focal_class']['methods'],
                ))
                if debug: break
                idx += 1
        return instances

    def load_retrieval_mapping(self, top_k=1):
        file = self.retrieval_res_file
        try:
            assert os.path.exists(file)
        except AssertionError:
            logger.error(f"Retrieval result file {file} does not exist, please check.")
            exit(-1)
        results = {}
        with open(file, 'r', encoding='utf-8') as reader:
            idx = 0
            for line in reader.readlines():
                line = line.strip()
                if line == '': continue
                inst = json.loads(line)
                results[idx] = inst['id']
                idx += 1
            pass
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

        filtered_instances = instances
        logger.info(f'After one-assertion-filtering, {len(filtered_instances)} instances left.')

        data = self.process_dataset(filtered_instances)
        logger.info(f'Processed {len(data)} instances for expected value inference.')

        # retrieval_result = self.load_retrieval_mapping(top_k)
        dual_instances = []
        num_none_instances = 0

        for target_group in data:
            inst, _, _, _ = target_group
            key = inst.id
            # retrieved_ut_key = retrieval_result[key]
            # retrieved_inst = self.load_one_instance_from_retrieval_data(inst.bug_id, retrieved_ut_key)
            retrieved_inst = None
            # retrieved_data = self.process_one_instance(retrieved_inst)
            retrieved_data = (retrieved_inst, '', '', '')
            if retrieved_data is None:
                num_none_instances += 1
            dual_instances.append([retrieved_data, target_group])
        logger.info(
            f'Filtered {len(dual_instances)} instances after retrieval. In which {num_none_instances} failed to extract valid similar instance.')
        return dual_instances

    def load_one_instance_from_retrieval_data(self, bug_id: str, id: str):
        return Instance(
            id=id,
            focal_method_name='//no focal method',
            focal_method='//no focal method',
            test_case=self.retrieved_source[bug_id][id],
            test_prefix='',
            assertion='',
            invocations=[],
            test_class_fields=[],
            focal_class_fields=[],
            focal_class_methods=[]
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
                #     logger.error(f'Assertion count mismatch: {len(assertions)}, expected to be 1:')
                #     logger.error(instance.test_case)
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


class Integration_Defects4J(Dataset):
    def __init__(self, config):
        self.input_ut_file = '/data/yanglin/gitrepos/DiffOracle/data/evosuite_generation_normal_inputs.jsonl'
        super().__init__(self.input_ut_file, '', '')
        pass

    def load_retrieval_mapping(self, top_k=1):
        pass

    def load_one_instance_from_retrieval_data(self, id):
        pass

    def load(self, debug=False) -> list:
        idx = 0
        instances = []
        with open(self.input_ut_file, 'r', encoding='utf-8') as reader:
            for line in reader.readlines():
                instance = json.loads(line.strip())
                instances.append((Instance(
                    bug_id=instance['bug_id'],
                    id=idx,
                    focal_method_name=instance['focal_method_signature'],
                    focal_method=instance['focal_method'],
                    test_case=instance['test_case'],
                    test_prefix='',
                    assertion='',
                    invocations=[],
                    test_class_fields=instance['test_class']['fields'],
                    focal_class_fields=instance['focal_class']['fields'],
                    focal_class_methods=instance['focal_class']['methods'],
                ), Instance(
                    bug_id=instance['bug_id'],
                    id=idx,
                    focal_method_name=instance['focal_method_signature'],
                    focal_method=instance['focal_method'],
                    test_case=instance['retrieved_test_case'],
                    test_prefix='',
                    assertion='',
                    invocations=[],
                    test_class_fields=instance['test_class']['fields'],
                    focal_class_fields=instance['focal_class']['fields'],
                    focal_class_methods=instance['focal_class']['methods'],
                )))
                if debug: break
                idx += 1
        return instances

    def load_retrieval_data(self, top_k=1):
        instances = self.load()
        logger.info(f'Loaded {len(instances)} raw instances from defects4j')

        data = self.process_dataset(instances)
        logger.info(f'Processed {len(data)} instances for expected value inference.')

        dual_instances = []
        num_none_instances = 0

        for target_group in data:
            d_insts, _, _, _ = target_group
            instance, retrieved_inst = d_insts
            target_group[0] = instance
            retrieved_data = (retrieved_inst, '', '', '')
            if retrieved_data is None:
                num_none_instances += 1
            dual_instances.append([retrieved_data, target_group])
        logger.info(
            f'Filtered {len(dual_instances)} instances after retrieval. In which {num_none_instances} failed to extract valid similar instance.')
        return dual_instances

    def one_assertion_filtering(self, instances):
        """
        Filter instances to include only those with exactly one assertion.

        Args:
            instances (list): A list of instances to be filtered.

        Returns:
            list: A list of instances that have exactly one assertion.
        """
        return instances

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
        for dual_instance in tqdm(instances, desc='Processing test prefixes and test oracles'):
            instance, retrieved_instance = dual_instance
            assertions = parse_assertions(instance.test_case)
            try:
                assert len(assertions) == 1
            except AssertionError:
                if 'assertThat' in instance.test_case:
                    exclude_reasons['assertThat'] += 1
                    pass
                else:
                    exclude_reasons['assertion_count_mismatch'] += 1
                #     logger.error(f'Assertion count mismatch: {len(assertions)}, expected to be 1:')
                #     logger.error(instance.test_case)
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
                    dataset.append([dual_instance, expected_value, raw_assertion, processed_assertion])
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
                    dataset.append([dual_instance, expected_value, raw_assertion, ''])
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
                    dataset.append([dual_instance, expected_value, raw_assertion, ''])
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
    ds = Defects4J(config)
    dual_instances = ds.load_retrieval_data(1)
    import re
    output_writer = open (os.path.join(code_base, 'data/AssertMate_RQ1_inputs_for_RetriGen.jsonl'),'w',encoding='utf-8')


    for (retrieved_group, target_group) in dual_instances:
        instance, _, _, _ = target_group
        new_instance = {
            "idx":instance.id,
            "focal_method":instance.focal_method,
            "test_prefix":instance.test_case.replace(instance.assertion, '<AssertionPlaceHolder>',1),
        }
        output_writer.write(json.dumps(new_instance,ensure_ascii=False)+'\n')
        pass
    output_writer.close()
    boolean_type = 0
    total = len(dual_instances)
    failed = set()
    failed_err = Counter()
    verified = set()
    # for _, target_group in tqdm(dual_instances,
    #                             desc=f'Downloading projects'):
    #     instance, expected_value, raw_assertion, processed_assertion = target_group
    #     if 'assertTrue' in raw_assertion or 'assertFalse' in raw_assertion:
    #         boolean_type += 1
    #         assert expected_value in ['assertTrue', 'assertFalse']
    #     repo_id = instance.repository.repo_id
    #     if repo_id in verified:
    #         continue
    #     repo_link = instance.repository.url
    #     repo_base = os.path.join(f'/Users/yanglin/Documents/Projects/data/methods2test_projects/{repo_id}')
    #     repo_dir = os.path.join(repo_base, repo_link.split('/')[-1])
    #
    #     if not os.path.exists(repo_base):
    #         os.makedirs(repo_base)
    #
    #     if os.path.exists(repo_dir):
    #         pass
    #     else:
    #         os.chdir(repo_base)
    #         logger.info('Cloning...')
    #         process = subprocess.Popen(f'git clone {repo_link}.git', shell=True, stdout=subprocess.PIPE,
    #                                    stderr=subprocess.PIPE)
    #         try:
    #
    #             stdout, stderr = process.communicate(timeout=300)
    #             ret_code = process.returncode
    #             if ret_code != 0:
    #                 failed.add(repo_id)
    #                 failed_err['Repo not found'] += 1
    #                 logger.error('Failed')
    #                 verified.add(repo_id)
    #                 continue
    #         except TimeoutExpired:
    #             failed.add(repo_id)
    #             failed_err['Repo clone timeout'] += 1
    #             verified.add(repo_id)
    #             continue
    #
    #     logger.info('Compiling...')
    #     os.chdir(repo_dir)
    #     print(os.getcwd())
    #     process = subprocess.Popen('mvn compile', shell=True, stdout=subprocess.PIPE,
    #                                stderr=subprocess.PIPE)
    #     try:
    #         stdout, stderr = process.communicate(timeout=300)
    #         ret_code = process.returncode
    #         if ret_code != 0:
    #             failed.add(repo_id)
    #             failed_err['Repo cannot compile'] += 1
    #             logger.error('Failed')
    #             verified.add(repo_id)
    #             continue
    #         verified.add(repo_id)
    #     except TimeoutExpired:
    #         failed.add(repo_id)
    #         failed_err['Repo compile timeout'] += 1
    #         verified.add(repo_id)
    # print(boolean_type)
    # pass
