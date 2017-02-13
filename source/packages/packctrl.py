# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com

import os
import sys
import ctypes
# import platform


def findPath(module_name, paths):
    for path in paths:
        trialpath = ''
        try:
            trialpath = os.path.join(sys._MEIPASS, path, module_name)
        except:
            trialpath = os.path.join(path, module_name)
        if os.path.exists(trialpath) is True:
            return trialpath
    return None


def trialPaths(module_name, paths):
    trialpaths = list()
    for path in paths:
        try:
            trialpaths.append(os.path.join(sys._MEIPASS, path, module_name))
        except:
            pass
        trialpaths.append(os.path.join(path, module_name))
    return trialpaths


def tryLoadDLL(module_name, paths):
    trialpaths = trialPaths(module_name, paths)
    module = None
    func_type = None
    for path in trialpaths:
        try:
            if sys.platform.startswith('win'):
                module = ctypes.WinDLL(path)
                func_type = ctypes.WINFUNCTYPE
            else:
                module = ctypes.CDLL(path)
                func_type = ctypes.CFUNCTYPE
        except:
            pass
        if module is not None and func_type is not None:
            return module, func_type


def get_libraryName(path):
    name = os.path.splitext(os.path.split(path)[-1])[0]
    return name.strip('py')


def get_libraryFileName(path):
    name = get_libraryName(path)
    if sys.platform.startswith('win'):
        return '%s.dll' % (name)
    elif sys.platform.startswith('darwin'):
        return 'lib%s.dylib' % (name)
    return 'lib%s.so' % (name)


def get_libraryLoadCMD(path):
    trialPaths = ['', 'packages']
    libraryName = get_libraryName(path)
    libraryFileName = get_libraryFileName(path)
    command = '%s_module, func_type = packctrl.tryLoadDLL("%s", %s)'
    # print('-' * 100)
    # print(command % (libraryName, libraryFileName, trialPaths))
    return command % (libraryName, libraryFileName, trialPaths)
