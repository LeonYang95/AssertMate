import json
import os
import re
import signal
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict

from loguru import logger
from tqdm import tqdm

defects4j_home = '/Users/yanglin/Documents/Projects/data/defects4j'
d4j_proj_base = f'{defects4j_home}/d4j_projects'
defects4j_cmd = f'{defects4j_home}/framework/bin/defects4j'
code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# 加载对应项目的src和test的路径
with open(f"{code_base}/resources/test_src.json", "r") as f:
    bug_paths = json.load(f)


def to_jave_bytecode_types(c_str: str):
    # ["B", "C", "D", "F", "I", "J", "Z", "S"]
    if c_str == "B":
        return "java.lang.byte"
    elif c_str == "C":
        return "java.lang.character"
    elif c_str == "D":
        return "java.lang.double"
    elif c_str == "F":
        return "java.lang.float"
    elif c_str == "I":
        return "java.lang.integer"
    elif c_str == "J":
        return "java.lang.long"
    elif c_str == "Z":
        return "java.lang.boolean"
    elif c_str == "S":
        return "java.lang.short"
    elif c_str.startswith("L"):
        return c_str[1:].replace("/", ".")
    elif c_str.startswith("["):
        return to_jave_bytecode_types(c_str[1:]) + "[]"
    else:
        raise NotImplementedError("class type %s not implemented yet" % c_str)


def _test_and_collect_results(root):
    """
    执行测试，并收集测试结果

    Args:
        root (str): 执行测试的根目录 (如Chart_1/fixed)

    Returns:
        dict : {
            "passed":是否通过测试，boolean类型,
        }
    """
    if not os.path.exists(root):
        raise FileNotFoundError()
    else:
        cur_dir = os.getcwd()
        os.chdir(root)
        test_cmd = f"timeout 10 {defects4j_cmd} test"
        process = subprocess.Popen(
            test_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            stdout, stderr = process.communicate(timeout=10)
            return_code = process.returncode
            if return_code == 124:
                return {
                    "passed": False,
                    "error_types": ["timeout"],
                    "error_info": ["timeout"],
                }
        except subprocess.TimeoutExpired as te:
            os.kill(process.pid, signal.SIGKILL)

            return {
                "passed": False,
                "error_types": ["timeout"],
                "error_info": ["timeout"],
            }
        test_flag = False
        if return_code == 0:
            # test命令正常结束了
            cmd_output = stdout.decode(encoding="utf-8").strip()
            num_failed = re.findall(r"Failing tests: (\d+)", cmd_output)
            num_failed = int(num_failed[0])
            if num_failed == 0:
                test_flag = True
    os.chdir(cur_dir)
    return test_flag


def parse_coverage_xml(coverage_report):
    """
    Load and parse the JaCoCo XML coverage report

    Args:
        coverage_report (str): jacoco生成的覆盖率报告路径

    Raises:
        NotImplementedError: 不支持的变量类型，请联系开发人员

    Returns:
        dict: 经过分析之后的jacoco覆盖率指标
    """
    tree = ET.parse(coverage_report)
    root = tree.getroot()

    coverage_data = defaultdict()
    # Iterate over the packages in the XML and collect data
    for package in root.findall(".//package"):
        package_name = package.attrib["name"]
        coverage_data[package_name] = defaultdict()

        for clazz in package.findall(".//class"):
            clazz_name = clazz.attrib["name"]
            if clazz.findall(".//method"):
                coverage_data[package_name][clazz_name] = defaultdict()

                for method in clazz.findall(".//method"):
                    method_name = method.attrib["name"]
                    pattern = r"\(.*?\)"
                    parameters = re.findall(pattern, method.attrib["desc"])[0][1:-1]
                    raw_param_list = parameters.split(";")
                    parameter_list = []

                    for param_str in raw_param_list:
                        if param_str == "":
                            continue
                        else:
                            param_stack = []

                            for i in range(len(param_str)):
                                c_str = param_str[i]
                                if c_str == "[":
                                    param_stack.append(c_str)
                                    continue
                                elif c_str == "L":
                                    param_stack.append(param_str[i:])
                                    res = "".join(param_stack)
                                    parameter_list.append(
                                        to_jave_bytecode_types(res).lower()
                                    )
                                    param_stack.clear()
                                    break
                                elif c_str in ["B", "C", "D", "F", "I", "J", "Z", "S"]:
                                    param_stack.append(c_str)
                                    pass
                                else:
                                    raise NotImplementedError(
                                        "Class Type %s not implemented yet." % c_str
                                    )
                                res = "".join(param_stack)
                                parameter_list.append(
                                    to_jave_bytecode_types(res).lower()
                                )
                                param_stack.clear()

                    tmp_list = []
                    for i in parameter_list:
                        if "/" in i:
                            tmp_list.append(i.split("/")[-1])
                        else:
                            tmp_list.append(i)
                    parameter_tuple = tuple(tmp_list)

                    if method_name not in coverage_data[package_name][clazz_name]:
                        coverage_data[package_name][clazz_name][
                            method_name
                        ] = defaultdict()

                    coverage_data[package_name][clazz_name][method_name][
                        parameter_tuple
                    ] = method.attrib["desc"]
                    # if method.find('.//counter[@type="LINE"]') is not None:
                    #     coverage_data[package_name][clazz_name][method_name][
                    #         parameter_tuple
                    #     ]["line_coverage"] = method.find(
                    #         './/counter[@type="LINE"]'
                    #     ).attrib
                    # else:
                    #     coverage_data[package_name][clazz_name][method_name][
                    #         parameter_tuple
                    #     ]["line_coverage"] = None
                    # if method.find('.//counter[@type="BRANCH"]') is not None:
                    #     coverage_data[package_name][clazz_name][method_name][
                    #         parameter_tuple
                    #     ]["branch_coverage"] = method.find(
                    #         './/counter[@type="BRANCH"]'
                    #     ).attrib
                    # else:
                    #     coverage_data[package_name][clazz_name][method_name][
                    #         parameter_tuple
                    #     ]["branch_coverage"] = None
                    #
    return coverage_data


def _check_coverage(directory_path, bug_id, report_dir):
    """
    执行完测试之后，收集coverage数据

    Args:
        directory_path (str): 目标项目的路径
        bug_id (str): 具体的defects4j bug
        report_dir (str): jacoco生成的报告路径

    Returns:
        dict: 经过分析后的jacoco覆盖率指标
    """

    project_name = bug_id
    if bug_paths[project_name]["src_class"][0] != "/":
        class_base = bug_paths[project_name]["src_class"]
    else:
        class_base = bug_paths[project_name]["src_class"][1:]
    class_base_dir = os.path.join(directory_path, class_base)

    if bug_paths[project_name]["src"][0] != "/":
        src_base = bug_paths[project_name]["src"]
    else:
        src_base = bug_paths[project_name]["src"][1:]
    src_base_dir = os.path.join(directory_path, src_base)

    cur_dir = os.getcwd()
    os.chdir(directory_path)

    row_report = f"{report_dir}/report.exec"
    report_file = f"{report_dir}/report.xml"

    commands = [
        "java",
        "-jar",
        f"{code_base}/resources/jacoco/jacococli.jar",
        "report",
        f"{row_report}",
        f"--classfiles {class_base_dir}",
        f"--sourcefiles {src_base_dir}",
        f"--xml {report_file}",
    ]
    cmd = " ".join(commands)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    os.chdir(cur_dir)
    coverage_data = parse_coverage_xml(report_file)
    return coverage_data


def check_test(bug_id, report_dir):
    fixed_passed = False
    fixed_coverage = {}
    buggy_passed = False
    fixed_err_types = []
    fixed_err_info = []
    fixed_dir = os.path.join(d4j_proj_base, f"{bug_id}/fixed")
    buggy_dir = os.path.join(d4j_proj_base, f"{bug_id}/buggy")
    if os.path.exists(fixed_dir) and os.path.exists(buggy_dir):
        if os.path.exists(report_dir):
            os.system(f"rm -rf {report_dir}")
        os.makedirs(report_dir, exist_ok=True)
        environ = f"-javaagent:{code_base}/resources/jacoco/jacocoagent.jar=destfile={report_dir}/report.exec"
        os.environ["JAVA_TOOL_OPTIONS"] = environ
        exec_res = _test_and_collect_results(fixed_dir)
        fixed_coverage = _check_coverage(fixed_dir, bug_id, report_dir)
        del os.environ["JAVA_TOOL_OPTIONS"]
        pass
    else:
        raise FileNotFoundError()
    return {
        "fixed_passed": fixed_passed,
        "buggy_passed": buggy_passed,
        "fixed_coverage": fixed_coverage,
        "fixed_error_types": fixed_err_types,
        "fixed_error_info": fixed_err_info,
    }


def calculate_coverage_stats(
        focal_method,
        fixed_coverage_data,
        method_name,
        package_dir,
        clazz_dir,
        parameter_tuple,
):
    res_dict = {
        "msg": "success",
        "line_coverage_covered": -1,
        "line_coverage_missed": -1,
        "branch_coverage_covered": -1,
        "branch_coverage_missed": -1,
    }

    if method_name in fixed_coverage_data.get(package_dir, {}).get(clazz_dir, {}):
        focal_method_cov = fixed_coverage_data[package_dir][clazz_dir][method_name].get(
            parameter_tuple, None
        )

    else:
        pass
    return res_dict


def parameter_matches(short, full):
    if full.startswith('L') and full.endswith(';'):
        full = full[1:-1]
    if not full.endswith(short.lower()):
        if '<' in short and '>' in short:
            short = short[:short.find('<')]
            if full.endswith(short.lower()):
                return True
        if short == 'char' and full == 'java.lang.character':
            return True
        if short == 'int' and full == 'java.lang.integer':
            return True
        if short == 'char[]' and full == 'java.lang.character[]':
            return True
        if short == 'int[]' and full == 'java.lang.integer[]':
            return True
        return False
    else:
        return True


def process(input):
    bugID, return_val, method_sig = input.split(' ')
    coverage = check_test(bugID, f"{code_base}/outputs/jacoco_reports/{bugID}")['fixed_coverage']
    target_class_name = method_sig.split('#')[0]
    class_name_tokens = target_class_name.rsplit('.')
    package_name = '/'.join(class_name_tokens[:-1])
    class_name = '/'.join(class_name_tokens)
    method_sig = " ".join(method_sig.split('#')[1:])
    left_brace_idx = method_sig.find('(')
    right_brace_idx = method_sig.find(')')
    method_name = method_sig[:left_brace_idx]

    if (package_name not in coverage or
            class_name not in coverage[package_name] or
            method_name not in coverage[package_name][class_name]):
        # package, class or method not found in the coverage result.
        print('no method found')
        pass
    else:
        if len(coverage[package_name][class_name][method_name]) == 1:
            # only one method found, no need to check the parameters.
            return class_name.replace('/', '.') + '.' + method_name + \
                list(coverage[package_name][class_name][method_name].items())[0][1]
        else:
            param_str = method_sig[left_brace_idx + 1:right_brace_idx]
            param_list = param_str.split(',')
            param_type_list = [param.split(' ')[0] for param in param_list]
            candidate_methods = [(param_tuple, desc) for param_tuple, desc in
                                 coverage[package_name][class_name][method_name].items() if
                                 len(param_tuple) == len(param_type_list)]
            if len(candidate_methods) == 1:
                return class_name.replace('/', '.') + '.' + method_name + str(candidate_methods[0][1])
            else:
                matched_desc = None
                for param_tuple, desc in candidate_methods:
                    if all(parameter_matches(short, full) for short, full in zip(param_type_list, param_tuple)):
                        matched_desc = desc
                        break
                if matched_desc:
                    return class_name.replace('/', '.') + '.' + method_name + str(matched_desc)
                return ""


if __name__ == '__main__':
    inputs = []
    with open(f"{code_base}/resources/fm_signatures.txt", 'r', encoding="utf-8") as f:
        for line in f.readlines():
            inputs.append(line.strip())
    writer = open(f'{code_base}/outputs/bytecode_signatures.txt', 'w', encoding='utf-8')
    idx = 0
    for input in tqdm(inputs):
        try:
            bytecode_signature = process(input)
            if bytecode_signature:
                writer.write(json.dumps({
                    'idx': idx,
                    "bug_id": input.split()[0],
                    "bytecode_signature": bytecode_signature
                }, ensure_ascii=False) + '\n')
            else:
                logger.error(f'{input.split()[0]} has no valid focal method.')
        except Exception as e:
            logger.error(f'Got {str(e)} when processing {input}')
        finally:
            idx += 1

    pass
