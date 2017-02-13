# -*- mode: python -*-
# encoding: utf-8

################################################################################
# MACROBOX executable builder
#-------------------------------------------------------------------------------
# author: Taehong Kim / MUTEKLAB
# email: peppy0510@hotmail.com / thkim@muteklab.com
#-------------------------------------------------------------------------------
# requires pyinstaller 2.0+ development version
# example: python "C:\Program Files (x86)\Python27\Lib
# \site-packages\pyinstaller\utils\Build.py" "macrobox.spec"
################################################################################

###############################################################################
# Project Environment
#-------------------------------------------------------------------------------
import os, sys
#-------------------------------------------------------------------------------
debug = False
#-------------------------------------------------------------------------------
# end of Project Environment
################################################################################

################################################################################
# Packaging Tool
#-------------------------------------------------------------------------------
class Struct:
    #---------------------------------------------------------------------------
    def __init__(self, **kwds):
        self.__dict__.update(kwds)
#-------------------------------------------------------------------------------
def grapdatas(home, path, depth, mode, specs=None):
    import glob; datas = list()
    paths = glob.glob(os.path.join(home, path, '*.*'))
    for this in paths:
        splpath = this.split(os.sep)
        if specs is not None and splpath[-1] not in specs:
            continue
        virpath = os.sep.join(splpath[-depth-1:])
        datas.append((virpath, this, mode))
    for data in datas: print data
    return datas
#-------------------------------------------------------------------------------
# end of Packaging Tool
################################################################################

################################################################################
# Project Environment
#-------------------------------------------------------------------------------
home = os.path.dirname(os.path.abspath(__file__))
path = Struct(packages=r'packages')
specs = ['bass.dll']
pathex = [home, path.packages]
hiddenimports = ['pybass']
output = os.path.join(r'build\pyi.win32\macrobox', r'macrobox.exe')
#-------------------------------------------------------------------------------
# end of Project Environment
################################################################################

################################################################################
# PyInstaller Packaging
#-------------------------------------------------------------------------------
a = Analysis(['macrobox.py'], pathex=pathex,
    hiddenimports=hiddenimports, hookspath=[path.packages])
a.datas += grapdatas(home, path.packages, 1, 'DATA', specs)
pyz = PYZ(a.pure)
#-------------------------------------------------------------------------------
# onedir mode
exe = EXE(pyz, a.scripts,\
    name=output, debug=debug, icon=r'packages\icon-macrobox.ico',\
    strip=None, upx=True, console=debug, exclude_binaries=1)
dist = COLLECT(exe, a.binaries, a.zipfiles, a.datas,\
    strip=None, upx=True, name='macrobox')
#-------------------------------------------------------------------------------
# onefile mode: multiprocessing meipass and homepath issue is still pending
# exe = EXE(pyz, a.scripts+[('O','','OPTION')], a.binaries, a.zipfiles, a.datas,
#     name=output, debug=debug, icon=r'packages\icon-macrobox.ico',\
#     strip=None, upx=True, console=debug)
#-------------------------------------------------------------------------------
# end of PyInstaller Packaging
################################################################################