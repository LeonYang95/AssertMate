import tree_sitter_java as ts_java
from loguru import logger
from tree_sitter import Parser, Language, Node

from config import *

parser = Parser(Language(ts_java.language()))


# 提取 test prefix
def parse_assertions(method_str: str) -> list:
    """
    This function parses the assertions from a given method string.

    Args:
        method_str (str): The method string to parse assertions from.

    Returns:
        list: A list of assertion statements found in the method, along with its corresponding expression_statement node.
    """
    assertions = []
    cls_str = 'public class ABC {' + method_str + '}'
    tree = parser.parse(bytes(cls_str, "utf-8"))
    language = Language(ts_java.language())
    query = language.query("(expression_statement) @exp")
    groups = query.captures(tree.root_node)
    for group in groups:
        child = group[0]
        if (child.children[0].type == 'method_invocation' and
                child.children[0].child_by_field_name('name').text.decode('utf-8') in known_assertions):
            assertions.append((child.text.decode('utf-8'), child))
            pass
    return assertions


def parse_expected_value(node: Node, log=True) -> tuple:
    raw_assertion = node.text.decode('utf-8')
    num_argument_children = len(node.children[0].children_by_field_name('arguments')[0].children)
    if num_argument_children == 5:
        # 2 parameters
        # by default, we select the first one as expected value, according to the Junit Api Document.
        expected_value = node.children[0].children_by_field_name('arguments')[0].children[1].text.decode('utf-8')
        actual_value = node.children[0].children_by_field_name('arguments')[0].children[3].text.decode('utf-8')
        processed_assertion = node.text.decode('utf-8').replace(expected_value, '<expected_value>', 1)
        return actual_value, expected_value, processed_assertion, raw_assertion
    elif num_argument_children == 7:
        # 3 parameters
        argument_children = [n for n in node.children[0].children_by_field_name('arguments')[0].children if
                             n.type not in [',', '(', ')']]
        if argument_children[0].type == 'string_literal':
            expected_value_node = argument_children[1]
            actual_value_node = argument_children[2]
        elif argument_children[-1].type in ['decimal_integer_literal', 'decimal_floating_point_literal']:
            expected_value_node = argument_children[0]
            actual_value_node = argument_children[1]
        elif argument_children[0].type in ['decimal_floating_point_literal']:
            expected_value_node = argument_children[0]
            actual_value_node = argument_children[1]
        elif argument_children[0].type in ['binary_expression']:
            if any([n.type == 'string_literal' for n in argument_children[0].children]):
                expected_value_node = argument_children[1]
                actual_value_node = argument_children[2]
            elif any([n.type in ['*', '*', '-'] for n in argument_children[0].children]):
                if not log: logger.warning('Complex binary expression detected, skipping.')
                return None,None, None, raw_assertion
            else:
                if not log: logger.warning(
                    f'Unexpected argument type: {argument_children[0].type} from {node.text.decode("utf-8")}')
                return None,None, None, raw_assertion
            pass
        else:
            if not log: logger.warning(
                f'Unexpected argument type: {argument_children[0].type} from {node.text.decode("utf-8")}')
            return None, None, None, raw_assertion
        expected_value = expected_value_node.text.decode('utf-8')
        actual_value = actual_value_node.text.decode('utf-8')
        processed_assertion = node.text.decode('utf-8').replace(expected_value, '<expected_value>', 1)
        return actual_value, expected_value, processed_assertion, raw_assertion
    elif num_argument_children == 9:
        # 4 parameters, only the second or the third could possibly be the expected value.
        # According to the junit api, we select the second one as expected value.
        argument_children = [n for n in node.children[0].children_by_field_name('arguments')[0].children if
                             n.type not in [',', '(', ')']]
        expected_value_node = argument_children[1]
        actual_value_node = argument_children[2]
        actual_value = actual_value_node.text.decode('utf-8')
        expected_value = expected_value_node.text.decode('utf-8')
        processed_assertion = node.text.decode('utf-8').replace(expected_value, '<expected_value>', 1)
        return actual_value, expected_value, processed_assertion, raw_assertion
    else:
        if log: logger.warning(
            f'Unexpected argument count: {num_argument_children - 2} of {node.text.decode("utf-8")}')
        return None, None, None, raw_assertion

def parse_assert_boolean(node: Node, log=True) -> tuple:
    raw_assertion = node.text.decode('utf-8')
    num_argument_children = len(node.children[0].children_by_field_name('arguments')[0].children)
    expected_value = 'assertTrue' if 'assertTrue' in node.children[0].children_by_field_name('name')[0].text.decode(
        'utf-8') else 'assertFalse'

    if num_argument_children == 5:
        # 2 parameters
        # by default, we select the second one as expected value, according to the Junit Api Document.
        argument_child = node.children[0].children_by_field_name('arguments')[0].children[3]
        if argument_child.type == 'string_literal':
            argument_child = node.children[0].children_by_field_name('arguments')[0].children[1]
        actual_value = argument_child.text.decode('utf-8')
        processed_assertion = f'assertEquals(<expected_value>, {actual_value});'
        return expected_value, actual_value, raw_assertion
    elif num_argument_children == 3:
        # 1 parameter
        actual_value = node.children[0].children_by_field_name('arguments')[0].children[1].text.decode('utf-8')

        processed_assertion = f'assertEquals(<expected_value>, {actual_value});'
        return expected_value, actual_value,raw_assertion
    else:
        if log: logger.error(
            f'Unexpected argument count: {num_argument_children - 2} of {node.text.decode("utf-8")}')
        return None, None, raw_assertion

def parse_assert_null_values(node: Node, log=True) -> tuple:
    raw_assertion = node.text.decode('utf-8')
    num_argument_children = len(node.children[0].children_by_field_name('arguments')[0].children)
    expected_value = 'assertNull' if 'assertNull' in node.children[0].children_by_field_name('name')[0].text.decode(
        'utf-8') else 'assertNotNull'

    if num_argument_children == 5:
        # 2 parameters
        # by default, we select the second one as expected value, according to the Junit Api Document.
        argument_child = node.children[0].children_by_field_name('arguments')[0].children[3]
        if argument_child.type == 'string_literal':
            argument_child = node.children[0].children_by_field_name('arguments')[0].children[1]
        actual_value = argument_child.text.decode('utf-8')
        return expected_value, actual_value, raw_assertion
    elif num_argument_children == 3:
        # 1 parameter
        actual_value = node.children[0].children_by_field_name('arguments')[0].children[1].text.decode('utf-8')

        return expected_value, actual_value,raw_assertion
    else:
        if log: logger.error(
            f'Unexpected argument count: {num_argument_children - 2} of {node.text.decode("utf-8")}')
        return None, None, raw_assertion



def parse_nloc_in_method(method_str: str) -> int:
    class_str = 'public class ABC {' + method_str + '}'
    tree = parser.parse(bytes(class_str, "utf-8"))
    for child in tree.root_node.children[0].children:
        if child.type == 'class_body':
            method_decl = child.children[1]
            try:
                assert method_decl.type == 'method_declaration'
            except AssertionError:
                return 0
            for c in method_decl.children:
                if c.type == 'block':
                    return len(c.children) - 2
        pass
    return 0


def parse_variables(method_str: str):
    class_str = 'public class ABC {' + method_str + '}'
    tree = parser.parse(bytes(class_str, "utf-8"))
    variables = []
    for child in tree.root_node.children[0].children:
        if child.type == 'class_body':
            method_decl = child.children[1]
            try:
                assert method_decl.type == 'method_declaration'
            except AssertionError:
                return []
            for c in method_decl.children:
                if c.type == 'block':
                    for block_child in c.children:
                        if block_child.type == 'local_variable_declaration':
                            variables.append(block_child.text.decode('utf-8'))
    return variables


def parse_method_name(method: str):
    class_str = 'public class ABC {' + method + '}'
    tree = parser.parse(bytes(class_str, "utf-8"))
    if tree.root_node.has_error: return None
    for child in tree.root_node.children[0].children:
        if child.type == 'class_body':
            method_decl = child.children[1]
            try:
                assert method_decl.type == 'method_declaration'
            except AssertionError:
                return None
            for child in method_decl.children:
                if child.type == 'identifier':
                    return child.text.decode('utf-8')
    return None


if __name__ == '__main__':
    # print(parse_variables('public void main(){\n int i = 1; \nint j =2; \nSystem.out.println("Hello World");\n}'))
    print(parse_method_name(
        'void process ( ) { try { personSaver . savePerson ( person ) ; return true ; } catch ( FailedToSavedPersonDataException e ) { System . err . printf ( "Exception occurred while trying save person data [%s]%n" , e ) ; return false ; } }'))
