# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import addons
import audio
import collections
import ctypes
import ctypes.wintypes
import gc
import library
import master
import math
import mfeats
# import modpybass as pybass
import numpy
import os
import radio
import sys
import threading
import time
import wx

from macroboxlib import COUNTS
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
# the key's move either way, in semitones
TEMPO_SEMITONES = 6
# the tempo's ranges (percent) and their steps as a CDJ's: 0.02% at 6, 0.05% at 10 and 16,
# 0.5% at WIDE (100: down to -100%, stopped as a CDJ is; with the key lock to -95%, the
# tempo stream's least)
TEMPO_RANGES = (6, 10, 16, 100)
TEMPO_STEPS = {6: 0.02, 10: 0.05, 16: 0.05, 100: 0.5}
TEMPO_LEAST_RATE = 0.05
# BASS's least rate (Hz): at -100% (0 would be the file's own rate)
LEAST_FREQUENCY = 100.0
# a song (or a station) kept among the played lately after it has played this long
RECENT_AFTER_MS = 5000
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
        # a station's stream that did not open: BASS's error (radio.ERRORS); the time its
        # connection began while it is being made
        self.stream_error = None
        self.connecting = None
        # SHORT's cuts (the radio edit): (path, [(from, to)]) jumped over at mixtime by syncs on the
        # stream (seamless, on the beat: a seek mutes and fades in)
        self.jumps = (None, [])
        self.jump_syncs = []
        self.jump_targets = []
        self.jump_proc = pybass.SYNCPROC(self.OnJump)
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
        if audio.is_stream_path(self.path):
            # a station as it comes: played faster, its buffer ran dry and it stuttered
            rate = 1.0
        if self.keylocked:
            # the tempo stream: the tempo there with the key lock, else by the rate as
            # without it; the key's move on top of either
            if self.parent.IsTempoKeyLockOn():
                self.base_freq = self.native_freq
                audio.set_tempo_percent(self.hStream, (rate - 1.0) * 100.0)
            else:
                self.base_freq = max(self.native_freq * rate, LEAST_FREQUENCY)
                audio.set_tempo_percent(self.hStream, 0.0)
            audio.set_tempo_pitch(self.hStream, self.parent.GetTempoSemitones())
        else:
            self.base_freq = self.native_freq * rate
        self.base_freq = max(self.base_freq, LEAST_FREQUENCY)
        if self.hStream and self.scratch.active is False:
            audio.set_frequency(self.hStream, self.base_freq)

    def NoteRecent(self, path):
        if path != self.parent.cue.path or self.parent.IsPlaying() is False:
            return
        (radio.note_recent if audio.is_stream_path(path) else library.note_recent)(path)

    def SetTempo(self):
        # from the GUI: a stream of the other kind is opened again (key lock on or
        # off, or off 0% with it); paused, it is opened so when played
        if self.hStream == 0:
            return
        if audio.is_stream_path(self.path):
            # a station: its key on its tempo stream as it plays (radio.open_stream), never
            # opened again (a connection's gap)
            self.ApplyTempo()
            return
        # a tempo stream back at 0% is kept (opened again it was a gap), not made
        wanted = self.parent.IsTempoKeyLockWanted() or (self.keylocked and (
            self.parent.IsTempoKeyLockOn() or self.parent.GetTempoSemitones() != 0))
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
        if scratch.held and pybass.BASS_ChannelIsActive(self.hStream)\
                != pybass.BASS_ACTIVE_PLAYING:
            # run into the file's start backwards: played on from there
            audio.play(self.hStream)

    def AutoFadeInOutTime(self):
        if self.parent.IsHighlightOn()\
                and self.parent.IsHighlightSkipOn() is False:
            self.fadein.time = 0.15
            self.fadeout.time = 1.00
        elif self.parent.IsRadioEditActive():
            # its end faded as a radio edit's: over a bar or so
            self.fadein.time = 0.1
            self.fadeout.time = 2.50
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

    def SetJumps(self, path, cuts):
        cuts = [tuple(v) for v in cuts]
        if (path, cuts) == self.jumps:
            return
        self.jumps = (path, cuts)
        self.ApplyJumps()

    def ApplyJumps(self):
        # the cuts of the stream's own file as its syncs (those of another file dropped)
        hstream = self.hStream
        for sync in self.jump_syncs:
            pybass.BASS_ChannelRemoveSync(hstream, sync)
        self.jump_syncs = []
        path, cuts = self.jumps
        if hstream == 0 or path != self.path:
            self.jump_targets = []
            return
        self.jump_targets = [pybass.BASS_ChannelSeconds2Bytes(hstream, to) for _, to in cuts]
        for i, (at, _) in enumerate(cuts):
            sync = pybass.BASS_ChannelSetSync(
                hstream, pybass.BASS_SYNC_POS | pybass.BASS_SYNC_MIXTIME,
                pybass.BASS_ChannelSeconds2Bytes(hstream, at), self.jump_proc, i)
            if sync:
                self.jump_syncs.append(sync)

    def OnJump(self, sync, channel, data, user):
        # BASS's mixing thread: on at once (a hand on the record plays it as it is)
        index = user or 0
        if self.scratch.active or index >= len(self.jump_targets):
            return
        pybass.BASS_ChannelSetPosition(channel, self.jump_targets[index], pybass.BASS_POS_BYTE)

    def GetSoundOffsetTime(self):
        # where a file opens: its edit's start (SHORT), its sound's (skip silence)
        edit = self.parent.IsRadioEditOn()
        if self.parent.IsSkipSilenceOn() is False and edit is False:
            return 0.0
        if self.parent.IsHighlightOn() and self.parent.IsHighlightSkipOn() is False:
            return 0.0
        try:
            resp = mfeats.getby_key_value('path', self.path)
        except Exception:
            return 0.0
        if resp is None or resp.error == 1 or audio.is_waveform_3band(resp.waveform) is False:
            return 0.0
        if edit:
            grid = mfeats.get_grid(resp.mdx)
            if grid is not None and grid.version == mfeats.GRID_VERSION and grid.bpm > 0:
                grid = mfeats.apply_grid_scale(grid)
                plan = mfeats.choose_radio_edit(resp.waveform, resp.duration, grid.bpm,
                                                mfeats.get_phrase_start(grid))
                if plan is not None:
                    return plan[0]
        if self.parent.IsSkipSilenceOn() is False:
            return 0.0
        return audio.get_waveform_sound_time(resp.waveform, resp.duration)[0]

    def InitAudio(self):
        COUNTS['init_audio'] += 1
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
        self.stream_error = None
        if audio.is_stream_path(self.path):
            # a station: its stream as it comes (no reverse, no key lock: nothing to seek);
            # the connection's start told while it lasts (IsStreamConnecting)
            self.connecting = time.time()
            try:
                self.hStream, self.stream_error = radio.open_stream(self.path)
            finally:
                self.connecting = None
            self.reversible = False
        else:
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
        # kept among the played lately (library.note_recent, radio.note_recent) once it has
        # played a while: a song skipped through (prev and next held) is not, and no
        # setting is written at each (14 ms a write); on the GUI's thread
        if is_position_set is False:
            wx.CallAfter(wx.CallLater, RECENT_AFTER_MS, self.NoteRecent, self.path)
        self.native_freq = audio.get_frequency(self.hStream)
        self.keylocked = audio.get_tempo_source(self.hStream) != 0
        self.ApplyTempo()
        self.jump_syncs = []
        self.ApplyJumps()

        ######
        # print(dir(pybass))
        # from pybass import pybass_vst
        # LOUD: Auto Master (audio.set_automaster), in LoudMax's place (not allowed to be
        # shipped)
        self.vstHandle = audio.set_automaster(self.hStream, self.parent.IsLoudOn(),
                                              master.get_values())
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
        audio.play(self.hStream)

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
        # the add-ons the repository may not carry, fetched once when missing (AAC loaded
        # as soon as it is in)
        addons.fetch_missing(lambda names: wx.CallAfter(audio.load_bass_plugins))
        playcue = GetPreference('playcue')
        if playcue is None:
            SetPreference('playcue', self.cue)
        else:
            # one saved before a key was added: that key's first value
            for key, value in self.cue.items():
                if hasattr(playcue, key) is False:
                    setattr(playcue, key, value)
            self.cue = playcue
        # HIGHLIGHT and SHORT both on, as saved: SHORT's is kept at its toggle, the song's
        # HIGHLIGHT only at a clean close, so SHORT turned on after it (a close missed)
        # is the later one
        if self.radio_edit and self.cue.highlight_on:
            self.cue.highlight_on = False

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
        # the key moved in semitones, its tempo kept (0 at every start too)
        self.tempo_semitones = 0
        self.tempo_keylock = GetPreference('tempo_keylock') is True
        # a range kept from before the CDJ's (8, 50): 10
        self.tempo_range = GetPreference('tempo_range')
        if self.tempo_range not in TEMPO_RANGES:
            self.tempo_range = 10
        self.skip_silence = GetPreference('skip_silence') is True
        self.radio_edit = GetPreference('radio_edit') is True
        self.radio_edit_cache = None
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
                          edit_skip=False,
                          order=None, listId=None, item=None, agc_headroom=1.0,)
        self.item_column = ListBoxColumn()
        self.live_trace = radio.LiveTrace()
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

    def SetStreamCue(self):
        # a station: nothing of the analysis looked up (no file), no length (no end, no
        # highlight, no waveform), its level as it comes
        for key in ('dbresp', 'mfeats', 'mdx', 'wave', 'early'):
            setattr(self.pending, key, False)
        self.pending.grid = False
        self.cue.mdx = None
        self.cue.waveform = None
        self.cue.grid = None
        self.cue.tempo = 0.0
        self.cue.key = '-'
        self.cue.channel = 2
        self.cue.autogain = 1.0
        self.cue.duration = 0.0
        self.cue.highlight = None
        self.cue.highlight_offset = None
        self.cue.highlight_variable = None
        self.cue.highlight_analyzed = None
        self.cue.offset = 0.0
        self.cue.finish = None
        self.live_trace.Reset()
        self.reInitWave = True

    def HandleStreamFailure(self):
        # a station that did not open: said in the status line, the player stopped (the
        # next row is often another station that the same network keeps from opening)
        error = self.AudioControl.stream_error
        # kept for the header and the waveform until another track plays
        self.stream_failure = (self.cue.path, error)
        status = getattr(self.parent, 'StatusBox', None)
        if status is not None and error is not None:
            status.alarm = 'Not played: %s (BASS error %s)' % (radio.ERRORS.get(error, 'error'),
                                                               error)
            status.alarm_color = 'red'
        self.AudioControl.failed = False
        self.OnPause(endoflist=True)

    def AudioEvent(self, event):
        ctime = time.time()
        if ctime - self.last_control_time < 0.05:
            return
        self.last_control_time = ctime
        if self.cue.path is None:
            return
        self.PrefetchAnalysis()
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

        if self.IsStreamTrack():
            # no analysis, no end, no fades, no jumps: only a failed opening to tell
            if self.AudioControl.failed:
                self.HandleStreamFailure()
            return

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
        self.cue.highlight_analyzed = None
        self.cue.fffr_static = 15.0
        self.cue.fffr_variable = 15.0
        self.cue.mdx = self.GetMDX(self.cue.path)
        self.cue.grid = None
        self.cue.edit_skip = False
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

    def PrefetchAnalysis(self):
        # the song's analysis read, and its whole waveform painted (PlayBoxWave.PaintAhead),
        # on a thread while the stream opens: read and painted after it, a long mix's
        # waveform came a second after its sound (the user)
        if self.pending.dbresp is False or self.IsStreamTrack():
            return
        prefetch = getattr(self, 'prefetch', None)
        if prefetch is not None and prefetch.path == self.cue.path:
            return
        prefetch = self.prefetch = Struct(path=self.cue.path, mdx=None, resp=None, done=False,
                                          used=False)

        def load():
            try:
                prefetch.mdx = audio.makemdx(prefetch.path)
                prefetch.resp = mfeats.getby_key_value('mdx', prefetch.mdx)
            except Exception:
                prefetch.resp = None
            prefetch.done = True
            if prefetch.resp is not None and self.prefetch is prefetch:
                self.Wave.PaintAhead(prefetch.resp.waveform)

        threading.Thread(target=load, name='prefetch', daemon=True).start()

    def SetAudioEventWithDBRESP(self):
        # if self.parent.MFEATS.IsPathTasking(self.cue.path):
        #   return
        # the prefetched (PrefetchAnalysis) the first time, waited for while it is read
        prefetch = getattr(self, 'prefetch', None)
        if prefetch is not None and prefetch.path == self.cue.path\
                and prefetch.mdx in (None, self.cue.mdx) and not prefetch.used:
            if prefetch.done is False:
                return
            prefetch.used = True
            self.pending.dbresp_lap = time.time()
            resp = prefetch.resp
        else:
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
        # the length first: the highlight's place is chosen for its length; on the grid
        # if the song has one. The waveform before the place: chosen without it, it was the
        # phrase nearest the analysis' start, and a length change moved it to the chosen one
        self.LoadGridNow()
        self.SetWaveImage(resp.waveform)
        self.SetBestHighlightVariablePeriodTime()
        self.SetHighlightOffsetTime(resp.highlight[0])
        self.SkipLeadingSilence()
        if resp.version != mfeats.MFEATS_VERSION:
            # analyzed before the current waveform: analyze again for it
            self.parent.MFEATS.AddMFEATSTask(self.cue.path, urgent=True, forced=True)
            self.pending.wave = time.time()
            self.pending.wave_since = time.time()
        if self.IsHighlightOn():
            self.SetTrackTimeWithHighlight()
            # gone to already with the early highlight, unless the grid moved it (the
            # range drawn and the one played were apart)
            if self.pending.early is False or self.IsOutsideHighlight():
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
        # the length first: the highlight's place is chosen for its length; on the grid
        # if the song has one. The waveform before the place: chosen without it, it was the
        # phrase nearest the analysis' start, and a length change moved it to the chosen one
        self.LoadGridNow()
        self.SetWaveImage(resp.waveform)
        self.SetBestHighlightVariablePeriodTime()
        self.SetHighlightOffsetTime(resp.highlight[0])
        self.SkipLeadingSilence()
        if self.IsHighlightOn():
            self.SetTrackTimeWithHighlight()
            if self.IsOutsideHighlight():
                self.GotoTrackOffsetTime()
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
        if self.LoadGridNow():
            self.ApplyGridToTimes()
            self.SkipLeadingSilence()
            self.Wave.reInitBuffer = True
            self.WaveDetail.reInitBuffer = True

    def LoadGridNow(self):
        # the song's grid if it is in (True): read with the analysis' values too, so the
        # highlight is placed once on the grid and not moved under the play a second later
        if self.pending.grid is False or self.pending.mdx or self.cue.mdx is None:
            return False
        grid = mfeats.get_grid(self.cue.mdx)
        if grid is None or grid.version != mfeats.GRID_VERSION:
            return False
        self.pending.grid = False
        self.cue.grid = mfeats.apply_grid_scale(grid) if grid.bpm > 0 else None
        self.SetBestFFFRVariableTime()
        return True

    def ApplyGridToTimes(self):
        # the highlight on a bar and the jumps in bars, once the grid is in (where it
        # plays is not moved)
        if self.GetGrid() is None:
            return
        self.SetBestFFFRVariableTime()
        offset = getattr(self.cue, 'highlight_analyzed', None) or self.GetHighlightOffsetTime()
        if offset is None or self.cue.highlight_variable is None:
            return
        self.SetBestHighlightVariablePeriodTime()
        self.SetHighlightOffsetTime(offset, analyzed=False)
        if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            before = self.GetTrackOffsetTime()
            offset = self.GetHighlightOffsetTime()
            finish = offset + self.GetHighlightVariablePeriodTime()
            self.SetTrackOffsetTime(offset)
            self.SetTrackFinishTime(finish)
            # the highlight moved while it plays: played from its new start, or a place
            # past its new end ended the song at once and one before it played outside it
            position = self.GetPositionTime()
            if before is None or abs(offset - before) > 0.01:
                # outside the new range, or still at the old start (the highlight is
                # played from where it is drawn)
                started = before is not None and 0.0 <= position - before < 5.0
                if started or position < offset - 0.5 or position >= finish:
                    self.GotoTrackOffsetTime()
        self.reInitWave = True

    def GetTempoRate(self):
        return self.tempo_rate

    def GetTempoStep(self):
        # the range's step in percent
        return TEMPO_STEPS.get(self.tempo_range, 0.05)

    def SetTempoRate(self, rate):
        # on the range's steps, within it
        limit = self.tempo_range / 100.0
        least = TEMPO_LEAST_RATE if self.tempo_keylock else 0.0
        rate = min(max(rate, 1.0 - limit, least), 1.0 + limit)
        step = self.GetTempoStep()
        rate = 1.0 + round(round((rate - 1.0) * 100.0 / step) * step, 2) / 100.0
        if abs(rate - self.tempo_rate) < 1e-6:
            return
        self.tempo_rate = rate
        self.AudioControl.SetTempo()
        self.Info.reInitBuffer = True
        self.OnTempoMoved('tempo')

    def SetTempoRateExact(self, rate):
        '''a rate as it is (DECK SYNC's: off the range's steps, a tempo to the hundredth),
        the range widened when it is past it'''
        rate = max(rate, TEMPO_LEAST_RATE if self.tempo_keylock else 0.01)
        percent = abs(rate - 1.0) * 100.0
        if percent > self.tempo_range:
            wider = [r for r in TEMPO_RANGES if r >= percent]
            if wider:
                self.tempo_range = wider[0]
                SetPreference('tempo_range', self.tempo_range)
        if abs(rate - self.tempo_rate) < 1e-9:
            return
        self.tempo_rate = rate
        self.AudioControl.SetTempo()
        self.Info.reInitBuffer = True
        self.OnTempoMoved('tempo')

    def IsTempoKeyLockOn(self):
        return self.tempo_keylock

    def SetTempoKeyLock(self, on):
        self.tempo_keylock = on
        SetPreference('tempo_keylock', on)
        # locked: no lower than the tempo stream goes (WIDE's -100% to -95%)
        self.SetTempoRate(self.tempo_rate)
        self.AudioControl.SetTempo()

    def IsTempoKeyLockWanted(self):
        # the tempo stream only when it changes something: the tempo with its key kept,
        # or the key moved
        return (self.tempo_keylock and abs(self.tempo_rate - 1.0) > 1e-6)\
            or self.tempo_semitones != 0

    def GetTempoSemitones(self):
        return self.tempo_semitones

    def SetTempoSemitones(self, semitones):
        semitones = int(min(max(semitones, -TEMPO_SEMITONES), TEMPO_SEMITONES))
        if semitones == self.tempo_semitones:
            return
        self.tempo_semitones = semitones
        self.AudioControl.SetTempo()
        self.Info.reInitBuffer = True
        self.OnTempoMoved('key')

    def GetPlayingKey(self):
        # the key heard: moved by the semitones, and with the rate when the pitch goes with it
        shift = self.tempo_semitones
        if self.tempo_keylock is False:
            # (stopped at WIDE's -100%: no key heard)
            if self.tempo_rate <= 0.0:
                return '-'
            shift += 12.0 * math.log2(self.tempo_rate)
        shift = int(round(shift))
        if shift == 0:
            return self.cue.key
        return mfeats.transpose_chord(self.cue.key, shift)

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
        # one saved with the player's state by an older version is not taken, nor one
        # read before the table had all its columns (the app did not start)
        if grid is None or grid.mdx != self.cue.mdx\
                or getattr(grid, 'version', None) != mfeats.GRID_VERSION\
                or any(hasattr(grid, key) is False for key, _ in mfeats.GRID_DEFINITION):
            return None
        return grid

    def IsGridShown(self):
        # View > Beat Grid
        return self.parent.parent.IsBeatGridShowOn()

    def GetGridDownbeat(self):
        grid = self.GetGrid()
        period = 60.0 / grid.bpm
        return (grid.downbeat + (grid.shift or 0) * period) % (period * 4)

    def IsGridPhraseKnown(self):
        # the phrase drawn and used when the analysis was sure of it, or the user set it
        grid = self.GetGrid()
        return bool(grid.phrase_set) or (grid.phrase_margin or 0.0) >= mfeats.PHRASE_SURE

    def GetGridPhraseBars(self):
        # bars from the (moved) downbeat to the first phrase's start
        grid = self.GetGrid()
        return ((grid.phrase or 0) + (grid.phrase_shift or 0)) % 4

    def GetGridPhraseStart(self):
        return mfeats.get_phrase_start(self.GetGrid())

    # a click or a drag on the waveforms lands on the grid: (mode, label, beats)
    SNAP_MODES = (('off', 'Off', 0), ('beat', 'Beat', 1), ('bar', 'Bar', 4),
                  ('phrase', '4 bars', 16))

    def GetSnapMode(self):
        # read once and kept (GetPreference opens the settings' file each time)
        if getattr(self, 'snap_mode', None) is None:
            mode = GetPreference('wave_snap')
            self.snap_mode = mode if mode in [v[0] for v in self.SNAP_MODES] else 'off'
        return self.snap_mode

    def SetSnapMode(self, mode):
        self.snap_mode = mode
        SetPreference('wave_snap', mode)
        if mode != 'off':
            self.snap_unit = mode
            SetPreference('wave_snap_unit', mode)

    def GetSnapUnit(self):
        # what SNAP snaps to when on: the mode, else the last one it was (bar at first)
        if self.GetSnapMode() != 'off':
            return self.GetSnapMode()
        if getattr(self, 'snap_unit', None) is None:
            unit = GetPreference('wave_snap_unit')
            self.snap_unit = unit if unit in [v[0] for v in self.SNAP_MODES[1:]] else 'bar'
        return self.snap_unit

    def ToggleSnap(self):
        self.SetSnapMode('off' if self.GetSnapMode() != 'off' else self.GetSnapUnit())

    def GetSnappedTime(self, seconds):
        # seconds on the nearest beat, bar or 4 bars (a phrase's start when it is known,
        # else counted from the downbeat); as they are with snap off, without a grid, or
        # for a station
        beats = dict((v[0], v[2]) for v in self.SNAP_MODES).get(self.GetSnapMode(), 0)
        grid = self.GetGrid()
        if beats == 0 or grid is None or self.IsStreamTrack():
            return seconds
        period = 60.0 / grid.bpm
        unit = period * beats
        anchor = self.GetGridDownbeat()
        if beats == 16 and self.IsGridPhraseKnown():
            anchor = self.GetGridPhraseStart()
        snapped = anchor + round((seconds - anchor) / unit) * unit
        duration = self.GetDurationTime()
        while snapped < 0:
            snapped += unit
        while duration > 0 and snapped >= duration:
            snapped -= unit
        snapped = max(snapped, 0.0)
        # the line it caught, lit a moment on the waveforms (GetSnapFlash)
        self.snap_flash = (snapped, time.time())
        return snapped

    # a snapped seek's line lit this long, fading
    SNAP_FLASH_SECONDS = 0.45

    def GetSnapFlash(self):
        '''(seconds, share) of the line a seek snapped to while it is lit (share 1 to 0 as
        it fades), None after'''
        flash = getattr(self, 'snap_flash', None)
        if flash is None:
            return None
        share = 1.0 - (time.time() - flash[1]) / self.SNAP_FLASH_SECONDS
        if share <= 0:
            self.snap_flash = None
            return None
        return flash[0], share

    def GetGridLines(self, start, end):
        '''[(seconds, level)] of the grid's beats from start to end; level 0 a beat, 1 a
        bar's first, 2 a phrase's (4 bars)'''
        grid = self.GetGrid()
        if grid is None or end <= start or self.IsGridShown() is False:
            return []
        period = 60.0 / grid.bpm
        downbeat = self.GetGridDownbeat()
        phrase = self.GetGridPhraseBars() * 4
        first = int(math.ceil((start - downbeat) / period))
        last = int(math.floor((end - downbeat) / period))
        known = self.IsGridPhraseKnown()
        return [(downbeat + k * period,
                 2 if known and (k - phrase) % 16 == 0 else 1 if k % 4 == 0 else 0)
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

    def SetGridScale(self, factor):
        # the tempo doubled or halved (a song analyzed at half or twice its tempo), or back
        # to the analysis' (factor None)
        grid = self.GetGrid()
        if grid is None:
            return
        scale = 1.0 if factor is None else (grid.bpm_scale or 1.0) * factor
        scale = min(max(scale, 0.25), 4.0)
        mfeats.set_grid_scale(grid.mdx, scale)
        stored = mfeats.get_grid(grid.mdx)
        self.cue.grid = mfeats.apply_grid_scale(stored) if stored is not None else None
        self.ApplyGridToTimes()
        self.Wave.reInitBuffer = True
        self.WaveDetail.reInitBuffer = True
        self.Info.reInitBuffer = True

    def SetGridPhraseShift(self, shift, set_by_user=True):
        grid = self.GetGrid()
        if grid is None:
            return
        grid.phrase_shift = shift % 4
        grid.phrase_set = 1 if set_by_user else 0
        mfeats.set_grid_shift(grid.mdx, grid.phrase_shift, key='phrase_shift',
                              phrase_set=grid.phrase_set)
        self.ApplyGridToTimes()
        self.Wave.reInitBuffer = True
        self.WaveDetail.reInitBuffer = True

    def SetGridPhraseAt(self, seconds):
        # the phrase from the bar nearest seconds
        grid = self.GetGrid()
        if grid is None:
            return
        bar = int(round((seconds - self.GetGridDownbeat()) / (60.0 / grid.bpm * 4)))
        self.SetGridPhraseShift(bar - (grid.phrase or 0))

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
            self.LoadGridNow()
            self.SetHighlightOffsetTime(wave.highlight[0])
            # its length in beats of the tempo before its octave: half a beat at most
            # from the one to come (the tempo itself is not shown before it)
            value = self.GetHighlightLength(self.cue.highlight_static, wave.tempo)
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

    def ChangeHighlightLength(self, static, turn_on=False):
        # a new length from the keys or the menu: it plays on where it is when that is still
        # in the highlight (it jumped to the start every time, and the start can move with
        # the length near the song's end); turn_on: the keys turn the highlight on too
        was_on = self.IsHighlightOn()
        self.SetBestHighlightVariablePeriodTime(static=static)
        if was_on is False:
            if turn_on:
                self.SetHighlightOn()
                self.GotoTrackOffsetTime()
        elif self.IsHighlightSkipOn() or self.IsOutsideHighlight():
            self.GotoTrackOffsetTime()
        self.reInitWave = True
        self.OnSize()

    def IsOutsideHighlight(self):
        # where it plays is not in the highlight's range (it moved after the play began)
        offset, finish = self.GetTrackTime()
        if offset is None or finish is None:
            return False
        position = self.GetPositionTime()
        return position < offset - 0.5 or position >= finish

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
        if self.IsRadioEditActive():
            edit = self.GetRadioEdit()
            return (edit[0], edit[1])
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
        # the sound's start, or the edit's (its intro skipped), when it plays before it
        self.ApplyRadioEdit()
        if self.IsSkipSilenceOn() is False and self.IsRadioEditActive() is False:
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

    # LOOP's modes, a press the next (a player's repeat: off, the list, the song): the song
    # again at its end (IsLoopOn, the one it was), or the list's first after its last
    LOOP_MODES = ('off', 'list', 'one')

    def IsLoopOn(self):
        return self.cue.loop_on

    def SetLoopOn(self):
        self.SetLoopMode('one')

    def SetLoopOff(self):
        self.SetLoopMode('off')

    def IsLoopListOn(self):
        # (a cue kept from before the list's mode: none)
        return getattr(self.cue, 'loop_list', False) and not self.cue.loop_on

    def GetLoopMode(self):
        return 'one' if self.cue.loop_on else 'list' if self.IsLoopListOn() else 'off'

    def SetLoopMode(self, mode):
        self.cue.loop_on = mode == 'one'
        self.cue.loop_list = mode == 'list'

    def CycleLoop(self):
        modes = self.LOOP_MODES
        self.SetLoopMode(modes[(modes.index(self.GetLoopMode()) + 1) % len(modes)])

    def IsLoudOn(self):
        return getattr(self.cue, 'loud_on', True)

    def SetLoudOn(self):
        self.cue.loud_on = True
        self.UpdateVSTBypass()

    def SetLoudOff(self):
        self.cue.loud_on = False
        # a kept A/B would play the original once MASTER is on again
        if master.METERS.IsCompared():
            master.METERS.SetCompared(False)
        self.UpdateVSTBypass()

    def UpdateVSTBypass(self):
        # (MASTER's header told at once, its power key and its state: stopped, nothing
        # draws it at the next frame)
        master = getattr(self, 'Master', None)
        if master is not None:
            master.reInitBuffer = True
        if hasattr(self, 'AudioControl') is False:
            return
        self.AudioControl.SetVSTBypass()

    # SHORT (the radio edit): a DJ track played short, as its radio edit would be (choose_radio_edit):
    # its intro and outro skipped, its long breakdowns cut on the grid. a mode kept from
    # track to track, HIGHLIGHT's alternative (one turns the other off)
    def IsRadioEditOn(self):
        return self.radio_edit

    def SetRadioEdit(self, on):
        self.radio_edit = bool(on)
        SetPreference('radio_edit', self.radio_edit)
        if self.radio_edit and self.IsHighlightOn():
            self.SetHighlightOff()
        self.cue.edit_skip = False
        self.ApplyRadioEdit(goto=True)

    # SHORT's lengths (radio_edit_length): the edit as found (0), or about so many seconds
    # (the edit's own jumps, its start and end brought in to a part's, the highlight held:
    # mfeats.window_edit)
    RADIO_EDIT_LENGTHS = ((0, 'Edit (intro, outro, breakdowns)'), (180, 'About 3 min'),
                          (120, 'About 2 min'))

    def GetRadioEditLength(self):
        # read once and kept (asked many times a frame: the settings' file opened each time
        # held the window still)
        if getattr(self, 'radio_edit_length', None) is None:
            length = GetPreference('radio_edit_length')
            self.radio_edit_length = length if length in [
                v[0] for v in self.RADIO_EDIT_LENGTHS] else 0
        return self.radio_edit_length

    def SetRadioEditLength(self, length):
        self.radio_edit_length = length
        SetPreference('radio_edit_length', length)
        # Option > Short Length's check with it (set from the mode key's menu too)
        for item, value in getattr(getattr(self.parent.parent, 'MenuBar', None),
                                   'shortLengthItems', ()):
            item.Check(value == length)
        self.cue.edit_skip = False
        # (now in a part it cuts: on to the next it plays, as when it is turned on)
        self.ApplyRadioEdit(goto=True)

    def GetRadioEdit(self):
        '''(start, end, cuts) of the playing song's edit, None without one (no grid or
        waveform yet, a station, no main part found)'''
        grid = self.GetGrid()
        waveform = self.cue.waveform
        if grid is None or waveform is None or self.IsStreamTrack():
            return None
        duration = self.GetDurationTime()
        # the highlight played whole in it (it was left out of most: the user)
        offset, length = self.GetHighlightTime()
        keep = (offset, offset + length) if offset is not None and length else None
        key = (self.cue.mdx, grid.bpm, self.GetGridPhraseStart(), len(waveform), duration,
               self.GetRadioEditLength(), keep)
        if self.radio_edit_cache is None or self.radio_edit_cache[0] != key:
            COUNTS['radio_edit'] += 1
            COUNTS['radio_edit_key'] = hash(key) % 1000
            plan = mfeats.choose_radio_edit(waveform, duration, grid.bpm, key[2],
                                            target=key[5] or None, keep=keep)
            self.radio_edit_cache = (key, plan)
        return self.radio_edit_cache[1]

    def IsRadioEditActive(self):
        # played as its edit now: on, the song's edit known, not left by a seek out of it
        return self.radio_edit and self.IsHighlightOn() is False\
            and self.cue.edit_skip is False and self.GetRadioEdit() is not None

    def GetPlayedRanges(self):
        '''[(start, end), ...] seconds the highlight or SHORT plays now ([] neither): the
        waveforms' grid lanes tinted over them (told apart from the dimmed by the wave alone
        too faintly)'''
        if self.IsHighlightKnown() and self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
            offset, period = self.GetHighlightTime()
            if offset is None or period is None:
                return []
            return [(offset, self.GetDurationTime() if period == 0 else offset + period)]
        if self.IsRadioEditActive():
            start, end, cuts = self.GetRadioEdit()
            bounds = [start] + [v for cut in cuts for v in cut] + [end]
            return list(zip(bounds[0::2], bounds[1::2]))
        return []

    def ApplyRadioEdit(self, goto=False):
        # the edit's range as the track's and its cuts as the stream's jumps (or the whole
        # sound and none); goto: from its start when it plays before it (the intro)
        edit = self.GetRadioEdit() if self.IsRadioEditActive() else None
        self.AudioControl.SetJumps(self.cue.path, edit[2] if edit else [])
        if self.IsHighlightOn():
            return
        self.SetSoundTrackTime()
        if edit is not None and goto:
            # turned on where it does not play: on to the next part it plays (in the intro
            # its start; in a cut, where the cut ends: it played the cut through before)
            position = self.GetPositionTime()
            if position < edit[0] - 0.5:
                self.SetPositionTime(edit[0])
            else:
                for begin, end in edit[2]:
                    if begin <= position < end:
                        self.SetPositionTime(end)
                        break
        self.reInitWave = True

    def LeaveRadioEdit(self, position):
        # a seek out of the edit (into its intro or outro): the whole song for this play
        if self.IsRadioEditActive() is False:
            return
        edit = self.GetRadioEdit()
        if position < edit[0] - 0.5 or position >= edit[1]:
            self.cue.edit_skip = True
            self.ApplyRadioEdit()

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
        if self.radio_edit:
            self.radio_edit = False
            SetPreference('radio_edit', False)
        if getattr(self, 'AudioControl', None) is not None:
            self.AudioControl.SetJumps(self.cue.path, [])

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

    def GetHighlightTempo(self, tempo):
        # the tempo the highlight is counted in: the grid's when there is one, doubled at 95
        # BPM and under as the author's analysis does (mfeats_single's xtempo)
        grid = self.GetGrid()
        if grid is not None:
            tempo = float(grid.bpm)
        try:
            tempo = float(tempo)
        except (TypeError, ValueError):
            return 0.0
        return tempo * 2.0 if 0 < tempo <= 95 else tempo

    def GetHighlightLength(self, static, tempo):
        # the menu's length: its bars (seconds / 2, the bars of a song at 120 BPM, as the
        # menu names them), whole bars at the song's tempo; seconds without a tempo
        tempo = self.GetHighlightTempo(tempo)
        if tempo <= 0:
            return static
        bars = max(1, int(round(static / 2.0)))
        return bars * 4 * 60.0 / tempo

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

    def SetHighlightOffsetTime(self, offset, analyzed=True):
        # with a grid, on a phrase's start (4 bars): of the phrases nearest the analysis'
        # start, the one loudest over the highlight. analyzed: offset is the analysis'
        # own, kept so a later move is made from it, not from where it was moved to
        if analyzed:
            self.cue.highlight_analyzed = offset
        grid = self.GetGrid()
        if grid is not None and offset is not None:
            offset = self.GetPhraseHighlightStart(offset)
        elif offset is not None:
            # no grid: the analysis' start, pulled back when the length runs past the end
            offset = self.GetFittedHighlightStart(offset)
        self.cue.highlight_offset = offset

    def GetPhraseHighlightStart(self, offset, keep=None):
        # the whole song's phrases weighed (mfeats.choose_phrase_highlight); without the
        # waveform yet, the phrase nearest the analysis' start
        grid = self.GetGrid()
        period = 60.0 / grid.bpm
        phrase = period * 16
        start = self.GetGridPhraseStart()
        nearest = start + round((offset - start) / phrase) * phrase
        if nearest < 0:
            nearest += phrase
        duration = self.GetDurationTime()
        waveform = self.cue.waveform
        if audio.is_waveform_3band(waveform) is False or duration <= 0:
            return self.GetFittedHighlightStart(nearest)
        # placed as the author placed it, for 64 beats (mfeats_single's highlight) whatever
        # the length played from it: a shorter one is that section's beginning
        tempo = self.GetHighlightTempo(grid.bpm)
        choose = 64 * 60.0 / tempo
        # a phrase not known: any bar may start it
        step = period * 16 if self.IsGridPhraseKnown() else period * 4
        # (kept for the same waveform and grid: a song opened chose it up to four times, the
        # early waveform, the analysis, the grid, each on the GUI thread)
        key = (self.cue.mdx, duration, grid.bpm, start, choose, step)
        cache = getattr(self, 'phrase_highlight_cache', None)
        if cache is not None and cache[0] == key and cache[1] is waveform:
            chosen = cache[2]
        else:
            chosen, _ = mfeats.choose_phrase_highlight(waveform, duration, grid.bpm, start,
                                                       choose, step)
            if chosen is not None:
                # on the drop, not the drum fill a bar before it
                chosen = mfeats.refine_highlight_start(waveform, duration, grid.bpm, chosen)
            self.phrase_highlight_cache = (key, waveform, chosen)
        if chosen is None:
            return self.KeepHighlightStart(self.GetFittedHighlightStart(nearest), keep)
        length = self.cue.highlight_variable or choose
        if length <= choose + 1e-6:
            return self.KeepHighlightStart(self.GetFittedHighlightStart(chosen), keep)
        # a longer one holds those 64 beats and grows, in steps from their start, to the
        # side with the fewest calm bars (a breakdown, the outro), then the side the author's
        # measure likes; never past the song's end
        earliest = max(chosen + choose - length, 0.0)
        latest = min(chosen, duration - length)
        longer = mfeats.choose_long_highlight(waveform, duration, grid.bpm, chosen, length,
                                              step, earliest, latest)
        chosen = self.GetFittedHighlightStart(chosen if longer is None else longer)
        return self.KeepHighlightStart(chosen, keep)

    def KeepHighlightStart(self, start, keep):
        # keep: where it plays, in the highlight before the length changed; the start placed
        # when it holds that place, else the one it had (fitted in the song) so the play is
        # not moved, else the placed one (the play goes to it)
        if keep is None:
            return start
        length = self.cue.highlight_variable or 0.0
        if start <= keep < start + length:
            return start
        kept = self.GetFittedHighlightStart(self.cue.highlight_offset)
        if kept <= keep < kept + length:
            return kept
        return start

    def GetFittedHighlightStart(self, offset):
        # the start kept when the highlight fits before the song's end, else the last step
        # it fits after (phrase, or bar), or the song's start when none does
        length = self.cue.highlight_variable or 0.0
        duration = self.GetDurationTime()
        if offset + length <= duration + 1e-6:
            return offset
        grid = self.GetGrid()
        if grid is None:
            return max(0.0, duration - length)
        period = 60.0 / grid.bpm
        step = period * 16 if self.IsGridPhraseKnown() else period * 4
        first = self.GetGridPhraseStart() % step
        steps = math.floor((duration - length - first) / step + 1e-9)
        return first + steps * step if steps >= 0 else 0.0

    def SetBestHighlightVariablePeriodTime(self, static=None, tempo=None):
        if tempo is not None:
            self.cue.tempo = tempo
        else:
            tempo = self.cue.tempo
        if static is not None:
            self.cue.highlight_static = static
        else:
            static = self.cue.highlight_static
        value = self.GetHighlightLength(static, tempo)
        duration = self.GetDurationTime()
        if value > duration:
            value = duration
        changed = static is not None and value != self.cue.highlight_variable
        self.cue.highlight_variable = value
        # a length the user chose: placed again for it (GetPhraseHighlightStart), with where
        # it plays kept in it when it can be (it moved off and the play jumped); the range
        # played with it (only the drawn one followed, and the old end was played)
        if changed and self.cue.highlight_offset is not None:
            analyzed = getattr(self.cue, 'highlight_analyzed', None)
            if self.GetGrid() is not None and analyzed is not None:
                keep = None
                if self.IsHighlightOn() and self.IsOutsideHighlight() is False:
                    keep = self.GetPositionTime()
                self.cue.highlight_offset = self.GetPhraseHighlightStart(analyzed, keep)
            else:
                self.cue.highlight_offset = self.GetFittedHighlightStart(
                    self.cue.highlight_offset)
            if self.IsHighlightOn() and self.IsHighlightSkipOn() is False:
                offset = self.GetHighlightOffsetTime()
                self.SetTrackOffsetTime(offset)
                self.SetTrackFinishTime(offset + value)

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

    def IsVisualPlaying(self):
        # what the meters, ANALYZER and the visuals read sounds
        return self.IsPlaying()

    def GetVisualStream(self):
        # (stream, channels, autogain) the spectrum, the vectorscope, ANALYZER and OUT
        # read
        return self.cue.hStream, self.cue.channel, self.cue.autogain

    def GetStreamFailure(self):
        # why the station playing did not open ('' when it did, or it is no station)
        failure = getattr(self, 'stream_failure', None)
        if failure is None or failure[0] != self.cue.path or self.IsStreamTrack() is False:
            return ''
        return radio.ERRORS.get(failure[1], 'an unknown error')

    def GetStreamConnecting(self):
        # the seconds a station has been connecting for, None when it is not (nor while the
        # player is being made: no AudioControl yet)
        control = getattr(self, 'AudioControl', None)
        since = control.connecting if control is not None else None
        if since is None or self.IsStreamTrack() is False:
            return None
        if self.AudioControl.path != self.cue.path:
            return None
        return time.time() - since

    def IsStreamWaiting(self):
        '''a station not sounding yet: connecting, opened and being started, or its buffer
        filling (stalled); the list's turning ring till it plays (the ring, the stopped
        square and the playing mark in turns before)'''
        control = getattr(self, 'AudioControl', None)
        if control is None or self.IsStreamTrack() is False:
            return False
        if self.GetStreamConnecting() is not None:
            return True
        if control.path != self.cue.path or control.failed:
            return False
        return control.pending\
            or pybass.BASS_ChannelIsActive(self.cue.hStream) == pybass.BASS_ACTIVE_STALLED

    def IsStreamTrack(self):
        # the cue is an internet radio station's row (its path the stream's address)
        return audio.is_stream_path(self.cue.path)

    def GetLiveTrace(self):
        # a station's last seconds as waveform columns for the waveform boxes; None for a
        # file (its waveform is the analysis')
        if self.IsStreamTrack() is False:
            return None
        return self.live_trace.Get(self.cue.hStream, self.IsPlaying())

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
        self.stream_failure = None
        self.parent.ListBox.List.pending.SkipStopIcon = True
        audio.set_volume(self.cue.hStream, 0.0)
        self.AudioControl.resume = 0.0
        self.pending.dbresp = True
        self.pending.dbresp_lap = 0.0
        self.pending.early = False
        self.pending.mdx = True
        self.pending.mfeats = True
        self.pending.wave = False
        # (the same song again read again)
        self.prefetch = None
        self.SetHighlightSkipOff()
        self.SetTrackOffsetTime(0.0)
        if self.IsStreamTrack():
            self.SetStreamCue()
        self.parent.ListBox.List.pending.SkipStopIcon = True
        self.parent.ListTab.reInitBuffer = True
        self.parent.ListBox.List.reInitBuffer = True

    def OnStop(self):
        audio.stop(self.cue.hStream)

    def OnPause(self, endoflist=False):
        self.cue.resume = audio.stop(self.cue.hStream)
        if endoflist or self.cue.resume == -1.0:
            self.cue.resume = self.GetTrackFinishTime()
        if self.cue.resume is None:
            # a station has no end to stand at (None there failed every event after)
            self.cue.resume = 0.0
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
        count = len(self.parent.ListBox.innerList[listIdx].items)
        if self.IsLoopListOn() and count:
            # the list looped: its first after its last, its last before its first
            targetItemIdx %= count
        if targetItemIdx == -1:
            return None
        if targetItemIdx >= count:
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
