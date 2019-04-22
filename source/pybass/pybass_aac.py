# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybass_aac.py - is ctypes python module for
BASS_AAC - extension to the BASS audio library that enables the playback
of Advanced Audio Coding and MPEG-4 streams (http://www.maresweb.de).
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_aac_module, func_type = bass.load(__file__)


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
DOWNLOADPROC = pybass.DOWNLOADPROC
BASS_FILEPROCS = pybass.BASS_FILEPROCS


# Additional BASS_SetConfig options
BASS_CONFIG_MP4_VIDEO = 0x10700  # play the audio from MP4 videos


# Additional tags available from BASS_StreamGetTags (for MP4 files)
BASS_TAG_MP4 = 7  # MP4/iTunes metadata


BASS_AAC_STEREO = 0x400000  # downmatrix to stereo


# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_AAC = 0x10b00  # AAC
BASS_CTYPE_STREAM_MP4 = 0x10b01  # MP4


# HSTREAM BASSAACDEF(BASS_AAC_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_AAC_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_AAC_StreamCreateFile', bass_aac_module))


# HSTREAM BASSAACDEF(BASS_AAC_StreamCreateURL)(
# const char *url, DWORD offset, DWORD flags, DOWNLOADPROC * proc, void * user);
BASS_AAC_StreamCreateURL = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p
)(('BASS_AAC_StreamCreateURL', bass_aac_module))


# HSTREAM BASSAACDEF(BASS_AAC_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_AAC_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_AAC_StreamCreateFileUser', bass_aac_module))


# HSTREAM BASSAACDEF(BASS_MP4_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_MP4_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_MP4_StreamCreateFile', bass_aac_module))


# HSTREAM BASSAACDEF(BASS_MP4_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_MP4_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_MP4_StreamCreateFileUser', bass_aac_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_AAC_StreamCreateFile(False, b'test.aac', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error%s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
