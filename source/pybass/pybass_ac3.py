# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybass_ac3.py - is ctypes python module for
BASS_AC3 - extension to the BASS audio library that enables the playback
of Dolby Digital AC-3 streams (http://www.maresweb.de).
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


# BASS_Set/GetConfig options
BASS_CONFIG_AC3_DYNRNG = 0x10001


# Additional BASS_AC3_StreamCreateFile/User/URL flags
BASS_AC3_DYNAMIC_RANGE = 0x800  # enable dynamic range compression


# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_AC3 = 0x11000


# HSTREAM BASSAC3DEF(BASS_AC3_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_AC3_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_AC3_StreamCreateFile', bass_ac3_module))


# HSTREAM BASSAC3DEF(BASS_AC3_StreamCreateURL)(
# const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user);
BASS_AC3_StreamCreateURL = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p
)(('BASS_AC3_StreamCreateURL', bass_ac3_module))


# HSTREAM BASSAC3DEF(BASS_AC3_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_AC3_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_AC3_StreamCreateFileUser', bass_ac3_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_AC3_StreamCreateFile(False, b'test.ac3', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
