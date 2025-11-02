from loguru import logger


def readGenerationFile(file):
    inputs = []
    with open(file, 'r', encoding='utf-8') as reader:
        for line in reader.readlines():
            inputs.append(line.strip())
    return inputs


def writeTestClass(file, testClassStr):
    try:
        with open(file, 'w', encoding='utf-8') as writer:
            writer.write(testClassStr)
            return True
    except Exception as e:
        logger.error(f'Failed to write to {file} due to {str(e)}.')
        return False
