# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybass_aix.py - is ctypes python module for
BASS_AIX - extension to the BASS audio library,
enabling the playing of AIX encoded files.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_ac3_module, func_type = bass.load(__file__)


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
DOWNLOADPROC = pybass.DOWNLOADPROC
BASS_FILEPROCS = pybass.BASS_FILEPROCS


# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_AIX = 0x1F001  # Only for ADX of all versions (with AIXP support)


# HSTREAM BASSAIXDEF(BASS_AIX_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_AIX_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_AIX_StreamCreateFile', bass_ac3_module))


# HSTREAM BASSAIXDEF(BASS_AIX_StreamCreateURL)(
# const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user);
BASS_AIX_StreamCreateURL = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p
)(('BASS_AIX_StreamCreateURL', bass_ac3_module))


# HSTREAM BASSAIXDEF(BASS_AIX_StreamCreateFileUser)(
# DWORD system, DWORD flags, BASS_FILEPROCS *procs, void *user);
BASS_AIX_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_AIX_StreamCreateFileUser', bass_ac3_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_AIX_StreamCreateFile(False, b'test.aix', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
