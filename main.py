from config import *


def load_arg_params():
    parser = argparse.ArgumentParser(description='LLM-based unit test generation.')
    parser.add_argument('--project', type=str, help='Project name.')
    parser.add_argument('--project-path', type=str, help='Path to the repository code base.', required=True)
    parser.add_argument('--config-file', type=str, default=f"{code_base}/config/basic_config.yaml",
                        help='Path to the configuration file', required=True)
    parser.add_argument('--source-code-path', type=str, default=f"src/main",
                        help='Relative path from the project path to the source code. By default, it is set as src/main')
    parser.add_argument('--test-code-path', type=str, default=f"src/test",
                        help='Relative path from the project path to the test code. By default, it is set as src/test')
    parser.add_argument('--output-file', type=str, default=f"outputs/default.jsonl",
                        help='Path of the JSONL file to store the generated test classes.')
    args = parser.parse_args()
    return args

if __name__ == '__main__':
    args = load_arg_params()
    logger.info('==== Received Arguments ====')
    for attr_name in dir(args):
        if attr_name.startswith('_'): continue
        logger.info(f"{attr_name}: {getattr(args, attr_name)}")
    logger.info('============================')
    project_name = 'jfreechart'
    target_project_base = os.path.join(code_base,f'resources/{project_name}')

    pass
