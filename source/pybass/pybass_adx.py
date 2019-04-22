# Copyright(c) Andrew Evans 2013
# BSD license


__version__ = '0.1'
__versionTime__ = '2013-03-28'
__author__ = 'Andrew Evans <themindflows@gmail.com>'
__doc__ = '''
pybass_adx.py - is ctypes python module for
BASS_ADX - extension to the BASS audio library that enables
the playback of ADX encoded files.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_adx_module, func_type = bass.load(__file__)


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
DOWNLOADPROC = pybass.DOWNLOADPROC
BASS_FILEPROCS = pybass.BASS_FILEPROCS


class TADX_LoopStruct(ctypes.Structure):
    _fields_ = [
        ('LoopEnabled', ctypes.c_bool),
        ('SampleStart', QWORD),
        ('ByteStart', QWORD),
        ('ByteEnd', QWORD)
    ]


# Additional BASS_SetConfig options
BASS_TAG_ADX_LOOP = 0x12000  # play the audio from MP4 videos


BASS_CTYPE_STREAM_ADX = 0x1F000


# HSTREAM BASSADXDEF(BASS_ADX_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_ADX_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_ADX_StreamCreateFile', bass_adx_module))


# HSTREAM BASSADXDEF(BASS_ADX_StreamCreateURL)(
# const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user);
BASS_ADX_StreamCreateURL = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p
)(('BASS_ADX_StreamCreateURL', bass_adx_module))


# HSTREAM BASSADXDEF(BASS_ADX_StreamCreateFileUser)(
# DWORD system, DWORD flags, BASS_FILEPROCS *procs, void *user);
BASS_ADX_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_ADX_StreamCreateFileUser', bass_adx_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error', pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_ADX_StreamCreateFile(False, 'test.adx', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error', pybass.get_error_description(pybass.BASS_ErrorGetCode()))
