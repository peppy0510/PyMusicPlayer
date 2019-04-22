# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybass_mpc.py - is ctypes python module for
BASS_MPC - extension to the BASS audio library
that enables the playback of Musepack streams.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_mpc_module, func_type = bass.load(__file__)


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
DOWNLOADPROC = pybass.DOWNLOADPROC
BASS_FILEPROCS = pybass.BASS_FILEPROCS


# Additional tags available from BASS_StreamGetTags
BASS_TAG_APE = 6  # APE tags


# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_MPC = 0x10a00


# HSTREAM BASSMPCDEF(BASS_MPC_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_MPC_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong
)(('BASS_MPC_StreamCreateFile', bass_mpc_module))


# HSTREAM BASSMPCDEF(BASS_MPC_StreamCreateURL)(
# const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user);
BASS_MPC_StreamCreateURL = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p
)(('BASS_MPC_StreamCreateURL', bass_mpc_module))


# HSTREAM BASSMPCDEF(BASS_MPC_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *proc, void *user);
BASS_MPC_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p
)(('BASS_MPC_StreamCreateFileUser', bass_mpc_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        handle = BASS_MPC_StreamCreateFile(False, b'test.mpc', 0, 0, 0)
        pybass.play_handle(handle)
        if not pybass.BASS_Free():
            print('BASS_Free error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
