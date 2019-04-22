# Copyright(c) Andrew Evans 2013 (themindflows@gmail.com)

import ctypes

from Tkinter import Frame
from Tkinter import Tk
from pybass import BASS_ErrorGetCode
from pybass import BASS_Init
from pybass import BASS_PluginLoad
from pybass import get_error_description
from pybass_vst import BASS_VST_ChannelCreate
from pybass_vst import BASS_VST_EmbedEditor
from pybass_vst import BASS_VST_GetInfo
from pybass_vst import BASS_VST_INFO


root = Tk()
root.title('Test :-P')
hwnd = root.winfo_id()
frame = Frame(root)


if not BASS_Init(-1, 44100, 0, 0, 0):
    print('BASS_Init error', get_error_description(BASS_ErrorGetCode()))
else:
    vst_load = BASS_PluginLoad('bass_vst.dll', 0)
    dsp = BASS_VST_ChannelCreate(44100, 1, 'C:\\Program Files\\Native Instruments\\VSTPlugins 32 bit\\FM8.dll', 0)
    info = BASS_VST_INFO()
    if BASS_VST_GetInfo(dsp, ctypes.byref(info)) and info.hasEditor:
        BASS_VST_EmbedEditor(dsp, hwnd)
    print(info.hasEditor)
    # BASS_ChannelPlay(channelHandle, False)
    # BASS_StreamFree(channelHandle)
frame.pack()
root.mainloop()
