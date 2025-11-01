import sys

sys.path.extend([".", ".."])
from tree_sitter import Parser, Language, Node
import tree_sitter_java as tsjava
from loguru import logger

from entities.CodeEntities import *

java_language = Language(tsjava.language())
parser = Parser(java_language)
valid_assertions = ['assertEquals', 'assertTrue', 'assertFalse', 'assertNull', 'assertNotNull']


def getClassBodyNode(classStr: str):
    """
    Parses the given Java class string and returns the body of the public class if it exists.

    Args:
        classStr (str): The Java class code as a string.

    Returns:
        tree_sitter.Node: The body node of the public class if found, otherwise None.
    """
    tree = parser.parse(bytes(classStr, "utf-8"))
    if tree.root_node.has_error:
        return None
    else:
        classDeclarationNodes = [node for node in tree.root_node.children if node.type == 'class_declaration']
        publicClassDeclarationNodes = [node for node in classDeclarationNodes if
                                       'public' in node.children[0].text.decode('utf-8')]
        if len(publicClassDeclarationNodes) == 1:
            classBody = publicClassDeclarationNodes[0].child_by_field_name('body')
            return classBody
        else:
            logger.error(f"found {len(publicClassDeclarationNodes)} public class declaration in :\n{classStr}")
            return None


def parseDeclaraedFields(classStr: str):
    """
      Parses the fields from the given Java class string.

      Args:
          classStr (str): The Java class code as a string.

      Returns:
          list: A list of dictionaries, each containing information about a field in the class.
                Each dictionary has the following keys:
                - field_name (str): The name of the field.
                - field_type (str): The type of the field.
                - field_modifiers (str): The modifiers of the field (e.g., public, private).
                - declaration_text (str): The full declaration text of the field.
      """
    classBodyNode = getClassBodyNode(classStr)

    # In case there is no valid class body
    if not classBodyNode:
        return None

    fieldDeclarationNodes = [node for node in classBodyNode.children if node.type == 'field_declaration']
    rets = []
    for node in fieldDeclarationNodes:
        # find modifiers
        modifierNodes = [n for n in node.children if n.type == 'modifiers']
        if modifierNodes:
            modifiers = modifierNodes[0].text.decode('utf-8')
        else:
            modifiers = 'private'

        declarator = node.child_by_field_name('declarator')
        name = declarator.child_by_field_name('name').text.decode('utf-8')
        declaration = declarator.text.decode('utf-8')
        type = node.child_by_field_name('type').text.decode('utf-8')
        rets.append({
            "field_name": name,
            "field_type": type,
            "field_modifiers": modifiers,
            "declaration_text": declaration,
        })
    return rets


def parseImports(classStr: str):
    rets = []
    tree = parser.parse(bytes(classStr, "utf-8"))
    importDeclarationNodes = [node for node in tree.root_node if node.type == 'import_declaration']
    for node in importDeclarationNodes:
        rets.append({
            'start': node.start_point[0],
            'end': node.end_point[0],
            'text': node.text.decode('utf-8')
        })
    return rets


def parseMethods(classStr: str, requiredModifier=None):
    """
    Analyze methods defined in the class.
    :param classStr:
    :return: list of collected methods. The elements are like:
                    {
                        "method_name": method_name,
                        "method_modifiers": method_modifiers,
                        "method_return_type": method_return_type,
                        "method_body": method_body,
                        "method_text": method_text,
                        "method_start_line": method start line,
                        "method_end_line": method end line
                    }
    """
    rets = []

    classBodyNode = getClassBodyNode(classStr)

    if not classBodyNode:
        return None

    methodDeclarationNodes = [node for node in classBodyNode.children if node.type == 'method_declaration']

    for node in methodDeclarationNodes:
        name = node.child_by_field_name('name').text.decode('utf-8')
        returnType = node.child_by_field_name('type').text.decode('utf-8')
        body = node.child_by_field_name('body').text.decode('utf-8')
        startLine = node.start_point[0]
        endLine = node.end_point[0]
        text = node.text.decode('utf-8')
        modifierNodes = [n.text.decode('utf-8') for n in node.children if n.type == 'modifiers']
        if modifierNodes:
            # modifier不为空，如果有指定 modifier，且不满足要求，则跳过该函数
            if requiredModifier and requiredModifier not in modifierNodes[0]:
                continue
            modifiers = modifierNodes[0]
        else:
            if requiredModifier:
                # 有指定 modifier 要求，但是函数 modifier 为空，则跳过该函数
                continue
            modifiers = 'private'
        rets.append({
            "method_name": name,
            "method_modifiers": modifiers,
            "method_return_type": returnType,
            "method_body": body,
            "method_text": text,
            "method_start_line": startLine,
            "method_end_line": endLine,
        })
        pass
    return rets


def parseClassName(classStr):
    tree = parser.parse(bytes(classStr, "utf-8"))
    if tree.root_node.has_error:
        return None
    else:
        classDeclarationNodes = [node for node in tree.root_node.children if node.type == 'class_declaration']
        return classDeclarationNodes[0].child_by_field_name('name').text.decode('utf-8')


def parseAssertions(methodStr: str):
    assertions = []
    classStr = 'public class A { ' + methodStr + ' }'
    classBodyNode = getClassBodyNode(classStr)
    if not classBodyNode:
        return None

    methodDeclarationNodes = [node for node in classBodyNode.children if node.type == 'method_declaration']

    for node in methodDeclarationNodes:
        methodBodyNode = node.child_by_field_name('body')
        methodBodyLines = methodStr.split('\n')
        expressionNodes = [n for n in methodBodyNode.children if n.type == 'expression_statement']
        for expression in expressionNodes:
            if expression.children[0].type == 'method_invocation' and expression.children[0].child_by_field_name(
                    'name').text.decode('utf-8') in valid_assertions:
                new_ut = '\n'.join(methodBodyLines[:expression.end_point[0] + 1]) + '\n}'
                methodBodyLines[expression.start_point[0]: expression.end_point[0] + 1] = [''] * (
                            expression.end_point[0] + 1 - expression.start_point[0])
                assertions.append({
                    'assertion': expression.text.decode('utf-8'),
                    'parent_ut': methodStr,
                    'ut': new_ut,
                })
        pass
    return assertions


def get_modifier(node: Node) -> str:
    return ' '.join([n.text.decode('utf-8') for n in node.children if n.type == 'modifiers'])


def _find_package_name(root_node: Node) -> str:
    # 查找 package 定义
    package_decl_node = next(filter(lambda n: n.type == 'package_declaration', root_node.children), None)

    if package_decl_node:
        try:
            assert isinstance(package_decl_node, Node)
            assert package_decl_node.child(1).type == 'scoped_identifier'  # 防止 magic number 出错
            pkg_name = package_decl_node.child(1).text.decode('utf-8')
        except AssertionError:
            # just in case.
            logger.error(
                f'Package declaration node is not as expected. Expected: package_declaration, got: {package_decl_node.type}; Expected child type: scoped_identifier, got: {package_decl_node.child(1).type}.')
            pkg_name = ''
        pass
    else:
        pkg_name = ''

    return pkg_name


def _find_class_declaration_node(root_node: Node, target_class_name: [str | None]) -> [None | Node]:
    # 查找目标类定义节点
    class_decl_node = None
    class_decl_nodes = [n for n in root_node.children if n.type == 'class_declaration']
    if target_class_name:
        # 如果有目标类的名字（根据文件名获得），那么根据名字查找，应该只有一个，用 next 获取
        class_decl_node = next(
            filter(lambda n: n.child_by_field_name('name').text.decode('utf-8') == target_class_name, class_decl_nodes),
            None)
    elif len(class_decl_nodes) >= 1:
        # 没有设定目标名字，默认取第一个 public 且非 abstract 的 class node。Interface 是另外的节点定义类型，在过滤 class_declaration 时已经过滤掉了。
        for node in class_decl_nodes:
            modifiers = next(filter(lambda n: n.type == 'modifiers', node.children), None)
            if modifiers:
                modifier_text = modifiers.text.decode('utf-8')
                if 'public' in modifier_text and 'abstract' not in modifier_text:
                    class_decl_node = node
                    break

    # 判断是否找到
    if not class_decl_node:
        logger.warning(f'Class declaration not found. Please refer to the debug information for debugging.')
        logger.debug(root_node.text.decode('utf-8'))

    return class_decl_node


def _find_imports(root_node: Node) -> list[str]:
    import_nodes = [n for n in root_node.children if n.type == 'import_declaration']
    return [n.text.decode('utf-8') for n in import_nodes] if import_nodes else []


def method_decl_node_to_method_obj(node: Node, pkg_name: str, class_name: str, ) -> Method:
    """
    Converts a method declaration node to a Method object.

    Args:
        node (Node): The method declaration node.
        pkg_name (str): The package name of the class containing the method.
        class_name (str): The name of the class containing the method.

    Returns:
        Method: An object representing the method.
    """
    docstring = node.prev_sibling.text.decode('utf-8') if node.prev_sibling.type == 'block_comment' else ''
    modifier = get_modifier(node)
    method_text = node.text.decode('utf-8')
    parameter_nodes = [n for n in node.child_by_field_name('parameters').children if n.type not in ['(', ')', ',']]
    parameters = []
    for p in parameter_nodes:
        if p.child_by_field_name('name') and p.child_by_field_name('type'):
            parameters.append(
                Field(
                    name=p.child_by_field_name('name').text.decode('utf-8'),
                    type=p.child_by_field_name('type').text.decode('utf-8'),
                    modifier='',
                    value='',
                    docstring=''
                ))
        else:
            parameters.append(
                Field(
                    name=p.text.decode('utf-8'),
                    type='',
                    modifier='',
                    value='',
                    docstring='',
                    text=p.text.decode('utf-8')
                )
            )

    return_type = node.child_by_field_name('type').text.decode('utf-8')

    return Method(
        name=node.child_by_field_name('name').text.decode('utf-8'),
        modifier=modifier,
        text=method_text,
        return_type=return_type,
        params=parameters,
        class_sig=pkg_name + '.' + class_name,
        docstring=docstring
    )


def field_decl_node_to_field_obj(node: Node) -> [Field | None]:
    """
    Converts a field declaration node to a Field object.

    Args:
        node (Node): The field declaration node.

    Returns:
        Field | None: An object representing the field, or None if no declarator is found.
    """
    docstring = node.prev_sibling.text.decode('utf-8') if node.prev_sibling.type == 'block_comment' else ''
    modifier = get_modifier(node)
    type = node.child_by_field_name('type').text.decode('utf-8')
    declarator = node.child_by_field_name('declarator')
    if declarator:
        name = declarator.child_by_field_name('name').text.decode('utf-8')
        value_node = declarator.child_by_field_name('value')
        value = value_node.text.decode('utf-8') if value_node else ''
        return Field(
            docstring=docstring,
            name=name,
            modifier=modifier,
            type=type,
            value=value,
            text=node.text.decode('utf-8')
        )
    else:
        logger.warning(f"No declarator found for {node.text.decode('utf-8')}")
        return None


def parseClassObj(file_content: str) -> [Class | None]:
    """
    Parses the class object from the given file content.

    Args:
        file_content (str): The content of the file to parse.
        target_class_name (str | None): The name of the target class to find. If None, the first public non-abstract class is used.

    Returns:
        Class | None: An object representing the class, or None if the class declaration is not found.
    """

    tree = parser.parse(bytes(file_content, 'utf-8'))
    pkg_name = _find_package_name(tree.root_node)
    class_decl_node = _find_class_declaration_node(tree.root_node, None)
    imports = _find_imports(tree.root_node)
    if not class_decl_node:
        return None

    superclass_node = class_decl_node.child_by_field_name('superclass')
    if superclass_node:
        superclass = class_decl_node.child_by_field_name('superclass').text.decode('utf-8')
    else:
        superclass = ''

    super_interface_node = class_decl_node.child_by_field_name('interfaces')
    if super_interface_node:
        interface = class_decl_node.child_by_field_name('interfaces').text.decode('utf-8')
    else:
        interface = ''

    class_obj = Class(
        package_name=pkg_name,
        name=class_decl_node.child_by_field_name('name').text.decode('utf-8'),
        modifier=get_modifier(class_decl_node),
        text=class_decl_node.text.decode('utf-8'),
        imports=imports,
        interface=interface,
        superclass=superclass
    )

    class_body = class_decl_node.child_by_field_name('body')
    for child in class_body.children:
        if child.type == 'method_declaration':
            # 只接受块注释的 docstring
            method_obj = method_decl_node_to_method_obj(child, pkg_name, class_obj.name)
            class_obj.add_method(method_obj)
        elif child.type == 'field_declaration':
            field_obj = field_decl_node_to_field_obj(child)
            if field_obj: class_obj.add_field(field_obj)
            pass

    return class_obj
