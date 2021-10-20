# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import gc
import mfeats
# import modpybass as pybass
import numpy
import os
import sys
import threading
import time
import wx

from macroboxlib import GetPreference
from macroboxlib import ListBoxColumn
from macroboxlib import MakeMusicFileItem
from macroboxlib import SUPPORTED_AUDIO_TYPE
from macroboxlib import SetPreference
# from pybass import bass as pybass
import pybass
# import pybass
# from packages import pybass
from utilities import Struct
# from macroboxlib import *


class PlayBoxDnD(wx.FileDropTarget):

    def __init__(self, parent):
        wx.FileDropTarget.__init__(self)
        self.parent = parent

    def OnDropFiles(self, x, y, inpaths):
        path = inpaths[0]
        file_type = os.path.splitext(path)[1][1:]
        if file_type not in SUPPORTED_AUDIO_TYPE:
            return
        mfeats.create_mfeats_table()
        self.parent.cue.path = path
        self.parent.OnPlay()
        return False

    def __del__(self):
        pass


class AudioControl(threading.Thread):

    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.parent = parent
        self.loop = True
        self.hStream = 0
        self.interval = 0.005
        self.fadein = Struct(cnt=0.0, time=0.0)
        self.fadeout = Struct(cnt=0.0, time=0.0)
        self.path = self.parent.cue.path
        self.pending = False
        self.resume = None
        # self._Thread__exc_clear()
        self.start()

    def run(self):
        while self.loop:
            self.LoopMainEvent()
            self.AutoFadeInOutTime()
            self.LoopFadeInEvent()
            self.LoopFadeOutEvent()

    def AutoFadeInOutTime(self):
        if self.parent.IsHighlightOn()\
                and self.parent.IsHighlightSkipOn() is False:
            self.fadein.time = 0.15
            self.fadeout.time = 1.00
        else:
            self.fadein.time = 0.1
            self.fadeout.time = 0.1

    def LoopMainEvent(self):
        time.sleep(self.interval)
        if hasattr(self.parent, 'cue') is False:
            return
        if self.parent.cue.path is None:
            return
        if self.path != self.parent.cue.path or self.resume is not None:
            self.pending = True
            self.InitAudio()

    def LoopFadeInEvent(self):
        # if self.parent.IsHighlightOn() is False: return
        if self.fadein.cnt == 0.0:
            return
        self.fadein.cnt -= self.interval
        if self.fadein.cnt < 0.0:
            self.fadein.cnt = 0.0
        ratio = 1.0 - self.fadein.cnt / self.fadein.time
        target_volume = self.parent.GetVolume()
        if self.parent.IsAutoGainOn():
            target_volume = target_volume\
                * self.parent.cue.autogain * self.parent.cue.agc_headroom
        audio.set_volume(self.hStream, target_volume * ratio)

    def StartFadeOut(self):
        if self.fadeout.cnt > 0.0:
            return
        self.fadeout.cnt = self.fadeout.time

    def LoopFadeOutEvent(self):
        # if self.parent.IsHighlightOn() is False: return
        if self.fadein.cnt > 0.0:
            self.fadeout.cnt = 0.0
            return
        if self.fadeout.cnt == 0.0:
            return
        self.fadeout.cnt -= self.interval
        if self.fadeout.cnt < 0.0:
            self.fadeout.cnt = 0.0
        ratio = self.fadeout.cnt / self.fadeout.time
        target_volume = self.parent.GetVolume()
        if self.parent.IsAutoGainOn():
            target_volume = target_volume * self.parent.cue.autogain
        audio.set_volume(self.hStream, target_volume * ratio)

    def InitAudio(self):
        ######
        # import ctypes
        # from packages.pybassex import pybassex
        # ex = pybassex()
        # path = 'C:\\Users\\tkmix\\Desktop\\WORK\\macrobox-player\\source\\packages\\bass_vst.dll'
        # bass_module = ctypes.WinDLL(path)
        # func_type = ctypes.WINFUNCTYPE
        # QWORD = ctypes.c_int64
        # HSTREAM = ctypes.c_ulong
        # BASS_VST_ChannelSetDSP = func_type(
        #     ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_int64, ctypes.c_ulong)(('BASS_VST_ChannelSetDSP', bass_module))
        # BASS_VST_GetParam = func_type(
        #     ctypes.c_bool, HSTREAM, ctypes.c_int64)(('BASS_VST_GetParam', bass_module))
        # # BASS_VST_SetParam = func_type(
        # #     ctypes.c_bool, HSTREAM, ctypes.c_int64, ctypes.c_float)(('BASS_VST_SetParam', bass_module))
        # BASS_VST_SetParam = func_type(
        #     ctypes.c_bool, HSTREAM, ctypes.c_int64, ctypes.c_float)(('BASS_VST_SetParam', bass_module))

        # BASS_VST_EmbedEditor = func_type(
        #     ctypes.c_bool, HSTREAM, ctypes.c_int64)(('BASS_VST_EmbedEditor', bass_module))
        # BASS_VST_SetScope = func_type(
        #     ctypes.c_bool, HSTREAM, ctypes.c_int64)(('BASS_VST_SetScope', bass_module))
        # BASS_VST_GetInfo = func_type(
        #     HSTREAM, ctypes.c_ulong)(('BASS_VST_GetInfo', bass_module))
        ######

        self.parent.parent.ListBox.List.pending.SkipStopIcon = True
        if self.path == self.parent.cue.path:
            is_position_set = True
        else:
            is_position_set = False
        self.path = self.parent.cue.path
        if pybass.BASS_ChannelIsActive(self.hStream) == 1:
            pybass.BASS_StreamFree(self.hStream)
        if sys.platform.startswith('win'):
            flags = pybass.BASS_STREAM_PRESCAN | pybass.BASS_UNICODE
        elif sys.platform.startswith('darwin'):
            flags = pybass.BASS_STREAM_PRESCAN
            self.path = self.path.encode(sys.getfilesystemencoding())

        self.hStream = pybass.BASS_StreamCreateFile(False, self.path, 0, 0, flags)

        ######
        # print(dir(pybass))
        # from pybass import pybass_vst
        vst_plugin_name = 'LoudMax64.dll'
        vst_plugin_name = 'LoudMaxLite64.dll'
        # vst_plugin_path = os.path.join(os.path.dirname(__file__), 'packages', vst_plugin_name)
        vst_plugin_path = os.path.join('assets', 'dlls', vst_plugin_name)
        if hasattr(sys, '_MEIPASS'):
            vst_plugin_path = os.path.join(sys._MEIPASS, vst_plugin_path)
        else:
            vst_plugin_path = os.path.join(os.path.dirname(
                os.path.dirname(__file__)), vst_plugin_path)
        # BASS_VST_KEEP_CHANS = 0x00000001
        flags = pybass.BASS_UNICODE | pybass.BASS_VST_KEEP_CHANS
        self.vstHandle = pybass.BASS_VST_ChannelSetDSP(self.hStream, vst_plugin_path, flags, 0)
        pybass.BASS_VST_SetParam(self.vstHandle, 0, 0.0)
        pybass.BASS_VST_SetParam(self.vstHandle, 1, 1.0)
        pybass.BASS_VST_SetParam(self.vstHandle, 2, 0.0)
        pybass.BASS_VST_SetParam(self.vstHandle, 3, 0.0)
        # print(os.path.join(os.path.dirname(__file__), 'packages', 'LoudMax64.dll'))
        # self.parent.Show()
        # x = BASS_VST_SetScope(self.vstHandle, 123)
        # dialog = wx.TextEntryDialog(self.parent.parent.parent, 'Enter Your Name', 'Text Entry Dialog')
        # BASS_VST_EmbedEditor(self.vstHandle, dialog.GetHandle())
        # dialog.ShowModal()
        # if dialog.ShowModal() == wx.ID_OK:
        #     self.text.SetValue('Name entered:' + dialog.GetValue())
        # dialog.Destroy()

        # BASS_VST_EmbedEditor(self.vstHandle, self.parent.GetHandle())
        # print()

        # param = BASS_VST_GetParam(self.vstHandle, 0)
        # info = None
        # BASS_VST_SetParam(self.vstHandle, 1, 1.0)

        # print(param)
        # param = BASS_VST_GetParam(self.vstHandle, 1)
        # print(param)
        ######

        self.parent.cue.hStream = self.hStream
        audio.set_volume(self.hStream, 0.0)
        if self.resume is not None:
            resume = self.resume
            if self.resume < 0:
                duration = audio.get_duration(self.hStream)
                resume = duration + self.resume
            audio.set_position(self.hStream, resume)
        pybass.BASS_ChannelPlay(self.hStream, False)

        self.fadein.cnt = self.fadein.time
        if is_position_set is False and self.parent.IsLoopOn():
            self.fadein.cnt = self.fadein.time
        else:
            self.parent.SetVolume()
        self.resume = None
        self.pending = False
        # self.parent.FocusPlayingItem()
        self.parent.parent.ListTab.reInitBuffer = True
        self.parent.parent.ListBox.List.reInitBuffer = True

    def Quit(self):
        self.loop = False
        if pybass.BASS_ChannelIsActive(self.hStream) == 1:
            pybass.BASS_StreamFree(self.hStream)
        # self._Thread__stop()

    def __del__(self):
        gc.collect()


class PlayBoxControl():

    def __init__(self, parent):
        self.parent = parent
        self.InitControlEvent()
        audio.init_bass_play()
        playcue = GetPreference('playcue')
        if playcue is None:
            SetPreference('playcue', self.cue)
        else:
            self.cue = playcue

    def InitControlEvent(self):
        self.reInitWave = True
        self.waveform_length = 1500
        self.pending = Struct(dbresp=False, mfeats=False, mdx=False)
        self.waveform_init = numpy.linspace(0, 0, self.waveform_length)
        self.cue = Struct(mdx=None, path=None, waveform=None,
                          is_playing=False, hStream=0, tempo=0.0, key='-',
                          offset=0, finish=0, duration=0.0, position=0.0, resume=0,
                          fffrTime=15, fffr_variable=15.0, fffr_static=15, channel=2,
                          loop_on=False, autogain_on=False, autogain=0.4, volume=1.0,
                          auto_next=True, highlight_on=False, highlight_skip=False,
                          highlight_offset=None, highlight_variable=None, highlight_static=32,
                          order=None, listId=None, item=None, agc_headroom=1.0,)
        self.item_column = ListBoxColumn()
        self.last_control_time = time.time()
        self.pending_fffr_prev = False
        self.pending_fffr_next = False

    def GetPlayingItemInfo(self, key):
        if self.cue.item is None:
            return None
        idx = [i for i, v in enumerate(self.item_column) if v.key == key]
        if idx == []:
            return None
        return self.cue.item[idx[0]]

    def GetOffsetTime(self):
        return self.cue.offset

    def SetOffsetTime(self, offset):
        self.cue.offset = offset

    def GetWaveform(self):
        return self.cue.waveform

    def SetWaveImage(self, waveform):
        if len(waveform) == 0:
            waveform = None
        self.cue.waveform = waveform

    def AudioEvent(self, event):
        ctime = time.time()
        if ctime - self.last_control_time < 0.05:
            return
        self.last_control_time = ctime
        if self.cue.path is None:
            return
        if self.AudioControl.pending:
            self.parent.ListBox.List.pending.SkipStopIcon = True
            return
        if self.cue.path != self.AudioControl.path:
            return
        if self.cue.hStream != self.AudioControl.hStream:
            return

        # if self.pending_fffr_prev:
        #     self.pending_fffr_prev = False

        # if self.pending_fffr_next:
        #     self.pending_fffr_next = False

        self.cue.position = self.GetPositionTime()
        if self.IsPlaying():
            self.SetResumeTime(self.GetPositionTime())
        else:
            self.cue.position = self.GetResumeTime()

        if self.pending.mdx:
            self.SetAudioEventWithMDX()

        if self.pending.dbresp:
            self.SetAudioEventWithDBRESP()

        if self.pending.mfeats:
            self.SetAudioEventWithMFEATS()

        self.HandleEventTrackFinishTime()
        self.HandleEventFadeOut()

        if not self.AudioControl.pending and self.pending_fffr_prev:
            offset, finish = self.GetTrackTime()
            fffr = self.GetFFFRVariableTime()
            self.SetPositionTime(finish - fffr)
            self.pending_fffr_prev = False

        if not self.AudioControl.pending and self.pending_fffr_next:
            offset, finish = self.GetTrackTime()
            self.SetPositionTime(offset)
            self.pending_fffr_next = False

    def HandleEventFadeOut(self):
        position = self.GetPositionTime()
        finish = self.GetTrackFinishTime()
        if finish == -1.0:
            return
        if finish is None:
            return
        if position is None:
            return
        if self.AudioControl.pending:
            return
        if position > finish - self.AudioControl.fadeout.time:
            self.AudioControl.StartFadeOut()

    def HandleEventTrackFinishTime(self):
        if self.IsTrackFinishTime() is False:
            return
        if self.IsLoopOn():
            self.GotoTrackOffsetTime()
        else:
            result = self.PlayAndFocusCueFileAround(1)
            if result is False:
                self.OnPause(endoflist=True)

    def SetAudioEventWithMDX(self):
        if self.AudioControl.path != self.cue.path:
            return
        self.pending.mdx = False
        self.cue.channel = 2
        self.cue.tempo = 0.0
        self.cue.autogain = 0.4
        self.cue.waveform = None
        self.cue.key = '-'
        self.cue.highlight = None
        self.cue.highlight_offset = None
        self.cue.highlight_variable = None
        self.cue.fffr_static = 15.0
        self.cue.fffr_variable = 15.0
        self.cue.mdx = self.GetMDX(self.cue.path)
        duration = audio.get_duration(self.cue.hStream)
        self.cue.duration = duration
        self.SetTrackOffsetTime(0.0)
        self.SetTrackFinishTime(duration)
        self.cue.item = MakeMusicFileItem(self.cue.path, 0, self.item_column)
        self.DirectDraw()

    def SetAudioEventWithMFEATS(self):
        self.pending.mfeats = False
        # self.SetVolume()
        self.AddMFEATSTask(self.cue.path, urgent=True)
        self.reInitWave = True

    def SetAudioEventWithDBRESP(self):
        # if self.parent.MFEATS.IsPathTasking(self.cue.path):
        #   return
        resp = mfeats.getby_key_value('mdx', self.cue.mdx)
        if resp is None:
            return
        if resp.error == 1:
            return
        self.pending.mfeats = False
        self.cue.autogain = resp.autogain
        self.cue.channel = resp.channel
        self.SetMFEATSKey(resp.key)
        self.SetMFEATSTempo(resp.tempo)
        self.SetBestFFFRVariableTime()
        self.cue.duration = resp.duration
        self.SetHighlightOffsetTime(resp.highlight[0])
        self.SetBestHighlightVariablePeriodTime()
        self.SetWaveImage(resp.waveform)
        if self.IsHighlightOn():
            self.SetTrackTimeWithHighlight()
            self.GotoTrackOffsetTime()
        self.pending.dbresp = False
        self.reInitWave = True

    def IsAutoGainOn(self):
        return False
        return self.cue.autogain_on

    def SetAutoGainOn(self):
        self.cue.autogain_on = True
        self.SetVolume()

    def SetAutoGainOff(self):
        self.cue.autogain_on = False
        self.SetVolume()

    def SetTrackTimeWithHighlight(self):
        offset = self.GetHighlightOffsetTime()
        self.SetTrackOffsetTime(offset)
        period = self.GetHighlightVariablePeriodTime()
        self.SetTrackFinishTime(offset + period)
        self.SetHighlightSkipOff()

    def SetOriginalTrackTime(self):
        self.SetTrackOffsetTime(0.0)
        duration = self.GetDurationtime()
        self.SetTrackFinishTime(duration)

    def AddMFEATSTask(self, path=None, urgent=True):
        if path is None:
            path = self.cue.path
        self.parent.MFEATS.AddMFEATSTask(path, urgent=urgent)

    def GotoTrackOffsetTime(self):
        if self.IsHighlightOn():
            self.SetHighlightSkipOff()
        offset = self.GetTrackOffsetTime()
        if offset is None:
            return
        self.SetPositionTime(offset)

    def IsTrackOffsetTime(self):
        offset = self.GetTrackOffsetTime()
        position = self.GetPositionTime()
        if offset <= position:
            return True
        return False

    def IsTrackFinishTime(self):
        # handles virtual offset and duration for highlight period control
        if self.IsEndOfTrack():
            return True
        finish = self.GetTrackFinishTime()
        position = self.GetPositionTime()
        if finish == -1.0:
            return False
        if finish is None:
            return False
        if position is None:
            return False
        if self.AudioControl.resume is not None:
            return False
        if position >= finish - 0.01:
            if self.IsHighlightOn()\
                    and self.GetHighlightVariablePeriodTime() is None:
                return False
            return True
        return False

    def IsEndOfTrack(self):
        position = self.GetPositionTime()
        duration = self.GetDurationTime()
        if duration == -1.0 or position == -1.0:
            return False
        if position >= duration:
            return True
        return False

    def SetBestTrackFinishTime(self):
        if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            offset, period = self.GetHighlightTime()
            self.SetTrackFinishTime(offset + period)
        else:
            self.SetTrackFinishTime(self.GetDurationTime)

    def GetTrackTime(self):
        return self.cue.offset, self.cue.finish

    def GetTrackOffsetTime(self):
        return self.cue.offset

    def SetTrackOffsetTime(self, offset):
        self.cue.offset = offset

    def GetTrackFinishTime(self):
        return self.cue.finish

    def SetTrackFinishTime(self, finish):
        self.cue.finish = finish

    def GetPath(self):
        return self.cue.path

    def SetPath(self, path):
        self.cue.path = path

    def GetMDX(self, path=None):
        if path is None:
            path = self.cue.path
        return audio.makemdx(path)

    def SetMDX(self, path=None):
        if path is None:
            path = self.cue.path
        self.cue.mdx = audio.makemdx(path)

    def IsLoopOn(self):
        return self.cue.loop_on

    def SetLoopOn(self):
        self.cue.loop_on = True

    def SetLoopOff(self):
        self.cue.loop_on = False

    def IsHighlightOn(self):
        return self.cue.highlight_on

    def SetHighlightOn(self):
        offset, period = self.GetHighlightTime()
        if offset is not None and period is not None:
            finish = offset + period
        else:
            finish = None
        self.SetTrackOffsetTime(offset)
        self.SetTrackFinishTime(finish)
        self.cue.highlight_skip = False
        self.cue.highlight_on = True

    def SetHighlightOff(self):
        self.SetTrackOffsetTime(0.0)
        duration = self.GetDurationTime()
        self.SetTrackFinishTime(duration)
        self.cue.highlight_on = False

    def IsHighlightSkipOn(self):
        return self.cue.highlight_skip

    def SetHighlightSkipOn(self):
        self.SetTrackOffsetTime(0.0)
        duration = self.GetDurationTime()
        self.SetTrackFinishTime(duration)
        self.cue.highlight_skip = True

    def SetHighlightSkipOff(self):
        offset, period = self.GetHighlightTime()
        if offset is None or period is None:
            return
        self.SetTrackOffsetTime(offset)
        self.SetTrackFinishTime(offset + period)
        self.cue.highlight_skip = False

    def SetMFEATSKey(self, key):
        self.cue.key = key

    def SetMFEATSTempo(self, tempo):
        self.cue.tempo = tempo

    def GetNearestBeatTime(self, period, tempo):
        if isinstance(tempo, float) is False:
            return period
        if tempo == 0:
            return period
        xtempo = tempo
        if xtempo <= 95:
            xtempo = xtempo * 2.0
        bar = (60.0 / xtempo) * 16
        periods = [bar * i for i in range(int(xtempo / 4.0))]
        best_period = min(enumerate(periods), key=lambda iv: abs(iv[1] - period))[1]
        return best_period

    def GetHighlightTime(self):
        return self.cue.highlight_offset, self.cue.highlight_variable

    def GetHighlightDurationTypeId(self):
        duration = self.GetHighlightStaticPeriodTime()
        return [i for i, v in enumerate(
            self.parent.parent.MenuBar.highlightDurationItems) if v == duration][0]

    def GetHighlightStaticPeriodTime(self):
        return self.cue.highlight_static

    def SetHighlightStaticPeriodTime(self, static):
        self.cue.highlight_static = static

    def GetHighlightVariablePeriodTime(self):
        return self.cue.highlight_variable

    def SetHighlightVariablePeriodTime(self, variable):
        self.cue.highlight_variable = variable

    def GetHighlightOffsetTime(self):
        return self.cue.highlight_offset

    def SetHighlightOffsetTime(self, offset):
        self.cue.highlight_offset = offset

    def SetBestHighlightVariablePeriodTime(self, static=None, tempo=None):
        if tempo is not None:
            self.cue.tempo = tempo
        else:
            tempo = self.cue.tempo
        if static is not None:
            self.cue.highlight_static = static
        else:
            static = self.cue.highlight_static
        value = self.GetNearestBeatTime(static, tempo)
        duration = self.GetDurationTime()
        if value > duration:
            value = duration
        self.cue.highlight_variable = value

    def GetFFFRStaticTime(self):
        return self.cue.fffr_static

    def SetFFFRStaticTime(self, static):
        self.cue.fffr_static = static

    def GetFFFRVariableTime(self):
        if self.IsHighlightOn():
            return self.cue.fffr_variable / 4
        return self.cue.fffr_variable

    def SetFFFRVariableTime(self, variable):
        self.cue.fffr_variable = variable

    def SetBestFFFRVariableTime(self, static=None, tempo=None):
        if tempo is not None:
            self.cue.tempo = tempo
        else:
            tempo = self.cue.tempo
        if static is not None:
            self.cue.fffr_static = static
        else:
            static = self.cue.fffr_static
        self.cue.fffr_variable = self.GetNearestBeatTime(static, tempo)

    def IsPlaying(self):
        return audio.is_playing(self.cue.hStream)

    def GetDurationTime(self):
        duration = audio.get_duration(self.cue.hStream)
        if duration == -1.0:
            return self.cue.duration
        return duration

    def SetDurationTime(self, duration=None):
        if duration is None:
            duration = audio.get_duration(self.cue.hStream)
        self.cue.duration = duration

    def GetPositionTime(self):
        position = audio.get_position(self.cue.hStream)
        if position == -1.0:
            return self.cue.resume
        return position

    def SetPositionTime(self, position):
        self.AudioControl.resume = position

    def SetResumeTime(self, position):
        self.cue.resume = position

    def GetResumeTime(self):
        return self.cue.resume

    def GetVolume(self):
        return self.cue.volume

    def SetVolume(self, value=None):
        if value is None:
            value = self.GetVolume()
        if value < 0.0:
            value = 0.0
        elif value > 1.0:
            value = 1.0
        self.cue.volume = value
        if self.IsAutoGainOn():
            value = value * self.cue.autogain
            value = value * self.cue.agc_headroom
            if value > 1.0:
                value = 1.0
        audio.set_volume(self.cue.hStream, value)

    def SetVolumeFadeIn(self):
        target_volume = self.GetVolume()
        for value in numpy.arange(0, target_volume, target_volume / 100.0):
            time.sleep(0.002)
            self.SetVolume(value)

    def OnPlay(self):
        self.parent.ListBox.List.pending.SkipStopIcon = True
        audio.set_volume(self.cue.hStream, 0.0)
        self.AudioControl.resume = 0.0
        self.pending.dbresp = True
        self.pending.mdx = True
        self.pending.mfeats = True
        self.SetHighlightSkipOff()
        self.SetTrackOffsetTime(0.0)
        self.parent.ListBox.List.pending.SkipStopIcon = True
        self.parent.ListTab.reInitBuffer = True
        self.parent.ListBox.List.reInitBuffer = True

    def OnStop(self):
        audio.stop(self.cue.hStream)

    def OnPause(self, endoflist=False):
        self.cue.resume = audio.stop(self.cue.hStream)
        if endoflist or self.cue.resume == -1.0:
            self.cue.resume = self.GetTrackFinishTime()
        self.parent.ListBox.List.reInitBuffer = True

    def OnResume(self):
        self.AudioControl.resume = self.cue.resume
        self.SetVolume(self.cue.volume)

    def OnScroll(self, event):
        if event.step < 0:
            audio.fbackward(self.cue.hStream, self.cue.fffr_variable)
        elif event.step > 0:
            audio.fforward(self.cue.hStream, self.cue.fffr_variable)

    def OnFastRewind(self):

        if self.AudioControl.pending or self.pending_fffr_prev:
            return
        if not self.IsPlaying():
            self.OnResume()
        fffr = self.GetFFFRVariableTime()
        if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            fffr = fffr / 1
        position = self.GetPositionTime()
        offset, finish = self.GetTrackTime()
        if position - fffr <= offset:
            if self.IsLoopOn():
                self.GotoTrackOffsetTime()
            else:
                self.pending_fffr_prev = True
                result = self.OnPrev()
                if result is False:
                    self.GotoTrackOffsetTime()
                    self.pending_fffr_prev = False
                self.SelectPlayingItem()
            return
        audio.fbackward(self.cue.hStream, fffr)

    def OnPrevResume(self, fffr):
        path = self.GetCueFileAroundPath(-1)
        if path is None:
            return False
        self.cue.path = path
        self.AudioControl.resume = -fffr
        self.parent.ListBox.List.reInitBuffer = True

    def IsDBRespPending(self):
        return self.pending.dbresp

    def OnFastForward(self):
        if self.AudioControl.pending or self.pending_fffr_next:
            return
        if not self.IsPlaying():
            self.OnResume()
        fffr = self.GetFFFRVariableTime()
        if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            fffr = fffr / 1
        position = self.GetPositionTime()
        offset, finish = self.GetTrackTime()
        if position + fffr >= finish:
            if self.IsLoopOn():
                self.GotoTrackOffsetTime()
            else:
                self.pending_fffr_Next = True
                result = self.OnNext()
                if result is False:
                    # self.GotoTrackOffsetTime()
                    self.pending_fffr_Next = False
                    self.OnPause()
                    self.SetResumeTime(finish)
                    self.Wave.reInitBuffer = True
                self.SelectPlayingItem()
            return
        audio.fforward(self.cue.hStream, fffr)

    def OnPrev(self):
        # is_playing = self.IsPlaying()
        retult = self.PlayAndFocusCueFileAround(-1)
        self.FocusPlayingItem()
        # if not is_playing:
        #     self.OnPause()
        return retult

    def OnNext(self):
        # is_playing = self.IsPlaying()
        result = self.PlayAndFocusCueFileAround(1)
        self.FocusPlayingItem()
        # if not is_playing:
        #     self.OnPause()
        return result

    def FocusPlayingItem(self):
        listItemIdx = self.GetPlayingListItemIdx()
        if listItemIdx == []:
            return False
        listIdx, itemIdx = listItemIdx
        if listIdx != self.parent.ListBox.selectedList:
            return False
        self.parent.ListBox.FocusItem(itemIdx)
        return True

    def SelectPlayingItem(self):
        listItemIdx = self.GetPlayingListItemIdx()
        if listItemIdx == []:
            return False
        listIdx, itemIdx = listItemIdx
        if listIdx != self.parent.ListBox.selectedList:
            return False
        self.parent.ListBox.SelectAndFocusItem(itemIdx)
        return True

    def PlayAndFocusCueFileAround(self, direction):
        path = self.GetCueFileAroundPath(direction)
        if path is None:
            return False
        self.cue.path = path
        self.OnPlay()
        return True

    def IsEndOfList(self, direction=1):
        path = self.GetCueFileAroundPath(direction)
        if path is None:
            return True
        return False

    def GetCueFileAroundPath(self, direction):
        if self.cue.path is None:
            return None
        listItemIdx = self.GetPlayingListItemIdx()
        if listItemIdx == []:
            return None
        listIdx, itemIdx = listItemIdx
        targetItemIdx = itemIdx + direction
        if targetItemIdx == -1:
            return None
        if targetItemIdx >= len(self.parent.ListBox.innerList[listIdx].items):
            return None
        targetPath = self.parent.ListBox\
            .GetItemValueByColumnKey(targetItemIdx, 'path', listIdx)
        return targetPath

    def GetPlayingListIdx(self):
        for listIdx in range(len(self.parent.ListBox.innerList)):
            if self.parent.ListBox.innerList[listIdx].Id == self.cue.listId:
                return listIdx
        return None

    def GetPlayingListItemIdx(self):
        listIdx = self.GetPlayingListIdx()
        if listIdx is None:
            return []
        pathItemsIdx = self.parent.ListBox\
            .GetItemsIdxByColumnKeyValue('path', self.cue.path, listIdx)
        if pathItemsIdx == []:
            return []
        return [listIdx, pathItemsIdx[0]]

    def __del__(self):
        pass
