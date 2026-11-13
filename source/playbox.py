# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import coverbox
import ctypes
import folders
import images
import io
import library
import listimages
import math
import mutagen
import os
import radio
import re
import tempfile
import threading
import time
import uikit
import wx

from PIL import Image
from macroboxlib import COUNTS
from macroboxlib import FONT_PLAYINFO
from macroboxlib import GetPreference
from macroboxlib import SetPreference
from macroboxlib import pointer_window
from macroboxlib import DrawPending
from macroboxlib import PaintUnpainted
from macroboxlib import RectBox
from analyzerbox import AnalyzerPanel
from masterbox import MasterPanel
from rackbox import Rack
from playboxlib import AudioControl
from playboxlib import PlayBoxControl
from playboxcontrols import PlayBoxControlButton
from playboxcontrols import SnapButton
from playboxcontrols import TempoStrip
from playboxcontrols import VolumeSlider
from playboxvisual import PlayBoxSpectrum
from playboxvisual import PlayBoxVectorScope
from playboxvisual import PlayBoxWave
from playboxvisual import PlayBoxWaveDetail
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
        self.TempoStrip = TempoStrip(self)
        self.SnapButton = SnapButton(self)
        # the rack over the header: MASTER at the top, ANALYZER under it
        self.Master = MasterPanel(self)
        self.Analyzer = AnalyzerPanel(self)
        self.Rack = Rack(self, [self.Master, self.Analyzer])
        # the volume as MASTER's child: a sibling over it was drawn under it
        self.VolumeSlider.Reparent(self.Master)
        self.Master.SetWindowStyleFlag(self.Master.GetWindowStyleFlag() | wx.CLIP_CHILDREN)
        # the header's visualizers in ANALYZER's BARS part
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

    # header: cover, title, info, spectrum and scope
    HEADER_HEIGHT = 61
    HEADER_COMPACT = 33
    CONTROL_HEIGHT = 33

    # an extra row of the info's cells (PlayBoxInfo.CELL_SLOT)
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
        # the info's rows at this width: a change lays the window out again
        info, title = getattr(self, 'Info', None), getattr(self, 'Title', None)
        if info is None or title is None or self.parent.parent.IsPlayerTopShowOn() is False:
            return
        # the cover grows with the info's rows: count again till they stay
        right = title.GetTextRight()
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

    # top to bottom: rack, header, waveforms, control row
    def GetHeaderTop(self):
        return self.GetRackHeight()

    # the tempo strip's columns, shown or hidden on their own
    def IsStripColumnShown(self, column):
        # cached: asked many times a frame
        shown = self.__dict__.setdefault('strip_shown', {})
        if column not in shown:
            if column == 'tempo':
                shown[column] = GetPreference('tempo_strip') is not False
            else:
                shown[column] = GetPreference('key_strip') is True
        return shown[column]

    def SetStripColumnShown(self, column, shown):
        '''a hidden column is off: its value kept till shown again'''
        shown = bool(shown)
        was = self.IsStripColumnShown(column)
        kept = self.__dict__.setdefault('strip_kept', {})
        self.__dict__.setdefault('strip_shown', {})[column] = shown
        SetPreference('tempo_strip' if column == 'tempo' else 'key_strip', shown)
        if shown and not was and column in kept:
            if column == 'tempo':
                self.SetTempoRate(kept.pop(column))
            else:
                self.SetTempoSemitones(kept.pop(column))
        elif was and not shown:
            if column == 'tempo':
                kept[column] = self.GetTempoRate()
                self.SetTempoRateExact(1.0)
            else:
                kept[column] = self.GetTempoSemitones()
                self.SetTempoSemitones(0)
        menubar = getattr(self.parent.parent, 'MenuBar', None)
        item = getattr(menubar, 'itemTempoControl' if column == 'tempo' else 'itemKeyControl',
                       None)
        if item is not None:
            item.Check(shown)
        self.OnSize(settle=True)

    def OnTempoMoved(self, column):
        # moved while hidden (a shortcut, DECK SYNC): show it
        if column == 'tempo':
            moved = abs(self.GetTempoRate() - 1.0) > 1e-9
        else:
            moved = self.GetTempoSemitones() != 0
        if moved and not self.IsStripColumnShown(column):
            self.__dict__.setdefault('strip_kept', {}).pop(column, None)
            self.SetStripColumnShown(column, True)

    def GetDeckRight(self):
        # right end of the header and the waveforms
        w = self.GetClientSize().width
        count = len([c for c in ('tempo', 'key') if self.IsStripColumnShown(c)])
        if count:
            return w - 8 - TempoStrip.GetWidth(count) - 8
        return w - 8

    # gap between control groups
    CONTROL_GAP = 13
    # narrower levels of the control row (SetPreInitRects)
    CONTROL_LEVELS = 2

    def GetControlNeed(self, level=0):
        # the width the control row needs on one row
        strip = PlayBoxControlButton.STRIP_WIDTH\
            - (PlayBoxControlButton.TRANSPORT_SAVE if level >= 1 else 0)\
            - (PlayBoxControlButton.LOOP_SAVE if level >= 1 else 0)
        return PlayBoxControlButton.STRIP_X + strip + self.CONTROL_GAP + SnapButton.LENGTH + 5

    def GetControlLevel(self):
        width = self.GetClientSize().width
        for level in range(self.CONTROL_LEVELS):
            if width >= self.GetControlNeed(level):
                return level
        return self.CONTROL_LEVELS - 1

    def GetControlRows(self):
        # two rows only when even the narrowest does not fit
        return 1 if self.GetClientSize().width\
            >= self.GetControlNeed(self.CONTROL_LEVELS - 1) else 2

    def GetControlHeight(self):
        return self.CONTROL_HEIGHT * getattr(self, 'control_rows', 1)

    def GetControlExtra(self):
        return self.GetControlHeight() - self.CONTROL_HEIGHT

    def GetControlTop(self):
        return self.GetClientSize().height - self.GetControlHeight()

    def IsControlTwoRows(self):
        # two rows: transport over the play modes, SNAP on the right
        return getattr(self, 'control_rows', 1) == 2

    def LookUpCover(self):
        path = self.cue.path
        if self.IsStreamTrack() or not path:
            return
        tags = audio.get_id3(path, [u'TPE1', u'TIT2']) or dict()
        coverbox.look_up_cover_for(self.parent.ListBox, [dict(
            path=path, mdx=getattr(self.cue, 'mdx', None), artist=tags.get(u'TPE1', ''),
            title=tags.get(u'TIT2', ''), label=os.path.basename(path))])

    def OpenTrackEditor(self):
        # the editor edits the list's selection: select the playing song
        if self.IsStreamTrack():
            return
        found = self.GetPlayingListItemIdx()
        if not found:
            return
        listIdx, itemIdx = found
        listbox = self.parent.ListBox
        if listIdx != listbox.selectedList:
            listbox.SetSelectedList(listIdx)
            self.parent.OnSize(None)
        listbox.SelectAndFocusItem(itemIdx)
        self.Apic.HidePreview()
        listbox.List.OpenItemEditBox(None)

    def HandleDragOut(self, box, event, kind):
        '''drag the playing song's file, or its cover as a file'''
        if event.LeftIsDown is False:
            box.dragging_out = False
            return
        if getattr(box, 'dragging_out', False) or event.LeftIsDrag is False\
                or event.drag.rectIdx is None or self.parent.HasToSkipEvent():
            return
        box.dragging_out = True
        path = self.cue.path
        if self.IsStreamTrack() or not path or not os.path.isfile(path):
            return
        if kind == 'cover':
            self.Apic.HidePreview()
            path = self.MakeCoverFile(path)
            if path is None:
                return
        self.parent.SetItemDrag((path,))

    # covers dragged out, kept: a drop may copy one after the drag ends
    COVER_FOLDER = os.path.join(tempfile.gettempdir(), 'PyMusicPlayer covers')

    def MakeCoverFile(self, path):
        # the cover's own bytes from the tags
        try:
            data = listimages.read_cover(path)
            kind = Image.open(io.BytesIO(data)).format if data else None
        except Exception:
            return None
        if not kind:
            return None
        extension = {'JPEG': 'jpg'}.get(kind, kind.lower())
        name = re.sub(r'[\\/:*?"<>|]', '_', os.path.splitext(os.path.basename(path))[0])
        os.makedirs(self.COVER_FOLDER, exist_ok=True)
        cover = os.path.join(self.COVER_FOLDER, f'{name}.{extension}')
        with open(cover, 'wb') as file:
            file.write(data)
        return cover

    def IsClickedOn(self, box, event):
        '''a right click pressed and let go on box, not dragged'''
        if getattr(event, 'covered', False) or box.onClient is False\
                or event.down.X is None or event.drag.x is not None:
            return False
        w, h = box.GetClientSize()
        if not (0 <= event.X < w and 0 <= event.Y < h
                and 0 <= event.down.X < w and 0 <= event.down.Y < h):
            return False
        # only the window under the pointer: else the menu opens twice
        return pointer_window() in (None, box.GetHandle())

    def HandleTrackEditor(self, event, box=None, menu_only=False):
        # double-click or menu on the title, cover or info: the tag editor
        if self.parent.HasToSkipEvent() or self.IsStreamTrack():
            return
        if event.LeftDClick and event.rectIdx is not None and menu_only is False:
            # after the event: the editor is modal
            wx.CallAfter(self.OpenTrackEditor)
        elif event.RightUp and box is not None and self.IsClickedOn(box, event):
            self.parent.SetPopupMenu(self.MakeTrackMenu(), (event.x, event.y))

    def MakeTrackMenu(self):
        # the list's song menu, its groups in its order, without what acts on a selection
        menu = wx.Menu()

        def add(name, handler):
            menu.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(handler),
                      menu.Append(wx.ID_ANY, name))

        path = self.cue.path
        starred = path in library.get_favorite_tracks()
        add('Remove from Favorite tracks' if starred else 'Add to Favorite tracks',
            self.ToggleFavoriteTrack)
        menu.AppendSeparator()
        add('Edit Track Info...', self.OpenTrackEditor)
        add('Look Up Cover...', self.LookUpCover)
        add('Copy Cover', lambda: coverbox.copy_cover(self.parent, path))
        menu.MenuItems[-1].Enable(coverbox.read_cover_of(path) is not None)
        add('Paste Cover', lambda: coverbox.paste_cover(
            self.parent.ListBox, [(path, getattr(self.cue, 'mdx', None))]))
        menu.MenuItems[-1].Enable(coverbox.has_copied_cover())
        add('Analyze', self.AnalyzeTrack)
        menu.AppendSeparator()
        add('Find Similar', self.FindSimilarTrack)
        # Find in Library with the playing tempo and key
        add('Find in Library...', lambda: wx.GetTopLevelParent(self).OnFindInLibrary(
            None, song=(self.GetPlayingTempo(), self.GetPlayingKey())))
        menu.AppendSeparator()
        add('Open Containing Folder', lambda: folders.show_in_explorer(path))
        return menu

    def ToggleFavoriteTrack(self):
        # imported here: listbox imports this module
        import listbox
        listbox.toggle_favorite_tracks(self.parent.ListBox, [self.cue.path])

    def AnalyzeTrack(self):
        threading.Thread(target=self.parent.MFEATS.AddMFEATSTask, args=(self.cue.path,),
                         kwargs=dict(urgent=True, forced=True), daemon=True).start()

    def FindSimilarTrack(self):
        import listbox
        keys = [v.key for v in self.item_column]
        listbox.find_similar(self.parent.ListBox, self.cue.path,
                             dict(zip(keys, self.cue.item or ())))

    def CheckControlRows(self):
        rows = self.GetControlRows()
        if rows == getattr(self, 'control_rows', 1):
            return
        self.control_rows = rows
        wx.CallAfter(self.RelayoutHeader)

    # room between the waveforms and the control row
    WAVE_BOTTOM_GAP = 11

    def GetRackHeight(self):
        # the rack over the header
        rack = getattr(self, 'Rack', None)
        return rack.GetHeight() if rack is not None else 0

    # the header's sizes at most (PlayBoxSpectrum.max_width)
    SCOPE_MOST = 44
    BARS_MOST = 30

    def LayoutAnalyzerVisuals(self):
        '''place the spectrum and the scope in ANALYZER's BARS part'''
        rect = getattr(self.Analyzer, 'bars_laid', None)
        if rect is None or rect.width < self.SCOPE_MOST + 32 + 40:
            self.Spectrum.Place(None)
            self.VectorScope.Place(None)
            return
        # side by side 14 px apart, centred, no bigger than in the header
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
        # control row: the bar's ground, a line over and under it
        tokens = uikit.ui()
        top = self.GetControlTop()
        bar = self.GetControlHeight()
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(tokens.BAR_BG))
        dc.DrawRectangle(0, top, width, bar)
        dc.SetPen(wx.Pen(tokens.BAR_LINE, 1))
        dc.DrawLine(0, top, width, top)
        dc.DrawLine(0, top + bar - 1, width, top + bar - 1)
        # two rows: a line between them
        if self.IsControlTwoRows():
            dc.DrawLine(0, top + self.CONTROL_HEIGHT - 1, width, top + self.CONTROL_HEIGHT - 1)
        self.DrawWaveFrame(dc)
        self.DrawLiveMessage(dc)

    # the waveforms' frame
    WAVE_FRAME = 4

    # frame room around the waveforms (left, top, right, bottom)
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
        # (text, warned) while a station connects or failed, else None
        failure = self.GetStreamFailure()
        if failure:
            return (f'Could not connect: {failure}', True)
        if self.GetStreamConnecting() is not None:
            return ('Connecting to the station...', False)
        return None

    def DrawLiveMessage(self, dc):
        # in the middle of the waveforms' place
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
        # hide the waveforms while a message takes their place
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
        # settle: paint the waveforms before the screen shows the change
        if event is not None:
            # sized by the mouse: lay out once more after the last size
            timer = getattr(self, 'settle_timer', None)
            if timer is None:
                self.settle_timer = wx.CallLater(200, self.OnSize)
            else:
                timer.Start(200)
        self.Freeze()
        self.DirectDraw()
        # the cover, the header right to left, then what fits between
        self.Apic.OnSize(None)
        self.VectorScope.OnSize(None)
        self.Spectrum.OnSize(None)
        self.Info.OnSize(None)
        self.Title.OnSize(None)
        self.Wave.OnSize(None)
        self.WaveDetail.OnSize(None)
        self.TempoStrip.OnSize(None)
        self.ControlButton.OnSize(None)
        self.Rack.OnSize()
        self.VolumeSlider.OnSize(None)
        self.SnapButton.OnSize(None)
        if settle:
            self.Wave.SettleNow()
        self.DirectDraw()
        self.Thaw()
        self.CheckHeaderRows()
        self.CheckControlRows()
        # the rack's height at this width: a change lays the window out again
        rack_height = self.GetRackHeight()
        if rack_height != getattr(self, 'rack_height', None):
            first = getattr(self, 'rack_height', None) is None
            self.rack_height = rack_height
            if not first:
                wx.CallAfter(self.RelayoutHeader)

    def CATCH_EVT_GLOBAL(self, event):

        self.AudioEvent(event)
        self.HandleLiveMessage()
        # the header's room between cover, title and info: their menu too
        top = self.GetHeaderTop()
        if top <= event.Y < top + self.GetHeaderHeight():
            self.HandleTrackEditor(event, self, menu_only=True)

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
            # the mode key: its mode on or off
            self.cache.oneshotkey = True
            self.ControlButton.ToggleMode()

        if namespace == 'mode_switch' and self.cache.oneshotkey is False:
            self.cache.oneshotkey = True
            self.ControlButton.SwitchMode()

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
            # off, the list, the song in turn, as LOOP's press
            self.cache.oneshotkey = True
            self.CycleLoop()
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
            # the mode's length a step shorter or longer
            step = 1 if namespace == 'highlight_increase' else -1
            if self.ControlButton.kind == 'short':
                lengths = [v[0] for v in self.RADIO_EDIT_LENGTHS]
                index = lengths.index(self.GetRadioEditLength()) + step
                if 0 <= index < len(lengths):
                    self.ControlButton.ChooseLength('short', lengths[index])
                return
            dutaionTypeId = self.GetHighlightDurationTypeId() + step
            items = self.parent.parent.MenuBar.highlightDurationItems
            if 0 <= dutaionTypeId < len(items):
                self.ControlButton.ChooseLength('highlight', items[dutaionTypeId])

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

    # visualizers' clock: a thread keeps the beat, drawing on the GUI thread
    def __init__(self, parent):
        threading.Thread.__init__(self, daemon=True)
        self.parent = parent
        self.loop = True
        self.posted = False
        self.done_at = 0.0
        # a wx.Timer too: in Windows' own loops (move, resize, drag and drop)
        # CallAfter waits, a WM_TIMER still comes
        self.sizing = wx.Timer()
        self.sizing.Bind(wx.EVT_TIMER, self.OnSizing)
        # the shortest a timer goes (about every 15.6 ms)
        self.sizing.Start(10)
        self.start()

    # gap after a tick so waiting WM_TIMERs get dispatched
    TICK_GAP = 0.005

    def OnSizing(self, event):
        self.Tick()

    def GetBoxes(self):
        parent = self.parent
        # ANALYZER first: drawn after them, it painted over them
        return [getattr(parent, name, None)
                for name in ('Analyzer', 'Master', 'Spectrum', 'VectorScope',
                             'Wave', 'WaveDetail')]

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
                # behind: no catching up
                due = time.perf_counter()
            # post the next tick after this one is done: else the queue never
            # empties and the mouse and key events never come
            while self.posted and self.loop:
                time.sleep(0.001)
            rest = self.done_at + self.TICK_GAP - time.perf_counter()
            if rest > 0:
                time.sleep(rest)
            if due < time.perf_counter() - 1.0 / self.GetFPS():
                due = time.perf_counter()
            self.posted = True
            wx.CallAfter(self.OnPosted)

    def OnPosted(self):
        try:
            self.Tick()
        finally:
            self.done_at = time.perf_counter()
            self.posted = False

    def Tick(self):
        if self.loop is False or not self.parent:
            return
        PaintUnpainted()
        DrawPending()
        if self.parent.IsVisualPlaying() is False:
            # stopped: the meters fall to rest, then nothing is drawn
            analyzer = getattr(self.parent, 'Analyzer', None)
            if analyzer is not None and analyzer.analyzer.IsSettled() is False:
                if analyzer.IsShown():
                    analyzer.DirectDraw()
                self.parent.Master.DirectDraw()
            # MASTER's meters drawn once more at rest
            master_panel = getattr(self.parent, 'Master', None)
            if master_panel is not None and not getattr(self, 'master_rested', False):
                master_panel.reInitBuffer = True
                self.master_rested = True
            return
        self.master_rested = False
        for box in self.GetBoxes():
            if box is not None and box.IsShown():
                # DEBUG(hang): each box's drawing time (mainapp's watchdog)
                lap = time.perf_counter()
                box.DirectDraw()
                COUNTS['ms ' + type(box).__name__] += int(
                    (time.perf_counter() - lap) * 1000)
                # on the screen now: Windows paints only when no other message waits
                box.Update()
        # the time display with the frames
        info = getattr(self.parent, 'Info', None)
        if info is not None and info.IsShown():
            info.HandleInfoChange()
            info.Update()

    def Quit(self):
        self.loop = False
        self.sizing.Stop()


class PlayBoxTitle(RectBox):

    # drawn first of the boxes waiting (macroboxlib.DrawPending)
    PENDING_FIRST = True

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
        self.tips = uikit.CutTips(self)
        # the star after the title: its rect as drawn, hovered, held, its tip
        self.starred = False
        self.star_rect = None
        self.star_hover = False
        self.star_down = False
        self.star_tip = None
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

    # title and subtitle font sizes
    TITLE_SIZE = 12
    SUBTITLE_SIZE = 11
    # the star after the title, as the list's: its radius, its room
    STAR_RADIUS = 5
    STAR_ROOM = 18

    def DrawTitle(self, dc):
        # the title, the folder or station under it; one line when compact
        width, height = self.GetSize()
        st = self.parent.st
        compact = self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT
        font = uikit.get_font(uikit.BODY if compact else self.TITLE_SIZE, bold=True)
        dc.SetFont(font)
        title = self.title
        room = width - self.STAR_ROOM if self.parent.cue.path is not None else width
        if dc.GetTextExtent(title)[0] > room:
            title = self.LimitTextLength(dc, title, room)
        tw, th = dc.GetTextExtent(title)
        # a pixel under the cover's top: its corners are round
        y = (height - th) // 2 if compact else 1
        self.rect = wx.Rect(0, y, tw, th)
        self.tips.Clear()
        self.tips.Add(self.rect, self.title, title)
        dc.SetTextForeground(st.TITLE_FG_COLOR)
        dc.DrawText(title, 0, y)
        self.DrawStar(dc, tw + 6 + self.STAR_RADIUS, y + th // 2)
        if compact or not self.subtitle:
            return
        dc.SetFont(uikit.get_font(self.SUBTITLE_SIZE))
        subtitle = self.subtitle
        if dc.GetTextExtent(subtitle)[0] > width:
            subtitle = self.LimitTextLength(dc, subtitle, width)
        dc.SetTextForeground(st.TITLE_DIM_COLOR)
        # 6 px under the title's descenders
        dc.DrawText(subtitle, 0, th + 4)
        sw, sh = dc.GetTextExtent(subtitle)
        self.tips.Add((0, th + 4, sw, sh), self.subtitle, subtitle)

    def DrawStar(self, dc, cx, cy):
        # as the list's: lit when starred, filled dim under the pointer, smaller held,
        # else a faint outline
        import listbox
        self.star_rect = None
        self.starred = self.IsStarred()
        if self.parent.cue.path is None:
            return
        self.star_rect = wx.Rect(cx - 7, cy - 8, 15, 16)
        r = self.STAR_RADIUS - 1 if self.star_down else self.STAR_RADIUS
        ui = uikit.ui()
        if self.starred:
            listbox.draw_star(dc, cx, cy, r, ui.WARN)
        elif self.star_hover:
            listbox.draw_star(dc, cx, cy, r, ui.BAR_TEXT_DIM)
        else:
            bg = wx.Colour(self.parent.st.PLAY_BG_COLOR)
            fg = wx.Colour(self.parent.st.TITLE_FG_COLOR)
            outline = wx.Colour(*[int(a + (b - a) * 0.22) for a, b in
                                  zip(bg.Get()[:3], fg.Get()[:3])])
            listbox.draw_star_outlines(dc, [(cx + 0.5, cy + 0.5)], r, outline)

    def IsStarred(self):
        path = self.parent.cue.path
        if path is None:
            return False
        if self.parent.IsStreamTrack():
            return path in radio.get_favorite_urls(self.parent.parent.ListBox)
        return path in library.get_favorite_tracks()

    def GetStarTip(self):
        kind = 'Favorites' if self.parent.IsStreamTrack() else 'Favorite tracks'
        return f'Remove from {kind}' if self.starred else f'Add to {kind}'

    def HandleStar(self, event):
        # a button: toggled on its release over it; True when the event is the star's
        rect = self.star_rect
        over = rect is not None and self.onClient\
            and rect.Contains(wx.Point(int(event.X), int(event.Y)))
        if over != self.star_hover:
            self.star_hover = over
            self.reInitBuffer = True
            self.DirectDraw()
        if event.LeftDown and over:
            self.star_down = True
            self.reInitBuffer = True
            self.DirectDraw()
            return True
        if self.star_down is False:
            return False
        if event.LeftUp:
            self.star_down = False
            if over:
                self.ToggleStar()
            self.reInitBuffer = True
            self.DirectDraw()
        # held: no drag nor double click of the title
        return True

    def ToggleStar(self):
        if self.parent.IsStreamTrack():
            radio.toggle_favorite(self.parent.parent, self.parent.cue.path)
        else:
            self.parent.ToggleFavoriteTrack()

    def GetSubtitle(self):
        # the file's folder; for a station its name
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
        # by the cue's own columns, not the playing list's
        value = self.parent.GetPlayingItemInfo(field)
        return '' if value is None else f'{value}'

    def CATCH_EVT_GLOBAL(self, event):
        # if self.parent.parent.HasToSkipEvent(): return
        # self.HandleItemDrag(event)
        starred = self.HandleStar(event)
        held = event.LeftIsDown or event.RightIsDown
        if self.star_hover and held is False:
            # the star's own tip there
            self.tips.Forget()
            if self.GetStarTip() != self.star_tip:
                self.star_tip = self.GetStarTip()
                self.SetToolTip(self.star_tip)
        else:
            if self.star_tip is not None:
                self.star_tip = None
                self.UnsetToolTip()
            self.tips.Update((event.X, event.Y) if self.onClient and held is False else None)
        self.HandleTitleChange(event)
        if starred:
            return
        self.parent.HandleTrackEditor(event, self)
        self.parent.HandleDragOut(self, event, 'file')

    def HandleTitleChange(self, event):
        if (self.GetTitle(), self.GetSubtitle(), self.IsStarred())\
                == (self.title, self.subtitle, self.starred):
            return
        # redrawn on the next frame: a DirectDraw too soon does nothing
        self.reInitBuffer = True
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
        # the header's right end
        return self.parent.GetDeckRight()

    def OnSize(self, event=None):
        left, right = self.GetTextLeft(), self.GetTextRight()
        if self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT:
            # the title, the info chips at the right (PlayBoxInfo)
            right = self.parent.Info.GetRect().x - 12
            self.SetRect((left, self.parent.GetHeaderTop() + 5, max(0, right - left), 23))
        else:
            # the capitals' top at PlayBoxApic.TEXT_TOP (the font's ink offset)
            offset = int(round(uikit.get_caps_ink(uikit.get_font(self.TITLE_SIZE,
                                                                 bold=True))[0]))
            # down to the info's cells, not over them
            self.SetRect((left, self.parent.GetHeaderTop() + PlayBoxApic.TEXT_TOP - offset,
                          max(0, right - left), offset + PlayBoxApic.CELLS))
        self.DirectDraw()


class PlayBoxInfo(RectBox):

    # cells dropped when narrow, first to last (the time stays)
    HIDE_ORDER = (1, 0)

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30

        self.information = GetPreference('playbox_information')
        if self.information is None:
            self.information = '000.0 | - | 00:00:00 | 00:00:00'
        self.segments = self.information.split(SEPARATOR)
        # the time cell: played or left, a click turns it
        self.time_left = bool(GetPreference('playbox_time_left'))
        self.cell_rects = dict()
        self.time_tip = False

        self.SetBackgroundColour(self.parent.st.PLAY_BG_COLOR)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.DrawInfo(dc)

    # the readouts as a rack's displays
    CELL_HEIGHT = 18
    CELL_SLOT = CELL_HEIGHT + 2
    CELL_PAD = 7
    CELL_GAP = 6
    LABEL_GAP = 6

    def GetChips(self):
        # (index, name, value[, width as]): tempo, key, time; 3: a status
        segments = list(self.segments) + [''] * (5 - len(self.segments))
        tempo, key, position, duration, remain = segments[:5]
        # the key as wide as its longest so the cells do not move
        key = (key.strip() or '-').ljust(3) if key else ''
        chips = [(0, 'BPM', tempo.strip()), (1, 'KEY', key)]
        if duration.strip():
            played = f'{position.strip()} / {duration.strip()}'
            left = f'{remain.strip()} / {duration.strip()}'
            widest = max(played, left, key=len)
            chips += [(2, 'LEFT', left, widest) if self.time_left else
                      (2, 'TIME', played, widest)]
        else:
            chips += [(3, '', position.strip())]
        return [v for v in chips if v[2]]

    def GetFonts(self):
        # made once: drawn 30 times a second
        if getattr(self, 'fonts', None) is None:
            value = wx.Font(wx.Size(0, uikit.READOUT), wx.FONTFAMILY_MODERN,
                            wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
            self.fonts = (value, uikit.get_font(uikit.LABEL, bold=True))
        return self.fonts

    def GetCellWidth(self, gc, chip):
        value, label = self.GetFonts()
        uikit.set_font(gc, value, wx.BLACK)
        width = gc.GetTextExtent(chip[3] if len(chip) > 3 else chip[2])[0] + self.CELL_PAD * 2
        if chip[1]:
            uikit.set_font(gc, label, wx.BLACK)
            width += gc.GetTextExtent(chip[1])[0] + self.LABEL_GAP
        return width

    # cells kept together on a row: tempo and key
    GROUPS = ((0, 1),)

    def GetRows(self, gc, chips, width):
        # the cells in rows of width, a group to the next row whole
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

    # a song's cells at their widest: the rows counted by them always
    SONG_CELLS = ((0, 'BPM', '000.0'), (1, 'KEY', 'C#m'),
                  (2, 'LEFT', '-00:00.00 / 00:00.00'))

    def GetRowCount(self, width):
        bitmap = wx.Bitmap(1, 1)
        dc = wx.MemoryDC(bitmap)
        gc = wx.GraphicsContext.Create(dc)
        count = max(len(self.GetRows(gc, self.SONG_CELLS, width)), 1)
        del gc
        dc.SelectObject(wx.NullBitmap)
        return count

    def GetFittingChips(self, gc):
        # the cells that fit the width: time left, key, then tempo dropped
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
        # left-aligned under the title, right-aligned when compact
        st = self.parent.st
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        self.cell_rects = dict()
        width, height = self.GetSize()
        if self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT:
            # one row at the right, the cells that do not fit dropped
            chips = self.GetFittingChips(gc)
            rows = [(width - self.GetChipsWidth(gc, chips), (height - self.CELL_HEIGHT) // 2,
                     chips)]
        else:
            # under the title, a row more for the cells that do not fit
            pad = (self.CELL_SLOT - self.CELL_HEIGHT) // 2
            cells = self.GetRows(gc, self.GetChips(), width)
            # fill the header's rows: a group a row
            want = getattr(self.parent, 'header_rows', 1)
            groups = [[v for v in self.GetChips() if v[0] in group] for group in self.GROUPS]
            groups += [[v] for v in self.GetChips()
                       if all(v[0] not in group for group in self.GROUPS)]
            groups = [g for g in groups if g]
            if len(cells) < want and 1 < len(groups) <= want:
                cells = groups
            rows = [(0, k * self.parent.INFO_ROW + pad, row) for k, row in enumerate(cells)]
        for x, y, chips in rows:
            self.DrawCells(gc, x, y, chips)

    def GetInkTop(self, font, y):
        # the capitals' middle on the cell's inside, on a whole row
        return int(math.floor(uikit.get_caps_top(font, y + 1, self.CELL_HEIGHT - 2) + 0.5))

    def DrawCells(self, gc, x, y, chips):
        st = self.parent.st
        value_font, label_font = self.GetFonts()
        tokens = uikit.ui()
        failed = bool(self.parent.GetStreamFailure())
        for chip in chips:
            index, label, text = chip[:3]
            w = self.GetCellWidth(gc, chip)
            self.cell_rects[index] = wx.Rect(int(x), int(y), int(w), self.CELL_HEIGHT)
            face, edge, ink = st.LCD_BG_COLOR, st.RACK_EDGE_COLOR, st.LCD_TEXT_COLOR
            if index == 3:
                # connecting in the accent, failed in the warning colour
                ink = tokens.WARN if failed else tokens.ACCENT
            gc.SetPen(wx.Pen(wx.Colour(edge), 1))
            gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(face))))
            # corners uikit.RADIUS as every box's
            gc.DrawRoundedRectangle(x + 0.5, y + 0.5, w - 1, self.CELL_HEIGHT - 1,
                                    uikit.RADIUS)
            tx = x + self.CELL_PAD
            if label:
                # the name on the value's capitals' middle
                uikit.set_font(gc, label_font, wx.Colour(st.RACK_LABEL_COLOR))
                gc.DrawText(label, tx, self.GetInkTop(label_font, y))
                tx += gc.GetTextExtent(label)[0] + self.LABEL_GAP
            # the value's capitals centred, not its text box
            uikit.set_font(gc, value_font, wx.Colour(ink))
            gc.DrawText(text, tx, self.GetInkTop(value_font, y))
            x += w + self.CELL_GAP

    def CATCH_EVT_GLOBAL(self, event):
        self.HandleTimeClick(event)
        self.HandleInfoChange(event)
        self.parent.HandleTrackEditor(event, self, menu_only=True)
        self.parent.HandleDragOut(self, event, 'file')

    def HandleTimeClick(self, event):
        rect = self.cell_rects.get(2)
        on = self.onClient and rect is not None and self.IsShown()\
            and rect.Contains(event.X, event.Y)
        if on != self.time_tip:
            # tip on the time cell alone
            self.time_tip = on
            if on:
                self.SetToolTip('Click: the time played or left')
            else:
                self.UnsetToolTip()
        # on the let go, not dragged: a drag is the song's file (HandleDragOut)
        if not on or event.LeftUp is False or getattr(self, 'dragging_out', False)\
                or self.parent.parent.HasToSkipEvent():
            return
        self.time_left = not self.time_left
        SetPreference('playbox_time_left', self.time_left)
        # drawn again now
        self.information = None
        self.HandleInfoChange()

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
        # none known: 0
        pos_sec, dur_sec = (
            self.parent.GetPositionTime() or 0.0, self.parent.cue.duration or 0.0)
        duration = f'{int(dur_sec / 60):02d}:{int(dur_sec % 60):02d}.{int(dur_sec % 1 * 100):02d}'
        position = f'{int(pos_sec / 60):02d}:{int(pos_sec % 60):02d}.{int(pos_sec % 1 * 100):02d}'
        # left: to where it moves on (song's end, highlight's or edit's)
        finish = self.parent.GetTrackFinishTime()
        if not finish or finish < 0:
            finish = dur_sec
        left = max(finish - pos_sec, 0.0)
        remain = f'-{int(left / 60):02d}:{int(left % 60):02d}.{int(left % 1 * 100):02d}'
        segments = [f'{tempo:05.1f}', key, position, duration, remain]
        if self.parent.IsStreamTrack():
            # a station: how long it has played, LIVE
            segments = ['', '', position, 'LIVE']
            connecting = self.parent.GetStreamConnecting()
            if connecting is not None:
                segments = ['', '', f'Connecting {int(connecting)}s', '']
            elif self.parent.GetStreamFailure():
                segments = ['', '', 'Not connected', '']
        information = SEPARATOR.join(segments)
        if information == self.information:
            return
        self.segments = segments
        self.information = information
        # redrawn on the next frame, as HandleTitleChange
        self.reInitBuffer = True
        self.DirectDraw()

    def OnSize(self, event):
        # under the title; at the right end when compact
        w = self.parent.GetClientSize().width
        title = self.parent.Title
        if self.parent.GetHeaderHeight() == self.parent.HEADER_COMPACT:
            width = max(0, min(300, w // 2))
            right = self.parent.GetDeckRight()
            self.SetRect((right - width, self.parent.GetHeaderTop() + 5, width, 23))
        else:
            left, right = title.GetTextLeft(), title.GetTextRight()
            rows = getattr(self.parent, 'header_rows', 1)
            # under the title (PlayBoxApic.TEXT_TOP)
            self.SetRect((left, self.parent.GetHeaderTop() + PlayBoxApic.TEXT_TOP
                          + PlayBoxApic.CELLS, max(0, right - left),
                          PlayBoxInfo.CELL_SLOT + (rows - 1) * self.parent.INFO_ROW))
        self.DirectDraw()


class PlayBoxApic(RectBox):

    # the cover as tall as the text beside it, 8 px round it
    TOP = 8
    # the text beside it 12 px under the rack
    TEXT_TOP = 12
    GAP = 8
    CELLS = 33
    # its bottom at the info's cells
    SIZE = TEXT_TOP - TOP + CELLS + PlayBoxInfo.CELL_SLOT

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
        # ICO too: a station's picture is often its favicon
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
            return self.GetApicImage(path[2]), path

        try:
            file = mutagen.File(path)
            key = [v for v in file.tags.keys() if 'APIC:' in v]
            if key == []:
                return None, path
            artwork = file.tags[key[0]].data
        except Exception:
            return None, path
        return self.GetApicImage(artwork), path

    def GetApicImage(self, artwork):
        # the picture's bytes as an image at its own size, or None
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
        return bmp if bmp.IsOk() and bmp.GetHeight() > 0 else None

    def GetShownImage(self, image):
        # cut to a square on its middle (View > Square Album Images)
        if image is None or self.parent.parent.parent.IsCoverSquareOn() is False:
            return image
        left, top, right, bottom = listimages.get_square_box(image.GetWidth(), image.GetHeight())
        return image.GetSubImage(wx.Rect(left, top, right - left, bottom - top))

    def GetApicBitmap(self, image):
        # the picture scaled into the box, or None
        image = self.GetShownImage(image)
        if image is None:
            return None
        ratio = 1.0 * image.GetWidth() / image.GetHeight()
        width, height = self.GetClientSize()
        w = width - self.margin * 2
        h = height - self.margin * 2
        if ratio < 1:
            w = int(round(w * ratio))
        elif ratio > 1:
            h = int(round(h / ratio))
        if w <= 0 or h <= 0:
            return None
        return image.Scale(w, h, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()

    def GetApicThread(self):
        image, path = self.GetApic(self.path)
        if path != self.path:
            return
        self.apic_image = image
        self.apic = self.GetApicBitmap(image)
        self.reInitBuffer = True
        # self.DirectDraw()

    def SetRectPre(self):
        pass

    def SetRectDraw(self, dc):
        self.DrawApic(dc)

    def CATCH_EVT_GLOBAL(self, event):
        self.HandleApicChange()
        self.HandlePreview(event)
        self.parent.HandleTrackEditor(event, self)
        self.parent.HandleDragOut(self, event, 'cover')
        # self.HandleSizeChange()

    # the cover large beside it on a click
    PREVIEW = 360

    def HandlePreview(self, event):
        if getattr(self, 'previewing', False) and (
                self.onClient is False or self.IsShown() is False
                or wx.GetKeyState(wx.WXK_ESCAPE)):
            self.HidePreview()
            return
        if event.LeftDClick:
            # double click is the tag editor's
            self.HidePreview()
            self.preview_skip = True
            return
        if event.LeftUp is False:
            return
        if getattr(self, 'preview_skip', False):
            self.preview_skip = False
            return
        # a click, not a drag
        if event.rectIdx is None or event.down.rectIdx is None or event.drag.x is not None:
            return
        if getattr(self, 'previewing', False):
            self.HidePreview()
        elif self.apic is not None and getattr(self, 'apic_image', None) is not None:
            self.previewing = True
            self.ShowPreview()

    def ShowPreview(self):
        # the file's own proportions, not the box's square
        image = getattr(self, 'apic_image', None)
        if not self or self.previewing is False or image is None:
            return
        iw, ih = image.GetWidth(), image.GetHeight()
        scale = min(float(self.PREVIEW) / max(iw, ih), 2.0)
        w, h = max(int(iw * scale), 1), max(int(ih * scale), 1)
        if getattr(self, 'preview', None) is None:
            # a popup: it takes neither the focus nor the mouse
            self.preview = wx.PopupWindow(self.GetTopLevelParent(), wx.BORDER_NONE)
            self.preview.Bind(wx.EVT_PAINT, self.OnPreviewPaint)
        self.preview.bitmap = image.Scale(w, h, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()
        # beside the cover at its top, kept on its display
        x, y = self.ClientToScreen((self.GetSize().width + 8, 0))
        index = wx.Display.GetFromWindow(self)
        area = wx.Display(index if index != wx.NOT_FOUND else 0).GetClientArea()
        x = min(x, area.right - w - 1)
        y = min(max(y, area.top), area.bottom - h - 1)
        self.preview.SetRect((x, y, w, h))
        self.preview.Show()
        self.preview.Refresh()

    def OnPreviewPaint(self, event):
        dc = wx.PaintDC(self.preview)
        dc.DrawBitmap(self.preview.bitmap, 0, 0)
        dc.SetPen(wx.Pen(self.parent.st.RACK_EDGE_COLOR, 1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        w, h = self.preview.GetClientSize()
        dc.DrawRectangle(0, 0, w, h)

    def HidePreview(self):
        self.previewing = False
        if getattr(self, 'preview', None) is not None:
            self.preview.Hide()

    def DrawApic(self, dc):
        # rounded by a clip; no picture: a record's label
        width, height = self.GetClientSize()
        st = self.parent.st
        dc.SetBackground(wx.Brush(st.PLAY_BG_COLOR))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None or width <= 0 or height <= 0:
            return
        path = gc.CreatePath()
        # the waveforms' frame's corners
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
        # the track's file; a station's address and picture
        if self.parent.IsStreamTrack():
            url = self.parent.cue.path
            return ('radio', url, radio.get_picture(url))
        return self.parent.cue.path

    def HandleApicChange(self, forced=False):
        source = self.GetApicSource()
        if source == self.path and forced is False:
            return
        self.apic = None
        self.apic_image = None
        self.HidePreview()
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
