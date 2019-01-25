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

from listboxlib import FileOpenDialog
from listboxlib import FileSaveDialog
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
        if self.parent.parent.parent.ListBox.IsFilteredAll():
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
            self.parent.parent.parent.ListBox.AddInnerList()
            # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(inpaths)
            self.DropFromOutside(inpaths)
            # t = threading.Thread(
            #     target=self.parent.parent.ListBox.List.FileDrop.DropFromOutside,
            #     args=(inpaths,), daemon=True
            # )
            # t.start()

            self.parent.parent.parent.ListBox.Header.SetAutoColumnWidth()
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
            self.parent.parent.parent.ListBox.AddInnerList(title)
            self.parent.parent.parent.ListBox.Header.SetAutoColumnWidth()
            # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(inpaths)
            self.DropFromOutside(inpaths)
            self.parent.reInitBuffer = True

    def DropFromOutside(self, inpaths, tabRectIdx=None):

        kwargs = {}
        if tabRectIdx:
            kwargs.update({'selectedList': tabRectIdx})

        t = threading.Thread(
            target=self.parent.parent.parent.ListBox.List.FileDrop.DropFromOutside,
            args=(inpaths,), kwargs=kwargs, daemon=True
        )
        t.start()

    def DropToExistingTab(self, inpaths, tabRectIdx):
        # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(
        #     inpaths, selectedList=tabRectIdx)
        self.DropFromOutside(inpaths, tabRectIdx)
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


class XXX():

    def GetRowsHeight(self):
        return 26
        # return self.TabList.tab_height

    def GetItemsLength(self):
        # print(len(self.parent.ListBox.innerList))
        return len(self.parent.ListBox.innerList)

    def GetNearestItem(self, focus, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        if focus < 0:
            return 0
        elif focus >= self.GetItemsLength(selectedList):
            return self.GetItemsLength(selectedList) - 1
        return focus

    def GetFocusedTabIndex(self):
        # return self.focus.item
        return self.parent.ListBox.selectedList

    def GetShiftedItem(self, selectedList=None):
        # return self.focus.shift
        if selectedList is None:
            selectedList = self.selectedList
        return self.innerList[selectedList].focus.shift

    def IsItemInViewRange(self, item):
        if self.ItemDirectionInViewRange(item) == 0:
            return True
        return False

    def ItemDirectionInViewRange(self, item):
        row_size = self.GetRowsHeight()
        height = self.List.GetSize().height
        y = self.GetVirtualPositionY() + item * row_size
        if y < 0:
            return -1
        if y > height - row_size:
            return 1
        return 0

    # Virtual Position Control

    def GetVirtualPositionX(self):
        return self.parent.ListBox.innerList[self.parent.ListBox.selectedList].rects.offset.x

    def GetVirtualPositionY(self):
        return self.virtual_position_y
        # return self.parent.ListBox.innerList[self.parent.ListBox.selectedList].rects.offset.y

    def GetVirtualPositionXW(self):
        vpxw = self.GetVirtualPositionX()
        for column in self.GetShownColumns():
            vpxw += column.width
        return vpxw

    # def GetVirtualPositionYH(self):
    #     row_size = self.GetRowsHeight()
    #     height = self.rects.list.height
    #     length = self.GetItemsLength()
    #     vpy = self.GetVirtualPositionY()
    #     return offset_y + length * row_size

    def GetVirtualPosition(self):
        x = self.GetVirtualPositionX()
        y = self.GetVirtualPositionY()
        return wx.Point(x, y)

    def SetVirtualPositionX(self, x):
        return
        x = self.LimitVirtualPositionX(x)
        self.innerList[self.selectedList].rects.offset.x = x
        self.reInitBuffer = True

    def SetVirtualPositionY(self, y, bounce=False):
        y = self.LimitVirtualPositionY(y, bounce=bounce)
        self.virtual_position_y = y
        # self.reInitBuffer = True
        # self.TabList.DirectDraw()
        # self.SliderV.DirectDraw()
        if hasattr(self, 'TabList'):
            self.TabList.reInitBuffer = True
        if hasattr(self, 'SliderV'):
            self.SliderV.reInitBuffer = True
            # self.SliderV.DirectDraw()

        # y = self.LimitVirtualPositionY(y, bounce=bounce)
        # if bounce:
        #   if y == 0: y = 1
        #   vpy_limit = self.GetVirtualPositionYLimit()
        #   if y == vpy_limit: y = y-5
        #   print y
        # self.innerList[self.selectedList].rects.offset.y = y
        # self.reInitBuffer = True

    def SetBestVirtualPositionX(self):
        vpx = self.GetVirtualPositionX()
        self.SetVirtualPositionX(vpx)

    def SetBestVirtualPositionY(self):
        vpy = self.GetVirtualPositionY()
        self.SetVirtualPositionY(vpy)

    def SetBestVirtualPosition(self):
        vpx = self.GetVirtualPositionX()
        vpy = self.GetVirtualPositionY()
        self.SetVirtualPositionX(vpx)
        self.SetVirtualPositionY(vpy)

    def LimitVirtualPositionX(self, x):
        return 0
        if x > 0:
            return 0
        try:
            list_width = self.List.GetSize().width
        except Exception:
            list_width = 0
        cols_width = self.parent.ListBox.GetShownColumnsWidth()
        if cols_width < list_width:
            return 0
        if cols_width + x < list_width:
            return -cols_width + list_width
        return x

    def LimitVirtualPositionY(self, vpy, bounce=False):
        if vpy > 0:
            return 0
        vpy_limit = self.GetVirtualPositionYLimit()
        if vpy < vpy_limit:
            if bounce:
                # return vpy_limit-1
                return vpy_limit
            return vpy_limit
        return vpy

    def GetVirtualPositionXLimit(self):
        length = self.GetShownColumnsWidth()
        if hasattr(self, 'List'):
            width = self.List.GetClientSize().height
        else:
            width = 0
        if length < width:
            return 0
        return -length + width
        # length = self.rectHeader.columns[-1].x+self.rectHeader.columns[-1].w
        # if length < self.rectList.w: return 0
        # return -length+self.rectList.w

    def GetVirtualPositionYLimit(self):
        row_size = self.GetRowsHeight()
        if hasattr(self, 'TabList'):
            height = self.TabList.GetSize().height
        else:
            height = 0
        length = self.GetItemsLength()
        # print(length)
        # print self.rects.list.height
        if length * row_size < height:
            return 0
        return -length * row_size + height

    # UI Action Control

    def ScrollH(self, scroll_size):
        vpx = self.GetVirtualPositionX()
        x = vpx + scroll_size * 5
        self.SetVirtualPositionX(x)

    def ScrollV(self, scroll_size):
        vpy = self.GetVirtualPositionY()
        y = vpy + scroll_size * self.GetRowsHeight()
        self.SetVirtualPositionY(y, bounce=True)

    def SlideVKnob(self, event):
        if event.LeftIsDrag is False:
            return
        rect = self.rectSliderV
        initPosY = event.drag.Y - rect.slidable.y
        if event.drag.rectIdx == 301 and self.pending.SliderDrag is False:
            self.dragSlidePosY = self.firstItemPosY
            self.pending.SliderDrag = True
        length = len(self.innerList) * self.row_size
        if length != 0:
            shownRatio = 1.0 * self.rectList.h / length
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        slidable = rect.slidable.h - rect.knob.h
        if slidable == 0:
            return
        diff = event.Y - initPosY - rect.slidable.y
        diffRatio = 1.0 * diff * (length - self.rectList.h) / slidable
        self.firstItemPosY = self.LimitFirstItemPosY(self.dragSlidePosY - diffRatio)
        self.reInitBuffer = True

    def SlideVSlidable(self, event):
        rect = self.rectSliderV
        slidable = rect.slidable.h - rect.knob.h
        if slidable != 0:
            posCYRatio = 1.0 * (event.Y - rect.slidable.y - rect.knob.h * 0.5) / slidable
        else:
            posCYRatio = 1.0
        firstItemPosYLimit = self.GetFirstItemPosYLimit()
        self.firstItemPosY = self.LimitFirstItemPosY(
            int(posCYRatio * firstItemPosYLimit))
        self.reInitBuffer = True

    def SelectAndFocusItem(self, item, shift=None, align=None):
        if item < 0:
            item = 0
        if item >= self.GetItemsLength():
            item = self.GetItemsLength() - 1
        self.innerList[self.selectedList].selectedItems = [item]
        self.FocusItem(item, shift=shift, align=align)

    def ControlSelectItem(self, item):
        if item in self.GetSelectedItems():
            self.innerList[self.selectedList].selectedItems.remove(item)
        else:
            self.innerList[self.selectedList].selectedItems.append(item)
        self.FocusItem(item)

    def ShiftSelectItems(self, item):
        if item < 0:
            item = 0
        itemsLength = self.GetItemsLength()
        if item >= itemsLength:
            item = itemsLength - 1
        shift = self.GetShiftedItem()
        if shift is None:
            self.SelectAndFocusItem(item, shift=item)
            return
        if shift < item:
            items = range(shift, item + 1)
        elif shift > item:
            items = range(shift, item - 1, -1)
        else:
            items = [item]
        self.innerList[self.selectedList].selectedItems = items
        self.FocusItem(item, shift=shift, align=None)

    def ScrollSelectItem(self, scroll_size, shifted=False):
        if scroll_size is None:
            return
        if isinstance(scroll_size, float) and scroll_size == 0.0:
            item = 0
        elif isinstance(scroll_size, float) and scroll_size == 1.0:
            item = self.GetItemsLength() - 1
        else:
            # self.GetSelectedItems()
            focusedItem = self.GetFocusedItem()
            if focusedItem is None:
                return
            item = self.GetNearestItem(focusedItem + scroll_size)
        if shifted is False:
            self.SelectAndFocusItem(item, shift=None, align=None)
            return
        self.ShiftSelectItems(item)

    def FocusItem(self, item, shift=None, align=None, selectedList=None):
        if selectedList is None:
            selectedList = self.selectedList
        self.innerList[selectedList].focus.item = item
        row_size = self.GetRowsHeight()
        if shift is None:
            self.innerList[selectedList].focus.shift = item
        else:
            self.innerList[selectedList].focus.shift = shift
        if align is None and self.IsItemInViewRange(item):
            self.reInitBuffer = True
            return
        if align is None:
            align = self.ItemDirectionInViewRange(item)
        height = self.List.GetClientSize().height
        offsetY = (height - row_size) * 0.5 * (align + 1)
        newPosY = -item * row_size + offsetY
        if newPosY > 0:
            newPosY = 0
        self.SetVirtualPositionY(newPosY, bounce=True)
        self.reInitBuffer = True
        self.SliderV.DirectDraw()


class ListBoxTab(RectBox, XXX):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.reInitBuffer = True
        self.rects = []
        self.scrollbar_size = 6
        self.is_slider_v_shown = True
        self.is_slider_h_shown = False
        self.always_show_slider = True
        self.virtual_position_y = 0
        self.st = parent.parent.st.LISTBOX
        self.TabList = ListBoxTabList(self)
        self.TabHeader = ListBoxTabHeader(self)
        self.SliderV = ListBoxTabSliderV(self)
        color = self.st.BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def GetBestRects(self):
        ss = self.scrollbar_size
        w, h = self.GetClientSize()
        if self.always_show_slider:
            padH, padV = (ss, ss)
        else:
            padH, padV = (0, 0)
        # self.SetBestVirtualPosition()
        # if self.IsNeededSliderH():
        #     padH = ss
        # if self.IsNeededSliderV():
        #     padV = ss
        # hh = self.GetRowsHeight()
        hh = self.TabList.tab_height
        padH = 0
        padV = ss
        bw = w - padV - 2
        bh = h - hh - padH - 1
        if padV > 0:
            bw -= 1
        if padH > 0:
            bh -= 1
        body = (1, hh, bw, bh + 1)
        header = (0, 0, w, hh)
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
        self.TabList.SetRect(body)
        self.TabHeader.SetRect(header)
        self.SliderV.SetRect(sliderV)

    def SetRectDraw(self, dc):
        self.TabList.reInitBuffer = True
        self.TabHeader.reInitBuffer = True
        self.SliderV.reInitBuffer = True

        lines = [(0, 0, 0, self.GetSize().height)]
        color = self.st.HEADER_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))

    def OnSize(self, event=None):
        self.Freeze()
        self.DirectDraw()
        self.TabList.DirectDraw()
        self.TabHeader.DirectDraw()
        self.SliderV.DirectDraw()
        self.DirectDraw()
        self.Thaw()


class ListBoxTabHeader(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.reInitBuffer = True
        self.bmp = Struct()
        self.bmp.add = images.listbox_tab_add.GetBitmap()
        color = self.parent.st.HEADER_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def CATCH_EVT_GLOBAL(self, event):
        # print(event)
        if self.parent.parent.HasToSkipEvent():
            return
        self.HandleEventTabAddDown(event)

    # def ExtendGlobalEvent(self, event):
    #     return event

    def HandleEventTabAddDown(self, event):
        if not self.onClient:
            return
        if event.LeftUp is False:
            return
        if event.click.x is None or event.click.y is None:
            return
        # if not event.LeftDown:
        #     return
        if not self.IsInRect(self.add_button, (event.X, event.Y)):
            return
        self.parent.parent.ListBox.AddInnerList()
        self.parent.parent.ListBox.Header.SetAutoColumnWidth()
        self.DirectDraw()
        scroll = self.parent.GetRowsHeight() * self.parent.GetItemsLength()
        self.parent.ScrollV(-scroll)
        self.parent.TabList.DirectDraw()
        self.parent.SliderV.DirectDraw()

    def SetRectDraw(self, dc):
        width, height = self.GetSize()
        lines = [(0, 1, width, 1)]
        x = width - self.parent.scrollbar_size - 3
        lines.append((x, 1, x, height))
        color = self.parent.st.HEADER_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))
        size = self.bmp.add.GetWidth()
        offset_x = width - (size + self.parent.scrollbar_size + 12)
        offset_y = (height - size) / 2 + 1
        dc.DrawBitmap(self.bmp.add, offset_x, offset_y, useMask=True)
        pad = 2
        self.add_button = (offset_x - pad, offset_y - pad, size + pad * 2, size + pad * 2)

        lines = [(0, 1, 0, self.GetSize().height)]
        color = self.parent.st.HEADER_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))

    def OnSize(self, event=None):
        self.DirectDraw()


class ListBoxTabList(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.reInitBuffer = True
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
        self.scrollbar_size = 6
        self.TextEdit = None
        self.text_edit_tabIdx = None
        self.rects = ((0, 0, 0, 0))
        self.FileDrop = ListBoxTabDnD(self)
        self.SetDropTarget(self.FileDrop)
        # self.SliderV = ListBoxTabSliderV(self)
        self.bmp = Struct()
        # self.bmp.add = images.listbox_tab_add.GetBitmap()
        self.bmp.close = images.listbox_tab_close.GetBitmap()
        color = self.parent.st.BG_COLOR
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
        self.DrawTabLine(dc)
        self.DrawTabInsertLine(dc)
        self.DrawTabPolygon(dc)
        self.DrawTabText(dc)
        # self.DrawTabLineV(dc)
        # self.DrawTabTextEdit(dc)

    # def DrawTabTextEdit(self, dc):
    #     if self.TextEdit is None:
    #         return
    #     x, y, w, h = self.TextEdit.GetRect()
    #     rect = (x - 4, y - 2, w + 8, h + 3)
    #     dc.DrawRectangleList((rect,),
    #                          pens=wx.Pen((255, 255, 255), 0), brushes=wx.Brush((255, 255, 255)))

    def DrawTabRectSelected(self, dc):
        x, y, w, h = self.rects[self.parent.parent.ListBox.selectedList]
        color = (200, 200, 200)
        rect = (x - 1, y, w + 2, h + 1)
        dc.DrawRectangleList((rect,), pens=wx.Pen((0, 0, 0), 1), brushes=wx.Brush(color))

    def DrawTabRect(self, dc):
        vpy = self.parent.GetVirtualPositionY()
        self.parent.SetVirtualPositionY(vpy)
        width, height = self.GetClientSize()

        rects = []
        vpy = self.parent.GetVirtualPositionY()
        for i in range(len(self.parent.parent.ListBox.innerList)):
            rects += [wx.Rect(1, self.tab_height * i + vpy, width - 1, self.tab_height - 1)]
        self.rects = rects

        def limitcolor(v):
            if v > 255:
                return 255
            if v < 0:
                return 0
            return v

        ct = self.parent.parent.ListBox.st.LIST_BG_CONTRAST
        r, g, b = self.parent.st.LIST_BG_COLOR
        bgcolor_odd = [limitcolor(v) for v in (r - ct, g - ct, b - ct)]
        bgcolor_even = [limitcolor(v) for v in (r + ct, g + ct, b + ct)]
        for i, rect in enumerate(rects):
            if i % 2 == 1:
                dc.GradientFillLinear(rect, bgcolor_even, bgcolor_even, nDirection=wx.SOUTH)
            else:
                dc.GradientFillLinear(rect, bgcolor_odd, bgcolor_odd, nDirection=wx.SOUTH)

    def DrawTabInsertLine(self, dc):
        if self.FileDrop.insertTabIdx is None:
            return
        if self.FileDrop.insertTabIdx < len(self.rects):
            rect = self.rects[self.FileDrop.insertTabIdx]
            y = rect.y - 1
        else:
            rect = self.rects[-1]
            y = rect.y + rect.height - 1
        length = self.parent.GetItemsLength()
        y = y - 1 if length == self.FileDrop.insertTabIdx else y
        dc.DrawRectangleList(((0, y, self.GetSize().width + 1, 3),),
                             pens=wx.Pen((20, 20, 20)), brushes=wx.Brush((200, 200, 200, 255)))

    def DrawTabLine(self, dc):
        color = self.parent.parent.ListBox.st.LIST_PN_COLOR
        lines = [(r.x, r.y + r.height, r.width, r.y + r.height) for r in self.rects]
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))

    # def DrawTabLineV(self, dc):
    #     return
    #     r_pad = 1
    #     color = (30, 30, 30)
    #     width, _ = self.GetSize()
    #     right_x = width - r_pad - self.scrollbar_size - 2
    #     lines = [(0, 1, 0, self.rects[0].height + 1), (0, 1, width, 1),
    #              (right_x, 1, right_x, self.rects[0].height + 1)]
    #     dc.DrawLineList(lines, pens=wx.Pen(color, 1))

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
        for i, v in enumerate(zip(self.rects, self.GetTabsTitles())):
            rect, title = v
            margin = self.close_rects[i].width + 15 + self.scrollbar_size
            if rect.width - margin < 12:
                continue
            if i == self.parent.parent.ListBox.selectedList:
                selected_texts.append(self.LimitTextLength(dc, title, rect.width - margin))
                selected_xys.append((rect.x + 11, rect.y + 5 + 1))
            else:
                texts.append(self.LimitTextLength(dc, title, rect.width - margin))
                xys.append((rect.x + 11, rect.y + 5 + 1))
        dc.DrawTextList(texts, xys, foregrounds=wx.Colour(210, 210, 210), backgrounds=None)
        dc.DrawTextList(selected_texts, selected_xys, foregrounds=wx.Colour(30, 30, 30), backgrounds=None)

    def DrawTabPolygon(self, dc):
        size = 6
        right_align = 10
        close_rects = []
        for i, rect in enumerate(self.rects):
            offset_x = rect.x + rect.width - size - right_align
            offset_y = rect.y + 8 + 1
            close_rects.append(wx.Rect(offset_x - 3, offset_y - 3, size + 6, size + 6))
            if i == self.parent.parent.ListBox.selectedList:
                dc.DrawBitmap(self.bmp.close, offset_x, offset_y, useMask=True)
        self.close_rects = close_rects

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        x, y = xy
        return self.GetTabRectIdx((x, y))

    def ExtendGlobalEvent(self, event):
        # print('ExtendGlobalEvent', (event.X, event.Y))
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
        if self.onClient is False:
            return
        self.parent.ScrollV(event.WheelRotation / 40)

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.parent.HasToSkipEvent():
            return
        # self.HandleEventTabAddDown(event)
        self.HandleEventTabCloseDown(event)
        self.HandleEventTabSelectDown(event)
        self.HandleEventTabShuffleDragPending(event)
        self.HandleEventTabShuffleDragFinalize(event)
        self.HandleEventTabDrag(event)
        self.HandleEventTabPopup(event)
        self.HandleEventTabAddPopup(event)
        # self.HandleEventTabTextEditOff(event)
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.FileDrop.downTabIdx = None
            self.FileDrop.insertTabIdx = None

    # def HandleEventTabTextEditOff(self, event):
    #     if self.TextEdit is None:
    #         return
    #     isInRect = self.IsInRect(self.TextEdit.GetRect(), (event.X, event.Y))
    #     if isInRect is False and (event.MiddleDown or event.RightDown):
    #         self.TextEdit.CommitText()
    #     if self.TextEdit.destroy:
    #         self.TextEdit.Destroy()
    #         self.TextEdit = None
    #         self.DirectDraw()

    # def HandleEventTabTextEditOn(self, event):
    #     if event.LeftDClick is False:
    #         return
    #     if self.TextEdit is not None:
    #         return
    #     if event.tabIdx is None:
    #         return
    #     if event.tabIdx == -1:
    #         return
    #     self.TextEdit = TabTextEdit(self)
    #     x, y, w, h = self.rects[event.tabIdx]
    #     self.TextEdit.SetRect((x + 9, y + 6, w - 17, h - 10))
    #     title = self.parent.ListBox.GetTabsTitles()[event.tabIdx]
    #     self.TextEdit.SetValue(title)
    #     self.reInitBuffer = True

    # def SetTabTextEditOn(self):
    #     tabIdx = self.text_edit_tabIdx
    #     self.TextEdit = TabTextEdit(self)
    #     x, y, w, h = self.rects[tabIdx]
    #     self.TextEdit.SetRect((x + 9, y + 6, w - 17, h - 10))
    #     title = self.GetTabsTitles()[tabIdx]
    #     self.TextEdit.SetValue(title)
    #     self.reInitBuffer = True

    def HandleEventTabPopup(self, event):
        if event.RightUp is False:
            return
        if event.rectIdx is None:
            return
        if event.tabIdx == -1:
            return
        if event.down.rectIdx is None:
            return
        if self.parent.parent.ListBox.selectedList != event.tabIdx:
            return
        self.text_edit_tabIdx = event.tabIdx
        self.parent.parent.SetPopupMenu(ListBoxPopupTab(self), (event.x, event.y))

    def HandleEventTabAddPopup(self, event):
        if event.RightUp is False:
            return
        if event.rectIdx is None:
            return
        if event.tabIdx != -1:
            return
        if event.down.rectIdx is None:
            return
        self.parent.parent.SetPopupMenu(ListBoxPopupTabAdd(self), (event.x, event.y))

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
        pathIdx = self.parent.parent.ListBox.GetColumnKeyToIdx('path')
        paths = map(itemgetter(pathIdx),
                    self.parent.parent.ListBox.innerList[selectedList].items)
        title = self.parent.parent.ListBox.innerList[selectedList].title
        filename = os.path.sep.join([get_user_docapp_path(), '%s.m3u' % (title)])
        audio.generate_m3u(filename, paths)
        filename = os.path.abspath(filename)
        self.parent.parent.SetItemDrag((filename,), del_source=True)

    def HandleEventTabShuffleDragPending(self, event):
        if event.drag.tabIdx == -1:
            return
        if event.drag.tabIdx is None:
            return
        if event.drag.closeIdx is not None:
            return
        # if event.drag.tabIdx == event.tabIdx:
        #     return
        self.FileDrop.downTabIdx = event.drag.tabIdx
        if len(self.parent.parent.ListBox.innerList) == 1:
            return
        self.FileDrop.insertTabIdx = self.GetInsertTabRectIdx((event.X, event.Y))

        height = self.GetSize().height
        row_size = self.parent.GetRowsHeight()
        isUpward = event.Y < 0 + row_size * 0.5
        isDownward = event.Y > 0 + height - row_size * 0.5
        # self.FileDrop.insertItemIdx = event.insertItemIdx
        if isUpward or isDownward:
            self.FileDrop.dropTimer += 1
        else:
            self.FileDrop.dropTimer = 0
        if self.FileDrop.dropTimer > 20:
            if isUpward:
                self.parent.ScrollV(0.18)
                self.parent.SliderV.DirectDraw()
            elif isDownward:
                self.parent.ScrollV(-0.18)
                self.parent.SliderV.DirectDraw()

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
        self.parent.parent.ListBox.DeleteInnerList(event.down.closeIdx)
        self.reInitBuffer = True
        self.parent.SliderV.DirectDraw()

    def HandleEventTabSelectDown(self, event):
        if event.tabIdx == -1:
            return
        if event.tabIdx is None:
            return
        if event.closeIdx is not None:
            return
        if event.LeftDown is False:
            return
        self.parent.parent.ListBox.SetSelectedList(event.tabIdx)
        # self.reInitBuffer = True
        self.parent.DirectDraw()
        self.DirectDraw()

    # Tab Control

    def SetTabShuffle(self, fromIdx, toIdx):
        if toIdx < fromIdx:
            self.parent.parent.ListBox.innerList.insert(
                toIdx, self.parent.parent.ListBox.innerList.pop(fromIdx))
            self.parent.parent.ListBox.SetSelectedList(toIdx)
        elif toIdx > fromIdx:
            self.parent.parent.ListBox.innerList.insert(
                toIdx - 1, self.parent.parent.ListBox.innerList.pop(fromIdx))
            self.parent.parent.ListBox.SetSelectedList(toIdx - 1)

    def SetTabTitle(self, title, selectedList=None):
        if selectedList is None:
            selectedList = self.parent.parent.ListBox.selectedList
        self.parent.parent.ListBox.SetListTitle(title, selectedList)

    def GetTabTitle(self, selectedList=None):
        if selectedList is None:
            selectedList = self.parent.parent.ListBox.selectedList
        return self.parent.parent.ListBox.innerList[selectedList].title

    def GetTabsTitles(self):
        titles = list()
        for i in range(len(self.parent.parent.ListBox.innerList)):
            titles.append(self.parent.parent.ListBox.innerList[i].title)
        return titles

    def GetTabRectIdx(self, xy):
        x, y = xy
        if self.onClient is False:
            return None
        xy = wx.Point(x, y)
        # add_button_size = self.rects[0].height

        for i, rect in enumerate(self.rects):
            if self.IsInRect(rect, xy):
                return i
        return None

    def GetInsertTabRectIdx(self, xy):
        if self.onClient is False:
            return None
        xy = wx.Point(*xy)
        for i, r in enumerate(self.rects):
            offsetY = 0 if i == 0 else self.rects[i - 1].y + self.rects[i - 1].height * 0.5
            finishY = r.y + r.height * 0.5
            rect = wx.Rect(r.x, offsetY, r.width, finishY - offsetY)
            if self.IsInRect(rect, xy):
                return i
        offsetY = self.rects[- 1].y + self.rects[- 1].height * 0.5
        finishY = self.GetSize().height
        rect = wx.Rect(r.x, offsetY, r.width, finishY - offsetY)
        if self.IsInRect(rect, xy):
            return i + 1

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


class ListBoxTabSliderV(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent

        self.pending = Struct(drag_vpy=None)
        color = self.parent.st.SCROLLBAR_BG_COLOR
        self.SetBackgroundColour(color)
        self.reInitBuffer = True
        self.InitBuffer()

    def SetRectDraw(self, dc):
        self.DrawSliderV(dc)

    def DrawSliderV(self, dc):
        width, height = self.GetSize()
        slider = wx.Rect(0, 0, width, height)
        btnup = wx.Rect(0, 0, width, width)
        btndown = wx.Rect(0, height - width, width, width)
        slidable = wx.Rect(0, width, width, height - width * 2)
        # print(slidable)
        # _, y, _, h = self.parent.TabList.rects[-1]
        # length = y + h
        length = self.parent.GetItemsLength() * self.parent.GetRowsHeight()
        # list_height = self.parent.TabList.GetSize().height
        if length <= 0 or height <= 0:
            return
        shownRatio = height / length
        if shownRatio > 1.0:
            shownRatio = 1.0

        # y = self.parent.rects[0][3]
        # x = parenst_size.width - width
        # self.SetRect((x, y, width, parenst_size.height - y))

        # if length != 0:
        #     shownRatio = 1.0 * self.parent.List.GetSize().height / length
        # else:
        #     shownRatio = 1.0
        # if shownRatio > 1.0:
        #     shownRatio = 1.0
        h = slidable.height * shownRatio
        if h < width:
            h = 1.0 * width
        # div = list_height - 10
        div = length - self.parent.TabList.GetSize().height
        if div != 0:
            posCYRatio = 1.0 * (-self.parent.GetVirtualPositionY()) / div
            # posCYRatio = 1.0
        else:
            posCYRatio = 1.0
        if posCYRatio > 1.0:
            posCYRatio = 1.0
        #     self.parent.parent.innerList[self.parent.selectedList].rects.offset.y = -div
        # x = slidable.x
        y = slidable.y + math.ceil((slidable.height - h) * posCYRatio)
        knob = wx.Rect(0, y, width, h)
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
        list_height = self.parent.TabList.GetSize().height
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
            self.parent.parent.parent.ListBox.AddInnerList()
            self.parent.parent.parent.ListBox.Header.SetAutoColumnWidth()


class ListBoxPopupTab(wx.Menu):

    def __init__(self, parent):
        wx.Menu.__init__(self)
        self.parent = parent
        if self.parent.parent.parent.ListBox.IsFilteredAll():
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
            self.parent.parent.parent.DialogBox = TabRenameBox(self.parent)
            title = self.parent.GetTabTitle()
            self.parent.parent.parent.DialogBox.UserInput.SetValue(title)

            x, y, w, h = self.parent.parent.parent.parent.GetRect()
            width, height = self.parent.parent.parent.DialogBox.GetSize()
            width = 350
            self.parent.parent.parent.DialogBox.SetRect(
                (x + (w - width) / 2, y + (h - height) / 2, width, height))
            self.parent.parent.parent.DialogBox.ShowModal()
            self.parent.parent.parent.DialogBox.Destroy()
            self.parent.parent.parent.DialogBox = None
            self.parent.DirectDraw()
        if event.GetId() == 3:
            selectedList = self.parent.parent.parent.ListBox.selectedList
            self.parent.parent.parent.ListBox.DeleteInnerList(selectedList)
            # self.parent.parent.ListTab.SetTabTextEditOn()
        if event.GetId() == 4:
            cwd = os.getcwd()
            self.parent.parent.parent.DialogBox = FileOpenDialog(self.parent)
            x, y, w, h = self.parent.parent.parent.parent.GetRect()
            # self.parent.parent.DialogBox.SetSize((1024,800))
            width, height = self.parent.parent.parent.DialogBox.GetSize()
            self.parent.parent.parent.DialogBox.SetRect(
                (x + (w - width) / 2, y + (h - height) / 2, width, height))
            self.parent.parent.parent.DialogBox.ShowModal()
            os.chdir(cwd)  # only works with windows, linux
            paths = self.parent.parent.parent.DialogBox.GetPaths()
            self.parent.parent.parent.ListBox.List.FileDrop.DropFromOutside(paths)
            self.parent.parent.parent.DialogBox.Destroy()
            self.parent.parent.parent.DialogBox = None
        if event.GetId() == 5:
            cwd = os.getcwd()
            self.parent.parent.parent.DialogBox = FileSaveDialog(self.parent)
            self.parent.parent.parent.DialogBox.ShowModal()
            os.chdir(cwd)  # only works with windows, linux
            savepath = self.parent.parent.parent.DialogBox.GetPath()
            self.parent.parent.parent.DialogBox.Destroy()
            self.parent.parent.parent.DialogBox = None
            selectedList = self.parent.parent.parent.ListBox.selectedList
            pathIdx = self.parent.parent.parent.ListBox.GetColumnKeyToIdx('path', selectedList)
            paths = map(itemgetter(pathIdx),
                        self.parent.parent.parent.ListBox.innerList[selectedList].items)
            try:
                audio.generate_m3u(savepath, paths)
            except Exception:
                pass


class TabRenameBox(UserInputDialogBox):

    def __init__(self, parent):
        UserInputDialogBox.__init__(self, parent)
        self.parent = parent
        self.SetTitle('Tab Rename')
        self.tab_idx = self.parent.parent.parent.ListBox.selectedList
        self.tab_title = self.parent.parent.parent.ListBox.GetListTitle(self.tab_idx)
        # string = self.UserInput.SetValue(self.tab_title)
        self.ApplyButton.SetLabelText('Rename')
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)

    def OnKeyDown(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.Unbind(wx.EVT_CHAR_HOOK, event)
            self.OnApply()
        else:
            event.Skip()

    def OnApply(self, event=None):
        string = self.UserInput.GetValue()
        self.parent.parent.parent.ListBox.SetListTitle(string, self.tab_idx)
        self.OnClose(None)
