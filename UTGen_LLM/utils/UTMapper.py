import json
import os
import subprocess
import sys

from tqdm import tqdm

sys.path.extend([".", ".."])
from utils.JavaAnalyzer import *

d4j_project_home ="/data/defects4j/evo_projects"
code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

primitive_and_wrapper_types = [
    "String",
    "Number",
    "Integer",
    "Double",
    "Float",
    "Long",
    "Short",
    "Byte",
    "Character",
    "Boolean",
    "boolean",
    "int",
    "char",
    "double",
    "float",
    "long",
    "short",
    "byte",
]
STL_type = [
    "List",
    "Map",
    "Set",
    "Queue",
    "Deque",
    "Stack",
    "PriorityQueue",
    "ArrayList",
    "LinkedList",
    "Vector",
    "HashMap",
    "TreeMap",
    "LinkedHashMap",
    "HashSet",
    "TreeSet",
    "LinkedHashSet",
    "PriorityQueue",
    "ArrayDeque",
    "Stack",
]


def load_bug_analysis_results():
    bug_analysis_results = {}
    dumped_file = f"{code_base}/outputs/project_class_method.json"
    if os.path.exists(dumped_file):
        with open(dumped_file, "r") as r:
            bug_analysis_results = json.load(r)
    return bug_analysis_results


def save_bug_analysis_results(updated):
    with open(
        f"{code_base}/outputs/project_class_method.json", "w", encoding="utf-8"
    ) as w:
        w.write(json.dumps(updated, ensure_ascii=False))


def analyze_one_bug(bug_id, paths):
    res_dict = {bug_id: {}}
    src_code_dir = os.path.join(d4j_project_home, f"{bug_id}/fixed/{paths['src']}")
    for root, dirs, files in os.walk(src_code_dir):
        for file in files:
            if file.endswith(".java"):
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        class_obj = parse_class_object_from_file_content(f.read())
                        if class_obj:
                            declared_methods = [
                                m.signature
                                for _, m in class_obj.methods.items()
                                if m.is_public
                                and contains_only_one_return_statement(m.text)
                                and not m.parameters
                            ]
                            if declared_methods:
                                res_dict[bug_id][class_obj.signature] = declared_methods
                except UnicodeDecodeError:
                    logger.warning(
                        f"Failed to read {file} in {bug_id} due to UnicodeDecodeError."
                    )
                    continue
    return res_dict


def file_by_method_sig(method_signature):
    cls_sig = method_signature.split("::")[0]
    sig_tks = cls_sig.split(".")
    pkg_path = os.path.sep.join(sig_tks[:-1])
    cls_path = sig_tks[-1] + ".java"
    return os.path.join(pkg_path, cls_path)


def dir_by_method_pkg(method_signature):
    cls_sig = method_signature.split("::")[0]
    sig_tks = cls_sig.split(".")
    pkg_path = os.path.sep.join(sig_tks[:-1])
    return pkg_path


def file_by_class_sig(class_signature):
    path = class_signature.replace(".", "/")
    path += ".java"
    return path


def process_one_bug_by_triggering_tests(bug_id, paths):

    jsondicts = []
    fm_objs = []
    src_cls_objs = []
    test_cls_objs = []
    target_project_dir = os.path.join(d4j_project_home, bug_id, "fixed")
    if not os.path.exists(target_project_dir):
        logger.warning(f"Fixed version of bug id {bug_id} does not exist.")
        return None, None
    src_dir = paths["src"]
    test_dir = paths["test"]
    os.chdir(target_project_dir)
    res = subprocess.run(
        f"defects4j export -p tests.trigger",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if res.returncode != 0:
        pass
    else:
        bug_trigger_tests = res.stdout.decode("utf-8").strip().split("\n")
        for tc_signature in bug_trigger_tests:
            test_class_file = os.path.join(
                target_project_dir, test_dir, file_by_method_sig(tc_signature)
            )

            # in case there is a junit in package
            if "junit" in tc_signature:
                tc_signature = tc_signature.replace("junit.", "")
                pass

            source_package_dir = os.path.join(
                target_project_dir, src_dir, dir_by_method_pkg(tc_signature)
            )
            test_class_name = tc_signature.split("::")[0].split(".")[-1]
            if os.path.exists(test_class_file) and os.path.exists(source_package_dir):
                source_class_file = None
                for entry in os.listdir(source_package_dir):
                    if (
                        entry.endswith(".java")
                        and entry.split(".")[0] in test_class_name
                    ):
                        source_class_file = os.path.join(source_package_dir, entry)
                        break
                    pass
                if not source_class_file:
                    logger.warning(f"No source class file found for {tc_signature}.")
                    continue
                    pass
                try:
                    with open(test_class_file, "r", encoding="utf-8") as reader:
                        test_class = reader.read()
                    with open(source_class_file, "r", encoding="utf-8") as reader:
                        source_class = reader.read()
                except UnicodeDecodeError:
                    logger.warning(f"{bug_id} contains non-utf-8 encoded files.")
                    continue
                tc_invoked_method_list = extract_method_invocation(
                    test_class,
                    target_class_name=test_class_name,
                    target_method_name=tc_signature.split("::")[-1],
                )
                tc_invoked_methods = set(tc_invoked_method_list)
                if not tc_invoked_methods:
                    logger.warning(
                        f"No method invocation found in {tc_signature} for {bug_id} bug."
                    )
                    continue
                if not any(
                    [
                        assert_type in tc_invoked_methods
                        for assert_type in [
                            "assertEquals",
                            "assertTrue",
                            "assertFalse",
                            "assertNull",
                            "assertNotNull",
                        ]
                    ]
                ):
                    logger.warning(
                        f"No valid assertions found in {tc_signature} for {bug_id} bug."
                    )
                    continue
                src_cls_obj = parse_class_object_from_file_content(
                    source_class, source_class_file.split(os.path.sep)[-1].split(".")[0]
                )

                if not src_cls_obj:
                    logger.warning(
                        "Source class is not a class, maybe an abstract class or interface."
                    )
                    continue

                test_cls_obj = parse_class_object_from_file_content(
                    test_class, test_class_name
                )
                defined_methods = set([m.name for _, m in src_cls_obj.methods.items()])
                intersection_of_methods = tc_invoked_methods.intersection(
                    defined_methods
                )
                if len(intersection_of_methods) == 1:
                    # 找到了待测函数
                    # 字段：待测函数，包括函数定义和函数体
                    focal_method_name = intersection_of_methods.pop()
                    focal_method_obj = [
                        m
                        for sig, m in src_cls_obj.methods.items()
                        if m.name == focal_method_name
                    ][0]
                    test_case_name = tc_signature.split("::")[-1]
                    test_method_obj = [
                        m
                        for sig, m in test_cls_obj.methods.items()
                        if m.name == test_case_name
                    ][0]

                    splitted_test_cases = split_test_case_by_assertion(
                        test_method_obj.text
                    )
                    for test_case in splitted_test_cases:
                        jsondict = {
                            "bug_id": bug_id,
                            "version": "fixed",
                            "focal_method_signature": focal_method_obj.signature,
                            "test_case_signature": tc_signature,
                            "test_file": test_class_file,
                            "source_file": source_class_file,
                            "focal_method": focal_method_obj.text,  # focal method
                            "return_type": focal_method_obj.return_type,
                            "test_case": test_case,  # test method
                            "parent_test_case": test_method_obj.text,
                            "test_case_invocations": tc_invoked_method_list,
                            "test_class": {
                                "path": test_class_file,
                                "imports": test_cls_obj.imports,  # 引用
                                "fields": [
                                    str(f) for k, f in test_cls_obj.fields.items()
                                ],  # 定义的属性
                                "methods": [
                                    m.signature
                                    for k, m in test_cls_obj.methods.items()
                                    if k != test_method_obj.signature
                                ],  # 定义的函数
                                "text": test_class,  # 完整的测试类
                            },
                            "focal_class": {
                                "name": src_cls_obj.name,
                                "path": source_class_file,
                                "superclass": src_cls_obj.superclass,
                                "interface": src_cls_obj.interface,
                                "imports": src_cls_obj.imports,  # 引用
                                "fields": [
                                    str(f) for k, f in src_cls_obj.fields.items()
                                ],  # 定义的属性
                                "methods": [
                                    m.signature
                                    for k, m in src_cls_obj.methods.items()
                                    if k != focal_method_obj.signature
                                ],  # 定义的函数
                                "other_methods": [
                                    m.short_definition
                                    for m in src_cls_obj.public_methods
                                    if m.signature != focal_method_obj.signature
                                ],
                                "fields_dict": dict(
                                    [(k, str(f)) for k, f in src_cls_obj.fields.items()]
                                ),
                                "text": source_class,  # 完整的待测类
                            },
                        }
                        jsondicts.append(pickle.loads(pickle.dumps(jsondict)))
                        fm_objs.append(focal_method_obj)
                        src_cls_objs.append(src_cls_obj)
                        test_cls_objs.append(test_cls_obj)
                    return jsondicts, (fm_objs, src_cls_objs, test_cls_objs)
                pass
            else:
                logger.warning(
                    f"Either {test_class_file} or {source_package_dir} does not exist."
                )
                continue
            pass
    return None, None


def process_one_bug_by_modified_classes(bug_id, paths) -> list:
    class_methods = load_bug_analysis_results()
    if bug_id not in class_methods:
        class_methods.update(analyze_one_bug(bug_id, paths))
        # save_bug_analysis_results(class_methods)
    class_methods = class_methods[bug_id]
    jsondicts = []
    target_project_dir = os.path.join(d4j_project_home, bug_id, "fixed")
    if not os.path.exists(target_project_dir):
        logger.warning(f"Fixed version of bug id {bug_id} does not exist.")
        return []
    src_dir = paths["src"]
    os.chdir(target_project_dir)
    res = subprocess.run(
        f"defects4j export -p classes.modified",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if res.returncode != 0:
        logger.error(f"Defects4j command failed for {bug_id}. Please check")
        return []
    else:
        modified_classes = res.stdout.decode("utf-8").strip().split("\n")
        for class_signature in modified_classes:
            source_class_file = os.path.join(
                target_project_dir, src_dir, class_signature.replace(".", "/") + ".java"
            )
            if os.path.exists(source_class_file):
                try:
                    with open(source_class_file, "r", encoding="utf-8") as reader:
                        source_class = reader.read()
                except UnicodeDecodeError:
                    logger.warning(
                        f"{source_class_file} contains non-utf-8 encoded files."
                    )
                    continue
                src_cls_obj = parse_class_object_from_file_content(
                    source_class, class_signature.split(".")[-1]
                )
                if not src_cls_obj:
                    logger.warning(
                        "Source class is not a class, maybe an abstract class or interface."
                    )
                    continue
                public_methods = [
                    m for _, m in src_cls_obj.methods.items() if m.is_public
                ]
                for method in public_methods:
                    if method.name.startswith(
                        "get"
                    ) and contains_only_one_return_statement(method.text):
                        logger.info(f"Method {method.name} is a getter method.")
                        continue
                    nloc = method.text.strip().count("\n") - 1
                    if nloc < 5:
                        logger.info(
                            f"Method {method.name} is excluded due to nloc < 5."
                        )
                        continue

                    assertion_subject_candidates = []
                    # 找一下 return type 对应的 class 信息
                    return_type = method.return_type
                    focal_class_imports = src_cls_obj.imports
                    if return_type != "void":
                        if (
                            return_type in primitive_and_wrapper_types
                            or return_type in STL_type
                        ):
                            assertion_subject_candidates.append(return_type)
                        elif any(
                            [i.endswith(return_type) for i in focal_class_imports]
                        ):
                            imported_class = [
                                i.endswith(return_type) for i in focal_class_imports
                            ]
                            try:
                                assert len(imported_class) == 1

                            except AssertionError:
                                logger.error(
                                    "Found multiple imports with same name, please check."
                                )
                            pass
                        else:
                            imports_with_star = [
                                i.split()[-1][:-1]
                                for i in focal_class_imports
                                if i.endswith(".*")
                            ]
                            imports_with_star.append(src_cls_obj.package_name + ".*")
                            for imported_class in imports_with_star:
                                target_class = imported_class.replace("*", return_type)
                                if target_class in class_methods:
                                    assertion_subject_candidates.extend(
                                        class_methods[target_class]
                                    )
                                    break
                                pass
                            pass
                    # 检查当前类的 getter
                    getters = [
                        m.signature
                        for _, m in src_cls_obj.methods.items()
                        if m.name.startswith("get")
                        and contains_only_one_return_statement(m.text)
                    ]
                    if getters:
                        assertion_subject_candidates.extend(getters)

                    jsondict = {
                        "bug_id": bug_id,
                        "version": "fixed",
                        "focal_method_signature": method.signature,
                        "source_file": source_class_file,
                        "focal_method": method.text,  # focal method
                        "return_type": method.return_type,
                        "assertion_subject_candidates": assertion_subject_candidates,
                        "focal_class": {
                            "name": src_cls_obj.name,
                            "path": source_class_file,
                            "superclass": src_cls_obj.superclass,
                            "interface": src_cls_obj.interface,
                            "imports": src_cls_obj.imports,  # 引用
                            "fields": [
                                str(f) for k, f in src_cls_obj.fields.items()
                            ],  # 定义的属性
                            "methods": [
                                m.signature
                                for k, m in src_cls_obj.methods.items()
                                if k != method.signature
                            ],  # 定义的函数
                            "other_methods": [
                                m.short_definition
                                for m in src_cls_obj.public_methods
                                if m.signature != method.signature
                            ],
                            "fields_dict": dict(
                                [(k, str(f)) for k, f in src_cls_obj.fields.items()]
                            ),
                            "text": source_class,  # 完整的待测类
                        },
                    }
                    jsondicts.append(pickle.loads(pickle.dumps(jsondict)))
            else:
                logger.error(f"Source class file {source_class_file} does not exist.")
                continue
        return jsondicts


if __name__ == "__main__":
    code_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    from collections import Counter

    return_type_counter = Counter()
    with open(os.path.join(code_base, "bug_path_mapping.json"), "r") as r:
        bug_paths = json.load(r)

    print(len(bug_paths.keys()))    
    # output_writer = open(
    #     os.path.join(code_base, "outputs/defects4j_inputs_with_candidates_triggering_tests-1.jsonl"),
    #     "w",
    #     encoding="utf-8",
    # )
    # for bug_id, paths in tqdm(bug_paths.items()):
    #     jsondicts, _ = process_one_bug_by_triggering_tests(bug_id, paths)
    #     if not jsondicts:
    #         continue
    #     for one_dict in jsondicts:
    #         output_writer.write(json.dumps(one_dict, ensure_ascii=False) + "\n")
    # output_writer.close()
    # pass
