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


def grapdatas(path, depth, mode, specs=None):
    import glob
    datas = list()
    paths = glob.glob(os.path.join(path, '*.*'))
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


path = Struct(
    root=os.path.dirname(os.path.abspath('')),
    packages=os.path.dirname(os.path.abspath('packages')),
    scipydll='C:\\Program Files\\Python36\\Lib\\site-packages\\scipy\\extra-dll')

output = 'build\\pyi.win32\\macrobox\\macrobox.exe'
a = Analysis(['macrobox.pyw'],
             hookspath=[path.root, path.packages, path.scipydll],
             pathex=[path.root, path.packages],
             hiddenimports=['pybass', 'mfeats', 'scipy', 'scipy.signal'])
a.datas += grapdatas(path.packages, 1, 'DATA', ['bass.dll'])
a.datas += grapdatas(path.scipydll, 1, 'DATA')
pyz = PYZ(a.pure)

# onedir mode
exe = EXE(pyz, a.scripts,
          name=output, debug=debug, icon='packages\\icon-macrobox.ico',
          strip=None, upx=True, console=debug, exclude_binaries=1)
dist = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
               strip=None, upx=True, name='macrobox')
# onefile mode: multiprocessing meipass and homepath issue is still pending
# exe = EXE(pyz, a.scripts+[('O','','OPTION')], a.binaries, a.zipfiles, a.datas,
#     name=output, debug=debug, icon=r'packages\icon-macrobox.ico',\
#     strip=None, upx=True, console=debug)
