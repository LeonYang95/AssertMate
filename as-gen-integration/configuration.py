import os
from tree_sitter import Language
import tree_sitter_java as tsjava

d4j_home = "/Users/yanglin/Documents/Projects/data/defects4j"
d4j_proj_base = f"{d4j_home}/d4j_projects"
output_dir = "data/results/example"
code_base = os.path.abspath(os.path.dirname(__file__))
output_base_dir = os.path.join(code_base, output_dir)
d4j_command = f"{d4j_home}/framework/bin/defects4j"
python_bin = "~/anaconda3/envs/codebot/bin/python"

JAVA_LANGUAGE = Language(tsjava.language())

RES_FILE = "/Users/yanglin/Documents/Projects/code-bot/data/outputs/deepseek-coder-6.7b-instruct_comment_extend_full.jsonl"
TMP_FOLDER = "/Users/yanglin/Documents/Projects/code-bot/data/tmp"
GRANULARITY = 'method'
OUTPUT_FILE = '/Users/yanglin/Documents/Projects/example.jsonl'

proxy_host = None
proxy_port = None
proxy_username = None
proxy_password = None

projects = [
    "JxPath",
    "Cli",
    "Math",
    "Csv",
    "Compress",
    "JacksonDatabind",
    "Time",
    "Collections",
    "JacksonXml",
    # "Mockito",
    "JacksonCore",
    "Lang",
    "Jsoup",
    "Chart",
    "Gson",
    "Closure",
    "Codec",
]

target_models = [
    # "WizardCoder-Python-34B-V1.0",
    # "CodeLlama-7b-hf",
    # "CodeLlama-7b-Instruct-hf",
    # "CodeLlama-13b-hf",
    # "CodeLlama-13b-Instruct-hf",
    # "CodeLlama-34b-hf",
    # "CodeLlama-34b-Instruct",
    "deepseek-coder-6.7b-instruct",
    # "deepseek-coder-33b-instruct",
    # "Phind-CodeLlama-34B-v2",
    # "starchat-beta",
    # "WizardCoder-15B-V1.0"，
    # "gpt4"
]

formats = [
    "comment",
    # 'natural'
]

strategies = [
    # 'generation',
    "extend"
]

ablations = [
    "full",
    # 'no_param',
    # 'no_param_constructor',
    # 'no_class_constructor',
    # 'no_class_fields',
    # 'no_class_other_methods'
]
