# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import os
import sys


debug = False


PYZ = PYZ  # noqa
EXE = EXE  # noqa
COLLECT = COLLECT  # noqa
Analysis = Analysis  # noqa


class Struct:

    def __init__(self, **kwds):
        self.__dict__.update(kwds)


def grapdatas(home, path, depth, mode, specs=None):
    import glob
    datas = list()
    paths = glob.glob(os.path.join(home, path, '*.*'))
    for this in paths:
        splpath = this.split(os.sep)
        if specs is not None and splpath[-1] not in specs:
            continue
        virpath = os.sep.join(splpath[-depth - 1:])
        datas.append((virpath, this, mode))
    for data in datas:
        print(data)
    return datas


# home = os.path.dirname(os.path.abspath(__file__))


home = os.path.dirname(os.path.abspath(''))
path = Struct(packages='packages')
specs = ['bass.dll']
pathex = [home, path.packages]
hiddenimports = ['pybass']
output = 'build\\pyi.win32\\mfeats\\mfeats.exe'

a = Analysis(['mfeats.py'], pathex=pathex, hiddenimports=hiddenimports, hookspath=[path.packages])
a.datas += grapdatas(home, path.packages, 1, 'DATA', specs)
pyz = PYZ(a.pure)

# onedir mode
exe = EXE(pyz, a.scripts, name=output, debug=debug,
          icon='packages\\icon-mfeats.ico',
          strip=None, upx=True, console=debug, exclude_binaries=1)
dist = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=None, upx=True, name='mfeats')

# onefile mode: multiprocessing meipass and homepath issue is still pending
# exe = EXE(pyz, a.scripts+[('O','','OPTION')], a.binaries, a.zipfiles, a.datas,
#     name=output, debug=debug, strip=None, upx=True, console=debug)
