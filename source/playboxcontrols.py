# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import images
import math
import numpy
import playboxlib
import time
import uikit
import wx

from macroboxlib import FONT_PLAYINFO
from macroboxlib import GetPreference
from macroboxlib import SetPreference
from macroboxlib import RectBox
from rackbox import KNOB_DRAG
from rackbox import RackModule
from utilities import Struct


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
