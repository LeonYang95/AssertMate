import sys

sys.path.extend([".", ".."])

import os
import json
from loguru import logger
from tqdm import *
from multiprocessing import Pool
from utils.UTGenerator import BasicGenerator
from entities.CodeEntities import Method, Class

code_base = os.path.abspath(os.path.dirname(__file__))


def inference(input):
    generator = BasicGenerator()
    i, cur_data = input
    output_writer = open(
        os.path.join(code_base, f"outputs/integration_llm_base_uts.jsonl_{i}"),
        "w",
        encoding="utf-8",
    )
    for group in tqdm(cur_data):
        response = generator.generate(
            method_instance=group[0], class_instance=group[1], other_methods=group[2]
        )
        jsondict = group[3]
        jsondict["generated_test_class"] = response
        output_writer.write(json.dumps(jsondict, ensure_ascii=False) + "\n")
    output_writer.close()


if __name__ == "__main__":

    data = []
    with open(
        os.path.join(code_base, "outputs/defects4j_inputs_with_candidates.jsonl"), "rb"
    ) as reader:
        for line in reader.readlines():
            input_obj = json.loads(line.strip())
            fm_obj = Method(
                name="",
                modifier="",
                text=input_obj["focal_method"],
                return_type="",
                params=[],
                class_sig="",
                docstring="",
            )
            fm_obj._signature = input_obj["focal_method_signature"]
            fc_obj = Class(
                package_name="",
                modifier="",
                name=input_obj["focal_class"]["name"],
                text=input_obj["focal_class"]["text"],
                imports=input_obj["focal_class"]["imports"],
                superclass=input_obj["focal_class"]["superclass"],
                interface=input_obj["focal_class"]["interface"],
            )
            fc_obj._fields = input_obj["focal_class"]["fields_dict"]
            other_methods = input_obj["focal_class"]["other_methods"]
            data.append((fm_obj, fc_obj, other_methods, input_obj))

    num_process = 10
    num_per_chunk = len(data) // num_process + 1
    chunks = [
        (i, data[i * num_per_chunk : (i + 1) * num_per_chunk])
        for i in range(num_process)
    ]
    with Pool(processes=num_process) as pool:
        pool.map(inference, chunks)

    logger.info("All Done")
    pass
