# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import glob
import images
import math
import os
import stat
import subprocess
import sys
import threading
import webbrowser
import wx

from listboxlib import ListBoxListDnD
from listboxlib import ListControl
from macroboxlib import Button
from macroboxlib import COLOR_STATUS_BG
from macroboxlib import ComboBox
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
from macroboxlib import FONT_ITEM
from macroboxlib import FONT_ITEM_SIZE
from macroboxlib import GetPreference
from macroboxlib import ItemTextEdit
from macroboxlib import ListBoxColumn
from macroboxlib import MakeMusicFileItem
from macroboxlib import RectBox
from macroboxlib import SUPPORTED_AUDIO_TYPE
from macroboxlib import SUPPORTED_PLAYLIST_TYPE
from macroboxlib import SetPreference
from macroboxlib import StaticText
from macroboxlib import TabTextEdit
from macroboxlib import TextCtrl
from macroboxlib import UserInputDialogBox
from operator import itemgetter
from utilities import Struct
from utilities import get_user_docapp_path


class ListBox(RectBox, ListControl):

    def __init__(self, parent, Id=None):
        RectBox.__init__(self, parent, Id)
        ListControl.__init__(self, parent)
        self.parent = parent
        self.st = parent.parent.st.LISTBOX
        self.freeze = False
        self.AddInnerList()
        self.rects = None
        self.is_slider_h_shown = False
        self.is_slider_v_shown = False
        self.focus = Struct(item=-1, shift=-1)
        self.edit = Struct(on=False, item=None, column=None, input=None, commit=False)
        self.LoadPreferences()
        self.SetBackgroundColour(self.st.LIST_BG_COLOR)

        self.List = ListBoxList(self)
        self.Header = ListBoxHeader(self)
        self.SliderV = ListBoxSliderV(self)
        self.SliderH = ListBoxSliderH(self)
        self.CheckAnalyzingStatus()

        self.SetListUnLockAll()
        self.InitBuffer()

    def LoadPreferences(self):
        line_contrast = GetPreference('listbox_line_contrast')
        if line_contrast is None:
            self.line_contrast = 3
        else:
            self.line_contrast = line_contrast

        line_space = GetPreference('listbox_line_space')
        if line_space is None:
            line_space = 26
        self.line_space = line_space
        self.SetRowsHeightAll(self.line_space)

        fontinfo = GetPreference('listbox_fontinfo')
        if fontinfo is None:
            self.SetFont(self.GetDefaultFont())
        else:
            self.GetFontByInfo(fontinfo)

        always_show_slider = GetPreference('always_show_slider')
        if always_show_slider is None:
            self.always_show_slider = False
        else:
            self.always_show_slider = always_show_slider

        scrollbar_size = GetPreference('scrollbar_size')
        if scrollbar_size is None:
            scrollbar_size = 6
        self.scrollbar_size = scrollbar_size

    def GetFont(self):
        return self.font

    def GetDefaultFont(self):
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((6, 12))
        font.SetFaceName(u'Segoe UI')
        return font

    def SetFont(self, font):
        self.font = font
        if hasattr(self, 'List'):
            self.List.DirectDraw()

    def GetFontByInfo(self, info):
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetStyle(info.style)
        font.SetPixelSize(info.size)
        font.SetWeight(info.weight)
        font.SetFaceName(info.name)
        self.SetFont(font)

    def GetFontInfo(self):
        style = self.font.GetStyle()
        size = self.font.GetPixelSize()
        weight = self.font.GetWeight()
        name = self.font.GetFaceName()
        return Struct(name=name, size=size, style=style, weight=weight)

    def GetBestRects(self):
        ss = self.scrollbar_size
        w, h = self.GetClientSize()
        if self.always_show_slider:
            padH, padV = (ss, ss)
        else:
            padH, padV = (0, 0)
        self.SetBestVirtualPosition()
        if self.IsNeededSliderH():
            padH = ss
        if self.IsNeededSliderV():
            padV = ss
        hh = self.GetRowsHeight()
        padV = ss
        bw = w - padV - 2
        bh = h - hh - padH - 1
        if padV > 0:
            bw -= 1
        if padH > 0:
            bh -= 1
        body = (1, hh, bw, bh)
        header = (0, 0, w - padV, hh)
        if padV == 0:
            sw = w - padV
        else:
            sw = w - padV - 1
        sliderH = (1, h - padH - 1, sw - 2, padH)
        if padH == 0:
            sh = h - hh - padH - 2
        else:
            sh = h - hh - padH - 1 - 2
        sliderV = (w - padV - 1, hh + 1, padV, sh + 1 - 1)
        if padH > 0:
            self.is_slider_h_shown = True
        else:
            self.is_slider_h_shown = False
        if padV > 0:
            self.is_slider_v_shown = True
        else:
            self.is_slider_v_shown = False
        return body, header, sliderH, sliderV

    def SetRectPre(self):
        rects = self.GetBestRects()
        if rects == self.rects:
            return
        self.rects = rects
        body, header, sliderH, sliderV = rects
        self.List.SetRect(body)
        self.Header.SetRect(header)
        self.SliderH.SetRect(sliderH)
        self.SliderV.SetRect(sliderV)

    def SetRectDraw(self, dc):
        width, height = self.GetClientSize()
        ss = self.scrollbar_size + 1
        if self.is_slider_v_shown:
            hh = self.GetRowsHeight()
            lines = ((width - ss, 0, width, 0), (width - ss, 1, width, 1),)
            hdcolor = self.st.HEADER_PN_COLOR
            bgcolor = self.st.HEADER_BG_COLOR
            pens = (wx.Pen(bgcolor, 1), wx.Pen(hdcolor, 1))
            dc.DrawLineList(lines, pens=pens)
            rects = ((width - ss, 2, ss, hh - 2),)
            color = self.st.HEADER_BG_COLOR
            dc.DrawRectangleList(rects,
                                 pens=wx.Pen(color, 1), brushes=wx.Brush(color))
        # color = self.st.SCROLLBAR_BG_COLOR
        # if self.is_slider_h_shown and self.is_slider_v_shown:
        #   rects = ((width-ss, height-ss, ss, ss),)
        #   dc.DrawRectangleList(rects,\
        #       pens=wx.Pen(color, 1), brushes=wx.Brush(color))
        self.List.reInitBuffer = True
        self.Header.reInitBuffer = True
        self.SliderH.reInitBuffer = True
        self.SliderV.reInitBuffer = True

    # Buffered DC

    def OnSize(self, event=None):
        self.Freeze()
        self.Header.SetAutoColumnWidth()
        self.DirectDraw()
        self.List.DirectDraw()
        self.Header.DirectDraw()
        self.SliderH.DirectDraw()
        self.SliderV.DirectDraw()
        self.DirectDraw()
        self.Thaw()

    def __del__(self):
        pass


class ListBoxList(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)

        self.cache.insertItemIdx = None  # MAC
        self.cache.insertItemDelayed = 0  # MAC
        self.cache.down.itemIdx = None
        self.cache.down.columnIdx = None
        self.cache.drag.columnIdx = None
        self.pending = Struct(insertItemIdx=None, SkipStopIcon=False,
                              SkipControlSelectItem=False, SkipItemSelection=False)
        self.TextEdit = None
        self.FileDrop = ListBoxListDnD(self)
        self.SetDropTarget(self.FileDrop)
        bgcolor = self.parent.GetBackgroundColour()
        self.SetBackgroundColour(bgcolor)

        self.bmp = Struct(playing=Struct())
        self.bmp.playing.black = images.listbox_playing_black.GetBitmap()
        self.bmp.playing.white = images.listbox_playing_white.GetBitmap()
        self.InitBuffer()

    # Draw ListBoxList

    def SetRectDraw(self, dc):
        self.DrawListItem(dc)
        self.DrawInsertItemLine(dc)
        self.DrawTextEdit(dc)

    def DrawTextEdit(self, dc):
        if self.TextEdit is None:
            return
        rect = self.GetRect()
        row_size = self.parent.GetRowsHeight()
        vpy = self.parent.GetVirtualPositionY()
        row_offset = abs(vpy) % row_size - 0
        columns = list()
        x = -1
        for i, column in enumerate(self.parent.GetShownColumns()):
            columns.append(Struct(x=x, width=column.width))
            x += column.width
        for row, item in enumerate(self.parent.GetShownItemsIdx()):
            for i, col in enumerate(self.parent.GetShownColumnsIdx()):
                column = columns[i]
                if item == self.TextEdit.itemIdx\
                        and col == self.TextEdit.columnIdx:
                    x = column.x + self.parent.GetVirtualPositionX()
                    y = row_size * row - row_offset + 1
                    w = column.width
                    if w > rect.width - x:
                        w = rect.width - x
                    h = row_size - 1
                    dc.DrawRectangleList(((x, y, w + 1, h),),
                                         pens=wx.Pen((30, 30, 30), 0),
                                         brushes=wx.Brush(wx.Colour(255, 255, 255)))
                    w = column.width - 8
                    if w > rect.width - x:
                        w = rect.width - x
                    self.TextEdit.SetRect(wx.Rect(x + 5, y + 3, w - 1, h - 4))
                    return

    def DrawListItem(self, dc):
        top_margin = 4
        left_margin = 5
        x, y = (0, 0)
        w, h = self.GetSize()
        row_size = self.parent.GetRowsHeight()
        vpx = self.parent.GetVirtualPositionX()
        vpy = self.parent.GetVirtualPositionY()
        rect = wx.Rect(x, y, w, h)
        x = vpx
        columns = list()
        for i, column in enumerate(self.parent.GetShownColumns()):
            columns.append(Struct(x=x, width=column.width))
            x += column.width
        lines = list()
        n_texts = list()
        n_xys = list()
        n_rects = list()
        s_texts = list()
        s_xys = list()
        s_rects = list()
        n_rects_odd = list()
        n_rects_even = list()
        row_offset = abs(vpy) % row_size - 0
        tww = self.parent.font.GetPixelSize().width
        dc.SetFont(self.parent.font)
        # tw, _ = dc.GetTextExtent(u'W')
        _, th = dc.GetTextExtent(u'A^`qj!#%*&ypQ')
        top_margin = int((row_size - th) * 0.5) + 1

        listIdx = self.parent.selectedList
        shownColIdx = self.parent.GetShownColumnsIdx()
        shownItemIdx = self.parent.GetShownItemsIdx()
        orderIdx = self.parent.GetColumnKeyToIdx('order')
        statusIdx = self.parent.GetColumnKeyToIdx('status')
        # itemslen = len(self.parent.innerList[listIdx].items)
        for row, item in enumerate(shownItemIdx):

            for i, col in enumerate(shownColIdx):
                column = columns[i]
                if item > len(self.parent.innerList[listIdx].items):
                    continue

                string = self.parent.innerList[listIdx].items[item][col]
                right_align = self.parent.innerList[listIdx].columns[col].right_align
                if col == statusIdx:
                    continue
                # limitedString = self.LimitTextLength(\
                #   dc, string, column.width-left_margin-15, tww)
                limitedString = self.LimitTextLength(
                    dc, string, column.width - left_margin - 8, tww)
                if right_align:
                    tw, _ = dc.GetTextExtent(limitedString)
                    txy = (column.x + column.width - left_margin - tw,
                           row_size * row + rect.y + top_margin - row_offset)
                else:
                    txy = (column.x + left_margin,
                           row_size * row + rect.y + top_margin - row_offset)
                if self.parent.IsHighlightedItem(item):
                    s_texts.append(limitedString)
                    s_xys.append(txy)
                else:
                    n_texts.append(limitedString)
                    n_xys.append(txy)

            width = column.x + column.width
            lines.append((rect.x, row_size * row + rect.y - row_offset,
                          width, row_size * row + rect.y - row_offset))
            if self.parent.IsHighlightedItem(item):
                s_rects.append((rect.x, row_size * row + rect.y - row_offset + 1, width, row_size - 1))
            else:
                n_rects.append((rect.x, row_size * row + rect.y - row_offset, width, row_size))

                if shownItemIdx[row] % 2 == 0:
                    n_rects_odd.append((rect.x, row_size * row + rect.y - row_offset, width, row_size))
                else:
                    n_rects_even.append((rect.x, row_size * row + rect.y - row_offset, width, row_size))

        if shownItemIdx != []:
            lines.append((rect.x, row_size * (row + 1) + rect.y - row_offset,
                          width, row_size * (row + 1) + rect.y - row_offset))

        def limitcolor(v):
            if v > 255:
                return 255
            if v < 0:
                return 0
            return v
        ct = self.parent.line_contrast
        r, g, b = self.parent.st.LIST_BG_COLOR
        bgcolor_odd = [limitcolor(v) for v in (r - ct, g - ct, b - ct)]
        bgcolor_even = [limitcolor(v) for v in (r + ct, g + ct, b + ct)]

        dc.DrawRectangleList(n_rects_odd,
                             pens=wx.Pen(bgcolor_odd, 1),
                             brushes=wx.Brush(bgcolor_odd))
        dc.DrawRectangleList(n_rects_even,
                             pens=wx.Pen(bgcolor_even, 1),
                             brushes=wx.Brush(bgcolor_even))

        sel_bgcolor = self.parent.st.SELECTED_BG_COLOR
        dc.DrawRectangleList(s_rects,
                             pens=wx.Pen(sel_bgcolor, 1),
                             brushes=wx.Brush(sel_bgcolor))

        sel_bgcolor = self.parent.st.SELECTED_BG_COLOR
        r, g, b = self.parent.st.LIST_FG_COLOR
        dc.DrawTextList(n_texts, n_xys, foregrounds=wx.Colour(r, g, b))
        r, g, b = self.parent.st.SELECTED_FG_COLOR
        dc.DrawTextList(s_texts, s_xys, foregrounds=wx.Colour(r, g, b))
        color = self.parent.st.LIST_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 0))

        # draw status column
        procpath = self.parent.parent.MFEATS.GetProcPath()
        pathIdx = self.parent.GetColumnKeyToIdx('path')
        for row, item in enumerate(shownItemIdx):
            for i, col in enumerate(shownColIdx):
                if col != orderIdx:
                    continue
                # analyzing status
                status = self.parent.innerList[listIdx].items[item][statusIdx]
                # rects = (columns[i].x+1, row_size*row+rect.y-row_offset+1,\
                #   columns[i].width-2-22, row_size-1)
                rects = (columns[i].x + 1, row_size * row + rect.y - row_offset + 1, 4, row_size - 1)
                # elif status == 'analyzing':
                #   dc.DrawRectangleList((rects,), pens=wx.Pen((80,80,255), 0),\
                #       brushes=wx.Brush(wx.Colour(100,100,255)))
                if self.parent.innerList[listIdx].items[item][pathIdx] in procpath:
                    color = self.parent.st.ANALYZE_PEND_COLOR
                    dc.DrawRectangleList((rects,), pens=wx.Pen(color, 1),
                                         brushes=wx.Brush(color))
                elif status == '':
                    color = self.parent.st.ANALYZE_NONE_COLOR
                    dc.DrawRectangleList((rects,), pens=wx.Pen(color, 1),
                                         brushes=wx.Brush(color))
                elif status == 'error':
                    if self.parent.IsHighlightedItem(item):
                        bmp = images.listbox_brokenlink_black.GetBitmap()
                    else:
                        bmp = images.listbox_brokenlink_red.GetBitmap()
                    m = int((row_size - bmp.GetHeight()) * 0.5) - 1
                    dc.DrawBitmap(bmp, rects[0], rects[1] + m, useMask=False)
                # playing status
                if self.parent.parent.PlayBox.cue.listId\
                        != self.parent.innerList[listIdx].Id:
                    continue
                if self.parent.innerList[listIdx].items[item][pathIdx]\
                        != self.parent.parent.PlayBox.cue.path:
                    continue
                column = columns[i]
                font_color = self.parent.st.LIST_FG_COLOR
                if self.parent.IsHighlightedItem(item):
                    font_color = self.parent.st.SELECTED_FG_COLOR
                if self.parent.parent.PlayBox.IsPlaying()\
                        or self.pending.SkipStopIcon and status != 'error':
                    self.pending.SkipStopIcon = False
                    if sum(font_color) / 3.0 > 125:
                        bmp = self.bmp.playing.white
                    else:
                        bmp = self.bmp.playing.black
                    offset = int((row_size - 8) * 0.5)
                    dc.DrawBitmap(bmp, column.x + 9,
                                  row_size * row + rect.y - row_offset + offset, useMask=False)
                else:
                    x = column.x + 9
                    offset = int((row_size - 8) * 0.5)
                    y = row_size * row + rect.y - row_offset + offset + 1
                    w, h = (7, 7)
                    rects = [(x, y, w, h)]
                    dc.DrawRectangleList(rects,
                                         pens=(wx.Pen(font_color, 1),), brushes=(wx.Brush(font_color),))
                break

    def DrawInsertItemLine(self, dc):
        row_size = self.parent.GetRowsHeight()
        vpy = self.parent.GetVirtualPositionY()
        itemsLength = self.parent.GetItemsLength()
        shownItemsIdx = self.parent.GetShownItemsIdx()
        # lines = list()
        row_offset = abs(vpy) % row_size - 0
        rows = [i for i, v in enumerate(shownItemsIdx)
                if v == self.FileDrop.insertItemIdx]
        if self.FileDrop.insertItemIdx == itemsLength:
            rows = [len(shownItemsIdx)]
        if len(rows) == 0:
            return
        x = self.parent.GetVirtualPositionX() - 1
        y = row_size * rows[0] - row_offset - 1
        w = self.parent.GetVirtualPositionXW() - 1 + 1
        # h = row_size * rows[0] - row_offset
        # color = self.parent.st.INSERTITEM_CURSOR_COLOR
        # dc.DrawLineList([(x, y, w, h)], pens=wx.Pen(color, 1))

        # lr_pad = 1
        # print(itemsLength, self.FileDrop.insertItemIdx)
        if itemsLength == self.FileDrop.insertItemIdx:
            y -= 1
        dc.DrawRectangleList(((x, y, w + 2, 3),),
                             pens=wx.Pen((20, 20, 20)), brushes=wx.Brush((200, 200, 200, 255)))

    # Handle ListBoxList Event

    def GetRectIdx(self, xy):
        x, y = xy
        if self.onClient is False:
            return None
        if self.parent.GetItemsLength() == 0:
            return 0
        if x >= self.parent.GetVirtualPositionXW():
            return 0
        if y >= self.parent.GetItemsLength() * self.parent.GetRowsHeight():
            return 0
        return 1

    def ExtendGlobalEvent(self, event):
        event.itemIdx = self.parent.PosY2Item(event.Y)
        event.columnIdx = self.parent.GetColumnRectIdx(event.X)
        event.insertItemIdx = self.parent.GetInsertItemIdx(event.Y)
        event.down.itemIdx = None
        event.down.columnIdx, event.drag.columnIdx = (None, None)
        event.isSelectedItem = self.parent.IsSelectedItem(event.itemIdx)
        if event.LeftDown or event.RightDown or event.MiddleDown:
            event.down.itemIdx = self.parent.PosY2Item(event.down.Y)
            event.down.columnIdx = self.parent.GetColumnRectIdx(event.down.X)
        if (event.LeftDown is False and event.LeftIsDown)\
                or (event.RightDown is False and event.RightIsDown)\
                or (event.MiddleDown is False and event.MiddleIsDown):
            event.down.itemIdx = self.cache.down.itemIdx
            event.down.columnIdx = self.cache.down.columnIdx
        if event.LeftDrag:
            event.drag.columnIdx = self.parent.GetColumnRectIdx(event.drag.X)
        if event.LeftDrag is False and event.LeftIsDrag:
            event.drag.columnIdx = self.cache.drag.columnIdx
        if event.LeftUp or event.RightUp or event.MiddleUp:
            event.down.itemIdx = self.cache.down.itemIdx
            event.down.columnIdx = self.cache.down.columnIdx
            event.drag.columnIdx = self.cache.drag.columnIdx
        self.cache.isSelectedItem = event.isSelectedItem
        self.cache.down.itemIdx = event.down.itemIdx
        self.cache.down.columnIdx = event.down.columnIdx
        self.cache.drag.columnIdx = event.drag.columnIdx
        return event

    def CATCH_EVT_GLOBAL(self, event):

        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleEventItemDrag(event)
        self.HandleEventFileDropPending(event)
        self.HandleEventFileDropFinish(event)
        self.HandleEventItemSelectionLeftIsDown(event)
        self.HandleEventItemSelectionRightIsDown(event)
        self.HandleEventItemSelectionLeftUp(event)
        self.HandleEventItemPopup(event)
        self.InitPendingEventState(event)
        self.HandleEventTextEditDestroy(event)

        # MACOSX
        if event.LeftUpDelayed:
            self.FileDrop.dropTimer = 0
            self.FileDrop.itemDrag = False
            self.FileDrop.importing = False
            self.FileDrop.insertItemIdx = None
            self.DirectDraw()
        if self.cache.insertItemDelayed > 100000000000000000:
            self.cache.insertItemDelayed = 11
        if self.FileDrop.insertItemIdx is not None:
            self.cache.insertItemDelayed = 0
        else:
            self.cache.insertItemDelayed += 1
        if self.cache.insertItemDelayed <= 10:
            self.DirectDraw()

    def HandleEventTextEditDestroy(self, event):
        if self.TextEdit is None:
            return
        isInRect = self.IsInRect(self.TextEdit.GetRect(), (event.X, event.Y))
        if isInRect is False and event.RightDown or event.MiddleDown:
            self.TextEdit.destroy = True
        if self.TextEdit.destroy:
            self.TextEdit.Destroy()
            self.TextEdit = None
            # self.reInitBuffer = True
            self.DirectDraw()

    def InitPendingEventState(self, event):
        if event.LeftUp is False:
            return
        self.pending.SkipControlSelectItem = False

    def HandleEventItemDrag(self, event):
        if self.FileDrop.itemDrag:
            self.parent.reInitBuffer = True
            self.parent.SliderV.DirectDraw()
        if event.LeftUp:
            self.FileDrop.itemDrag = False
            self.FileDrop.dropTimer = 0
        if event.drag.rectIdx == 0:
            return
        if event.LeftIsDrag is False:
            return
        if event.drag.rectIdx is None:
            return
        if event.down.itemIdx == event.itemIdx\
            and self.FileDrop.itemDrag is False\
                and event.rectIdx is not None:
            return
        self.FileDrop.itemDrag = True
        self.pending.SkipItemSelection = True
        selected = self.parent.GetSelectedItemsKeyValue('path')
        if selected is None:
            return
        self.parent.parent.SetItemDrag(selected)

    def HandleEventFileDropFinish(self, event):
        if self.parent.IsFilteredAll():
            return
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.FileDrop.insertItemIdx = None
            self.FileDrop.onClient = False
            self.FileDrop.importing = False
        mouseUp = event.LeftUpDelayed or event.RightUp or event.MiddleUp
        if self.FileDrop.insertItemIdx is not None\
                and (event.rectIdx is None or mouseUp):
            self.FileDrop.insertItemIdx = None
            self.DirectDraw()

    def HandleEventFileDropPending(self, event):
        if self.parent.IsFilteredAll():
            return
        if event.insertItemIdx is None:
            return
        if self.FileDrop.onClient is False:
            return
        if event.drag.rectIdx is None:
            self.FileDrop.importing = True
        else:
            self.FileDrop.importing = False
        orderIdx = self.parent.GetColumnKeyToIdx('order')
        if self.parent.GetLastSortedColumn()[0] != orderIdx:
            return
        height = self.GetSize().height
        row_size = self.parent.GetRowsHeight()
        isUpward = event.Y < 0 + row_size * 0.5
        isDownward = event.Y > 0 + height - row_size * 0.5
        self.FileDrop.insertItemIdx = event.insertItemIdx
        if isUpward or isDownward:
            self.FileDrop.dropTimer += 1
        else:
            self.FileDrop.dropTimer = 0
        if self.FileDrop.dropTimer > 20:
            if isUpward:
                self.parent.ScrollV(0.18)
            elif isDownward:
                self.parent.ScrollV(-0.18)
        self.DirectDraw()

    def HandleEventItemSelectionLeftIsDown(self, event):
        if self.FileDrop.itemDrag:
            return
        if self.FileDrop.importing:
            return
        if self.FileDrop.insertItemIdx is not None:
            return
        if event.LeftIsDown is False:
            return
        # self.parent.SelectAndFocusItem(event.itemIdx)
        # self.parent.LeftDoubleClick(event)

        if event.down.rectIdx == 0 and event.LeftDrag:
            self.parent.SelectAndFocusItem(event.down.itemIdx)
        elif event.down.rectIdx == 0 and event.LeftIsDrag:
            self.parent.ShiftSelectItems(event.itemIdx)

        if event.rectIdx != 1:
            return

        if event.LeftDClick:
            self.parent.SelectAndFocusItem(event.itemIdx)
            self.parent.LeftDoubleClick(event)
        elif event.ShiftDown and event.LeftDown:
            self.parent.ShiftSelectItems(event.itemIdx)

        elif event.ControlDown and event.LeftDown\
                and event.isSelectedItem is False:
            self.parent.ControlSelectItem(event.itemIdx)
            self.pending.SkipControlSelectItem = True

        elif event.LeftDown and event.isSelectedItem is False:
            self.parent.SelectAndFocusItem(event.itemIdx)

        # elif event.LeftDown:
        #     is_playing_item = False
        #     selectedItems = self.parent.GetSelectedItems()
        #     if self.parent.parent.PlayBox.IsPlaying():
        #         path = self.parent.GetItemValueByColumnKey(event.itemIdx, 'path')
        #         if path == self.parent.parent.PlayBox.GetPlayingItemInfo('path'):
        #             is_playing_item = True
        #     if is_playing_item is False and len(selectedItems) == 1\
        #             and selectedItems[0] == event.itemIdx:
        #         self.parent.LeftDoubleClick(event)

    def HandleEventItemSelectionRightIsDown(self, event):
        # if event.rectIdx is None: return
        if event.RightIsDown is False:
            return

        if event.RightDown and event.rectIdx == 1\
                and event.isSelectedItem is False:
            self.parent.SelectAndFocusItem(event.itemIdx)

        elif event.RightDrag and event.rectIdx in (0, 1):
            self.parent.SelectAndFocusItem(event.down.itemIdx)

        elif event.RightIsDrag and event.down.rectIdx is not None:
            self.parent.ShiftSelectItems(event.itemIdx)

    def HandleEventItemSelectionLeftUp(self, event):
        if event.LeftUp is False:
            return
        if self.pending.SkipItemSelection:
            self.pending.SkipItemSelection = False
            return
        if event.rectIdx != 1:
            return

        if event.ControlDown and event.isSelectedItem\
                and self.pending.SkipControlSelectItem is False:
            self.parent.ControlSelectItem(event.itemIdx)

        elif event.down.rectIdx == 1 and event.isSelectedItem is True\
                and event.ControlDown is False and event.ShiftDown is False:
            self.parent.SelectAndFocusItem(event.itemIdx)

    def HandleEventItemPopup(self, event):
        if self.TextEdit is not None:
            return
        if event.RightUp is False:
            return
        if event.rectIdx != 1:
            return
        if event.down.rectIdx != 1:
            return
        if event.drag.rectIdx is not None:
            return
        self.DirectDraw()
        self.parent.parent.SetPopupMenu(ListBoxPopupItem(self), (event.x, event.y))

    def CATCH_EVT_KEY_UP(self, event):
        return

    def CATCH_EVT_KEY_DOWN(self, event):
        # isSPKD = event.AltDown or event.CmdDown\
        #   or event.ControlDown or event.ShiftDown
        # if namespace is None: return
        # print event.KeyCode

        if event.ControlDown and event.KeyCode == 65:  # A
            self.parent.SelectItemAll()

        elif event.ControlDown and event.KeyCode == wx.WXK_SPACE:
            pass

        elif event.ControlDown and event.KeyCode == wx.WXK_LEFT:
            maxListIdx = len(self.parent.innerList) - 1
            idx = self.parent.GetSelectedListIdx()
            idx -= 1
            if idx < 0:
                idx = maxListIdx
            self.parent.SetSelectedList(idx)
            self.parent.DirectDraw()
            self.parent.parent.OnSize(None)

        elif event.ControlDown and event.KeyCode == wx.WXK_RIGHT:
            maxListIdx = len(self.parent.innerList) - 1
            idx = self.parent.GetSelectedListIdx()
            idx += 1
            if idx > maxListIdx:
                idx = 0
            self.parent.SetSelectedList(idx)
            self.parent.DirectDraw()
            self.parent.parent.OnSize(None)

        elif event.ShiftDown and event.KeyCode == wx.WXK_UP:
            self.parent.ScrollSelectItem(-1, shifted=True)
        elif event.KeyCode == wx.WXK_UP:
            self.parent.ScrollSelectItem(-1)

        elif event.ShiftDown and event.KeyCode == wx.WXK_DOWN:
            self.parent.ScrollSelectItem(1, shifted=True)
        elif event.KeyCode == wx.WXK_DOWN:
            self.parent.ScrollSelectItem(1)

        elif event.ShiftDown and event.KeyCode == wx.WXK_PAGEUP:
            self.parent.ScrollSelectItem(-self.parent.GetMaxLine() + 1, shifted=True)
        elif event.KeyCode == wx.WXK_PAGEUP:
            self.parent.ScrollSelectItem(-self.parent.GetMaxLine() + 1)

        elif event.ShiftDown and event.KeyCode == wx.WXK_PAGEDOWN:
            self.parent.ScrollSelectItem(self.parent.GetMaxLine() - 1, shifted=True)
        elif event.KeyCode == wx.WXK_PAGEDOWN:
            self.parent.ScrollSelectItem(self.parent.GetMaxLine() - 1)

        elif event.ShiftDown and event.KeyCode == wx.WXK_HOME:
            self.parent.ScrollSelectItem(0.0, shifted=True)
        elif event.KeyCode == wx.WXK_HOME:
            self.parent.ScrollSelectItem(0.0)

        elif event.ShiftDown and event.KeyCode == wx.WXK_END:
            self.parent.ScrollSelectItem(1.0, shifted=True)
        elif event.KeyCode == wx.WXK_END:
            self.parent.ScrollSelectItem(1.0)

        elif event.KeyCode == wx.WXK_DELETE:
            self.parent.RemoveSelectedItems()

        ctrl = event.CmdDown or event.ControlDown
        namespace = self.parent.parent.parent.GetNameSpaceByRawKeyFlag(
            event.RawKeyFlags, ctrl, event.ShiftDown)

        if namespace == 'open_id3tageditor':
            self.OpenItemEditBox(event)

        if namespace == 'open_scripteditor':
            self.OpenScriptEditBox(event)

        if namespace == 'open_websearch_1':
            weblink = OpenWebLinkHandler(self)
            weblink.OnWebLink(None, idx=0)

        if namespace == 'open_websearch_2':
            weblink = OpenWebLinkHandler(self)
            weblink.OnWebLink(None, idx=1)

        if namespace == 'open_websearch_3':
            weblink = OpenWebLinkHandler(self)
            weblink.OnWebLink(None, idx=2)

    def OpenScriptEditBox(self, event):
        self.parent.parent.parent.OnScriptEditor(event)

    def OpenItemEditBox(self, event):
        self.parent.parent.parent.DialogBox = ItemEditBox(self)
        x, y, w, h = self.parent.parent.parent.GetRect()
        width, height = self.parent.parent.parent.DialogBox.GetSize()
        self.parent.parent.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.parent.parent.DialogBox.ShowModal()
        self.parent.parent.parent.DialogBox.Destroy()
        self.parent.parent.parent.DialogBox = None
        self.DirectDraw()

    def EditItemColumnText(self, event):
        if self.TextEdit is not None:
            return
        if self.parent.GetSelectedItemsLength() != 1:
            return
        columnIdx = self.parent.GetGlobalColumnIdx(event.X)
        if self.parent.IsEdiditableColumnByColumnIdx(columnIdx) is False:
            return
        selectedItem = self.parent.GetSelectedItem()
        self.TextEdit = ItemTextEdit(self)
        self.parent.FocusItem(selectedItem)
        self.TextEdit.SetText(selectedItem, columnIdx)

    def CATCH_EVT_MOUSEWHEEL(self, event):

        if self.TextEdit is not None:
            self.TextEdit.CommitText()
        if self.onClient is False:
            return
        self.parent.ScrollV(event.WheelRotation / 40)

    def OnSize(self, event=None):
        self.DirectDraw()


class ListBoxHeader(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.height = 23
        self.cache.splitterIdx = None
        self.cache.down.columnIdx = None
        self.cache.down.splitterIdx = None
        self.cache.drag.columnIdx = None
        self.cache.drag.splitterIdx = None
        self.cache.skip = Struct(leftDClick=False)
        self.pending = Struct(autoColumnWidthIdx=None, downColumnIdx=None,
                              insertColumnIdx=None, dragColumnWidth=None, ColumnSortDown=False,
                              LeftDoubleClick=False)
        self.InitBuffer()

    def SetAutoColumnWidth(self):
        width, height = self.GetSize()
        idx = 2
        left_pad = 58
        right_pad = 55 + 55 + 65 + 3  # -10
        self.parent.SetColumnWidthAll(idx, width - left_pad - right_pad)

    def IsSplitterOnSize(self):
        if self.cache.down.columnIdx is not None:
            return False
        if self.cache.down.splitterIdx is not None:
            return True
        # if self.cache.splitterIdx is not None: return True
        return False

    # Draw ListBoxHeader

    def SetRectDraw(self, dc):
        self.SetAutoWidthColumn(dc)
        self.DrawHeaderRect(dc)
        self.DrawHeaderLine(dc)
        self.DrawHeaderText(dc)
        self.DrawHeaderPolygon(dc)
        self.DrawHeaderInsertLine(dc)

    def SetAutoWidthColumn(self, dc):
        idx = self.pending.autoColumnWidthIdx
        if idx is None:
            return
        self.pending.autoColumnWidthIdx = None
        cid = self.parent.GetShownColumnsIdx()[idx]
        ft = self.parent.GetFontInfo()
        font = wx.Font(0, wx.MODERN, wx.NORMAL, ft.weight)
        font.SetPixelSize(ft.size)
        font.SetFaceName(ft.name)
        font.SetStyle(ft.style)
        dc.SetFont(font)
        tws = list()
        for item in self.parent.GetShownItemsIdx():
            string = '%s' % (self.parent
                             .innerList[self.parent.selectedList].items[item][cid])
            # string = string.encode(sys.getfilesystemencoding())
            tw = dc.GetPartialTextExtents(string)
            if len(tw) == 0:
                tw = [0]
            tws.append(max(tw))
        if len(tws) == 0:
            tws = 0
        else:
            tws = max(tws) + 20
        if tws < 26:
            tws = 26
        self.parent.SetBestColumnWidth(cid, tws)

    def DrawHeaderRect(self, dc):
        shownColumns = self.parent.GetShownColumns()
        width, height = self.GetClientSize()
        rects = list() * len(shownColumns)
        x = self.parent.GetVirtualPositionX()
        for i, column in enumerate(shownColumns):
            rects.append(wx.Rect(x, 0, column.width, height))
            x += column.width
        self.rects = rects
        rect = (0, 0, width, height)
        color = self.parent.st.HEADER_BG_COLOR
        dc.DrawRectangleList((rect,),
                             pens=wx.Pen(color, 1),
                             brushes=wx.Brush(color))

    def DrawHeaderLine(self, dc):
        lines = list()
        for rect in self.rects:
            lines.append((rect.x, rect.y + 1, rect.x, rect.y + rect.height))
        lines.append((rect.x + rect.width, rect.y + 1, rect.x + rect.width, rect.y + rect.height))
        width = self.rects[-1].x + self.rects[-1].width
        # height = self.rects[-1].height
        lines.append((0, 1, width, 1))
        width = self.parent.GetRect().width
        lines.append((0, 1, width, 1))
        color = self.parent.st.HEADER_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))

    def DrawHeaderText(self, dc):
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font_size = FONT_ITEM_SIZE
        # font_size = (5,10)
        font.SetPixelSize(font_size)
        font.SetFaceName(FONT_ITEM)
        dc.SetFont(font)
        tw, th = font_size
        rows_height = self.parent.GetRowsHeight()
        margin_top = int((rows_height - th) * 0.5)  # -1
        # shownColumns = self.parent.GetShownColumns()
        shownColumnsIdx = self.parent.GetShownColumnsIdx()
        lastSortedColumn = self.parent.GetLastSortedColumn()
        sortedIdx = [i for i, v in enumerate(shownColumnsIdx) if v == lastSortedColumn[0]]
        xys = list()
        texts = list()
        if sys.platform.startswith('win'):
            osxpad = 0
        elif sys.platform.startswith('darwin'):
            osxpad = 2
        for cid, v in enumerate(zip(self.rects, self.parent.GetShownColumns())):
            rect, column = v
            right_pad = 0
            if sortedIdx != [] and cid == sortedIdx[0]:
                right_pad = 17
            limit = len([i for i in dc.GetPartialTextExtents(column.title)
                         if i <= rect.width - tw - 8 - right_pad])
            title = column.title[:limit]
            texts.append(title)
            xys.append((rect.x + 10, rect.y + margin_top + osxpad))
        # tw, th = dc.GetTextExtent('A')
        r, g, b = self.parent.st.HEADER_FG_COLOR
        dc.DrawTextList(texts, xys, foregrounds=wx.Colour(r, g, b), backgrounds=None)

    def DrawHeaderPolygon(self, dc):
        rows_height = self.parent.GetRowsHeight()
        margin_top = int((rows_height - 10) * 0.5) + 4
        shownColumns = self.parent.GetShownColumns()
        shownColumnsIdx = self.parent.GetShownColumnsIdx()
        lastSortedColumn = self.parent.GetLastSortedColumn()
        if lastSortedColumn == [None, None]:
            return [[(0, 0)]]
        if lastSortedColumn[1] == -1:
            triangle = [(0, 0), (2, 0), (1, 1)]
        elif lastSortedColumn[1] == 1:
            triangle = [(0, 1), (2, 1), (1, 0)]
        size = 3
        x_margin = 13
        y_margin = 10
        y_margin = margin_top
        idx = [i for i, v in enumerate(shownColumnsIdx) if v == lastSortedColumn[0]]
        if idx == []:
            return None
        vpxw = self.parent.GetVirtualPositionX()
        for v in shownColumns[:idx[0] + 1]:
            vpxw += v.width
        x_margin = vpxw - x_margin - size
        for i in range(0, len(triangle)):
            triangle[i] = (triangle[i][0] * size + x_margin, triangle[i][1] * size + y_margin)
        r, g, b = self.parent.st.HEADER_FG_COLOR
        dc.DrawPolygonList((triangle,), pens=wx.Pen((r, g, b), 1),
                           brushes=wx.Brush(wx.Colour(r, g, b)))

    def DrawHeaderInsertLine(self, dc):
        if self.pending.insertColumnIdx is None:
            return
        width, heigth = self.GetSize()
        vpx = self.parent.GetVirtualPositionX()
        vpxw = self.parent.GetVirtualPositionXW()
        shownColumns = self.parent.GetShownColumns()
        insertColumnX = 0
        for v in shownColumns[:self.pending.insertColumnIdx]:
            insertColumnX += v.width
        if self.pending.insertColumnIdx < len(shownColumns):
            dropPosX = insertColumnX + vpx
        else:
            dropPosX = vpxw
        if dropPosX < 2:
            dropPosX = 0
        if dropPosX > width - 2:
            dropPosX = width - 1
        r, g, b = self.parent.st.INSERTCOLCURSOR_FG_COLOR
        border = self.parent.st.INSERTCOLCURSOR_BG_COLOR
        dc.DrawRectangleList(((dropPosX - 1, 3, 3, heigth - 4),),
                             pens=wx.Pen(border, 1), brushes=wx.Brush((r, g, b)))

    # Handle ListBoxHeader Event

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        return 1

    def ExtendGlobalEvent(self, event):
        event.columnIdx = self.parent.GetColumnRectIdx(event.X)
        event.splitterIdx = self.parent.GetColumnSplitterIdx(event.X)
        event.insertColumnIdx = self.parent.GetInsertColumnIdx(event.X)
        event.down.columnIdx, event.drag.columnIdx = (None, None)
        event.down.splitterIdx, event.drag.splitterIdx = (None, None)
        if event.LeftDown or event.RightDown or event.MiddleDown:
            event.down.columnIdx = self.parent.GetColumnRectIdx(event.down.X)
            event.down.splitterIdx = self.parent.GetColumnSplitterIdx(event.down.X)
        if (event.LeftDown is False and event.LeftIsDown)\
                or (event.RightDown is False and event.RightIsDown)\
                or (event.MiddleDown is False and event.MiddleIsDown):
            event.down.columnIdx = self.cache.down.columnIdx
            event.down.splitterIdx = self.cache.down.splitterIdx
        if event.LeftDrag:
            event.drag.columnIdx = self.parent.GetColumnRectIdx(event.drag.X)
            event.drag.splitterIdx = self.parent.GetColumnSplitterIdx(event.drag.X)
        if event.LeftDrag is False and event.LeftIsDrag:
            event.drag.columnIdx = self.cache.drag.columnIdx
            event.drag.splitterIdx = self.cache.drag.splitterIdx
        if event.LeftUp or event.RightUp or event.MiddleUp:
            event.down.columnIdx = self.cache.down.columnIdx
            event.down.splitterIdx = self.cache.down.splitterIdx
            event.drag.columnIdx = self.cache.drag.columnIdx
            event.drag.splitterIdx = self.cache.drag.splitterIdx
        self.cache.splitterIdx = event.splitterIdx
        self.cache.down.columnIdx = event.down.columnIdx
        self.cache.down.splitterIdx = event.down.splitterIdx
        self.cache.drag.columnIdx = event.drag.columnIdx
        self.cache.drag.splitterIdx = event.drag.splitterIdx
        return event

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleEventColumnSortDown(event)
        # self.HandleEventColumnShuffleDrag(event)
        # self.HandleEventColumnSplitterAuto(event)
        # self.HandleEventColumnSplitterDrag(event)
        # self.HandleEventHeaderPopup(event)
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.pending.downColumnIdx = None
            self.pending.insertColumnIdx = None
            self.pending.dragColumnWidth = None
            self.pending.ColumnSortDown = False

    def HandleEventColumnSplitterAuto(self, event):
        if event.LeftDClick is False:
            return
        if event.down.splitterIdx is None:
            return
        self.pending.ColumnSortDown = True
        if event.splitterIdx is None:
            return
        self.pending.autoColumnWidthIdx = event.splitterIdx

    def HandleEventColumnSplitterDrag(self, event):
        if self.parent.List.FileDrop.itemDrag:
            return

        if event.LeftUp:
            self.parent.reInitBuffer = True
        if event.drag.splitterIdx is None:
            return
        idx = self.parent.GetShownColumnsIdx()[event.drag.splitterIdx]
        if event.LeftDrag and event.drag.rectIdx is not None:
            self.pending.dragColumnWidth = self.parent.GetColumns()[idx].width
        if self.pending.dragColumnWidth is None or event.drag.X is None:
            return
        width = self.pending.dragColumnWidth + event.X - event.drag.X
        self.parent.SetBestColumnWidth(idx, width)

    def HandleEventHeaderPopup(self, event):
        if event.RightUp is False:
            return
        if event.down.rectIdx is None:
            return
        if self.onClient is False:
            return
        self.parent.parent.SetPopupMenu(ListBoxPopupHeader(self), (event.x, event.y))

    def HandleEventColumnSortDown(self, event):
        if self.pending.ColumnSortDown and event.LeftUp:
            self.pending.ColumnSortDown = False
            return
        if event.LeftIsDrag:
            return
        if event.LeftUp is False:
            return
        if self.onClient is False:
            return
        if event.splitterIdx is not None:
            return
        if event.down.rectIdx is None:
            return
        if event.down.columnIdx is None:
            return
        if event.down.splitterIdx is not None:
            return
        if self.pending.ColumnSortDown:
            return
        columnIdx = event.down.columnIdx
        self.parent.SortColumn(self.parent.GetShownColumnsIdx()[columnIdx])

    def HandleEventColumnShuffleDrag(self, event):
        if event.drag.rectIdx is None:
            return
        if event.drag.splitterIdx is not None:
            return
        self.FinalizeColumnShuffleDrag(event)
        if event.rectIdx is None and self.pending.insertColumnIdx is not None:
            self.pending.insertColumnIdx = None
            self.parent.reInitBuffer = True

        if event.LeftUp:
            return
        if event.drag.columnIdx is None:
            return
        width, _ = self.GetSize()
        isLeftward = (event.X < 20) and (event.X > 0)
        isRightward = (event.X > width - 20) and (event.X < width)
        if isLeftward:
            self.parent.ScrollH(2)
        if isRightward:
            self.parent.ScrollH(-2)
        if event.drag.columnIdx == event.columnIdx\
                and self.pending.insertColumnIdx is None:
            return
        self.pending.ColumnSortDown = True
        self.pending.insertColumnIdx = event.insertColumnIdx
        self.parent.reInitBuffer = True

    def FinalizeColumnShuffleDrag(self, event):
        if event.LeftUp is False:
            return
        if self.pending.insertColumnIdx is None:
            return
        fromIdx = event.drag.columnIdx
        toIdx = self.pending.insertColumnIdx
        self.parent.SetShownColumnShuffle(fromIdx, toIdx)
        self.pending.insertColumnIdx = None
        self.parent.reInitBuffer = True

    def OnSize(self, event=None):
        self.DirectDraw()


class SearchText(wx.TextCtrl):

    def __init__(self, parent):
        wx.TextCtrl.__init__(self, parent, pos=(0, 0), size=(0, 0), style=0)
        self.parent = parent
        self.onClient = False
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour((255, 255, 255))
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetFaceName(FONT_ITEM)
        font.SetPixelSize((6, 12))
        self.SetFont(font)
        fc = sum(self.GetBackgroundColour()) / 3.0
        if fc > 125:
            self.SetForegroundColour((0, 0, 0))
        else:
            self.SetForegroundColour((255, 255, 255))

    def OnFocus(self, event):
        self.onClient = True
        event.Skip()

    def OnKillFocus(self, event):
        self.onClient = False
        event.Skip()

    def OnKeyDown(self, event):
        blocked_keys = (wx.WXK_UP,
                        wx.WXK_DOWN, wx.WXK_NUMPAD_UP, wx.WXK_NUMPAD_DOWN, wx.WXK_PAGEUP,
                        wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEUP, wx.WXK_NUMPAD_PAGEDOWN)
        if event.KeyCode in blocked_keys:
            return
        elif event.KeyCode == wx.WXK_BACK and len(self.GetValue()) == 0:
            return
        event.Skip()
        # event.ResumePropagation(0)
        # wx.WXK_TAB, wx.WXK_ESCAPE, wx.WXK_HOME, wx.WXK_END, wx.WXK_BACK

    def EventToFilter(self):
        if self.parent.parent.ListBox.IsFilteredAll() is False:
            self.parent.button_state[0] = True
            self.parent.parent.ListBox.SetFilterOnAll()
            query = self.GetValue()
            query_columnKey = self.parent.query_columnKey
            self.parent.parent.ListBox.FilterItemsAll(query_columnKey, query)
            self.parent.parent.ListBox.reInitBuffer = True
            self.parent.reInitBuffer = True


class SearchComboFilter(ComboBox):

    def __init__(self, parent):
        self.choices = ('Filename', 'Album', 'Artist',
                        'Title', 'Genre', 'Key', 'Tempo', 'Type', 'Path')
        ComboBox.__init__(self, parent, choices=self.choices,
                          pos=(5, 3 + 1 + 1), size=(76, 21), style=wx.CB_READONLY)
        # wx.combo.ComboCtrl # self.SetButtonPosition(side=wx.LEFT)
        self.parent = parent
        self.onClient = False
        self.SetBackgroundColour(COLOR_STATUS_BG)
        self.SetStringSelection(self.choices[0])
        self.Bind(wx.EVT_COMBOBOX, self.OnSelect)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetFaceName(FONT_ITEM)
        font.SetPixelSize((6, 12))
        self.SetFont(font)

    def OnFocus(self, event):
        self.onClient = True
        event.Skip()

    def OnKillFocus(self, event):
        self.onClient = False
        event.Skip()

    def OnSelect(self, event):
        query_columnKey = event.GetString().lower()
        value = self.parent.parent.ListSearch.SearchText.GetValue()
        self.parent.query_columnKey = query_columnKey
        if value == '':
            return
        self.parent.parent.ListBox.FilterItemsAll(query_columnKey, value)


class ListBoxSearch(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        color = self.parent.parent.st.LISTBOX.TOOLBAR_BG_COLOR
        self.SetBackgroundColour(color)
        self.last_query = ''
        self.query_columnKey = 'filename'
        self.SearchComboFilter = SearchComboFilter(self)
        self.SetDoubleBuffered(True)
        self.SearchText = SearchText(self)
        # self.button_color_on = (255,0,0)
        # self.button_color_off = (0,0,0)
        self.button_color_on = color
        self.button_color_off = color
        self.button_state = [False]
        button_color = []
        for v in self.button_state:
            if v:
                button_color += [(self.button_color_on)]
            else:
                button_color += [(self.button_color_off)]
        self.button_color = button_color
        self.OnSize()
        self.InitBuffer()

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        for i in range(len(self.rects[:-1])):
            if self.IsInRect(self.rects[i], xy):
                return i
        return None

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.HasToSkipEvent():
            return
        if self.onClient and event.LeftDown\
                and self.parent.ListBox.List.TextEdit is not None:
            self.parent.ListBox.List.TextEdit.CommitText()
        self.OverrideEventFromParent(event)
        self.HandleEventFilterQuery(event)
        self.HandleEventButtonColor(event)
        value = self.SearchText.GetValue()
        if len(value) > 0:
            self.parent.ListBox.SetFilterOnAll()
        elif len(value) == 0:
            self.parent.ListBox.SetFilterOffAll()
        # self.HandleEventSearchPopup(event)

    def HandleEventSearchPopup(self, event):
        if event.RightUp is False and event.LeftUp is False:
            return
        if event.rectIdx != 0:
            return
        if event.down.rectIdx != 0:
            return
        self.parent.SetPopupMenu(ListBoxPopupSearch(self), (event.x, event.y))

    def OverrideEventFromParent(self, event):
        status = self.parent.ListBox.IsFilteredAll()
        if self.button_state[0] == status:
            return
        self.button_state[0] = status
        self.reInitBuffer = True

    def HandleEventButtonColor(self, event):
        button_color = []
        for v in self.button_state:
            if v:
                button_color += [(self.button_color_on)]
            else:
                button_color += [(self.button_color_off)]
        self.button_color = button_color
        if event.rectIdx is None:
            return
        if event.LeftDown is False:
            return
        if event.down.rectIdx is None:
            return
        self.reInitBuffer = True

    def HandleEventFilterQuery(self, event):
        if self.parent.ListBox.IsFilteredAll() is False:
            return
        query = self.SearchText.GetValue()
        if self.last_query == query:
            return
        # print 'Listbox.Tool.HandleEventFilterQuery'
        self.last_query = query
        self.parent.ListBox.FilterItemsAll(self.query_columnKey, query)
        self.parent.ListBox.reInitBuffer = True
        self.reInitBuffer = True

    # Draw ListBoxList

    def SetRectDraw(self, dc):
        return
        if self.button_state[0]:
            dc.DrawRectangleList((self.rects[1],),
                                 pens=wx.Pen(self.button_color[0], 3),
                                 brushes=wx.Brush(COLOR_STATUS_BG))
        else:
            dc.DrawRectangleList((self.rects[1],),
                                 pens=wx.Pen(self.button_color[0], 3),
                                 brushes=wx.Brush(COLOR_STATUS_BG))

    def OnSize(self, event=None):
        w, h = self.GetClientSize()
        self.rects = ((3, 3, w - 6, h - 1), (3, 3, w - 6, h - 1))
        self.SearchText.SetRect((83 + 2 + 1, 5, w - 83 - 4 - 6 + 3 - 1, 14 + 4 + 3))
        self.text_xys = ((10, 5),)
        self.DirectDraw()


threadListLock = threading.Lock()


class ListBoxTabDnD(wx.FileDropTarget):

    def __init__(self, parent):
        wx.FileDropTarget.__init__(self)
        self.parent = parent
        self.tabDrag = False
        self.downTabIdx = None
        self.insertTabIdx = None

    def OnEnter(self, x, y, d):
        self.onClient = True
        self.parent.onClient = True
        return d

    def OnLeave(self):
        self.onClient = False
        self.parent.onClient = False

    def OnDragOver(self, x, y, d):
        self.onClient = True
        self.parent.onClient = True
        return d

    def OnDropFiles(self, x, y, inpaths):
        if self.tabDrag:
            return 0
        if self.parent.parent.ListBox.IsFilteredAll():
            return 0
        # if self.parent.parent.ListBox.IsFilteredAll():
        #   filtered = True
        # else: filtered = False
        tabRectIdx = self.parent.GetTabRectIdx((x, y))
        if self.downTabIdx is not None:
            return
        isExistingTab = tabRectIdx is not None and tabRectIdx != -1
        if isExistingTab:
            self.DropToExistingTab(inpaths, tabRectIdx)
        elif self.parent.IsTabCreationLimited():
            return 0
        else:
            self.CreateAndDropToNewTab(inpaths)
        return 0

    def CreateAndDropToNewTab(self, inpaths):
        if len(inpaths) > 1:
            self.parent.parent.ListBox.AddInnerList()
            # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(inpaths)
            self.DropFromOutside(inpaths)
            # t = threading.Thread(
            #     target=self.parent.parent.ListBox.List.FileDrop.DropFromOutside,
            #     args=(inpaths,), daemon=True
            # )
            # t.start()

            self.parent.parent.ListBox.Header.SetAutoColumnWidth()
            self.parent.reInitBuffer = True

        elif len(inpaths) == 1:
            path = inpaths[0]
            if os.path.isfile(path) is False\
                    and os.path.isdir(path) is False:
                return
            stats = os.stat(path)
            basename = os.path.basename(path)
            file_type = os.path.splitext(basename)[1][1:].lower()
            if stats[stat.ST_MODE] == 16895:
                title = basename
            elif stats[stat.ST_MODE] == 33206\
                    and file_type in SUPPORTED_PLAYLIST_TYPE:
                title = os.path.splitext(basename)[0]
                inpaths = audio.read_m3u(path)
            else:
                title = None
            self.parent.parent.ListBox.AddInnerList(title)
            self.parent.parent.ListBox.Header.SetAutoColumnWidth()
            # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(inpaths)
            self.DropFromOutside(inpaths)
            self.parent.reInitBuffer = True

    def DropFromOutside(self, inpaths, tabRectIdx=None):

        kwargs = {}
        if tabRectIdx:
            kwargs.update({'selectedList': tabRectIdx})

        t = threading.Thread(
            target=self.parent.parent.ListBox.List.FileDrop.DropFromOutside,
            args=(inpaths,), kwargs=kwargs, daemon=True
        )
        t.start()

    def DropToExistingTab(self, inpaths, tabRectIdx):
        # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(
        #     inpaths, selectedList=tabRectIdx)
        self.DropFromOutside(inpaths, selectedList=tabRectIdx)
        self.parent.reInitBuffer = True

    def SearchPatternIncludeSub(self, filepath, pattern='*'):
        # filepath = unicode(filepath)
        # pattern = unicode(pattern)
        retlist = glob.glob(os.path.join(filepath, pattern))
        findlist = os.listdir(filepath)
        for f in findlist:
            next = os.path.join(filepath, f)
            if os.path.isdir(next):
                retlist += self.SearchPatternIncludeSub(next, pattern)
        return retlist


class ListBoxTab(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.cache.down.tabIdx = None
        self.cache.drag.tabIdx = None
        self.cache.down.closeIdx = None
        self.cache.drag.closeIdx = None
        self.cache.tabIdx = None
        self.cache.skip = Struct(leftDClick=False)
        self.tab_num_limit = 20
        self.tab_width = 200
        self.tab_height = 26
        self.bottom_height = 1
        self.tab_rel_width = 200
        self.TextEdit = None
        self.text_edit_tabIdx = None
        self.rects = ((0, 0, 0, 0), (0, 0, 0, 0))
        self.FileDrop = ListBoxTabDnD(self)
        self.SetDropTarget(self.FileDrop)
        self.bmp = Struct()
        self.bmp.add = images.listbox_tab_add.GetBitmap()
        self.bmp.close = images.listbox_tab_close.GetBitmap()
        color = self.parent.parent.st.LISTBOX.LISTTAB_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def IsTabCreationLimited(self):
        return False
        if len(self.rects) > self.tab_num_limit:
            return True
        return False

    # Draw ListBoxTab

    def SetRectDraw(self, dc):
        self.DrawTabRect(dc)
        self.DrawTabRectSelected(dc)
        self.DrawTabLineH(dc)
        self.DrawTabLineV(dc)
        self.DrawTabInsertLine(dc)
        self.DrawTabPolygon(dc)
        self.DrawTabText(dc)
        self.DrawTabTextEdit(dc)

    def DrawTabTextEdit(self, dc):
        if self.TextEdit is None:
            return
        x, y, w, h = self.TextEdit.GetRect()
        rect = (x - 4, y - 2, w + 8, h + 3)
        dc.DrawRectangleList((rect,),
                             pens=wx.Pen((255, 255, 255), 0), brushes=wx.Brush((255, 255, 255)))

    def DrawTabRectSelected(self, dc):
        x, y, w, h = self.rects[self.parent.ListBox.selectedList + 1]
        rect = (x + 1, y, w - 1, h + 1)
        color = self.parent.parent.st.LISTBOX.LISTTAB_FG_COLOR
        color = (200, 200, 200)
        dc.DrawRectangleList((rect,),
                             pens=wx.Pen((0, 0, 0), 1), brushes=wx.Brush(color))

    def DrawTabRect(self, dc):
        tabLength = len(self.parent.ListBox.innerList)
        width, height = self.GetClientSize()
        add_width = width
        rects = list()
        if tabLength == 0:
            r_width = 0
        else:
            r_width = 1.0 * (width - add_width) / tabLength
        if r_width > self.tab_width:
            r_width = self.tab_width
        x = 0
        rects.append(wx.Rect(0, 0, width - 1, self.tab_height - 1))
        for i in range(1, tabLength + 1):
            rects.append(wx.Rect(
                0,
                self.tab_height * i,
                width - 1,
                self.tab_height - 1))
            x += r_width
        x = rects[-1].x + rects[-1].width
        if x > width - add_width:
            x = width - add_width
        # rects.append(wx.Rect(0, height - self.tab_height, width - 1, self.tab_height))

        # print(rects)
        # rects.append(wx.Rect(0, 0, 0, 0))
        self.rects = rects
        color = self.parent.parent.st.LISTBOX.LISTTAB_BG_COLOR
        for i in range(1, len(rects)):
            dc.GradientFillLinear(rects[i], color, color, nDirection=wx.EAST)

        rect = wx.Rect(rects[0])
        rect.height += 1
        dc.GradientFillLinear(rect, (0, 0, 0), (0, 0, 0), nDirection=wx.EAST)
        # self.tab_rel_width = r_width
        # self.tab_rel_width = 200
        # if self.IsTabCreationLimited():
        #     dc.GradientFillLinear(rects[-1], color, color, nDirection=wx.SOUTH)

    # def DrawTabRect(self, dc):
    #     tabLength = len(self.parent.ListBox.innerList)
    #     width, height = self.GetClientSize()
    #     add_width = 26
    #     rects = list()
    #     if tabLength == 0:
    #         r_width = 0
    #     else:
    #         r_width = 1.0 * (width - add_width) / tabLength
    #     if r_width > self.tab_width:
    #         r_width = self.tab_width
    #     x = 0
    #     for i in range(0, tabLength):
    #         rects.append(wx.Rect(int(i * r_width), 0, math.ceil(r_width), height - self.bottom_height))
    #         x += r_width
    #     x = rects[-1].x + rects[-1].width
    #     if x > width - add_width:
    #         x = width - add_width
    #     rects.append(wx.Rect(x, 0, add_width - 1, height - self.bottom_height))
    #     self.rects = rects
    #     color = self.parent.parent.st.LISTBOX.LISTTAB_BG_COLOR
    #     for i in range(len(rects)):
    #         dc.GradientFillLinear(rects[i], color, color, nDirection=wx.SOUTH)
    #     self.tab_rel_width = r_width
    #     if self.IsTabCreationLimited():
    #         dc.GradientFillLinear(rects[-1], color, color, nDirection=wx.SOUTH)

    def DrawTabInsertLine(self, dc):
        if self.FileDrop.insertTabIdx is None:
            return
        # print(self.FileDrop.insertTabIdx)
        if self.FileDrop.insertTabIdx + 1 < len(self.rects):
            rect = self.rects[self.FileDrop.insertTabIdx + 1]
            y = rect.y - 1
        else:
            rect = self.rects[-1]
            y = rect.y + rect.height - 1
        lr_pad = 1
        dc.DrawRectangleList(((lr_pad, y, self.GetSize().width - lr_pad * 2, 3),),
                             pens=wx.Pen((20, 20, 20)), brushes=wx.Brush((200, 200, 200, 255)))
        # dc.DrawLineList(((lr_pad, y, self.GetSize().width - lr_pad * 2, y),),
        #                 pens=wx.Pen((250, 250, 250), 1))

    def DrawTabLineH(self, dc):
        lines = list()
        for rect in self.rects[1:]:
            lines.append((rect.x,
                          rect.y + rect.height,
                          rect.width,
                          rect.y + rect.height))
        lines.append((rect.x,
                      rect.y + rect.height,
                      rect.width,
                      rect.y + rect.height))
        dc.DrawLineList(lines, pens=wx.Pen((30, 30, 30), 1))

    def DrawTabLineV(self, dc):
        lines = list()
        width, height = self.GetSize()
        height = self.rects[-1].y + self.rects[-1].height
        lines.append((0, 1, width, 1))

        lr_pad = 1
        lines.append((lr_pad, self.rects[1].y, lr_pad, height + 1))
        lines.append((width - lr_pad * 2, self.rects[1].y, width - lr_pad * 2, height + 1))

        lines.append((lr_pad, 1, lr_pad, self.rects[0].height + 1))
        lines.append((width - lr_pad * 2, 1, width - lr_pad * 2, self.rects[0].height + 1))
        # lines.append((0, height - 1, width, height - 1))
        # color = (0, 0, 0)
        color = (30, 30, 30)
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))
        # w, h = self.GetSize()
        # dc.DrawLineList(((0, 0, w, 0), (0, h - 1, w, h - 1),), pens=wx.Pen(color, 1))

    def DrawTabText(self, dc):
        if self.tab_rel_width < 30:
            return
        xys = list()
        texts = list()
        selected_xys = list()
        selected_texts = list()
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((6, 11))
        font.SetFaceName(FONT_ITEM)
        dc.SetFont(font)
        for i, v in enumerate(zip(self.rects[1:], self.GetTabsTitles())):
            rect, title = v
            margin = self.close_rects[i].width + 15
            if rect.width - margin < 12:
                continue
            if i == self.parent.ListBox.selectedList:
                selected_texts.append(self.LimitTextLength(dc, title, rect.width - margin))
                selected_xys.append((rect.x + 11, rect.y + 5 + 1))
            else:
                texts.append(self.LimitTextLength(dc, title, rect.width - margin))
                xys.append((rect.x + 11, rect.y + 5 + 1))
        dc.DrawTextList(texts, xys,
                        foregrounds=wx.Colour(210, 210, 210), backgrounds=None)
        dc.DrawTextList(selected_texts, selected_xys,
                        foregrounds=wx.Colour(30, 30, 30), backgrounds=None)

    def DrawTabPolygon(self, dc):
        size = 6
        right_align = 10
        close_rects = list()
        for i, rect in enumerate(self.rects[1:]):
            offset_x = rect.x + rect.width - size - right_align
            # offset_y = (self.GetSize().height - size) * 0.5 - 1
            offset_y = rect.y + 8 + 1
            # print(offset_x, offset_y)
            # if self.tab_rel_width < 60 and i != self.parent.ListBox.selectedList:
            #     close_rects.append(wx.Rect(0, 0, 0, 0))
            #     continue
            # elif self.cache.tabIdx != i or i != self.parent.ListBox.selectedList:
            #     close_rects.append(wx.Rect(0, 0, 0, 0))
            #     continue
            # else:
            close_rects.append(wx.Rect(offset_x - 3, offset_y - 3, size + 6, size + 6))
            if i == self.parent.ListBox.selectedList:
                dc.DrawBitmap(self.bmp.close, offset_x, offset_y, useMask=True)
        self.close_rects = close_rects
        rect = self.rects[0]
        offset_x = rect.x + rect.width - size - right_align
        # offset_y = (self.GetSize().height - size) * 0.5 - 1
        offset_y = 8 + 1
        if self.IsTabCreationLimited() is False:
            dc.DrawBitmap(self.bmp.add, offset_x, offset_y, useMask=True)

    # Handle ListBoxTab Event

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        x, y = xy
        return self.GetTabRectIdx((x, y))

    def ExtendGlobalEvent(self, event):
        event.tabIdx = self.GetTabRectIdx((event.X, event.Y))
        event.down.tabIdx, event.drag.tabIdx = (None, None)
        event.closeIdx = self.GetTabCloseRectIdx((event.X, event.Y))
        event.down.closeIdx, event.drag.closeIdx = (None, None)
        if event.LeftDown or event.RightDown or event.MiddleDown:
            event.down.tabIdx = self.GetTabRectIdx((event.down.X, event.down.Y))
            event.down.closeIdx = self.GetTabCloseRectIdx((event.X, event.Y))
        if (event.LeftDown is False and event.LeftIsDown)\
                or (event.RightDown is False and event.RightIsDown)\
                or (event.MiddleDown is False and event.MiddleIsDown):
            event.down.tabIdx = self.cache.down.tabIdx
            event.down.closeIdx = self.cache.down.closeIdx
        if event.LeftDrag:
            event.drag.tabIdx = self.GetTabRectIdx((event.drag.X, event.drag.Y))
            event.drag.closeIdx = self.GetTabCloseRectIdx((event.X, event.Y))
        if event.LeftDrag is False and event.LeftIsDrag:
            event.drag.tabIdx = self.cache.drag.tabIdx
            event.drag.closeIdx = self.cache.drag.closeIdx
        if event.LeftUp or event.RightUp or event.MiddleUp:
            event.down.tabIdx = self.cache.down.tabIdx
            event.drag.tabIdx = self.cache.drag.tabIdx
            event.down.closeIdx = self.cache.down.closeIdx
            event.drag.closeIdx = self.cache.drag.closeIdx
        self.cache.down.tabIdx = event.down.tabIdx
        self.cache.drag.tabIdx = event.drag.tabIdx
        self.cache.down.closeIdx = event.down.closeIdx
        self.cache.drag.closeIdx = event.drag.closeIdx
        return event

    def CATCH_EVT_MOUSEWHEEL(self, event):

        if self.TextEdit is not None:
            self.TextEdit.CommitText()

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.HasToSkipEvent():
            return
        self.HandleEventTabAddDown(event)
        self.HandleEventTabCloseDown(event)
        self.HandleEventTabSelectDown(event)
        self.HandleEventTabShuffleDragPending(event)
        self.HandleEventTabShuffleDragFinalize(event)
        self.HandleEventTabDrag(event)
        self.HandleEventTabPopup(event)
        self.HandleEventTabAddPopup(event)
        self.HandleEventTabTextEditOff(event)
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.FileDrop.downTabIdx = None
            self.FileDrop.insertTabIdx = None

    def HandleEventTabTextEditOff(self, event):
        if self.TextEdit is None:
            return
        isInRect = self.IsInRect(self.TextEdit.GetRect(), (event.X, event.Y))
        if isInRect is False and (event.MiddleDown or event.RightDown):
            self.TextEdit.CommitText()
        if self.TextEdit.destroy:
            self.TextEdit.Destroy()
            self.TextEdit = None
            self.DirectDraw()

    def HandleEventTabTextEditOn(self, event):
        if event.LeftDClick is False:
            return
        if self.TextEdit is not None:
            return
        if event.tabIdx is None:
            return
        if event.tabIdx == -1:
            return
        self.TextEdit = TabTextEdit(self)
        x, y, w, h = self.rects[event.tabIdx]
        self.TextEdit.SetRect((x + 9, y + 6, w - 17, h - 10))
        title = self.parent.ListBox.GetTabsTitles()[event.tabIdx]
        self.TextEdit.SetValue(title)
        self.reInitBuffer = True

    def SetTabTextEditOn(self):
        tabIdx = self.text_edit_tabIdx
        self.TextEdit = TabTextEdit(self)
        x, y, w, h = self.rects[tabIdx]
        self.TextEdit.SetRect((x + 9, y + 6, w - 17, h - 10))
        title = self.GetTabsTitles()[tabIdx]
        self.TextEdit.SetValue(title)
        self.reInitBuffer = True

    def HandleEventTabPopup(self, event):
        if event.RightUp is False:
            return
        if event.rectIdx is None:
            return
        if event.tabIdx == -1:
            return
        if event.down.rectIdx is None:
            return
        if self.parent.ListBox.selectedList != event.tabIdx:
            return
        self.text_edit_tabIdx = event.tabIdx
        self.parent.SetPopupMenu(ListBoxPopupTab(self), (event.x, event.y))

    def HandleEventTabAddPopup(self, event):
        if event.RightUp is False:
            return
        if event.rectIdx is None:
            return
        if event.tabIdx != -1:
            return
        if event.down.rectIdx is None:
            return
        self.parent.SetPopupMenu(ListBoxPopupTabAdd(self), (event.x, event.y))

    def HandleEventTabDrag(self, event):
        if event.LeftUp:
            self.FileDrop.tabDrag = False
        if self.FileDrop.tabDrag:
            return
        if event.LeftDrag is False:
            return
        if event.drag.tabIdx == -1:
            return
        if event.drag.tabIdx is None:
            return
        if event.drag.closeIdx is not None:
            return
        self.FileDrop.tabDrag = True
        self.ExportPlayList(event.down.tabIdx)

        # self.parent.ListBox.List.FileDrop.dropTimer = 0
        # self.parent.ListBox.List.FileDrop.itemDrag = False
        # self.parent.ListBox.List.FileDrop.importing = False

    def ExportPlayList(self, selectedList=None):
        if selectedList is None:
            if hasattr(self, 'selectedList') is False:
                return
            selectedList = self.selectedList
        pathIdx = self.parent.ListBox.GetColumnKeyToIdx('path')
        paths = map(itemgetter(pathIdx),
                    self.parent.ListBox.innerList[selectedList].items)
        title = self.parent.ListBox.innerList[selectedList].title
        filename = os.path.sep.join([get_user_docapp_path(), '%s.m3u' % (title)])
        audio.generate_m3u(filename, paths)
        filename = os.path.abspath(filename)
        self.parent.SetItemDrag((filename,), del_source=True)

    def HandleEventTabShuffleDragPending(self, event):
        if event.drag.tabIdx == -1:
            return
        if event.drag.tabIdx is None:
            return
        if event.drag.closeIdx is not None:
            return
        if event.drag.tabIdx == event.tabIdx:
            return
        self.FileDrop.downTabIdx = event.drag.tabIdx
        if len(self.parent.ListBox.innerList) == 1:
            return
        self.FileDrop.insertTabIdx = self.GetInsertTabRectIdx(event.Y)
        self.DirectDraw()

    def HandleEventTabShuffleDragFinalize(self, event):
        # if event.LeftUpDelayed is False: return
        if event.LeftUp is False:
            return
        if event.drag.tabIdx == -1:
            return
        if event.drag.tabIdx is None:
            return
        if event.drag.closeIdx is not None:
            return
        if self.FileDrop.downTabIdx is None:
            return
        if self.FileDrop.insertTabIdx is None:
            return
        fromIdx = self.FileDrop.downTabIdx
        toIdx = self.FileDrop.insertTabIdx
        self.FileDrop.downTabIdx = None
        self.FileDrop.insertTabIdx = None
        self.SetTabShuffle(fromIdx, toIdx)
        self.reInitBuffer = True

    def HandleEventTabAddDown(self, event):
        if event.tabIdx != -1:
            return
        if event.LeftUp is False:
            return
        if event.down.tabIdx != -1:
            return
        if self.IsTabCreationLimited():
            return
        self.parent.ListBox.AddInnerList()
        self.parent.ListBox.Header.SetAutoColumnWidth()
        self.reInitBuffer = True

    def HandleEventTabCloseDown(self, event):
        if self.cache.tabIdx != event.tabIdx:
            self.cache.tabIdx = event.tabIdx
            self.reInitBuffer = True
        if event.LeftUp is False:
            return
        if event.closeIdx is None:
            return
        if event.down.closeIdx is None:
            return
        self.parent.ListBox.DeleteInnerList(event.down.closeIdx)
        self.reInitBuffer = True

    def HandleEventTabSelectDown(self, event):
        if event.tabIdx == -1:
            return
        if event.tabIdx is None:
            return
        if event.closeIdx is not None:
            return
        if event.LeftDown is False:
            return
        self.parent.ListBox.SetSelectedList(event.tabIdx)
        # self.reInitBuffer = True
        self.parent.DirectDraw()
        self.DirectDraw()

    # Tab Control

    def SetTabShuffle(self, fromIdx, toIdx):
        if toIdx < fromIdx:
            self.parent.ListBox.innerList.insert(
                toIdx, self.parent.ListBox.innerList.pop(fromIdx))
            self.parent.ListBox.SetSelectedList(toIdx)
        elif toIdx > fromIdx:
            self.parent.ListBox.innerList.insert(
                toIdx - 1, self.parent.ListBox.innerList.pop(fromIdx))
            self.parent.ListBox.SetSelectedList(toIdx - 1)

    def SetTabTitle(self, title, selectedList=None):
        if selectedList is None:
            selectedList = self.parent.ListBox.selectedList
        self.parent.ListBox.SetListTitle(title, selectedList)

    def GetTabTitle(self, selectedList=None):
        if selectedList is None:
            selectedList = self.parent.ListBox.selectedList
        self.parent.ListBox.innerList[selectedList].title

    def GetTabsTitles(self):
        titles = list()
        for i in range(len(self.parent.ListBox.innerList)):
            titles.append(self.parent.ListBox.innerList[i].title)
        return titles

    def GetTabRectIdx(self, xy):
        x, y = xy
        if self.onClient is False:
            return None
        xy = wx.Point(x, y)
        # add_button_size = self.rects[0].height

        add_button = wx.Rect((
            self.close_rects[0].x,
            self.close_rects[0].y - self.rects[0].height,
            self.close_rects[0].width,
            self.close_rects[0].height,
        ))

        if self.IsInRect(add_button, xy):
            return -1
        for i, rect in enumerate(self.rects[1:]):
            if self.IsInRect(rect, xy):
                return i
        return None

    def GetInsertTabRectIdx(self, y):
        if self.onClient is False:
            return None
        # xy = wx.Point(x, 0.5 * self.GetSize().height)
        xy = wx.Point(1, y)
        for i, r in enumerate(self.rects[1:]):
            y = r.y - r.height * 0.5
            height = r.height
            if i == 0:
                y = 0
                height = r.y + r.height * 0.5
            # if i == len(self.rects[1:]) - 1:
            #     height = self.GetSize().height - r.y + r.height * 0.5
                # print(height)
            rect = wx.Rect(r.x, y, r.width, height)
            if self.IsInRect(rect, xy):
                return i
        return i + 1
        # x = self.rects[-1].x - self.rects[-2].width * 0.5
        # width = self.GetSize().width - x
        # rect = wx.Rect(x, r.y, width, r.height)
        # if self.IsInRect(rect, xy):
        #     return i + 1
        # return None

    def GetTabCloseRectIdx(self, xy):
        if self.onClient is False:
            return None
        x, y = xy
        for i, rect in enumerate(self.close_rects):
            if self.IsInRect(rect, xy):
                return i
        return None

    def OnSize(self, event=None):
        self.DirectDraw()


class ListBoxSliderV(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.pending = Struct(drag_vpy=None)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.DrawSliderV(dc)

    def DrawSliderV(self, dc):
        width, height = self.GetSize()
        slider = wx.Rect(0, 0, width, height)
        btnup = wx.Rect(0, 0, width, width)
        btndown = wx.Rect(0, height - width, width, width)
        slidable = wx.Rect(0, width, width, height - width * 2)
        length = self.parent.GetItemsLength() * self.parent.GetRowsHeight()
        if length != 0:
            shownRatio = 1.0 * self.parent.List.GetSize().height / length
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        h = slidable.height * shownRatio
        if h < width:
            h = 1.0 * width
        div = length - self.parent.List.GetSize().height
        if div != 0:
            posCYRatio = 1.0 * (-self.parent.GetVirtualPositionY()) / div
        else:
            posCYRatio = 1.0
        if posCYRatio > 1.0:
            posCYRatio = 1.0
            self.parent.innerList[self.parent.selectedList].rects.offset.y = -div
        x = slidable.x
        y = slidable.y + math.ceil((slidable.height - h) * posCYRatio)
        knob = wx.Rect(x, y, width, h)
        self.rects = Struct(slider=slider, slidable=slidable,
                            knob=knob, btnup=btnup, btndown=btndown)

        bgcolor = self.parent.st.SCROLLBAR_BG_COLOR
        fgcolor = self.parent.st.SCROLLBAR_FG_COLOR
        bdcolor = self.parent.st.SCROLLBAR_PN_COLOR
        dc.DrawRectangleList((slidable,),
                             pens=wx.Pen(bgcolor, 1), brushes=wx.Brush(bgcolor))
        lines = ((slidable.x + 1, slidable.y, slidable.x + width - 1, slidable.y),
                 (slidable.x + 1, slidable.height + width - 1, slidable.x + width - 1, slidable.height + width - 1))
        dc.DrawLineList(lines, pens=wx.Pen(bgcolor, 1))
        dc.DrawRectangleList((knob, btnup, btndown),
                             pens=wx.Pen(bdcolor, 1), brushes=wx.Brush(fgcolor))

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        if self.IsInRect(self.rects.btnup, xy):
            return 5
        elif self.IsInRect(self.rects.btndown, xy):
            return 4
        elif self.IsInRect(self.rects.knob, xy):
            return 3
        elif self.IsInRect(self.rects.slidable, xy):
            return 2
        return 1

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleSliderVKnobDrag(event)
        self.HandleSliderVButtonDown(event)
        self.HandleSliderVSlidableDown(event)
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.pending.drag_vpy = None

    def HandleSliderVButtonDown(self, event):
        if event.rectIdx == 5 and event.down.rectIdx == 5:
            self.parent.ScrollV(0.2)
        elif event.rectIdx == 4 and event.down.rectIdx == 4:
            self.parent.ScrollV(-0.2)

    def HandleSliderVKnobDrag(self, event):
        if event.down.rectIdx == 2:
            return
        if event.drag.rectIdx != 3:
            return
        rect = self.rects
        initPosY = event.drag.Y - rect.slidable.y
        if event.drag.rectIdx == 3 and self.pending.drag_vpy is None:
            self.pending.drag_vpy = self.parent.GetVirtualPositionY()
        length = self.parent.GetItemsLength() * self.parent.GetRowsHeight()
        list_height = self.parent.List.GetSize().height
        if length != 0:
            shownRatio = 1.0 * list_height / length
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        slidable = rect.slidable.height - rect.knob.height
        if slidable == 0:
            return
        diff = event.Y - initPosY - rect.slidable.y
        if self.pending.drag_vpy is None:
            return
        diffRatio = 1.0 * diff * (length - list_height) / slidable
        vpy = self.pending.drag_vpy - diffRatio
        self.parent.SetVirtualPositionY(vpy)

    def HandleSliderVSlidableDown(self, event):
        if event.LeftDown is False:
            return
        if event.down.rectIdx != 2:
            return
        rect = self.rects
        slidable = rect.slidable.height - rect.knob.height
        if slidable != 0:
            posCYRatio = 1.0\
                * (event.Y - rect.slidable.y - rect.knob.height * 0.5) / slidable
        else:
            posCYRatio = 1.0
        vpy_limit = self.parent.GetVirtualPositionYLimit()
        vpy = int(posCYRatio * vpy_limit)
        self.parent.SetVirtualPositionY(vpy)

    def CATCH_EVT_MOUSEWHEEL(self, event):

        if self.onClient is False:
            return
        self.parent.ScrollV(event.WheelRotation / 40)

    def OnSize(self, event=None):
        self.DirectDraw()


class ListBoxSliderH(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.pending = Struct(drag_vpx=None)
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.DrawSliderH(dc)

    def DrawSliderH(self, dc):
        width, height = self.GetSize()
        slider = wx.Rect(0, 0, width, height)
        btnleft = wx.Rect(0, 0, height, height)
        btnright = wx.Rect(width - height, 0, height, height)
        slidable = wx.Rect(height, 0, width - height * 2, height)
        length = self.parent.GetVirtualPositionXW()\
            - self.parent.GetVirtualPositionX()
        if length != 0:
            shownRatio = 1.0 * self.parent.List.GetSize().width / length
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        w = slidable.width * shownRatio
        if w < height:
            w = 1.0 * height
        div = length - self.parent.List.GetSize().width
        if div != 0:
            posCXRatio = 1.0 * (-self.parent.GetVirtualPositionX()) / div
        else:
            posCXRatio = 1.0
        if posCXRatio > 1.0:
            posCXRatio = 1.0
        x = slidable.x + math.ceil((slidable.width - w) * posCXRatio)
        y = slidable.y
        knob = wx.Rect(x, y, w, height)
        self.rects = Struct(slider=slider, slidable=slidable, knob=knob,
                            btnleft=btnleft, btnright=btnright)

        bgcolor = self.parent.st.SCROLLBAR_BG_COLOR
        fgcolor = self.parent.st.SCROLLBAR_FG_COLOR
        bdcolor = self.parent.st.SCROLLBAR_PN_COLOR
        dc.DrawRectangleList((slidable,),
                             pens=wx.Pen(bgcolor, 1), brushes=wx.Brush(bgcolor))
        lines = ((slidable.x, slidable.y + 1, slidable.x, slidable.y + height - 1),
                 (slidable.width + height - 1, slidable.y + 1, slidable.width + height - 1, slidable.y + height - 1))
        dc.DrawLineList(lines, pens=wx.Pen(bgcolor, 1))
        dc.DrawRectangleList((knob, btnleft, btnright),
                             pens=wx.Pen(bdcolor, 1), brushes=wx.Brush(fgcolor))

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        if self.IsInRect(self.rects.btnleft, xy):
            return 5
        elif self.IsInRect(self.rects.btnright, xy):
            return 4
        elif self.IsInRect(self.rects.knob, xy):
            return 3
        elif self.IsInRect(self.rects.slidable, xy):
            return 2
        return 1

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleSliderHKnobDrag(event)
        self.HandleSliderHButtonDown(event)
        self.HandleSliderHSlidableDown(event)
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.pending.drag_vpx = None

    def HandleSliderHButtonDown(self, event):
        if event.rectIdx == 5 and event.down.rectIdx == 5:
            self.parent.ScrollH(1)
        elif event.rectIdx == 4 and event.down.rectIdx == 4:
            self.parent.ScrollH(-1)

    def HandleSliderHSlidableDown(self, event):
        if event.LeftDown is False:
            return
        if event.down.rectIdx != 2:
            return
        rect = self.rects
        slidable = rect.slidable.width - rect.knob.width
        if slidable != 0:
            posCXRatio = 1.0 * (event.X - rect.slidable.x - rect.knob.width * 0.5) / slidable
        else:
            posCXRatio = 1.0
        vpx_limit = self.parent.GetVirtualPositionXLimit()
        vpx = int(posCXRatio * vpx_limit)
        self.parent.SetVirtualPositionX(vpx)

    def HandleSliderHKnobDrag(self, event):
        if event.down.rectIdx == 2:
            return
        if event.drag.rectIdx != 3:
            return
        rect = self.rects
        initPosX = event.drag.X - rect.slidable.x
        if event.drag.rectIdx == 3 and self.pending.drag_vpx is None:
            self.pending.drag_vpx = self.parent.GetVirtualPositionX()
        length = self.parent.GetShownColumnsWidth()
        list_width = self.parent.List.GetSize().width
        if length != 0:
            shownRatio = 1.0 * list_width / length
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        slidable = rect.slidable.width - rect.knob.width
        if slidable == 0:
            return
        diff = event.X - initPosX - rect.slidable.x
        if self.pending.drag_vpx is None:
            return
        diffRatio = 1.0 * diff * (length - list_width) / slidable
        vpx = self.pending.drag_vpx - diffRatio
        self.parent.SetVirtualPositionX(vpx)

    def CATCH_EVT_MOUSEWHEEL(self, event):

        if self.onClient is False:
            return
        self.parent.ScrollV(event.WheelRotation / 40)

    def OnSize(self, event=None):
        self.DirectDraw()


# http://www.blog.pythonlibrary.org/2011/02/10/
# wxpython-showing-2-filetypes-in-wx-filedialog/

class FileOpenDialog(wx.FileDialog):

    def __init__(self, parent):
        self.parent = parent
        message = 'Import Tracks'
        defaultDir = os.path.expanduser(u'~')
        defaultDir = os.path.dirname(defaultDir)
        wildcard = [u'*.%s' % (v) for v in SUPPORTED_PLAYLIST_TYPE]
        wildcard += [u'*.%s' % (v) for v in SUPPORTED_AUDIO_TYPE]
        wildcard = u';'.join(wildcard)
        wx.FileDialog.__init__(self, parent,
                               defaultDir=defaultDir, message=message, wildcard=wildcard,
                               style=wx.FD_OPEN | wx.FD_MULTIPLE | wx.FD_CHANGE_DIR)


class FileSaveDialog(wx.FileDialog):

    def __init__(self, parent):
        self.parent = parent
        message = 'Export Tracklist'
        defaultDir = os.path.expanduser(u'~')
        defaultDir = os.path.dirname(defaultDir)
        wildcard = [u'*.%s' % (v) for v in SUPPORTED_PLAYLIST_TYPE]
        wildcard = u';'.join(wildcard)
        wx.FileDialog.__init__(self, parent,
                               defaultDir=defaultDir, message=message, wildcard=wildcard,
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT | wx.FD_CHANGE_DIR)
        filename = self.parent.parent.ListBox.GetListTitle()
        self.SetFilename(filename)


class TabRenameBox(UserInputDialogBox):

    def __init__(self, parent):
        UserInputDialogBox.__init__(self, parent)
        self.parent = parent
        self.SetTitle('Tab Rename')
        self.tab_idx = self.parent.parent.ListBox.selectedList
        self.tab_title = self.parent.parent.ListBox.GetListTitle(self.tab_idx)
        # string = self.UserInput.SetValue(self.tab_title)
        self.ApplyButton.SetLabelText('Rename')

    def OnApply(self, event):
        string = self.UserInput.GetValue()
        self.parent.parent.ListBox.SetListTitle(string, self.tab_idx)
        self.OnClose(None)


class ItemEditPanel(DialogPanel):

    def __init__(self, parent, pos=(0, 0)):
        DialogPanel.__init__(self, parent)
        self.Show(False)
        self.parent = parent
        x, y = pos
        width, height = self.parent.GetSize()
        self.SetRect((x, y, width, 247))
        self.labels = ('Path', 'Filename', 'Duration', 'Size', 'Bitrate',
                       'Channel', 'Artist', 'Title', 'Album', 'Genre', 'Key', 'Tempo')
        self.disables = ('Duration', 'Type', 'Size', 'Bitrate', 'Channel', 'Path')

    def SetPage(self, item_idx):
        if hasattr(self, 'TextCtrls') is False:
            self.InitTextCtrls()
        self.restore_value = list()
        for i, v in enumerate(self.labels):
            columnKey = v.lower()
            value = self.parent.parent.parent.GetItemValueByColumnKey(item_idx, columnKey)
            # if type(value) == str:
            # if isinstance(value, str):
            #     value = value.decode(sys.getfilesystemencoding())
            # if type(value) in (int, float, long):
            if isinstance(value, int) or isinstance(value, float):
                value = str(value)
            self.TextCtrls[i].SetValue(value)
            self.restore_value.append(value)
            if columnKey == 'path':
                value = os.path.dirname(value)
            if isinstance(value, str):
                # value = value.decode(sys.getfilesystemencoding())
                self.TextCtrls[i].SetValue(value)
            if v in self.disables:
                self.TextCtrls[i].Disable()
        self.Refresh()

    def InitTextCtrls(self):
        width, height = self.GetClientSize()
        posX = 76
        posY = 25
        twh = (50, 20)
        self.TextCtrls = list()
        self.StaticTexts = list()

        self.StaticTexts += [StaticText(self, label=self.labels[0],
                                        pos=(15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX, posY - 5 + 1), size=(width - posX - 24, 22))]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[1],
                                        pos=(15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX, posY - 5 + 1), size=(width - posX - 24, 22))]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[2],
                                        pos=(15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX, posY - 5 + 1), size=(65, 22), style=wx.ALIGN_RIGHT)]

        self.StaticTexts += [StaticText(self, label=self.labels[3],
                                        pos=(15 + 145, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX + 145, posY - 5 + 1), size=(65, 22), style=wx.ALIGN_RIGHT)]

        self.StaticTexts += [StaticText(self, label=self.labels[4],
                                        pos=(15 + 300 - 10, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX + 300 - 10, posY - 5 + 1), size=(65, 22), style=wx.ALIGN_RIGHT)]

        self.StaticTexts += [StaticText(self, label=self.labels[5],
                                        pos=(15 + 300 - 10 + 145, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX + 300 - 10 + 145, posY - 5 + 1), size=(65, 22), style=wx.ALIGN_RIGHT)]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[6],
                                        pos=(15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX, posY - 5 + 1), size=(width - posX - 24, 22))]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[7],
                                        pos=(15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX, posY - 5 + 1), size=(width - posX - 24, 22))]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[8],
                                        pos=(15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self,
                                    pos=(posX, posY - 5 + 1), size=(width - posX - 24, 22))]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[9],
                                        pos=(15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(posX, posY - 5 + 1), size=(210, 22))]

        self.StaticTexts += [
            StaticText(self, label=self.labels[10], pos=(15 + 300 - 10, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(posX + 300 - 10, posY - 5 + 1), size=(65, 22))]

        self.StaticTexts += [StaticText(
            self, label=self.labels[11], pos=(15 + 300 - 10 + 145, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(
            self, pos=(posX + 300 - 10 + 145, posY - 5 + 1), size=(65, 22), style=wx.ALIGN_RIGHT)]

    def OnClose(self, event):
        self.Destroy()


class ItemEditBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(600, 310))
        self.parent = parent
        self.auto_save = True
        self.SetTitle('Track Information Editor')
        self.selectedList = self.parent.parent.selectedList
        self.selectedItems = self.parent.parent.GetSelectedItems()
        self.total_items = len(self.selectedItems)
        self.selected_idx = 0
        width, height = self.GetClientSize()
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        w, h = self.CloseButton.GetSize()
        height -= h + 15
        self.CloseButton.SetPosition((width - 95 + 3, height))
        self.NextButton = Button(self, label='Next')
        self.NextButton.SetPosition((width - 95 - 80 + 3, height))
        self.NextButton.Bind(wx.EVT_BUTTON, self.OnNext)
        self.PrevButton = Button(self, label='Prev')
        self.PrevButton.Bind(wx.EVT_BUTTON, self.OnPrev)
        self.PrevButton.SetPosition((width - 95 - 80 * 2 + 3, height))
        self.ItemEditPanel = ItemEditPanel(self)
        self.ItemEditPanel.SetPage(self.selectedItems[self.selected_idx])
        label = '%d / %d' % (self.selected_idx + 1, self.total_items)
        self.PageNumber = StaticText(self, label=label,
                                     pos=(width - 95 - 160 - 120, height + 5),
                                     size=(80, 20), style=wx.ALIGN_RIGHT)
        self.AutoSeButtonState()
        self.ItemEditPanel.Show(True)

    def OnAutoSave(self, event):
        if event.IsChecked():
            self.auto_save = True
            self.SaveButton.Disable()
            SetPreference('item_editor_auto_save', True)
        else:
            self.auto_save = False
            self.SaveButton.Enable()
            SetPreference('item_editor_auto_save', False)
        self.parent.parent.parent.parent.item_editor_auto_save = self.auto_save

    def AutoSeButtonState(self):
        if self.selected_idx == 0:
            self.PrevButton.Disable()
        else:
            self.PrevButton.Enable()
        if self.selected_idx == self.total_items - 1:
            self.NextButton.Disable()
        else:
            self.NextButton.Enable()

    def CommitText(self):
        itemIdx = self.selectedItems[self.selected_idx]
        if self.columnIdx == self.parent.parent.GetColumnKeyToIdx('filename'):
            self.RenameFile()
        if self.parent.parent.IsID3TAGColumnByColumnIdx(self.columnIdx):
            self.RenameID3TAG()
        newValue = self.GetValue()
        columnKey = self.parent.parent.GetColumnIdxToKey(self.columnIdx)
        if columnKey == 'tempo':
            try:
                newValue = float(newValue)
                newValue = u'%05.1f' % (0.1 * round(newValue * 10))
            except Exception:
                newValue = ''
        self.parent.parent.SetItemValueByColumnIdx(itemIdx, self.columnIdx, newValue)

    def RenameID3TAG(self):
        newValue = self.GetValue()
        resp = self.parent.parent.RenameID3TAGByColumnItemIdx(
            self.columnIdx, self.selectedItems[self.selected_idx], newValue)
        if resp is False:
            self.SetValue(self.restore_value)

    def RenameFile(self):
        itemIdx = self.selectedItems[self.selected_idx]
        newFilename = self.GetValue()
        newFilename = self.parent.parent.LimitFileName(newFilename)
        oldPath = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
        pathBase = os.path.sep.join(oldPath.split(os.path.sep)[:-1])
        fileType = os.path.splitext(oldPath)[-1]
        newPath = os.path.sep.join([pathBase, newFilename])
        newPath = ''.join([newPath, fileType])
        resp = self.parent.parent.RenameFileByItemIdx(itemIdx, newPath)
        if resp is False:
            self.SetValue(self.restore_value)

    def OnSave(self, event):
        itemIdx = self.selectedItems[self.selected_idx]
        is_playing_item = False
        if self.parent.parent.parent.PlayBox.IsPlaying():
            path = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
            if path == self.parent.parent.parent.PlayBox.GetPlayingItemInfo('path'):
                is_playing_item = True
                self.parent.parent.parent.PlayBox.OnPause()
                # resume = self.parent.parent.parent.PlayBox.cue.resume

        for i, v in enumerate(self.ItemEditPanel.labels):
            if v in self.ItemEditPanel.disables:
                continue
            columnIdx = self.parent.parent.GetColumnKeyToIdx(v.lower())
            if v.lower() == 'filename':
                newFilename = self.ItemEditPanel.TextCtrls[i].GetValue()
                newFilename = self.parent.parent.LimitFileName(newFilename)
                oldPath = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
                pathBase = os.path.sep.join(oldPath.split(os.path.sep)[:-1])
                fileType = os.path.splitext(oldPath)[-1]
                newPath = os.path.sep.join([pathBase, newFilename])
                newPath = ''.join([newPath, fileType])
                if oldPath != newPath:
                    path_resp = self.parent.parent.RenameFileByItemIdx(itemIdx, newPath)
                    if path_resp is False:
                        self.ItemEditPanel.TextCtrls[i].SetValue(self.ItemEditPanel.restore_value[i])
                else:
                    path_resp = True
            elif self.parent.parent.IsID3TAGColumnByColumnIdx(columnIdx):
                newValue = self.ItemEditPanel.TextCtrls[i].GetValue()
                oldValue = self.ItemEditPanel.restore_value[i]
                # if type(oldValue) != unicode:
                #     oldValue = oldValue.decode(sys.getfilesystemencoding())
                if newValue == oldValue:
                    continue
                if v.lower() == 'tempo':
                    try:
                        newValue = float(newValue)
                        newValue = u'%05.1f' % (0.1 * round(newValue * 10))
                    except Exception:
                        newValue = ''
                tag_resp = self.parent.parent.RenameID3TAGByColumnItemIdx(columnIdx, itemIdx, newValue)
                if tag_resp is False:
                    self.ItemEditPanel.TextCtrls[i].SetValue(self.ItemEditPanel.restore_value[i])

        if is_playing_item:
            if path_resp:
                self.parent.parent.parent.PlayBox.cue.path = newPath
                self.parent.parent.parent.PlayBox.cue.mdx\
                    = self.parent.parent.parent.PlayBox.GetMDX(newPath)
                self.parent.parent.parent.PlayBox.cue.item\
                    = MakeMusicFileItem(newPath, 0, ListBoxColumn())
            self.parent.parent.parent.PlayBox.OnResume()
        self.SetPage()
        self.parent.parent.List.DirectDraw()

    def OnPrev(self, event):
        if self.auto_save:
            self.OnSave(None)
        self.selected_idx -= 1
        if self.selected_idx < 0:
            self.selected_idx = 0
            return
        self.SetPage()

    def OnNext(self, event):
        if self.auto_save:
            self.OnSave(None)
        self.selected_idx += 1
        if self.selected_idx > self.total_items - 1:
            self.selected_idx = self.total_items - 1
            return
        self.SetPage()

    def SetPage(self):
        self.Freeze()
        self.AutoSeButtonState()
        self.ItemEditPanel.SetPage(self.selectedItems[self.selected_idx])
        label = '%d / %d' % (self.selected_idx + 1, self.total_items)
        size = self.PageNumber.GetSize()
        self.PageNumber.SetLabelText(label)
        self.PageNumber.SetInitialSize(size)
        self.Thaw()

    def OnClose(self, event):
        if self.auto_save:
            self.OnSave(None)
        self.EndModal(0)
        self.Destroy()


class ListBoxPopupSearch(wx.Menu):

    def __init__(self, parent):
        wx.Menu.__init__(self)
        self.parent = parent
        self.items = ['Filename', 'Type', 'Artist', 'Title', 'Album', 'Genre', 'Path']
        for i, item in enumerate(self.items):
            menuitem = wx.MenuItem(self, i + 1, item, wx.EmptyString, wx.ITEM_CHECK)
            self.Append(menuitem)
            menuitem.Destroy()
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[i])
            if self.parent.parent.ListSearch.query_columnKey == item.lower():
                self.MenuItems[i].Check()

    def OnCheck(self, event):
        query_columnKey = self.items[event.Id - 1].lower()
        value = self.parent.parent.ListSearch.SearchText.GetValue()
        self.parent.parent.ListSearch.query_columnKey = query_columnKey
        if value == '':
            return
        self.parent.parent.ListBox.FilterItemsAll(query_columnKey, value)


class ListBoxPopupTabAdd(wx.Menu):

    def __init__(self, parent):
        wx.Menu.__init__(self)
        self.parent = parent
        self.items = ['Create Playlist']
        for i, item in enumerate(self.items):
            if item == '':
                self.AppendSeparator()
                continue
            self.Append(wx.MenuItem(self, i + 1, item, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[i])

    def OnCheck(self, event):
        if event.GetId() == 1:
            self.parent.parent.ListBox.AddInnerList()
            self.parent.parent.ListBox.Header.SetAutoColumnWidth()


class ListBoxPopupTab(wx.Menu):

    def __init__(self, parent):
        wx.Menu.__init__(self)
        self.parent = parent
        if self.parent.parent.ListBox.IsFilteredAll():
            self.items = ['Rename', '', 'Close Playlist']
        else:
            self.items = ['Rename', '', 'Close Playlist', 'Import Tracks', 'Export Playlist']
        for i, item in enumerate(self.items):
            if item == '':
                self.AppendSeparator()
                continue
            self.Append(wx.MenuItem(self, i + 1, item, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[i])

    def OnCheck(self, event):
        if event.GetId() == 1:
            self.parent.parent.DialogBox = TabRenameBox(self.parent)
            x, y, w, h = self.parent.parent.parent.GetRect()
            width, height = self.parent.parent.DialogBox.GetSize()
            self.parent.parent.DialogBox.SetRect(
                (x + (w - width) / 2, y + (h - height) / 2, width, height))
            self.parent.parent.DialogBox.ShowModal()
            self.parent.parent.DialogBox.Destroy()
            self.parent.parent.DialogBox = None
            self.parent.DirectDraw()
        if event.GetId() == 3:
            selectedList = self.parent.parent.ListBox.selectedList
            self.parent.parent.ListBox.DeleteInnerList(selectedList)
            # self.parent.parent.ListTab.SetTabTextEditOn()
        if event.GetId() == 4:
            cwd = os.getcwd()
            self.parent.parent.DialogBox = FileOpenDialog(self.parent)
            x, y, w, h = self.parent.parent.parent.GetRect()
            # self.parent.parent.DialogBox.SetSize((1024,800))
            width, height = self.parent.parent.DialogBox.GetSize()
            self.parent.parent.DialogBox.SetRect(
                (x + (w - width) / 2, y + (h - height) / 2, width, height))
            self.parent.parent.DialogBox.ShowModal()
            os.chdir(cwd)  # only works with windows, linux
            paths = self.parent.parent.DialogBox.GetPaths()
            self.parent.parent.ListBox.List.FileDrop.DropFromOutside(paths)
            self.parent.parent.DialogBox.Destroy()
            self.parent.parent.DialogBox = None
        if event.GetId() == 5:
            cwd = os.getcwd()
            self.parent.parent.DialogBox = FileSaveDialog(self.parent)
            self.parent.parent.DialogBox.ShowModal()
            os.chdir(cwd)  # only works with windows, linux
            savepath = self.parent.parent.DialogBox.GetPath()
            self.parent.parent.DialogBox.Destroy()
            self.parent.parent.DialogBox = None
            selectedList = self.parent.parent.ListBox.selectedList
            pathIdx = self.parent.parent.ListBox.GetColumnKeyToIdx('path', selectedList)
            paths = map(itemgetter(pathIdx),
                        self.parent.parent.ListBox.innerList[selectedList].items)
            try:
                audio.generate_m3u(savepath, paths)
            except Exception:
                pass


class ListBoxPopupHeader(wx.Menu):

    def __init__(self, parent):
        wx.Menu.__init__(self)
        self.parent = parent
        self.columns = list()
        for i, v in enumerate(self.parent.parent.GetColumns()):
            if v.private:
                continue
            self.Append(wx.MenuItem(self, i + 1, v.title, wx.EmptyString, wx.ITEM_CHECK))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[i])
            if v.show is True:
                self.MenuItems[i].Check()
            self.columns.append(Struct(idx=i + 1, key=v.key))
        self.AppendSeparator()
        self.idx = i + 1
        self.Append(wx.MenuItem(self, self.idx, 'Set as default', wx.EmptyString, wx.ITEM_CHECK))
        self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[self.idx])
        self.Append(wx.MenuItem(self, self.idx + 1, 'Apply to all tab', wx.EmptyString, wx.ITEM_CHECK))
        self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[self.idx + 1])

    def OnCheck(self, event):
        v = [v for v in self.parent.parent.GetColumns()
             if v.show is True and v.private is False]
        if len(v) == 1 and event.IsChecked() is False:
            return
        idx = [v.idx for v in self.columns if v.idx == event.Id]
        if len(idx) != 0:
            self.parent.parent.SetColumn(event.Id - 1, show=event.IsChecked())
        if event.Id == self.idx:
            columns = self.parent.parent.GetColumns()
            SetPreference('columns', columns)
        if event.Id == self.idx + 1:
            self.parent.parent.CloneColumnsDefinitionToAll()
        self.parent.DirectDraw()


class OpenWebLinkHandler():

    def __init__(self, parent):
        self.parent = parent
        self.weblink_preset = self.parent.parent.parent.parent.WebLinkPreset.preset
        self.weblink_preset = [v for v in self.weblink_preset if v[0] != '' and v[1] != '']
        self.weblink_preset = [v for v in self.weblink_preset if v[2] != '' or v[3] != '']

    def OnWebLink(self, event=None, idx=None):
        if event is not None:
            idx = event.GetId() - 121
            parents = 'self.parent.parent'
        else:
            parents = 'self.parent.parent'
        preset = self.weblink_preset[idx]
        query_url = preset[1]
        field1 = preset[2].lower()
        field2 = preset[3].lower()
        if field1 != '':
            # exec('field1 = %s.GetSelectedItemsKeyValue(field1)[0]' % (parents))
            field1 = eval('%s.GetSelectedItemsKeyValue(field1)[0]' % (parents))
        if field2 != '':
            # exec('field2 = %s.GetSelectedItemsKeyValue(field2)[0]' % (parents))
            field2 = eval('%s.GetSelectedItemsKeyValue(field2)[0]' % (parents))
        fields = '+'.join((field1, field2)).strip('+')
        if len(fields) < 3:
            # exec('filename = %s.GetSelectedItemsKeyValue("filename")[0]' % (parents))
            filename = eval('%s.GetSelectedItemsKeyValue("filename")[0]' % (parents))
            for srp in '_|-|(|)|[|]|{|}|&'.split('|'):
                filename = filename.replace(srp, ' ')
                filename = filename.replace('  ', ' ')
            fields = '+'.join((fields, filename)).strip('+')
        fields.strip()
        fields = fields.replace(' ', '+')
        url = query_url + fields
        webbrowser.open(url)


class ListBoxPopupItem(wx.Menu, OpenWebLinkHandler):

    def __init__(self, parent):
        wx.Menu.__init__(self)
        OpenWebLinkHandler.__init__(self, parent)
        self.parent = parent
        if self.parent.parent.GetSelectedItemsLength() == 1:
            single = True
        else:
            single = False

        if single:
            idx = 1
            name = 'Play'
            self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        idx = 2
        name = 'Edit'
        self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        # WebLink

        # if single:
        #   self.AppendSeparator()
        #   idx = 120;
        #   self.itemWebLink = wx.Menu()
        #   for ps in self.weblink_preset:
        #       idx += 1
        #       fields = ' + '.join((ps[2], ps[3])).strip(' + ')
        #       name = '\t'.join((ps[0], fields))
        #       menuitem = wx.MenuItem(self.itemWebLink,\
        #           idx, name, wx.EmptyString, wx.ITEM_NORMAL)
        #       self.itemWebLink.Append(menuitem)
        #       self.Bind(wx.EVT_MENU, self.OnWebLink, menuitem)
        #       menuitem.Destroy()
        #   idx = 7; name = 'Web Link'
        #   self.AppendMenu(idx, name, self.itemWebLink)

        self.AppendSeparator()

        idx = 3
        name = 'Delete'
        self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        idx = 4
        name = 'Analyze'
        self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        if single:
            idx = 5
            name = 'Open Containing Folder'
            self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        self.AppendSeparator()

        # ConvertTempoRange

        self.itemConvertTempoRange = wx.Menu()

        idx = 101
        name = 'Convert to Up Tempo (95bpm~)'
        self.itemConvertTempoRange.Append(wx.MenuItem(
            self.itemConvertTempoRange, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheckConvertTempoRange, self.itemConvertTempoRange.MenuItems[0])

        idx = 102
        name = 'Convert to Down Tempo (~120bpm)'
        self.itemConvertTempoRange.Append(wx.MenuItem(
            self.itemConvertTempoRange, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheckConvertTempoRange, self.itemConvertTempoRange.MenuItems[1])

        idx = 8
        name = 'Convert Tempo Range'
        self.Append(idx, name, self.itemConvertTempoRange)

        # ConvertKeyFormat

        self.itemConvertKeyFormat = wx.Menu()

        idx = 111
        name = 'Convert Key Format to Flat (Dbm)'
        self.itemConvertKeyFormat.Append(wx.MenuItem(
            self.itemConvertKeyFormat, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheckConvertKeyFormat, self.itemConvertKeyFormat.MenuItems[0])

        idx = 112
        name = 'Convert Key Format to Sharp (C#m)'
        self.itemConvertKeyFormat.Append(wx.MenuItem(
            self.itemConvertKeyFormat, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheckConvertKeyFormat, self.itemConvertKeyFormat.MenuItems[1])

        idx = 113
        name = 'Convert Key Format to Camelot (12A)'
        self.itemConvertKeyFormat.Append(wx.MenuItem(
            self.itemConvertKeyFormat, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheckConvertKeyFormat, self.itemConvertKeyFormat.MenuItems[2])

        idx = 9
        name = 'Convert Key Format'
        self.Append(idx, name, self.itemConvertKeyFormat)

    def OnScriptControl(self, event):
        idx = event.GetId() - 131
        selected = self.scriptcontrol_preset[idx]
        self.ScriptControl.SetPlayBox(self.parent.parent.parent.PlayBox)
        self.ScriptControl.SetListBox(self.parent.parent)
        path = self.ScriptControl.GetSelectedScriptPath(selected)
        f = open(path, 'rb')
        script = f.read()
        result = self.ScriptControl.GetScriptResult(script)
        f.close()
        self.ScriptControl.ProcessScript(result)

    def OnCheckConvertTempoRange(self, event):
        if event.Id == 101:
            self.parent.parent.ConvertToUpTempo(
                self.parent.parent.GetSelectedItems())
        elif event.Id == 102:
            self.parent.parent.ConvertToDownTempo(
                self.parent.parent.GetSelectedItems())

    def OnCheckConvertKeyFormat(self, event):
        if event.Id == 111:
            self.parent.parent.ConvertKeyFormat(
                self.parent.parent.GetSelectedItems(), 0)
        elif event.Id == 112:
            self.parent.parent.ConvertKeyFormat(
                self.parent.parent.GetSelectedItems(), 1)
        elif event.Id == 113:
            self.parent.parent.ConvertKeyFormat(
                self.parent.parent.GetSelectedItems(), 2)

    def OnCheck(self, event):
        if event.Id == 1:
            self.PlaySelectedItem()
        elif event.Id == 2:
            self.EditSelectedItem()
        elif event.Id == 3:
            self.DeleteSelectedItem()
        elif event.Id == 4:
            self.AnalyzeSelectedItems(forced=True)
        elif event.Id == 5:
            self.OpenContainingFolder()
        # elif event.Id == 7-diff:
        #   self.AnalyzeSelectedItems()
        # elif event.Id == 8-diff:
        #   self.AnalyzeSelectedItems(forced=True)
        # elif event.Id == 8-diff:
        #   self.CheckItemsConsistency()

    def EditSelectedItem(self):
        self.parent.parent.parent.DialogBox = ItemEditBox(self.parent)
        x, y, w, h = self.parent.parent.parent.parent.GetRect()
        width, height = self.parent.parent.parent.DialogBox.GetSize()
        self.parent.parent.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.parent.parent.DialogBox.ShowModal()
        self.parent.parent.parent.DialogBox.Destroy()
        self.parent.parent.parent.DialogBox = None
        self.parent.DirectDraw()

    def DeleteSelectedItem(self):
        self.parent.parent.RemoveSelectedItems()

    def PlaySelectedItem(self):
        self.parent.parent.LeftDoubleClick(None)

    def AnalyzeSelectedItems(self, forced=False):
        mdxs = self.parent.parent.GetSelectedItemsKeyValue('mdx')
        paths = self.parent.parent.GetSelectedItemsKeyValue('path')
        for path, mdx in zip(paths, mdxs):
            # print('xxxxxxx')
            # self.parent.parent.parent.MFEATS.AddMFEATSTask(path, urgent=False, forced=forced)
            t = threading.Thread(
                target=self.parent.parent.parent.MFEATS.AddMFEATSTask,
                args=(path,), kwargs={'urgent': False, 'forced': forced},
                daemon=True
            )
            t.start()

    def CheckItemsConsistency(self):
        selectedItems = self.parent.parent.GetSelectedItems()
        self.parent.parent.CheckItemsConsistency(selectedItems)
        self.parent.parent.reInitBuffer = True

    def OpenContainingFolder(self):
        path = self.parent.parent.GetSelectedItemsKeyValue('path')[0]
        dirname = os.path.dirname(path)
        # filename = os.path.splitext(os.path.basename(path))[0]
        # upath = path.encode(sys.getfilesystemencoding())
        if sys.platform == 'darwin':
            cmd = r'''open -- "%s"''' % (dirname)
        elif sys.platform == 'linux2':
            cmd = r'''gnome-open -- "%s"''' % (dirname)
        elif sys.platform.startswith('win'):
            cmd = r'''Explorer /select, "%s"''' % (path)
        subprocess.call(cmd, shell=False)


class StatusBox(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        st = self.parent.parent.st.LISTBOX
        self.SetBackgroundColour(st.TOOLBAR_BG_COLOR)
        self.messages = (u'', u'')
        self.proc = 0
        self.alarm = None
        self.alarm_color = None
        self.alarm_timer = 0
        self.InitBuffer()

    def CATCH_EVT_GLOBAL(self, event):
        self.HandleMessages()
        if self.alarm is not None:
            self.alarm_timer += 1
        if self.alarm_timer > 50:
            self.alarm_timer = 0
            self.alarm = None
            self.alarm_color = None
        # self.HandlePopupMenu(event)

    def HandlePopupMenu(self, event):
        if event.rectIdx is None:
            return
        if event.RightUp is False:
            return
        if event.down.rectIdx is None:
            return
        # if event.down.rectIdx == 0:
        # self.parent.SetPopupMenu(PlayBoxPopupAnalyzerProcs(self), (event.x, event.y))

    def HandleMessages(self):
        if self.parent.ListBox.IsFilteredAll():
            filtered = 'FILTERED'
        else:
            filtered = ''
        total = self.parent.ListBox.GetItemsLength()
        selected = self.parent.ListBox.GetSelectedItemsLength()
        proc, task, core = self.parent.MFEATS.GetWorkingCount()
        self.proc = proc
        if self.alarm is not None:
            message_left = self.alarm
        else:
            message_left = u'Selected %s / %s tracks %s'\
                % (selected, total, filtered)
        message_right = u'Analyzing %s / %s tracks using %s Threads'\
            % (proc, task + proc, core)
        messages = (message_left, message_right)
        if self.messages == messages:
            return
        self.messages = messages
        self.reInitBuffer = True

    def SetRectDraw(self, dc):
        message_left, message_right = self.messages
        w, h = self.parent.GetSize()
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((6, 11))
        font.SetFaceName(FONT_ITEM)
        dc.SetFont(font)
        tw, th = dc.GetTextExtent(message_right)
        xys = ((10, 7), (w - tw - 10, 7),)
        if self.alarm_color == 'blue':
            color_left = wx.Colour(0, 0, 120)
        elif self.alarm_color == 'red':
            color_left = wx.Colour(120, 0, 0)
        else:
            color_left = wx.Colour(0, 0, 0)
        if self.proc != 0:
            color_right = wx.Colour(0, 0, 120)
        else:
            color_right = wx.Colour(0, 0, 0)
        dc.DrawTextList(self.messages, xys, foregrounds=(color_left, color_right))

    def OnSize(self, event=None):
        self.DirectDraw()
