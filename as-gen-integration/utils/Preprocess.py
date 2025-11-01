def extractTestClass(generationStr):
    generatedTestClassLines = []
    writting = False
    for line in generationStr.split('\n'):
        if line.startswith('```'):
            if not writting:
                writting = True
                continue
            else:
                break
        else:
            if writting:
                generatedTestClassLines.append(line)
    generatedTestClass = '\n'.join(generatedTestClassLines)
    return generatedTestClass


def getImportsFromFocalClass(focalClassStr):
    lines = focalClassStr.split('\n')
    newImports = []
    for line in lines:
        if line.startswith('package'):
            newImports.append(
                line.replace('package','import',1).replace(';','.*;')
            )
        elif line.startswith('import'):
            newImports.append(line.strip())
        else:
            continue
    return '\n'.join(newImports)


