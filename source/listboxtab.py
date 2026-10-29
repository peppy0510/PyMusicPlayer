# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import glob
import images
import library
import macroboxstyle
import math
import os
import stat
import subprocess
import sys
import threading
import time
import radio
import webbrowser
import uikit
import wx

from listboxlib import FileOpenDialog
from listboxlib import FileSaveDialog
from listboxlib import ListBoxListDnD
from listboxlib import ListControl
from macroboxlib import DIALOG_PAD
from macroboxlib import Button
from macroboxlib import COLOR_STATUS_BG
from macroboxlib import ComboBox
from macroboxlib import ConfirmDialogBox
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
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
from utilities import get_user_appdata_path
from utilities import get_user_docapp_path


class ListBoxTabDnD(wx.FileDropTarget):

    def __init__(self, parent):
        wx.FileDropTarget.__init__(self)
        self.parent = parent
        self.tabDrag = False
        self.downTabIdx = None
        self.insertTabIdx = None
        self.dropInsertIdx = None
        self.dropEdge = 0.3
        self.dropEdgeLap = None
        self.dropEdgeWait = 0.4

    def OnEnter(self, x, y, d):
        self.onClient = True
        self.parent.onClient = True
        return d

    def OnLeave(self):
        self.onClient = False
        self.parent.onClient = False
        self.SetDropInsertIdx(None)
        self.SetDropFavorites(False)
        self.dropEdgeLap = None

    def OnDragOver(self, x, y, d):
        self.onClient = True
        self.parent.onClient = True
        place = None if self.tabDrag else self.GetDropPlace(x, y)
        self.SetDropInsertIdx(place[1] if place and place[0] == 'insert' else None)
        self.SetDropFavorites(bool(place) and place[0] == 'favorites')
        self.ScrollAtEdge(y)
        return d

    def GetDraggedKind(self):
        # what the list drags ('stations' or 'songs'), None from outside (files)
        mainpanel = self.parent.parent.parent
        drag = getattr(mainpanel, 'pending_item_drag', None)
        paths = list(drag.paths) if drag is not None else []
        if not paths:
            return None
        return 'stations' if all(audio.is_stream_path(v) for v in paths) else 'songs'

    def GetDropPlace(self, x, y):
        # ('favorites', None) over the radio's Favorites (its tab, or its row before it is
        # made); into a tab, or between the playlists. Stations only to the Favorites, songs
        # and files only to the playlists' section (the insert line was drawn among the
        # radio's rows, and between the playlists for a station)
        kind = self.GetDraggedKind()
        if self.parent.IsOverFavorites(y):
            return ('favorites', None) if kind != 'songs' else None
        if kind == 'stations':
            return None
        rects = self.parent.rects if isinstance(self.parent.rects, list) else []
        titles = self.parent.GetTabsTitles()
        for i, rect in enumerate(rects):
            if rect.height <= 0:
                continue
            if i not in self.parent.normal_tabs and rect.y <= y <= rect.y + rect.height:
                if titles[i] in radio.RADIO_TABS:
                    return None
                return ('into', i)
            if rect.y <= y <= rect.y + rect.height:
                edge = rect.height * self.dropEdge
                if y < rect.y + edge:
                    return ('insert', i)
                if y > rect.y + rect.height - edge:
                    return ('insert', i + 1)
                return ('into', i)
        normal = self.parent.normal_tabs
        if normal:
            # under the last playlist, up to half a row (not on into the sections after it)
            bottom = rects[normal[-1]].y + rects[normal[-1]].height
            if bottom < y <= bottom + rects[normal[-1]].height * 0.5:
                return ('insert', normal[-1] + 1)
        return None

    def SetDropFavorites(self, on):
        # the Favorites row outlined while stations are dragged over it
        if on == self.parent.drop_favorites:
            return
        self.parent.drop_favorites = on
        self.parent.DirectDraw()

    def SetDropInsertIdx(self, idx):
        if idx == self.dropInsertIdx:
            return
        self.dropInsertIdx = idx
        self.parent.DirectDraw()

    def ScrollAtEdge(self, y):
        row = self.parent.tab_height
        height = self.parent.GetSize().height
        step = 0.18 if y < row * 0.5 else -0.18 if y > height - row * 0.5 else 0
        if step == 0:
            self.dropEdgeLap = None
            return
        now = time.time()
        if self.dropEdgeLap is None:
            self.dropEdgeLap = now
        if now - self.dropEdgeLap < self.dropEdgeWait:
            return
        self.parent.parent.ScrollV(step)
        self.parent.parent.SliderV.DirectDraw()
        self.parent.DirectDraw()

    def OnDropFiles(self, x, y, inpaths):
        place = self.GetDropPlace(x, y)
        if place is None and self.GetDraggedKind() is not None:
            # the list's rows dropped where they do not go (stations off the Favorites,
            # songs on the radio's rows): nothing made (a new playlist was)
            self.SetDropInsertIdx(None)
            self.SetDropFavorites(False)
            return 0
        self.SetDropInsertIdx(None)
        self.SetDropFavorites(False)
        self.dropEdgeLap = None
        if self.tabDrag:
            return 0
        if self.parent.parent.parent.ListBox.IsFilteredAll():
            return 0
        # if self.parent.parent.ListBox.IsFilteredAll():
        #   filtered = True
        # else: filtered = False
        if self.downTabIdx is not None:
            return
        if place and place[0] == 'favorites':
            # stations kept in the favorites (a file is no station: left out)
            mainpanel = self.parent.parent.parent
            urls = [v for v in inpaths if audio.is_stream_path(v)]
            stations = [radio.get_station(v) or dict(url=v, name=v) for v in urls]
            if stations:
                radio.add_favorites(mainpanel, stations)
            return 0
        if place and place[0] == 'into':
            self.DropToExistingTab(inpaths, place[1])
        elif self.parent.IsTabCreationLimited():
            return 0
        else:
            self.CreateAndDropToNewTab(inpaths, place[1] if place else None)
        return 0

    def MoveNewTab(self, insertIdx):
        count = len(self.parent.parent.parent.ListBox.innerList)
        if insertIdx is not None and insertIdx < count - 1:
            self.parent.SetTabShuffle(count - 1, insertIdx)

    def CreateAndDropToNewTab(self, inpaths, insertIdx=None):
        if len(inpaths) > 1:
            self.parent.parent.parent.ListBox.AddInnerList()
            self.MoveNewTab(insertIdx)
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
            if stat.S_ISDIR(stats[stat.ST_MODE]):
                title = basename
            elif stat.S_ISREG(stats[stat.ST_MODE])\
                    and file_type in SUPPORTED_PLAYLIST_TYPE:
                title = os.path.splitext(basename)[0]
                inpaths = audio.read_m3u(path)
            else:
                title = None
            self.parent.parent.parent.ListBox.AddInnerList(title)
            self.MoveNewTab(insertIdx)
            self.parent.parent.parent.ListBox.Header.SetAutoColumnWidth()
            # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(inpaths)
            self.DropFromOutside(inpaths)
            self.parent.reInitBuffer = True

    def DropFromOutside(self, inpaths, tabRectIdx=None):

        if tabRectIdx is None:
            tabRectIdx = self.parent.parent.parent.ListBox.selectedList

        t = threading.Thread(
            target=self.parent.parent.parent.ListBox.List.FileDrop.DropFromOutside,
            args=(inpaths,), kwargs={'selectedList': tabRectIdx}, daemon=True
        )
        t.start()

    def DropToExistingTab(self, inpaths, tabRectIdx):
        # self.parent.parent.ListBox.List.FileDrop.DropFromOutside(
        #     inpaths, selectedList=tabRectIdx)
        self.DropFromOutside(inpaths, tabRectIdx)
        self.parent.reInitBuffer = True

    def SearchPatternIncludeSub(self, filepath, pattern='*', visited=None):
        # filepath = unicode(filepath)
        # pattern = unicode(pattern)
        if visited is None:
            visited = set()
        realpath = os.path.realpath(filepath)
        if realpath in visited:
            return []
        visited.add(realpath)
        retlist = glob.glob(os.path.join(filepath, pattern))
        findlist = os.listdir(filepath)
        for f in findlist:
            next = os.path.join(filepath, f)
            if os.path.isdir(next):
                retlist += self.SearchPatternIncludeSub(next, pattern, visited)
        return retlist


class XXX():

    def GetRowsHeight(self):
        return 26
        # return self.TabList.tab_height

    def GetItemsLength(self):
        # print(len(self.parent.ListBox.innerList))
        return len(self.parent.ListBox.innerList)

    def GetContentHeight(self):
        # the sidebar's rows with its headers and stations (TabList.DrawTabRect), else the
        # tabs alone
        tablist = getattr(self, 'TabList', None)
        if tablist is not None and tablist.content_height:
            return tablist.content_height
        return self.GetItemsLength() * self.GetRowsHeight()

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
        if hasattr(self, 'TabList'):
            height = self.TabList.GetSize().height
        else:
            height = 0
        length = self.GetContentHeight()
        if length < height:
            return 0
        return -length + height

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


# the sidebar's sections folded (sidebar_folded: 'playlists', 'library', 'radio'), each
# by a click on its name: many playlists pushed the library and the radio out of sight
# (read once and kept: asked at every drawing of the sidebar)
FOLDED = None


def is_section_folded(section):
    global FOLDED
    if FOLDED is None:
        FOLDED = list(GetPreference('sidebar_folded') or [])
    return section in FOLDED


def toggle_section(section):
    global FOLDED
    folded = [v for v in (FOLDED if FOLDED is not None else
                          GetPreference('sidebar_folded') or []) if v != section]
    if not is_section_folded(section):
        folded.append(section)
    FOLDED = folded
    SetPreference('sidebar_folded', folded)


def draw_fold_mark(dc, x, cy, folded, colour):
    # after a section's name: pointing down open, right folded (5 px)
    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        return
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour).Width(1.3)))
    if folded:
        gc.StrokeLines([(x + 1, cy - 3.5), (x + 4, cy - 0.5), (x + 1, cy + 2.5)])
    else:
        gc.StrokeLines([(x - 0.5, cy - 2), (x + 2.5, cy + 1), (x + 5.5, cy - 2)])


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
        # the + under the mouse, and held down on it (as the rows' close mark)
        button = getattr(self, 'add_button', None)
        kind = self.parent.TabList.GetCurrentSection()[1]
        hovered = bool(button) and self.onClient and self.IsInRect(button, (event.X, event.Y))
        downed = hovered and event.LeftIsDown and event.down.X is not None\
            and self.IsInRect(button, (event.down.X, event.down.Y))
        if (hovered, downed) != getattr(self, 'add_state', (False, False)):
            self.add_state = (hovered, downed)
            self.reInitBuffer = True
        self.HandleEventTabAddDown(event)
        # the name (anywhere off the +): its section folded or opened (the next one's, on its
        # top coming up into the box)
        following = self.parent.TabList.GetFollowingSection()
        if following and event.Y >= following[2]:
            kind = following[1]
        if self.onClient and event.LeftDown and hovered is False:
            toggle_section(kind)
            self.reInitBuffer = True
            self.parent.TabList.reInitBuffer = True
            self.parent.SliderV.reInitBuffer = True

    # def ExtendGlobalEvent(self, event):
    #     return event

    def HandleEventTabAddDown(self, event):
        if not self.onClient:
            return
        if event.LeftUp is False:
            return
        # if event.click.x is None or event.click.y is None:
        #     return
        # if not event.LeftDown:
        #     return
        # pressed and released on it, as the tab's close (a click was lost to
        # a pixel's move or a press over half a second)
        if event.down.X is None or event.down.Y is None or not self.add_button:
            return
        if not self.IsInRect(self.add_button, (event.down.X, event.down.Y)):
            return
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
        tablist = self.parent.TabList
        label, kind = tablist.GetCurrentSection()
        following = tablist.GetFollowingSection()
        self.drawn_sticky = ((label, kind), following)
        # pushed up by the next section's header coming up into it (its top here, the rest
        # in the rows under it), its line over it with it
        shift = following[2] - height if following else 0
        lines = [(0, 1 + shift, width, 1 + shift)]
        x = width - self.parent.scrollbar_size - 3
        lines.append((x, 1, x, height))
        color = self.parent.st.HEADER_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))
        self.DrawName(dc, label, kind, height, shift)
        self.add_button = None
        if kind == 'playlists':
            self.DrawAddButton(dc, width, height, shift)
        if following:
            body = tablist.GetRect()
            tablist.DrawHeader(dc, following[2], following[0], following[1], body.x,
                               body.width)
        lines = [(0, 1, 0, self.GetSize().height)]
        color = self.parent.st.HEADER_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))

    def DrawAddButton(self, dc, width, height, shift=0):
        size = self.bmp.add.GetWidth()
        # over the rows' close mark (2 px right with it, ListBoxTabList.DrawTabPolygon)
        offset_x = width - (size + self.parent.scrollbar_size + 10)
        offset_y = (height - size) / 2 + 1 + shift
        # under the mouse a key's face behind it, pressed the pressed face and the mark a
        # pixel down (the rows' close mark's: ListBoxTabList.DrawTabPolygon)
        hovered, downed = getattr(self, 'add_state', (False, False))
        if hovered:
            tokens = macroboxstyle.current().UI
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(tokens.CONTROL_DOWN if downed
                                           else tokens.CONTROL_HOVER)))
            # even as the mark (8 px) is, 4 px round it every way (15 sat it half a pixel off)
            face = size + 8
            dc.DrawRoundedRectangle(int(offset_x) - 4, int(offset_y) - 4, face, face,
                                    uikit.RADIUS)
        offset_y += 1 if downed else 0
        dc.DrawBitmap(self.bmp.add, int(offset_x), int(offset_y), useMask=True)
        # pad = 2
        # self.add_button = (offset_x - pad, offset_y - pad, size + pad * 2, size + pad * 2)
        # the header's height, up to the line before the scrollbar (the 8px mark was 12px to hit)
        pad = 8
        self.add_button = (offset_x - pad, shift, size + pad * 2, height)

    def DrawName(self, dc, label, kind, height, shift=0):
        # the section scrolled into named (the + adds a playlist: PLAYLISTS' alone), in
        # capitals as the list's header names its columns; its own header under it in the
        # rows (PLAYLISTS fixed over LIBRARY's and RADIO's rows read as theirs: the user)
        font = uikit.get_font(10)
        dc.SetFont(font)
        dc.SetTextForeground(self.parent.TabList.GetColours()[1])
        # a pixel lower than the middle by its caps (it sat a pixel over the list's header
        # names beside it, measured)
        top = int(round(uikit.get_caps_top(font, 2, height - 2))) + 1 + shift
        dc.DrawText(label.upper(), ListBoxTabList.HEADER_X, top)
        caps = uikit.get_caps_ink(font)
        draw_fold_mark(dc, ListBoxTabList.HEADER_X + dc.GetTextExtent(label.upper())[0] + 6,
                       top + caps[0] + caps[1] / 2.0, is_section_folded(kind),
                       self.parent.TabList.GetColours()[1])

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
        # the sidebar's sections: the playlists (the header box above has their +), the
        # library's tabs (Search, Similar), the radio's (Favorites, Browse stations: a row
        # before its tab is made, made when clicked)
        self.headers = []
        self.normal_tabs = []
        self.virtual_entries = {}
        self.drop_favorites = False
        self.content_height = 0
        color = self.parent.st.BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def IsTabCreationLimited(self):
        return False
        if len(self.rects) > self.tab_num_limit:
            return True
        return False

    # Draw ListBoxTab

    HEADER_HEIGHT = 24
    ROW_HEIGHT = 26

    def SetRectDraw(self, dc):
        self.DrawTabRect(dc)
        self.DrawTabRectSelected(dc)
        self.DrawTabInsertLine(dc)
        self.DrawTabPolygon(dc)
        self.DrawTabText(dc)
        self.DrawHeaders(dc)

    def DrawTabRect(self, dc):
        # the rows laid out by section, each tab by its title: the playlists in their order,
        # then Library's and Radio's tabs under their headers (the headers are gaps no tab
        # is hit in; a radio tab not made yet is a row of its own, virtual_entries)
        vpy = self.parent.GetVirtualPositionY()
        self.parent.SetVirtualPositionY(vpy)
        width, height = self.GetClientSize()
        vpy = self.parent.GetVirtualPositionY()
        titles = self.GetTabsTitles()
        library_titles = (library.FAVORITES_TITLE, library.RECENT_TITLE, library.SEARCH_TITLE,
                          library.SIMILAR_TITLE)
        rects = [None] * len(titles)
        headers, normal = [], []
        y = vpy + 2

        def row():
            return wx.Rect(1, round(y), round(width - 1), self.ROW_HEIGHT - 1)

        for i, title in enumerate(titles):
            if title in library_titles or title in radio.RADIO_TABS\
                    or is_section_folded('playlists'):
                continue
            rects[i] = row()
            normal.append(i)
            y += self.ROW_HEIGHT
        # the library: its favorite and recent tracks always (a row before their tab is
        # made), the found ones when there are
        virtual = {}
        y += 6
        headers.append((y, 'Library', 'library'))
        y += self.HEADER_HEIGHT
        for title in library_titles:
            if is_section_folded('library'):
                break
            if title in titles:
                rects[titles.index(title)] = row()
            elif title in (library.FAVORITES_TITLE, library.RECENT_TITLE):
                virtual[title] = row()
            else:
                continue
            y += self.ROW_HEIGHT
        y += 6
        headers.append((y, 'Radio', 'radio'))
        y += self.HEADER_HEIGHT
        for title in radio.RADIO_TABS:
            if is_section_folded('radio'):
                break
            if title in titles:
                rects[titles.index(title)] = row()
            else:
                virtual[title] = row()
            y += self.ROW_HEIGHT
        self.rects = [v if v is not None else wx.Rect(0, 0, 0, 0) for v in rects]
        self.normal_tabs = normal
        self.headers = headers
        self.SetCurrentSection(headers)
        self.virtual_entries = virtual
        # 2 px under the last row as over the first (4 more left 5, the list read as ending
        # short of its edge: the user)
        self.content_height = y - vpy + 1

    def GetColours(self):
        # (text, dimmed text, hover ground, selected ground, accent) for the sidebar
        st = self.parent.st
        tokens = macroboxstyle.current().UI
        fg = wx.Colour(st.LIST_FG_COLOR)
        bg = wx.Colour(st.BG_COLOR)
        accent = wx.Colour(tokens.ACCENT)

        def mix(a, b, share):
            return wx.Colour(*[int(x + (y - x) * share) for x, y in
                               zip(a.Get()[:3], b.Get()[:3])])
        return fg, mix(bg, fg, 0.5), mix(bg, fg, 0.08), mix(bg, accent, 0.32), accent

    def DrawTabRectSelected(self, dc):
        # the hovered row lighter, the selected one in the accent's tint with its bar
        fg, dim, hover, selected, accent = self.GetColours()
        dc.SetPen(wx.TRANSPARENT_PEN)
        hovered = self.cache.tabIdx
        if hovered is not None and 0 <= hovered < len(self.rects):
            dc.SetBrush(wx.Brush(hover))
            dc.DrawRectangle(self.rects[hovered])
        index = self.parent.parent.ListBox.selectedList
        if 0 <= index < len(self.rects):
            x, y, w, h = self.rects[index]
            dc.SetBrush(wx.Brush(selected))
            dc.DrawRectangle(x, y, w, h)
            dc.SetBrush(wx.Brush(accent))
            dc.DrawRectangle(0, y, 3, h)
        if self.drop_favorites:
            titles = self.GetTabsTitles()
            rect = self.rects[titles.index(radio.RADIO_TITLE)] if radio.RADIO_TITLE in titles\
                else self.virtual_entries.get(radio.RADIO_TITLE)
            if rect is not None:
                dc.SetPen(wx.Pen(accent, 2))
                dc.SetBrush(wx.TRANSPARENT_BRUSH)
                dc.DrawRectangle(rect.x + 1, rect.y + 1, rect.width - 2, rect.height - 1)

    def DrawTabInsertLine(self, dc):
        idx = self.FileDrop.insertTabIdx
        if idx is None:
            idx = self.FileDrop.dropInsertIdx
        if idx is None or not self.rects:
            return
        if idx < len(self.rects) and (idx in self.normal_tabs or idx == 0):
            rect = self.rects[idx]
            y = rect.y - 1
        elif idx > 0 and idx - 1 < len(self.rects):
            # after the last playlist: under it (the row at idx is another section's)
            rect = self.rects[idx - 1]
            y = rect.y + rect.height - 1
        else:
            rect = self.rects[-1]
            y = rect.y + rect.height - 1
        length = self.parent.GetItemsLength()
        y = y - 1 if length == idx else y
        color = self.parent.parent.ListBox.st.INSERTITEM_CURSOR_COLOR
        dc.DrawRectangleList(((0, y, self.GetSize().width + 1, 3),),
                             pens=wx.Pen((20, 20, 20)), brushes=wx.Brush((*color, 255)))

    def GetFont(self, pixels=12, bold=False):
        font = wx.Font(wx.Size(0, pixels), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL, faceName='Segoe UI')
        return font

    def DrawTabText(self, dc):
        if self.tab_rel_width < 30:
            return
        fg, dim = self.GetColours()[:2]
        rows = list(zip(self.rects, self.GetTabsTitles(), range(len(self.rects))))
        rows += [(rect, title, None) for title, rect in self.virtual_entries.items()]
        for rect, title, i in rows:
            margin = 15 + self.scrollbar_size
            if i is not None:
                margin += self.close_rects[i].width
            if rect.height <= 0 or rect.width - margin < 12:
                continue
            # one weight selected or not (the bar and the tint say it; bold moved the cut)
            dc.SetFont(self.GetFont(12))
            dc.SetTextForeground(fg)
            # its kind's icon before it (a playlist, a search, the favorites, the stations)
            self.DrawRowIcon(dc, self.GetRowIcon(title), rect.x + self.ICON_X,
                             rect.y + rect.height / 2.0, dim)
            # the radio's tabs by what they are (Favorites, Browse stations)
            text = self.LimitTextLength(dc, radio.RADIO_TABS.get(title, title),
                                        rect.width - margin - self.ICON_ROOM)
            th = dc.GetTextExtent(text)[1]
            dc.DrawText(text, rect.x + self.ICON_X + self.ICON_ROOM, rect.y + (rect.height - th) // 2)

    # the icon's left (12, then 10; now 6 px after the selection bar, the section's name,
    # PLAYLISTS, moved with it: HEADER_X) and its room before a row's name (12 px and its gap)
    ICON_X = 7
    HEADER_X = 9
    ICON_ROOM = 20

    def GetRowIcon(self, title):
        if title in (radio.RADIO_TITLE, library.FAVORITES_TITLE):
            return 'star'
        if title == radio.BROWSE_TITLE:
            return 'radio'
        if title in (library.SEARCH_TITLE, library.SIMILAR_TITLE):
            return 'search'
        if title in (library.RECENT_TITLE, radio.RECENT_TITLE):
            return 'recent'
        return 'list'

    def DrawRowIcon(self, dc, icon, x, cy, colour):
        # 12 px line drawings in the dimmed text's colour
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour).Width(1.3)))
        gc.SetBrush(wx.NullGraphicsBrush)
        if icon == 'list':
            for k in (-3.5, 0, 3.5):
                gc.StrokeLine(x + 1, cy + k, x + 11, cy + k)
        elif icon == 'recent':
            # a clock: its face and hands at ten past
            gc.DrawEllipse(x + 0.5, cy - 5.5, 11, 11)
            gc.StrokeLine(x + 6, cy, x + 6, cy - 3.5)
            gc.StrokeLine(x + 6, cy, x + 8.5, cy + 1.5)
        elif icon == 'search':
            gc.DrawEllipse(x + 0.5, cy - 5.5, 8, 8)
            gc.StrokeLine(x + 7.5, cy + 1.5, x + 11.5, cy + 5.5)
        elif icon == 'star':
            path = gc.CreatePath()
            for k in range(10):
                radius = 6.0 if k % 2 == 0 else 2.6
                angle = math.pi * (k / 5.0 - 0.5)
                px, py = x + 6 + radius * math.cos(angle), cy + 0.5 + radius * math.sin(angle)
                if k == 0:
                    path.MoveToPoint(px, py)
                else:
                    path.AddLineToPoint(px, py)
            path.CloseSubpath()
            gc.StrokePath(path)
        elif icon == 'radio':
            # a mast and its waves (the outer 7.5 round: wider than the other icons)
            gc.StrokeLine(x + 6, cy - 1, x + 6, cy + 5.5)
            gc.DrawEllipse(x + 4.5, cy - 3.5, 3, 3)
            for r in (4.0, 6.5):
                for side in (-1, 1):
                    path = gc.CreatePath()
                    start = math.radians(-40 if side > 0 else 140)
                    path.AddArc(x + 6, cy - 2, r, start, start + math.radians(80), True)
                    gc.StrokePath(path)

    def DrawTabPolygon(self, dc):
        # the close mark on the hovered tab only (it stood on the selected one too), drawn
        # (the bitmap was dark, for the light block the selected tab was): dimmed; under the
        # mouse, full on a key's face; pressed, on the pressed face; its room kept on every
        # row (DrawTabText: the title not cut again as it comes and goes)
        size = 6
        # 9 px from the row's right end, as the icon from its left (11 before: asked
        # closer), under the header's + (moved with it); its hover face 4 px round it
        right_align = 4 + self.scrollbar_size
        close_rects = []
        fg, dim = self.GetColours()[:2]
        tokens = macroboxstyle.current().UI
        hovered, downed = getattr(self, 'close_state', (None, None))
        titles = self.GetTabsTitles()
        for i, rect in enumerate(self.rects):
            if rect.height <= 0 or titles[i] in radio.RADIO_TABS:
                # the radio's tabs are not closed (the favorites would go with it)
                close_rects.append(wx.Rect(0, 0, 0, 0))
                continue
            offset_x = rect.x + rect.width - size - right_align
            offset_y = rect.y + (rect.height - size) // 2
            close_rects.append(wx.Rect(offset_x - 3, offset_y - 3, size + 6, size + 6))
            if i == self.cache.tabIdx:
                face = tokens.CONTROL_DOWN if downed == i else tokens.CONTROL_HOVER\
                    if hovered == i else None
                if face is not None:
                    dc.SetPen(wx.TRANSPARENT_PEN)
                    dc.SetBrush(wx.Brush(wx.Colour(face)))
                    dc.DrawRoundedRectangle(offset_x - 4, offset_y - 4, size + 9,
                                            size + 9, uikit.RADIUS)
                sink = 1 if downed == i else 0
                offset_y += sink
                dc.SetPen(wx.Pen(fg if face is not None else dim, 1))
                dc.DrawLine(offset_x, offset_y, offset_x + size + 1, offset_y + size + 1)
                dc.DrawLine(offset_x, offset_y + size, offset_x + size + 1, offset_y - 1)
        self.close_rects = close_rects

    def SetCurrentSection(self, headers):
        '''as a web page's sticky headers: the box over the sidebar the top of one view with
        the rows, the section scrolled into named there once its header has gone up into
        it, and the next one's header, coming up into it, pushing it out (its top in the
        box, the rest in the rows: one header). named there while its header still showed
        whole under it, LIBRARY read twice ("not as the web does", the user); the box drawn
        again as it changes'''
        box = getattr(self.parent, 'TabHeader', None)
        band = box.GetSize().height if box is not None else self.HEADER_HEIGHT
        current, following = ('Playlists', 'playlists'), None
        for y, label, kind in headers:
            if y + band > 0:
                if y < 0:
                    following = (label, kind, int(y) + band)
                break
            current = (label, kind)
        self.current_section = current
        self.following_section = following
        if box is not None and getattr(box, 'drawn_sticky', None) != (current, following):
            box.reInitBuffer = True
            box.DirectDraw()

    def GetFollowingSection(self):
        # (name, kind, its top in the box) of the next section's header coming up into the
        # box over the sidebar, else None
        return getattr(self, 'following_section', None)

    def GetCurrentSection(self):
        # (name, kind) of the section the sidebar is scrolled into
        return getattr(self, 'current_section', ('Playlists', 'playlists'))

    def DrawHeaders(self, dc):
        # the section names dimmed, in capitals (as the list's header), each on a band as
        # PLAYLISTS' header is (its ground, the line over it, its name placed as there):
        # on the rows' ground they looked another kind of thing
        width = self.GetClientSize().width
        for y, label, kind in self.headers:
            self.DrawHeader(dc, y, label, kind, 0, width)

    def DrawHeader(self, dc, y, label, kind, x, width):
        # a section's header from (x, y) (the box over the sidebar draws the top of one coming
        # up into it: its x the rows')
        dim = self.GetColours()[1]
        font = uikit.get_font(10)
        caps = uikit.get_caps_ink(font)
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(self.parent.st.HEADER_BG_COLOR))
        dc.DrawRectangle(x, int(y), width, self.HEADER_HEIGHT)
        dc.SetPen(wx.Pen(self.parent.st.HEADER_PN_COLOR, 1))
        dc.DrawLine(x, int(y), x + width, int(y))
        dc.SetFont(font)
        dc.SetTextForeground(dim)
        top = int(round(uikit.get_caps_top(font, y + 2, self.HEADER_HEIGHT - 2))) + 1
        dc.DrawText(label.upper(), x + self.HEADER_X, top)
        draw_fold_mark(dc, x + self.HEADER_X + dc.GetTextExtent(label.upper())[0] + 6,
                       top + caps[0] + caps[1] / 2.0, is_section_folded(kind), dim)

    def HandleEventSectionFold(self, event):
        # a section's name clicked: its rows folded or opened (toggle_section)
        if event.LeftDown is False or self.onClient is False:
            return False
        for y, label, kind in self.headers:
            if kind is not None and y <= event.Y < y + self.HEADER_HEIGHT:
                toggle_section(kind)
                self.reInitBuffer = True
                self.parent.SliderV.reInitBuffer = True
                return True
        return False

    def IsOverFavorites(self, y):
        # y on the Favorites row (its tab, or its row before the tab is made)
        titles = self.GetTabsTitles()
        if radio.RADIO_TITLE in titles:
            rect = self.rects[titles.index(radio.RADIO_TITLE)]
        else:
            rect = self.virtual_entries.get(radio.RADIO_TITLE)
        return rect is not None and rect.height > 0 and rect.y <= y <= rect.y + rect.height

    def HandleEventRadioEntries(self, event):
        # a radio row clicked: its tab made when it is not there, selected; Browse with
        # nothing in it reads the most voted
        if event.LeftDown is False or self.onClient is False:
            return
        titles = self.GetTabsTitles()
        clicked = [title for title, rect in self.virtual_entries.items()
                   if self.IsInRect(rect, (event.X, event.Y))]
        clicked += [titles[i] for i, rect in enumerate(self.rects)
                    if (titles[i] in radio.RADIO_TABS
                        or titles[i] in (library.FAVORITES_TITLE, library.RECENT_TITLE))
                    and self.IsInRect(rect, (event.X, event.Y))]
        if not clicked:
            return
        mainpanel = self.parent.parent
        if clicked[0] == library.FAVORITES_TITLE:
            # the starred songs as they are now, their tab selected
            library.show_favorites(mainpanel.ListBox)
            self.reInitBuffer = True
            return
        if clicked[0] == library.RECENT_TITLE:
            library.show_recent(mainpanel.ListBox)
            self.reInitBuffer = True
            return
        if clicked[0] == radio.RECENT_TITLE:
            radio.show_recent(mainpanel)
            self.reInitBuffer = True
            return
        index = radio.open_tab(mainpanel.ListBox, clicked[0])
        mainpanel.ListBox.SetSelectedList(index)
        if clicked[0] == radio.BROWSE_TITLE and not mainpanel.ListBox.innerList[index].items:
            radio.browse(mainpanel, 'Top voted', lambda: radio.get_stations())
        self.reInitBuffer = True

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
        if self.HandleEventSectionFold(event):
            return
        self.HandleEventRadioEntries(event)
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
        # the x under the mouse, and held down on it (DrawTabPolygon)
        downed = event.down.closeIdx if event.LeftIsDown\
            and event.down.closeIdx == event.closeIdx else None
        state = (event.closeIdx, downed)
        if state != getattr(self, 'close_state', (None, None)):
            self.close_state = state
            self.reInitBuffer = True
        if event.LeftUp is False:
            return
        if event.closeIdx is None:
            return
        if event.down.closeIdx is None:
            return
        # asked first (a click on the x deleted the playlist at once)
        if confirm_delete_tab(self, event.down.closeIdx) is False:
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

        # (on a header: no row under it hit)
        if any(top <= y < top + self.HEADER_HEIGHT for top, _, _ in self.headers):
            return None
        for i, rect in enumerate(self.rects):
            if self.IsInRect(rect, xy):
                return i
        return None

    def GetInsertTabRectIdx(self, xy):
        # between the playlists only (the library's and the radio's tabs are in their own
        # sections, whatever their place in the tabs)
        if self.onClient is False or not self.normal_tabs:
            return None
        xy = wx.Point(*xy)
        rects = [(i, self.rects[i]) for i in self.normal_tabs]
        last = None
        for k, (i, r) in enumerate(rects):
            offsetY = 0 if k == 0 else rects[k - 1][1].y + rects[k - 1][1].height * 0.5
            finishY = r.y + r.height * 0.5
            rect = wx.Rect(round(r.x), round(offsetY), round(r.width), round(finishY - offsetY))
            if self.IsInRect(rect, xy):
                return i
            last = (i, r)
        i, r = last
        offsetY = r.y + r.height * 0.5
        rect = wx.Rect(round(r.x), round(offsetY), round(r.width), round(r.height))
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
        length = self.parent.GetContentHeight()
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
        knob = wx.Rect(0, round(y), round(width), round(h))
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
        length = self.parent.GetContentHeight()
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
            self.items = ['Rename', '', 'Delete Playlist']
        else:
            self.items = ['Rename', '', 'Delete Playlist', 'Import Tracks', 'Export Playlist']
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
            # x, y, w, h = self.parent.parent.parent.DialogBox.ApplyButton.GetRect()
            # self.parent.parent.parent.DialogBox.ApplyButton.SetRect((
            #     width - w, 0, w, h))
            self.parent.parent.parent.DialogBox.ShowModal()
            self.parent.parent.parent.DialogBox.Destroy()
            self.parent.parent.parent.DialogBox = None
            self.parent.DirectDraw()
        if event.GetId() == 3:
            selectedList = self.parent.parent.parent.ListBox.selectedList
            if confirm_delete_tab(self.parent, selectedList):
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


class TabDeleteBox(ConfirmDialogBox):

    # a playlist's deleting asked: Delete (the accent) or Cancel; confirmed when Delete
    def __init__(self, parent, title, count, answer):
        ConfirmDialogBox.__init__(self, parent)
        self.answer = answer
        self.SetTitle('Delete Playlist')
        self.ApplyButton.SetLabelText('Delete')
        # its message two lines tall, a text of its own (the box's sized itself to one)
        self.Message.Hide()
        self.Text = wx.StaticText(self, label='Delete "%s" (%d tracks)?\nThe files stay where '
                                  'they are.' % (title, count),
                                  style=wx.ALIGN_CENTER_HORIZONTAL | wx.ST_NO_AUTORESIZE)
        self.Text.SetForegroundColour(macroboxstyle.current().UI.TEXT)
        self.Text.SetFont(uikit.get_font(uikit.BODY))
        # two lines PAD in (the dialogs' spacing), the footer under them
        self.SetClientSize((340, DIALOG_PAD * 2 + 40 + self.GetFooterHeight()))
        self.OnSize(None)

    def OnSize(self, event):
        ConfirmDialogBox.OnSize(self, event)
        if getattr(self, 'Text', None) is not None:
            width, height = self.GetClientSize()
            self.Text.SetRect((DIALOG_PAD, DIALOG_PAD, width - DIALOG_PAD * 2, 40))

    def OnApply(self, event):
        # (told by a list of its caller's: the box is gone when ShowModal returns)
        self.answer.append(True)
        self.OnClose(event)


def confirm_delete_tab(tablist, index):
    # True when the playlist at index is to be deleted (asked over the player)
    listbox = tablist.parent.parent.ListBox
    inner = listbox.innerList[index]
    answer = []
    box = TabDeleteBox(tablist, inner.title, len(inner.items), answer)
    frame = wx.GetTopLevelParent(tablist)
    x, y, w, h = frame.GetRect()
    bw, bh = box.GetSize()
    box.SetPosition((x + (w - bw) // 2, y + (h - bh) // 2))
    box.ShowModal()
    return bool(answer)


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
