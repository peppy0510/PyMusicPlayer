# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import ctypes
import folders
import images
import io
import library
import listimages
import math
import mutagen
import numpy
import os
import mfeats
import playboxlib
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
from rackbox import KNOB_DRAG
from rackbox import Rack
from rackbox import RackModule
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
        # imported here: listbox imports this module
        import listbox
        path = self.cue.path
        if self.IsStreamTrack() or not path:
            return
        tags = audio.get_id3(path, [u'TPE1', u'TIT2']) or dict()
        listbox.look_up_cover_for(self.parent.ListBox, [dict(
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
        import listbox
        add('Copy Cover', lambda: listbox.copy_cover(self.parent, path))
        menu.MenuItems[-1].Enable(listbox.read_cover_of(path) is not None)
        add('Paste Cover', lambda: listbox.paste_cover(
            self.parent.ListBox, [(path, getattr(self.cue, 'mdx', None))]))
        menu.MenuItems[-1].Enable(listbox.has_copied_cover())
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


def get_span_text(seconds):
    # 2.1 s, 45 s, 3:20
    if seconds < 10:
        return f'{seconds:.1f} s'
    if seconds < 60:
        return f'{round(seconds)} s'
    return f'{int(seconds // 60)}:{int(seconds % 60):02d}'


def draw_live_trace(dc, parent, rect, seconds, spread=audio.WAVEFORM_BAND_SPREAD):
    '''a station's last seconds as a scrolling waveform, False for a file'''
    if parent.IsStreamTrack() is False:
        return False
    trace = parent.GetLiveTrace()
    x, y, w, h = rect
    if parent.GetLiveMessage() is not None:
        # nothing to play: a message instead (PlayBox.DrawLiveMessage)
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

    # first button 8 px in
    STRIP_X = 6
    # narrower levels: the transport's keys and LOOP's
    TRANSPORT_SAVE = 32
    LOOP_SAVE = 14
    # the strip's width
    STRIP_WIDTH = 278

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
        # 0: the mode key (HIGHLIGHT or SHORT), 6: MASTER's panel, 8: its menu
        self.toggle_buttons = [True, False, True, False, True, True, False, True, False,
                               False]
        # the mode the key plays: the last chosen
        kind = GetPreference('play_mode_kind')
        self.kind = kind if kind in ('highlight', 'short') else 'highlight'
        self.hovered = None
        # PREV and NEXT: a song before and after the playing one (GetAround)
        self.around = (True, True)
        self.around_drawn = self.around
        self.around_lap = 0.0
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
            # a button with no room is not hit
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
            # LOOP's tip
            if hovered == 4:
                self.SetToolTip(self.GetLoopTip())
            else:
                self.UnsetToolTip()
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
        if self.GetAround() != self.around_drawn:
            self.around_drawn = self.around
            self.reInitBuffer = True
        # the mode key names the mode on
        kind = 'short' if self.parent.IsRadioEditOn() else\
            'highlight' if self.parent.IsHighlightOn() else self.kind
        on = self.parent.IsRadioEditOn() if kind == 'short' else self.parent.IsHighlightOn()
        if kind != self.kind:
            self.kind = kind
            self.reInitBuffer = True
        if on != self.button_status[0]:
            self.button_status[0] = on
            self.SetButtonColors()
        elif self.parent.IsPlaying() and self.button_status[2] is False:
            self.button_status[2] = True
            self.SetButtonColors()
        elif self.parent.IsPlaying() is False and self.button_status[2]:
            self.button_status[2] = False
            self.SetButtonColors()
        elif (self.parent.GetLoopMode() != 'off') != self.button_status[4]:
            self.button_status[4] = self.parent.GetLoopMode() != 'off'
            self.SetButtonColors()
        elif self.parent.GetLoopMode() != getattr(self, 'loop_drawn', None):
            # the list's mark or the song's, and its tip
            self.loop_drawn = self.parent.GetLoopMode()
            if self.hovered == 4:
                self.SetToolTip(self.GetLoopTip())
            self.reInitBuffer = True
        elif self.parent.IsLoudOn() and self.button_status[5] is False:
            self.button_status[5] = True
            self.SetButtonColors()
        elif self.parent.IsLoudOn() is False and self.button_status[5]:
            self.button_status[5] = False
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
        if downIdx == 0:
            self.SetMode(self.kind, status[0])
        if downIdx == 4:
            # off, the list, the song in turn
            self.parent.CycleLoop()
            status[4] = self.parent.GetLoopMode() != 'off'
            self.SetButtonColors()
        if downIdx == 5 and status[5]:
            self.parent.SetLoudOn()
        if downIdx == 5 and status[5] is False:
            self.parent.SetLoudOff()

        if downIdx == 8:
            self.PopupMode()
        if downIdx == 6:
            self.parent.parent.parent.SetMasterShow(self.parent.Master.folded)
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

    # 5: MASTER (Auto Master), 7: SHORT (the radio edit)
    LABELS = ('HIGHLIGHT', None, None, None, 'LOOP', 'MASTER', None, 'SHORT', None, None)

    LOOP_TIPS = {'off': 'Loop: off (click: the list)',
                 'list': 'Loop: the list, its first after its last (click: the song)',
                 'one': 'Loop: the song again at its end (click: off)'}

    def GetLoopTip(self):
        return self.LOOP_TIPS[self.parent.GetLoopMode()]

    def GetLabel(self, i):
        if i == 0:
            return 'SHORT' if self.kind == 'short' else 'HIGHLIGHT'
        if i == 4:
            # LOOP is an icon, its name in the tip (GetLoopTip)
            return None
        return self.LABELS[i]

    def SetMode(self, kind, on):
        # the mode key: HIGHLIGHT or SHORT on or off, the other off with it
        self.kind = kind
        SetPreference('play_mode_kind', kind)
        if kind == 'short':
            self.parent.SetRadioEdit(on)
        elif on:
            self.parent.SetHighlightOn()
            self.parent.GotoTrackOffsetTime()
        else:
            self.parent.SetHighlightOff()
        self.reInitBuffer = True

    def IsModeOn(self):
        if self.kind == 'short':
            return self.parent.IsRadioEditOn()
        return self.parent.IsHighlightOn()

    def ToggleMode(self):
        self.SetMode(self.kind, not self.IsModeOn())

    def SwitchMode(self):
        # the other mode, on if this one was
        self.SetMode('highlight' if self.kind == 'short' else 'short', self.IsModeOn())

    # SHORT on a mix set (PlayBox.MIX_SET_SECONDS): an edit, not a length
    MIX_SET_LABEL = 'Short on a mix set: Edit (intro, outro, breakdowns)'

    @staticmethod
    def GetLengthLabel(kind, length):
        if kind == 'short':
            return f'Short {int(length // 60)}:{int(length % 60):02d}'
        return f'Highlight {int(length // 2)} bars (about {int(length)} s)'

    def GetLengths(self):
        # [(kind, length)]: HIGHLIGHT's lengths, then SHORT's
        frame = self.parent.parent.parent
        return [('highlight', v) for v in frame.MenuBar.highlightDurationItems]\
            + [('short', v[0]) for v in self.parent.RADIO_EDIT_LENGTHS]

    def IsLengthChecked(self, kind, length):
        # the mode the key plays and its length (none on a mix set)
        if kind != self.kind:
            return False
        if kind == 'short':
            return length == self.parent.GetRadioEditLength() and not self.parent.IsMixSet()
        return length == self.parent.GetHighlightStaticPeriodTime()

    def ChooseLength(self, kind, length):
        # a length chosen turns its mode on
        if kind == 'short':
            self.parent.SetRadioEditLength(length)
            if self.parent.IsRadioEditOn() is False:
                self.SetMode('short', True)
            return
        self.kind = kind
        SetPreference('play_mode_kind', kind)
        self.parent.ChangeHighlightLength(length, turn_on=True)
        frame = self.parent.parent.parent
        SetPreference('highlight_duration_type',
                      frame.MenuBar.highlightDurationItems.index(length))
        self.reInitBuffer = True

    def PopupMode(self):
        # the two modes' lengths under the mode key
        menu = wx.Menu()
        previous = None
        for kind, length in self.GetLengths():
            if previous is not None and kind != previous:
                menu.AppendSeparator()
            previous = kind
            item = menu.AppendCheckItem(wx.ID_ANY, self.GetLengthLabel(kind, length))
            item.Check(self.IsLengthChecked(kind, length))
            menu.Bind(wx.EVT_MENU, lambda e, kind=kind, length=length:
                      self.ChooseLength(kind, length), item)
        if self.parent.IsMixSet():
            item = menu.AppendCheckItem(wx.ID_ANY, self.MIX_SET_LABEL)
            item.Check(self.kind == 'short')
            item.Enable(False)
        x, y, w, h = self.rects[0]
        self.menu_open = 8
        self.DirectDraw()
        self.parent.parent.SetPopupMenu(menu, tuple(self.ClientToScreen((x, y + h + 2))),
                                        closed=self.MenuClosed)

    def MenuClosed(self):
        self.menu_open = None
        self.reInitBuffer = True

    def SetRectDraw(self, dc):
        # uikit's faces and the groups' lines
        dc.SetPen(wx.Pen(uikit.ui().BAR_LINE, 1))
        for sx in self.separators:
            dc.DrawLine(sx, 3, sx, self.height - 2)
        if self.parent.IsControlTwoRows():
            # the line between the rows
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
            elif i == 4:
                # loop one: a 1 by it
                icon = 'loop_one' if self.parent.GetLoopMode() == 'one' else 'loop'
            elif i in (8, 9):
                # turned over while its menu is open
                icon = 'up' if getattr(self, 'menu_open', None) == i else 'down'
            elif i == 6:
                # the panel is made after this row
                master = getattr(self.parent, 'Master', None)
                icon = 'up' if master is not None and master.shown else 'down'
            on = toggle and status and i != 2
            # the length key lit with the key it is joined to
            if i in self.JOINED:
                on = self.toggle_buttons[self.JOINED[i]] and self.button_status[self.JOINED[i]]
            down = self.downed_button == i or (not toggle and status and i not in self.JOINED)
            corners = 'right' if i in self.JOINED else 'left' if i in self.JOINED.values()\
                else self.TRANSPORT.get(i, 'all')
            uikit.draw_button(dc, rect, label=self.GetLabel(i), icon=icon, on=on, down=down,
                              hover=self.hovered == i, disabled=self.IsDisabled(i),
                              corners=corners)

    # the length key and the mode key it is joined to
    JOINED = {8: 0}
    # prev, play and next as a group: rounded at its ends
    TRANSPORT = {1: 'left', 2: 'none', 3: 'right'}

    # the mode key and LOOP: off for a station (no length)
    STREAM_DISABLED = (0, 4, 8)

    def IsDisabled(self, idx):
        # PREV and NEXT: nothing before or after the song
        if idx in (1, 3):
            return self.around[0 if idx == 1 else 1] is False
        return idx in self.STREAM_DISABLED and self.parent.IsStreamTrack()

    # how often the list is scanned for the song's neighbours
    AROUND_EVERY = 0.3

    def GetAround(self):
        now = time.time()
        if now - self.around_lap >= self.AROUND_EVERY:
            self.around_lap = now
            self.around = tuple(self.parent.GetCueFileAroundPath(direction) is not None
                                for direction in (-1, 1))
        return self.around

    # Buffered DC

    def OnSize(self, event=None):
        # two rows: the play modes under the transport
        two = self.parent.IsControlTwoRows()
        level = self.parent.GetControlLevel()
        if (two, level) != (getattr(self, 'two_rows', None), getattr(self, 'level', None)):
            self.SetPreInitRects(two, level)
        rows = 2 if two else 1
        # as wide as its keys
        width = max(r[0] + r[2] for r in self.rects) + 2
        self.SetRect((self.STRIP_X, self.parent.GetControlTop() + 5, width,
                      self.height + (rows - 1) * self.parent.CONTROL_HEIGHT))
        self.DirectDraw()

    def SetPreInitRects(self, two=False, level=0):
        # make polygons, rectangles and lines when class starts
        # by index: highlight, prev, play, next, loop, loud, its arrow, short
        x, y, h = (2, 2, 19)
        # 5, 6, 7, 9 have no room here: MASTER is on the rack bar
        d = -self.TRANSPORT_SAVE if level >= 1 else 0
        loop = 40 - (self.LOOP_SAVE if level >= 1 else 0)
        transport = ((x, y, 31, h), (x + 30, y, 34, h), (x + 63, y, 31, h)) if level >= 1\
            else ((x, y, 40, h), (x + 39, y, 48, h), (x + 86, y, 40, h))
        # LOOP beside the transport, a line, then the mode key and its menu
        lx = x + 126 + d + 3
        mx = lx + loop + 14
        rects = ((mx, y, 70, h),) + transport\
            + ((lx, y, loop, h), (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0),
               (mx + 69, y, 20, h), (0, 0, 0, 0))
        self.separators = (lx + loop + 7,)
        if two:
            # the mode key a row under the transport
            y2 = y + 33
            rects = ((x, y2, 70, h), rects[1], rects[2], rects[3], rects[4],
                     rects[5], rects[6], rects[7], (x + 69, y2, 20, h), rects[9])
            self.separators = ()
        self.two_rows = two
        self.level = level
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


# the lanes over what plays: the ground this share to the accent
LANE_PLAYED = 0.4


def draw_snap_flash(dc, x, top, height, share):
    # a snapped seek's line: the accent, 3 px, fading by share
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
    # two decimals as a CDJ, one from 100; 0 without a sign
    text = f'{percent:+.1f}' if abs(percent) >= 99.995 else f'{percent:+.2f}'
    return ' ' + text[1:] if float(text) == 0 else text


def format_semitones(semitones):
    # K+1, K-2; K 0 at 0
    return f'K{int(semitones):+d}' if semitones else 'K 0'


class VolumeSlider(RectBox):

    '''the volume on the rack bar: a mute key and a knob'''

    # the knob's arc is 3 px outside its radius
    LENGTH = 52
    HEIGHT = 23
    KEY = (0, 2, 22, 19)
    KNOB = (40, 11.5, 7)

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.muted_volume = None
        self.hovered = None
        self.drag = None
        # on the rack bar's ground
        self.SetBackgroundColour(self.parent.st.RACK_BG_COLOR)
        self.InitBuffer()

    def GetVolume(self):
        return self.parent.GetVolume()

    def SetVolume(self, volume):
        volume = min(max(volume, 0.0), 1.0)
        if volume == self.GetVolume():
            return
        self.parent.SetVolume(volume)
        self.reInitBuffer = True
        self.ShowLevel()

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
        self.ShowLevel()

    def GetLevelText(self):
        # dB of the amplitude, MUTE when muted, minus infinity at 0
        volume = self.GetVolume()
        if self.IsMuted():
            return 'MUTE'
        if volume <= 0.0:
            return '-\u221e dB'
        return f'{20 * math.log10(volume):.1f} dB'

    def ShowLevel(self):
        # no room for the level on the bar: in the tip
        self.SetToolTip(f'Volume {self.GetLevelText()}')

    def SetRectDraw(self, dc):
        muted = self.IsMuted()
        # the speaker key, warned while muted
        uikit.draw_button(dc, self.KEY, icon='mute' if muted else 'speaker', warn=muted,
                          hover=self.hovered == 'key')
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        cx, cy, r = self.KNOB
        # as MASTER's knobs
        RackModule.DrawKnob(self, gc, cx, cy, 0.0 if muted else self.GetVolume(),
                            self.hovered == 'knob' or self.drag is not None, radius=r)

    def GetHit(self, x, y):
        if wx.Rect(*self.KEY).Contains((x, y)):
            return 'key'
        cx, cy, r = self.KNOB
        if abs(x - cx) <= r + 4 and abs(y - cy) <= r + 3:
            return 'knob'
        return None

    def CATCH_EVT_GLOBAL(self, event):
        hit = self.GetHit(event.X, event.Y) if self.onClient else None
        if hit != self.hovered:
            self.hovered = hit
            self.reInitBuffer = True
        if self.drag is not None:
            if event.LeftIsDown:
                y0, v0 = self.drag
                self.SetVolume(v0 + (y0 - event.y) / float(KNOB_DRAG))
                return
            self.drag = None
            self.reInitBuffer = True
        if self.parent.parent.HasToSkipEvent() or hit is None:
            return
        if hit == 'knob' and event.LeftDClick:
            self.muted_volume = None
            self.SetVolume(1.0)
            return
        if event.LeftDown is False:
            return
        if hit == 'key':
            self.ToggleMute()
        else:
            self.muted_volume = None
            self.drag = (event.y, self.GetVolume())
            self.reInitBuffer = True

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        self.muted_volume = None
        self.SetVolume(self.GetVolume() + event.WheelRotation / 400.0 / 3)

    def OnSize(self, event=None):
        # where MASTER's header put it (MasterPanel.DrawHeaderRight)
        bar = getattr(self.parent, 'Master', None)
        at = getattr(bar, 'volume_at', None)
        if at is None or bar.IsShown() is False:
            self.Hide()
            return
        self.SetRect((at[0], at[1], self.LENGTH, self.HEIGHT))
        self.Show()
        self.ShowLevel()
        self.DirectDraw()


class TempoStrip(RectBox):

    '''the tempo and key faders at the deck's right'''

    RANGES = playboxlib.TEMPO_RANGES
    # within this share of the range from 0 a drag stops at 0
    DETENT = 0.03
    COLUMN = 41
    # the plate's inside at its sides
    PAD = 1
    FADER = 4
    KEY_ROW = 22

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.side = None
        # the key under the pointer, and the one held down
        self.hovered = None
        self.downed = None
        self.SetBackgroundColour(self.parent.st.PLAY_BG_COLOR)
        self.InitBuffer()

    @classmethod
    def GetWidth(cls, count):
        return cls.COLUMN * count - (count - 1) + cls.PAD * 2 if count else 0

    def GetColumns(self):
        return [c for c in ('tempo', 'key') if self.parent.IsStripColumnShown(c)]

    # keys a column
    KEY_ROWS = 2
    # KEY + and KEY -: their marks (uikit.draw_button)
    KEY_MARKS = {'key_up': 'plus', 'key_down': 'minus'}

    def GetKeyRects(self):
        # (column, key, label, on, rect), from the bottom up
        h = self.GetClientSize().height
        keys = []
        span = self.parent.GetTempoRange()
        for k, column in enumerate(self.GetColumns()):
            x = self.PAD + k * (self.COLUMN - 1) + 2
            if column == 'tempo':
                rows = (('lock', 'LOCK', self.parent.IsTempoKeyLockOn()),
                        ('range', 'WIDE' if span >= 100 else f'{int(span)}%', False))
            else:
                # plus and minus drawn by KEY_MARKS
                rows = (('key_down', 'KEY', False), ('key_up', 'KEY', False))
            for r, (key, label, on) in enumerate(rows):
                keys.append((column, key, label, on,
                             wx.Rect(x, h - 3 - 19 - r * self.KEY_ROW, 37, 19)))
        return keys

    def GetSliderRange(self):
        # the faders as long as the keys under them leave
        h = self.GetClientSize().height
        return (26, h - 3 - 19 - (self.KEY_ROWS - 1) * self.KEY_ROW - 10)

    def GetFaderColumn(self, x, y):
        # the column whose fader is at x, y, or None
        top, bottom = self.GetSliderRange()
        columns = self.GetColumns()
        if not columns or not top - 8 <= y <= bottom + 8:
            return None
        index = min(max(int((x - self.PAD) // (self.COLUMN - 1)), 0), len(columns) - 1)
        if self.parent.IsStreamTrack() and columns[index] == 'tempo':
            return None
        return columns[index]

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
        # a station: tempo off, key on (radio.open_stream)
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
                text = format_semitones(self.parent.GetTempoSemitones())
            dc.SetFont(font)
            dc.SetTextForeground(tokens.BAR_TEXT_DIM if disabled else st.LCD_TEXT_COLOR)
            tw, th = dc.GetTextExtent(text)
            dc.DrawText(text, int(self.PAD + index * (self.COLUMN - 1)
                                  + (self.COLUMN - tw) * 0.5), 6)
        for column, key, label, on, rect in self.GetKeyRects():
            disabled = stream and column == 'tempo'
            uikit.draw_button(dc, tuple(rect), label=label, on=on and not disabled,
                              down=self.downed == key, hover=self.hovered == key,
                              disabled=disabled, mark=self.KEY_MARKS.get(key))

    def CATCH_EVT_GLOBAL(self, event):
        # redraw when tempo, key, range or lock changed elsewhere
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
        if self.parent.parent.HasToSkipEvent() or self.onClient is False:
            return
        if event.LeftDClick:
            # a fader double-clicked: back to 0
            column = self.GetFaderColumn(event.X, event.Y)
            if column is not None:
                self.side = None
                if column == 'tempo':
                    self.parent.SetTempoRate(1.0)
                else:
                    self.parent.SetTempoSemitones(0)
                self.Changed()
                return
        if event.LeftDown is False:
            return
        for column, key, label, on, rect in self.GetKeyRects():
            if rect.Contains(position):
                if stream and column == 'tempo':
                    return
                self.downed = key
                self.Press(key)
                self.Changed()
                return
        column = self.GetFaderColumn(event.X, event.Y)
        if column is not None:
            self.side = column
            self.Slide(event.Y)

    def Press(self, key):
        if key == 'lock':
            self.parent.SetTempoKeyLock(self.parent.IsTempoKeyLockOn() is False)
        elif key == 'range':
            ranges = self.RANGES
            current = self.parent.GetTempoRange()
            index = ranges.index(current) if current in ranges else -1
            self.parent.SetTempoRange(ranges[(index + 1) % len(ranges)])
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
        # the range's step a notch, as a CDJ
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

    def OnSize(self, event=None):
        # from the header's top to the waveforms' frame's bottom; none: hidden
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

    # left of TEMPO: where a click or drag on the waveforms lands
    # (beat, bar, 4 bars or anywhere); the arrow picks the unit
    LENGTH = 102
    FACE = (1, 2, 80, 19)
    # joined to it, their edge shared
    ARROW = (80, 2, 20, 19)

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.hovered = False
        self.SetBackgroundColour(uikit.ui().BAR_BG)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        # its unit named while off too
        unit = self.parent.GetSnapUnit()
        label = dict((v[0], v[1]) for v in self.parent.SNAP_MODES)[unit]
        disabled = self.parent.IsStreamTrack()
        part, down = getattr(self, 'state', (None, None))
        on = self.parent.GetSnapMode() != 'off'
        uikit.draw_button(dc, self.FACE, label=f'SNAP {label.upper()}', on=on,
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
        if event.LeftDown:
            # a press elsewhere: nothing held
            self.down = None
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
            item = menu.AppendCheckItem(wx.ID_ANY, label)
            item.Check(mode == self.parent.GetSnapUnit())
            menu.Bind(wx.EVT_MENU, lambda e, mode=mode: self.Choose(mode), item)
        # under the key, from its face's left
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
        if self.parent.IsControlTwoRows():
            # two rows: the second's right end
            self.Show()
            self.SetRect((w - 5 - self.LENGTH, self.parent.GetControlTop()
                          + self.parent.CONTROL_HEIGHT + 5, self.LENGTH, 23))
            self.DirectDraw()
            return
        # the row's right end
        x = w - 5 - self.LENGTH
        self.Show()
        self.SetRect((x, self.parent.GetControlTop() + 5, self.LENGTH, 23))
        self.DirectDraw()


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


class PlayBoxSpectrum(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.scale = 1
        self.max_scale = 3
        # 300 at most
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
        # the ground and the bars as one picture
        w, h = self.GetSize()
        if w <= 0 or h <= 0:
            return
        scale = 0.4
        xs = numpy.array(self.GetBarSlots(w))
        levels = self.FitBarLevels(spectrum, len(xs))
        talls = (levels * h * scale).astype(int)
        # no bar under 2 px
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
        # a bar every bar_pitch pixels across the box
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
        # the bins follow the width, the bars fitted to it (FitBarLevels)
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
        # a square, the L and R axes as an X
        self.size = 56
        self.margin = 2
        self.vectorscope = None
        # earlier frames fade like a phosphor screen (rates at 30 fps);
        # the gain follows the track slowly to fill the scope
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
            # the spectrum hidden: read its frame here for the samples
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
        self.ahead = None
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

        # the frame 8 px from the window's edges or the tempo strip
        leftPad = 12
        self.height = self.parent.parent.parent.GetWaveformHeight()
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
        same_width = len(self.last_size) == 4 and self.last_size[2] == rect[2]
        self.last_size = rect
        self.SetRect(rect)
        # while resizing the last waveform is stretched, painted after
        if self.wave_exact is None:
            self.parent.reInitWave = True
        elif same_width:
            # its height alone: painted now from the kept columns
            if self.resize_timer is not None:
                self.resize_timer.Stop()
            self.SetRectWave(now=True)
            self.SetRectHighlight()
            self.InitBuffer()
        else:
            self.StretchWave()
            if self.resize_timer is None:
                self.resize_timer = wx.CallLater(150, self.OnResized)
            else:
                self.resize_timer.Start(150)
        self.DirectDraw()

    def SettleNow(self):
        # a single step's new width: painted now, no stretch
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
        # with the grid shown, a lane above and below for its ticks
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
        # a station: the last half minute of what it plays
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
        # the line a seek snapped to, lit till it fades
        flash = self.parent.GetSnapFlash()
        duration = self.parent.GetDurationTime()
        if flash is None or duration <= 0:
            return
        x, y, w, h = self.wave_rect
        draw_snap_flash(dc, int(math.ceil(x + flash[0] * w / duration)), 0,
                        self.GetSize().height, flash[1])
        self.redraw_next = True

    def DrawPlayedLanes(self, dc):
        # the grid's lanes over what plays, tinted (LANE_PLAYED)
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
        # every 16 bars across, brighter in the lanes; every 4 bars in the
        # lanes when 6 px apart; from the first phrase, else the downbeat
        grid = self.parent.GetGrid()
        duration = self.parent.GetDurationTime()
        if grid is None or duration <= 0 or self.wave_bitmaps is None\
                or self.parent.IsGridShown() is False:
            return
        known = self.parent.IsGridPhraseKnown()
        anchor = self.parent.GetGridPhraseStart() if known else self.parent.GetGridDownbeat()
        # lines cached per song, size and theme, drawn a list a pen
        key = (grid.bpm, anchor, known, duration, tuple(self.wave_rect),
               tuple(self.parent.st.PLAY_BG_COLOR))
        cache = getattr(self, 'grid_lines', None)
        if cache is None or cache[0] != key:
            cache = self.grid_lines = (key, self.MakeGridLines(grid, anchor, known, duration))
        for pen, lines in cache[1]:
            if lines:
                dc.DrawLineList(lines, pens=pen)

    def MakeGridLines(self, grid, anchor, known, duration):
        # [(pen, [(x1, y1, x2, y2), ...])]: across, in the lanes, 4 bars
        x, y, w, h = self.wave_rect
        span = 60.0 / grid.bpm * 64
        if span / duration * w < 6:
            return []
        bg = wx.Colour(self.parent.st.PLAY_BG_COLOR)

        def light(share):
            return wx.Pen(wx.Colour(*[int(v + (255 - v) * share)
                                      for v in (bg.Red(), bg.Green(), bg.Blue())]), 1)

        across, lanes, fours = [], [], []
        lane = PlayBoxWaveDetail.GRID_LANE
        bottom = y + h
        # 4 bars a step
        phrase = span / 4
        seconds = anchor % phrase
        index = -int(round((anchor - seconds) / phrase))
        # DrawLineList leaves out the last pixel too
        while seconds < duration:
            lx = int(x + seconds * w / duration)
            if index % 4 == 0:
                if known:
                    across.append((lx, y, lx, bottom))
                lanes.append((lx, y - lane, lx, y))
                lanes.append((lx, bottom, lx, bottom + lane))
            elif phrase / duration * w >= 6:
                fours.append((lx, y - lane, lx, y - lane // 2))
                fours.append((lx, bottom + lane // 2, lx, bottom + lane))
            seconds += phrase
            index += 1
        return [(light(0.35), across), (light(0.9), lanes), (light(0.5), fours)]

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
        # none left from the track before
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
        # rounded as DrawCursor (ceil)
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
        # SHORT: what it skips dimmed, what it plays in full
        x, y, w, h = self.wave_rect
        duration = self.parent.GetDurationTime()
        dc.DrawBitmap(self.wave_bitmaps[1], x, y)
        if duration <= 0:
            return
        start, end, cuts = self.parent.GetRadioEdit()
        bounds = [start] + [v for cut in cuts for v in cut] + [end]
        # what it plays on the highlight's ground
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
        # now: painted on this thread at once, not stretched first
        x, y, w, h = self.GetWaveRect()
        self.wave_rect = (x, y, w, h)
        waveform = self.parent.GetWaveform()
        self.wave_job += 1
        if audio.is_waveform_3band(waveform) is False or w <= 0 or h <= 0:
            self.wave_bitmaps = None
            self.wave_exact = None
            self.wave_source = None
            return
        # painted on a thread: a long mix blocked the window; till then the
        # same song's last waveform is stretched, a new song's is flat
        if self.wave_source is waveform and self.wave_exact is not None:
            self.StretchWave()
        else:
            self.wave_bitmaps = None
            self.wave_exact = None
        self.wave_source = waveform
        grounds = self.GetWaveGrounds()
        job = self.wave_job
        ahead = self.ahead
        if ahead is not None and ahead[0] is waveform and ahead[1] == (w, h, grounds):
            # painted while the stream opened (PaintAhead)
            self.ahead = None
            self.SetWaveImages(job, (x, y, w, h), ahead[2])
            return

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

    def GetWaveGrounds(self):
        # normal, dimmed outside the highlight, on the highlight ground
        bgcolor = self.parent.st.PLAY_BG_COLOR
        hlcolor = self.parent.st.HIGHLIGHT_BG_COLOR
        return ((bgcolor, 1.0), (bgcolor, self.highlight_dim), (hlcolor, 1.0))

    def PaintAhead(self, waveform):
        # on the prefetch thread: painted at the last size for SetRectWave
        if audio.is_waveform_3band(waveform) is False:
            return
        _, _, w, h = self.wave_rect
        if w <= 0 or h <= 0:
            return
        grounds = self.GetWaveGrounds()
        images = [audio.paint_waveform_3band(waveform, w, h, ground=ground, dim=dim).tobytes()
                  for ground, dim in grounds]
        self.ahead = (waveform, (w, h, grounds), images)

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
        # the grid's menu, at the time clicked on the whole song
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
        # pressed: a marker follows the drag; let go: plays from the snapped point
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
        # where the press or the drag is now, unsnapped, or None
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
        # seconds across at first: fine enough to scratch
        # self.span = 12.0
        self.span = 5.0
        self.span_least = 1.5
        self.span_most = 3 * 60 * 60
        self.span_step = 1.25
        self.drag_least = 4
        self.highlight_dim = 0.45
        self.drag = None
        # the strip is the record: playing, a press stops it and a drag
        # scratches; paused, a drag seeks. a click alone does not seek
        self.scratching = None
        self.last_key = None
        self.last_step = 0
        self.last_bitmap = None
        # the zoom chip's left, the bar numbers kept off it
        self.chips_left = None
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
        # the hand is read off the cursor (ScratchPress), at the view's scale
        # but no coarser than the scale heard clean
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
        # hidden when off or while a message takes the waveforms' place
        if self.parent.parent.parent.IsWaveformDetailShowOn() is False\
                or getattr(self.parent, 'live_message', None) is not None:
            self.drag = None
            self.Hide()
            return
        self.Show()
        self.height = self.parent.parent.parent.GetWaveformHeight('detail')
        x, y, w, h = self.parent.Wave.GetRect()
        self.SetRect((x, y - self.height - self.gap, w, self.height))
        # not painted here: a new width is a new key (DrawDetailWave)
        self.DirectDraw()

    def GetSpan(self):
        duration = self.parent.GetDurationTime()
        if duration <= 0:
            return self.span
        return min(self.span, duration)

    def GetCentre(self):
        # a drag belongs to the track it began on
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

    # the zoom chip: bars across when the grid is known, else seconds
    CHIP_TOP = 3
    CHIP_HEIGHT = 17

    # least pixels between numbered bars
    NUMBER_SPACING = 64

    def SetRectDraw(self, dc):
        self.DrawStrip(dc)
        self.DrawChips(dc)
        self.DrawBarNumbers(dc)

    def DrawBarNumbers(self, dc):
        # bar numbers by their lines: every bar, 4 or 16 by the zoom
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
        # from the phrase's first bar when it is known, else from bar 1
        anchor = self.parent.GetGridPhraseBars() if self.parent.IsGridPhraseKnown() else 0
        first = int(math.floor((start - downbeat) / bar))
        last = int(math.ceil((start + span - downbeat) / bar))
        st = self.parent.st
        # small and dimmed
        dc.SetFont(wx.Font(wx.Size(0, 9), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                           wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO))
        for index in range(max(first, 0), last + 1):
            if every > 1 and (index - anchor) % every:
                continue
            x = int(self.margin + (downbeat + index * bar - start) / pixel)
            if x < self.margin or x > self.margin + w - 8:
                continue
            text = f'{index + 1}'
            tw, th = dc.GetTextExtent(text)
            if self.chips_left is not None and x + tw + 6 >= self.chips_left\
                    and 2 + th >= self.CHIP_TOP:
                continue
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(st.PLAY_BG_COLOR))
            dc.DrawRectangle(x + 2, 1, tw + 4, th + 1)
            dc.SetTextForeground(st.TITLE_DIM_COLOR)
            dc.DrawText(text, x + 4, 1)

    def GetZoomText(self):
        span = self.GetSpan()
        if self.parent.IsStreamTrack():
            return get_span_text(min(self.span, radio.TRACE_SECONDS))
        grid = self.parent.GetGrid()
        if grid is None or not grid.bpm:
            return get_span_text(span)
        bars = span * grid.bpm / 240.0
        value = f'{round(bars)}' if bars >= 10 else (f'{bars:.1f}').rstrip('0').rstrip('.')
        return f'{value} BAR{"" if value == "1" else "S"}'

    def DrawChips(self, dc):
        self.chips_left = None
        w, h = self.GetSize()
        if w < 200 or h < 20:
            return
        st = self.parent.st
        y, ch = self.CHIP_TOP, self.CHIP_HEIGHT
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        # a readout on the waveform, its ground a little see-through
        text = self.GetZoomText()
        font = wx.Font(wx.Size(0, 11), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
        uikit.set_font(gc, font, wx.Colour(st.CHIP_FG_COLOR))
        tw, th = gc.GetTextExtent(text)[:2]
        cw = int(tw) + 14
        x = w - self.margin - 4 - cw
        face = wx.Colour(st.CHIP_BG_COLOR)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(face.Red(), face.Green(), face.Blue(), 225))))
        gc.DrawRoundedRectangle(x, y, cw, ch, uikit.RADIUS)
        gc.DrawText(text, x + 7, y + (ch - th) / 2.0)
        self.chips_left = x

    def DrawStrip(self, dc):
        w, h = self.GetSize()
        w -= self.margin * 2
        if w <= 0 or h <= 0:
            return
        # a station: its last seconds at the strip's zoom
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
        # the line a seek snapped to, lit till it fades
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
        # on whole pixels, or the picture shimmers as it scrolls; while
        # resizing the strip keeps its scale, painted after
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
        # a strip three windows wide, painted again only near its ends
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
            # what plays on the highlight's ground, the rest dimmed
            if played:
                inside = numpy.zeros(len(times), dtype=bool)
                for a, b in played:
                    inside |= (times >= a) & (times < b)
                hlcolor = numpy.array(self.parent.st.HIGHLIGHT_BG_COLOR, dtype=float)
                ground = numpy.where(inside[:, None], hlcolor, bgcolor)
                dim = numpy.where(inside, 1.0, self.highlight_dim)
            columns = len(waveform) / duration
            # with the grid shown, a lane above and below for its ticks
            lane = self.GRID_LANE if gridkey is not None and h > self.GRID_LANE * 4 else 0
            image = audio.paint_waveform_3band(
                waveform, w * 3, h - lane * 2, ground=ground, dim=dim,
                start=start * columns, end=(start + span * 3) * columns, spread=0)
            if lane:
                band = numpy.broadcast_to(numpy.array(ground, dtype=float), (w * 3, 3))
                if played:
                    # over what plays, tinted (LANE_PLAYED)
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

    # the grid's tick lanes above and below the waveform (px)
    GRID_LANE = 4

    def PaintGridLines(self, image, start, pixel, lane=0):
        # the beat grid lightened in: beats left out under 4 px apart;
        # ticks in the lanes: a beat's half the lane, a bar's all of it
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
        # up narrows, down widens; kept as chosen (GetSpan fits it)
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
        # a drag seeks, let go where it should play; a scratch has the press
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
                # free while it moves; snapped when let go (SeekTo)
                self.drag.time = self.drag.start - 1.0 * dx / width * self.GetSpan()
            return
        drag = self.drag
        self.drag = None
        if drag.moved:
            position = drag.time
        elif self.parent.GetWaveformMode() == 'seek':
            # seek mode: a click plays from where it is
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
        # on the grid as SNAP says
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
        # parent: the PlayBox; seconds: where the strip was clicked
        wx.Menu.__init__(self)
        self.parent = parent
        self.seconds = seconds
        grid = self.parent.GetGrid()
        if grid is None:
            item = self.Append(wx.ID_ANY, 'No beat grid yet')
            item.Enable(False)
            return
        # the time clicked, shown in the labels
        at = f'{int(seconds // 60)}:{seconds % 60:04.1f}'
        labels = (f'Bar starts on this beat ({at})', 'Bar starts at the play position',
                  'Bar one beat earlier', 'Bar one beat later', 'Bar as analyzed')
        for label, handler in zip(labels, (self.OnHere, self.OnHerePlaying, self.OnEarlier,
                                           self.OnLater, self.OnAnalyzed)):
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        labels = (f'Phrase starts on this bar ({at})', 'Phrase starts at the play position',
                  'Phrase as analyzed')
        for label, handler in zip(labels, (self.OnPhraseHere, self.OnPhraseHerePlaying,
                                           self.OnPhraseAnalyzed)):
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        source = 'Beat This!' if grid.source.startswith('beatthis') else 'the beats alone'
        if grid.source.endswith('+changes'):
            source += ', moved by the song\'s changes'
        item = self.Append(wx.ID_ANY, f'{grid.bpm:.3f} BPM, bar from {source}')
        item.Enable(False)
        self.AppendSeparator()
        scale = grid.bpm_scale or 1.0
        labels = [(f'Tempo x2 ({grid.bpm * 2:.2f} BPM)', self.OnTempoDouble),
                  (f'Tempo /2 ({grid.bpm / 2:.2f} BPM)', self.OnTempoHalf)]
        if scale != 1.0:
            labels.append((f'Tempo as analyzed ({grid.bpm / scale:.2f} BPM)',
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
