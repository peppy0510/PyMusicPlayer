# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
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
from macroboxlib import RectBox
from playboxlib import AudioControl
from playboxlib import PlayBoxControl
from playboxlib import PlayBoxDnD
from utilities import Struct
# from playboxlib import *  # noqa


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
        self.Info = PlayBoxInfo(self)
        # self.InfoR = PlayBoxInfoR(self)
        self.Title = PlayBoxTitle(self)
        self.Spectrum = PlayBoxSpectrum(self)
        self.VectorScope = PlayBoxVectorScope(self)
        self.Apic = PlayBoxApic(self)
        self.ControlButton = PlayBoxControlButton(self)
        self.VolumeSlider = VolumeSlider(self)
        self.AudioControl = AudioControl(self)
        self.InitBuffer()

    def IsSideWideEnough(self):
        w, _ = self.GetSize()
        if w >= 840:
            return True
        return False

    def SetRectDraw(self, dc):
        width, height = self.GetSize()
        rects = [(-1, 0, width + 2, 33)]
        dc.DrawRectangleList(rects, pens=wx.Pen((0, 0, 0), 1), brushes=wx.Brush(COLOR_TOOLBAR_BG))

    def OnSize(self, event=None):
        self.Freeze()
        self.DirectDraw()
        self.Title.OnSize(None)
        self.Wave.OnSize(None)
        self.Info.OnSize(None)
        # self.InfoR.OnSize(None)
        self.Spectrum.OnSize(None)
        self.VectorScope.OnSize(None)
        self.Apic.OnSize(None)
        self.ControlButton.OnSize(None)
        self.VolumeSlider.OnSize(None)
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

        # if namespace == 'agc_toggle' and self.cache.oneshotkey is False:
        #   self.cache.oneshotkey = True
        #   if self.IsAutoGainOn():
        #       self.SetAutoGainOff()
        #   else: self.SetAutoGainOn()
        #   self.reInitBuffer = True

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
        self.AudioControl._Thread__stop()
        self.AudioControl._Thread__exc_clear()


class PlayBoxControlButton(RectBox):

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
        self.button_flash = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.button_status = [False, False, False, False, False]
        self.toggle_buttons = [True, False, True, False, True]
        # self.button_flash = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        # self.button_status = [False, False, False, False, False, False]
        # self.toggle_buttons = [True, False, True, False, True, True]
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
        for nv in ('highlight', 'play', 'loop'):
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
        # elif self.parent.IsAutoGainOn() and self.button_status[5] is False:
        #   self.button_status[5] = True
        #   self.SetButtonColors()
        # elif self.parent.IsAutoGainOn() is False and self.button_status[5]:
        #   self.button_status[5] = False
        #   self.SetButtonColors()

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
        # if downIdx == 5 and status[5]:
        #   self.parent.SetAutoGainOn()
        # if downIdx == 5 and status[5] is False:
        #   self.parent.SetAutoGainOff()

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
        # exec('bmp = self.bmp.agc_%s' % (button_colors[5]))
        # dc.DrawBitmap(bmp, 140+40*2, 1, useMask=False)

        dc.DrawLineList(self.lines, pens=wx.Pen((0, 0, 0), 1))

    # Buffered DC

    def OnSize(self, event=None):
        self.SetRect((5, 5, 220, self.height))
        self.DirectDraw()

    def SetPreInitRects(self):
        # make polygons, rectangles and lines when class starts
        x, y, h = (2, 2, 19)
        rects = ((x, y, 56, h), (59 + x, y, 37, h), (99 + x, y, 37, h),
                 (139 + x, y, 37, h), (179 + x, y, 37, h),)
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

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.width = 4
        self.volume = 1.0
        self.buffer.fps = 30
        self.muted_volume = None
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        w, h = self.GetClientSize()
        x = (w - self.width) * 0.5
        volume = self.parent.GetVolume()
        rects = [(x - 2, 0, self.width + 2, h), (x - 1, h - 1, self.width, -volume * (h - 2))]
        bgcolor = self.parent.st.VOLUME_BG_COLOR
        fgcolor = self.parent.st.VOLUME_FG_COLOR
        pncolor = self.parent.st.VOLUME_PN_COLOR
        pens = [wx.Pen(pncolor, 1), wx.Pen(fgcolor, 1)]
        brushes = [wx.Brush(bgcolor), wx.Brush(fgcolor)]
        dc.DrawRectangleList(rects, pens=pens, brushes=brushes)

    def CATCH_EVT_GLOBAL(self, event):
        if self.onClient:
            pass
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
        self.reInitBuffer = True

    def CATCH_EVT_MOUSEWHEEL(self, event):

        if self.onClient is False:
            return
        volume = self.GetVolume()
        diff = event.WheelRotation / 400.0 / 3
        self.SetVolume(volume + diff)

    def HandleButtonStatus(self, event):
        if event.down.rectIdx is None:
            return
        if event.LeftDClick:
            self.ToggleMute()
            self.reInitBuffer = True
        elif event.LeftDown:
            self.down_volume = self.GetVolume()
        elif event.LeftIsDrag:
            _, h = self.GetSize()
            diff = -1.0 * (event.y - event.down.y) / h
            self.SetVolume(self.down_volume + diff)

    def ToggleMute(self):
        if self.muted_volume is None:
            self.muted_volume = self.GetVolume()
            self.SetVolume(0)
        elif self.muted_volume is not None:
            self.SetVolume(self.muted_volume)
            self.muted_volume = None

    def OnSize(self, event=None):
        x, y, w, h = self.parent.Wave.GetRect()
        self.SetRect((x + w + 4 + 4, y - 1, 10, h))
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

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30

        self.information = GetPreference('playbox_information')
        if self.information is None:
            self.information = '000.0 | - | 00:00:00 | 00:00:00'

        self.SetBackgroundColour(COLOR_TOOLBAR_BG)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.DrawInfo(dc)

    def DrawInfo(self, dc):
        # w = self.parent.GetSize().width
        width = self.GetSize().width
        information = self.information
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((7, 13))
        font.SetFaceName(FONT_PLAYINFO)
        dc.SetFont(font)
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
        tempo = self.parent.cue.tempo
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
        multi_feat = '%05.1f | %s' % (tempo, key)
        pos_sec, dur_sec = (
            self.parent.GetPositionTime(), self.parent.cue.duration)
        duration = '%02d:%02d.%02d' % (dur_sec / 60, dur_sec % 60, dur_sec % 1 * 100)
        position = '%02d:%02d.%02d' % (pos_sec / 60, pos_sec % 60, pos_sec % 1 * 100)
        time_info = '%s | %s' % (position, duration)
        # information = '%05.2f | %s | %s' % (decibel, multi_feat, time_info)
        information = '%s | %s' % (multi_feat, time_info)
        if information == self.information:
            return
        self.information = information
        self.DirectDraw()

    def OnSize(self, event):
        # vol_align = 12
        x, y, w, h = self.parent.GetRect()
        self.SetRect((w - 255, 5, 250, 23))
        # self.SetRect((w-255-70, 5, 250+70, 23))
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
            dc.DrawCircle(width / 2, height / 2, (width * 0.6 / 2))
        else:
            w, h = self.apic.GetSize()
            x, y = (0, 0)
            if w > h:
                y = (w - h) * 0.5
            elif h > w:
                x = (h - w) * 0.5
            dc.DrawBitmap(self.apic, x + self.margin, y + self.margin, useMask=False)
        dc.DrawBitmap(self.overlap_mask, 0, 0, useMask=False)

    def HandleApicChange(self, forced=False):
        if self.parent.cue.path == self.path and forced is False:
            return
        self.apic = None
        self.path = self.parent.cue.path
        if hasattr(self, 'Thread') and self.Thread.is_alive():
            self.Thread._Thread__stop()
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
        self.width = 320 * self.scale
        self.height = 39
        self.resolution = 1
        self.saturation = 0.1

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
        self.DrawSpectrumGround(dc)
        if spectrum is None:
            return
        self.DrawSpectrumHTB(dc, spectrum)
        if hasattr(self.parent, 'VectorScope'):
            self.parent.VectorScope.vectorscope = vectorscope

    def DrawSpectrumGround(self, dc):
        color = self.parent.st.SPECTRUM_BG_COLOR
        dc.DrawRectangleList(self.ground, pens=wx.Pen(color, 1),
                             brushes=wx.Brush(color))

    def DrawSpectrumHTB(self, dc, spectrum):
        fgcolor = self.parent.st.SPECTRUM_FG_COLOR
        w, h = self.GetSize()
        scale = 0.4
        spLength = len(spectrum) - 1
        sw = int(1.0 * w / spLength)
        offset = (w - sw * spLength) * 0.5
        rects = [(sw * i + offset + 1, (h - level * h * scale) * 0.5,
                  sw - 2, level * h * scale) for i, level in enumerate(spectrum)]
        stroke = self.parent.st.SPECTRUM_STROKE
        dc.DrawRectangleList(rects, pens=wx.Pen(fgcolor, stroke),
                             brushes=wx.Brush(fgcolor))

    def OnSize(self, event=None):
        if self.parent.parent.parent.IsPlayerTopShowOn() is False:
            self.Hide()
            return
        self.Show()
        _, y, _, _ = self.parent.Wave.GetRect()
        w, _ = self.parent.GetSize()

        scale = int((w - 200) / 320)
        scale = 1 if scale < 1 else scale
        scale = 3 if scale > 3 else scale
        if self.scale != scale:
            self.scale = scale
            self.width = 320 * self.scale
            self.InitGround()

        wr = self.parent.Wave.GetRect()
        x = wr.x + 0.5 * (wr.width + 12 - self.width) - 33 + 33
        y = y - self.height - 20
        self.SetRect((x, y, self.width, self.height))

        w, h = self.GetSize()
        len_spectrum = 103 * self.scale
        spLength = len_spectrum - 1
        sw = int(1.0 * w / spLength)
        offset = (w - sw * spLength) * 0.5
        ground = [wx.Rect(sw * i + offset + 1, h / 2 - 1, sw - 2, 2)
                  for i in range(len_spectrum)]
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
        self.size = 50
        self.margin = 2
        self.vectorscope = []
        self.polygon = ((0, 0), (0, 0),)
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def GetVectorScope(self):
        if self.parent.IsPlaying() is False:
            self.vectorscope = None
            return
        return self.vectorscope

    def SetRectDraw(self, dc):
        if self.parent.IsPlaying() is False:
            self.DrawVectorScope(dc, None)
            return
        self.DrawVectorScope(dc, self.vectorscope)

    def CATCH_EVT_GLOBAL(self, event):
        self.DirectDraw()

    def DrawVectorScope(self, dc, vectorscope):
        bgcolor = self.parent.st.VECTORSCOPE_BG_COLOR
        pncolor = self.parent.st.VECTORSCOPE_PN_COLOR
        dc.SetBrush(wx.Brush(bgcolor))
        dc.SetPen(wx.Pen(pncolor, 1))
        # ODDEVEN_RULE WINDING_RULE
        # dc.DrawPolygon(self.polygon, 0, 0, fillStyle=wx.ODDEVEN_RULE)
        dc.DrawPolygon(self.polygon, 0, 0)
        if vectorscope is None:
            return
        fgcolor = self.parent.st.VECTORSCOPE_FG_COLOR
        dc.DrawPointList(vectorscope, pens=wx.Pen(fgcolor, 1))

    def OnSize(self, event=None):
        isTopShowOn = self.parent.parent.parent.IsPlayerTopShowOn()
        if isTopShowOn is False:
            self.Hide()
            return
        self.Show()
        w, h = (self.size, self.size)
        sr = self.parent.Spectrum.GetRect()
        x = sr.x + sr.width + 8 + 5
        y = sr.y - 6
        self.SetRect(wx.Rect(x, y, w, h))
        self.polygon = ((0.5 * w, 1), (1, 0.5 * h), (0.5 * w, h - 1), (w - 1, 0.5 * h))
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
        self.highlight_waveform = None
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
        leftPad, rightPad = (13, 25 + 5)
        if isSideShowOn:
            leftPad = 8
        elif isSideShowOn and isTopShowOn:
            leftPad = 13

        leftPad = 13

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
        self.parent.reInitWave = True
        self.DirectDraw()

    def SetRectPre(self):
        if self.parent.reInitWave is True:
            self.parent.reInitWave = False
            self.SetRectWave()
            self.SetRectHighlight()

    def SetRectDraw(self, dc):
        draw_highlight = self.parent.IsDBRespPending() is False\
            and self.parent.IsHighlightOn()\
            and self.parent.IsHighlightSkipOn() is False
        if draw_highlight:
            self.DrawHighlightWave(dc)
        else:
            self.DrawNormalWave(dc)
        self.DrawCursor(dc)

    def DrawNormalWave(self, dc):
        fgcolor = self.parent.st.WAVEFORM_FG_COLOR
        dc.SetPen(wx.Pen(fgcolor, 1))
        dc.DrawLines(list(self.wave))

    def SetRectHighlight(self):
        if self.wave is None or self.parent.IsDBRespPending():
            self.rectHighlight = (0, 0, 0, 0)
            return
        duration = self.parent.GetDurationTime()
        if duration == 0.0:
            return
        offset, period = self.parent.GetHighlightTime()
        if offset is None or period is None:
            return
        x = 0.5 * offset * len(self.wave) / duration
        w = period * 0.5 * len(self.wave) / duration
        if w == 0:
            xw = int(0.5 * len(self.wave))
            w = int(xw - x)
        else:
            xw = int(x + w)
        x = int(x)
        if x == 0:
            x = 1
        if xw > len(self.wave):
            xw = len(self.wave) / 2
        hiwave = self.wave[x:xw] + self.wave[-xw:-x] + [self.wave[x]]
        _, height = self.GetSize()
        self.highlight_waveform = hiwave
        self.rectHighlight = (int(x) + self.margin, 0, int(w), height)

    def DrawHighlightWave(self, dc):
        bgcolor = self.parent.st.HIGHLIGHT_BG_COLOR
        pncolor = self.parent.st.HIGHLIGHT_PN_COLOR
        fgcolor = self.parent.st.HIGHLIGHT_FG_COLOR
        if self.highlight_waveform is None:
            x, y = (self.margin, self.height * 0.5 - 1)
            w = self.GetSize().width - self.margin * 2 - 2
            dc.SetPen(wx.Pen(pncolor, 1))
            # dc.DrawPolygon(((x, y), (x + w, y)), 0, 0, fillStyle=wx.WINDING_RULE)
            dc.DrawPolygon(((x, y), (x + w, y)), 0, 0)
            return
        dc.SetPen(wx.Pen(pncolor, 1))
        dc.DrawLines(self.wave)
        # ODDEVEN_RULE, WINDING_RULE
        dc.SetBrush(wx.Brush(bgcolor))
        # dc.DrawPolygon(self.highlight_waveform, 0, 0, fillStyle=wx.WINDING_RULE)
        dc.DrawPolygon(self.highlight_waveform, 0, 0)
        dc.SetPen(wx.Pen(fgcolor, 1))
        dc.DrawLines(self.highlight_waveform)

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
        dc.DrawRectangle(x - self.cursor_width * 0.5, 0, self.cursor_width, h)

    def SetRectWave(self):
        w, h = self.GetSize()
        x, y = (self.margin, 2)
        w, h = (w - x * 2, h - y * 2 - 1)
        # cx = w * 0.5 + x
        cy = h * 0.5 + y
        waveform = self.parent.GetWaveform()

        if waveform is None:
            self.wave = list(zip(range(x, x + w), numpy.linspace(cy, cy, w)))
            return
        filled_wave = audio.max_wide_fill_sym(waveform, w) / 256.0 * h
        if max(filled_wave) != 0 and self.parent.wave_max:
            filled_wave = 1.0 * filled_wave * 0.5 * h / max(filled_wave)
        filled_wave = numpy.round(filled_wave)
        self.wave = [(x, cy)] + list(zip(range(x, x + w, 1), filled_wave + cy))\
            + [(x + w, cy)] + [(x + w, cy)] + list(zip(range(x, x + w, 1), -filled_wave + cy))[::-1] + [(x, cy)]

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.parent.HasToSkipEvent() is False:
            self.HandleEventLeftIsDown(event)
            self.HandleEventHighlight(event)
        self.DirectDraw()

    def HandleEventHighlight(self, event):
        if event.rectIdx is None:
            return
        if event.LeftDown is False:
            return
        if self.parent.IsDBRespPending():
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
