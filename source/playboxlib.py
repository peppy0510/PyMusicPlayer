# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import collections
import ctypes
import ctypes.wintypes
import gc
import math
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
        if len(inpaths) == 0:
            return False
        path = inpaths[0]
        file_type = os.path.splitext(path)[1][1:].lower()
        if file_type not in SUPPORTED_AUDIO_TYPE:
            return False
        mfeats.create_mfeats_table()
        self.parent.cue.path = path
        self.parent.OnPlay()
        return True

    def __del__(self):
        pass


# the scratch: the hand's speed over this long, how fast the record follows it
# and comes back to speed when let go, and
# the speed under which the direction is kept
# SCRATCH_VELOCITY_WINDOW = 0.04
# SCRATCH_FOLLOW_SECONDS = 0.0046
# the hand's speed is the slope of where it was over this long (a line fitted,
# not the two ends: the cursor moves in whole pixels, and the ends of a short
# stretch made the speed, and so the pitch, wobble ~10%, heard as a metallic ring)
SCRATCH_VELOCITY_WINDOW = 0.06
SCRATCH_FOLLOW_SECONDS = 0.010
# the least pixels of hand a second at normal speed (the jog test's 300, heard
# clean): the view's own scale is used down to this; at 12 s across a pixel was
# 8.6 ms of sound, too coarse to scratch with
SCRATCH_PIXELS_PER_SECOND = 250.0
SCRATCH_RELEASE_SECONDS = 0.04
SCRATCH_DEADBAND = 0.05
SCRATCH_INTERVAL = 0.002


WAVEFORM_MODES = ('vinyl', 'seek')


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
        self.vstHandle = None
        self.failed = False
        # the scratch on the waveform: the GUI says where the hand is, this thread
        # plays the record at the hand's speed (LoopScratchEvent)
        self.reversible = False
        self.base_freq = 44100.0
        # the tempo control: the file's own rate, and whether the stream keeps the
        # pitch (a tempo stream, built only for key lock off 0%)
        self.native_freq = 44100.0
        self.keylocked = False
        self.reopen = False
        self.scratch = Struct(active=False, held=False, moves=collections.deque(),
                              lap=0.0, speed=1.0, seconds_per_pixel=0.0, event_x=0,
                              direction=audio.BASS_FX_RVS_FORWARD)
        threading.Thread(target=self.RunScratch, daemon=True).start()
        # self.maximize_loudness = False
        # self._Thread__exc_clear()
        self.start()

    def run(self):
        while self.loop:
            self.LoopMainEvent()
            self.AutoFadeInOutTime()
            self.LoopFadeInEvent()
            self.LoopFadeOutEvent()

    def RunScratch(self):
        # the scratch on a beat of its own: every 2 ms while a hand is on the
        # record (the test it was heard clean on), not the playback loop's 5 ms
        while self.loop:
            if self.scratch.active:
                time.sleep(SCRATCH_INTERVAL)
                self.LoopScratchEvent()
            else:
                time.sleep(0.01)

    def IsScratchable(self):
        if hasattr(ctypes, 'windll') is False:
            return False
        return self.reversible and self.hStream != 0 and self.pending is False

    def ScratchPress(self, seconds_per_pixel):
        # the hand is read off the cursor by the scratch's own thread every 2 ms
        # (GetCursorPos), not taken from the GUI's mouse events: with the player
        # drawing, those came late and in bunches, and their own times are only
        # to the system tick (about 16 ms), so the record jumped or stood still
        scratch = self.scratch
        scratch.seconds_per_pixel = seconds_per_pixel
        scratch.moves = collections.deque([(time.perf_counter(), self.GetCursorValue())])
        scratch.lap = time.perf_counter()
        scratch.held = True
        scratch.active = True

    def GetCursorValue(self):
        # where the hand is, in the file's seconds: the sound follows the hand, so
        # a drag to the left is later in the file
        point = ctypes.wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            x = point.x
        else:
            # no cursor to read (no desktop): the GUI's last mouse event
            x = self.scratch.event_x
        return -x * self.scratch.seconds_per_pixel

    def ScratchEventAt(self, x):
        # the GUI's mouse events, in screen pixels: a fallback only
        self.scratch.event_x = x

    def SampleHand(self):
        scratch = self.scratch
        now = time.perf_counter()
        scratch.moves.append((now, self.GetCursorValue()))
        while len(scratch.moves) > 2 and now - scratch.moves[0][0] > SCRATCH_VELOCITY_WINDOW:
            scratch.moves.popleft()

    def ScratchRelease(self):
        self.scratch.held = False

    def GetHandSpeed(self):
        # the hand's speed (x normal) over the last moments; a hand still is 0
        moves = list(self.scratch.moves)
        count = len(moves)
        if count < 2:
            return 0.0
        # least squares: the slope of value over time
        mt = sum(t for t, _ in moves) / count
        mv = sum(v for _, v in moves) / count
        stt = sum((t - mt) * (t - mt) for t, _ in moves)
        if stt <= 0:
            return 0.0
        return sum((t - mt) * (v - mv) for t, v in moves) / stt

    def ApplyTempo(self):
        # key locked: the tempo stream's percent; else the rate, the pitch with it (the
        # scratch's speeds are of this rate)
        rate = self.parent.GetTempoRate()
        if self.keylocked:
            self.base_freq = self.native_freq
            audio.set_tempo_percent(self.hStream, (rate - 1.0) * 100.0)
        else:
            self.base_freq = self.native_freq * rate
        if self.hStream and self.scratch.active is False:
            audio.set_frequency(self.hStream, self.base_freq)

    def SetTempo(self):
        # from the GUI: a stream of the other kind is opened again (key lock on or
        # off, or off 0% with it); paused, it is opened so when played
        if self.hStream == 0:
            return
        # a tempo stream back at 0% is kept (opened again it was a gap), not made
        wanted = self.parent.IsTempoKeyLockOn() and (
            self.parent.IsTempoKeyLockWanted() or self.keylocked)
        if wanted != self.keylocked:
            if self.IsSeekable():
                self.reopen = True
            return
        self.ApplyTempo()

    def LoopScratchEvent(self):
        scratch = self.scratch
        if scratch.active is False:
            return
        if self.IsScratchable() is False:
            # a seek (a click on the strip) or a new file came in: back to speed
            # first, or the record was left turning at the hand's last speed
            if self.hStream and scratch.held is False:
                audio.set_frequency(self.hStream, self.base_freq)
                audio.set_direction(self.hStream, audio.BASS_FX_RVS_FORWARD)
            scratch.direction = audio.BASS_FX_RVS_FORWARD
            scratch.speed = 1.0
            scratch.active = False
            return
        now = time.perf_counter()
        elapsed = now - scratch.lap
        scratch.lap = now
        if scratch.held:
            self.SampleHand()
            target, tau = (self.GetHandSpeed(), SCRATCH_FOLLOW_SECONDS)
        else:
            target, tau = (1.0, SCRATCH_RELEASE_SECONDS)
        scratch.speed += (target - scratch.speed) * (1.0 - math.exp(-elapsed / tau))
        if scratch.held is False and abs(scratch.speed - 1.0) < 0.01:
            # let go and back to speed: as it was before the hand
            scratch.speed = 1.0
            scratch.active = False
        # a deadband: nearly still, the direction is kept, not flipped back and forth
        if scratch.speed < -SCRATCH_DEADBAND and scratch.direction != audio.BASS_FX_RVS_REVERSE:
            scratch.direction = audio.BASS_FX_RVS_REVERSE
            audio.set_direction(self.hStream, scratch.direction)
        elif scratch.speed > SCRATCH_DEADBAND and scratch.direction != audio.BASS_FX_RVS_FORWARD:
            scratch.direction = audio.BASS_FX_RVS_FORWARD
            audio.set_direction(self.hStream, scratch.direction)
        if scratch.active is False:
            audio.set_frequency(self.hStream, self.base_freq)
            return
        # BASS's least rate is 100 Hz: near enough to stopped
        audio.set_frequency(self.hStream, max(self.base_freq * min(abs(scratch.speed), 4.0), 100.0))
        if scratch.held and pybass.BASS_ChannelIsActive(self.hStream) != pybass.BASS_ACTIVE_PLAYING:
            # run into the file's start backwards: played on from there
            pybass.BASS_ChannelPlay(self.hStream, False)

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
        if self.reopen:
            # key lock on or off while it plays: opened again where it is
            self.reopen = False
            if self.path == self.parent.cue.path and self.IsSeekable():
                self.resume = audio.get_position(self.hStream)
                self.pending = True
                self.InitAudio()
                return
        if self.path != self.parent.cue.path:
            self.pending = True
            self.InitAudio()
        elif self.resume is not None:
            self.pending = True
            if self.IsSeekable():
                self.SeekAudio()
            else:
                self.InitAudio()

    def IsSeekable(self):
        # the same file still playing: moved in it, not opened again
        if self.hStream == 0:
            return False
        return pybass.BASS_ChannelIsActive(self.hStream) == pybass.BASS_ACTIVE_PLAYING

    def SeekAudio(self):
        audio.set_volume(self.hStream, 0.0)
        if self.scratch.held is False:
            # a click on the strip pressed the record still: let go, at speed
            self.scratch.active = False
            self.scratch.speed = 1.0
            self.scratch.direction = audio.BASS_FX_RVS_FORWARD
            audio.set_frequency(self.hStream, self.base_freq)
            audio.set_direction(self.hStream, audio.BASS_FX_RVS_FORWARD)
        resume = self.resume
        if resume < 0:
            resume = audio.get_duration(self.hStream) + resume
        audio.set_position(self.hStream, resume)
        self.fadeout.cnt = 0.0
        self.fadein.cnt = self.fadein.time
        self.resume = None
        self.pending = False

    def FreeAudio(self):
        # every stream, played out or not: only playing ones were freed, and one
        # that had reached its end kept its file and its plugin
        if self.hStream == 0:
            return
        if self.vstHandle:
            pybass.BASS_VST_ChannelRemoveDSP(self.hStream, self.vstHandle)
            self.vstHandle = None
        pybass.BASS_StreamFree(self.hStream)
        self.hStream = 0

    def LoopFadeInEvent(self):
        # if self.parent.IsHighlightOn() is False: return
        if self.fadein.cnt == 0.0:
            return
        self.fadein.cnt -= self.interval
        if self.fadein.cnt < 0.0:
            self.fadein.cnt = 0.0
        ratio = 1.0 - self.fadein.cnt / self.fadein.time
        audio.set_volume(self.hStream, self.parent.GetOutputVolume() * ratio)

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
        finish = self.parent.GetTrackFinishTime()
        if finish is not None and finish != -1.0:
            left = finish - audio.get_position(self.hStream)
            ratio = min(ratio, max(left, 0.0) / self.fadeout.time)
        audio.set_volume(self.hStream, self.parent.GetOutputVolume() * ratio)

    def GetSoundOffsetTime(self):
        if self.parent.IsSkipSilenceOn() is False:
            return 0.0
        if self.parent.IsHighlightOn() and self.parent.IsHighlightSkipOn() is False:
            return 0.0
        try:
            resp = mfeats.getby_key_value('path', self.path)
        except Exception:
            return 0.0
        if resp is None or resp.error == 1 or audio.is_waveform_3band(resp.waveform) is False:
            return 0.0
        return audio.get_waveform_sound_time(resp.waveform, resp.duration)[0]

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
        #     ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_int64, ctypes.c_ulong
        # )(('BASS_VST_ChannelSetDSP', bass_module))
        # BASS_VST_GetParam = func_type(
        #     ctypes.c_bool, HSTREAM, ctypes.c_int64
        # )(('BASS_VST_GetParam', bass_module))
        # BASS_VST_SetParam = func_type(
        #     ctypes.c_bool, HSTREAM, ctypes.c_int64, ctypes.c_float
        # )(('BASS_VST_SetParam', bass_module))
        # BASS_VST_SetParam = func_type(
        #     ctypes.c_bool, HSTREAM, ctypes.c_int64, ctypes.c_float
        # )(('BASS_VST_SetParam', bass_module))

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
        # if pybass.BASS_ChannelIsActive(self.hStream) == 1:
        #     pybass.BASS_StreamFree(self.hStream)
        self.FreeAudio()
        if sys.platform.startswith('win'):
            flags = pybass.BASS_STREAM_PRESCAN | pybass.BASS_UNICODE
        elif sys.platform.startswith('darwin'):
            flags = pybass.BASS_STREAM_PRESCAN
            self.path = self.path.encode(sys.getfilesystemencoding())

        # self.hStream = pybass.BASS_StreamCreateFile(False, self.path, 0, 0, flags)
        self.hStream, self.reversible = audio.create_play_stream(
            self.path, flags, keylock=self.parent.IsTempoKeyLockWanted())
        self.scratch.active = False
        self.scratch.speed = 1.0
        self.scratch.direction = audio.BASS_FX_RVS_FORWARD
        if self.hStream == 0:
            # not opened (gone, unreadable, no device): the player moves on
            self.parent.cue.hStream = 0
            self.failed = True
            self.resume = None
            self.pending = False
            return
        self.native_freq = audio.get_frequency(self.hStream)
        self.keylocked = audio.get_tempo_source(self.hStream) != 0
        self.ApplyTempo()

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
        # loudness_value = 1.0 if self.maximize_loudness else 0.0
        # pybass.BASS_VST_SetParam(self.vstHandle, 1, loudness_value)
        pybass.BASS_VST_SetParam(self.vstHandle, 1, 1.0)
        pybass.BASS_VST_SetParam(self.vstHandle, 2, 0.0)
        pybass.BASS_VST_SetParam(self.vstHandle, 3, 0.0)
        self.SetVSTBypass()
        # print(os.path.join(os.path.dirname(__file__), 'packages', 'LoudMax64.dll'))
        # self.parent.Show()
        # x = BASS_VST_SetScope(self.vstHandle, 123)
        # dialog = wx.TextEntryDialog(
        #     self.parent.parent.parent, 'Enter Your Name', 'Text Entry Dialog')
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
        if self.resume == 0.0 and is_position_set is False:
            self.resume = self.GetSoundOffsetTime()
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
        elif self.fadein.cnt == 0.0:
            self.parent.SetVolume()
        self.resume = None
        self.pending = False
        # self.parent.FocusPlayingItem()
        self.parent.parent.ListTab.reInitBuffer = True
        self.parent.parent.ListBox.List.reInitBuffer = True

    # def IsMaximizeLoudnessOn(self):
    #     pybass.BASS_VST_GetParam(self.vstHandle, 1)

    # def SetMaximizeLoudnessOn(self):
    #     if not self.vstHandle:
    #         return
    #     self.maximize_loudness = True
    #     pybass.BASS_VST_SetParam(self.vstHandle, 1, 1.0)

    # def SetMaximizeLoudnessOff(self):
    #     if not self.vstHandle:
    #         return
    #     self.maximize_loudness = False
    #     pybass.BASS_VST_SetParam(self.vstHandle, 1, 0.0)

    def SetVSTBypass(self):
        if not self.vstHandle:
            return
        pybass.BASS_VST_SetBypass(self.vstHandle, self.parent.IsLoudOn() is False)

    def Quit(self):
        self.loop = False
        # if pybass.BASS_ChannelIsActive(self.hStream) == 1:
        #     pybass.BASS_StreamFree(self.hStream)
        self.FreeAudio()
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
        # grid: the last look for the song's beat grid (False: not looked for), so the
        # song the app opens with is looked up too
        self.pending = Struct(dbresp=False, mfeats=False, mdx=False, wave=False, early=False,
                              dbresp_lap=0.0, wave_since=0.0, grid=0.0, grid_since=time.time())
        self.failed_count = 0
        # the tempo control: a rate kept from song to song (1.0 at every start), the
        # key lock and the slider's range (percent) kept
        self.tempo_rate = 1.0
        self.tempo_keylock = GetPreference('tempo_keylock') is True
        self.tempo_range = GetPreference('tempo_range') or 8
        self.skip_silence = GetPreference('skip_silence') is True
        # the waveform detail strip's mode: 'vinyl' (a record to scratch) or 'seek'
        # (click or drag to a place); before it, a scratch on/off of its own
        self.waveform_mode = GetPreference('waveform_mode')
        if self.waveform_mode not in WAVEFORM_MODES:
            # self.waveform_mode = 'seek' if GetPreference('waveform_scratch') is False else 'vinyl'
            # seek by default; vinyl is chosen in the preferences
            self.waveform_mode = 'seek'
        self.waveform_init = numpy.linspace(0, 0, self.waveform_length)
        self.cue = Struct(mdx=None, path=None, waveform=None,
                          is_playing=False, hStream=0, tempo=0.0, key='-',
                          offset=0, finish=0, duration=0.0, position=0.0, resume=0,
                          fffrTime=15, fffr_variable=15.0, fffr_static=15, channel=2,
                          loop_on=False, loud_on=True, autogain_on=False, autogain=0.4,
                          volume=1.0,
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
        if audio.is_waveform_3band(waveform) is False:
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

        if self.pending.wave:
            self.SetAudioEventWithWAVE()

        if self.pending.grid is not False:
            self.SetAudioEventWithGRID()

        if self.HandleEventOpenFailure():
            return
        if self.cue.hStream:
            self.failed_count = 0

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

    def HandleEventOpenFailure(self):
        # the file did not open: on to the next one, but not through a whole list
        # that cannot be played (no device)
        if self.AudioControl.failed is False:
            return False
        self.AudioControl.failed = False
        self.failed_count += 1
        if self.failed_count > 3:
            self.failed_count = 0
            self.OnPause(endoflist=True)
            return True
        result = self.PlayAndFocusCueFileAround(1)
        if result is False:
            self.failed_count = 0
            self.OnPause(endoflist=True)
        return True

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
        self.cue.grid = None
        self.pending.grid = 0.0
        self.pending.grid_since = time.time()
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
        # once a second while the file is being analyzed, not every event
        if time.time() - self.pending.dbresp_lap < 1.0:
            return
        self.pending.dbresp_lap = time.time()
        resp = mfeats.getby_key_value('mdx', self.cue.mdx)
        if resp is None:
            self.SetEarlyAnalysis(highlight=True)
            return
        if resp.error == 1:
            # not analyzable: nothing more will come
            self.pending.dbresp = False
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
        self.SkipLeadingSilence()
        if resp.version != mfeats.MFEATS_VERSION:
            # analyzed before the current waveform: analyze again for it
            self.parent.MFEATS.AddMFEATSTask(self.cue.path, urgent=True, forced=True)
            self.pending.wave = time.time()
            self.pending.wave_since = time.time()
        if self.IsHighlightOn():
            self.SetTrackTimeWithHighlight()
            # gone to already with the early highlight (the same offset)
            if self.pending.early is False:
                self.GotoTrackOffsetTime()
        self.pending.dbresp = False
        self.reInitWave = True

    def SetAudioEventWithWAVE(self):
        if time.time() - self.pending.wave < 1.0:
            return
        # given up on after a while (a three-hour mix takes a couple of minutes)
        if time.time() - self.pending.wave_since > 600:
            self.pending.wave = False
            return
        self.pending.wave = time.time()
        resp = mfeats.getby_key_value('mdx', self.cue.mdx)
        if resp is None:
            return
        if resp.error == 1:
            self.pending.wave = False
            return
        if resp.version != mfeats.MFEATS_VERSION:
            # analyzed again while it plays: the waveform early, its highlight with
            # the rest (where it plays is not moved)
            self.SetEarlyAnalysis(highlight=False)
            return
        # analyzed again: all the new values in place of the older version's (they
        # were the waveform's alone), and where it plays left as it is
        self.pending.wave = False
        self.cue.autogain = resp.autogain
        self.cue.channel = resp.channel
        self.SetMFEATSKey(resp.key)
        self.SetMFEATSTempo(resp.tempo)
        self.SetBestFFFRVariableTime()
        self.cue.duration = resp.duration
        self.SetHighlightOffsetTime(resp.highlight[0])
        self.SetBestHighlightVariablePeriodTime()
        self.SetWaveImage(resp.waveform)
        self.SkipLeadingSilence()
        if self.IsHighlightOn():
            self.SetTrackTimeWithHighlight()
        self.reInitWave = True

    def SetAudioEventWithGRID(self):
        # once a second until the song's grid is in (a grid alone takes seconds, a
        # whole analysis more), given up on after a while
        if self.pending.mdx or self.cue.mdx is None:
            return
        if time.time() - self.pending.grid < 1.0:
            return
        if time.time() - self.pending.grid_since > 600:
            self.pending.grid = False
            return
        self.pending.grid = time.time()
        grid = mfeats.get_grid(self.cue.mdx)
        if grid is None or grid.version != mfeats.GRID_VERSION:
            return
        self.pending.grid = False
        self.cue.grid = grid if grid.bpm > 0 else None
        self.ApplyGridToTimes()
        self.Wave.reInitBuffer = True
        self.WaveDetail.reInitBuffer = True

    def ApplyGridToTimes(self):
        # the highlight on a bar and the jumps in bars, once the grid is in (where it
        # plays is not moved)
        if self.GetGrid() is None:
            return
        self.SetBestFFFRVariableTime()
        offset = self.GetHighlightOffsetTime()
        if offset is None or self.cue.highlight_variable is None:
            return
        self.SetHighlightOffsetTime(offset)
        self.SetBestHighlightVariablePeriodTime()
        if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            offset = self.GetHighlightOffsetTime()
            self.SetTrackOffsetTime(offset)
            self.SetTrackFinishTime(offset + self.GetHighlightVariablePeriodTime())
        self.reInitWave = True

    def GetTempoRate(self):
        return self.tempo_rate

    def SetTempoRate(self, rate):
        limit = self.tempo_range / 100.0
        rate = min(max(rate, 1.0 - limit), 1.0 + limit)
        if abs(rate - self.tempo_rate) < 1e-6:
            return
        self.tempo_rate = rate
        self.AudioControl.SetTempo()
        self.Info.reInitBuffer = True

    def IsTempoKeyLockOn(self):
        return self.tempo_keylock

    def SetTempoKeyLock(self, on):
        self.tempo_keylock = on
        SetPreference('tempo_keylock', on)
        self.AudioControl.SetTempo()

    def IsTempoKeyLockWanted(self):
        # the tempo stream only when it changes something
        return self.tempo_keylock and abs(self.tempo_rate - 1.0) > 1e-6

    def GetTempoRange(self):
        return self.tempo_range

    def SetTempoRange(self, percent):
        self.tempo_range = percent
        SetPreference('tempo_range', percent)
        self.SetTempoRate(self.tempo_rate)

    def GetPlayingTempo(self):
        # the BPM heard: the grid's (or the analysis') times the rate
        grid = self.GetGrid()
        tempo = grid.bpm if grid is not None else self.cue.tempo
        try:
            return float(tempo) * self.tempo_rate
        except (TypeError, ValueError):
            return 0.0

    def GetGrid(self):
        # the playing song's grid, or None (none yet, none found)
        grid = getattr(self.cue, 'grid', None)
        if grid is None or grid.mdx != self.cue.mdx:
            return None
        return grid

    def IsGridShown(self):
        # View > Beat Grid
        return self.parent.parent.IsBeatGridShowOn()

    def GetGridDownbeat(self):
        grid = self.GetGrid()
        period = 60.0 / grid.bpm
        return (grid.downbeat + (grid.shift or 0) * period) % (period * 4)

    def GetGridLines(self, start, end):
        '''[(seconds, level)] of the grid's beats from start to end; level 0 a beat, 1 a
        bar's first, 2 a phrase's (4 bars)'''
        grid = self.GetGrid()
        if grid is None or end <= start or self.IsGridShown() is False:
            return []
        period = 60.0 / grid.bpm
        downbeat = self.GetGridDownbeat()
        first = int(math.ceil((start - downbeat) / period))
        last = int(math.floor((end - downbeat) / period))
        return [(downbeat + k * period, 2 if k % 16 == 0 else 1 if k % 4 == 0 else 0)
                for k in range(first, last + 1)]

    def SetGridShift(self, shift):
        grid = self.GetGrid()
        if grid is None:
            return
        grid.shift = shift % 4
        mfeats.set_grid_shift(grid.mdx, grid.shift)
        self.ApplyGridToTimes()
        self.Wave.reInitBuffer = True
        self.WaveDetail.reInitBuffer = True

    def SetGridBarAt(self, seconds):
        # the bar from the beat nearest seconds
        grid = self.GetGrid()
        if grid is None:
            return
        period = 60.0 / grid.bpm
        self.SetGridShift(int(round((seconds - grid.downbeat) / period)))

    def SetEarlyAnalysis(self, highlight=True):
        # being analyzed: its waveform and highlight as soon as the worker has them,
        # before the tempo's octave and the key (mfeats.insert_mfeats_wave)
        if self.pending.early:
            return
        wave = mfeats.getby_mdx_wave(self.cue.mdx)
        if wave is None or audio.is_waveform_3band(wave.waveform) is False:
            return
        self.pending.early = True
        if audio.is_waveform_3band(self.cue.waveform) is False:
            self.SetWaveImage(wave.waveform)
        if highlight:
            self.SetHighlightOffsetTime(wave.highlight[0])
            # its length in beats of the tempo before its octave: half a beat at most
            # from the one to come (the tempo itself is not shown before it)
            value = self.GetNearestBeatTime(self.cue.highlight_static, wave.tempo)
            self.cue.highlight_variable = min(value, self.GetDurationTime())
            if self.IsHighlightOn():
                self.SetTrackTimeWithHighlight()
                self.GotoTrackOffsetTime()
        self.reInitWave = True

    def IsHighlightKnown(self):
        # analyzed, or its highlight early (SetEarlyAnalysis)
        return self.pending.dbresp is False or self.pending.early

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

    def IsWaveformScratchOn(self):
        return self.waveform_mode == 'vinyl'

    def GetWaveformMode(self):
        return self.waveform_mode

    def SetWaveformMode(self, mode):
        if mode not in WAVEFORM_MODES:
            return
        self.waveform_mode = mode
        SetPreference('waveform_mode', mode)
        self.AudioControl.ScratchRelease()

    def IsSkipSilenceOn(self):
        return self.skip_silence

    def SetSkipSilenceOn(self):
        self.skip_silence = True
        SetPreference('skip_silence', True)
        self.SetSoundTrackTime()

    def SetSkipSilenceOff(self):
        self.skip_silence = False
        SetPreference('skip_silence', False)
        self.SetSoundTrackTime()

    def GetSoundTime(self):
        duration = self.GetDurationTime()
        if self.IsSkipSilenceOn() and audio.is_waveform_3band(self.cue.waveform):
            return audio.get_waveform_sound_time(self.cue.waveform, duration)
        return (0.0, duration)

    def SetSoundTrackTime(self):
        # the whole track, or its sound alone when skipping silence; the
        # highlight keeps its own period
        if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            return
        offset, finish = self.GetSoundTime()
        self.SetTrackOffsetTime(offset)
        self.SetTrackFinishTime(finish)

    def SkipLeadingSilence(self):
        self.SetSoundTrackTime()
        if self.IsSkipSilenceOn() is False:
            return
        if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            return
        offset = self.GetTrackOffsetTime()
        if self.GetPositionTime() < offset:
            self.SetPositionTime(offset)

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

    def IsLoudOn(self):
        return getattr(self.cue, 'loud_on', True)

    def SetLoudOn(self):
        self.cue.loud_on = True
        self.UpdateVSTBypass()

    def SetLoudOff(self):
        self.cue.loud_on = False
        self.UpdateVSTBypass()

    def UpdateVSTBypass(self):
        if hasattr(self, 'AudioControl') is False:
            return
        self.AudioControl.SetVSTBypass()

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
        # self.SetTrackOffsetTime(0.0)
        # duration = self.GetDurationTime()
        # self.SetTrackFinishTime(duration)
        offset, finish = self.GetSoundTime()
        self.SetTrackOffsetTime(offset)
        self.SetTrackFinishTime(finish)
        self.cue.highlight_on = False

    def IsHighlightSkipOn(self):
        return self.cue.highlight_skip

    def SetHighlightSkipOn(self):
        # self.SetTrackOffsetTime(0.0)
        # duration = self.GetDurationTime()
        # self.SetTrackFinishTime(duration)
        offset, finish = self.GetSoundTime()
        self.SetTrackOffsetTime(offset)
        self.SetTrackFinishTime(finish)
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
        # the grid's tempo when there is one (the analysis' own is in 0.1 BPM steps)
        grid = self.GetGrid()
        if grid is not None:
            tempo = float(grid.bpm)
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
        # on the nearest bar's first beat when the song has a grid
        grid = self.GetGrid()
        if grid is not None and offset is not None:
            bar = 60.0 / grid.bpm * 4
            downbeat = self.GetGridDownbeat()
            offset = downbeat + round((offset - downbeat) / bar) * bar
            if offset < 0:
                offset += bar
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
        # 16 bars on the grid (4 in a highlight, GetFFFRVariableTime): a jump lands
        # on the same place in the beat
        grid = self.GetGrid()
        if grid is not None:
            self.cue.fffr_variable = 60.0 / grid.bpm * 64

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
        audio.set_volume(self.cue.hStream, self.GetOutputVolume(value))

    def GetOutputVolume(self, value=None):
        # the stream's volume for a volume: with the auto gain and its
        # headroom, the fades' end and start too
        if value is None:
            value = self.GetVolume()
        if self.IsAutoGainOn():
            value = min(value * self.cue.autogain * self.cue.agc_headroom, 1.0)
        return value

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
        self.pending.dbresp_lap = 0.0
        self.pending.early = False
        self.pending.mdx = True
        self.pending.mfeats = True
        self.pending.wave = False
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
        if offset is None or finish is None:
            # a highlight without its period yet (not analyzed): the whole sound
            offset, finish = self.GetSoundTime()
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
        if offset is None or finish is None:
            offset, finish = self.GetSoundTime()
        if position + fffr >= finish:
            if self.IsLoopOn():
                self.GotoTrackOffsetTime()
            else:
                self.pending_fffr_next = True
                result = self.OnNext()
                if result is False:
                    # self.GotoTrackOffsetTime()
                    self.pending_fffr_next = False
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
