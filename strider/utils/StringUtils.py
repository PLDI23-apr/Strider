import re, random
import string

def removeComment(content):
    pattern1 = "/\*.*?\*/"
    pattern2 = "//.*?\n"
    content = re.sub(pattern1, "\n", content)
    content = re.sub(pattern2, "\n", content)
    return content

def genRandomString(length=4):
    retList = random.sample(string.digits, length)
    return ''.join(retList)

def subString(pattern, repl, dstString):
    return re.sub(pattern, repl, dstString)