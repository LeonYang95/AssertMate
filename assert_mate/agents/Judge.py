import os.path
import sys

sys.path.extend(['.', '..'])
import yaml

from agents.base.llm import LLM
from dotmap import DotMap


class Judge():
    def __init__(self, model: LLM):
        self.model = model
        self.system_prompt = "You are an expert in software testing, with 10 years of experience. You are a leader of a software testing team. Should your teammates have any question, you will listen to their stories and give a final judgement."
        self._history = []
        pass

    @property
    def history(self):
        return self._history

    def _verdict_instruction(self, focal_method: str, test_prefix: str, responses: dict) -> str:
        instruction = f'There are {len(responses)} teammates in your team, and they are writing expected values in assertions.'
        instruction += f'The method they are going to test is:\n```java\n{focal_method}\n```\n'
        instruction += f'And they are asked to determine the proper value in the `<expected_value>` part in the test case: \n```java\n{test_prefix}\n```\n'
        instruction += f'Here are their responses:\n'
        for member, response in responses.items():
            instruction += f'Team Member {member}: {response}\n'
        instruction += 'Please read the codes and the responses, and determine whether they have the same answer regarding the what to fill in the `<expected_value>` part in the assertion. If their answer were different, please answer **NO**. Otherwise, please answer **YES**.'
        return instruction

    def _interpretation_instruction(self,processed_assertion:str) -> str:
        instruction = ('Please do the following:\n'
                       '- If your previous answer is **NO**, please give them some comment regarding their answers according to your understanding. Please do not repeat their answers.\n'
                       f'- If your previous answer is **YES**, then fill in the `<expected_value>` part of `{processed_assertion}`. Please just return the complete **assertion statement**.\n')
        return instruction

    def _final_verdict_instruction(self, focal_method, test_prefix, responses: dict) -> str:
        instruction = f'There are {len(responses)} teammates in your team, and they are writing expected values in assertions.'
        instruction += f'The method they are going to test is:\n```java\n{focal_method}\n```\n'
        instruction += f'And they are asked to determine the proper value in the `<expected_value>` part in the test case: \n```java\n{test_prefix}\n```\n'
        instruction += f'Here are their responses:\n'
        for member, response in responses.items():
            instruction += f'Team Member {member}: {response}\n'
        instruction += 'Please read the codes and their responses, and determine what to fill in the `<expected_value>` part in the assertion statement. Please directly response the **assertion statement** wrapped in code block without explanation.'
        return instruction

    def _group_final_verdict_messages(self, focal_method: str, test_prefix: str, responses: dict) -> list:
        instruction = self._final_verdict_instruction(focal_method, test_prefix, responses)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': instruction
        })
        return messages

    def _group_verdict_messages(self, focal_method: str, test_prefix: str, responses: dict) -> list:
        instruction = self._verdict_instruction(focal_method, test_prefix, responses)
        messages = []
        messages.append({
            'role': 'system',
            'content': self.system_prompt
        })
        messages.append({
            'role': 'user',
            'content': instruction
        })

        return messages

    def _group_interpretation_messages(self, focal_method: str, test_prefix: str, responses: dict,
                                       first_judge: str,
                                       processed_assertion:str) -> list:
        messages = self._group_verdict_messages(focal_method, test_prefix, responses)
        messages.append({
            'role': 'assistant',
            'content': first_judge
        })
        messages.append({
            'role': 'user',
            'content': self._interpretation_instruction(processed_assertion)
        })
        return messages

    def make_decision(self, focal_method, test_prefix, responses):
        messages = self._group_verdict_messages(focal_method, test_prefix, responses)
        response = self.model.get_response(messages=messages)
        return response

    def explain_decision(self, focal_method, test_prefix, responses, first_decision, processed_assertion):
        messages = self._group_interpretation_messages(focal_method, test_prefix, responses, first_decision,processed_assertion)
        response = self.model.get_response(messages=messages)
        return response

    def final_decision(self, focal_method, test_prefix, responses) -> str:
        messages = self._group_final_verdict_messages(focal_method, test_prefix, responses)
        self._history = messages
        response = self.model.get_response(messages)
        return response


if __name__ == '__main__':
    code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    with open(os.path.join(code_base, 'config/basic_config.yaml'), 'r') as reader:
        config = DotMap(yaml.load(reader, Loader=yaml.FullLoader))
    from agents.base.llm import DeepSeek

    model = DeepSeek(config)
    generator = Judge(model)
    focal_method = """
    public static String findLongestCommonSubstring(String s1, String s2) {
        int m = s1.length();
        int n = s2.length();
        int maxLength = 0;
        int endIndex = 0;

        // 创建二维数组用于存储最长公共子串的长度
        int[][] dp = new int[m + 1][n + 1];

        // 填充DP表
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                if (s1.charAt(i - 1) == s2.charAt(j - 1)) {
                    dp[i][j] = dp[i - 1][j - 1] + 1;
                    if (dp[i][j] > maxLength) {
                        maxLength = dp[i][j];
                        endIndex = i - 1;
                    }
                }
            }
        }

        // 返回最长公共子串
        return s1.substring(endIndex - maxLength + 1, endIndex + 1);
    }
    """
    test_prefix = """
    @Test
    void testFindLongestCommonSubstring() {
        LongestCommonSubstring lcs = new LongestCommonSubstring();

        assertEquals( <expected_value> , lcs.findLongestCommonSubstring("abcdef", "zabckl"));
    }
    """
    responses = ['"abc"', '"```java\nabc\n```"',
                 '"```java\nassertEquals( "abc" , lcs.findLongestCommonSubstring("abcdef", "zabckl"));\n```"']
    response = generator.make_decision(focal_method, test_prefix, responses)
    print(response)
    response = generator.explain_decision(focal_method, test_prefix, responses, response)
    print(response)
    pass
