# Copyright(c) Andrew Evans 2013
# BSD license


__version__ = '0.1'
__versionTime__ = '2013-03-28'
__author__ = 'Andrew Evans <themindflows@gmail.com>'
__doc__ = '''
pybass_vst.py - is ctypes python module for
BASS_VST - An extension enabling the use of VST effect plugins with BASS.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_vst_module, func_type = bass.load(__file__)


HSTREAM = pybass.HSTREAM
BASS_FILEPROCS = pybass.BASS_FILEPROCS


BASS_VST_KEEP_CHANS = 0x00000001


BASS_VST_ChannelSetDSP = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int
)(('BASS_VST_ChannelSetDSP', bass_vst_module))


BASS_VST_ChannelRemoveDSP = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_VST_ChannelRemoveDSP', bass_vst_module))


BASS_VST_ChannelCreate = func_type(

    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong
)(('BASS_VST_ChannelCreate', bass_vst_module))


BASS_VST_ChannelFree = func_type(
    HSTREAM, ctypes.c_ulong
)(('BASS_VST_ChannelFree', bass_vst_module))


BASS_VST_GetParamCount = func_type(
    HSTREAM, ctypes.c_ulong
)(('BASS_VST_GetParamCount', bass_vst_module))


BASS_VST_GetParam = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int
)(('BASS_VST_GetParam', bass_vst_module))


BASS_VST_SetParam = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int, ctypes.c_float
)(('BASS_VST_SetParam', bass_vst_module))


class BASS_VST_PARAM_INFO(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char * 16),
        ('unit', ctypes.c_char * 16),
        ('display', ctypes.c_char * 16),
        ('defaultValue', ctypes.c_float)
    ]


BASS_VST_GetParamInfo = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(BASS_VST_PARAM_INFO)
)(('BASS_VST_GetParamInfo', bass_vst_module))


BASS_VST_GetProgramCount = func_type(
    HSTREAM, ctypes.c_ulong
)(('BASS_VST_GetProgramCount', bass_vst_module))


BASS_VST_GetProgram = func_type(
    HSTREAM, ctypes.c_ulong
)(('BASS_VST_GetProgram', bass_vst_module))


BASS_VST_SetProgram = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int
)(('BASS_VST_SetProgram', bass_vst_module))


BASS_VST_GetProgramParam = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int
)(('BASS_VST_GetProgramParam', bass_vst_module))


BASS_VST_SetProgramParam = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(ctypes.c_float)
)(('BASS_VST_SetProgramParam', bass_vst_module))


BASS_VST_GetProgramName = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int
)(('BASS_VST_GetProgramName', bass_vst_module))


BASS_VST_SetProgramName = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_int, ctypes.c_char_p
)(('BASS_VST_SetProgramName', bass_vst_module))


BASS_VST_Resume = func_type(
    HSTREAM, ctypes.c_ulong
)(('BASS_VST_Resume', bass_vst_module))


BASS_VST_SetBypass = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_bool
)(('BASS_VST_SetBypass', bass_vst_module))


BASS_VST_GetBypass = func_type(
    HSTREAM, ctypes.c_ulong
)(('BASS_VST_GetBypass', bass_vst_module))


class BASS_VST_INFO(ctypes.Structure):
    _fields_ = [
        ('channelHandle', ctypes.c_ulong),
        ('uniqueID', ctypes.c_ulong),
        ('effectName', ctypes.c_char * 80),
        ('effectVersion', ctypes.c_ulong),
        ('effectVstVersion', ctypes.c_ulong),
        ('hostVstVersion', ctypes.c_ulong),
        ('productName', ctypes.c_char * 80),
        ('vendorName', ctypes.c_char * 80),
        ('vendorVersion', ctypes.c_ulong),
        ('chansIn', ctypes.c_ulong),
        ('chansOut', ctypes.c_ulong),
        ('initialDelay', ctypes.c_ulong),
        ('hasEditor', ctypes.c_ulong),
        ('editorWidth', ctypes.c_ulong),
        ('editorHeight', ctypes.c_ulong),
        ('aeffect', ctypes.c_void_p),
        ('isInstrument', ctypes.c_ulong),
        ('dspHandle', ctypes.c_ulong)
    ]


BASS_VST_GetInfo = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.POINTER(BASS_VST_INFO)
)(('BASS_VST_GetInfo', bass_vst_module))


BASS_VST_EmbedEditor = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_void_p
)(('BASS_VST_EmbedEditor', bass_vst_module))


BASS_VST_SetScope = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_VST_SetScope', bass_vst_module))


VSTPROC = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p
)


BASS_VST_PARAM_CHANGED = 1
BASS_VST_EDITOR_RESIZED = 2
BASS_VST_AUDIO_MASTER = 3


BASS_VST_SetCallback = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.POINTER(VSTPROC)
)(('BASS_VST_SetCallback', bass_vst_module))


class BASS_VST_AUDIO_MASTER_PARAM(ctypes.Structure):
    _fields_ = [
        ('aeffect', ctypes.c_void_p),
        ('opcode', ctypes.c_long),
        ('index', ctypes.c_long),
        ('value', ctypes.c_long),
        ('ptr', ctypes.c_void_p),
        ('opt', ctypes.c_float),
        ('doDefault', ctypes.c_long),
    ]


BASS_VST_SetLanguage = func_type(
    HSTREAM, ctypes.c_char_p
)(('BASS_VST_SetLanguage', bass_vst_module))


BASS_VST_ProcessEvent = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_VST_ProcessEvent', bass_vst_module))


BASS_VST_ProcessEventRaw = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong
)(('BASS_VST_ProcessEventRaw', bass_vst_module))


BASS_VST_ERROR_NOINPUTS = 3000
BASS_VST_ERROR_NOOUTPUTS = 3001
BASS_VST_ERROR_NOREALTIME = 3002
