# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import os
import re
import sys
import glob


class RenameRule():

    @classmethod
    def replace(self, string, patterns, repl, params=''):
        flags = re.UNICODE
        if 'ignorecase' in params.split('|'):
            flags = flags | re.IGNORECASE
        for pattern in patterns.split(':'):
            string = re.sub(pattern, repl, string, count=0, flags=flags)
        return string

    @classmethod
    def regexp(self, string, patterns, repl, params=''):
        flags = re.UNICODE
        if 'ignorecase' in params.split('|'):
            flags = flags | re.IGNORECASE
        for pattern in patterns.split(':'):
            string = re.sub(pattern, repl, string, count=0, flags=flags)
        return string

    @classmethod
    def case(self, string, patterns, repl, params=''):
        # print patterns, repl
        # for pattern in patterns:
        # 	print re.findall(string, pattern)
        # print params, patterns
        flags = re.UNICODE
        if 'ignorecase' in params.split('|'):
            flags = flags | re.IGNORECASE
        for pattern in patterns.split(':'):
            offset = 0
            for i in range(255):
                m = re.search(pattern, string[offset:], flags=flags)
                if m is None:
                    break
                a, b = m.span()
                a, b = (a + offset, b + offset)
                replaced = string[a:b].upper()
                string = u''.join([string[:offset], string[offset:a], replaced, string[b:]])
                offset = b
        # if 'lower' in params.split('|'):
        # 	string = string.lower()
        # if 'upper' in params.split('|'):
        # 	string = string.upper()
        # if 'capitalize' in params.split('|'):
        # 	string = string.title()
        return string


def loadscript(path):
    f = open(path, 'rb')
    return f.read()


def rename(path, script):
    FILENAME = os.path.basename(path)
    try:
        exec(script)
    except:
        'ERROR'
    return FILENAME
    filename = os.path.basename(path)
    keywords = r'regexp|replace|case'
    keywords = r'[\t|\s]{0,}(%s){1}' % (keywords)
    parameters = r'(\([\w\d\_\|\,]{0,}\)){0,}'
    linepattern = r'^%s%s\:(.*){1}\:(.*){1}\:' % (keywords, parameters)
    linepattern = re.compile(linepattern)
    for line in script.split(os.linesep):
        line = line.strip(os.linesep)
        m = re.match(linepattern, line)
        # print line, 'xxxxxx', m
        if m is None:
            continue
        rule = m.groups()
        if rule[1] is None:
            params = ''
        else:
            params = rule[1].strip('(').strip(')').lower()
        command = 'filename = RenameRule.%s(filename, rule[2], rule[3], params)'
        exec(command % (rule[0].lower()))
    return filename

if __name__ == "__main__":
    filepath = u'D:\DOWNLOAD\+FINISHED\(+PENDING+)\AAAA'
    filepaths = glob.glob(os.path.join(filepath, u'*'))
    # filepaths = [os.path.basename(v) for v in filepaths][:5]
    filepaths = [os.path.splitext(os.path.basename(v))[0] for v in filepaths][:5]
    script = loadscript('renamer.txt')
    for filepath in filepaths:
        print(rename(filepath, script))


# filename = u'01-james_priestley_and_marco_antonio-speed_(original_mix)-marco italive 2013 0daymusic.org'
# artist = u'James Priestley & Marco Antonio'
# title = u'Speed (Original Mix)'
# album = u'http://www.0dayvinyls.org'
    # keyword = 'replace'
    # if line.strip().startswith(keyword):
        # line = line[len(keyword):].strip()
        # line = line.split('>')

        # pattern = r'([\d]+)-([\w]+)'
        # repl = r'\1 - \2'
        # string = filename
        # string = re.sub(pattern, repl, line, count=0, flags=re.UNICODE)
        # print line
        # line = line.strip(os.linesep)
        # m = re.match(r'^[\t|\s]{0,}(replace:)(.*)>(.*)', line)
        # print m
        # if m != None:
        # 	print 'xxxxxxxxxxxxx'
        # 	print m.groups()

        # patterns, repl = line.split(u'>')
        # print string
        # print mreplace(filename, patterns, repl)
        # continue
    # print line


# if wordbase is False:
# 	if caseignore is False:
# 		for src in srclist:
# 			regexp = re.compile(re.escape(src))
# 			string = regexp.sub(dst, string)
# 	elif caseignore is True:
# 		for src in srclist:
# 			regexp = re.compile(re.escape(src), re.IGNORECASE)
# 			string = regexp.sub(dst, string)

# << include >>

# << namespace: alias name >>
# << replace: case sensitive >>
# script

# vs|vs >> Vs
# filename = u'01-james_priestley_and_marco_antonio-speed_(original_mix)-italive 2013 0daymusic.org 하하'
# artist = u'James Priestley & Marco Antonio'
# title = u'Speed (Original Mix)'
# album = u'http://www.0dayvinyls.org'

# # src = r'([\d]+)-(.*)'
# # dst = r'$1 -------- $1'
# # string = filename

# # regexp = re.compile(re.escape(src))
# # string = regexp.sub(dst, string)

# pattern = r'([\d]+)-([\w]+)'
# repl = r'\1 - \2'
# string = filename
# string = re.sub(pattern, repl, string, count=0, flags=re.UNICODE)
# re.purge()

# print string

# a = """

# def aaa():
# 	print 'aaa'

# aaa()
# """
# exec(a)
