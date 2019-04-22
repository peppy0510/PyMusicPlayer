# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybass_ofr.py - is ctypes python module for
BASS_OFR - extension to the BASS audio library
that enables the playback of OptimFROG streams.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_ofr_module, func_type = bass.load(__file__)


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
BASS_FILEPROCS = pybass.BASS_FILEPROCS


# Additional tags available from BASS_StreamGetTags
BASS_TAG_APE = 6  # APE tags


# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_OFR = 0x10600


# HSTREAM BASSOFRDEF(BASS_OFR_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_OFR_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_OFR_StreamCreateFile', bass_ofr_module))


# HSTREAM BASSOFRDEF(BASS_OFR_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_OFR_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_OFR_StreamCreateFileUser', bass_ofr_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_OFR_StreamCreateFile(False, b'test.ofr', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
