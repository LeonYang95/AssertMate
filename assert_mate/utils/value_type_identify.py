import re

def is_number(s):
    pattern = r'^-?\d+(\.\d+)?$'
    return re.match(pattern, s) is not None
if __name__ == '__main__':

    # 示例
    print(is_number("123"))      # 输出: True
    print(is_number("-123.45"))  # 输出: True
    print(is_number("12a3"))     # 输出: False