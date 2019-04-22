__version__ = '0.0.1'
__author__ = 'Taehong Kim'
__email__ = 'peppy0510@hotmail.com'
__license__ = 'BSD'
__doc__ = '''
bass_module, func_type = bass.load(__file__)
'''


TRIAL_MODULES = [
    'pybass',
    'pybass_vst',
    # 'pybass_aac',
    # 'pybass_ac3',
    # 'pybass_adx',
    # 'pybass_aix',
    # 'pybass_alac',
    # 'pybass_ape',
    # 'pybass_mpc',
    # 'pybass_ofr',
    # 'pybass_sfx',
    # 'pybass_spx',
    # 'pybass_tta',
    # 'pybassasio',
    # 'pybassflac',
    'pybassmidi',
    # 'pybassmix',
    # 'pybasswasapi',
    # 'pybasswma',
    # 'pyogginfo',
    'pytags',
]


IMPORTED_MODULES = []


for name in TRIAL_MODULES:
    # try:
    #     exec('from %s import *' % (name))
    # except ImportError:
    try:
        exec('from .%s import *' % (name))
    except ImportError:
        continue
    IMPORTED_MODULES += [name]

    # try:
    #     try:
    #         exec('from %s import *' % (name))
    #     except ImportError:
    #         exec('from .%s import *' % (name))
    #     IMPORTED_MODULES += [name]
    # except Exception:
    #     pass


from .pybass import *  # noqa
from .pybass_vst import *  # noqa
from .pybassmidi import *  # noqa
from .pybassmix import *  # noqa
from .pytags import *  # noqa


if __name__ == '__main__':
    print(IMPORTED_MODULES)
    # print(list(globals()))
