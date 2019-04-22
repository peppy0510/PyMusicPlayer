# Copyright(c) Andrew Evans 2013
# BSD license


__version__ = '0.1'
__versionTime__ = '2013-03-28'
__author__ = 'Andrew Evans <themindflows@gmail.com>'
__doc__ = '''
pybass_alac.py - is ctypes python module for
BASS_ALAC - extension to the BASS audio library that enables
the playback of ALAC (Apple Lossless) encoded files.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_alac_module, func_type = bass.load(__file__)


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
DOWNLOADPROC = pybass.DOWNLOADPROC
BASS_FILEPROCS = pybass.BASS_FILEPROCS


# Additional BASS_SetConfig options
BASS_TAG_MP4 = 7


BASS_CTYPE_STREAM_ALAC = 0x10e00


# HSTREAM BASSALACDEF(BASS_ALAC_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_ALAC_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_ALAC_StreamCreateFile', bass_alac_module))


# HSTREAM BASSALACDEF(BASS_ALAC_StreamCreateURL)(
# const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user);
BASS_ALAC_StreamCreateURL = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p
)(('BASS_ALAC_StreamCreateURL', bass_alac_module))


# HSTREAM BASSALACDEF(BASS_ALAC_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_ALAC_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_ALAC_StreamCreateFileUser', bass_alac_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error', pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_ALAC_StreamCreateFile(False, 'test.alac', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error', pybass.get_error_description(pybass.BASS_ErrorGetCode()))
