# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybass_tta.py - is ctypes python module for
BASS_TTA - extension to the BASS audio library
that enables the playback of The True Audio streams.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_tta_module, func_type = bass.load(__file__)


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
BASS_FILEPROCS = pybass.BASS_FILEPROCS


# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_TTA = 0x10f00


# HSTREAM BASSTTADEF(BASS_TTA_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_TTA_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_TTA_StreamCreateFile', bass_tta_module))


# HSTREAM BASSTTADEF(BASS_TTA_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_TTA_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_TTA_StreamCreateFileUser', bass_tta_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_TTA_StreamCreateFile(False, b'test.tta', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
