# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import glob
import os


debug = True
upx = True
onefile = True


PYZ = PYZ  # noqa
EXE = EXE  # noqa
COLLECT = COLLECT  # noqa
Analysis = Analysis  # noqa


__default_python_path__ = 'C:\\Program Files\\Python36'
__appname__ = 'PyMusicPlayer'
__api_ms_win_crt_path__ = 'C:\\Windows\\WinSxS\\amd64_microsoft-windows-m..namespace-downlevel_31bf3856ad364e35_10.0.17763.1_none_b82ac495d943b9d7'


class Path():

    def __init__(self, **kwargs):
        for key in kwargs.keys():
            kwargs[key] = os.path.abspath(kwargs[key])
        self.__dict__.update(kwargs)


def grapdatas(home, path, depth, mode, specs=None):
    datas = []
    for p in glob.glob(os.path.join(home, path, '*.*')):
        splpath = p.split(os.sep)
        if specs is None or splpath[-1] in specs:
            virpath = os.sep.join(splpath[-depth - 1:])
            datas += [(virpath, p, mode)]
    return datas


# home = os.path.dirname(os.path.abspath(__file__))


path = Path(
    home='',
    assets=os.path.join('assets'),
    icon=os.path.join('assets', 'icon', 'icon.ico'),
    dlls=os.path.join('assets', 'dlls'),
    packages=os.path.dirname(os.path.abspath('packages')),
    output=os.path.join('build', '{}.exe'.format(__appname__)),
    winsxs=__api_ms_win_crt_path__,
    scipydll=os.path.join(__default_python_path__, 'Lib', 'site-packages', 'scipy', 'extra-dll'),
    # modpybassdll=os.path.join(__default_python_path__, 'Lib', 'site-packages', 'modpybass', 'lib', 'x64'),
)

# output = 'build\\pyi.win32\\macrobox\\macrobox.exe'
a = Analysis([os.path.join('source', 'main.pyw')],
             hookspath=[path.home, path.packages, path.scipydll],
             pathex=[path.home, path.assets, path.packages, path.dlls, path.winsxs],
             hiddenimports=['pybass', 'pybass.bass', 'mfeats', 'scipy', 'scipy.signal'])

a.datas += grapdatas(path.assets, 'icon', 2, 'DATA', ['icon.ico'])
a.datas += grapdatas(path.assets, 'fonts', 2, 'DATA', ['unifont.ttf'])
a.datas += grapdatas(path.assets, 'dlls', 2, 'DATA', [
    'LoudMax.dll', 'LoudMax64.dll', 'LoudMaxLite.dll', 'LoudMaxLite64.dll'])
a.datas += grapdatas(path.assets, 'dlls', 2, 'DATA', [
    'bass.dll', 'bass_fx.dll', 'bass_vst.dll', 'bassmidi.dll', 'bassmix.dll', 'tags.dll'])
# a.datas += grapdatas(path.packages, 1, 'DATA', ['bass.dll'])
# a.datas += grapdatas(path.packages, 1, 'DATA', ['LoudMax.dll', 'LoudMax64.dll'])
# a.datas += grapdatas(path.scipydll, 1, 'DATA')

pyz = PYZ(a.pure)


print('-' * 100)
for v in a.datas:
    print(v)
print('-' * 100)


if onefile:
    exe = EXE(pyz, a.scripts + [('O', '', 'OPTION')],
              a.binaries, a.zipfiles, a.datas,
              uac_admin=True, uac_uiaccess=True,
              icon=path.icon, name=path.output,
              upx=upx, strip=None, debug=debug, console=debug)
    # runtime_tmpdir='%HOMEPATH%\\AppData\\Local\\Temp\\' + name
else:
    exe = EXE(pyz, a.scripts, name=path.output, icon=path.icon,
              uac_admin=True, uac_uiaccess=True, upx=upx, strip=None,
              debug=debug, console=debug, exclude_binaries=1)
    dist = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
                   upx=upx, strip=None, name=__appname__)
