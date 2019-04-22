# Copyright(c) Andrew Evans 2013
# BSD license


__version__ = '0.1'
__versionTime__ = '2013-03-29'
__author__ = 'Andrew Evans <themindflows@gmail.com>'
__doc__ = '''
pybass_sfx.py - is ctypes python module for
BASS_SFX - An extension allowing the use of Sonique, Winamp,
Windows Media Player, and BassBox visual plugins with BASS.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bass_vst_module, func_type = bass.load(__file__)


# ~ from ctypes.wintypes import HINSTANCE
# ~ from ctypes.wintypes import HWND
# ~ from ctypes.wintypes import LPCWSTR
# ~ from ctypes.wintypes import HDC


HSTREAM = pybass.HSTREAM
BASS_FILEPROCS = pybass.BASS_FILEPROCS
HSFX = ctypes.c_long


# visualization plugin types
BASS_SFX_SONIQUE = 0
BASS_SFX_WINAMP = 1
BASS_SFX_WMP = 2
BASS_SFX_BBP = 3


# PluginCreate Flags
BASS_SFX_SONIQUE_OPENGL = 1  # render sonique plugins using OpenGL
BASS_SFX_SONIQUE_OPENGL_DOUBLEBUFFER = 2  # use OpenGL double buffering


# Error codes returned by BASS_SFX_ErrorGetCode
BASS_SFX_OK = 0  # all is OK
BASS_SFX_ERROR_MEM = 1  # memory error
BASS_SFX_ERROR_FILEOPEN = 2  # can't open the file
BASS_SFX_ERROR_HANDLE = 3  # invalid handle
BASS_SFX_ERROR_ALREADY = 4  # already initialized
BASS_SFX_ERROR_FORMAT = 5  # unsupported plugin format
BASS_SFX_ERROR_INIT = 6  # BASS_SFX_Init has not been successfully called
BASS_SFX_ERROR_GUID = 7  # can't open WMP plugin using specified GUID
BASS_SFX_ERROR_UNKNOWN = -1  # some other mystery problem


# LPCWSTR = c_long_p = ctypes.POINTER(c_long)


# Windows Media Player Specific
class BASS_SFX_PLUGININFO(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char_p),
        ('clsid', ctypes.c_char_p),
    ]


class BASS_SFX_PLUGINFOW(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_wchar_p),
        ('clsid', ctypes.c_wchar_p),
    ]


# BOOL SFXDEF(BASS_SFX_WMP_GetPlugin)(int index, BASS_SFX_PLUGININFO* info);
BASS_SFX_WMP_GetPlugin = func_type(
    HSTREAM, ctypes.c_int, ctypes.POINTER(BASS_SFX_PLUGININFO)
)(('BASS_SFX_WMP_GetPlugin', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_WMP_GetPluginW)(int index, BASS_SFX_PLUGININFOW* info);
BASS_SFX_WMP_GetPluginW = func_type(
    HSTREAM, ctypes.c_int, ctypes.POINTER(BASS_SFX_PLUGINFOW)
)(('BASS_SFX_WMP_GetPluginW', bass_vst_module))


# DWORD SFXDEF(BASS_SFX_GetVersion)();
BASS_SFX_GetVersion = func_type(
    HSTREAM
)(('BASS_SFX_GetVersion', bass_vst_module))


# DWORD SFXDEF(BASS_SFX_ErrorGetCode)();
BASS_SFX_ErrorGetCode = func_type(
    HSTREAM
)(('BASS_SFX_ErrorGetCode', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_Init)(HINSTANCE hInstance, HWND hWnd);
BASS_SFX_Init = func_type(
    HSTREAM, ctypes.c_void_p, ctypes.c_void_p
)(('BASS_SFX_Init', bass_vst_module))


# DWORD SFXDEF(BASS_SFX_PluginFlags)(HSFX handle, DWORD flags, DWORD mask);
BASS_SFX_PluginFlags = func_type(
    HSTREAM, HSFX, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_SFX_PluginFlags', bass_vst_module))


# HSFX SFXDEF(BASS_SFX_PluginCreate)(char* strPath, HWND hPluginWnd, int nWidth, int nHeight, DWORD flags);
BASS_SFX_PluginCreate = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
)(('BASS_SFX_PluginCreate', bass_vst_module))


# HSFX SFXDEF(BASS_SFX_PluginCreateW)(LPCWSTR strPath, HWND hPluginWnd, int nWidth, int nHeight, DWORD flags);
BASS_SFX_PluginCreateW = func_type(
    HSTREAM, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_ulong
)(('BASS_SFX_PluginCreate', bass_vst_module))


# int SFXDEF(BASS_SFX_PluginGetType)(HSFX handle);
BASS_SFX_PluginGetType = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginGetType', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginSetStream)(HSFX handle, HSTREAM hStream);
BASS_SFX_PluginSetStream = func_type(
    HSTREAM, HSFX, HSTREAM
)(('BASS_SFX_PluginSetStream', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginStart)(HSFX handle);
BASS_SFX_PluginStart = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginStart', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginStop)(HSFX handle);
BASS_SFX_PluginStop = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginStop', bass_vst_module))


# char* SFXDEF(BASS_SFX_PluginGetName)(HSFX handle);
BASS_SFX_PluginGetName = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginGetName', bass_vst_module))


# char* SFXDEF(BASS_SFX_PluginGetNameW)(HSFX handle);
BASS_SFX_PluginGetNameW = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginGetNameW', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginConfig)(HSFX handle);
BASS_SFX_PluginConfig = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginConfig', bass_vst_module))


# int SFXDEF(BASS_SFX_PluginModuleGetCount)(HSFX handle);
BASS_SFX_PluginModuleGetCount = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginModuleGetCount', bass_vst_module))


# char* SFXDEF(BASS_SFX_PluginModuleGetName)(HSFX handle, int module);
BASS_SFX_PluginModuleGetName = func_type(
    HSTREAM, HSFX, ctypes.c_int
)(('BASS_SFX_PluginModuleGetName', bass_vst_module))


# LPCWSTR SFXDEF(BASS_SFX_PluginModuleGetNameW)(HSFX handle, int module);
BASS_SFX_PluginModuleGetNameW = func_type(
    HSTREAM, HSFX, ctypes.c_int
)(('BASS_SFX_PluginModuleGetNameW', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginModuleSetActive)(HSFX handle, int module);
BASS_SFX_PluginModuleSetActive = func_type(
    HSTREAM, HSFX, ctypes.c_int
)(('BASS_SFX_PluginModuleSetActive', bass_vst_module))


# int SFXDEF(BASS_SFX_PluginModuleGetActive)(HSFX handle);
BASS_SFX_PluginModuleGetActive = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginModuleGetActive', bass_vst_module))


# HBITMAP SFXDEF(BASS_SFX_PluginRender)(HSFX handle, HSTREAM hStream, HDC hDC); //only sonique, bassbox, or WMP
BASS_SFX_PluginRender = func_type(
    HSTREAM, HSFX, HSTREAM, ctypes.c_void_p
)(('BASS_SFX_PluginRender', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginClicked)(HSFX handle, int x, int y);
BASS_SFX_PluginClicked = func_type(
    HSTREAM, HSFX, ctypes.c_int, ctypes.c_int
)(('BASS_SFX_PluginClicked', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginResize)(HSFX handle, int nWidth, int nHeight);
BASS_SFX_PluginResize = func_type(
    HSTREAM, HSFX, ctypes.c_int, ctypes.c_int
)(('BASS_SFX_PluginResize', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginResizeMove)(HSFX handle, int nLeft, int nTop, int nWidth, int nHeight);
BASS_SFX_PluginResizeMove = func_type(
    HSTREAM, HSFX, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
)(('BASS_SFX_PluginResizeMove', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_PluginFree)(HSFX handle);
BASS_SFX_PluginFree = func_type(
    HSTREAM, HSFX
)(('BASS_SFX_PluginFree', bass_vst_module))


# BOOL SFXDEF(BASS_SFX_Free)();
BASS_SFX_Free = func_type(
    HSTREAM
)(('BASS_SFX_Free', bass_vst_module))
