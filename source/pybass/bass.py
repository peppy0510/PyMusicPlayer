__version__ = '0.1'
__author__ = 'Taehong Kim'
__email__ = 'peppy0510@hotmail.com'
__license__ = 'BSD'
__doc__ = '''
bass_module, func_type = bass.load(__file__)
'''


import ctypes
import os
import platform
import sys


def load(name='bass'):
    name = os.path.splitext(os.path.basename(name))[0]
    if name.startswith('py'):
        name = name[2:]

    if hasattr(sys, '_MEIPASS'):
        assets = os.path.join(sys._MEIPASS, 'assets')
    else:
        assets = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets')
    # architecture = 'x64' if platform.machine().endswith('64') else 'x86'
    extension = ['', '.dll'] if sys.platform.startswith('win') else ['lib', '.so']
    filename = name.join(extension)
    # path = os.path.join(lib, 'dlls', architecture, filename)
    path = os.path.join(assets, 'dlls', filename)
    # print(path)

    if os.path.isfile(path):
        try:
            if sys.platform.startswith('win'):
                bass_module = ctypes.WinDLL(path)
                func_type = ctypes.WINFUNCTYPE
            else:
                bass_module = ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                func_type = ctypes.CFUNCTYPE
            return bass_module, func_type
        except Exception:
            pass
    raise FileNotFoundError('Failed to load BASS module "%s"' % (filename))


# TRIAL_MODULES = [
#     'pybass',
#     'pybass_vst',
#     'pybass_aac',
#     'pybass_ac3',
#     'pybass_adx',
#     'pybass_aix',
#     'pybass_alac',
#     'pybass_ape',
#     'pybass_mpc',
#     'pybass_ofr',
#     'pybass_sfx',
#     'pybass_spx',
#     'pybass_tta',
#     'pybass_vst',
#     'pybassasio',
#     'pybassflac',
#     'pybassmidi',
#     'pybassmix',
#     'pybasswasapi',
#     'pybasswma',
#     'pyogginfo',
#     'pytags',
# ]


# IMPORTED_MODULES = []

# from .pybass import *
# from .pybass_vst import *
# from .pybassmidi import *
# from .pybassmix import *
# from .pytags import *

# # bass_module, func_type = load('bass')
# # bass_module, func_type = load('bass_vst')
# # bass_module, func_type = load('bassmidi')
# # bass_module, func_type = load('bassmix')
# # bass_module, func_type = load('tags')

# for name in TRIAL_MODULES:

#     try:
#         try:
#             exec('from %s import *' % (name))
#         except ImportError:
#             exec('from .%s import *' % (name))
#         IMPORTED_MODULES += [name]
#     except Exception:
#         pass


if __name__ == '__main__':
    bass_module, func_type = load('bass')
