# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import ctypes
import images
import io
import math
import mutagen
import numpy
import os
import mfeats
import playboxlib
import radio
import threading
import time
import instruments
import uikit
import wx

from PIL import Image
from macroboxlib import FONT_PLAYINFO
from macroboxlib import GetPreference
from macroboxlib import SetPreference
from macroboxlib import PaintUnpainted
from macroboxlib import RectBox
from analyzerbox import AnalyzerPanel
from masterbox import MasterPanel
from instrumentsbox import InstrumentsPanel
from mixerbox import MixerPanel
from pianorollbox import PianoRollPanel
from rackbox import Rack
from rackbox import RackBar
from playboxlib import AudioControl
from playboxlib import PlayBoxControl
from playboxlib import PlayBoxDnD
from playboxlib import SCRATCH_PIXELS_PER_SECOND
from utilities import Struct
# from playboxlib import *  # noqa


SEPARATOR = ' | '


class PlayBox(RectBox, PlayBoxControl):

    def __init__(self, parent):
        PlayBoxControl.__init__(self, parent)
        RectBox.__init__(self, parent)
        self.parent = parent
        self.st = parent.parent.st.PLAYBOX

        self.wave_x = 220
        self.wave_height = 40
        self.show_apic = True
        self.apic_size = 150
        self.wave_max = True
        self.button_size = 17
        self.cursor_stroke = 4
        self.cache.timestamp = time.time()
        self.cache.framemove = None
        self.cache.oneshotkey = False
        color = self.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.Wave = PlayBoxWave(self)
        self.WaveDetail = PlayBoxWaveDetail(self)
        self.Info = PlayBoxInfo(self)
        # self.InfoR = PlayBoxInfoR(self)
        self.Title = PlayBoxTitle(self)
        self.Spectrum = PlayBoxSpectrum(self)
        self.VectorScope = PlayBoxVectorScope(self)
        self.Apic = PlayBoxApic(self)
        self.VisualClock = PlayBoxVisualClock(self)
        self.ControlButton = PlayBoxControlButton(self)
        self.VolumeSlider = VolumeSlider(self)
        self.TempoButton = TempoButton(self)
        self.KeyButton = KeyButton(self)
        self.TempoStrip = TempoStrip(self)
        self.SnapButton = SnapButton(self)
        # the rack over the header: its bar at the top (a key for each module), under it
        # MASTER's module and ANALYZER's (the bar's arrows; ANALYZER also from the View
        # menu, or a click on the header's spectrum or scope)
        self.Master = MasterPanel(self)
        self.Analyzer = AnalyzerPanel(self)
        self.Instruments = InstrumentsPanel(self)
        self.Mixer = MixerPanel(self)
        self.PianoRoll = PianoRollPanel(self)
        self.Rack = Rack(self, [self.Analyzer, self.Master, self.Mixer, self.Instruments,
                                self.PianoRoll])
        self.RackBar = RackBar(self)
        # the header's visualizers in ANALYZER's BARS part: its children, its drawing
        # leaving them out
        self.Spectrum.Reparent(self.Analyzer)
        self.VectorScope.Reparent(self.Analyzer)
        self.Analyzer.SetWindowStyleFlag(self.Analyzer.GetWindowStyleFlag() | wx.CLIP_CHILDREN)
        self.AudioControl = AudioControl(self)
        self.InitBuffer()

    def IsSideWideEnough(self):
        w, _ = self.GetSize()
        if w >= 840:
            return True
        return False

    # the header (cover, title, info, spectrum and scope; one line without the spectrum)
    # above the control row, the waveforms at the bottom: the box's height as before
    # 13 px under the info's cells to the waveforms' frame, as over the cover and the title
    # from the rack (92: 26 under, measured)
    # (the waveforms' frame 8 px under the cover and the info's cells, as the rack 8 over
    # them: 13, then 10 before)
    HEADER_HEIGHT = 57
    HEADER_COMPACT = 33
    CONTROL_HEIGHT = 33

    # the info's cells a row more each when the title's width does not hold them (the
    # header as much taller); none let go
    # (a row of the info's cells and the 5 px under it: PlayBoxInfo.CELL_SLOT)
    INFO_ROW = 24

    def GetHeaderHeight(self):
        if self.parent.parent.IsPlayerTopShowOn():
            return self.HEADER_HEIGHT + self.GetHeaderExtra()
        return self.HEADER_COMPACT

    def GetHeaderExtra(self):
        if self.parent.parent.IsPlayerTopShowOn() is False:
            return 0
        return (getattr(self, 'header_rows', 1) - 1) * self.INFO_ROW

    def CheckHeaderRows(self):
        # the info's rows at this width: a change lays the window out again (the player's
        # height is the main panel's to give)
        info, title = getattr(self, 'Info', None), getattr(self, 'Title', None)
        if info is None or title is None or self.parent.parent.IsPlayerTopShowOn() is False:
            return
        # counted as with the tempo strip at its widest (both its faders): the header's
        # height kept when TEMPO or KEY shows or hides them
        # the cover as tall as the info's rows (PlayBoxApic.GetCoverSize): wider with more
        # of them, the text's room counted again for its size till the rows stay
        right = title.GetTextRight() - self.GetStripSlack()
        side = self.parent.parent.IsPlayerSideShowOn()
        rows = 1
        for _ in range(3):
            left = 8 + (PlayBoxApic.GetCoverSize(rows) + PlayBoxApic.GAP if side else 0)
            counted = info.GetRowCount(right - left)
            if counted <= rows:
                break
            rows = counted
        if rows == getattr(self, 'header_rows', 1):
            return
        self.header_rows = rows
        wx.CallAfter(self.RelayoutHeader)

    def RelayoutHeader(self):
        frame = self.parent.parent
        if frame.IsPlayerOnlyModeOn():
            frame.SetPlayerOnlyHeight()
        self.parent.OnSize()
        self.OnSize()

    # top to bottom: the rack (its modules, the plug-ins' plates), the header (cover,
    # title, info, spectrum and scope), the waveforms, the control row at the bottom (under
    # the waveforms, as a deck's transport)
    def GetHeaderTop(self):
        return self.GetRackHeight()

    # the tempo strip at the deck's right, its columns shown or hidden on their own: the
    # tempo's by TEMPO (shown unless hidden), the key's by KEY (hidden unless shown); kept
    def IsStripColumnShown(self, column):
        # read once and kept (asked many times a frame, the settings' file opened each time)
        shown = self.__dict__.setdefault('strip_shown', {})
        if column not in shown:
            if column == 'tempo':
                shown[column] = GetPreference('tempo_strip') is not False
            else:
                shown[column] = GetPreference('key_strip') is True
        return shown[column]

    def SetStripColumnShown(self, column, shown):
        self.__dict__.setdefault('strip_shown', {})[column] = bool(shown)
        SetPreference('tempo_strip' if column == 'tempo' else 'key_strip', bool(shown))
        self.TempoButton.reInitBuffer = True
        self.KeyButton.reInitBuffer = True
        self.OnSize(settle=True)

    def GetDeckRight(self):
        # the header's and the waveforms' right end: left of the tempo strip when shown
        w = self.GetClientSize().width
        count = len([c for c in ('tempo', 'key') if self.IsStripColumnShown(c)])
        if count:
            return w - 8 - TempoStrip.GetWidth(count) - 8
        return w - 8

    def GetStripSlack(self):
        # the room the tempo strip leaves now past its widest (both its columns): what is
        # sized by the header's room counted as at its widest, kept as TEMPO or KEY toggles
        return TempoStrip.GetWidth(2) + 8 - (self.GetClientSize().width - 8
                                             - self.GetDeckRight())

    def GetControlRows(self):
        # the control row a row more when the window is too narrow for both its sides: the
        # transport and the ways it plays on the first, SNAP, TEMPO, KEY and the volume on
        # the second (SNAP was hidden)
        right = SnapButton.LENGTH + SnapButton.GROUP_GAP + TempoButton.LENGTH\
            + KeyButton.LENGTH + SnapButton.GROUP_GAP + VolumeSlider.LENGTH + 5
        left = PlayBoxControlButton.STRIP_X + PlayBoxControlButton.STRIP_WIDTH + 6
        return 1 if self.GetClientSize().width >= left + right else 2

    def GetControlHeight(self):
        return self.CONTROL_HEIGHT * getattr(self, 'control_rows', 1)

    def GetControlExtra(self):
        return self.GetControlHeight() - self.CONTROL_HEIGHT

    def GetControlTop(self):
        return self.GetClientSize().height - self.GetControlHeight()

    def GetRightControlTop(self):
        # the volume's row: the last
        return self.GetClientSize().height - self.CONTROL_HEIGHT

    def IsControlTwoRows(self):
        # two rows: on the left the transport over the ways it plays, on the right SNAP,
        # TEMPO and KEY over the volume
        return getattr(self, 'control_rows', 1) == 2

    def GetVolumeRoom(self):
        # the volume's width and its gap left of TEMPO's group, on the same row
        return 0 if self.IsControlTwoRows() else VolumeSlider.LENGTH + SnapButton.GROUP_GAP

    def CheckControlRows(self):
        rows = self.GetControlRows()
        if rows == getattr(self, 'control_rows', 1):
            return
        self.control_rows = rows
        wx.CallAfter(self.RelayoutHeader)

    # the room between the waveforms' bottom and the control row
    WAVE_BOTTOM_GAP = 11

    def GetRackHeight(self):
        # the rack over the header: its bar and its modules shown
        rack = getattr(self, 'Rack', None)
        return RackBar.HEIGHT + (rack.GetHeight() if rack is not None else 0)

    # the header's last sizes (44 and 30, 300 wide at most: PlayBoxSpectrum.max_width)
    SCOPE_MOST = 44
    BARS_MOST = 30

    def LayoutAnalyzerVisuals(self):
        '''the spectrum's bars and the scope in ANALYZER's BARS part (their windows its
        children: AnalyzerPanel.bars_rect), the scope a square at its right, 8 px apart;
        hidden with the part or ANALYZER'''
        rect = getattr(self.Analyzer, 'bars_laid', None)
        if rect is None or rect.width < self.SCOPE_MOST + 32 + 40:
            self.Spectrum.Place(None)
            self.VectorScope.Place(None)
            return
        # as big as they were in the header at most, side by side 14 px apart (as there),
        # the two on the part's middle (the part's whole size made them too big)
        size = min(rect.height, self.SCOPE_MOST)
        bars = min(rect.height, self.BARS_MOST)
        width = min(self.Spectrum.max_width, rect.width - 16 - size - 14)
        left = rect.x + (rect.width - (width + 14 + size)) // 2
        cy = rect.y + rect.height // 2
        self.Spectrum.Place(wx.Rect(left, cy - bars // 2, width, bars))
        self.VectorScope.Place(wx.Rect(left + width + 14, cy - size // 2, size, size))

    def GetWaveTop(self):
        if self.WaveDetail.IsShown():
            return self.WaveDetail.GetRect().y
        return self.Wave.GetRect().y

    def SetRectDraw(self, dc):
        width, height = self.GetSize()
        # the control row under the header: the bar's ground, a line over and under it
        tokens = uikit.ui()
        top = self.GetControlTop()
        bar = self.GetControlHeight()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(tokens.BAR_BG))
        dc.DrawRectangle(0, top, width, bar)
        dc.SetPen(wx.Pen(tokens.BAR_LINE, 1))
        dc.DrawLine(0, top, width, top)
        dc.DrawLine(0, top + bar - 1, width, top + bar - 1)
        # two rows: a line between them (the control buttons' own over theirs)
        if self.IsControlTwoRows():
            dc.DrawLine(0, top + self.CONTROL_HEIGHT - 1, width, top + self.CONTROL_HEIGHT - 1)
        self.DrawWaveFrame(dc)
        # the right side's separators on SNAP's row (the first)
        # the line between SNAP's group and TEMPO's
        snap = getattr(self, 'SnapButton', None)
        if snap is not None and snap.IsShown():
            sx = snap.GetRect().GetRight() + 1 + SnapButton.GROUP_GAP // 2
            dc.DrawLine(sx, top + 8, sx, top + self.CONTROL_HEIGHT - 7)
        # and between TEMPO's and KEY's and the volume's (on one row)
        key = getattr(self, 'KeyButton', None)
        if key is not None and self.IsControlTwoRows() is False:
            sx = key.GetRect().GetRight() + 1 + SnapButton.GROUP_GAP // 2
            dc.DrawLine(sx, top + 8, sx, top + self.CONTROL_HEIGHT - 7)
        self.DrawLiveMessage(dc)

    # the waveforms' frame: a display's edge this far around them
    WAVE_FRAME = 4

    # the frame's room around the waveforms' boxes (left, top, right, bottom): their
    # pictures 9 px in from it on every side (the strip's starts at its top, under a 4 px
    # lane; the overview's ends 7 px over its bottom, the boxes' own margins 5 at the sides)
    WAVE_FRAME_ROOM = (4, 5, 4, 2)

    def GetWaveFrameRect(self, rect):
        left, top, right, bottom = self.WAVE_FRAME_ROOM
        return wx.Rect(rect.x - left, rect.y - top, rect.width + left + right,
                       rect.height + top + bottom)

    def DrawWaveFrame(self, dc):
        wave = getattr(self, 'Wave', None)
        if wave is None or wave.IsShown() is False:
            return
        rect = wave.GetRect()
        detail = getattr(self, 'WaveDetail', None)
        if detail is not None and detail.IsShown():
            rect = rect.Union(detail.GetRect())
        rect = self.GetWaveFrameRect(rect)
        dc.SetPen(wx.Pen(self.st.RACK_EDGE_COLOR, 1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRoundedRectangle(rect, uikit.RADIUS)

    def GetLiveMessage(self):
        # (text, warned) while a station connects or after it failed to, else None
        failure = self.GetStreamFailure()
        if failure:
            return ('Could not connect: %s' % (failure), True)
        if self.GetStreamConnecting() is not None:
            return ('Connecting to the station...', False)
        return None

    def DrawLiveMessage(self, dc):
        # in the middle of the waveforms' place (they step aside: HandleLiveMessage)
        message = getattr(self, 'live_message', None)
        if message is None:
            return
        text, warned = message
        width, _ = self.GetSize()
        # between the header and the control row
        top = self.GetHeaderTop() + self.GetHeaderHeight()
        height = self.GetControlTop()
        dc.SetFont(uikit.get_font(uikit.BODY))
        dc.SetTextForeground(uikit.ui().WARN if warned else self.st.TITLE_DIM_COLOR)
        tw, th = dc.GetTextExtent(text)
        dc.DrawText(text, (width - tw) // 2, top + (height - top - th) // 2)

    def HandleLiveMessage(self):
        # the waveforms hidden while there is a message for their place, shown again after
        # (the detail strip as the View menu has it)
        message = self.GetLiveMessage()
        if message == getattr(self, 'live_message', None):
            return
        self.live_message = message
        self.Wave.Show(message is None)
        if message is None:
            self.WaveDetail.OnSize()
        else:
            self.WaveDetail.Hide()
        self.DirectDraw()

    def OnSize(self, event=None, settle=False):
        # settle: a single step's change (the tempo strip toggled), the waveforms painted
        # for it before the screen shows it (PlayBoxWave.SettleNow)
        self.Freeze()
        self.DirectDraw()
        # the cover, the header right to left (scope, spectrum: as wide as leaves the title
        # its room), then what fits between them (the info, the title: the compact header's
        # title ends at the info)
        self.Apic.OnSize(None)
        self.VectorScope.OnSize(None)
        self.Spectrum.OnSize(None)
        self.Info.OnSize(None)
        self.Title.OnSize(None)
        self.Wave.OnSize(None)
        self.WaveDetail.OnSize(None)
        self.TempoStrip.OnSize(None)
        self.ControlButton.OnSize(None)
        self.RackBar.OnSize()
        self.Rack.OnSize()
        self.VolumeSlider.OnSize(None)
        self.TempoButton.OnSize(None)
        self.KeyButton.OnSize(None)
        self.SnapButton.OnSize(None)
        if settle:
            self.Wave.SettleNow()
        self.DirectDraw()
        self.Thaw()
        self.CheckHeaderRows()
        self.CheckControlRows()

    def CATCH_EVT_GLOBAL(self, event):

        self.AudioEvent(event)
        self.HandleLiveMessage()

    def OnIdle(self, event):
        if self.reInitBuffer is False:
            return
        elapsed_time = time.time() - self.buffer.lap
        if elapsed_time < 1.0 / self.buffer.fps:
            return
        self.buffer.lap = time.time()
        self.InitBuffer()
        self.Refresh(False)

    def CATCH_EVT_KEY_UP(self, event):

        self.cache.oneshotkey = False

    def CATCH_EVT_KEY_DOWN(self, event):

        if self.parent.ListSearch.SearchText.onClient:
            return
        # isSPKD = event.AltDown or event.CmdDown or event.ControlDown or event.ShiftDown
        # OnStop(), OnReview(), OnStop(), OnFR(), OnFF(), OnCmax()
        # 1:49, 2:50, 3:51, Q:81, W:87, E:69, A:65, S:83, D:68, R:82, T:84, F:70
        # print event.KeyCode
        # 96, 49, 50, 51, 52, 53
        # print event.KeyCode
        # print event.RawKeyFlags
        ctrl = event.CmdDown or event.ControlDown
        namespace = self.parent.parent.GetNameSpaceByRawKeyFlag(
            event.RawKeyFlags, ctrl, event.ShiftDown)
        # print namespace
        if namespace is None:
            return

        if namespace == 'highlight_toggle' and self.cache.oneshotkey is False:
            self.cache.oneshotkey = True
            if self.IsHighlightOn():
                self.SetHighlightOff()
            else:
                self.SetHighlightOn()
                self.GotoTrackOffsetTime()

        if namespace == 'play_toggle' and self.cache.oneshotkey is False:
            self.cache.oneshotkey = True
            playIdx = self.GetPlayingListItemIdx()
            selItemIdx = self.parent.ListBox.GetSelectedItems()
            selListIdx = self.parent.ListBox.GetSelectedListIdx()
            if len(selItemIdx) == 1 and playIdx != [selListIdx, selItemIdx[0]]:
                self.parent.ListBox.LeftDoubleClick(None)
            elif self.IsPlaying():
                self.OnPause()
            else:
                self.OnResume()

        if namespace == 'loop_toggle' and self.cache.oneshotkey is False:
            self.cache.oneshotkey = True
            if self.IsLoopOn():
                self.SetLoopOff()
            else:
                self.SetLoopOn()
            self.reInitBuffer = True

        if namespace == 'loud_toggle' and self.cache.oneshotkey is False:
            self.cache.oneshotkey = True
            if self.IsLoudOn():
                self.SetLoudOff()
            else:
                self.SetLoudOn()

        if namespace == 'previous_track':
            self.ControlButton.SetButtonFlash(1)
            result = self.OnPrev()
            if result is False:
                self.GotoTrackOffsetTime()
            self.SelectPlayingItem()

        if namespace == 'next_track':
            self.ControlButton.SetButtonFlash(3)
            self.OnNext()
            self.SelectPlayingItem()

        if namespace == 'fast_forward':
            self.OnFastForward()

        if namespace == 'fast_backward':
            self.OnFastRewind()

        # if isSPKD is False and event.KeyCode in (49, 50, 51, 52, 53): # 1 2 3 4 5
        if namespace == 'highlight_increase' or namespace == 'highlight_decrease':
            dutaionTypeId = self.GetHighlightDurationTypeId()
            if namespace == 'highlight_increase':
                dutaionTypeId += 1
            if namespace == 'highlight_decrease':
                dutaionTypeId -= 1
            if dutaionTypeId > 4:
                return
            if dutaionTypeId < 0:
                return
            value = self.parent.parent.MenuBar.highlightDurationItems[dutaionTypeId]
            # value = (8, 16, 32, 48, 64)[dutaionTypeId]
            self.ChangeHighlightLength(value, turn_on=True)
            for i in range(len(self.parent.parent.MenuBar.highlightDurationItems)):
                if i == dutaionTypeId:
                    self.parent.parent.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check()
                else:
                    self.parent.parent.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check(False)

    def CATCH_EVT_MOUSEWHEEL(self, event):

        if event.rectIdx == 100 and event.WheelRotation < 0:
            self.OnFF()
        if event.rectIdx == 100 and event.WheelRotation > 0:
            self.OnFR()

    def __del__(self):
        self.AudioControl.loop = False
        # self.AudioControl._Thread__stop()
        # self.AudioControl._stop()
        self.AudioControl._delete()
        self.AudioControl._Thread__exc_clear()




class PlayBoxVisualClock(threading.Thread):

    # the visualizers' own clock while playing: the global events come every 25 ms
    # (about 32 a second on Windows), which was the most any fps setting gave. a
    # thread keeps the beat (time.sleep is to the millisecond) and the drawing is
    # done on the GUI thread, one tick waiting at a time
    def __init__(self, parent):
        threading.Thread.__init__(self, daemon=True)
        self.parent = parent
        self.loop = True
        self.posted = False
        # a wx.Timer beside the thread, always: in the loops Windows runs on its own
        # (a window moved or resized, a drag and drop) the CallAfter below waited, up
        # to 220 ms a frame measured, and a timer's WM_TIMER still comes. outside them
        # its beats are the thread's twice over, and a box draws once a frame
        # (DirectDraw)
        self.sizing = wx.Timer()
        self.sizing.Bind(wx.EVT_TIMER, self.OnSizing)
        # the shortest a timer goes (it comes about every 15.6 ms)
        self.sizing.Start(10)
        self.start()

    def OnSizing(self, event):
        self.Tick()

    def GetBoxes(self):
        parent = self.parent
        # ANALYZER before the spectrum and the scope in it (drawn after them, it painted
        # over them)
        return [getattr(parent, name, None)
                for name in ('RackBar', 'Analyzer', 'Master', 'Mixer', 'Instruments', 'PianoRoll',
                             'Spectrum', 'VectorScope', 'Wave', 'WaveDetail')]

    def GetFPS(self):
        fps = [box.buffer.fps for box in self.GetBoxes() if box is not None]
        return max(fps + [1])

    def run(self):
        due = time.perf_counter()
        while self.loop:
            due += 1.0 / self.GetFPS()
            delay = due - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                # behind (the computer was busy): from now on, no catching up
                due = time.perf_counter()
            if self.posted:
                continue
            self.posted = True
            wx.CallAfter(self.Tick)

    def Tick(self):
        self.posted = False
        if self.loop is False or not self.parent:
            return
        PaintUnpainted()
        if self.parent.IsVisualPlaying() is False:
            # stopped: ANALYZER's meters and the rack bar's fall to rest, then nothing is
            # drawn; INSTRUMENTS goes on while they play alone (its step lit moved only
            # with the mouse over it)
            analyzer = getattr(self.parent, 'Analyzer', None)
            if analyzer is not None and analyzer.analyzer.IsSettled() is False:
                if analyzer.IsShown():
                    analyzer.DirectDraw()
                self.parent.RackBar.DirectDraw()
            panel = getattr(self.parent, 'Instruments', None)
            if panel is not None and panel.IsShown() and panel.IsActive():
                panel.DirectDraw()
                panel.Update()
                # (the piano roll's step heard with them)
                roll = getattr(self.parent, 'PianoRoll', None)
                if roll is not None and roll.IsShown():
                    roll.DirectDraw()
                    roll.Update()
            # MASTER's meters drawn once more, at rest (they held their last frame)
            master_panel = getattr(self.parent, 'Master', None)
            if master_panel is not None and not getattr(self, 'master_rested', False):
                master_panel.reInitBuffer = True
                self.master_rested = True
            # MIXER's meters with them (and falling to rest after)
            mixer = getattr(self.parent, 'Mixer', None)
            if mixer is not None and mixer.IsShown() and (
                    mixer.IsActive() or panel is not None and panel.IsActive()):
                mixer.DirectDraw()
                mixer.Update()
            return
        self.master_rested = False
        for box in self.GetBoxes():
            if box is not None and box.IsShown():
                # DEBUG(hang): each box's drawing time (mainapp's watchdog); removed once
                # found
                lap = time.perf_counter()
                box.DirectDraw()
                instruments.COUNTS['ms ' + type(box).__name__] += int(
                    (time.perf_counter() - lap) * 1000)
                # put on the screen now: Windows paints only when no other message
                # waits, and with the mouse moving over the window the frames drawn
                # waited (the clock kept 60 a second, the screen did not). here only:
                # for every box (DirectDraw) a sash dragged painted each one at every
                # step and could not keep up with the mouse
                box.Update()
        # the time shown with them (its own 30 a second): it came with the global
        # events, a wx.Timer, held back with the mouse moving as the frames were
        info = getattr(self.parent, 'Info', None)
        if info is not None and info.IsShown():
            info.HandleInfoChange()
            info.Update()

    def Quit(self):
        self.loop = False
        self.sizing.Stop()


def get_span_text(seconds):
    # a span as it reads best: 2.1 s, 45 s, 3:20
    if seconds < 10:
        return '%.1f s' % (seconds)
    if seconds < 60:
        return '%d s' % (round(seconds))
    return '%d:%02d' % (seconds // 60, seconds % 60)


def draw_live_trace(dc, parent, rect, seconds, spread=audio.WAVEFORM_BAND_SPREAD):
    '''a station's last seconds in rect, painted as a track's waveform is (the same
    painter, ground and colours), the newest at the right edge, moving left: an
    oscilloscope of what plays. False for a file (its waveform is the analysis')'''
    if parent.IsStreamTrack() is False:
        return False
    trace = parent.GetLiveTrace()
    x, y, w, h = rect
    if parent.GetLiveMessage() is not None:
        # nothing played yet, or nothing to play: said in the middle of the waveforms'
        # place instead (PlayBox.DrawLiveMessage)
        return True
    if trace is None or len(trace) == 0 or w <= 0 or h <= 0:
        return True
    count = len(trace)
    end = count
    start = end - seconds / mfeats.WAVEFORM_COLUMN_SECONDS
    image = audio.paint_waveform_3band(
        trace, w, h, ground=numpy.array(parent.st.PLAY_BG_COLOR, dtype=float),
        start=start, end=end, spread=spread)
    dc.DrawBitmap(wx.Bitmap.FromBuffer(w, h, image.tobytes()), x, y)
    return True


class PlayBoxControlButton(RectBox):

    # (its first button 8 px in: 6 and its own 2)
    STRIP_X = 6
    # (HIGHLIGHT's and SHORT's length keys joined to them; HIGHLIGHT and SHORT 8 px in
    # their faces either side, 6 and 7 before)
    STRIP_WIDTH = 354

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.height = 23
        self.buffer.fps = 30
        self.font_colors = []
        self.button_colors = []
        self.LoadBitmapImages()
        self.font_color_on = (0, 0, 0)
        self.font_color_off = (125, 125, 125)
        self.button_color_on = (200, 200, 220)
        self.button_color_toggle_on = (255, 120, 120)
        self.button_color_off = (0, 0, 0)
        self.button_color_down = (180, 180, 180)
        self.polygons = Struct(play=None, next=None, prev=None)
        self.downed_button = None
        self.button_flash = [0.0] * 10
        self.button_status = [False] * 10
        # 6: MASTER's panel folded or open (not a toggle of its own: the panel says);
        # 7: SHORT (the radio edit); 8, 9: HIGHLIGHT's and SHORT's lengths (a menu each,
        # the main menu's Highlight Duration before)
        self.toggle_buttons = [True, False, True, False, True, True, False, True, False,
                               False]
        self.hovered = None
        self.SetBackgroundColour(uikit.ui().BAR_BG)
        self.SetPreInitRects()
        self.SetButtonColors()
        self.OnSize()
        self.InitBuffer()

    def LoadBitmapImages(self):
        self.bmp = Struct()
        command = 'self.bmp.%s_%s = images.playbox_button_%s_%s.GetBitmap()'
        for nv in ('ff', 'fr'):
            for cv in ('black', 'white'):
                exec(command % (nv, cv, nv, cv))
        for nv in ('highlight', 'play', 'loop', 'loud'):
            for cv in ('red', 'black', 'white'):
                exec(command % (nv, cv, nv, cv))

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        for i in range(len(self.rects)):
            # (a button with no room: not hit at its corner)
            if self.rects[i][2] and self.IsInRect(self.rects[i], xy):
                return i
        return None

    def CATCH_EVT_GLOBAL(self, event):
        self.OverrideStatusFromParent()
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleEventButtonStatus(event)
        self.HandleEventPlayControl(event)
        self.HandleButtonFlash(event)
        hovered = event.rectIdx if self.onClient else None
        if hovered != self.hovered:
            self.hovered = hovered
            self.reInitBuffer = True
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.downed_button = None

    def SetButtonFlash(self, idx):
        self.button_flash[idx] = 1.0

    def HandleButtonFlash(self, event):
        flash_buttons = [(i, cnt) for i, cnt
                         in enumerate(self.button_flash) if cnt > 0.0]
        if flash_buttons == []:
            return
        for i, cnt in flash_buttons:
            self.button_flash[i] -= 0.2
            if self.button_flash[i] <= 0.0:
                self.button_flash[i] = 0.0
                self.button_status[i] = False
            else:
                self.button_status[i] = True
        self.SetButtonColors()

    def OverrideStatusFromParent(self):
        if self.parent.IsHighlightOn() and self.button_status[0] is False:
            self.button_status[0] = True
            self.SetButtonColors()
        elif self.parent.IsHighlightOn() is False and self.button_status[0]:
            self.button_status[0] = False
            self.SetButtonColors()
        elif self.parent.IsPlaying() and self.button_status[2] is False:
            self.button_status[2] = True
            self.SetButtonColors()
        elif self.parent.IsPlaying() is False and self.button_status[2]:
            self.button_status[2] = False
            self.SetButtonColors()
        elif self.parent.IsLoopOn() and self.button_status[4] is False:
            self.button_status[4] = True
            self.SetButtonColors()
        elif self.parent.IsLoopOn() is False and self.button_status[4]:
            self.button_status[4] = False
            self.SetButtonColors()
        elif self.parent.IsLoudOn() and self.button_status[5] is False:
            self.button_status[5] = True
            self.SetButtonColors()
        elif self.parent.IsLoudOn() is False and self.button_status[5]:
            self.button_status[5] = False
            self.SetButtonColors()
        elif self.parent.IsRadioEditOn() != self.button_status[7]:
            self.button_status[7] = self.parent.IsRadioEditOn()
            self.SetButtonColors()

    def HandleEventPlayControl(self, event):
        if event.LeftDown is False:
            return
        if event.down.rectIdx is None:
            return
        status = self.button_status
        downIdx = event.down.rectIdx
        if self.IsDisabled(downIdx):
            return
        if downIdx == 0 and status[0]:
            self.parent.SetHighlightOn()
            self.parent.GotoTrackOffsetTime()
        if downIdx == 0 and status[0] is False:
            self.parent.SetHighlightOff()
        if downIdx == 4 and status[4]:
            self.parent.SetLoopOn()
        if downIdx == 4 and status[4] is False:
            self.parent.SetLoopOff()
        if downIdx == 5 and status[5]:
            self.parent.SetLoudOn()
        if downIdx == 5 and status[5] is False:
            self.parent.SetLoudOff()

        if downIdx == 7:
            self.parent.SetRadioEdit(status[7])
        if downIdx in (8, 9):
            self.PopupLength(downIdx)
        if downIdx == 6:
            self.parent.Master.Toggle()
        if downIdx == 1:
            self.parent.OnPrev()
            self.parent.SelectPlayingItem()
        if downIdx == 2 and status[2]:
            if self.parent.IsTrackFinishTime():
                self.parent.OnPlay()
            else:
                self.parent.OnResume()
        if downIdx == 2 and status[2] is False:
            self.parent.OnPause()
        if downIdx == 3:
            self.parent.OnNext()
            self.parent.SelectPlayingItem()

    def HandleEventButtonStatus(self, event):
        downIdx = event.down.rectIdx
        if downIdx is not None and self.IsDisabled(downIdx):
            return
        if downIdx is not None and event.LeftUp:
            if self.toggle_buttons[downIdx] is False:
                self.button_status[downIdx] = False
            self.downed_button = None
            self.SetButtonColors()
            return
        if downIdx is not None and event.LeftDown:
            self.downed_button = downIdx
            if self.toggle_buttons[downIdx]:
                if self.button_status[downIdx]:
                    self.button_status[downIdx] = False
                else:
                    self.button_status[downIdx] = True
            else:
                self.button_status[downIdx] = True
            self.SetButtonColors()
            return

    def SetButtonColors(self):
        button_colors = list()
        for i, v in enumerate(self.button_status):
            if v:
                if self.toggle_buttons[i]:
                    button_colors += ['red']
                else:
                    button_colors += ['white']
            else:
                button_colors += ['black']
        downIdx = self.downed_button
        if downIdx is not None and self.toggle_buttons[downIdx]:
            button_colors[downIdx] = 'white'
        self.button_colors = button_colors
        self.reInitBuffer = True

    # Draw SideBoxTool

    # LOUD renamed MASTER (it is Auto Master: levels, stereo and the limiter), its panel's
    # arrow beside it
    # 7, the radio edit, named SHORT (RADIO EDIT read as the song's own radio edit)
    LABELS = ('HIGHLIGHT', None, None, None, 'LOOP', 'MASTER', None, 'SHORT', None, None)

    def PopupLength(self, idx):
        # under its key, from the key it goes with: HIGHLIGHT's lengths (as the main
        # menu's), SHORT's (PlayBox.RADIO_EDIT_LENGTHS); chosen, the way it plays now
        menu = wx.Menu()
        if idx == 8:
            frame = self.parent.parent.parent
            current = self.parent.GetHighlightStaticPeriodTime()
            for i, seconds in enumerate(frame.MenuBar.highlightDurationItems):
                item = menu.AppendRadioItem(wx.ID_ANY, '%d bars (about %d s)'
                                            % (seconds // 2, seconds))
                item.Check(seconds == current)
                menu.Bind(wx.EVT_MENU, lambda e, i=i: self.ChooseHighlightLength(i), item)
            owner = self.rects[0]
        else:
            current = self.parent.GetRadioEditLength()
            for length, label in self.parent.RADIO_EDIT_LENGTHS:
                item = menu.AppendRadioItem(wx.ID_ANY, label)
                item.Check(length == current)
                menu.Bind(wx.EVT_MENU,
                          lambda e, length=length: self.parent.SetRadioEditLength(length), item)
            owner = self.rects[7]
        x, y, w, h = owner
        self.menu_open = idx
        self.DirectDraw()
        self.parent.parent.SetPopupMenu(menu, tuple(self.ClientToScreen((x, y + h + 2))),
                                        closed=self.MenuClosed)

    def MenuClosed(self):
        self.menu_open = None
        self.reInitBuffer = True

    def ChooseHighlightLength(self, index):
        # as the main menu's Highlight Duration (its check moved with it)
        frame = self.parent.parent.parent
        items = frame.MenuBar.highlightDurationItems
        self.parent.ChangeHighlightLength(items[index])
        for i in range(len(items)):
            frame.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check(i == index)
        SetPreference('highlight_duration_type', index)

    def SetRectDraw(self, dc):
        # uikit's faces: the toggles (HIGHLIGHT, LOOP, LOUD) on in the accent, play showing
        # pause while it plays, prev and next pressed while held; the groups' lines
        dc.SetPen(wx.Pen(uikit.ui().BAR_LINE, 1))
        for sx in self.separators:
            dc.DrawLine(sx, 3, sx, self.height - 2)
        if self.parent.IsControlTwoRows():
            # the line between the rows, as the row's (PlayBox.SetRectDraw) across it
            y = self.parent.CONTROL_HEIGHT - 5 - 1
            dc.DrawLine(-self.STRIP_X, y, self.GetSize().width, y)
        for i, rect in enumerate(self.rects):
            if rect[2] == 0:
                continue
            status = self.button_status[i]
            toggle = self.toggle_buttons[i]
            icon = None
            if i == 1:
                icon = 'prev'
            elif i == 3:
                icon = 'next'
            elif i == 2:
                icon = 'pause' if status else 'play'
            elif i in (8, 9):
                # turned over while its menu is open
                icon = 'up' if getattr(self, 'menu_open', None) == i else 'down'
            elif i == 6:
                # the panel made after this row: folded until it is
                master = getattr(self.parent, 'Master', None)
                icon = 'up' if master is not None and master.shown else 'down'
            on = toggle and status and i != 2
            # the length keys lit with the key they are joined to, their faces one
            if i in self.JOINED:
                on = self.toggle_buttons[self.JOINED[i]] and self.button_status[self.JOINED[i]]
            down = self.downed_button == i or (not toggle and status and i not in self.JOINED)
            corners = 'right' if i in self.JOINED else 'left' if i in self.JOINED.values()\
                else 'all'
            uikit.draw_button(dc, rect, label=self.LABELS[i], icon=icon, on=on, down=down,
                              hover=self.hovered == i, disabled=self.IsDisabled(i),
                              corners=corners)

    # the length keys and the keys they are joined to (HIGHLIGHT, SHORT)
    JOINED = {8: 0, 9: 7}

    # HIGHLIGHT, LOOP and SHORT: nothing for a station (a stream has no length)
    STREAM_DISABLED = (0, 4, 7, 8, 9)

    def IsDisabled(self, idx):
        return idx in self.STREAM_DISABLED and self.parent.IsStreamTrack()

    # Buffered DC

    def OnSize(self, event=None):
        # two rows: the ways it plays under the transport
        two = self.parent.IsControlTwoRows()
        if two != getattr(self, 'two_rows', None):
            self.SetPreInitRects(two)
        rows = 2 if two else 1
        # as wide as its keys (two rows: the second's, narrower; the first row's width
        # covered SNAP in a narrow window)
        width = max(r[0] + r[2] for r in self.rects) + 2
        self.SetRect((self.STRIP_X, self.parent.GetControlTop() + 5, width,
                      self.height + (rows - 1) * self.parent.CONTROL_HEIGHT))
        self.DirectDraw()

    def SetPreInitRects(self, two=False):
        # make polygons, rectangles and lines when class starts
        # by index highlight, prev, play, next, loop, loud, its arrow, radio edit; placed
        # transport first (prev, play wider, next), then the toggles (highlight, radio edit
        # beside it: the two ways to play a song short, loop, master)
        # in three groups, a line between them: the transport, the ways it plays (highlight,
        # radio edit, loop), master
        x, y, h = (2, 2, 19)
        # (MASTER and its arrow, 5 and 6, are the rack bar's now: no room of their own)
        # (HIGHLIGHT and SHORT each a narrow key joined to it, their edge shared: its
        # length, 8 and 9, an input group's)
        # (the length keys 20 wide, as the rack bar's arrows: 16 was tight round the mark)
        rects = ((x + 140, y, 70, h), (x, y, 37, h), (x + 40, y, 46, h), (x + 89, y, 37, h),
                 (x + 304, y, 44, h), (0, 0, 0, 0), (0, 0, 0, 0),
                 (x + 232, y, 50, h), (x + 209, y, 20, h), (x + 281, y, 20, h))
        self.separators = (x + 133,)
        if two:
            # the ways it plays a row under the transport, from its left
            y2 = y + 33
            rects = ((x, y2, 70, h), rects[1], rects[2], rects[3], (x + 164, y2, 44, h),
                     rects[5], rects[6], (x + 92, y2, 50, h), (x + 69, y2, 20, h),
                     (x + 141, y2, 20, h))
            self.separators = ()
        self.two_rows = two
        self.rects = rects
        rx = max(v[0] + v[2] for v in rects) + 1
        lines = [(0, rects[-1][3] + 3, rx + 1, rects[-1][3] + 3)]
        lines += [(0, 0, rx, 0), (rx, rects[-1][1] - 2, rx, rects[-1][3] + 3)]
        for i, v in enumerate(rects):
            lines += [(v[0] - 2, v[1] - 1, v[0] - 2, v[3] + 3)]
        self.lines = lines

    def GetDLTriangle(self, size, offset, reversed=False):
        pointsB = self.GetTrianglePoint(size, offset)[size - 1:]
        pointsT = self.GetTrianglePoint(size - 2, wx.Point(offset.x + 1, offset.y + 1))
        if reversed:
            pointsB = (0, 0) - numpy.array(pointsB)
            pointsT = (0, 0) - numpy.array(pointsT)
            pointsB = tuple(pointsB)
            pointsT = tuple(pointsT)
        return pointsB, pointsT

    def GetTrianglePoint(self, size, offset):
        points = list()
        for x in range(0, size):
            for y in range(0, size / 2):
                if x + 1 < y * 2:
                    points.append((x + offset.x, y + offset.y))
                if x + 1 < size - y * 2:
                    points.append((x + offset.x, y + size / 2 + offset.y))
        return points


# the grid's lanes over what plays (the highlight, SHORT): the ground this share to the
# accent (blue: told from the rest by brightness too)
LANE_PLAYED = 0.4


def draw_snap_flash(dc, x, top, height, share):
    # a snapped seek's line: the accent, 3 px, fading by share (1 to 0)
    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        return
    accent = uikit.colour(uikit.ui().ACCENT)
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(accent.Red(), accent.Green(), accent.Blue(),
                                                  int(230 * share)))))
    gc.DrawRectangle(x - 1, top, 3, height)


def get_lane_played(st):
    ground = wx.Colour(st.PLAY_BG_COLOR)
    accent = uikit.colour(uikit.ui().ACCENT)
    return tuple(int(g + (a - g) * LANE_PLAYED) for g, a in
                 zip(ground.Get()[:3], accent.Get()[:3]))


def format_tempo(percent):
    # two decimals as a CDJ shows them; one from 100 (WIDE's whole range: its 0.5 steps)
    return '%+.1f' % (percent) if abs(percent) >= 99.995 else '%+.2f' % (percent)


class VolumeSlider(RectBox):

    '''the volume in the control row's right end, always there: a speaker key (a click
    mutes, again unmutes), a slider (a click or a drag sets it, the wheel steps it), its
    level in dB (a dropdown before)'''

    LENGTH = 164
    KEY = (1, 2, 22, 19)
    TRACK_LEFT = 32
    TRACK_WIDTH = 70
    READOUT = 46

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.muted_volume = None
        self.hovered = None
        self.sliding = False
        self.SetBackgroundColour(uikit.ui().BAR_BG)
        self.InitBuffer()

    def GetVolume(self):
        return self.parent.GetVolume()

    def SetVolume(self, volume):
        volume = min(max(volume, 0.0), 1.0)
        if volume == self.GetVolume():
            return
        self.parent.SetVolume(volume)
        self.reInitBuffer = True

    def IsMuted(self):
        return self.muted_volume is not None

    def ToggleMute(self):
        if self.muted_volume is None:
            self.muted_volume = self.GetVolume()
            self.SetVolume(0)
        else:
            self.SetVolume(self.muted_volume)
            self.muted_volume = None
        self.reInitBuffer = True

    def GetTrackRect(self):
        h = self.GetClientSize().height
        return wx.Rect(self.TRACK_LEFT, 2, self.TRACK_WIDTH, 19)

    def SetRectDraw(self, dc):
        st = self.parent.st
        tokens = uikit.ui()
        muted = self.IsMuted()
        # the speaker key, warned (orange) while muted
        uikit.draw_button(dc, self.KEY, icon='mute' if muted else 'speaker', warn=muted,
                          hover=self.hovered == 'key')
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        track = self.GetTrackRect()
        cy = track.y + track.height / 2.0
        volume = self.GetVolume()
        # the track, its level in the accent, a handle on it
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(tokens.CONTROL_BG))))
        gc.DrawRoundedRectangle(track.x, cy - 2, track.width, 4, 2)
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(
            tokens.BAR_TEXT_DIM if muted else tokens.ACCENT))))
        gc.DrawRoundedRectangle(track.x, cy - 2, max(track.width * volume, 2), 4, 2)
        hx = track.x + track.width * volume
        face = uikit.colour(tokens.BAR_TEXT if self.hovered == 'track' or self.sliding
                            else tokens.CONTROL_FG)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(tokens.BAR_BG)).Width(1)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(face)))
        # (half a pixel up and left: the renderer draws a shape's edge half a pixel down
        # and right, and the handle sat low on the track, measured)
        gc.DrawEllipse(hx - 5.5, cy - 5.5, 10, 10)
        # the level: dB of the amplitude, MUTE muted
        if muted:
            text = 'MUTE'
        elif volume <= 0.0:
            # silent but not muted (the slider at its bottom): minus infinity, as a mixer
            # shows it; MUTE is the key's (it gives the level back)
            text = '-\u221e'
        else:
            text = '%.1f' % (20 * math.log10(volume))
        font = wx.Font(wx.Size(0, uikit.READOUT), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
        # on a display's cell as the other readouts (the digits ran to the row's edge)
        gc.SetFont(font, uikit.colour(tokens.WARN if muted else st.LCD_TEXT_COLOR))
        tw, th = gc.GetTextExtent('-00.0')[:2]
        cell = wx.Rect(self.LENGTH - 3 - int(tw) - 14, 2, int(tw) + 14, 19)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(st.RACK_EDGE_COLOR)).Width(1)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(st.LCD_BG_COLOR))))
        gc.DrawRoundedRectangle(cell.x, cell.y, cell.width - 1, cell.height - 1, uikit.RADIUS)
        tw = gc.GetTextExtent(text)[0]
        # the level right-aligned as numbers are; MUTE (a word) centred
        tx = cell.x + (cell.width - tw) / 2.0 if muted else cell.GetRight() - 6 - tw
        gc.DrawText(text, tx, cell.y + (cell.height - th) / 2.0)

    def GetHit(self, x, y):
        if wx.Rect(*self.KEY).Contains((x, y)):
            return 'key'
        track = self.GetTrackRect()
        if wx.Rect(track.x - 6, 0, track.width + 12, 23).Contains((x, y)):
            return 'track'
        return None

    def SetFromX(self, x):
        track = self.GetTrackRect()
        self.muted_volume = None
        self.SetVolume(1.0 * (x - track.x) / track.width)
        self.reInitBuffer = True

    def CATCH_EVT_GLOBAL(self, event):
        hit = self.GetHit(event.X, event.Y) if self.onClient else None
        if hit != self.hovered:
            self.hovered = hit
            self.reInitBuffer = True
        if self.sliding:
            if event.LeftIsDown:
                self.SetFromX(event.X)
                return
            self.sliding = False
            self.reInitBuffer = True
        if self.parent.parent.HasToSkipEvent() or event.LeftDown is False or hit is None:
            return
        if hit == 'key':
            self.ToggleMute()
        else:
            self.sliding = True
            self.SetFromX(event.X)

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        self.muted_volume = None
        self.SetVolume(self.GetVolume() + event.WheelRotation / 400.0 / 3)

    def OnSize(self, event=None):
        # the control row's right end, TEMPO left of it
        w = self.parent.GetClientSize().width
        x = w - 5 - VolumeSlider.LENGTH
        self.SetRect((x, self.parent.GetRightControlTop() + 5, self.LENGTH, 23))
        self.DirectDraw()


class TempoButton(RectBox):

    '''left of the volume: the tempo strip's tempo fader shown or hidden (on, in the
    accent, while shown); its label the tempo moved (+1.20), else TEMPO; the wheel over it
    steps the tempo'''

    # TEMPO 7 px in from either side (5 it was)
    LENGTH = 52
    FACE = (1, 2, 49, 19)
    COLUMN = 'tempo'

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.hovered = False
        self.SetBackgroundColour(uikit.ui().BAR_BG)
        self.InitBuffer()

    def GetLabel(self):
        # its name for a station (no tempo of its own)
        percent = (self.parent.GetTempoRate() - 1.0) * 100.0
        if self.parent.IsStreamTrack():
            return 'TEMPO'
        return format_tempo(percent) if abs(percent) > 1e-6 else 'TEMPO'

    def SetRectDraw(self, dc):
        # a station's too: the strip shown or hidden still (its faders off there, the strip
        # dims them); it was off, the strip left open with no way to close it
        uikit.draw_button(dc, self.FACE, label=self.GetLabel(),
                          on=self.parent.IsStripColumnShown(self.COLUMN),
                          hover=self.onClient)

    def CATCH_EVT_GLOBAL(self, event):
        if self.onClient != self.hovered:
            self.hovered = self.onClient
            self.reInitBuffer = True
        if self.parent.parent.HasToSkipEvent():
            return
        if event.LeftDown and event.down.rectIdx is not None:
            shown = self.parent.IsStripColumnShown(self.COLUMN)
            self.parent.SetStripColumnShown(self.COLUMN, not shown)

    def Step(self, rotation):
        self.parent.TempoStrip.StepTempo(rotation)

    def CATCH_EVT_MOUSEWHEEL(self, event):
        # a station's key moves, its tempo not (radio.open_stream)
        if self.onClient is False or self.parent.IsStreamTrack() and self.COLUMN == 'tempo':
            return
        self.Step(event.WheelRotation)

    def GetX(self):
        w = self.parent.GetClientSize().width
        return w - 5 - self.parent.GetVolumeRoom() - KeyButton.LENGTH - self.LENGTH

    def OnSize(self, event=None):
        # on the control row's first row (two rows: the volume under it)
        self.SetRect((self.GetX(), self.parent.GetControlTop() + 5, self.LENGTH, 23))
        self.DirectDraw()


class KeyButton(TempoButton):

    '''right of TEMPO: the strip's key fader shown or hidden; its label the key moved
    (K+1), else KEY; the wheel over it steps the key'''

    LENGTH = 40
    FACE = (1, 2, 37, 19)
    COLUMN = 'key'

    def GetLabel(self):
        semitones = self.parent.GetTempoSemitones()
        return 'K%+d' % (semitones) if semitones else 'KEY'

    def Step(self, rotation):
        self.parent.TempoStrip.StepKey(rotation)

    def GetX(self):
        w = self.parent.GetClientSize().width
        return w - 5 - self.parent.GetVolumeRoom() - self.LENGTH


class TempoStrip(RectBox):

    '''the tempo at the deck's right, as a deck's pitch fader: its columns side by side,
    each shown or hidden on its own (TEMPO, KEY): the tempo (in percent, its range, the key
    lock and 0 under it) and the key (in semitones, a semitone up, down and 0 under it,
    its keys row by row with the tempo's); their values over them;
    from the header's top to the waveforms' bottom (a dropdown under TEMPO before)'''

    RANGES = playboxlib.TEMPO_RANGES
    # within this share of the range from 0 a drag stops at 0
    DETENT = 0.03
    COLUMN = 41
    # the plate's inside at its sides, past the columns' own 2 px (1 more, asked)
    PAD = 1
    FADER = 4
    KEY_ROW = 22

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.side = None
        # the key under the pointer, and the one held down (as the control row's)
        self.hovered = None
        self.downed = None
        self.SetBackgroundColour(self.parent.st.PLAY_BG_COLOR)
        self.InitBuffer()

    @classmethod
    def GetWidth(cls, count):
        return cls.COLUMN * count - (count - 1) + cls.PAD * 2 if count else 0

    def GetColumns(self):
        return [c for c in ('tempo', 'key') if self.parent.IsStripColumnShown(c)]

    def GetKeyRects(self):
        # (column, key, label, on, rect): three keys a column, from the bottom up
        h = self.GetClientSize().height
        keys = []
        span = self.parent.GetTempoRange()
        for k, column in enumerate(self.GetColumns()):
            x = self.PAD + k * (self.COLUMN - 1) + 2
            if column == 'tempo':
                rows = (('reset', '0%', False),
                        ('lock', 'LOCK', self.parent.IsTempoKeyLockOn()),
                        ('range', 'WIDE' if span >= 100 else '%d%%' % (span), False))
            else:
                # the minus sign (U+2212) as wide as the plus, set as KEY 0 is
                rows = (('key_reset', 'KEY 0', False), ('key_down', 'KEY \u2212', False),
                        ('key_up', 'KEY +', False))
            for r, (key, label, on) in enumerate(rows):
                keys.append((column, key, label, on,
                             wx.Rect(x, h - 3 - 19 - r * self.KEY_ROW, 37, 19)))
        return keys

    def GetSliderRange(self):
        # the faders as long as the three keys under them leave; 9 px under the readout as
        # over the keys (7 under it was, measured)
        h = self.GetClientSize().height
        return (26, h - 3 - 19 - 2 * self.KEY_ROW - 10)

    def GetSliderX(self, index):
        return self.PAD + index * (self.COLUMN - 1) + (self.COLUMN - self.FADER) * 0.5

    def GetShare(self, column):
        if column == 'tempo':
            return (self.parent.GetTempoRate() - 1.0) * 100.0 / self.parent.GetTempoRange()
        return 1.0 * self.parent.GetTempoSemitones() / playboxlib.TEMPO_SEMITONES

    def SetRectDraw(self, dc):
        st = self.parent.st
        tokens = uikit.ui()
        w, h = self.GetClientSize()
        # a station's tempo column off, its key on (radio.open_stream: the key moves as it
        # plays, the tempo not)
        stream = self.parent.IsStreamTrack()
        # a plate as the waveforms' frame
        dc.SetPen(wx.Pen(st.RACK_EDGE_COLOR, 1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRoundedRectangle(0, 0, w, h, uikit.RADIUS)
        top, bottom = self.GetSliderRange()
        centre = (top + bottom) * 0.5
        font = wx.Font(wx.Size(0, uikit.READOUT), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
        for index, column in enumerate(self.GetColumns()):
            disabled = stream and column == 'tempo'
            share = self.GetShare(column)
            x = self.GetSliderX(index)
            rects = [(x - 1, top - 1, self.FADER + 2, bottom - top + 2),
                     (x, centre, self.FADER, -share * (bottom - top) * 0.5)]
            rects = [[int(v) for v in rect] for rect in rects]
            fill = st.METER_OFF_COLOR if disabled else tokens.ACCENT
            dc.DrawRectangleList(rects, pens=[wx.Pen(st.VOLUME_PN_COLOR, 1), wx.Pen(fill, 1)],
                                 brushes=[wx.Brush(st.VOLUME_BG_COLOR), wx.Brush(fill)])
            # 0 marked across the track, the handle where it is
            dc.SetPen(wx.Pen(st.VOLUME_PN_COLOR, 1))
            dc.DrawLine(int(x - 6), int(centre), int(x + self.FADER + 6), int(centre))
            hy = centre - share * (bottom - top) * 0.5
            dc.SetPen(wx.Pen(st.PLAY_BG_COLOR, 1))
            dc.SetBrush(wx.Brush(tokens.CONTROL_FG if disabled else tokens.BAR_TEXT))
            dc.DrawRoundedRectangle(int(x - 8), int(hy - 3), self.FADER + 16, 6, 2)
            if column == 'tempo':
                text = format_tempo((self.parent.GetTempoRate() - 1.0) * 100.0)
            else:
                text = 'K%+d' % (self.parent.GetTempoSemitones())
            dc.SetFont(font)
            dc.SetTextForeground(tokens.BAR_TEXT_DIM if disabled else st.LCD_TEXT_COLOR)
            tw, th = dc.GetTextExtent(text)
            dc.DrawText(text, int(self.PAD + index * (self.COLUMN - 1)
                                  + (self.COLUMN - tw) * 0.5), 6)
        for column, key, label, on, rect in self.GetKeyRects():
            disabled = stream and column == 'tempo'
            uikit.draw_button(dc, tuple(rect), label=label, on=on and not disabled,
                              down=self.downed == key, hover=self.hovered == key,
                              disabled=disabled)

    def CATCH_EVT_GLOBAL(self, event):
        # drawn again when the tempo, the key, the range or the lock moved elsewhere (keys)
        state = (self.parent.GetTempoRate(), self.parent.GetTempoSemitones(),
                 self.parent.GetTempoRange(), self.parent.IsTempoKeyLockOn(),
                 self.parent.IsStreamTrack())
        if state != getattr(self, 'state', None):
            self.state = state
            self.reInitBuffer = True
        position = wx.Point(int(event.X), int(event.Y))
        hovered = None
        stream = self.parent.IsStreamTrack()
        if self.onClient and self.side is None:
            for column, key, label, on, rect in self.GetKeyRects():
                if rect.Contains(position) and not (stream and column == 'tempo'):
                    hovered = key
        downed = self.downed if event.LeftIsDown else None
        if (hovered, downed) != (self.hovered, self.downed):
            self.hovered, self.downed = hovered, downed
            self.reInitBuffer = True
        if self.IsShown() is False:
            self.side = None
            return
        if self.side is not None:
            if event.LeftIsDown:
                self.Slide(event.Y)
                return
            self.side = None
        if self.parent.parent.HasToSkipEvent() or event.LeftDown is False\
                or self.onClient is False:
            return
        for column, key, label, on, rect in self.GetKeyRects():
            if rect.Contains(position):
                if stream and column == 'tempo':
                    return
                self.downed = key
                self.Press(key)
                self.Changed()
                return
        top, bottom = self.GetSliderRange()
        columns = self.GetColumns()
        index = min(max(int((event.X - self.PAD) // (self.COLUMN - 1)), 0), len(columns) - 1)
        if columns and top - 8 <= event.Y <= bottom + 8\
                and not (stream and columns[index] == 'tempo'):
            self.side = columns[index]
            self.Slide(event.Y)

    def Press(self, key):
        if key == 'lock':
            self.parent.SetTempoKeyLock(self.parent.IsTempoKeyLockOn() is False)
        elif key == 'range':
            ranges = self.RANGES
            current = self.parent.GetTempoRange()
            index = ranges.index(current) if current in ranges else -1
            self.parent.SetTempoRange(ranges[(index + 1) % len(ranges)])
        elif key == 'reset':
            self.parent.SetTempoRate(1.0)
        elif key == 'key_reset':
            self.parent.SetTempoSemitones(0)
        elif key in ('key_up', 'key_down'):
            self.StepKey(1 if key == 'key_up' else -1)

    def Slide(self, y):
        top, bottom = self.GetSliderRange()
        share = min(max(((top + bottom) * 0.5 - y) / ((bottom - top) * 0.5), -1.0), 1.0)
        if self.side == 'tempo':
            if abs(share) < self.DETENT:
                share = 0.0
            self.parent.SetTempoRate(1.0 + share * self.parent.GetTempoRange() / 100.0)
        else:
            self.parent.SetTempoSemitones(round(share * playboxlib.TEMPO_SEMITONES))
        self.Changed()

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        columns = self.GetColumns()
        index = min(max(int((event.X - self.PAD) // (self.COLUMN - 1)), 0), len(columns) - 1)
        if columns and columns[index] == 'key':
            self.StepKey(event.WheelRotation)
        elif self.parent.IsStreamTrack() is False:
            self.StepTempo(event.WheelRotation)

    def StepTempo(self, rotation):
        # the range's step a notch (as a CDJ's: 0.02% at 6, 0.05% at 10 and 16, 0.5% WIDE)
        step = self.parent.GetTempoStep() * (1 if rotation > 0 else -1)
        percent = (self.parent.GetTempoRate() - 1.0) * 100.0 + step
        self.parent.SetTempoRate(1.0 + percent / 100.0)
        self.Changed()

    def StepKey(self, rotation):
        # a semitone a notch
        step = 1 if rotation > 0 else -1
        self.parent.SetTempoSemitones(self.parent.GetTempoSemitones() + step)
        self.Changed()

    def Changed(self):
        self.reInitBuffer = True
        self.parent.TempoButton.reInitBuffer = True
        self.parent.KeyButton.reInitBuffer = True

    def OnSize(self, event=None):
        # from the header's top to the waveforms' frame's bottom, 8 px from the right; as
        # wide as its columns shown, none: hidden
        count = len(self.GetColumns())
        if count == 0:
            self.Hide()
            return
        w = self.parent.GetClientSize().width
        width = self.GetWidth(count)
        top = self.parent.GetHeaderTop() + 8
        bottom = self.parent.Wave.GetRect().GetBottom() + 1\
            + self.parent.WAVE_FRAME_ROOM[3]
        self.SetRect((w - 8 - width, top, width, max(bottom - top, 120)))
        self.Show()
        self.DirectDraw()


class SnapButton(RectBox):

    GROUP_GAP = 13

    # left of TEMPO: where a click or a drag on the waveforms lands (the grid's beat, bar or
    # 4 bars, or anywhere); lit while it snaps. a click on it snaps or not (its unit kept),
    # its arrow the units (as HIGHLIGHT's and SHORT's lengths; the one key a menu before)
    # its widest label (SNAP 4 BARS, 64 px) 8 px in from either side (3 it was)
    LENGTH = 102
    FACE = (1, 2, 80, 19)
    # joined to it, their edge shared (an input group's); 20 wide as the rack bar's
    ARROW = (80, 2, 20, 19)

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.hovered = False
        self.SetBackgroundColour(uikit.ui().BAR_BG)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        # its unit named off too (what a click turns on)
        unit = self.parent.GetSnapUnit()
        label = dict((v[0], v[1]) for v in self.parent.SNAP_MODES)[unit]
        disabled = self.parent.IsStreamTrack()
        part, down = getattr(self, 'state', (None, None))
        on = self.parent.GetSnapMode() != 'off'
        uikit.draw_button(dc, self.FACE, label='SNAP %s' % (label.upper()), on=on,
                          hover=part == 'face', down=down == 'face', disabled=disabled,
                          corners='left')
        # its arrow turned over while the menu is open
        icon = 'up' if getattr(self, 'menu_open', False) else 'down'
        uikit.draw_button(dc, self.ARROW, icon=icon, on=on, hover=part == 'arrow',
                          down=down == 'arrow', disabled=disabled, corners='right')

    def GetPart(self, x, y):
        for part, (rx, ry, rw, rh) in (('face', self.FACE), ('arrow', self.ARROW)):
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return part
        return None

    def CATCH_EVT_GLOBAL(self, event):
        part = self.GetPart(event.X, event.Y) if self.onClient else None
        down = getattr(self, 'down', None) if event.LeftIsDown else None
        if (part, down) != getattr(self, 'state', (None, None)):
            self.state = (part, down)
            self.reInitBuffer = True
        if self.parent.parent.HasToSkipEvent():
            return
        if event.LeftDown is False or part is None or self.parent.IsStreamTrack():
            return
        self.down = part
        self.state = (part, part)
        self.reInitBuffer = True
        if part == 'face':
            self.parent.ToggleSnap()
            return
        menu = wx.Menu()
        for mode, label, _ in self.parent.SNAP_MODES[1:]:
            item = menu.AppendRadioItem(wx.ID_ANY, label)
            item.Check(mode == self.parent.GetSnapUnit())
            menu.Bind(wx.EVT_MENU, lambda e, mode=mode: self.Choose(mode), item)
        # under the key, from its face's left (a dropdown's)
        x, y, w, h = self.FACE
        self.menu_open = True
        self.DirectDraw()
        self.parent.parent.SetPopupMenu(menu, tuple(self.ClientToScreen((x, y + h + 2))),
                                        closed=self.MenuClosed)

    def MenuClosed(self):
        self.menu_open = False
        self.reInitBuffer = True

    def Choose(self, mode):
        # a unit chosen: snapping to it
        self.parent.SetSnapMode(mode)
        self.reInitBuffer = True

    def OnSize(self, event=None):
        w = self.parent.GetClientSize().width
        # its own group: a line between it and TEMPO (PlayBox.SetRectDraw)
        x = w - 5 - self.parent.GetVolumeRoom() - KeyButton.LENGTH\
            - TempoButton.LENGTH - self.GROUP_GAP - self.LENGTH
        # out of the way only when it would meet the transport keys on its row (prev, play,
        # next: the control strip's first 128 px)
        if x < PlayBoxControlButton.STRIP_X + 128 + self.GROUP_GAP:
            self.Hide()
            return
        self.Show()
        self.SetRect((x, self.parent.GetControlTop() + 5, self.LENGTH, 23))
        self.DirectDraw()


class PlayBoxTitle(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.last_rect = self.GetRect()
        self.title = ''
        self.buffer.fps = 30
        self.rect = wx.Rect(0, 0, 0, 0)
        title_type = GetPreference('play_title_format_type')
        if title_type is None:
            title_type = 0
        self.title_type = title_type
        self.subtitle = ''
        self.SetBackgroundColour(self.parent.st.PLAY_BG_COLOR)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.title = self.GetTitle()
        self.subtitle = self.GetSubtitle()
        self.DrawTitle(dc)

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        if self.IsInRect(self.rect, xy):
            return 1
        return None

    # the title's size: four steps under the dialogs' titles (uikit.TITLE, 16; 15 to 13
    # too: large beside the info's cells), the subtitle's a step under the list's (12)
    TITLE_SIZE = 12
    SUBTITLE_SIZE = 11

    def DrawTitle(self, dc):
        # in the header: the title large, the folder (or the station) under it; one line
        # in the compact header
        width, height = self.GetSize()
        st = self.parent.st
        compact = self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT
        font = uikit.get_font(uikit.BODY if compact else self.TITLE_SIZE, bold=True)
        dc.SetFont(font)
        title = self.title
        if dc.GetTextExtent(title)[0] > width:
            title = self.LimitTextLength(dc, title, width)
        tw, th = dc.GetTextExtent(title)
        # a pixel under the cover's top (flush with it, it looked to rise over it: the
        # cover's corners are round)
        y = (height - th) // 2 if compact else 1
        self.rect = wx.Rect(0, y, tw, th)
        dc.SetTextForeground(st.TITLE_FG_COLOR)
        dc.DrawText(title, 0, y)
        if compact or not self.subtitle:
            return
        dc.SetFont(uikit.get_font(self.SUBTITLE_SIZE))
        subtitle = self.subtitle
        if dc.GetTextExtent(subtitle)[0] > width:
            subtitle = self.LimitTextLength(dc, subtitle, width)
        dc.SetTextForeground(st.TITLE_DIM_COLOR)
        # (3 px under the title's descenders was tight, asked: 6 now)
        dc.DrawText(subtitle, 0, th + 4)

    def GetSubtitle(self):
        # the folder the file is in; a station's name under what it plays now
        if self.parent.IsStreamTrack():
            if radio.get_stream_title(self.parent.cue.hStream):
                return self.GetStationName()
            return 'Internet radio'
        if self.parent.cue.path is None:
            return ''
        return os.path.basename(os.path.dirname(self.parent.cue.path))

    def GetStationName(self):
        station = radio.get_station(self.parent.cue.path) or {}
        return station.get('name') or self.parent.cue.path

    def SetTitleType(self, title_type):
        self.title_type = title_type

    def GetTitle(self):
        if self.parent.IsStreamTrack():
            # what the station plays now, or its name
            return radio.get_stream_title(self.parent.cue.hStream) or self.GetStationName()
        if self.parent.cue.path is None:
            return ''
        if hasattr(self.parent.parent.parent, 'PlayBoxTitleFormat'):
            preset = self.parent.parent.parent.PlayBoxTitleFormat.preset
        else:
            preset = ['', '', '']
        # filename = os.path.splitext(os.path.basename(self.parent.cue.path))[0]
        title = []
        for field in preset:
            if field == '':
                title += ['']
            elif field.lower() == 'filename':
                title += [os.path.splitext(os.path.basename(self.parent.cue.path))[0]]
            else:
                title += [self.GetID3Tag(field.lower())]
        return ' :: '.join(title).strip(' :: ')
        # return ' - '.join(title).strip(' - ')

    def GetID3Tag(self, field):
        if hasattr(self.parent.parent, 'ListBox') is False:
            return ''
        if self.parent.cue.listId is None:
            return ''
        listId = self.parent.GetPlayingListIdx()
        if listId is None:
            return ''
        # by the cue's own columns (item_column: its row is made in them), not the playing
        # list's (a station's tab has its own order: an index of its put a number here)
        value = self.parent.GetPlayingItemInfo(field)
        return '' if value is None else '%s' % (value)

    def CATCH_EVT_GLOBAL(self, event):
        # if self.parent.parent.HasToSkipEvent(): return
        # self.HandleItemDrag(event)
        self.HandleTitleChange(event)

    def HandleTitleChange(self, event):
        title, subtitle = self.GetTitle(), self.GetSubtitle()
        if (title, subtitle) == (self.title, self.subtitle):
            return
        self.title, self.subtitle = title, subtitle
        self.DirectDraw()

    def HandleItemDrag(self, event):
        if event.drag.rectIdx is None:
            return
        self.parent.parent.SetItemDrag((self.parent.cue.path,))

    def GetTextLeft(self):
        # right of the cover when it is shown
        apic = self.parent.Apic
        if apic.IsShown() and apic.GetSize().width > 0:
            return apic.GetRect().GetRight() + 1 + PlayBoxApic.GAP
        return 8

    def GetTextRight(self):
        # the header's right end (the spectrum and the scope are the rack bar's now)
        return self.parent.GetDeckRight()

    def OnSize(self, event=None):
        left, right = self.GetTextLeft(), self.GetTextRight()
        if self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT:
            # the title, the info chips at the right (PlayBoxInfo)
            right = self.parent.Info.GetRect().x - 12
            self.SetRect((left, self.parent.GetHeaderTop() + 5, max(0, right - left), 23))
        else:
            # the title's capitals' top on the cover's top (PlayBoxApic.TOP), measured
            # (the title's capitals' top: its font's ink offset over its box)
            offset = int(round(uikit.get_caps_ink(uikit.get_font(self.TITLE_SIZE,
                                                                 bold=True))[0]))
            # down to the info's cells, not over them (40 tall it covered their top edge)
            self.SetRect((left, self.parent.GetHeaderTop() + PlayBoxApic.TOP - offset,
                          max(0, right - left), offset + PlayBoxApic.CELLS))
        self.DirectDraw()


class PlayBoxInfo(RectBox):

    # the cells let go when narrow, first to last (the time played always stays): the
    # time left, the key, the tempo
    HIDE_ORDER = (4, 1, 0)

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30

        self.information = GetPreference('playbox_information')
        if self.information is None:
            self.information = '000.0 | - | 00:00:00 | 00:00:00'
        self.segments = self.information.split(SEPARATOR)

        self.SetBackgroundColour(self.parent.st.PLAY_BG_COLOR)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.DrawInfo(dc)

    # the readouts as a rack's displays: a cell's recessed ground, its name dimmed and its
    # value in the display's ink
    # 5 px over and under the capitals inside (7 before: 22 tall); its row's slot 2 more
    CELL_HEIGHT = 18
    CELL_SLOT = CELL_HEIGHT + 2
    CELL_PAD = 7
    CELL_GAP = 6
    LABEL_GAP = 6

    def GetChips(self):
        # (index, name, value): the tempo, the key, the time played of the length, the time
        # left (to where the song moves on: its end, a highlight's or the edit's); a status
        # (Connecting) in the accent, index 3
        segments = list(self.segments) + [''] * (5 - len(self.segments))
        tempo, key, position, duration, remain = segments[:5]
        # the key as wide as its longest (C#m: the monospace's three), so the cells do not
        # move (nor their rows change) as the tempo moves the key heard (C, C#, C#m)
        # (a song's key not known, or none heard at WIDE's -100%: '-'; a station's: no cell)
        key = (key.strip() or '-').ljust(3) if key else ''
        chips = [(0, 'BPM', tempo.strip()), (1, 'KEY', key)]
        if duration.strip():
            chips += [(2, 'TIME', '%s / %s' % (position.strip(), duration.strip())),
                      (4, 'LEFT', remain.strip())]
        else:
            chips += [(3, '', position.strip())]
        return [v for v in chips if v[2]]

    def GetFonts(self):
        value = wx.Font(wx.Size(0, uikit.READOUT), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                        wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
        return value, uikit.get_font(uikit.LABEL, bold=True)

    def GetCellWidth(self, gc, chip):
        value, label = self.GetFonts()
        gc.SetFont(value, wx.BLACK)
        width = gc.GetTextExtent(chip[2])[0] + self.CELL_PAD * 2
        if chip[1]:
            gc.SetFont(label, wx.BLACK)
            width += gc.GetTextExtent(chip[1])[0] + self.LABEL_GAP
        return width

    # the cells kept together on a row: the song's (tempo, key) and its time (played, left)
    GROUPS = ((0, 1), (2, 4))

    def GetRows(self, gc, chips, width):
        # the cells in rows as wide as width, in their order, a group to the next row whole
        # (a group wider than the row alone broken there)
        groups = [[v for v in chips if v[0] in group] for group in self.GROUPS]
        groups += [[v] for v in chips if all(v[0] not in group for group in self.GROUPS)]
        rows, row, used = [], [], 0
        for group in [g for g in groups if g]:
            widths = [self.GetCellWidth(gc, chip) for chip in group]
            whole = sum(widths) + self.CELL_GAP * (len(widths) - 1)
            if row and used + self.CELL_GAP + whole > width:
                rows.append(row)
                row, used = [], 0
            for chip, w in zip(group, widths):
                if row and used + self.CELL_GAP + w > width:
                    rows.append(row)
                    row, used = [], 0
                used += (self.CELL_GAP if row else 0) + w
                row.append(chip)
        return rows + ([row] if row else [])

    # the cells a song has, at their widest: the rows counted by them whatever plays (a
    # station's one cell made the header a row shorter, and taller again with a song)
    SONG_CELLS = ((0, 'BPM', '000.0'), (1, 'KEY', 'C#m'), (2, 'TIME', '00:00.00 / 00:00.00'),
                  (4, 'LEFT', '-00:00.00'))

    def GetRowCount(self, width):
        bitmap = wx.Bitmap(1, 1)
        dc = wx.MemoryDC(bitmap)
        gc = wx.GraphicsContext.Create(dc)
        count = max(len(self.GetRows(gc, self.SONG_CELLS, width)), 1)
        del gc
        dc.SelectObject(wx.NullBitmap)
        return count

    def GetFittingChips(self, gc):
        # the cells that fit the width, the time left, the key and then the tempo let go
        chips = self.GetChips()
        width = self.GetSize().width
        for index in (None,) + self.HIDE_ORDER:
            if index is not None:
                chips = [v for v in chips if v[0] != index]
            if self.GetChipsWidth(gc, chips) <= width:
                break
        return chips

    def GetChipsWidth(self, gc, chips):
        widths = [self.GetCellWidth(gc, chip) for chip in chips]
        return sum(widths) + self.CELL_GAP * max(0, len(widths) - 1)

    def DrawInfo(self, dc):
        # the cells left-aligned under the title, right-aligned in the compact header
        st = self.parent.st
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        width, height = self.GetSize()
        if self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT:
            # one row at the right, the cells let go that do not fit
            chips = self.GetFittingChips(gc)
            rows = [(width - self.GetChipsWidth(gc, chips), (height - self.CELL_HEIGHT) // 2,
                     chips)]
        else:
            # under the title, a row more for the cells that do not fit
            pad = (self.CELL_SLOT - self.CELL_HEIGHT) // 2
            rows = [(0, k * self.parent.INFO_ROW + pad, row)
                    for k, row in enumerate(self.GetRows(gc, self.GetChips(), width))]
        for x, y, chips in rows:
            self.DrawCells(gc, x, y, chips)

    def GetInkTop(self, font, y):
        # the font's capitals' middle on the cell's inside (its edge's rows left out), on a
        # whole row, a half one down (round() took 146.5 to 146: the names a pixel high)
        return int(math.floor(uikit.get_caps_top(font, y + 1, self.CELL_HEIGHT - 2) + 0.5))

    def DrawCells(self, gc, x, y, chips):
        st = self.parent.st
        value_font, label_font = self.GetFonts()
        tokens = uikit.ui()
        failed = bool(self.parent.GetStreamFailure())
        for chip in chips:
            index, label, text = chip
            w = self.GetCellWidth(gc, chip)
            face, edge, ink = st.LCD_BG_COLOR, st.RACK_EDGE_COLOR, st.LCD_TEXT_COLOR
            if index == 3:
                # connecting in the accent, not connected warned (orange)
                face, ink = (tokens.WARN, tokens.WARN_FG) if failed else\
                    (tokens.ACCENT, tokens.ACCENT_FG)
                edge = face
            gc.SetPen(wx.Pen(wx.Colour(edge), 1))
            gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(face))))
            # (every box's corners uikit.RADIUS: the cells' were 2, the keys' 3)
            gc.DrawRoundedRectangle(x + 0.5, y + 0.5, w - 1, self.CELL_HEIGHT - 1,
                                    uikit.RADIUS)
            tx = x + self.CELL_PAD
            if label:
                # the name on the value's capitals' middle
                gc.SetFont(label_font, wx.Colour(st.RACK_LABEL_COLOR))
                gc.DrawText(label, tx, self.GetInkTop(label_font, y))
                tx += gc.GetTextExtent(label)[0] + self.LABEL_GAP
            # the value's capitals (its digits) centred too, not its text box: it sat a pixel
            # high, 5 px over it and 7 under (measured)
            gc.SetFont(value_font, wx.Colour(ink))
            gc.DrawText(text, tx, self.GetInkTop(value_font, y))
            x += w + self.CELL_GAP

    def CATCH_EVT_GLOBAL(self, event):
        self.HandleInfoChange(event)

    def HandleInfoChange(self, event=None):
        # autogain = self.parent.cue.autogain
        # decibel =  autogain/0.14
        key = self.parent.GetPlayingKey()
        tempo = self.parent.GetPlayingTempo()
        if key == '':
            key = ' '
        if key == '-':
            # error = True
            key = ' '
        if key == '':
            key = ' '
        if tempo == '':
            tempo = 000.0
        if len(key) == 2:
            key = key + ' '
        elif len(key) == 1:
            key = key + '  '
        # none known (a station that did not open, a cue being opened): 0
        pos_sec, dur_sec = (
            self.parent.GetPositionTime() or 0.0, self.parent.cue.duration or 0.0)
        duration = '%02d:%02d.%02d' % (dur_sec / 60, dur_sec % 60, dur_sec % 1 * 100)
        position = '%02d:%02d.%02d' % (pos_sec / 60, pos_sec % 60, pos_sec % 1 * 100)
        # left: to where it moves on (the song's end, or a highlight's, or the edit's)
        finish = self.parent.GetTrackFinishTime()
        if not finish or finish < 0:
            finish = dur_sec
        left = max(finish - pos_sec, 0.0)
        remain = '-%02d:%02d.%02d' % (left / 60, left % 60, left % 1 * 100)
        segments = ['%05.1f' % tempo, key, position, duration, remain]
        if self.parent.IsStreamTrack():
            # a station: how long it has played, live (no tempo, no key, no length); while
            # it connects, for how long (a second at a time, nothing moving)
            segments = ['', '', position, 'LIVE']
            connecting = self.parent.GetStreamConnecting()
            if connecting is not None:
                segments = ['', '', 'Connecting %ds' % (int(connecting)), '']
            elif self.parent.GetStreamFailure():
                segments = ['', '', 'Not connected', '']
        information = SEPARATOR.join(segments)
        if information == self.information:
            return
        self.segments = segments
        self.information = information
        self.DirectDraw()

    def OnSize(self, event):
        # under the title in the header; at the right end of the compact header
        w = self.parent.GetClientSize().width
        title = self.parent.Title
        if self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT:
            width = max(0, min(300, w // 2))
            right = self.parent.GetDeckRight()
            self.SetRect((right - width, self.parent.GetHeaderTop() + 5, width, 23))
        else:
            left, right = title.GetTextLeft(), title.GetTextRight()
            rows = getattr(self.parent, 'header_rows', 1)
            # its last row's cells' bottom on the cover's bottom (PlayBoxApic.GetCoverSize)
            self.SetRect((left, self.parent.GetHeaderTop() + PlayBoxApic.TOP
                          + PlayBoxApic.CELLS, max(0, right - left),
                          PlayBoxInfo.CELL_SLOT + (rows - 1) * self.parent.INFO_ROW))
        self.DirectDraw()


class PlayBoxApic(RectBox):

    # the cover as tall as the text beside it, edge to edge: the title's capitals' top to
    # the info's last row's cells' bottom (72 centred in the header before, out of line
    # with both; 65 to the first row's, the rows after it under it), 13 px under the rack
    # and over the waveforms. CELLS: the cells' top under it (the subtitle 6 px over them,
    # 10 before)
    # 8 px round it every way, the window's gutter at its left: under the rack, over the
    # waveforms' frame, before the text (13, then 10 before)
    TOP = 8
    GAP = 8
    CELLS = 33
    SIZE = CELLS + PlayBoxInfo.CELL_SLOT

    @classmethod
    def GetCoverSize(cls, rows=1):
        return cls.SIZE + (rows - 1) * PlayBox.INFO_ROW

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.margin = 2
        self.size = 118
        self.apic = None
        self.path = None
        self.buffer.fps = 30
        self.last_size = self.size

        show_left = GetPreference('apic_show_left')
        if show_left is None:
            self.left = True
        else:
            show_left = show_left
        self.overlap_mask = images.apicoverlapmask.GetBitmap()

        self.SetSize((self.size, self.size))
        self.InitBuffer()

    def IsStreamImage(self, stream):
        # http://www.wxpython.org/docs/api/wx.ImageHandler-class.html#SetType
        # ICO too: a radio station's picture is often its favicon
        for v in ('JPEG', 'BMP', 'PNG', 'GIF', 'ICO'):
            # exec('handler = wx.%sHandler()' % (v))
            # handler = eval('wx.%sHandler()' % (v))
            if hasattr(wx, v + 'Handler'):
                handler = getattr(wx, v + 'Handler')()
                if hasattr(handler, 'CanRead') and handler.CanRead(stream):
                    handler.Destroy()
                    return True
                handler.Destroy()
        return False

    def GetApic(self, path):
        # access APIC frame and grab the image
        # mutagen can automatically detect format and type of tags
        # APIC:cover.jpg, APIC:Cover Image, APIC:desc, APIC:
        if isinstance(path, tuple):
            # a station: its picture (radio.get_picture)
            return self.GetApicBitmap(path[2]), path

        try:
            file = mutagen.File(path)
            key = [v for v in file.tags.keys() if 'APIC:' in v]
            if key == []:
                return None, path
            artwork = file.tags[key[0]].data
        except Exception:
            return None, path
        return self.GetApicBitmap(artwork), path

    def GetApicBitmap(self, artwork):
        # the picture's bytes scaled into the box, or None
        if not artwork:
            return None
        buf = io.BytesIO(artwork)
        if self.IsStreamImage(buf) is False:
            buf.close()
            return None
        im = Image.open(buf)
        if 'icc_profile' in im.info:
            im.info.pop('icc_profile')
            rebuf = io.BytesIO()
            im.save(rebuf, 'PNG')
            rebuf.seek(0)
            bmp = wx.Image(rebuf)
            rebuf.close()
        else:
            buf.seek(0)
            bmp = wx.Image(buf)
        buf.close()
        ratio = 1.0 * bmp.GetWidth() / bmp.GetHeight()
        width, height = self.GetClientSize()
        w = width - self.margin * 2
        h = height - self.margin * 2
        if ratio < 1:
            w = int(round(w * ratio))
        elif ratio > 1:
            h = int(round(h / ratio))
        if w <= 0 or h <= 0:
            return None
        bmp = bmp.Rescale(w, h, quality=wx.IMAGE_QUALITY_HIGH)
        bmp = bmp.ConvertToBitmap()
        return bmp

    def GetApicThread(self):
        bmp, path = self.GetApic(self.path)
        if path != self.path:
            return
        self.apic = bmp
        self.reInitBuffer = True
        # self.DirectDraw()

    def SetRectPre(self):
        pass

    def SetRectDraw(self, dc):
        self.DrawApic(dc)

    def CATCH_EVT_GLOBAL(self, event):
        self.HandleApicChange()
        # self.HandleSizeChange()

    def DrawApic(self, dc):
        # rounded by a clip (the overlay mask was a 150 px picture for one size); no
        # picture: a record's label
        width, height = self.GetClientSize()
        st = self.parent.st
        dc.SetBackground(wx.Brush(st.PLAY_BG_COLOR))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None or width <= 0 or height <= 0:
            return
        path = gc.CreatePath()
        # the waveforms' frame's corners (uikit.RADIUS; 6 before)
        path.AddRoundedRectangle(0, 0, width, height, uikit.RADIUS)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(st.APIC_BG_COLOR if self.apic else st.CHIP_BG_COLOR)))
        gc.FillPath(path)
        if self.apic is None:
            gc.SetBrush(gc.CreateBrush(wx.Brush(st.APIC_PN_COLOR)))
            r = width * 0.3
            gc.DrawEllipse(width / 2.0 - r, height / 2.0 - r, r * 2, r * 2)
            return
        w, h = self.apic.GetSize()
        gc.DrawBitmap(self.apic, (width - w) / 2.0, (height - h) / 2.0, w, h)
        # the corners cut back to the ground
        corners = gc.CreatePath()
        corners.AddRectangle(0, 0, width, height)
        corners.AddRoundedRectangle(0, 0, width, height, uikit.RADIUS)
        gc.SetBrush(gc.CreateBrush(wx.Brush(st.PLAY_BG_COLOR)))
        gc.FillPath(corners, wx.ODDEVEN_RULE)

    def GetApicSource(self):
        # the track's file; a station's address and picture (read once, None till then)
        if self.parent.IsStreamTrack():
            url = self.parent.cue.path
            return ('radio', url, radio.get_picture(url))
        return self.parent.cue.path

    def HandleApicChange(self, forced=False):
        source = self.GetApicSource()
        if source == self.path and forced is False:
            return
        self.apic = None
        self.path = source
        if hasattr(self, 'Thread') and self.Thread.is_alive():
            # print(dir(self.Thread))
            self.Thread._delete()
            # self.Thread._set_tstate_lock()
            # self.Thread._stop()
            # self.Thread._Thread__stop()
        self.Thread = threading.Thread(
            target=self.GetApicThread, name='apic', args=())
        self.Thread.start()

    def HandlePopupMenu(self, event):
        if event.rectIdx is None:
            return
        if event.RightUp is False:
            return
        if event.down.rectIdx is None:
            return
        # self.parent.parent.SetPopupMenu(PlayBoxPopupApic(self), (event.x, event.y))

    def OnSize(self, event=None):
        # the header's left, beside the title; not in the compact header
        if self.parent.parent.parent.IsPlayerSideShowOn() is False\
                or self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT:
            self.SetRect((0, 0, 0, 0))
            self.Hide()
            return
        self.margin = 0
        size = self.GetCoverSize(getattr(self.parent, 'header_rows', 1))
        x, y = (8, self.parent.GetHeaderTop() + self.TOP)
        self.SetRect((x, y, size, size))
        if size != self.last_size:
            self.HandleApicChange(forced=True)
        else:
            self.HandleApicChange()
        self.last_size = size
        self.DirectDraw()
        self.Show()


class PlayBoxSpectrum(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.scale = 1
        self.max_scale = 3
        # (300 at most, the header's)
        self.max_width = 300
        self.width = 320 * self.scale
        self.height = 30
        self.resolution = 1
        self.saturation = 0.1
        self.bar_pitch = 3
        self.bar_width = 1

        fps = GetPreference('spectrum_fps')
        if fps is None:
            fps = 60
        self.buffer.fps = fps

        self.ground = ((0, 0, 0, 0),)
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        # self.InitGround()
        self.InitBuffer()

    def InitGround(self):
        w, h = (self.width, self.height)
        len_spectrum = 103 * self.scale
        spLength = len_spectrum - 1
        sw = int(1.0 * w / spLength)
        offset = (w - sw * spLength) * 0.5
        ground = [(sw * i + offset + 1, h / 2 - 1) for i in range(len_spectrum)]
        ground += [(sw * i + offset + 1, h / 2) for i in range(len_spectrum)]
        self.ground = ground

    def SetRectPre(self):
        pass

    def CATCH_EVT_GLOBAL(self, event):
        # while playing the visual clock draws it (PlayBoxVisualClock)
        if self.parent.IsVisualPlaying() is False:
            self.DirectDraw()

    def GetSpectrumVectorScope(self):
        if self.parent.IsVisualPlaying() is False:
            return None, None
        if self.IsShown() is False and self.parent.VectorScope.IsShown() is False:
            return None, None
        hstream, channel, autogain = self.parent.GetVisualStream()
        return audio.get_stream_spectrum_vectorscope(
            hstream, self.parent.VectorScope.size, channel, autogain,
            spectrum_scale=self.scale)

    def SetRectDraw(self, dc):
        spectrum, vectorscope = self.GetSpectrumVectorScope()
        if spectrum is None:
            self.DrawSpectrumGround(dc)
            return
        self.DrawSpectrumHTB(dc, spectrum)
        if hasattr(self.parent, 'VectorScope'):
            self.parent.VectorScope.SetSamples(vectorscope)

    def DrawSpectrumGround(self, dc):
        color = self.parent.st.SPECTRUM_BG_COLOR
        dc.DrawRectangleList(self.ground, pens=wx.Pen(color, 1),
                             brushes=wx.Brush(color))

    def DrawSpectrumHTB(self, dc, spectrum):
        # the ground and the bars as one picture: drawn a rectangle at a time
        # (DrawRectangleList) they took about 4 ms a frame, most of the visualizers'
        w, h = self.GetSize()
        if w <= 0 or h <= 0:
            return
        scale = 0.4
        xs = numpy.array(self.GetBarSlots(w))
        levels = self.FitBarLevels(spectrum, len(xs))
        talls = (levels * h * scale).astype(int)
        # a bar a pixel tall was not drawn as a rectangle: not drawn here either
        talls[talls < 2] = 0
        tops = ((h - levels * h * scale) * 0.5).astype(int)
        image = numpy.empty((h, w, 3), dtype=numpy.uint8)
        image[:] = wx.Colour(self.GetBackgroundColour()).Get()[:3]
        top = int(h / 2 - 1)
        for x in range(self.bar_width):
            image[top:top + 2, xs + x] = wx.Colour(self.parent.st.SPECTRUM_BG_COLOR).Get()[:3]
        rows = numpy.arange(h)[:, None]
        bars = (rows >= tops) & (rows < tops + talls)
        for x in range(self.bar_width):
            columns = image[:, xs + x]
            columns[bars] = wx.Colour(self.parent.st.SPECTRUM_FG_COLOR).Get()[:3]
            image[:, xs + x] = columns
        dc.DrawBitmap(wx.Bitmap.FromBuffer(w, h, image.tobytes()), 0, 0)

    def GetBarSlots(self, w):
        # a bar every bar_pitch pixels from one end of the box to the other
        count = max(2, int(w - 1) // self.bar_pitch + 1)
        offset = (int(w) - 1 - self.bar_pitch * (count - 1)) // 2
        return [offset + self.bar_pitch * i for i in range(count)]

    def FitBarLevels(self, levels, count):
        # more slots than bins: joined linearly between neighbours,
        # fewer: the largest of the bins falling into each slot
        levels = numpy.asarray(levels, dtype=float)
        length = len(levels)
        if length < 2:
            return numpy.resize(levels, count)
        if count >= length:
            return numpy.interp(numpy.linspace(0, length - 1, count),
                                numpy.arange(length), levels)
        edges = numpy.linspace(0, length, count + 1).astype(int)
        return numpy.maximum.reduceat(levels, edges[:-1])

    def OnSize(self, event=None):
        # in ANALYZER's BARS part (PlayBox.LayoutAnalyzerVisuals)
        self.parent.LayoutAnalyzerVisuals()

    def Place(self, rect):
        if rect is None:
            self.SetRect((0, 0, 0, 0))
            self.Hide()
            return
        width, height = rect.width, rect.height
        # the bins follow the width, the bars are fitted to it (FitBarLevels)
        scale = int(round(width / 320.0))
        scale = 1 if scale < 1 else scale
        scale = self.max_scale if scale > self.max_scale else scale
        if self.scale != scale or self.width != width or self.height != height:
            self.scale = scale
            self.width = width
            self.height = height
            self.InitGround()
        self.SetRect(rect)
        self.Show()
        w, h = self.GetSize()
        self.ground = [wx.Rect(x, int(h / 2 - 1), self.bar_width, 2)
                       for x in self.GetBarSlots(w)]
        self.DirectDraw()


class PlayBoxVectorScope(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        fps = GetPreference('vectorscope_fps')
        if fps is None:
            fps = 60
        self.buffer.fps = fps
        # a square, no border, the L and R axes as an X; as tall as ANALYZER's BARS part
        # (Place)
        self.size = 56
        self.margin = 2
        self.vectorscope = None
        # the dots of the frames before stay and fade like on a phosphor screen
        # (persist and dot are a frame's at 30 fps), the gain follows the track
        # slowly so that the dots fill the scope whether it is loud or quiet
        self.persist = 0.55
        self.dot = 0.30
        self.gain = 1.0
        self.glow = None
        self.glow_lap = 0
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def GetVectorScope(self):
        if self.parent.IsVisualPlaying() is False:
            self.vectorscope = None
            return
        if self.parent.Spectrum.IsShown() is False:
            # the spectrum stepped aside (a narrow window): its frame read here (it gave the
            # scope its samples; without it the scope stood still)
            _, samples = self.parent.Spectrum.GetSpectrumVectorScope()
            self.SetSamples(samples)
        return self.vectorscope

    def SetSamples(self, samples):
        if samples is None:
            self.glow = None
            self.vectorscope = None
            return
        w = h = self.size
        now = time.time()
        frames = 1.0
        if self.glow is None or self.glow.shape != (h, w):
            self.glow = numpy.zeros((h, w), dtype='float32')
        else:
            frames = min(6.0, max(0.0, now - self.glow_lap) * 30)
        self.glow_lap = now
        persist = self.persist ** frames
        self.glow *= persist
        left, right = samples
        energy = float(numpy.sqrt((left ** 2 + right ** 2).mean()))
        target = min(8.0, 0.35 / max(energy, 1e-4))
        self.gain += (target - self.gain) * (1 - 0.85 ** frames)
        if energy >= 1e-5:
            radius = (0.5 * w - 2) * self.gain
            side = (right - left) * 0.7071 * radius
            mid = (right + left) * 0.7071 * radius
            xs = numpy.clip(0.5 * w + side, 0, w - 1).astype(int)
            ys = numpy.clip(0.5 * h - mid, 0, h - 1).astype(int)
            hits = numpy.bincount(ys * w + xs, minlength=w * h).reshape(h, w)
            dot = self.dot * (1 - persist) / (1 - self.persist)
            self.glow += hits * dot
            numpy.minimum(self.glow, 1.0, out=self.glow)
        self.vectorscope = None if self.glow.max() < 0.02 else self.GetGlowBitmap()

    def GetGlowBitmap(self):
        # one bitmap of the brightness, not a point at a time
        h, w = self.glow.shape
        bgcolor = wx.Colour(self.parent.st.VECTORSCOPE_BG_COLOR).Get()[:3]
        fgcolor = wx.Colour(self.parent.st.VECTORSCOPE_FG_COLOR).Get()[:3]
        bgcolor = numpy.array(bgcolor, dtype='float32')
        fgcolor = numpy.array(fgcolor, dtype='float32')
        rgb = (bgcolor + (fgcolor - bgcolor) * self.glow[..., None]).astype('uint8')
        alpha = (numpy.minimum(1.0, self.glow * 4) * 255).astype('uint8')
        return wx.Bitmap.FromBufferRGBA(w, h, numpy.dstack([rgb, alpha[..., None]]).tobytes())

    def SetRectDraw(self, dc):
        if self.parent.IsVisualPlaying() is False:
            self.SetSamples(None)
            self.DrawVectorScope(dc, None)
            return
        self.DrawVectorScope(dc, self.GetVectorScope())

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.IsVisualPlaying() is False:
            self.DirectDraw()

    def DrawVectorScope(self, dc, vectorscope):
        bgcolor = self.parent.st.VECTORSCOPE_BG_COLOR
        pncolor = self.parent.st.VECTORSCOPE_PN_COLOR
        w, h = (self.size, self.size)
        dc.SetBrush(wx.Brush(bgcolor))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(0, 0, w, h)
        dc.SetPen(wx.Pen(pncolor, 1))
        dc.DrawLine(0, 0, w, h)
        dc.DrawLine(w - 1, 0, -1, h)
        if vectorscope is None:
            return
        dc.DrawBitmap(vectorscope, 0, 0, True)

    def OnSize(self, event=None):
        # in ANALYZER's BARS part (PlayBox.LayoutAnalyzerVisuals)
        self.parent.LayoutAnalyzerVisuals()

    def Place(self, rect):
        if rect is None:
            self.SetRect((0, 0, 0, 0))
            self.Hide()
            return
        # as big as the part is tall (its picture's size: SetSamples)
        self.size = rect.width
        self.SetRect(rect)
        self.Show()
        self.DirectDraw()


class PlayBoxWave(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.position = 0.0
        self.height = 40
        self.margin = 5
        self.buffer.fps = 60
        self.cursor_width = 4
        self.highlight_dim = 0.45
        self.wave_rect = (0, 0, 0, 0)
        self.wave_bitmaps = None
        self.wave_exact = None
        self.wave_source = None
        self.wave_job = 0
        self.resize_timer = None
        self.last_size = self.GetSize()
        self.rectHighlight = (0, 0, 0, 0)
        self.SetDropTarget(PlayBoxDnD(self.parent))
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def OnSize(self, event):
        if self.parent.parent.parent.IsPlayerSideShowOn():
            if self.parent.parent.parent.IsPlayerTopShowOn():
                # apic_pad = self.parent.Apic.GetSize().width+10
                apic_pad = 119 + 13
            else:
                apic_pad = 59 + 13
        else:
            apic_pad = 0
        apic_pad = 0
        _, cy, _, ch = self.parent.ControlButton.GetRect()
        w, h = self.parent.GetSize()
        # vol_align = 12
        isTopShowOn = self.parent.parent.parent.IsPlayerTopShowOn()
        isSideShowOn = self.parent.parent.parent.IsPlayerSideShowOn()
        # leftPad, rightPad = (13, 25 + 5)
        leftPad, rightPad = (13, 10)
        if isSideShowOn:
            leftPad = 8
        elif isSideShowOn and isTopShowOn:
            leftPad = 13

        # the frame (4 px around) 8 px from the window's edges (or from the tempo strip)
        leftPad = 12
        rightPad = self.parent.GetClientSize().width - self.parent.GetDeckRight() + 4

        # over the control row
        x, y = (leftPad, self.parent.GetControlTop() - self.parent.WAVE_BOTTOM_GAP - self.height)
        # x, y = (leftPad, cy-self.height-15)
        if self.parent.Apic.left:
            rect = (x + apic_pad, y, w - (leftPad + rightPad + apic_pad), self.height)
        else:
            rect = (x, y, w - (leftPad + rightPad + apic_pad), self.height)
        if rect == self.last_size:
            return
        self.last_size = rect
        self.SetRect(rect)
        # while the window is resized the last waveform is stretched to it, and
        # painted again for the width once the resizing stops: painted at every
        # step it took 18 ms a step for a song and 140 ms for a two-hour mix
        if self.wave_exact is None:
            self.parent.reInitWave = True
        else:
            self.StretchWave()
            if self.resize_timer is None:
                self.resize_timer = wx.CallLater(150, self.OnResized)
            else:
                self.resize_timer.Start(150)
        self.DirectDraw()

    def SettleNow(self):
        # a single step's new width (TEMPO, KEY shown or hidden): the waveforms painted for
        # it now (the strip's scale too), no stretch and no repaint after
        if self.resize_timer is not None:
            self.resize_timer.Stop()
        if self.wave_source is not None:
            self.SetRectWave(now=True)
            self.SetRectHighlight()
        self.InitBuffer()
        self.Refresh(False)
        self.parent.WaveDetail.InitBuffer()
        self.parent.WaveDetail.Refresh(False)

    def OnResized(self):
        # the window can be gone by then
        if not self:
            return
        self.parent.reInitWave = True
        self.InitBuffer()
        self.Refresh(False)
        self.parent.WaveDetail.InitBuffer()
        self.parent.WaveDetail.Refresh(False)

    def IsResizing(self):
        return self.resize_timer is not None and self.resize_timer.IsRunning()

    def GetWaveRect(self):
        # with the grid shown, a lane above and below for its ticks (as the strip's)
        w, h = self.GetSize()
        x, y = (self.margin, 2)
        lane = PlayBoxWaveDetail.GRID_LANE if self.parent.IsGridShown() else 0
        return (x, y + lane, w - x * 2, h - y * 2 - 1 - lane * 2)

    def StretchWave(self):
        x, y, w, h = self.GetWaveRect()
        if w <= 0 or h <= 0:
            return
        self.wave_rect = (x, y, w, h)
        self.wave_bitmaps = [wx.Bitmap(bitmap.ConvertToImage().Scale(w, h, wx.IMAGE_QUALITY_NORMAL))
                             for bitmap in self.wave_exact]
        self.SetRectHighlight()

    def SetRectPre(self):
        if self.parent.reInitWave is True:
            self.parent.reInitWave = False
            self.SetRectWave()
            self.SetRectHighlight()

    def SetRectDraw(self, dc):
        # the radio playing alone: what it plays, the last half minute
        if draw_live_trace(dc, self.parent, self.wave_rect, radio.TRACE_SECONDS):
            return
        draw_highlight = self.parent.IsHighlightKnown()\
            and self.parent.IsHighlightOn()\
            and self.parent.IsHighlightSkipOn() is False
        if draw_highlight:
            self.DrawHighlightWave(dc)
        elif self.parent.IsRadioEditActive() and self.wave_bitmaps is not None:
            self.DrawEditWave(dc)
        else:
            self.DrawNormalWave(dc)
        self.DrawPlayedLanes(dc)
        self.DrawGridLines(dc)
        self.DrawSnapFlash(dc)
        self.DrawCursor(dc)
        self.DrawPressMarker(dc)

    def DrawSnapFlash(self, dc):
        # the line a seek snapped to, lit a moment (drawn again till it fades)
        flash = self.parent.GetSnapFlash()
        duration = self.parent.GetDurationTime()
        if flash is None or duration <= 0:
            return
        x, y, w, h = self.wave_rect
        draw_snap_flash(dc, int(math.ceil(x + flash[0] * w / duration)), 0,
                        self.GetSize().height, flash[1])
        self.redraw_next = True

    def DrawPlayedLanes(self, dc):
        # the grid's lanes over what the highlight or SHORT plays, tinted (LANE_PLAYED)
        ranges = self.parent.GetPlayedRanges()
        duration = self.parent.GetDurationTime()
        if not ranges or duration <= 0 or self.parent.IsGridShown() is False:
            return
        x, y, w, h = self.wave_rect
        lane = PlayBoxWaveDetail.GRID_LANE
        colour = wx.Colour(*get_lane_played(self.parent.st))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(colour))
        for a, b in ranges:
            left = int(math.ceil(a * w / duration))
            right = min(int(math.ceil(b * w / duration)), w)
            if right <= left:
                continue
            dc.DrawRectangle(x + left, y - lane, right - left, lane)
            dc.DrawRectangle(x + left, y + h, right - left, lane)

    def DrawGridLines(self, dc):
        # every 16 bars across the whole song (each bar would run together), brighter in
        # the lanes above and below it; every 4 bars there too when they are 6 px apart.
        # counted from the first phrase's start when it is known, else from the first
        # downbeat (as the strip's bar numbers): then in the lanes alone, no line across
        grid = self.parent.GetGrid()
        duration = self.parent.GetDurationTime()
        if grid is None or duration <= 0 or self.wave_bitmaps is None\
                or self.parent.IsGridShown() is False:
            return
        known = self.parent.IsGridPhraseKnown()
        anchor = self.parent.GetGridPhraseStart() if known else self.parent.GetGridDownbeat()
        x, y, w, h = self.wave_rect
        span = 60.0 / grid.bpm * 64
        if span / duration * w < 6:
            return
        bg = wx.Colour(self.parent.st.PLAY_BG_COLOR)

        def light(share):
            return wx.Colour(*[int(v + (255 - v) * share) for v in (bg.Red(), bg.Green(), bg.Blue())])

        lane = PlayBoxWaveDetail.GRID_LANE
        bottom = y + h
        # 4 bars a step (the 16 bars are 4 of them)
        phrase = span / 4
        seconds = anchor % phrase
        index = -int(round((anchor - seconds) / phrase))
        while seconds < duration:
            lx = int(x + seconds * w / duration)
            if index % 4 == 0:
                if known:
                    dc.SetPen(wx.Pen(light(0.35), 1))
                    dc.DrawLine(lx, y, lx, bottom)
                dc.SetPen(wx.Pen(light(0.9), 1))
                dc.DrawLine(lx, y - lane, lx, y)
                dc.DrawLine(lx, bottom, lx, bottom + lane)
            elif phrase / duration * w >= 6:
                dc.SetPen(wx.Pen(light(0.5), 1))
                dc.DrawLine(lx, y - lane, lx, y - lane // 2)
                dc.DrawLine(lx, bottom + lane // 2, lx, bottom + lane)
            seconds += phrase
            index += 1

    def DrawNormalWave(self, dc):
        if self.wave_bitmaps is None:
            self.DrawFlatWave(dc, self.parent.st.WAVEFORM_FG_COLOR)
            return
        x, y, w, h = self.wave_rect
        dc.DrawBitmap(self.wave_bitmaps[0], x, y)

    def DrawFlatWave(self, dc, color):
        x, y, w, h = self.wave_rect
        cy = int(h * 0.5 + y)
        dc.SetPen(wx.Pen(color, 1))
        dc.DrawLine(x, cy, x + w, cy)

    def DrawClippedWave(self, dc, bitmap, start, end):
        x, y, w, h = self.wave_rect
        start, end = (max(int(start), 0), min(int(end), w))
        if end <= start:
            return
        dc.SetClippingRegion(x + start, y, end - start, h)
        dc.DrawBitmap(bitmap, x, y)
        dc.DestroyClippingRegion()

    def SetRectHighlight(self):
        # none left from the track before when this one has none
        self.rectHighlight = (0, 0, 0, 0)
        if self.parent.IsHighlightKnown() is False:
            return
        duration = self.parent.GetDurationTime()
        if duration <= 0.0:
            return
        offset, period = self.parent.GetHighlightTime()
        if offset is None or period is None:
            return
        _, _, width, _ = self.wave_rect
        # the cursor's rounding (DrawCursor: ceil), so it sits on the edge it goes to
        x = int(math.ceil(offset * width / duration))
        if period == 0:
            xw = width
        else:
            xw = min(int(math.ceil((offset + period) * width / duration)), width)
        # if x == 0:
        #     x = 1
        _, height = self.GetSize()
        self.rectHighlight = (x + self.margin, 0, xw - x, height)

    def DrawEditWave(self, dc):
        # SHORT (the radio edit): what it skips (the intro, the outro, the breakdowns' cuts) dimmed as
        # outside a highlight, what it plays in full
        x, y, w, h = self.wave_rect
        duration = self.parent.GetDurationTime()
        dc.DrawBitmap(self.wave_bitmaps[1], x, y)
        if duration <= 0:
            return
        start, end, cuts = self.parent.GetRadioEdit()
        bounds = [start] + [v for cut in cuts for v in cut] + [end]
        # what it plays on the highlight's ground, as the highlight's (the wave in full)
        color = self.parent.st.HIGHLIGHT_BG_COLOR
        dc.SetPen(wx.Pen(color, 1))
        dc.SetBrush(wx.Brush(color))
        for a, b in zip(bounds[0::2], bounds[1::2]):
            left, right = math.ceil(a * w / duration), math.ceil(b * w / duration)
            if right > left:
                dc.DrawRectangle(int(x + left), 0, int(right - left), self.GetSize().height)
            self.DrawClippedWave(dc, self.wave_bitmaps[2], left, right)

    def DrawHighlightWave(self, dc):
        if self.wave_bitmaps is None:
            self.DrawFlatWave(dc, self.parent.st.HIGHLIGHT_PN_COLOR)
            return
        # outside dimmed, inside in full on the highlight ground
        x, y, w, h = self.wave_rect
        dc.DrawBitmap(self.wave_bitmaps[1], x, y)
        start = max(self.rectHighlight[0] - self.margin, 0)
        end = min(start + self.rectHighlight[2], w)
        if end <= start:
            return
        color = self.parent.st.HIGHLIGHT_BG_COLOR
        dc.SetPen(wx.Pen(color, 1))
        dc.SetBrush(wx.Brush(color))
        dc.DrawRectangle(int(x + start), 0, int(end - start), self.GetSize().height)
        self.DrawClippedWave(dc, self.wave_bitmaps[2], start, end)

    def DrawCursor(self, dc):
        w, h = self.GetSize()
        slidable = w - self.margin * 2
        position = self.parent.GetPositionTime()
        duration = self.parent.GetDurationTime()
        if duration == 0:
            x_ratio = 0.0
        else:
            x_ratio = 1.0 * position / duration

        bgcolor = self.parent.st.PLAYCURSOR_BG_COLOR
        fgcolor = self.parent.st.PLAYCURSOR_FG_COLOR
        stroke = self.parent.st.PLAYCURSOR_STROKE
        dc.SetBrush(wx.Brush(bgcolor))
        dc.SetPen(wx.Pen(fgcolor, stroke))
        x = math.ceil(self.margin + slidable * x_ratio)
        dc.DrawRectangle(int(x - self.cursor_width * 0.5), 0, int(self.cursor_width), int(h))

    def SetRectWave(self, now=False):
        # now: painted on this thread at once (a single step's change: TEMPO, KEY), not
        # stretched first and painted 150 ms later (two jolts, seen)
        x, y, w, h = self.GetWaveRect()
        self.wave_rect = (x, y, w, h)
        waveform = self.parent.GetWaveform()
        self.wave_job += 1
        if audio.is_waveform_3band(waveform) is False or w <= 0 or h <= 0:
            self.wave_bitmaps = None
            self.wave_exact = None
            self.wave_source = None
            return
        # painted on a thread: on this one a long mix held the window 100 ms and
        # more at every change of song. until it is done the same song's last
        # waveform is stretched over, a new song's is the flat line
        if self.wave_source is waveform and self.wave_exact is not None:
            self.StretchWave()
        else:
            self.wave_bitmaps = None
            self.wave_exact = None
        self.wave_source = waveform
        # normal, dimmed for outside the highlight, and on the highlight ground
        bgcolor = self.parent.st.PLAY_BG_COLOR
        hlcolor = self.parent.st.HIGHLIGHT_BG_COLOR
        grounds = ((bgcolor, 1.0), (bgcolor, self.highlight_dim), (hlcolor, 1.0))
        job = self.wave_job

        def paint():
            images = [audio.paint_waveform_3band(waveform, w, h, ground=ground, dim=dim).tobytes()
                      for ground, dim in grounds]
            if now:
                self.SetWaveImages(job, (x, y, w, h), images)
            else:
                wx.CallAfter(self.SetWaveImages, job, (x, y, w, h), images)

        if now:
            paint()
            return
        threading.Thread(target=paint, daemon=True).start()

    def SetWaveImages(self, job, rect, images):
        # a song or a size since: painted again for that one already
        if not self or job != self.wave_job:
            return
        x, y, w, h = rect
        self.wave_bitmaps = [wx.Bitmap.FromBuffer(w, h, image) for image in images]
        self.wave_exact = self.wave_bitmaps
        if self.GetWaveRect() != rect:
            self.StretchWave()
        self.InitBuffer()
        self.Refresh(False)

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.parent.HasToSkipEvent() is False:
            self.HandleEventLeftIsDown(event)
            self.HandleEventHighlight(event)
            self.HandleEventGridMenu(event)
        if self.parent.IsPlaying() is False:
            self.DirectDraw()

    def HandleEventGridMenu(self, event):
        # the grid's menu here too, at the time clicked on the whole song
        if event.RightUp is False or event.rectIdx is None or self.parent.IsGridShown() is False:
            return
        width = max(self.GetSize().width - self.margin * 2, 1)
        share = min(max(1.0 * (event.X - self.margin) / width, 0.0), 1.0)
        seconds = share * self.parent.GetDurationTime()
        self.parent.parent.SetPopupMenu(PlayBoxPopupGrid(self.parent, seconds), (event.x, event.y))

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        if event.WheelRotation > 0:
            self.parent.OnFastRewind()
        else:
            self.parent.OnFastForward()

    def HandleEventHighlight(self, event):
        if event.rectIdx is None:
            return
        if event.LeftDown is False:
            return
        if self.parent.IsHighlightKnown() is False:
            return
        if self.parent.IsHighlightOn() is False:
            return
        if self.IsInRect(self.rectHighlight, (event.X, event.Y)):
            return
        self.parent.SetHighlightSkipOn()

    def HandleEventLeftIsDown(self, event):
        # pressed: a marker under the pointer, moved freely with a drag; let go: it plays
        # from the grid point SNAP says (OnClickWave)
        if event.LeftDown and event.rectIdx is not None:
            self.press_x = event.X
            self.reInitBuffer = True
            return
        if getattr(self, 'press_x', None) is None:
            return
        if event.LeftIsDown:
            if event.X != self.press_x:
                self.press_x = event.X
                self.reInitBuffer = True
            return
        x, self.press_x = self.press_x, None
        self.OnClickWave(Struct(X=x))
        self.reInitBuffer = True

    def GetPressTime(self):
        # where the press or the drag is now (not snapped), None when there is none
        x = getattr(self, 'press_x', None)
        duration = self.parent.GetDurationTime()
        if x is None or duration <= 0:
            return None
        width, _ = self.GetSize()
        ratio = min(max(1.0 * (x - 5) / max(width - 5 * 2, 1), 0.0), 0.999999)
        return duration * ratio

    def DrawPressMarker(self, dc):
        seconds = self.GetPressTime()
        if seconds is None:
            return
        w, h = self.GetSize()
        x = int(math.ceil(self.margin + (w - self.margin * 2) * seconds /
                          self.parent.GetDurationTime()))
        accent = uikit.ui().ACCENT
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(accent))
        dc.DrawRectangle(x - 1, 0, 2, h)

    def OnClickWave(self, event):
        width, height = self.GetSize()
        x = event.X - 5
        slidable = width - 5 * 2
        posRatio = 1.0 * x / slidable
        if posRatio <= 0.0:
            posRatio = 0.0
        elif posRatio >= 1.0:
            posRatio = 0.999999
        duration = self.parent.GetDurationTime()
        # on the grid as SNAP says
        new_position = self.parent.GetSnappedTime(duration * posRatio)
        # into the edit's intro or outro: the whole song for this play
        self.parent.LeaveRadioEdit(new_position)
        if self.parent.IsPlaying():
            self.parent.SetPositionTime(new_position)
        else:
            self.parent.SetResumeTime(new_position)
            self.reInitBuffer = True


class PlayBoxWaveDetail(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.height = 40
        self.gap = 6
        self.margin = 5
        self.buffer.fps = 60
        # seconds across: at first, the least and how far a wheel notch goes. at
        # first a pixel is about 3.6 ms of sound, fine enough to scratch with the
        # waveform staying under the hand
        # self.span = 12.0
        self.span = 5.0
        self.span_least = 1.5
        self.span_most = 3 * 60 * 60
        self.span_step = 1.25
        self.drag_least = 4
        self.highlight_dim = 0.45
        self.drag = None
        # the strip is the record: playing, a hand on it stops it and a drag
        # scratches it, the waveform under the hand; paused, a drag moves through
        # the file and it plays from there. a click alone does not seek (the bar
        # below does): it was a stop, a seek or a scratch by how long and how far
        # the press went, and it could not be told which
        self.scratching = None
        self.last_key = None
        self.last_step = 0
        self.last_bitmap = None
        self.SetDropTarget(PlayBoxDnD(self.parent))
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnScratchDown)
        self.Bind(wx.EVT_MOTION, self.OnScratchMotion)
        self.Bind(wx.EVT_LEFT_UP, self.OnScratchUp)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnScratchCaptureLost)
        self.InitBuffer()

    def IsScratchable(self):
        return self.parent.IsWaveformScratchOn() and self.parent.IsPlaying()\
            and self.parent.AudioControl.IsScratchable()

    def OnScratchDown(self, event):
        if self.IsScratchable() is False:
            event.Skip()
            return
        self.CaptureMouse()
        self.drag = None
        self.scratching = Struct(x=event.GetX(), time=time.time(), moved=False,
                                 start=self.parent.GetPositionTime(), path=self.parent.cue.path)
        # the hand itself is read off the cursor by the audio side (ScratchPress),
        # at the view's own scale so the waveform stays under the hand, but no
        # coarser than the scale heard clean (zoomed far out, the hand outruns it)
        width = max(self.GetSize().width - self.margin * 2, 1)
        seconds_per_pixel = min(1.0 * self.GetSpan() / width, 1.0 / SCRATCH_PIXELS_PER_SECOND)
        self.parent.AudioControl.ScratchEventAt(self.ClientToScreen(event.GetPosition()).x)
        self.parent.AudioControl.ScratchPress(seconds_per_pixel)

    def OnScratchMotion(self, event):
        if self.scratching is None:
            event.Skip()
            return
        if abs(event.GetX() - self.scratching.x) >= self.drag_least:
            self.scratching.moved = True
        self.parent.AudioControl.ScratchEventAt(self.ClientToScreen(event.GetPosition()).x)

    def OnScratchUp(self, event):
        if self.scratching is None:
            event.Skip()
            return
        scratching = self.scratching
        self.scratching = None
        if self.HasCapture():
            self.ReleaseMouse()
        self.parent.AudioControl.ScratchRelease()
        # if scratching.moved or time.time() - scratching.time > self.click_seconds:
        #     return
        # if scratching.path != self.parent.cue.path:
        #     return
        # width = max(self.GetSize().width - self.margin * 2, 1)
        # self.SeekTo(scratching.start + (1.0 * (scratching.x - self.margin) / width - 0.5) * self.GetSpan())

    def OnScratchCaptureLost(self, event):
        self.scratching = None
        self.parent.AudioControl.ScratchRelease()

    def OnSize(self, event=None):
        # hidden while a station's message takes the waveforms' place
        if self.parent.parent.parent.IsWaveformDetailShowOn() is False\
                or getattr(self.parent, 'live_message', None) is not None:
            self.drag = None
            self.Hide()
            return
        self.Show()
        x, y, w, h = self.parent.Wave.GetRect()
        self.SetRect((x, y - self.height - self.gap, w, self.height))
        # not painted again here: a new width is a new key (DrawDetailWave), and
        # while the window is resized the strip is kept
        self.DirectDraw()

    def GetSpan(self):
        duration = self.parent.GetDurationTime()
        if duration <= 0:
            return self.span
        return min(self.span, duration)

    def GetCentre(self):
        # a drag is of the track it began on: the next track's waveform is not
        # shown at its time, nor played from it
        if self.drag is not None and self.drag.path != self.parent.cue.path:
            self.drag = None
        if self.drag is not None and self.drag.moved:
            return self.drag.time
        return self.parent.GetPositionTime()

    def IsHighlightDrawn(self):
        return self.parent.IsHighlightKnown()\
            and self.parent.IsHighlightOn()\
            and self.parent.IsHighlightSkipOn() is False

    def GetHighlightPeriod(self):
        if self.IsHighlightDrawn() is False:
            return None
        offset, period = self.parent.GetHighlightTime()
        if offset is None or period is None:
            return None
        if period == 0:
            return (offset, self.parent.GetDurationTime())
        return (offset, offset + period)

    # the zoom told at the strip's right top: against the first zoom (span 5 s), the
    # seconds across, and where it is between the closest and the widest (a bar)
    ZOOM_FIRST = 5.0

    # bar numbers: at least this many pixels from one numbered bar to the next (30 made a
    # row of them zoomed out)
    NUMBER_SPACING = 64

    def SetRectDraw(self, dc):
        self.DrawStrip(dc)
        self.zoom_rect = None
        self.DrawZoom(dc)
        self.DrawBarNumbers(dc)

    def DrawBarNumbers(self, dc):
        # the bars' numbers by their lines (the first downbeat bar 1): every bar zoomed in,
        # every 4 bars (the phrases' lines when the phrase is known), every 16 zoomed out;
        # on the strip's whole pixels as its waveform is (DrawDetailWave)
        grid = self.parent.GetGrid()
        duration = self.parent.GetDurationTime()
        if grid is None or duration <= 0 or self.parent.IsGridShown() is False\
                or self.parent.IsStreamTrack() or self.parent.GetLiveMessage() is not None:
            return
        w, h = self.GetSize()
        w -= self.margin * 2
        if w <= 0:
            return
        span = self.GetSpan()
        pixel = span / w
        start = round((self.GetCentre() - span * 0.5) / pixel) * pixel
        period = 60.0 / grid.bpm
        bar = period * 4
        downbeat = self.parent.GetGridDownbeat()
        every = 1
        if bar / pixel < self.NUMBER_SPACING:
            every = 4 if bar * 4 / pixel >= self.NUMBER_SPACING else 16
        # numbered from the phrase's first bar when it is known, else from bar 1
        anchor = self.parent.GetGridPhraseBars() if self.parent.IsGridPhraseKnown() else 0
        first = int(math.floor((start - downbeat) / bar))
        last = int(math.ceil((start + span - downbeat) / bar))
        st = self.parent.st
        # small and dimmed on the strip's own black: read when looked for, not first
        dc.SetFont(wx.Font(wx.Size(0, 9), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                           wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO))
        for index in range(max(first, 0), last + 1):
            if every > 1 and (index - anchor) % every:
                continue
            x = int(self.margin + (downbeat + index * bar - start) / pixel)
            if x < self.margin or x > self.margin + w - 8:
                continue
            text = '%d' % (index + 1)
            tw, th = dc.GetTextExtent(text)
            if self.zoom_rect is not None and x + tw + 6 >= self.zoom_rect.x\
                    and 2 + th >= self.zoom_rect.y:
                continue
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(st.PLAY_BG_COLOR))
            dc.DrawRectangle(x + 2, 1, tw + 4, th + 1)
            dc.SetTextForeground(st.TITLE_DIM_COLOR)
            dc.DrawText(text, x + 4, 1)

    def DrawZoom(self, dc):
        w, h = self.GetSize()
        if w < 200 or h < 20:
            return
        st = self.parent.st
        span = self.GetSpan()
        if self.parent.IsStreamTrack():
            span = min(self.span, radio.TRACE_SECONDS)
        text = '\u00d7%.1f  %s' % (self.ZOOM_FIRST / span, get_span_text(span))
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        font = wx.Font(wx.Size(0, 11), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
        gc.SetFont(font, wx.Colour(st.CHIP_FG_COLOR))
        tw, th = gc.GetTextExtent(text)[:2]
        bar = 36
        cw, ch = tw + bar + 22, 16
        x, y = w - self.margin - cw - 4, 3
        self.zoom_rect = wx.Rect(int(x), int(y), int(cw), int(ch))
        face = wx.Colour(st.CHIP_BG_COLOR)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(face.Red(), face.Green(), face.Blue(), 225))))
        gc.DrawRoundedRectangle(x, y, cw, ch, uikit.RADIUS)
        gc.DrawText(text, x + 7, y + (ch - th) / 2.0)
        # the bar: closest (span_least) at its left, the whole track (or the widest) at its
        # right, by the wheel's steps (a log scale)
        widest = max(self.parent.GetDurationTime(), self.span_least * self.span_step)
        share = math.log(max(span, self.span_least) / self.span_least)\
            / math.log(max(widest, self.span_least * 1.01) / self.span_least)
        share = min(max(share, 0.0), 1.0)
        bx, by = x + tw + 14, y + ch / 2.0 - 1
        gc.SetBrush(gc.CreateBrush(wx.Brush(st.TITLE_DIM_COLOR)))
        gc.DrawRectangle(bx, by, bar, 2)
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.ui().ACCENT)))
        gc.DrawRoundedRectangle(bx + share * (bar - 4), by - 3, 4, 8, 1.5)

    def DrawStrip(self, dc):
        w, h = self.GetSize()
        w -= self.margin * 2
        if w <= 0 or h <= 0:
            return
        # the radio playing alone: its last seconds at the strip's zoom
        if draw_live_trace(dc, self.parent, (self.margin, 0, w, h),
                           min(self.span, radio.TRACE_SECONDS), spread=0):
            return
        waveform = self.parent.GetWaveform()
        duration = self.parent.GetDurationTime()
        if audio.is_waveform_3band(waveform) and duration > 0:
            self.DrawDetailWave(dc, waveform, duration, w, h)
        else:
            # the waveform bar's flat line colour
            if self.IsHighlightDrawn():
                color = self.parent.st.HIGHLIGHT_PN_COLOR
            else:
                color = self.parent.st.WAVEFORM_FG_COLOR
            dc.SetPen(wx.Pen(color, 1))
            dc.DrawLine(self.margin, int(h * 0.5), self.margin + w, int(h * 0.5))
        # the line a seek snapped to, lit a moment (drawn again till it fades)
        flash = self.parent.GetSnapFlash()
        if flash is not None:
            fx = self.margin + w * (0.5 + (flash[0] - self.GetCentre()) / self.GetSpan())
            if self.margin <= fx <= self.margin + w:
                draw_snap_flash(dc, int(math.ceil(fx)), 0, h, flash[1])
            self.redraw_next = True
        # the same cursor as the waveform bar's
        cursor_width = self.parent.Wave.cursor_width
        dc.SetBrush(wx.Brush(self.parent.st.PLAYCURSOR_BG_COLOR))
        dc.SetPen(wx.Pen(self.parent.st.PLAYCURSOR_FG_COLOR, self.parent.st.PLAYCURSOR_STROKE))
        x = math.ceil(self.margin + w * 0.5)
        dc.DrawRectangle(int(x - cursor_width * 0.5), 0, int(cursor_width), int(h))

    def DrawDetailWave(self, dc, waveform, duration, w, h):
        span = self.GetSpan()
        centre = self.GetCentre()
        period = self.GetHighlightPeriod()
        # the window on whole pixels: the sound moves a pixel at a time and each
        # pixel keeps its columns, or the picture shimmered as it scrolled; and
        # painted again only when it has moved a pixel
        # while the window is resized the strip keeps its own scale (the window
        # shows more or less of it) and is painted again once the resizing stops:
        # painted at every step it was 8 ms a step, at times 70
        if self.last_key is not None and self.parent.Wave.IsResizing()\
                and self.last_key[:4] == (id(waveform), duration, span, period):
            kept = self.last_key[4]
            step = round((centre - span * 0.5) / (span / kept))
            if kept // 4 <= step - self.last_step <= kept * 2 - kept // 4:
                dc.SetClippingRegion(self.margin, 0, w, h)
                dc.DrawBitmap(self.last_bitmap,
                              self.margin + (w - kept) // 2 - (step - self.last_step), 0)
                dc.DestroyClippingRegion()
                return
        pixel = span / w
        step = round((centre - span * 0.5) / pixel)
        # a strip three windows wide on the same pixels, moved under the window
        # and painted again only near its ends: painted every frame it was about
        # 2.5 ms a frame
        grid = self.parent.GetGrid()
        gridkey = None if grid is None or self.parent.IsGridShown() is False\
            else (grid.bpm, grid.downbeat, grid.shift, grid.phrase, grid.phrase_shift,
                  grid.phrase_set)
        played = tuple(self.parent.GetPlayedRanges())
        key = (id(waveform), duration, span, period, w, h, gridkey, played)
        if key != self.last_key or not w // 4 <= step - self.last_step <= w * 2 - w // 4:
            self.last_step = step - w
            start = self.last_step * pixel
            times = start + (numpy.arange(w * 3) + 0.5) * span / w
            bgcolor = numpy.array(self.parent.st.PLAY_BG_COLOR, dtype=float)
            ground, dim = (bgcolor, 1.0)
            # what plays (the highlight, SHORT's parts) on the highlight's ground, the rest
            # dimmed (SHORT's were not: its parts not told apart here)
            if played:
                inside = numpy.zeros(len(times), dtype=bool)
                for a, b in played:
                    inside |= (times >= a) & (times < b)
                hlcolor = numpy.array(self.parent.st.HIGHLIGHT_BG_COLOR, dtype=float)
                ground = numpy.where(inside[:, None], hlcolor, bgcolor)
                dim = numpy.where(inside, 1.0, self.highlight_dim)
            columns = len(waveform) / duration
            # with the grid shown, a lane above and below the waveform for its ticks (a
            # line in the waveform alone was lost where the sound is bright)
            lane = self.GRID_LANE if gridkey is not None and h > self.GRID_LANE * 4 else 0
            image = audio.paint_waveform_3band(
                waveform, w * 3, h - lane * 2, ground=ground, dim=dim,
                start=start * columns, end=(start + span * 3) * columns, spread=0)
            if lane:
                band = numpy.broadcast_to(numpy.array(ground, dtype=float), (w * 3, 3))
                if played:
                    # over what the highlight or SHORT plays, tinted (LANE_PLAYED)
                    inside = numpy.zeros(w * 3, dtype=bool)
                    for a, b in played:
                        inside |= (times >= a) & (times < b)
                    tint = numpy.array(get_lane_played(self.parent.st), dtype=float)
                    band = numpy.where(inside[:, None], tint, band)
                band = numpy.repeat(band[None, :, :].astype(numpy.uint8), lane, axis=0)
                image = numpy.concatenate((band, image, band), axis=0)
            self.PaintGridLines(image, start, pixel, lane)
            self.last_bitmap = wx.Bitmap.FromBuffer(w * 3, h, image.tobytes())
            self.last_key = key
        dc.SetClippingRegion(self.margin, 0, w, h)
        dc.DrawBitmap(self.last_bitmap, self.margin - (step - self.last_step), 0)
        dc.DestroyClippingRegion()

    # the grid's ticks' lanes, above and below the strip's waveform (pixels)
    GRID_LANE = 4

    def PaintGridLines(self, image, start, pixel, lane=0):
        # the beat grid lightened into the strip: told apart by strength and width, not
        # by colour. a beat's line is left out when beats are closer than 4 pixels. in the
        # lanes (lane: their height) a tick of it brighter: a beat's half the lane, a
        # bar's and a phrase's all of it
        height, width, _ = image.shape
        lines = self.parent.GetGridLines(start, start + width * pixel)
        if lines == []:
            return
        beat_pixels = 60.0 / self.parent.GetGrid().bpm / pixel
        for seconds, level in lines:
            if level == 0 and beat_pixels < 4:
                continue
            x = int((seconds - start) / pixel)
            strength, thick = ((0.22, 1), (0.5, 1), (0.75, 2))[level]
            left, right = max(x, 0), min(x + thick, width)
            if right <= left:
                continue
            part = image[:, left:right].astype(numpy.float32)
            image[:, left:right] = (part + (255 - part) * strength).astype(numpy.uint8)
            if lane:
                tick = lane // 2 if level == 0 else lane
                bright = (0.5, 0.8, 0.95)[level]
                for rows in (slice(0, tick), slice(height - tick, height)):
                    part = image[rows, left:right].astype(numpy.float32)
                    image[rows, left:right] = (part + (255 - part) * bright).astype(numpy.uint8)

    def CATCH_EVT_GLOBAL(self, event):
        if self.IsShown() is False:
            return
        if self.parent.parent.HasToSkipEvent() is False:
            self.HandleEventDrag(event)
            self.HandleEventGridMenu(event)
        if self.parent.IsPlaying() is False:
            self.DirectDraw()

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        # up narrows, down widens; kept as the span chosen, not fitted to the
        # track (GetSpan does that), or a short track, or none, left every track
        # after it zoomed in
        duration = self.parent.GetDurationTime()
        if duration <= 0:
            return
        if event.WheelRotation > 0:
            span = min(self.span, duration) / self.span_step
        else:
            span = min(self.span * self.span_step, max(duration, self.span))
        # most = max(self.parent.GetDurationTime(), self.span_least)
        # self.span = min(max(span, self.span_least), most)
        self.span = min(max(span, self.span_least), self.span_most)
        self.reInitBuffer = True

    def HandleEventDrag(self, event):
        # a drag moves through the file, let go where it should play; a click
        # plays from where it is
        # a scratch has the press (OnScratchDown)
        if self.scratching is not None:
            return
        if event.LeftDown and event.rectIdx is not None:
            if self.IsScratchable():
                return
            centre = self.parent.GetPositionTime()
            self.drag = Struct(x=event.X, start=centre, time=centre, moved=False,
                               path=self.parent.cue.path)
            return
        if self.drag is not None and self.drag.path != self.parent.cue.path:
            self.drag = None
        if self.drag is None:
            return
        width = max(self.GetSize().width - self.margin * 2, 1)
        if event.LeftIsDown:
            dx = event.X - self.drag.x
            if abs(dx) >= self.drag_least:
                self.drag.moved = True
            if self.drag.moved:
                # free while it moves; let go, it lands on the grid as SNAP says (SeekTo)
                self.drag.time = self.drag.start - 1.0 * dx / width * self.GetSpan()
            return
        drag = self.drag
        self.drag = None
        if drag.moved:
            position = drag.time
        elif self.parent.GetWaveformMode() == 'seek':
            # seek mode: a click plays from where it is (vinyl: the bar below does)
            position = drag.start + (1.0 * (drag.x - self.margin) / width - 0.5) * self.GetSpan()
        else:
            return
        self.SeekTo(position)

    def HandleEventGridMenu(self, event):
        if event.RightUp is False or event.rectIdx is None or self.parent.IsGridShown() is False:
            return
        width = max(self.GetSize().width - self.margin * 2, 1)
        seconds = self.GetCentre() + (1.0 * (event.X - self.margin) / width - 0.5) * self.GetSpan()
        self.parent.parent.SetPopupMenu(PlayBoxPopupGrid(self.parent, seconds), (event.x, event.y))

    def SeekTo(self, position):
        duration = self.parent.GetDurationTime()
        # a click or a drag's end on the grid as SNAP says
        position = self.parent.GetSnappedTime(position)
        position = min(max(position, 0.0), duration * 0.999999)
        period = self.GetHighlightPeriod()
        if period is not None and (position < period[0] or position >= period[1]):
            self.parent.SetHighlightSkipOn()
        self.parent.LeaveRadioEdit(position)
        if self.parent.IsPlaying():
            self.parent.SetPositionTime(position)
        else:
            self.parent.SetResumeTime(position)
            self.parent.Wave.reInitBuffer = True
        self.reInitBuffer = True


class PlayBoxPopupGrid(wx.Menu):

    def __init__(self, parent, seconds):
        # parent: the PlayBox; seconds: where in the song the strip was clicked
        wx.Menu.__init__(self)
        self.parent = parent
        self.seconds = seconds
        grid = self.parent.GetGrid()
        if grid is None:
            item = self.Append(wx.ID_ANY, 'No beat grid yet')
            item.Enable(False)
            return
        # the time clicked in the labels: where it lands is seen before it is chosen
        at = '%d:%04.1f' % (seconds // 60, seconds % 60)
        labels = ('Bar starts on this beat (%s)' % (at), 'Bar starts at the play position',
                  'Bar one beat earlier', 'Bar one beat later', 'Bar as analyzed')
        for label, handler in zip(labels, (self.OnHere, self.OnHerePlaying, self.OnEarlier,
                                           self.OnLater, self.OnAnalyzed)):
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        labels = ('Phrase starts on this bar (%s)' % (at), 'Phrase starts at the play position',
                  'Phrase as analyzed')
        for label, handler in zip(labels, (self.OnPhraseHere, self.OnPhraseHerePlaying,
                                           self.OnPhraseAnalyzed)):
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        source = 'Beat This!' if grid.source.startswith('beatthis') else 'the beats alone'
        if grid.source.endswith('+changes'):
            source += ', moved by the song\'s changes'
        item = self.Append(wx.ID_ANY, '%.3f BPM, bar from %s' % (grid.bpm, source))
        item.Enable(False)
        self.AppendSeparator()
        scale = grid.bpm_scale or 1.0
        labels = [('Tempo x2 (%.2f BPM)' % (grid.bpm * 2), self.OnTempoDouble),
                  ('Tempo /2 (%.2f BPM)' % (grid.bpm / 2), self.OnTempoHalf)]
        if scale != 1.0:
            labels.append(('Tempo as analyzed (%.2f BPM)' % (grid.bpm / scale),
                           self.OnTempoAnalyzed))
        for label, handler in labels:
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        if grid.phrase_set:
            phrase = 'Phrase set by you'
        elif self.parent.IsGridPhraseKnown():
            phrase = 'Phrase from the song\'s changes'
        else:
            phrase = 'Phrase unsure, not drawn: set it on a bar above'
        item = self.Append(wx.ID_ANY, phrase)
        item.Enable(False)

    def OnHere(self, event):
        self.parent.SetGridBarAt(self.seconds)

    def OnHerePlaying(self, event):
        self.parent.SetGridBarAt(self.parent.GetPositionTime())

    def OnPhraseHerePlaying(self, event):
        self.parent.SetGridPhraseAt(self.parent.GetPositionTime())

    def OnEarlier(self, event):
        self.parent.SetGridShift((self.parent.GetGrid().shift or 0) - 1)

    def OnLater(self, event):
        self.parent.SetGridShift((self.parent.GetGrid().shift or 0) + 1)

    def OnAnalyzed(self, event):
        self.parent.SetGridShift(0)

    def OnPhraseHere(self, event):
        self.parent.SetGridPhraseAt(self.seconds)

    def OnTempoDouble(self, event):
        self.parent.SetGridScale(2.0)

    def OnTempoHalf(self, event):
        self.parent.SetGridScale(0.5)

    def OnTempoAnalyzed(self, event):
        self.parent.SetGridScale(None)

    def OnPhraseAnalyzed(self, event):
        self.parent.SetGridPhraseShift(0, set_by_user=False)
