import json
import os.path
import subprocess

from configuration import code_base, d4j_command
from utils.StaticAnalyzer import parseMethods


class Defects4jRunner():
    def __init__(self, projectsHome: str):
        self.home = projectsHome
        self.compileCommand = d4j_command + ' compile'
        self.testCommand = d4j_command + ' test'
        self.bugID2Paths = {}
        with open(os.path.join(code_base, 'resources/test_src.json'), 'r', encoding='utf-8') as reader:
            self.bugID2Paths = json.load(reader)
        pass

    def runCompile(self, bug_id, version):
        executionPath = os.path.join(self.home, bug_id, version)
        os.chdir(executionPath)
        env = os.environ.copy()
        compile_proc = subprocess.run(
            self.compileCommand,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # extracting error message
        compile_error_lines = compile_proc.stderr.decode("utf-8").split("\n")[2:]
        compile_error_lines = [
            e
            for e in compile_error_lines
            if ("[javac] [" not in e) or ("[exec] [" not in e)
        ]
        compile_error_lines = [
            e for e in compile_error_lines if ("[javac]" in e) or ("[exec]" in e)
        ]
        compile_error_lines = [e for e in compile_error_lines if "warning:" not in e]
        compile_error_lines = [e for e in compile_error_lines if "[javac] Note:" not in e]
        compile_error_lines = [
            e for e in compile_error_lines if "compiler be upgraded." not in e
        ]
        errMsgs = []
        linesContainErr = []
        for line in compile_error_lines:
            if "error:" in line:
                tokens = line.strip().split(':')
                linesContainErr.append(int(tokens[1].strip()))
                errMsgs.append(tokens[3].strip())
        compileSucceeded = True
        if compile_proc.returncode != 0:
            compileSucceeded = False
        return compileSucceeded, errMsgs, linesContainErr

    def runTest(self, bug_id, version):
        executionPath = os.path.join(self.home, bug_id, version)
        os.chdir(executionPath)
        os.remove(os.path.join(executionPath, 'failing_tests'))
        env = os.environ.copy()
        test_proc = subprocess.run(
            self.testCommand,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        returnCode = test_proc.returncode

        if returnCode != 0:
            return False, ["Test Crashed"], []
        else:
            failingTestFile = os.path.join(executionPath, 'failing_tests')
            with open(failingTestFile, 'r', encoding='utf-8') as reader:
                failingTestMsg = reader.read()

            if failingTestMsg.strip() == '':
                return True, ["Test Passed"], []

            failingTests = []
            failingLines = []
            msgLines = failingTestMsg.split('\n')
            msglen = len(msgLines)
            for i in range(msglen):
                line = msgLines[i]
                if line.startswith('---'):
                    failingTest = line[4:].strip()
                    failingTests.append(failingTest)
                    failingLines.append(msgLines[i + 1])
                    i += 1
                    pass
            return False, failingLines, failingTests

    def refineTestClassByErrorLines(self, classStr, errLines):
        methods = parseMethods(classStr, requiredModifier='@Test')
        correctMethods = []
        refinedClassStr = classStr
        for method in methods:
            if any(lineNum in range(method['method_start_line'], method['method_end_line']) for lineNum in errLines):
                refinedClassStr = refinedClassStr.replace(method['method_text'], '')
            else:
                correctMethods.append(method)
        return refinedClassStr, correctMethods

