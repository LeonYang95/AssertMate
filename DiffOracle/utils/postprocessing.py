import re
import javalang
import tree_sitter_java as ts_java
from tree_sitter import Parser, Language

language = Language(ts_java.language())
parser = Parser(language)


def normalize_junit_assertion(code):
    # 改进正则表达式，正确匹配字符串和字符字面量
    string_pattern = r'"(?:\\.|[^"\\])*"'  # 匹配双引号字符串
    string_pattern += r"|'(?:\\.|[^'\\])*'"  # 匹配单引号字符串

    # 使用re.split分割字符串和非字符串部分
    tokens = re.split(f'({string_pattern})', code)

    new_tokens = []
    for token in tokens:
        if re.fullmatch(string_pattern, token):
            new_tokens.append(token)
        else:
            normalized_token = re.sub(r'\s+', '', token)
            new_tokens.append(normalized_token)
    return ''.join(new_tokens)


def extract_assertion_from_response(llm_response: str) -> str:
    if llm_response == '':
        return ''
    lines = llm_response.split('\n')
    code_lines = []
    in_code_block = False
    for line in lines:
        if line.startswith('```'):
            if in_code_block:
                in_code_block = False
            else:
                in_code_block = True
        elif in_code_block:
            code_lines.append(line)
        else:
            pass
    if len(code_lines) == 1:
        return normalize_junit_assertion(code_lines[0].strip())
    code = '\n'.join(code_lines)

    # parse assertions
    cls_str = 'public class ABC { ' + code + ' }'
    assertions = []
    tree = parser.parse(bytes(cls_str, "utf-8"))
    if tree.root_node.has_error:
        cls_str = 'public class ABC { public void test() { ' + code + ' } }'
        tree = parser.parse(bytes(cls_str, "utf-8"))
        if tree.root_node.has_error:
            return ''
    query = language.query("(expression_statement) @exp")
    groups = query.captures(tree.root_node)
    for group in groups:
        child = group[0]
        if (child.children[0].type == 'method_invocation' and
                child.children[0].child_by_field_name('name').text.decode('utf-8').startswith('assert')):
            assertions.append(child.text.decode('utf-8'))
            pass
    return normalize_junit_assertion(assertions[0])

def get_normalized_ast(code):
    try:
        tree = javalang.parse.parse_expression(code)
    except (javalang.tokenizer.LexerError, javalang.parser.JavaSyntaxError):
        return None
    # 将AST转换为可比较的元组
    return ast_to_tuple(tree)

def ast_to_tuple(node):
    if isinstance(node, list):
        return [ast_to_tuple(child) for child in node]
    elif hasattr(node, 'children'):
        children = [ast_to_tuple(child) for child in node.children]
        node_type = type(node).__name__
        # 提取节点的关键属性
        attributes = {k: v for k, v in node.__dict__.items() if not k.startswith('_') and k != 'children'}
        return (node_type, attributes, children)
    else:
        return node

