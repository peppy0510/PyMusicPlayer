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
import threading
import time
import wx

from PIL import Image
from macroboxlib import COLOR_TOOLBAR_BG
from macroboxlib import FONT_ITEM
from macroboxlib import FONT_PLAYINFO
from macroboxlib import GetPreference
from macroboxlib import PaintUnpainted
from macroboxlib import RectBox
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
        self.VolumeDropdown = VolumeDropdown(self)
        self.TempoButton = TempoButton(self)
        self.TempoDropdown = TempoDropdown(self)
        self.AudioControl = AudioControl(self)
        self.InitBuffer()

    def IsSideWideEnough(self):
        w, _ = self.GetSize()
        if w >= 840:
            return True
        return False

    def GetWaveTop(self):
        if self.WaveDetail.IsShown():
            return self.WaveDetail.GetRect().y
        return self.Wave.GetRect().y

    def SetRectDraw(self, dc):
        width, height = self.GetSize()
        rects = [(-1, 0, width + 2, 33)]
        dc.DrawRectangleList(rects, pens=wx.Pen((0, 0, 0), 1), brushes=wx.Brush(COLOR_TOOLBAR_BG))

    def OnSize(self, event=None):
        self.Freeze()
        self.DirectDraw()
        self.Title.OnSize(None)
        self.Wave.OnSize(None)
        self.WaveDetail.OnSize(None)
        self.Info.OnSize(None)
        # self.InfoR.OnSize(None)
        self.Spectrum.OnSize(None)
        self.VectorScope.OnSize(None)
        self.Apic.OnSize(None)
        self.ControlButton.OnSize(None)
        self.VolumeSlider.OnSize(None)
        self.TempoButton.OnSize(None)
        self.DirectDraw()
        self.Thaw()

    def CATCH_EVT_GLOBAL(self, event):

        self.AudioEvent(event)

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
            self.SetBestHighlightVariablePeriodTime(static=value)
            if self.IsHighlightOn() is False:
                self.SetHighlightOn()
            if self.IsPlaying() and self.IsHighlightOn():
                self.GotoTrackOffsetTime()
                self.reInitWave = True
                self.OnSize()
            elif self.IsHighlightOn():
                self.GotoTrackOffsetTime()
                self.reInitWave = True
                self.OnSize()
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
        return [getattr(parent, name, None)
                for name in ('Spectrum', 'VectorScope', 'Wave', 'WaveDetail')]

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
        if self.parent.IsPlaying() is False:
            return
        for box in self.GetBoxes():
            if box is not None and box.IsShown():
                box.DirectDraw()
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


class PlayBoxControlButton(RectBox):

    STRIP_X = 5
    STRIP_WIDTH = 260

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
        self.button_flash = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.button_status = [False, False, False, False, False, False]
        self.toggle_buttons = [True, False, True, False, True, True]
        self.SetBackgroundColour((35, 35, 35))
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
            if self.IsInRect(self.rects[i], xy):
                return i
        return None

    def CATCH_EVT_GLOBAL(self, event):
        self.OverrideStatusFromParent()
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleEventButtonStatus(event)
        self.HandleEventPlayControl(event)
        self.HandleButtonFlash(event)
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

    def HandleEventPlayControl(self, event):
        if event.LeftDown is False:
            return
        if event.down.rectIdx is None:
            return
        status = self.button_status
        downIdx = event.down.rectIdx
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

    def SetRectDraw(self, dc):
        button_colors = self.button_colors

        # exec('bmp = self.bmp.highlight_%s' % (button_colors[0]))
        bmp = getattr(self.bmp, 'highlight_%s' % (button_colors[0]))
        dc.DrawBitmap(bmp, 1, 1, useMask=False)
        # exec('bmp = self.bmp.fr_%s' % (button_colors[1]))
        bmp = getattr(self.bmp, 'fr_%s' % (button_colors[1]))
        dc.DrawBitmap(bmp, 60, 1, useMask=False)
        # exec('bmp = self.bmp.play_%s' % (button_colors[2]))
        bmp = getattr(self.bmp, 'play_%s' % (button_colors[2]))
        dc.DrawBitmap(bmp, 100, 1, useMask=False)
        # exec('bmp = self.bmp.ff_%s' % (button_colors[3]))
        bmp = getattr(self.bmp, 'ff_%s' % (button_colors[3]))
        dc.DrawBitmap(bmp, 140, 1, useMask=False)
        # exec('bmp = self.bmp.loop_%s' % (button_colors[4]))
        bmp = getattr(self.bmp, 'loop_%s' % (button_colors[4]))
        dc.DrawBitmap(bmp, 140 + 40, 1, useMask=False)
        # exec('bmp = self.bmp.loud_%s' % (button_colors[5]))
        bmp = getattr(self.bmp, 'loud_%s' % (button_colors[5]))
        dc.DrawBitmap(bmp, 140 + 40 * 2, 1, useMask=False)

        dc.DrawLineList(self.lines, pens=wx.Pen((0, 0, 0), 1))

    # Buffered DC

    def OnSize(self, event=None):
        self.SetRect((self.STRIP_X, 5, self.STRIP_WIDTH, self.height))
        self.DirectDraw()

    def SetPreInitRects(self):
        # make polygons, rectangles and lines when class starts
        x, y, h = (2, 2, 19)
        rects = ((x, y, 56, h), (59 + x, y, 37, h), (99 + x, y, 37, h),
                 (139 + x, y, 37, h), (179 + x, y, 37, h), (219 + x, y, 37, h),)
        self.rects = rects
        rx = rects[-1][0] + rects[-1][2] + 1
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


class VolumeSlider(RectBox):

    # a button beside the control buttons, its slider dropping down under it
    LENGTH = 40

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.volume = 1.0
        self.buffer.fps = 30
        self.muted_volume = None
        self.font = wx.Font(wx.Size(0, 8), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                            wx.FONTWEIGHT_BOLD, faceName='Arial')
        self.SetBackgroundColour((35, 35, 35))
        self.InitBuffer()

    def IsPopupShown(self):
        # the dropdown is made after the button, which draws itself first
        dropdown = getattr(self.parent, 'VolumeDropdown', None)
        return dropdown is not None and dropdown.IsShown()

    def SetRectDraw(self, dc):
        # drawn as the control buttons' bitmaps are: 39x21, a 1px margin, a 1px border
        # muted: toggled on (red) and named so
        text = 'VOL'
        if self.IsMuted():
            fill, label, text = ((255, 120, 120), (0, 0, 0), 'MUTE')
        elif self.IsPopupShown():
            fill, label = ((180, 180, 180), (0, 0, 0))
        else:
            fill, label = ((0, 0, 0), (125, 125, 125))
        dc.SetPen(wx.Pen((10, 10, 10), 1))
        dc.SetBrush(wx.Brush(fill))
        dc.DrawRectangle(1, 2, 37, 19)
        # the strip's black frame carried on: top, bottom and the right end (its
        # left end is the strip's last line)
        dc.DrawLineList([(0, 0, 40, 0), (0, 22, 40, 22), (39, 0, 39, 23)],
                        pens=wx.Pen((0, 0, 0), 1))
        dc.SetFont(self.font)
        dc.SetTextForeground(label)
        w, h = dc.GetTextExtent(text)
        dc.DrawText(text, int((39 - w) * 0.5), int(1 + (21 - h) * 0.5))

    def CATCH_EVT_GLOBAL(self, event):
        if self.IsPopupShown():
            self.parent.VolumeDropdown.FollowButton(event)
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleButtonStatus(event)

    def GetVolume(self):
        return self.parent.GetVolume()

    def SetVolume(self, volume):
        if volume < 0.0:
            volume = 0.0
        elif volume > 1.0:
            volume = 1.0
        if volume == self.GetVolume():
            return
        self.parent.SetVolume(volume)
        if self.IsPopupShown():
            self.parent.VolumeDropdown.Refresh(False)
        self.reInitBuffer = True

    def CATCH_EVT_MOUSEWHEEL(self, event):

        if self.onClient is False:
            return
        volume = self.GetVolume()
        diff = event.WheelRotation / 400.0 / 3
        self.SetVolume(volume + diff)
        self.muted_volume = None
        self.reInitBuffer = True

    def HandleButtonStatus(self, event):
        if event.down.rectIdx is None:
            return
        # a click opens or closes the dropdown, nothing more: a double click
        # muted, and two quick clicks to open and close it muted by surprise
        # if event.LeftDClick:
        #     self.HidePopup()
        #     self.ToggleMute()
        #     self.reInitBuffer = True
        if event.LeftDown:
            self.ShowPopup()

    def ShowPopup(self):
        if self.IsPopupShown():
            self.parent.VolumeDropdown.HideDropdown()
        else:
            self.parent.VolumeDropdown.ShowDropdown()

    def HidePopup(self):
        if self.IsPopupShown():
            self.parent.VolumeDropdown.HideDropdown()

    def IsMuted(self):
        return self.muted_volume is not None

    def ToggleMute(self):
        if self.muted_volume is None:
            self.muted_volume = self.GetVolume()
            self.SetVolume(0)
        elif self.muted_volume is not None:
            self.SetVolume(self.muted_volume)
            self.muted_volume = None
        self.reInitBuffer = True

    def OnSize(self, event=None):
        # x, y, w, h = self.parent.Wave.GetRect()
        # self.SetRect((x + w + 4 + 4, y - 1, 10, h))
        x = PlayBoxControlButton.STRIP_X + PlayBoxControlButton.STRIP_WIDTH
        self.SetRect((x, 5, self.LENGTH, 23))
        self.DirectDraw()


class VolumeDropdown(wx.PopupWindow):

    # the volume slider dropped down under its button, a window of its own so
    # nothing in the player draws over it; it never takes the mouse, so the
    # buttons still see their presses let go
    def __init__(self, parent):
        wx.PopupWindow.__init__(self, parent, wx.BORDER_NONE)
        self.parent = parent
        self.width = 4
        self.pad = 8
        self.sliding = False
        # the slider, and the mute button under it; as wide as the VOL button's
        # cell, its black frame lines included
        self.SetSize((41, 134))
        self.rect_mute = (2, 134 - 3 - 19, 37, 19)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouse)
        self.Bind(wx.EVT_MOTION, self.OnMouse)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()
        dc.SetPen(wx.Pen((0, 0, 0), 1))
        dc.SetBrush(wx.Brush((35, 35, 35)))
        dc.DrawRectangle(0, 0, w, h)
        x = (w - self.width) * 0.5
        top, bottom = self.GetSliderRange()
        volume = self.parent.GetVolume()
        rects = [(x - 1, top - 1, self.width + 2, bottom - top + 2),
                 (x, bottom, self.width, -volume * (bottom - top))]
        rects = [[int(v) for v in rect] for rect in rects]
        st = self.parent.st
        pens = [wx.Pen(st.VOLUME_PN_COLOR, 1), wx.Pen(st.VOLUME_FG_COLOR, 1)]
        brushes = [wx.Brush(st.VOLUME_BG_COLOR), wx.Brush(st.VOLUME_FG_COLOR)]
        dc.DrawRectangleList(rects, pens=pens, brushes=brushes)
        self.DrawMuteButton(dc)

    def GetSliderRange(self):
        return (self.pad, self.rect_mute[1] - self.pad)

    def DrawMuteButton(self, dc):
        # drawn as the control buttons are: red while toggled on
        if self.parent.VolumeSlider.IsMuted():
            fill, label = ((255, 120, 120), (0, 0, 0))
        else:
            fill, label = ((0, 0, 0), (125, 125, 125))
        x, y, w, h = self.rect_mute
        dc.SetPen(wx.Pen((10, 10, 10), 1))
        dc.SetBrush(wx.Brush(fill))
        dc.DrawRectangle(x, y, w, h)
        dc.SetFont(self.parent.VolumeSlider.font)
        dc.SetTextForeground(label)
        tw, th = dc.GetTextExtent('MUTE')
        dc.DrawText('MUTE', int(x + (w - tw) * 0.5), int(y + (h - th) * 0.5))

    def OnMouse(self, event):
        button = self.parent.VolumeSlider
        if event.LeftDown():
            if wx.Rect(*self.rect_mute).Contains(event.GetPosition()):
                self.sliding = False
                button.ToggleMute()
                self.Refresh(False)
                return
            self.sliding = True
        if event.LeftIsDown() is False:
            self.sliding = False
        if self.sliding is False:
            return
        top, bottom = self.GetSliderRange()
        button.SetVolume(1.0 * (bottom - event.GetY()) / (bottom - top))
        button.muted_volume = None
        button.reInitBuffer = True

    def OnMouseWheel(self, event):
        button = self.parent.VolumeSlider
        button.SetVolume(self.parent.GetVolume() + event.GetWheelRotation() / 400.0 / 3)
        button.muted_volume = None
        button.reInitBuffer = True
        self.Refresh(False)

    def GetBestPosition(self):
        button = self.parent.VolumeSlider
        # from the strip's line left of the button, its top on the strip's bottom line
        x, y = button.ClientToScreen((-1, 22))
        return (x, y)

    def ShowDropdown(self):
        self.SetPosition(self.GetBestPosition())
        self.Show()
        self.Refresh(False)
        self.parent.VolumeSlider.reInitBuffer = True

    def HideDropdown(self):
        self.Hide()
        self.parent.VolumeSlider.reInitBuffer = True

    def FollowButton(self, event):
        # closed by a press anywhere else, or when the player is left; kept
        # under its button when the player moves
        if self.IsShown() is False:
            return
        foreground = ctypes.windll.user32.GetForegroundWindow()
        if foreground not in (wx.GetTopLevelParent(self.parent).GetHandle(), self.GetHandle()):
            self.HideDropdown()
            return
        if event.LeftDown and self.GetScreenRect().Contains((event.x, event.y)) is False\
                and self.parent.VolumeSlider.onClient is False:
            self.HideDropdown()
            return
        position = self.GetBestPosition()
        if tuple(self.GetPosition()) != tuple(position):
            self.SetPosition(position)


class TempoButton(VolumeSlider):

    # beside VOL, its slider dropping down the same way: the tempo in percent, the
    # key lock and the range under it
    LENGTH = 40

    def IsPopupShown(self):
        dropdown = getattr(self.parent, 'TempoDropdown', None)
        return dropdown is not None and dropdown.IsShown()

    def SetRectDraw(self, dc):
        # off 0%: toggled on (red), its percent the label
        percent = (self.parent.GetTempoRate() - 1.0) * 100.0
        text = 'TEMPO'
        if abs(percent) > 1e-6:
            fill, label, text = ((255, 120, 120), (0, 0, 0), '%+.1f' % (percent))
        elif self.IsPopupShown():
            fill, label = ((180, 180, 180), (0, 0, 0))
        else:
            fill, label = ((0, 0, 0), (125, 125, 125))
        dc.SetPen(wx.Pen((10, 10, 10), 1))
        dc.SetBrush(wx.Brush(fill))
        dc.DrawRectangle(1, 2, 37, 19)
        dc.DrawLineList([(0, 0, 40, 0), (0, 22, 40, 22), (39, 0, 39, 23)],
                        pens=wx.Pen((0, 0, 0), 1))
        dc.SetFont(self.font)
        dc.SetTextForeground(label)
        w, h = dc.GetTextExtent(text)
        dc.DrawText(text, int((39 - w) * 0.5), int(1 + (21 - h) * 0.5))

    def CATCH_EVT_GLOBAL(self, event):
        if self.IsPopupShown():
            self.parent.TempoDropdown.FollowButton(event)
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleButtonStatus(event)

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        self.parent.TempoDropdown.StepTempo(event.WheelRotation)
        self.reInitBuffer = True

    def ShowPopup(self):
        if self.IsPopupShown():
            self.parent.TempoDropdown.HideDropdown()
        else:
            self.parent.TempoDropdown.ShowDropdown()

    def HidePopup(self):
        if self.IsPopupShown():
            self.parent.TempoDropdown.HideDropdown()

    def IsMuted(self):
        return False

    def OnSize(self, event=None):
        x = PlayBoxControlButton.STRIP_X + PlayBoxControlButton.STRIP_WIDTH + VolumeSlider.LENGTH
        self.SetRect((x, 5, self.LENGTH, 23))
        self.DirectDraw()


class TempoDropdown(VolumeDropdown):

    RANGES = (8, 16, 50)
    # within this share of the range from 0 a drag stops at 0
    DETENT = 0.03

    def __init__(self, parent):
        VolumeDropdown.__init__(self, parent)
        height = 182
        self.SetSize((41, height))
        self.rect_reset = (2, height - 3 - 19, 37, 19)
        self.rect_range = (2, height - 3 - 19 * 2 - 3, 37, 19)
        self.rect_key = (2, height - 3 - 19 * 3 - 6, 37, 19)

    def GetSliderRange(self):
        return (self.pad, self.rect_key[1] - self.pad)

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()
        dc.SetPen(wx.Pen((0, 0, 0), 1))
        dc.SetBrush(wx.Brush((35, 35, 35)))
        dc.DrawRectangle(0, 0, w, h)
        x = (w - self.width) * 0.5
        top, bottom = self.GetSliderRange()
        centre = (top + bottom) * 0.5
        share = (self.parent.GetTempoRate() - 1.0) * 100.0 / self.parent.GetTempoRange()
        st = self.parent.st
        rects = [(x - 1, top - 1, self.width + 2, bottom - top + 2),
                 (x, centre, self.width, -share * (bottom - top) * 0.5)]
        rects = [[int(v) for v in rect] for rect in rects]
        pens = [wx.Pen(st.VOLUME_PN_COLOR, 1), wx.Pen(st.VOLUME_FG_COLOR, 1)]
        brushes = [wx.Brush(st.VOLUME_BG_COLOR), wx.Brush(st.VOLUME_FG_COLOR)]
        dc.DrawRectangleList(rects, pens=pens, brushes=brushes)
        # 0% marked across the track
        dc.SetPen(wx.Pen(st.VOLUME_PN_COLOR, 1))
        dc.DrawLine(int(x - 5), int(centre), int(x + self.width + 5), int(centre))
        self.DrawButton(dc, self.rect_key, 'KEY', self.parent.IsTempoKeyLockOn())
        self.DrawButton(dc, self.rect_range, '%d%%' % (self.parent.GetTempoRange()), False)
        self.DrawButton(dc, self.rect_reset, '0%', False)

    def DrawButton(self, dc, rect, text, on):
        # drawn as the control buttons are: red while toggled on
        if on:
            fill, label = ((255, 120, 120), (0, 0, 0))
        else:
            fill, label = ((0, 0, 0), (125, 125, 125))
        x, y, w, h = rect
        dc.SetPen(wx.Pen((10, 10, 10), 1))
        dc.SetBrush(wx.Brush(fill))
        dc.DrawRectangle(x, y, w, h)
        dc.SetFont(self.parent.TempoButton.font)
        dc.SetTextForeground(label)
        tw, th = dc.GetTextExtent(text)
        dc.DrawText(text, int(x + (w - tw) * 0.5), int(y + (h - th) * 0.5))

    def OnMouse(self, event):
        position = event.GetPosition()
        if event.LeftDown():
            self.sliding = False
            if wx.Rect(*self.rect_key).Contains(position):
                self.parent.SetTempoKeyLock(self.parent.IsTempoKeyLockOn() is False)
            elif wx.Rect(*self.rect_range).Contains(position):
                ranges = self.RANGES
                current = self.parent.GetTempoRange()
                index = ranges.index(current) if current in ranges else -1
                self.parent.SetTempoRange(ranges[(index + 1) % len(ranges)])
            elif wx.Rect(*self.rect_reset).Contains(position):
                self.parent.SetTempoRate(1.0)
            else:
                self.sliding = True
            if self.sliding is False:
                self.Changed()
                return
        if event.LeftIsDown() is False:
            self.sliding = False
        if self.sliding is False:
            return
        top, bottom = self.GetSliderRange()
        share = ((top + bottom) * 0.5 - event.GetY()) / ((bottom - top) * 0.5)
        if abs(share) < self.DETENT:
            share = 0.0
        self.parent.SetTempoRate(1.0 + share * self.parent.GetTempoRange() / 100.0)
        self.Changed()

    def OnMouseWheel(self, event):
        self.StepTempo(event.GetWheelRotation())

    def StepTempo(self, rotation):
        # 0.1% a notch, up faster
        percent = (self.parent.GetTempoRate() - 1.0) * 100.0 + rotation / 120.0 * 0.1
        self.parent.SetTempoRate(1.0 + round(percent, 1) / 100.0)
        self.Changed()

    def Changed(self):
        self.Refresh(False)
        self.parent.TempoButton.reInitBuffer = True

    def GetBestPosition(self):
        x, y = self.parent.TempoButton.ClientToScreen((-1, 22))
        return (x, y)

    def ShowDropdown(self):
        self.SetPosition(self.GetBestPosition())
        self.Show()
        self.Refresh(False)
        self.parent.TempoButton.reInitBuffer = True

    def HideDropdown(self):
        self.Hide()
        self.parent.TempoButton.reInitBuffer = True

    def FollowButton(self, event):
        if self.IsShown() is False:
            return
        foreground = ctypes.windll.user32.GetForegroundWindow()
        if foreground not in (wx.GetTopLevelParent(self.parent).GetHandle(), self.GetHandle()):
            self.HideDropdown()
            return
        if event.LeftDown and self.GetScreenRect().Contains((event.x, event.y)) is False\
                and self.parent.TempoButton.onClient is False:
            self.HideDropdown()
            return
        position = self.GetBestPosition()
        if tuple(self.GetPosition()) != tuple(position):
            self.SetPosition(position)


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
        self.SetBackgroundColour((180, 180, 180))
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.title = self.GetTitle()
        self.DrawTitle(dc)

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        if self.IsInRect(self.rect, xy):
            return 1
        return None

    def DrawTitle(self, dc):
        width = self.GetSize().width
        title = self.title
        tw_limit, _ = self.GetSize()
        tw_limit = tw_limit - 20
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((6, 12))
        font.SetFaceName(FONT_ITEM)
        dc.SetFont(font)
        tw, th = dc.GetTextExtent(title)
        if tw > tw_limit:
            tw = tw_limit
            title = self.LimitTextLength(dc, title, tw_limit)
        x, y = (width - tw - 10, 4)
        self.rect = wx.Rect(x, y, tw, th)
        r, g, b = (0, 0, 0)
        dc.DrawTextList(((title),), ((x, y),), foregrounds=wx.Colour(r, g, b))

    def SetTitleType(self, title_type):
        self.title_type = title_type

    def GetTitle(self):
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
        idx = self.parent.parent.ListBox.GetColumnKeyToIdx(field, listId)
        if idx is None:
            return ''
        if self.parent.cue.item is None:
            return ''
        return self.parent.cue.item[idx]

    def CATCH_EVT_GLOBAL(self, event):
        # if self.parent.parent.HasToSkipEvent(): return
        # self.HandleItemDrag(event)
        self.HandleTitleChange(event)

    def HandleTitleChange(self, event):
        title = self.GetTitle()
        if title == self.title:
            return
        self.title = title
        self.DirectDraw()

    def HandleItemDrag(self, event):
        if event.drag.rectIdx is None:
            return
        self.parent.parent.SetItemDrag((self.parent.cue.path,))

    def OnSize(self, event=None):
        x, y, w, h = self.parent.GetRect()
        self.SetRect((1 - 1, 33, w - 2 + 2, 24))
        self.DirectDraw()


class PlayBoxInfo(RectBox):

    # index into tempo | key | position | duration, duration always stays
    HIDE_ORDER = (1, 0, 2)

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30

        self.information = GetPreference('playbox_information')
        if self.information is None:
            self.information = '000.0 | - | 00:00:00 | 00:00:00'
        self.segments = self.information.split(SEPARATOR)

        self.SetBackgroundColour(COLOR_TOOLBAR_BG)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.DrawInfo(dc)

    def GetFittingInformation(self, dc):
        width = self.GetSize().width
        shown = list(self.segments)
        for index in self.HIDE_ORDER:
            if index >= len(shown):
                continue
            information = SEPARATOR.join([v for v in shown if v is not None])
            if dc.GetTextExtent(information)[0] + 6 <= width:
                return information
            shown[index] = None
        return SEPARATOR.join([v for v in shown if v is not None])

    def DrawInfo(self, dc):
        # w = self.parent.GetSize().width
        width = self.GetSize().width
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((7, 13))
        font.SetFaceName(FONT_PLAYINFO)
        dc.SetFont(font)
        information = self.GetFittingInformation(dc)
        tw, th = dc.GetTextExtent(information)
        x, y = ((width - tw - 6), 3)
        r, g, b = (0, 0, 0)
        dc.DrawTextList(((information),), ((x, y),), foregrounds=wx.Colour(r, g, b))

    def CATCH_EVT_GLOBAL(self, event):
        self.HandleInfoChange(event)

    def HandleInfoChange(self, event=None):
        # autogain = self.parent.cue.autogain
        # decibel =  autogain/0.14
        key = self.parent.cue.key
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
        pos_sec, dur_sec = (
            self.parent.GetPositionTime(), self.parent.cue.duration)
        duration = '%02d:%02d.%02d' % (dur_sec / 60, dur_sec % 60, dur_sec % 1 * 100)
        position = '%02d:%02d.%02d' % (pos_sec / 60, pos_sec % 60, pos_sec % 1 * 100)
        segments = ['%05.1f' % tempo, key, position, duration]
        information = SEPARATOR.join(segments)
        if information == self.information:
            return
        self.segments = segments
        self.information = information
        self.DirectDraw()

    def OnSize(self, event):
        # vol_align = 12
        x, y, w, h = self.parent.GetRect()
        left = PlayBoxControlButton.STRIP_X + PlayBoxControlButton.STRIP_WIDTH
        left += VolumeSlider.LENGTH + TempoButton.LENGTH + 8
        right = w - 5
        width = max(0, min(250, right - left))
        self.SetRect((right - width, 5, width, 23))
        self.DirectDraw()


class PlayBoxApic(RectBox):

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
        for v in ('JPEG', 'BMP', 'PNG', 'GIF',):
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

        try:
            file = mutagen.File(path)
            key = [v for v in file.tags.keys() if 'APIC:' in v]
            if key == []:
                return None, path
            artwork = file.tags[key[0]].data
        except Exception:
            return None, path

        buf = io.BytesIO(artwork)
        if self.IsStreamImage(buf) is False:
            buf.close()
            return None, path
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
            return None, path
        bmp = bmp.Rescale(w, h, quality=wx.IMAGE_QUALITY_HIGH)
        bmp = bmp.ConvertToBitmap()
        return bmp, path

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
        width, height = self.GetClientSize()
        bgcolor = self.parent.st.APIC_BG_COLOR
        pncolor = self.parent.st.APIC_PN_COLOR
        fgcolor = self.parent.st.APIC_FG_COLOR
        cpcolor = self.parent.st.APIC_CP_COLOR
        dc.SetPen(wx.Pen(pncolor, 1))
        dc.SetBrush(wx.Brush(bgcolor))
        dc.DrawRectangle(0, 0, width, height)
        if self.apic is None:
            dc.SetPen(wx.Pen(cpcolor, 1))
            dc.SetBrush(wx.Brush(fgcolor))
            dc.DrawCircle(round(width / 2), round(height / 2), round(width * 0.6 / 2))
        else:
            w, h = self.apic.GetSize()
            x, y = (0, 0)
            if w > h:
                y = (w - h) * 0.5
            elif h > w:
                x = (h - w) * 0.5
            dc.DrawBitmap(self.apic, int(x + self.margin), int(y + self.margin), useMask=False)
        dc.DrawBitmap(self.overlap_mask, 0, 0, useMask=False)

    def HandleApicChange(self, forced=False):
        if self.parent.cue.path == self.path and forced is False:
            return
        self.apic = None
        self.path = self.parent.cue.path
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
        width, height = self.parent.GetClientSize()
        if self.parent.parent.parent.IsPlayerSideShowOn() is False:
            self.Hide()
            return
        if self.parent.Spectrum.IsShown():
            size = 119
            self.margin = 2
            size = 45
        else:
            size = 59
            self.margin = 1
            size = 0
        # rect = self.parent.Title.GetRect()

        if self.left:
            x = 14
        else:
            x = self.parent.GetClientSize().width - size - 1 - 10
        y = 68

        y = 78
        # Spectrum
        # print(self.parent.Spectrum.GetPosition())
        x = self.parent.Spectrum.GetPosition().x - size - 12

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
        self.max_width = 500
        self.width = 320 * self.scale
        self.height = 39
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
        if self.parent.IsPlaying() is False:
            self.DirectDraw()

    def GetSpectrumVectorScope(self):
        if self.parent.IsPlaying() is False:
            return None, None
        if self.IsShown() is False and self.parent.VectorScope.IsShown() is False:
            return None, None
        return audio.get_stream_spectrum_vectorscope(
            self.parent.cue.hStream, self.parent.VectorScope.size,
            self.parent.cue.channel, self.parent.cue.autogain, spectrum_scale=self.scale)

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
        if self.parent.parent.parent.IsPlayerTopShowOn() is False:
            self.Hide()
            return
        self.Show()
        y = self.parent.GetWaveTop()
        w, _ = self.parent.GetSize()
        # the cover's left and the vectorscope's right margins no smaller than
        # their gaps to the spectrum (cover 45 + 12, vectorscope 12 + 45)
        width = max(min(self.max_width, w - 152), 103 * 2)
        # the bins follow the width, the bars are fitted to it (FitBarLevels)
        scale = int(round(width / 320.0))
        scale = 1 if scale < 1 else scale
        scale = self.max_scale if scale > self.max_scale else scale
        if self.scale != scale or self.width != width:
            self.scale = scale
            self.width = width
            self.InitGround()

        wr = self.parent.Wave.GetRect()
        # x = wr.x + 0.5 * (wr.width + 12 - self.width) - 33 + 33
        x = wr.x + 0.5 * (wr.width - self.width)
        y = y - self.height - 20
        self.SetRect((int(x), int(y), int(self.width), int(self.height)))

        w, h = self.GetSize()
        ground = [wx.Rect(x, int(h / 2 - 1), self.bar_width, 2) for x in self.GetBarSlots(w)]
        self.ground = ground
        self.DirectDraw()


class PlayBoxVectorScope(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        fps = GetPreference('vectorscope_fps')
        if fps is None:
            fps = 60
        self.buffer.fps = fps
        # a square the cover's size (PlayBoxApic), no border, the L and R axes as an X
        self.size = 45
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
        if self.parent.IsPlaying() is False:
            self.vectorscope = None
            return
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
        if self.parent.IsPlaying() is False:
            self.SetSamples(None)
            self.DrawVectorScope(dc, None)
            return
        self.DrawVectorScope(dc, self.vectorscope)

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.IsPlaying() is False:
            self.DirectDraw()

    def DrawVectorScope(self, dc, vectorscope):
        bgcolor = self.parent.st.VECTORSCOPE_BG_COLOR
        pncolor = self.parent.st.VECTORSCOPE_PN_COLOR
        w, h = (self.size, self.size)
        dc.SetBrush(wx.Brush(bgcolor))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(0, 0, w, h)
        # ODDEVEN_RULE WINDING_RULE
        # dc.DrawPolygon(self.polygon, 0, 0, fillStyle=wx.ODDEVEN_RULE)
        dc.SetPen(wx.Pen(pncolor, 1))
        dc.DrawLine(0, 0, w, h)
        dc.DrawLine(w - 1, 0, -1, h)
        if vectorscope is None:
            return
        dc.DrawBitmap(vectorscope, 0, 0, True)

    def OnSize(self, event=None):
        isTopShowOn = self.parent.parent.parent.IsPlayerTopShowOn()
        if isTopShowOn is False:
            self.Hide()
            return
        self.Show()
        w, h = (self.size, self.size)
        sr = self.parent.Spectrum.GetRect()
        # as far from the spectrum as the cover on the other side
        x = sr.x + sr.width + 12
        y = sr.y + (sr.height - h) // 2
        self.SetRect(wx.Rect(round(x), round(y), round(w), round(h)))
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

        leftPad = 10

        x, y = (leftPad, h - self.height - 15 + 1 - 3)
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
        w, h = self.GetSize()
        x, y = (self.margin, 2)
        return (x, y, w - x * 2, h - y * 2 - 1)

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
        draw_highlight = self.parent.IsHighlightKnown()\
            and self.parent.IsHighlightOn()\
            and self.parent.IsHighlightSkipOn() is False
        if draw_highlight:
            self.DrawHighlightWave(dc)
        else:
            self.DrawNormalWave(dc)
        self.DrawGridLines(dc)
        self.DrawCursor(dc)

    def DrawGridLines(self, dc):
        # every 16 bars across the whole song (each bar would run together)
        grid = self.parent.GetGrid()
        duration = self.parent.GetDurationTime()
        if grid is None or duration <= 0 or self.wave_bitmaps is None\
                or self.parent.IsGridShown() is False:
            return
        x, y, w, h = self.wave_rect
        span = 60.0 / grid.bpm * 64
        if span / duration * w < 6:
            return
        bg = wx.Colour(self.parent.st.PLAY_BG_COLOR)
        color = wx.Colour(*[int(v + (255 - v) * 0.35) for v in (bg.Red(), bg.Green(), bg.Blue())])
        dc.SetPen(wx.Pen(color, 1))
        seconds = self.parent.GetGridDownbeat()
        while seconds < duration:
            lx = int(x + seconds * w / duration)
            dc.DrawLine(lx, y, lx, y + h)
            seconds += span

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

    def SetRectWave(self):
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
            wx.CallAfter(self.SetWaveImages, job, (x, y, w, h), images)

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
        if self.parent.IsPlaying() is False:
            self.DirectDraw()

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
        if event.rectIdx is None:
            return
        if event.LeftDown is False:
            return
        self.OnClickWave(event)

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
        new_position = duration * posRatio
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
        if self.parent.parent.parent.IsWaveformDetailShowOn() is False:
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

    def SetRectDraw(self, dc):
        w, h = self.GetSize()
        w -= self.margin * 2
        if w <= 0 or h <= 0:
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
            else (grid.bpm, grid.downbeat, grid.shift)
        key = (id(waveform), duration, span, period, w, h, gridkey)
        if key != self.last_key or not w // 4 <= step - self.last_step <= w * 2 - w // 4:
            self.last_step = step - w
            start = self.last_step * pixel
            times = start + (numpy.arange(w * 3) + 0.5) * span / w
            bgcolor = numpy.array(self.parent.st.PLAY_BG_COLOR, dtype=float)
            ground, dim = (bgcolor, 1.0)
            if period is not None:
                inside = (times >= period[0]) & (times < period[1])
                hlcolor = numpy.array(self.parent.st.HIGHLIGHT_BG_COLOR, dtype=float)
                ground = numpy.where(inside[:, None], hlcolor, bgcolor)
                dim = numpy.where(inside, 1.0, self.highlight_dim)
            columns = len(waveform) / duration
            image = audio.paint_waveform_3band(
                waveform, w * 3, h, ground=ground, dim=dim,
                start=start * columns, end=(start + span * 3) * columns, spread=0)
            self.PaintGridLines(image, start, pixel)
            self.last_bitmap = wx.Bitmap.FromBuffer(w * 3, h, image.tobytes())
            self.last_key = key
        dc.SetClippingRegion(self.margin, 0, w, h)
        dc.DrawBitmap(self.last_bitmap, self.margin - (step - self.last_step), 0)
        dc.DestroyClippingRegion()

    def PaintGridLines(self, image, start, pixel):
        # the beat grid lightened into the strip: told apart by strength and width, not
        # by colour. a beat's line is left out when beats are closer than 4 pixels
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
        position = min(max(position, 0.0), duration * 0.999999)
        period = self.GetHighlightPeriod()
        if period is not None and (position < period[0] or position >= period[1]):
            self.parent.SetHighlightSkipOn()
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
        labels = ('Bar starts on this beat', 'Bar one beat earlier', 'Bar one beat later',
                  'Bar as analyzed')
        for label, handler in zip(labels, (self.OnHere, self.OnEarlier, self.OnLater,
                                           self.OnAnalyzed)):
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        source = 'Beat This!' if grid.source == 'beatthis' else 'the beats alone'
        item = self.Append(wx.ID_ANY, '%.3f BPM, bar from %s' % (grid.bpm, source))
        item.Enable(False)

    def OnHere(self, event):
        self.parent.SetGridBarAt(self.seconds)

    def OnEarlier(self, event):
        self.parent.SetGridShift((self.parent.GetGrid().shift or 0) - 1)

    def OnLater(self, event):
        self.parent.SetGridShift((self.parent.GetGrid().shift or 0) + 1)

    def OnAnalyzed(self, event):
        self.parent.SetGridShift(0)
