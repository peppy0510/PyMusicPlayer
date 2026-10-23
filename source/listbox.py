# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import ctypes
import glob
import images
import io
import library
import listimages
import macroboxstyle
import math
import os
import radio
import stat
import subprocess
import sys
import threading
import time
import uikit
import webbrowser
import webinfo
import wx

from listboxlib import FileOpenDialog
from listboxlib import FileSaveDialog
from listboxlib import ListBoxListDnD
from listboxlib import ListControl
from listboxtab import ListBoxPopupTab
from listboxtab import ListBoxPopupTabAdd
from listboxtab import ListBoxTab
from listboxtab import ListBoxTabDnD
from listboxtab import ListBoxTabSliderV
from listboxtab import TabRenameBox
from macroboxlib import Button
from macroboxlib import CheckBox
from macroboxlib import COLOR_STATUS_BG
from macroboxlib import ComboBox
from macroboxlib import NativeComboBox
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
from macroboxlib import EVT_GLOBAL
from macroboxlib import FONT_ITEM
from macroboxlib import FONT_ITEM_SIZE
from macroboxlib import FONT_PLAYINFO
from macroboxlib import GetPreference
from macroboxlib import GetPreferences
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
        self.SetBackgroundColour(self.st.BG_COLOR)

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
            dc.DrawRectangleList(rects, pens=wx.Pen(color, 1), brushes=wx.Brush(color))
        # color = self.st.SCROLLBAR_BG_COLOR
        # if self.is_slider_h_shown and self.is_slider_v_shown:
        #   rects = ((width-ss, height-ss, ss, ss),)
        #   dc.DrawRectangleList(rects,\
        #       pens=wx.Pen(color, 1), brushes=wx.Brush(color))

        self.List.reInitBuffer = True
        self.Header.reInitBuffer = True
        self.SliderH.reInitBuffer = True
        self.SliderV.reInitBuffer = True

        lines = [(0, 0, 0, self.GetSize().height)]
        color = self.st.HEADER_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 1))

    # Buffered DC

    def OnSize(self, event=None):
        self.Freeze()
        # auto width reads the header size, so hand it the new rect first
        self.SetRectPre()
        self.Header.SetAutoColumnWidth()
        self.DirectDraw()
        self.List.DirectDraw()
        self.Header.DirectDraw()
        self.SliderH.DirectDraw()
        self.SliderV.DirectDraw()
        self.DirectDraw()
        # drawn just above: not again when idle (the draw before this one asks it,
        # SetRectDraw), or a step of a sash dragged drew the list twice
        self.List.reInitBuffer = False
        self.Header.reInitBuffer = False
        self.SliderH.reInitBuffer = False
        self.SliderV.reInitBuffer = False
        self.Thaw()

    def __del__(self):
        pass


# the files whose comment was read (fill_comments: once a file, a session)
COMMENTS_READ = set()


def fill_comments(listbox):
    '''the comment column's values read for the rows made before it was (their files' ID3
    COMM), on a thread, put in every tab's rows with the same file when read'''
    inner = listbox.innerList[listbox.selectedList]
    keys = [v.key for v in inner.columns]
    if 'comment' not in keys or 'path' not in keys:
        return
    pathIdx = keys.index('path')
    paths = [item[pathIdx] for item in inner.items
             if item[pathIdx] not in COMMENTS_READ and not audio.is_stream_path(item[pathIdx])]
    if not paths:
        return

    def read():
        found = {}
        for path in paths:
            tags = audio.get_id3(path, [u'COMM'])
            found[path] = (tags or {}).get(u'COMM', u'')
        wx.CallAfter(put, found)

    def put(found):
        COMMENTS_READ.update(found)
        for each in listbox.innerList:
            keys = [v.key for v in each.columns]
            if 'comment' not in keys or 'path' not in keys:
                continue
            ci, pi = keys.index('comment'), keys.index('path')
            for rows in (each.items, getattr(each, 'filterCache', None) or []):
                for i, row in enumerate(rows):
                    if row[pi] in found and found[row[pi]] != row[ci]:
                        rows[i] = tuple(row[:ci]) + (found[row[pi]],) + tuple(row[ci + 1:])
        listbox.reInitBuffer = True

    threading.Thread(target=read, daemon=True).start()


def toggle_favorite_tracks(listbox, paths):
    # songs starred or let go: the favorites' tab (when open) as they are now, told
    starred = library.toggle_favorite_tracks(paths)
    if any(v.title == library.FAVORITES_TITLE for v in listbox.innerList):
        selected = listbox.selectedList
        library.show_favorites(listbox)
        listbox.SetSelectedList(selected)
    listbox.reInitBuffer = True
    listbox.List.reInitBuffer = True
    mainpanel = listbox.parent
    mainpanel.ListTab.TabList.reInitBuffer = True
    radio.tell(mainpanel, 'Added to Favorite tracks' if starred else 'Removed from Favorite tracks')


def draw_analysis_icon(dc, cx, cy, working, r=4.0, alpha=255):
    # a song's analysis: under way (a ring three quarters round, the accent) or waiting (a
    # ring of dots, dimmed), 9 px across; see-through by alpha (under the playing mark)
    tokens = macroboxstyle.current().UI

    def ink(name):
        c = uikit.colour(getattr(tokens, name))
        return wx.Colour(c.Red(), c.Green(), c.Blue(), alpha)
    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        return
    if working:
        # turning, a turn in 1.2 s (the list drawn again for it while songs are analysed)
        start = math.radians((time.time() % 1.2) / 1.2 * 360.0)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink('ACCENT')).Width(1.8)))
        path = gc.CreatePath()
        path.AddArc(cx, cy, r, start, start + math.radians(270), True)
        gc.StrokePath(path)
        return
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(ink('BAR_TEXT_DIM'))))
    dots = 8 if r <= 4.0 else 12
    for k in range(dots):
        angle = math.radians(k * 360.0 / dots)
        gc.DrawEllipse(cx + r * math.cos(angle) - 0.9, cy + r * math.sin(angle) - 0.9, 1.8, 1.8)


def draw_star(dc, cx, cy, r, colour):
    # a five-pointed star, filled (a favorite station)
    points = []
    for k in range(10):
        radius = r if k % 2 == 0 else r * 0.45
        angle = math.pi / 2 + k * math.pi / 5
        points.append((int(round(cx + radius * math.cos(angle))),
                       int(round(cy - radius * math.sin(angle)))))
    dc.SetPen(wx.Pen(colour, 1))
    dc.SetBrush(wx.Brush(colour))
    dc.DrawPolygon(points)


def draw_star_outline(dc, cx, cy, r, colour):
    # a song not starred: the star's outline, faint (where a click stars it), smoothed
    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        return
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour).Width(1)))
    path = gc.CreatePath()
    for k in range(10):
        radius = r if k % 2 == 0 else r * 0.45
        angle = math.pi / 2 + k * math.pi / 5
        x, y = cx + radius * math.cos(angle), cy - radius * math.sin(angle)
        if k == 0:
            path.MoveToPoint(x, y)
        else:
            path.AddLineToPoint(x, y)
    path.CloseSubpath()
    gc.StrokePath(path)


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
                    # the cell's editor ground, as the editor is (it was white under the
                    # dark editor)
                    edit_bg = macroboxstyle.current().UI.EDIT_BG
                    dc.DrawRectangleList(((x, y, w + 1, h),),
                                         pens=wx.Pen(edit_bg, 0), brushes=wx.Brush(edit_bg))
                    w = column.width - 8
                    if w > rect.width - x:
                        w = rect.width - x
                    self.TextEdit.SetRect(wx.Rect(x + 5, y + 3, w - 1, h - 4))
                    return

    def GetMonoFont(self):
        # the list font's height in the monospace
        font = wx.Font(wx.Size(0, self.parent.font.GetPixelSize().height), wx.FONTFAMILY_MODERN,
                       wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
        return font

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
        # the numbers (the right-aligned columns: order, duration, tempo) in the display's
        # monospace, so their digits line up row under row; on the text's baseline
        mono = self.GetMonoFont()
        _, mh, descent, _ = dc.GetFullTextExtent(u'0', mono)
        _, fh, fdescent, _ = dc.GetFullTextExtent(u'0', self.parent.font)
        mono_shift = (fh - fdescent) - (mh - descent)
        mono_width = dc.GetFullTextExtent(u'0', mono)[0]
        m_texts, m_xys, ms_texts, ms_xys = [], [], [], []

        listIdx = self.parent.selectedList
        shownColIdx = self.parent.GetShownColumnsIdx()
        shownItemIdx = self.parent.GetShownItemsIdx()
        orderIdx = self.parent.GetColumnKeyToIdx('order')
        statusIdx = self.parent.GetColumnKeyToIdx('status')
        # itemslen = len(self.parent.innerList[listIdx].items)
        listColumns = self.parent.innerList[listIdx].columns
        self.KeepOrderRoom(listColumns, orderIdx, mono_width, left_margin)
        pictures = list()
        for row, item in enumerate(shownItemIdx):

            for i, col in enumerate(shownColIdx):
                column = columns[i]
                if item > len(self.parent.innerList[listIdx].items):
                    continue
                # a cover or a waveform: drawn after the text, over the row's ground
                if listColumns[col].key in ('cover', 'wave'):
                    pictures.append((listColumns[col].key, row, item, column))
                    continue

                string = self.parent.innerList[listIdx].items[item][col]
                right_align = self.parent.innerList[listIdx].columns[col].right_align
                if col == statusIdx:
                    continue
                # limitedString = self.LimitTextLength(\
                #   dc, string, column.width-left_margin-15, tww)
                if right_align:
                    # cut by the monospace digits it is drawn in (measured in the list's
                    # font it came out wider and ran left over the column before it)
                    string = '%s' % (string)
                    fits = max(int((column.width - left_margin - 8) // mono_width), 0)
                    limitedString = string if len(string) <= fits\
                        else string[:max(fits - 1, 0)] + '\u2026'
                    tw = mono_width * len(limitedString)
                    txy = (column.x + column.width - left_margin - tw,
                           row_size * row + rect.y + top_margin - row_offset + mono_shift)
                    texts, xys = (ms_texts, ms_xys) if self.parent.IsHighlightedItem(item)\
                        else (m_texts, m_xys)
                    texts.append(limitedString)
                    xys.append(txy)
                    continue
                limitedString = self.LimitTextLength(
                    dc, string, column.width - left_margin - 8, tww)
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
                s_rects.append((rect.x, row_size * row + rect.y -
                                row_offset + 1, width, row_size - 1))
            else:
                n_rects.append((rect.x, row_size * row + rect.y - row_offset, width, row_size))

                if shownItemIdx[row] % 2 == 0:
                    n_rects_odd.append((rect.x + 1, row_size * row + rect.y -
                                        row_offset, width - 1, row_size))
                else:
                    n_rects_even.append((rect.x + 1, row_size * row + rect.y -
                                         row_offset, width - 1, row_size))

        if shownItemIdx != []:
            lines.append((rect.x, row_size * (row + 1) + rect.y - row_offset,
                          width, row_size * (row + 1) + rect.y - row_offset))

        def limitcolor(v):
            if v > 255:
                return 255
            if v < 0:
                return 0
            return v
        ct = self.parent.st.LIST_BG_CONTRAST
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
        # the selected rows' bar at the left, in the accent
        bar = self.parent.st.SELECTED_BAR_COLOR
        dc.DrawRectangleList([(x, y, 3, h) for x, y, w, h in s_rects],
                             pens=wx.Pen(bar, 1), brushes=wx.Brush(bar))

        sel_bgcolor = self.parent.st.SELECTED_BG_COLOR
        r, g, b = self.parent.st.LIST_FG_COLOR
        dc.DrawTextList(n_texts, n_xys, foregrounds=wx.Colour(r, g, b))
        r, g, b = self.parent.st.SELECTED_FG_COLOR
        dc.DrawTextList(s_texts, s_xys, foregrounds=wx.Colour(r, g, b))
        dc.SetFont(mono)
        dc.DrawTextList(m_texts, m_xys, foregrounds=wx.Colour(*self.parent.st.LIST_FG_COLOR))
        dc.DrawTextList(ms_texts, ms_xys,
                        foregrounds=wx.Colour(*self.parent.st.SELECTED_FG_COLOR))
        dc.SetFont(self.parent.font)
        color = self.parent.st.LIST_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 0))
        self.DrawPictures(dc, pictures, listIdx, row_size, rect.y - row_offset,
                          bgcolor_odd, bgcolor_even, shownItemIdx)

        # draw status column
        procpath = self.parent.parent.MFEATS.GetProcPath()
        # waiting in the queue: red too, analyzed before or not (a song analyzed
        # by an older version waits for its analysis again)
        taskpath = set(self.parent.parent.MFEATS.GetTaskPath())
        pathIdx = self.parent.GetColumnKeyToIdx('path')
        # the radio's Browse tab: the stations in the favorites starred
        # starred: the stations in the radio's favorites (Browse), the songs in the
        # favorite tracks (every playlist's rows)
        favorites = set()
        # the songs and Browse's stations not starred: an outline, faint (the Favorites'
        # rows none: all of them are)
        outline = None
        if self.parent.innerList[listIdx].title != radio.RADIO_TITLE:
            bg = wx.Colour(self.parent.st.LIST_BG_COLOR)
            fg = wx.Colour(self.parent.st.LIST_FG_COLOR)
            outline = wx.Colour(*[int(a + (b - a) * 0.22) for a, b in
                                  zip(bg.Get()[:3], fg.Get()[:3])])
        if self.parent.innerList[listIdx].title in (radio.BROWSE_TITLE, radio.RECENT_TITLE):
            favorites = radio.get_favorite_urls(self.parent)
        elif self.parent.innerList[listIdx].title not in radio.RADIO_TABS:
            favorites = set(library.get_favorite_tracks())
        for row, item in enumerate(shownItemIdx):
            for i, col in enumerate(shownColIdx):
                if col != orderIdx:
                    continue
                # 5 px right of the playing mark's ring (MARK_X)
                cx = columns[i].x + self.STAR_X
                # 1 px over the row's middle (a star's ink is low in its box: it looked low at
                # +1, high at -1)
                cy = row_size * row + rect.y - row_offset + row_size // 2
                star = 4 if item == getattr(self, 'star_down', None) else 5
                if self.parent.innerList[listIdx].items[item][pathIdx] in favorites:
                    draw_star(dc, cx, cy, star, macroboxstyle.current().UI.WARN)
                elif item == getattr(self, 'star_hover', None):
                    # under the pointer: where a click stars it
                    draw_star(dc, cx, cy, star, macroboxstyle.current().UI.BAR_TEXT_DIM)
                elif outline is not None:
                    draw_star_outline(dc, cx + 0.5, cy + 0.5, 5, outline)
                # analyzing status
                status = self.parent.innerList[listIdx].items[item][statusIdx]
                # rects = (columns[i].x+1, row_size*row+rect.y-row_offset+1,\
                #   columns[i].width-2-22, row_size-1)
                rects = (columns[i].x + 1, row_size * row +
                         rect.y - row_offset + 1, 4, row_size - 1)
                # elif status == 'analyzing':
                #   dc.DrawRectangleList((rects,), pens=wx.Pen((80,80,255), 0),\
                #       brushes=wx.Brush(wx.Colour(100,100,255)))
                # as icons where the playing mark goes (none on the playing row): being
                # analysed a ring three quarters drawn in the accent, waiting a dotted ring
                # dimmed (told by their shapes, not by red and blue bars)
                path = self.parent.innerList[listIdx].items[item][pathIdx]
                # on the play mark's centre (its 9 rows from int((row_size - 8) / 2): the
                # middle row's middle), a half row off by row_size / 2 in an even row
                cy = row_size * row + rect.y - row_offset + int((row_size - 8) * 0.5) + 4.5
                # (the playing row's its own size, the playing mark half see-through over it:
                # a wider ring round the mark looked off centre)
                analysing = path in procpath or status == '' or path in taskpath
                if path in procpath:
                    draw_analysis_icon(dc, columns[i].x + self.MARK_X + 4, cy, True)
                elif status == '' or path in taskpath:
                    draw_analysis_icon(dc, columns[i].x + self.MARK_X + 4, cy, False)
                elif status == 'error':
                    if self.parent.IsHighlightedItem(item):
                        bmp = images.listbox_brokenlink_black.GetBitmap()
                    else:
                        bmp = images.listbox_brokenlink_red.GetBitmap()
                    m = int((row_size - bmp.GetHeight()) * 0.5) - 1
                    dc.DrawBitmap(bmp, rects[0], rects[1] + m, useMask=False)
                # playing status: in the tab it was played from; a station's in every tab
                # (the same stream wherever its row is)
                if self.parent.parent.PlayBox.cue.listId\
                        != self.parent.innerList[listIdx].Id\
                        and audio.is_stream_path(self.parent.parent.PlayBox.cue.path) is False:
                    continue
                if self.parent.innerList[listIdx].items[item][pathIdx]\
                        != self.parent.parent.PlayBox.cue.path:
                    continue
                column = columns[i]
                font_color = self.parent.st.LIST_FG_COLOR
                if self.parent.IsHighlightedItem(item):
                    font_color = self.parent.st.SELECTED_FG_COLOR
                # while it starts (a file opening, a station connecting) the playing mark
                # held: it was let go after a frame and taken again at the next event, the
                # mark and the stopped square in turns
                playbox = self.parent.parent.PlayBox
                starting = playbox.AudioControl.pending\
                    or playbox.GetStreamConnecting() is not None
                if playbox.IsStreamWaiting():
                    # a station connecting or filling its buffer: the turning ring in the
                    # mark's place (its mark once it sounds), as the analysing song's
                    self.pending.SkipStopIcon = False
                    offset = int((row_size - 8) * 0.5)
                    draw_analysis_icon(dc, column.x + self.MARK_X + 4,
                                       row_size * row + rect.y - row_offset + offset + 4.5, True)
                elif playbox.IsPlaying() or starting\
                        or self.pending.SkipStopIcon and status != 'error':
                    self.pending.SkipStopIcon = False
                    if sum(font_color) / 3.0 > 125:
                        bmp = self.bmp.playing.white
                    else:
                        bmp = self.bmp.playing.black
                    offset = int((row_size - 8) * 0.5)
                    mx = column.x + self.MARK_X
                    my = row_size * row + rect.y - row_offset + offset
                    if analysing:
                        # over the analysis icon: cut out of it by a pixel of the row's
                        # ground round it, its own colour kept (see-through, it took the
                        # ring's blue and the ground's grey)
                        halo = self.GetHalo(bmp, self.GetRowGround(item, row, shownItemIdx,
                                                                   bgcolor_odd, bgcolor_even))
                        for dx, dy in self.HALO_STEPS:
                            dc.DrawBitmap(halo, mx + dx, my + dy, useMask=False)
                    dc.DrawBitmap(bmp, mx, my, useMask=False)
                else:
                    # its centre the play mark's (9 px, centred on MARK_X + 4)
                    x = column.x + self.MARK_X + 1
                    offset = int((row_size - 8) * 0.5)
                    y = row_size * row + rect.y - row_offset + offset + 1
                    w, h = (7, 7)
                    if analysing:
                        # cut out of the icon as the playing mark is
                        ground = self.GetRowGround(item, row, shownItemIdx, bgcolor_odd,
                                                   bgcolor_even)
                        dc.SetPen(wx.Pen(ground, 1))
                        dc.SetBrush(wx.Brush(ground))
                        dc.DrawRectangle(x - 1, y - 1, w + 2, h + 2)
                    dc.DrawRectangleList([(x, y, w, h)], pens=(wx.Pen(font_color, 1),),
                                         brushes=(wx.Brush(font_color),))
                break

    # the playing mark's cut-out: its shape a pixel round it, every way
    HALO_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))

    def GetRowGround(self, item, row, shownItemIdx, odd, even):
        # the row's ground: selected, or its stripe's
        if self.parent.IsHighlightedItem(item):
            return wx.Colour(self.parent.st.SELECTED_BG_COLOR)
        return wx.Colour(*(odd if shownItemIdx[row] % 2 == 0 else even)[:3])

    def GetHalo(self, bmp, ground):
        # the mark's shape in the ground's colour (made once a mark and a ground)
        cache = self.__dict__.setdefault('halos', {})
        key = (id(bmp), ground.Get()[:3])
        if key not in cache:
            image = bmp.ConvertToImage()
            if not image.HasAlpha():
                image.InitAlpha()
            r, g, b = ground.Get()[:3]
            image.SetRGB(wx.Rect(0, 0, image.GetWidth(), image.GetHeight()), r, g, b)
            cache[key] = (bmp, image.ConvertToBitmap())
        return cache[key][1]

    WAVE_DIM = 0.55

    # between the star's right and the order's first digit
    ORDER_GAP = 6

    def KeepOrderRoom(self, columns, orderIdx, digit, margin):
        # the # column widened when its numbers would run into the marks before them (the
        # playing mark, the star: STAR_X) as the list grows (100, 1000 rows); the file
        # name's column gives the room
        if orderIdx is None or orderIdx < 0:
            return
        count = len(self.parent.innerList[self.parent.selectedList].items)
        need = self.STAR_X + 5 + self.ORDER_GAP + digit * len(str(max(count, 1))) + margin
        column = columns[orderIdx]
        if column.show and column.width < need:
            column.width = need
            wx.CallAfter(self.parent.Header.SetAutoColumnWidth)
    # the # column's marks: the playing mark's left (9 px wide, its ring 6.5 round its
    # centre, clear of the selection bar's 3 px by 2.5) and the star's centre
    MARK_X = 8
    STAR_X = 29

    def DrawPictures(self, dc, pictures, listIdx, row_size, top, bgcolor_odd, bgcolor_even,
                     shownItemIdx):
        if pictures == []:
            return
        if getattr(self, 'images', None) is None:
            self.images = listimages.ListImages(self.parent.parent.MFEATS.RequestListRedraw)
        items = self.parent.innerList[listIdx].items
        mdxIdx = self.parent.GetColumnKeyToIdx('mdx')
        pathIdx = self.parent.GetColumnKeyToIdx('path')
        selected = self.parent.st.SELECTED_BG_COLOR
        # the waveforms quieted but the playing song's (a column of them drew the eye before
        # the titles did): their row's ground over them at WAVE_DIM
        cue = self.parent.parent.PlayBox.cue
        playing = cue.path if cue.listId == self.parent.innerList[listIdx].Id else None
        gc = None
        for kind, row, item, column in pictures:
            if item >= len(items):
                continue
            if self.parent.IsHighlightedItem(item):
                ground = selected
            else:
                ground = bgcolor_odd if shownItemIdx[row] % 2 == 0 else bgcolor_even
            width, height = (column.width - 4, row_size - 2)
            if width < 4 or height < 4:
                continue
            bitmap = self.images.GetBitmap(kind, items[item][mdxIdx], items[item][pathIdx],
                                           width, height, ground)
            if bitmap:
                x, y = column.x + 2, row_size * row + top + 1
                dc.DrawBitmap(bitmap, x, y)
                if kind == 'wave' and items[item][pathIdx] != playing:
                    gc = gc or wx.GraphicsContext.Create(dc)
                    gc.SetPen(wx.NullGraphicsPen)
                    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(
                        *ground[:3], int(255 * self.WAVE_DIM)))))
                    gc.DrawRectangle(x, y, bitmap.GetWidth(), bitmap.GetHeight())

    def DrawInsertItemLine(self, dc):
        row_size = self.parent.GetRowsHeight()
        vpy = self.parent.GetVirtualPositionY()
        itemsLength = self.parent.GetItemsLength()
        shownItemsIdx = self.parent.GetShownItemsIdx()
        row_offset = abs(vpy) % row_size - 0
        rows = [i for i, v in enumerate(shownItemsIdx)
                if v == self.FileDrop.insertItemIdx]
        if self.FileDrop.insertItemIdx == itemsLength:
            rows = [len(shownItemsIdx)]
        if len(rows) == 0:
            return
        x = self.parent.GetVirtualPositionX() - 1
        w = self.parent.GetVirtualPositionXW() + 2
        y = row_size * rows[0] - row_offset - 1
        y = y - 1 if itemsLength == self.FileDrop.insertItemIdx else y
        color = self.parent.st.INSERTITEM_CURSOR_COLOR
        dc.DrawRectangleList(((x, y, w, 3),), pens=wx.Pen((20, 20, 20)), brushes=wx.Brush((*color, 255)))

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

    def GetStarSpan(self):
        # the # column's star (x from, to: right of the playing mark), None without it
        x = self.parent.GetVirtualPositionX()
        for column in self.parent.GetShownColumns():
            if column.key == 'order':
                return (x + self.STAR_X - 7, x + self.STAR_X + 8)
            x += column.width
        return None

    def GetStarItem(self, event):
        # the song (or a Browse row's station) under the pointer in the star's span, None
        # elsewhere (or in the Favorites: all starred, taken out by their menu)
        if self.onClient is False:
            return None
        if self.parent.innerList[self.parent.selectedList].title == radio.RADIO_TITLE:
            return None
        span = self.GetStarSpan()
        if span is None or not span[0] <= event.X <= span[1]:
            return None
        item = self.parent.PosY2Item(event.Y)
        if item < 0 or item >= self.parent.GetItemsLength():
            return None
        return item

    def HandleEventStar(self, event):
        # a click on a song's star: starred or let go (not selected); its star shown dimmed
        # under the pointer before (True: the click was the star's)
        # held down on it: drawn smaller, pressed in, till let go (the press the rows'
        # selection and drag do not take)
        item = self.GetStarItem(event)
        down = getattr(self, 'star_down', None)
        if down is not None and event.LeftIsDown is False:
            self.star_down = down = None
            self.reInitBuffer = True
        if item != getattr(self, 'star_hover', None):
            self.star_hover = item
            self.reInitBuffer = True
        if down is not None:
            return True
        if item is None or event.LeftDown is False:
            return False
        self.star_down = item
        self.reInitBuffer = True
        path = self.parent.GetItemValueByColumnKey(item, 'path')
        if self.parent.innerList[self.parent.selectedList].title in (radio.BROWSE_TITLE,
                                                                       radio.RECENT_TITLE):
            radio.toggle_favorite(self.parent.parent, path)
        else:
            toggle_favorite_tracks(self.parent, [path])
        return True

    # while songs are analysed or a station connects, the list drawn again this often (their icons turning: at 10
    # a second they turned in steps)
    SPIN_INTERVAL = 1.0 / 30

    def CATCH_EVT_GLOBAL(self, event):
        turning = self.parent.parent.MFEATS.GetProcPath()\
            or self.parent.parent.PlayBox.IsStreamWaiting()
        if turning and time.time() - getattr(self, 'spin_lap', 0.0) >= self.SPIN_INTERVAL:
            self.spin_lap = time.time()
            self.reInitBuffer = True
        if self.parent.parent.HasToSkipEvent():
            return
        if self.HandleEventStar(event):
            return
        self.HandleEventItemDrag(event)
        self.HandleEventFileDropPending(event)
        self.HandleEventFileDropFinish(event)
        self.HandleEventItemSelectionLeftIsDown(event)
        self.HandleEventItemSelectionRightIsDown(event)
        self.HandleEventItemSelectionLeftUp(event)
        self.HandleEventItemPopup(event)
        self.InitPendingEventState(event)
        # self.HandleEventTextEditDestroy(event)

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

    # def HandleEventTextEditDestroy(self, event):
    #     if self.TextEdit is None:
    #         return
    #     isInRect = self.IsInRect(self.TextEdit.GetRect(), (event.X, event.Y))
    #     if isInRect is False and event.RightDown or event.MiddleDown:
    #         self.TextEdit.destroy = True
    #     if self.TextEdit.destroy:
    #         self.TextEdit.Destroy()
    #         self.TextEdit = None
    #         # self.reInitBuffer = True
    #         self.DirectDraw()

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

        if namespace == 'playlist_toggle':
            self.parent.parent.parent.ToggleListTabShow()

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
        # drawn when idle (OnIdle), not at once: resized, it is drawn by the list box
        # laying out right after (ListBox.OnSize), and a step of a sash dragged drew
        # it twice, 16 ms each
        self.reInitBuffer = True


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

    # the file name's least width when the other columns take the room (the rest is
    # scrolled to)
    FILENAME_LEAST = 160

    def SetAutoColumnWidth(self):
        # the file name's column takes the room the other shown columns leave, each tab by
        # its own columns (it was the list's width less the first columns' widths: with the
        # cover and the waveform shown, those ran past the list's right edge)
        width, height = self.GetSize()
        for inner in self.parent.innerList:
            keys = [v.key for v in inner.columns]
            if 'filename' not in keys:
                continue
            idx = keys.index('filename')
            rest = sum(v.width for i, v in enumerate(inner.columns) if v.show is True and i != idx)
            inner.columns[idx].width = max(width - rest - 3, self.FILENAME_LEAST)
        self.parent.reInitBuffer = True

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

    def FitColumnWidth(self, idx):
        # the shown column idx as wide as its widest text, now (a measuring DC)
        bitmap = wx.Bitmap(1, 1)
        dc = wx.MemoryDC(bitmap)
        self.pending.autoColumnWidthIdx = idx
        self.SetAutoWidthColumn(dc)
        dc.SelectObject(wx.NullBitmap)

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
        # the columns' names as a rack's labels: in capitals (bold left DURATION cut), dimmed,
        # on their middle
        font = uikit.get_font(10)
        dc.SetFont(font)
        tw, th = FONT_ITEM_SIZE
        # under the line at its top (rows 0 and 1), down to the list's first row (3 rows of
        # the same ground under it are the list's): measured on the screen, 8 rows over the
        # capitals and 9 under them (an odd row left: under, as the eye takes it centred)
        height = self.GetClientSize().height + 1
        margin_top = int(round(uikit.get_caps_top(font, 2, height - 2)))
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
            name = column.title.upper()
            limit = len([i for i in dc.GetPartialTextExtents(name)
                         if i <= rect.width - tw - 8 - right_pad])
            title = name[:limit]
            texts.append(title)
            xys.append((rect.x + 10, rect.y + margin_top + osxpad))
        # tw, th = dc.GetTextExtent('A')
        dim = [int(v * 0.62 + w * 0.38) for v, w in zip(self.parent.st.HEADER_FG_COLOR,
                                                        self.parent.st.HEADER_BG_COLOR)]
        dc.DrawTextList(texts, xys, foregrounds=wx.Colour(*dim), backgrounds=None)

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
        self.HandleEventColumnSplitterAuto(event)
        self.HandleEventColumnSplitterDrag(event)
        self.HandleEventSplitterCursor(event)
        self.HandleEventHeaderPopup(event)
        mouseIsDown = event.LeftIsDown or event.RightIsDown or event.MiddleIsDown
        if mouseIsDown is False:
            self.pending.downColumnIdx = None
            self.pending.insertColumnIdx = None
            self.pending.dragColumnWidth = None
            self.pending.ColumnSortDown = False

    def HandleEventSplitterCursor(self, event):
        # the resize cursor over a column's edge, and while one is dragged
        on = self.onClient and (event.splitterIdx is not None or (
            event.LeftIsDown and event.drag.splitterIdx is not None))
        if on == getattr(self, 'splitter_cursor', False):
            return
        self.splitter_cursor = on
        self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE if on else wx.CURSOR_ARROW))

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


LIST_SASH_HOT_MARGIN = 4

# a window cursor only reaches the screen on the next WM_SETCURSOR, too late for a 25ms poll
user32 = ctypes.windll.user32
user32.SetCursor.argtypes = (ctypes.c_void_p,)
user32.SetCursor.restype = ctypes.c_void_p


class ListBoxSash():

    # sash has no window of its own, it only grabs the ListTab and ListBox border

    def __init__(self, parent):
        self.parent = parent
        self.rect = (0, 0, 0, 0)
        self.cursor_windows = []
        self.cursor_stock = Struct(
            ARROW=wx.Cursor(wx.CURSOR_ARROW),
            SIZEWE=wx.Cursor(wx.CURSOR_SIZEWE))
        self.pending = Struct(drag_offset=None, width_reset=False)
        self.last_xy = None
        self.hot = False
        self.force_tail = 0

    def SetRect(self, rect):
        self.rect = rect

    def IsOnSize(self):
        if self.pending.drag_offset is not None:
            return True
        return self.pending.width_reset

    def IsInSashPoint(self, xy, margin=0):
        if self.rect[2] <= 0:
            return False
        x, y, w, h = self.rect
        rect = (x - margin, y, w + margin * 2, h)
        return self.parent.IsInRect(rect, self.parent.ScreenToClient(xy))

    def IsInSash(self, event):
        return self.IsInSashPoint((event.x, event.y))

    def WasInSash(self):
        if self.last_xy is None:
            return False
        return self.IsInSashPoint(self.last_xy)

    def IsHot(self):
        return self.hot

    def SetHot(self, event):
        if self.IsOnSize():
            self.hot = True
        elif getattr(event, 'covered', False):
            # a dialog over the divider: its resize cursor was forced in the dialog
            self.hot = False
        elif self.hot:
            self.hot = self.IsInSashPoint((event.x, event.y), LIST_SASH_HOT_MARGIN)
        else:
            self.hot = self.IsInSash(event) or self.WasInSash()

    def CatchEvent(self, event):
        if event.EventType != EVT_GLOBAL.evtType[0]:
            return
        if self.IsOnSize() is False and self.parent.HasToSkipEvent():
            # every drag frame opens a skip window, releasing here would blink
            self.HandleEventSashCursor(event)
            self.last_xy = (event.x, event.y)
            return
        self.SetHot(event)
        self.HandleEventSashWidthReset(event)
        self.HandleEventSashDrag(event)
        self.HandleEventSashCursor(event)
        self.last_xy = (event.x, event.y)

    def HandleEventSashWidthReset(self, event):
        if event.LeftIsDown is False and event.LeftUp is False:
            self.pending.width_reset = False
        if event.LeftDClick is False:
            return
        if self.hot is False:
            return
        self.pending.width_reset = True
        self.pending.drag_offset = None
        self.parent.ResetListTabWidth()

    def HandleEventSashDrag(self, event):
        if event.LeftIsDown is False:
            if event.LeftUp is False:
                self.pending.drag_offset = None
            return
        if self.pending.width_reset:
            return
        if self.pending.drag_offset is None:
            if event.LeftDown is False:
                return
            if self.hot is False:
                return
            x, y = self.parent.ScreenToClient((event.down.x, event.down.y))
            # a late press sample would make the divider trail the cursor
            width = self.parent.LimitListTabWidth(self.parent.GetListTabWidth())
            offset = x - width
            offset = max(offset, self.rect[0] - width)
            offset = min(offset, self.rect[0] + self.rect[2] - width)
            self.pending.drag_offset = offset
        x, y = self.parent.ScreenToClient((event.x, event.y))
        self.parent.SetListTabWidth(x - self.pending.drag_offset)

    def HandleEventSashCursor(self, event):
        if self.hot is False:
            self.SetCursorARROW()
            return
        self.SetCursorSIZEWE()
        self.ForceCursor(self.cursor_stock.SIZEWE)

    def SetCursorSIZEWE(self):
        if self.cursor_windows != []:
            return
        self.force_tail = 0
        self.cursor_windows = self.CollectBandWindows()
        for window in self.cursor_windows:
            window.SetCursor(self.cursor_stock.SIZEWE)

    def CollectBandWindows(self):
        x, y, w, h = self.rect
        sx, sy = self.parent.ClientToScreen((x, y))
        band = (sx, sy, w, h)
        found = []
        stack = list(self.parent.GetChildren())
        while stack != []:
            window = stack.pop()
            if self.IsRectOverlap(band, tuple(window.GetScreenRect())) is False:
                continue
            found.append(window)
            stack.extend(window.GetChildren())
        return found

    def IsRectOverlap(self, a, b):
        if a[2] <= 0 or a[3] <= 0 or b[2] <= 0 or b[3] <= 0:
            return False
        if a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]:
            return False
        if a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]:
            return False
        return True

    def SetCursorARROW(self):
        if self.cursor_windows == []:
            # a late WM_SETCURSOR can revive the resize cursor after leaving
            if self.force_tail > 0:
                self.force_tail -= 1
                self.ForceCursor(self.cursor_stock.ARROW)
            return
        for window in self.cursor_windows:
            try:
                window.SetCursor(self.cursor_stock.ARROW)
            except RuntimeError:
                pass
        self.cursor_windows = []
        self.force_tail = 8
        self.ForceCursor(self.cursor_stock.ARROW)

    def ForceCursor(self, cursor):
        user32.SetCursor(ctypes.c_void_p(cursor.GetHandle()))


class SearchText(wx.TextCtrl):

    def __init__(self, parent):
        wx.TextCtrl.__init__(self, parent, pos=(0, 0), size=(0, 0),
                             style=wx.TE_PROCESS_ENTER | wx.BORDER_NONE)
        self.parent = parent
        self.onClient = False
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour(macroboxstyle.current().UI.EDIT_BG)
        self.SetHint('Filter this playlist')
        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter)
        self.Bind(wx.EVT_TEXT, self.parent.OnSearchTyped)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.SetFont(wx.Font(wx.Size(0, 13), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                             wx.FONTWEIGHT_NORMAL, faceName='Segoe UI'))
        self.SetForegroundColour(macroboxstyle.current().UI.EDIT_FG)

    def OnEnter(self, event):
        # the directory (Browse) or the library searched now, not after the pause; nothing
        # more for a filter (it follows the typing)
        text = self.GetValue().strip()
        if not text:
            return
        search = self.parent
        if search.live_search is not None:
            search.live_search.Stop()
            search.live_search = None
        search.searched = None
        if search.mode == 'browse':
            search.SearchDirectory(text)
            return
        if search.IsLibraryScope():
            search.SearchLibrary(text)

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


class SearchComboFilter(NativeComboBox):

    def __init__(self, parent):
        self.choices = ('Filename', 'Album', 'Artist',
                        'Title', 'Genre', 'Key', 'Tempo', 'Type', 'Path')
        NativeComboBox.__init__(self, parent, choices=self.choices,
                          pos=(5, 3 + 1 + 1), size=(86, 23), style=wx.CB_READONLY)
        # wx.combo.ComboCtrl # self.SetButtonPosition(side=wx.LEFT)
        self.parent = parent
        self.onClient = False
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
        self.Choose(event.GetString())

    def Choose(self, label):
        # the choice by its label (this hidden combo keeps the choices; the drawn chooser,
        # ListBoxSearch, shows them as a menu)
        self.SetStringSelection(label)
        self.parent.reInitBuffer = True
        if self.parent.browse_mode:
            # the radio's Browse tab: the directory by the chosen (top voted, a genre, a
            # country)
            found = [v for v in self.parent.browse_choices if v[0] == label]
            if found:
                label, query = found[0]
                radio.browse(self.parent.parent, label,
                             lambda: radio.get_stations(**query))
            return
        if self.parent.mode == 'favorites':
            keys = dict(self.parent.FAVORITE_KEYS)
            query_columnKey = keys.get(label, 'filename')
        else:
            query_columnKey = label.lower()
        value = self.parent.parent.ListSearch.SearchText.GetValue()
        self.parent.query_columnKey = query_columnKey
        if value == '':
            return
        self.parent.parent.ListBox.FilterItemsAll(query_columnKey, value)


class ListBoxSearch(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        color = self.parent.parent.st.LISTBOX.HEADER_BG_COLOR
        self.SetBackgroundColour(color)
        self.last_query = ''
        self.query_columnKey = 'filename'
        self.SearchComboFilter = SearchComboFilter(self)
        # drawn instead (a rounded field, a chooser): the combo keeps the choices hidden
        self.SearchComboFilter.Hide()
        self.field_rect = self.clear_rect = self.chooser_rect = wx.Rect(0, 0, 0, 0)
        self.sidebar_rect = wx.Rect(0, 0, 0, 0)
        self.scope_rects = []
        self.chooser_width = 96
        self.drawn = None
        # the selected tab's search (SetMode): its mode, the directory's choices, the live
        # search's timer and the last text searched
        self.mode = 'playlist'
        self.scope = GetPreference('search_scope') or 'list'
        self.browse_mode = False
        self.browse_choices = []
        self.live_search = None
        self.searched = None
        # the playlist the library was searched from, gone back to when the field empties
        self.library_origin = None
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
        # the hint and the parts for the scope kept (the mode is set again on a change only)
        self.SetMode(self.mode, force=True)
        self.InitBuffer()

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        for i in range(len(self.rects[:-1])):
            if self.IsInRect(self.rects[i], xy):
                return i
        return None

    # what the row searches by the selected tab, all as typed (the clear mark empties it):
    # a playlist by the scope switch, this list (filtered by the chosen column) or the
    # library (every playlist, the found shown in the Search tab); the radio's Favorites
    # (filtered by name or tags); the radio's Browse (the directory, after a pause)
    FAVORITE_KEYS = (('Name', 'filename'), ('Tags', 'genre'))
    SCOPES = (('list', 'THIS LIST'), ('library', 'LIBRARY'))
    LIVE_SEARCH_MS = 600
    LIBRARY_SEARCH_MS = 350
    LIVE_SEARCH_LEAST = 2

    def IsLibraryScope(self):
        return self.mode == 'playlist' and self.scope == 'library'

    def SetScope(self, scope):
        # the playlist's search: this list's filter let go for the library, and back
        if scope == self.scope:
            return
        self.scope = scope
        SetPreference('search_scope', scope)
        self.parent.ListBox.SetFilterOffAll()
        self.searched = None
        self.SetMode(self.mode, force=True)
        if scope == 'library':
            self.SearchLibrary()

    def SearchLibrary(self, text=None):
        # every playlist searched, the found in the Search tab (selected)
        self.live_search = None
        if not self or self.IsLibraryScope() is False:
            return
        text = (self.SearchText.GetValue() if text is None else text).strip()
        if len(text) < self.LIVE_SEARCH_LEAST or text == self.searched:
            return
        self.searched = text
        listbox = self.parent.ListBox
        current = listbox.innerList[listbox.selectedList]
        if current.title != library.SEARCH_TITLE:
            self.library_origin = current
        found = library.search(library.collect(listbox), text=text)
        library.show_results(listbox, library.SEARCH_TITLE, found)
        self.parent.StatusBox.alarm = '%d found for "%s" in the library' % (len(found), text)
        self.parent.StatusBox.alarm_color = 'blue'
        self.parent.ListTab.TabList.reInitBuffer = True
        listbox.reInitBuffer = True

    def GetMode(self):
        listbox = self.parent.ListBox
        title = listbox.innerList[listbox.selectedList].title
        if title == radio.BROWSE_TITLE:
            return 'browse'
        if title in (radio.RADIO_TITLE, radio.RECENT_TITLE):
            return 'favorites'
        return 'playlist'

    def SetMode(self, mode, force=False):
        last, self.mode = self.mode, mode
        self.browse_mode = mode == 'browse'
        combo, text = self.SearchComboFilter, self.SearchText
        if last == 'playlist':
            self.playlist_key = self.query_columnKey
        if mode == 'browse':
            # a filter let go: it would hide the directory's rows
            text.ChangeValue('')
            self.parent.ListBox.SetFilterOffAll()
            text.SetHint('Station name, searched as you type')
            combo.Set(['Top voted'])
            combo.SetSelection(0)
            self.chooser_width = 190

            def run():
                try:
                    choices = radio.get_browse_choices()
                except Exception:
                    return
                wx.CallAfter(filled, choices)

            def filled(choices):
                if not self or self.browse_mode is False:
                    return
                self.browse_choices = choices
                combo.Set([label for label, _ in choices])
                combo.SetSelection(0)
            self.browse_choices = [('Top voted', dict())]
            threading.Thread(target=run, daemon=True).start()
        elif mode == 'favorites':
            # (the recent stations' too)
            text.SetHint('Filter stations by name or tags')
            combo.Set([label for label, _ in self.FAVORITE_KEYS])
            combo.SetSelection(0)
            self.query_columnKey = self.FAVORITE_KEYS[0][1]
            self.chooser_width = 96
        elif self.scope == 'library':
            text.SetHint('Search all playlists (found in the Search tab)')
            # its place kept, the chooser shown off (the field's width does not jump as the
            # scope changes): the library is searched in all its fields
            self.chooser_width = 96
        else:
            text.SetHint('Filter this playlist')
            self.query_columnKey = getattr(self, 'playlist_key', 'filename')
            combo.Set(list(combo.choices))
            combo.SetStringSelection(self.query_columnKey.capitalize()
                                     if self.query_columnKey.capitalize() in combo.choices
                                     else combo.choices[0])
            self.chooser_width = 96
        self.OnSize()

    def OnSearchTyped(self, event):
        # the directory (Browse) or the library searched once the typing pauses, from
        # LIVE_SEARCH_LEAST letters, not at every key; this list's filter follows as typed
        event.Skip()
        if self.live_search is not None:
            self.live_search.Stop()
            self.live_search = None
        if self.browse_mode:
            self.live_search = wx.CallLater(self.LIVE_SEARCH_MS, self.SearchDirectory)
        elif self.IsLibraryScope():
            if self.SearchText.GetValue().strip():
                self.live_search = wx.CallLater(self.LIBRARY_SEARCH_MS, self.SearchLibrary)
            else:
                self.LeaveLibrarySearch()

    def LeaveLibrarySearch(self):
        # the field emptied (typed away or its x): back to the playlist searched from, as
        # this list's filter let go shows the list again; the Search tab kept as it is
        self.searched = None
        origin, self.library_origin = self.library_origin, None
        listbox = self.parent.ListBox
        if origin is None or listbox.innerList[listbox.selectedList].title\
                != library.SEARCH_TITLE:
            return
        for index, inner in enumerate(listbox.innerList):
            if inner is origin:
                listbox.SetSelectedList(index)
                self.parent.ListTab.TabList.reInitBuffer = True
                listbox.reInitBuffer = True
                return

    def SearchDirectory(self, text=None):
        self.live_search = None
        if not self or self.browse_mode is False:
            return
        text = (self.SearchText.GetValue() if text is None else text).strip()
        if len(text) < self.LIVE_SEARCH_LEAST or text == self.searched:
            return
        self.searched = text
        radio.browse(self.parent, 'Name: %s' % (text), lambda: radio.get_stations(name=text))

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.HasToSkipEvent():
            return
        mode = self.GetMode()
        if mode != self.mode:
            self.SetMode(mode)
        self.HandleEventDrawnControls(event)
        if mode == 'browse' or self.IsLibraryScope():
            # the directory's or the library's rows are not filtered (OnSearchTyped)
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
        # the rows are drawn by the list inside (and its slider), not the box around it
        self.parent.ListBox.reInitBuffer = True
        self.parent.ListBox.List.reInitBuffer = True
        self.parent.ListBox.SliderV.reInitBuffer = True
        self.reInitBuffer = True

    # Draw ListBoxList

    def SetRectDraw(self, dc):
        # a rounded field (a magnifier, the text box inside it, a clear mark with text),
        # outlined in the accent while typed in; the chooser as the control buttons are
        tokens = macroboxstyle.current().UI
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        x, y, w, h = self.field_rect
        gc.SetPen(wx.Pen(tokens.ACCENT, 1) if self.SearchText.onClient else wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(tokens.CONTROL_BG)))
        # (the keys' corners: uikit.RADIUS, one for every box; 6 before)
        gc.DrawRoundedRectangle(x + 0.5, y + 0.5, w - 1, h - 1, uikit.RADIUS)
        ink = wx.Colour(tokens.BAR_TEXT_DIM)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.6)))
        gc.SetBrush(wx.NullGraphicsBrush)
        cx, cy = x + 13, y + h / 2.0 - 1
        gc.DrawEllipse(cx - 4.5, cy - 4.5, 9, 9)
        gc.StrokeLine(cx + 3.2, cy + 3.2, cx + 6.5, cy + 6.5)
        if self.SearchText.GetValue():
            cx, cy = self.clear_rect.x + self.clear_rect.width / 2.0, y + h / 2.0
            gc.StrokeLine(cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5)
            gc.StrokeLine(cx - 3.5, cy + 3.5, cx + 3.5, cy - 3.5)
        pointer = self.ScreenToClient(wx.GetMousePosition())
        if self.chooser_rect.width > 0:
            if self.IsLibraryScope():
                uikit.draw_button(dc, self.chooser_rect, label='All fields', disabled=True)
            else:
                label = self.SearchComboFilter.GetStringSelection()
                uikit.draw_button(dc, self.chooser_rect, label='%s  \u25be' % (label),
                                  hover=self.IsInRect(self.chooser_rect, pointer))
        uikit.draw_button(dc, self.sidebar_rect, icon='menu',
                          on=self.parent.parent.IsListTabShowOn(),
                          hover=self.IsInRect(self.sidebar_rect, pointer))
        # the playlist's scope: this list or the library, the one searched lit
        # the lit one drawn last: the edge they share its own
        order = sorted(enumerate(self.scope_rects), key=lambda v: v[1][0] == self.scope)
        for k, (key, rect, label) in order:
            corners = 'left' if k == 0 else 'right' if k == len(self.scope_rects) - 1\
                else 'none'
            uikit.draw_button(dc, rect, label=label, on=key == self.scope,
                              hover=key != self.scope and self.IsInRect(rect, pointer),
                              corners=corners)

    def OnSize(self, event=None):
        # the field from the left, the chooser at the right end
        w, h = self.GetClientSize()
        self.rects = ((3, 3, w - 6, h - 1), (3, 3, w - 6, h - 1))
        chooser = self.chooser_width
        right = w - 8
        # the keys 21 rows tall (odd: 22 left the capitals' 7 rows half a row high, measured
        # 5 over and 6 under)
        # 6 rows over them and 6 under, to the list's frame (5 and 7 they were, measured)
        top = 6
        self.chooser_rect = wx.Rect(right - chooser, top, chooser, h - 11)
        if chooser:
            right -= chooser + 8
        # the scope switch left of the chooser, for a playlist
        self.scope_rects = []
        if self.mode == 'playlist':
            for key, label in self.SCOPES[::-1]:
                width = 74
                right -= width
                self.scope_rects.insert(0, (key, wx.Rect(right, top, width, h - 11), label))
                # joined, their edge shared (a segmented switch: the row's only gap that
                # was not 8, 2 px)
                right += 1
            right -= 1 + 8
        # the sidebar's key at the row's left (the status line's before), the field after it
        self.sidebar_rect = wx.Rect(8, top, 26, h - 11)
        # as tall as the keys and on their rows (24 rows from 4 before: 3 taller, half a row
        # lower, measured)
        self.field_rect = wx.Rect(8 + 26 + 8, top, max(0, right - 8 - 26 - 8), h - 11)
        x, y, fw, fh = self.field_rect
        self.clear_rect = wx.Rect(x + fw - 24, y, 24, fh)
        tokens = macroboxstyle.current().UI
        self.SearchText.SetBackgroundColour(tokens.CONTROL_BG)
        self.SearchText.SetForegroundColour(tokens.BAR_TEXT)
        th = min(self.SearchText.GetBestSize().height, fh - 2)
        self.SearchText.SetRect((x + 26, y + (fh - th) // 2, max(0, fw - 26 - 26), th))
        self.text_best = self.SearchText.GetBestSize().height
        self.text_xys = ((10, 5),)
        self.DirectDraw()

    def HandleEventDrawnControls(self, event):
        # a click on the chooser opens its choices as a menu, on the clear mark empties
        # the text, elsewhere in the field puts the caret in it; drawn again for the hover,
        # the focus and the text there or not
        point = (event.X, event.Y)
        state = (self.IsInRect(self.chooser_rect, point) and self.onClient,
                 self.IsInRect(self.sidebar_rect, point) and self.onClient,
                 self.parent.parent.IsListTabShowOn(),
                 [self.IsInRect(rect, point) and self.onClient for _, rect, _ in
                  self.scope_rects], self.scope,
                 self.SearchText.onClient, bool(self.SearchText.GetValue()),
                 self.SearchComboFilter.GetStringSelection())
        if state != self.drawn:
            self.drawn = state
            self.DirectDraw()
        if event.LeftDown is False or self.onClient is False:
            return
        if self.IsInRect(self.sidebar_rect, point):
            self.parent.parent.ToggleListTabShow()
            return
        for key, rect, _ in self.scope_rects:
            if self.IsInRect(rect, point):
                self.SetScope(key)
                return
        if self.chooser_rect.width > 0 and self.IsLibraryScope() is False\
                and self.IsInRect(self.chooser_rect, point):
            menu = wx.Menu()
            for label in self.SearchComboFilter.GetStrings():
                item = menu.AppendRadioItem(wx.ID_ANY, label)
                item.Check(label == self.SearchComboFilter.GetStringSelection())
                menu.Bind(wx.EVT_MENU, lambda e, label=label: self.SearchComboFilter.Choose(label),
                          item)
            # under the chooser, from its left (a dropdown's: it opened at the pointer)
            rect = self.chooser_rect
            self.parent.SetPopupMenu(menu, tuple(self.ClientToScreen(
                (rect.x, rect.y + rect.height + 2))))
        elif self.SearchText.GetValue() and self.IsInRect(self.clear_rect, point):
            self.SearchText.SetValue('')
            self.SearchText.SetFocus()
        elif self.IsInRect(self.field_rect, point):
            self.SearchText.SetFocus()


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
        knob = wx.Rect(round(x), round(y), round(width), round(h))
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
        knob = wx.Rect(round(x), round(y), round(w), round(height))
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


class ItemEditPanel(DialogPanel):

    def __init__(self, parent, pos=(0, 0)):
        DialogPanel.__init__(self, parent)
        self.Show(False)
        self.parent = parent
        x, y = pos
        width, height = self.parent.GetSize()
        self.SetRect((x, y, width - 4, 247))
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
                # shown as values, not fields
                self.TextCtrls[i].SetReadOnly()
        self.Refresh()

    def InitTextCtrls(self):
        width, height = self.GetClientSize()
        posX = 76
        posY = 25
        twh = (50, 20)
        right = 27
        self.TextCtrls = list()
        self.StaticTexts = list()

        self.StaticTexts += [StaticText(self, label=self.labels[0], pos=(15, posY - 5 + 4),
                                        size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(posX, posY - 5 + 1),
                                    size=(width - posX - right, 22))]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[1], pos=(15, posY - 5 + 4),
                                        size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(posX, posY - 5 + 1),
                                    size=(width - posX - right, 22))]
        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[2], pos=(
            15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX, posY - 5 + 1), size=(65 - 2, 22), style=wx.ALIGN_RIGHT)]

        self.StaticTexts += [StaticText(self, label=self.labels[3], pos=(
            15 + 145 - 2, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX + 145 - 2, posY - 5 + 1), size=(65 - 2, 22), style=wx.ALIGN_RIGHT)]

        self.StaticTexts += [StaticText(self, label=self.labels[4], pos=(
            15 + 300 - 10 - 4, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX + 300 - 10 - 4, posY - 5 + 1), size=(65 - 2, 22), style=wx.ALIGN_RIGHT)]

        self.StaticTexts += [StaticText(self, label=self.labels[5], pos=(
            15 + 300 - 10 + 145 - 6, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX + 300 - 10 + 145 - 6, posY - 5 + 1), size=(65 - 2, 22), style=wx.ALIGN_RIGHT)]

        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[6], pos=(
            15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX, posY - 5 + 1), size=(width - posX - right, 22))]

        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[7], pos=(
            15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX, posY - 5 + 1), size=(width - posX - right, 22))]

        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[8], pos=(
            15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX, posY - 5 + 1), size=(width - posX - right, 22))]

        posY += 30

        self.StaticTexts += [StaticText(self, label=self.labels[9], pos=(
            15, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX, posY - 5 + 1), size=(210 - 4, 22))]

        self.StaticTexts += [StaticText(self, label=self.labels[10], pos=(
            15 + 300 - 10 - 4, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        # (Key's field on Bitrate's column, Tempo's name on its row: both were off)
        self.TextCtrls += [TextCtrl(self, pos=(
            posX + 300 - 10 - 4, posY - 5 + 1), size=(65 - 2, 22))]

        self.StaticTexts += [StaticText(self, label=self.labels[11], pos=(
            15 + 300 - 10 + 145 - 6, posY - 5 + 4), size=twh, style=wx.ALIGN_RIGHT)]
        self.TextCtrls += [TextCtrl(self, pos=(
            posX + 300 - 10 + 145 - 6, posY - 5 + 1), size=(65 - 2, 22), style=wx.ALIGN_RIGHT)]
        # the names dimmed, the values (and the fields) brighter
        for text in self.StaticTexts:
            text.SetForegroundColour(macroboxstyle.current().UI.BAR_TEXT_DIM)

    def OnClose(self, event):
        self.Destroy()


class ItemEditBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(600, 320))
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
        left = 2
        label = '%d / %d' % (self.selected_idx + 1, self.total_items)
        self.PageNumber = StaticText(self, label=label, pos=(
            width - 95 - 160 - 120 + left, height + 5), size=(80, 20), style=wx.ALIGN_RIGHT)
        self.CloseButton.SetPosition((width - 95 + 3 + left, height))
        self.NextButton = Button(self, label='Next')
        self.NextButton.SetPosition((width - 95 - 80 + 3 + left, height))
        self.NextButton.Bind(wx.EVT_BUTTON, self.OnNext)
        self.PrevButton = Button(self, label='Prev')
        self.PrevButton.Bind(wx.EVT_BUTTON, self.OnPrev)
        self.PrevButton.SetPosition((width - 95 - 80 * 2 + 3 + left, height))
        self.LookUpButton = Button(self, label='Look Up')
        self.LookUpButton.Bind(wx.EVT_BUTTON, self.OnLookUp)
        self.LookUpButton.SetPosition((10, height))
        self.LookUpButton.SetToolTip(wx.ToolTip(
            'Find artist, title, album and genre on Discogs, Last.fm and AcoustID.'
            '\nThe keys are set in Preference > Web Services.'))
        self.ItemEditPanel = ItemEditPanel(self)
        self.ItemEditPanel.SetPage(self.selectedItems[self.selected_idx])
        self.AutoSeButtonState()
        self.ItemEditPanel.Show(True)

    def GetFieldText(self, label):
        return self.ItemEditPanel.TextCtrls[self.ItemEditPanel.labels.index(label)]

    def OnLookUp(self, event):
        keys = dict(zip(webinfo.PREFERENCE_KEYS, GetPreferences(webinfo.PREFERENCE_KEYS)))
        if not any(keys.values()):
            wx.MessageBox('Set a key in Preference > Web Services first.',
                          'Look Up', wx.OK | wx.ICON_INFORMATION, self)
            return
        itemIdx = self.selectedItems[self.selected_idx]
        path = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
        artist = self.GetFieldText('Artist').GetValue().strip()
        title = self.GetFieldText('Title').GetValue().strip()
        self.LookUpButton.Disable()
        self.LookUpButton.SetLabel('Looking...')
        thread = threading.Thread(target=self.LookUpThread,
                                  args=(self.selected_idx, path, artist, title, keys))
        thread.daemon = True
        thread.start()

    def LookUpThread(self, selected_idx, path, artist, title, keys):
        try:
            candidates, errors = webinfo.lookup(path, artist, title, keys, webinfo.Cache())
        except Exception as error:
            candidates, errors = list(), [str(error)]
        wx.CallAfter(self.OnLookedUp, selected_idx, candidates, errors)

    def OnLookedUp(self, selected_idx, candidates, errors):
        if not self:
            return
        self.LookUpButton.SetLabel('Look Up')
        self.LookUpButton.Enable()
        if selected_idx != self.selected_idx:
            return
        itemIdx = self.selectedItems[self.selected_idx]
        length = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'duration')
        dialog = WebInfoBox(self, candidates, errors, length)
        if dialog.ShowModal() == wx.ID_OK and dialog.selected is not None:
            chosen = candidates[dialog.selected]
            for label in ('Artist', 'Title', 'Album', 'Genre'):
                if chosen[label.lower()]:
                    self.GetFieldText(label).SetValue(chosen[label.lower()])
        dialog.Destroy()

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
                        self.ItemEditPanel.TextCtrls[i].SetValue(
                            self.ItemEditPanel.restore_value[i])
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
                tag_resp = self.parent.parent.RenameID3TAGByColumnItemIdx(
                    columnIdx, itemIdx, newValue)
                if tag_resp is False:
                    self.ItemEditPanel.TextCtrls[i].SetValue(
                        self.ItemEditPanel.restore_value[i])

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


def show_library_results(mainpanel, title, songs):
    # the found songs in their tab, the tab chosen and drawn as a new one is
    library.show_results(mainpanel.ListBox, title, songs)
    mainpanel.ListBox.Header.SetAutoColumnWidth()
    mainpanel.ListBox.reInitBuffer = True
    mainpanel.ListBox.List.reInitBuffer = True
    mainpanel.ListTab.reInitBuffer = True
    mainpanel.ListTab.TabList.DirectDraw()


class LibrarySearchBox(DialogBox):

    # the library (every playlist's songs) searched: words, a BPM range, a key and a genre
    # together; what matches goes to the Search tab
    def __init__(self, parent, mainpanel):
        DialogBox.__init__(self, parent, size=(440, 250))
        self.mainpanel = mainpanel
        self.SetTitle('Find in Library')
        x, y = (90, 16)
        style = wx.TE_PROCESS_ENTER
        StaticText(self, label='Words', pos=(10, y + 3), size=(70, -1), style=wx.ALIGN_RIGHT)
        self.Words = TextCtrl(self, pos=(x, y), size=(320, 22), style=style)
        y += 32
        StaticText(self, label='BPM', pos=(10, y + 3), size=(70, -1), style=wx.ALIGN_RIGHT)
        self.Low = TextCtrl(self, pos=(x, y), size=(60, 22), style=style)
        StaticText(self, label='to', pos=(x + 66, y + 3), size=(16, -1))
        self.High = TextCtrl(self, pos=(x + 86, y), size=(60, 22), style=style)
        self.Octave = CheckBox(self, label='Half and double too', pos=(x + 160, y + 4))
        y += 32
        StaticText(self, label='Key', pos=(10, y + 3), size=(70, -1), style=wx.ALIGN_RIGHT)
        self.Key = TextCtrl(self, pos=(x, y), size=(60, 22), style=style)
        self.Compatible = CheckBox(self, label='Compatible keys too', pos=(x + 160, y + 4))
        y += 32
        StaticText(self, label='Genre', pos=(10, y + 3), size=(70, -1), style=wx.ALIGN_RIGHT)
        self.Genre = TextCtrl(self, pos=(x, y), size=(150, 22), style=style)
        for control in (self.Words, self.Low, self.High, self.Key, self.Genre):
            control.Bind(wx.EVT_TEXT_ENTER, self.OnSearch)
        width, height = self.GetClientSize()
        self.Status = StaticText(self, label='', pos=(10, height - 60), size=(width - 20, 18))
        self.PlayingButton = Button(self, label='From playing song')
        self.PlayingButton.SetRect((10, height - 36, 130, 26))
        self.PlayingButton.Bind(wx.EVT_BUTTON, self.OnPlaying)
        self.SearchButton = Button(self, label='Search', primary=True)
        self.SearchButton.SetPosition((width - 175, height - 36))
        self.SearchButton.Bind(wx.EVT_BUTTON, self.OnSearch)
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.SetPosition((width - 90, height - 36))
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)

    def OnPlaying(self, event):
        playbox = self.mainpanel.PlayBox
        tempo = playbox.GetPlayingTempo()
        if tempo > 0:
            self.Low.SetValue('%.1f' % (tempo * 0.97))
            self.High.SetValue('%.1f' % (tempo * 1.03))
            self.Octave.SetValue(True)
        key = playbox.GetPlayingKey()
        if key and key not in ('-', ' '):
            self.Key.SetValue(key)
            self.Compatible.SetValue(True)

    def OnSearch(self, event):
        songs = library.collect(self.mainpanel.ListBox)
        found = library.search(
            songs, text=self.Words.GetValue(), low=library.to_float(self.Low.GetValue()),
            high=library.to_float(self.High.GetValue()), octave=self.Octave.GetValue(),
            key=self.Key.GetValue().strip(), compatible=self.Compatible.GetValue(),
            genre=self.Genre.GetValue())
        show_library_results(self.mainpanel, library.SEARCH_TITLE, found)
        self.Status.SetLabel('%d of %d songs in the library' % (len(found), len(songs)))

    def OnClose(self, event):
        self.Destroy()


class WebInfoBox(DialogBox):

    COVER = 200

    def __init__(self, parent, candidates, errors, length=''):
        DialogBox.__init__(self, parent, size=(1150, 340))
        title = 'Look Up: %d found' % (len(candidates))
        if length:
            title += ', this file %s' % (length)
        self.SetTitle(title)
        self.candidates = candidates
        self.selected = None
        self.cover_timer = None
        width, height = self.GetClientSize()
        self.List = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        columns = (('Source', 65), ('Artist', 120), ('Title', 140), ('Album', 120),
                   ('Release', 230), ('Genre', 80), ('Length', 50), ('Year', 45), ('Score', 45))
        for i, (title, column_width) in enumerate(columns):
            self.List.InsertColumn(i, title, width=column_width)
        for i, v in enumerate(candidates):
            score = '' if v['score'] is None else '%.2f' % (v['score'])
            values = (v['source'], v['artist'], v['title'], v['album'], v['release'],
                      v['genre'], webinfo.format_duration(v['duration']), v['year'], score)
            self.List.InsertItem(i, values[0])
            for column, value in enumerate(values[1:], 1):
                self.List.SetItem(i, column, value)
        self.List.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnApply)
        self.List.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnOpenLink)
        self.List.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelected)
        self.Cover = wx.StaticBitmap(self, bitmap=wx.Bitmap(self.COVER, self.COVER))
        self.CoverText = StaticText(self, label='', style=wx.ALIGN_CENTER)
        self.ApplyButton = Button(self, label='Apply', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CancelButton = Button(self, label='Cancel')
        self.CancelButton.Bind(wx.EVT_BUTTON, self.OnCancel)
        w, h = self.CancelButton.GetSize()
        bottom = height - h - 10
        self.List.SetRect((10, 10, width - 30 - self.COVER,
                           bottom - 20 - (20 if errors else 0)))
        self.Cover.SetRect((width - 10 - self.COVER, 10, self.COVER, self.COVER))
        self.CoverText.SetRect((width - 10 - self.COVER, 10 + self.COVER + 6, self.COVER, 18))
        self.SetCover(None, '')
        if errors:
            StaticText(self, label=' / '.join(errors),
                       pos=(10, bottom - 25), size=(width - 20, 18))
        self.CancelButton.SetPosition((width - 95, bottom))
        self.ApplyButton.SetPosition((width - 95 - 80, bottom))
        if candidates:
            self.List.Select(0)
        else:
            self.ApplyButton.Disable()

    def OnApply(self, event):
        idx = self.List.GetFirstSelected()
        if idx < 0:
            return
        self.selected = idx
        self.EndModal(wx.ID_OK)

    def SetCover(self, data, label):
        image = None
        if data:
            try:
                image = wx.Image(io.BytesIO(data))
            except Exception:
                image = None
        if image is not None and image.IsOk():
            w, h = image.GetSize()
            scale = min(self.COVER / w, self.COVER / h)
            image = image.Scale(max(1, int(w * scale)), max(1, int(h * scale)),
                                wx.IMAGE_QUALITY_HIGH)
            image.Resize((self.COVER, self.COVER),
                         ((self.COVER - image.GetWidth()) // 2,
                          (self.COVER - image.GetHeight()) // 2), *macroboxstyle.current().UI.RAISED_BG)
            self.Cover.SetBitmap(wx.Bitmap(image))
        else:
            bmp = wx.Bitmap(self.COVER, self.COVER)
            dc = wx.MemoryDC(bmp)
            dc.SetBackground(wx.Brush(macroboxstyle.current().UI.RAISED_BG))
            dc.Clear()
            dc.SelectObject(wx.NullBitmap)
            self.Cover.SetBitmap(bmp)
        self.CoverText.SetLabel(label)

    def OnSelected(self, event):
        # only the row the selection rests on is fetched, not every row passed over
        if self.cover_timer is not None:
            self.cover_timer.Stop()
        self.cover_timer = wx.CallLater(250, self.LoadCover, event.GetIndex())

    def LoadCover(self, idx):
        url = self.candidates[idx]['image']
        if not url:
            self.SetCover(None, 'No cover')
            return
        self.SetCover(None, 'Loading...')
        thread = threading.Thread(target=self.LoadCoverThread, args=(idx, url))
        thread.daemon = True
        thread.start()

    def LoadCoverThread(self, idx, url):
        try:
            data, label = webinfo.fetch_image(url), ''
        except Exception as error:
            data, label = None, str(error)
        wx.CallAfter(self.OnCoverLoaded, idx, data, label)

    def OnCoverLoaded(self, idx, data, label):
        if not self or self.List.GetFirstSelected() != idx:
            return
        self.SetCover(data, label)

    def OnOpenLink(self, event):
        url = self.candidates[event.GetIndex()]['url']
        if url:
            webbrowser.open(url)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnClose(self, event):
        self.EndModal(wx.ID_CANCEL)

    def Destroy(self):
        if self.cover_timer is not None:
            self.cover_timer.Stop()
        return DialogBox.Destroy(self)


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


class ListBoxPopupHeader(wx.Menu):

    # the header's menu: the columns shown, their widths fitted to what they show or back
    # to the first ones, and the columns kept as the default or for every tab. built by the
    # columns themselves (an item's place in the menu was taken for the column's, and the
    # private columns, left out, put them apart)

    def __init__(self, parent):
        wx.Menu.__init__(self)
        self.parent = parent
        listbox = self.parent.parent
        for i, v in enumerate(listbox.GetColumns()):
            if v.private:
                continue
            item = self.AppendCheckItem(wx.ID_ANY, v.title)
            item.Check(v.show is True)
            self.Bind(wx.EVT_MENU, lambda e, i=i: self.OnShow(i, e.IsChecked()), item)
        self.AppendSeparator()
        item = self.Append(wx.ID_ANY, 'Fit columns to content')
        self.Bind(wx.EVT_MENU, self.OnFit, item)
        item = self.Append(wx.ID_ANY, 'Reset column widths')
        self.Bind(wx.EVT_MENU, self.OnReset, item)
        self.AppendSeparator()
        item = self.Append(wx.ID_ANY, 'Set as default')
        self.Bind(wx.EVT_MENU, self.OnDefault, item)
        item = self.Append(wx.ID_ANY, 'Apply to all tabs')
        self.Bind(wx.EVT_MENU, self.OnApplyAll, item)

    def OnShow(self, index, show):
        listbox = self.parent.parent
        shown = [v for v in listbox.GetColumns() if v.show is True and v.private is False]
        if len(shown) == 1 and show is False:
            return
        listbox.SetColumn(index, show=show)
        if show and listbox.GetColumns()[index].key == 'comment':
            fill_comments(listbox)
        # the file name's column gives the new one its room (or takes it back)
        self.parent.SetAutoColumnWidth()
        self.parent.DirectDraw()
        listbox.reInitBuffer = True

    def OnFit(self, event):
        # every shown column as wide as its widest text (the edge's double click, each)
        for i in range(len(self.parent.parent.GetShownColumnsIdx())):
            self.parent.FitColumnWidth(i)
        self.parent.DirectDraw()
        self.parent.parent.reInitBuffer = True

    def OnReset(self, event):
        # the widths the columns are made with
        listbox = self.parent.parent
        first = dict((v.key, v.width) for v in ListBoxColumn())
        for i, v in enumerate(listbox.GetColumns()):
            if v.key in first:
                listbox.SetColumnWidth(i, first[v.key])
        # and the file name's over the room left, as when the list is resized
        self.parent.SetAutoColumnWidth()
        self.parent.DirectDraw()
        listbox.reInitBuffer = True

    def OnDefault(self, event):
        SetPreference('columns', self.parent.parent.GetColumns())

    def OnApplyAll(self, event):
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
        # internet radio stations only: played and deleted, nothing of a file (its tags,
        # its folder, its analysis)
        listbox = self.parent.parent
        rows = listbox.innerList[listbox.selectedList].items
        pathIdx = listbox.GetColumnKeyToIdx('path')
        selected = listbox.GetSelectedItems()
        stations = bool(selected) and all(
            audio.is_stream_path(rows[i][pathIdx]) for i in selected if i < len(rows))

        if single:
            idx = 1
            name = 'Play'
            self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        if stations is False:
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
        title = listbox.innerList[listbox.selectedList].title
        if not stations:
            # a song starred (or let go): the favorite tracks (the sidebar's Library)
            paths = self.GetSelectedPaths()
            starred = set(library.get_favorite_tracks())
            name = 'Remove from Favorite tracks' if paths and all(v in starred for v in paths)\
                else 'Add to Favorite tracks'
            item = wx.MenuItem(self, wx.ID_ANY, name, wx.EmptyString, wx.ITEM_NORMAL)
            self.Append(item)
            self.Bind(wx.EVT_MENU, self.OnToggleFavoriteTracks, item)
        if stations and title != radio.RADIO_TITLE:
            # found or put elsewhere: kept in the radio's favorites
            item = wx.MenuItem(self, wx.ID_ANY, 'Add to Favorite stations', wx.EmptyString,
                               wx.ITEM_NORMAL)
            self.Append(item)
            self.Bind(wx.EVT_MENU, self.OnAddFavorites, item)
        if title == radio.RADIO_TITLE:
            item = wx.MenuItem(self, wx.ID_ANY, 'Add Station URL...', wx.EmptyString,
                               wx.ITEM_NORMAL)
            self.Append(item)
            self.Bind(wx.EVT_MENU, self.OnAddStationURL, item)
        if stations:
            return

        idx = 4
        name = 'Analyze'
        self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        if single:
            idx = 5
            name = 'Open Containing Folder'
            self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])
            idx = 6
            name = 'Find Similar'
            self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        self.AppendSeparator()

        # ConvertTempoRange

        self.itemConvertTempoRange = wx.Menu()

        idx = 101
        name = 'Convert to Up Tempo (95bpm~)'
        self.itemConvertTempoRange.Append(wx.MenuItem(
            self.itemConvertTempoRange, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheckConvertTempoRange,
                  self.itemConvertTempoRange.MenuItems[0])

        idx = 102
        name = 'Convert to Down Tempo (~120bpm)'
        self.itemConvertTempoRange.Append(wx.MenuItem(
            self.itemConvertTempoRange, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
        self.Bind(wx.EVT_MENU, self.OnCheckConvertTempoRange,
                  self.itemConvertTempoRange.MenuItems[1])

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

    def GetSelectedStations(self):
        # the selected rows' stations (their names and tags as their rows have them)
        listbox = self.parent.parent
        rows = listbox.innerList[listbox.selectedList].items
        keys = [v.key for v in listbox.innerList[listbox.selectedList].columns]
        stations = []
        for i in listbox.GetSelectedItems():
            if i >= len(rows):
                continue
            values = dict(zip(keys, rows[i]))
            if audio.is_stream_path(values.get('path')):
                station = radio.get_station(values['path']) or dict(
                    url=values['path'], name=values.get('filename', ''),
                    tags=values.get('genre', ''))
                stations.append(station)
        return stations

    def GetSelectedPaths(self):
        listbox = self.parent.parent
        rows = listbox.innerList[listbox.selectedList].items
        keys = [v.key for v in listbox.innerList[listbox.selectedList].columns]
        return [rows[i][keys.index('path')] for i in listbox.GetSelectedItems()
                if i < len(rows)]

    def OnToggleFavoriteTracks(self, event):
        toggle_favorite_tracks(self.parent.parent, self.GetSelectedPaths())

    def OnAddFavorites(self, event):
        radio.add_favorites(self.parent.parent.parent, self.GetSelectedStations())

    def OnAddStationURL(self, event):
        radio.add_url(self.parent.parent.parent)

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
        elif event.Id == 6:
            self.FindSimilar()
        # elif event.Id == 7-diff:
        #   self.AnalyzeSelectedItems()
        # elif event.Id == 8-diff:
        #   self.AnalyzeSelectedItems(forced=True)
        # elif event.Id == 8-diff:
        #   self.CheckItemsConsistency()

    def FindSimilar(self):
        # the library ranked against the song on a thread (each song's waveform is read
        # once), the result in the Similar tab
        listbox = self.parent.parent
        mainpanel = listbox.parent
        selected = listbox.GetSelectedItems()
        if selected == []:
            return
        path = listbox.GetItemValueByColumnKey(selected[0], 'path')
        songs = library.collect(listbox)
        target = [v for v in songs if v.path == path]
        if target == []:
            return
        mainpanel.StatusBox.alarm = 'Finding songs like %s ...' % (os.path.basename(path))
        mainpanel.StatusBox.alarm_timer = 0

        def work():
            found = library.similar(songs, target[0])
            wx.CallAfter(done, found)

        def done(found):
            show_library_results(mainpanel, library.SIMILAR_TITLE, [target[0]] + found)
            mainpanel.StatusBox.alarm = '%d songs like it in the Similar tab' % (len(found))
            mainpanel.StatusBox.alarm_timer = 0

        threading.Thread(target=work, daemon=True).start()

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

    # (the sidebar's key is the search row's now: the messages from the left edge)
    MESSAGE_LEFT_X = 8
    PROGRESS_WIDTH = 80

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.SetBackgroundColour(macroboxstyle.current().UI.BAR_BG)
        self.messages = (u'', u'')
        self.proc = 0
        # the analysis' run: the most tracks waiting in it, and how many of them are done
        # (a bar at the right while it runs)
        self.batch = 0
        self.progress = None
        self.alarm = None
        self.alarm_color = None
        self.alarm_timer = 0
        self.rects = ()
        self.InitBuffer()

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        for i in range(len(self.rects)):
            if self.IsInRect(self.rects[i], xy):
                return i
        return None

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
        waiting = task + proc
        if waiting == 0:
            self.batch = 0
            self.progress = None
            message_right = u'Analysis idle'
        else:
            self.batch = max(self.batch, waiting)
            done = self.batch - waiting
            self.progress = 1.0 * done / self.batch
            message_right = self.GetProgressText(done + 1, self.batch, core)
        messages = (message_left, message_right)
        if self.messages == messages:
            return
        self.messages = messages
        self.reInitBuffer = True

    def GetProgressText(self, current, batch, core):
        return u'Analyzing %s of %s  \u00b7  %s processes' % (current, batch, core)

    def SetRectDraw(self, dc):
        message_left, message_right = self.messages
        w, h = self.parent.GetSize()
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((6, 11))
        font.SetFaceName(FONT_ITEM)
        dc.SetFont(font)
        tw, th = dc.GetTextExtent(message_right)
        # 9 rows over the capitals and 9 under (7 left 10 and 8, measured)
        ty = 6
        xys = ((self.MESSAGE_LEFT_X, ty), (w - tw - 10, ty),)
        if self.progress is not None:
            # the run's progress: a thin bar before its text, kept where the run's longest
            # text puts it (it moved as the count gained a digit)
            widest = self.GetProgressText(self.batch, self.batch, 88)
            ww = max(tw, dc.GetTextExtent(widest)[0])
            bx, bw = w - ww - 10 - 10 - self.PROGRESS_WIDTH, self.PROGRESS_WIDTH
            by = ty + th // 2 - 2
            tokens = macroboxstyle.current().UI
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(tokens.CONTROL_BG))
            dc.DrawRectangle(bx, by, bw, 4)
            dc.SetBrush(wx.Brush(tokens.ACCENT))
            dc.DrawRectangle(bx, by, max(int(bw * self.progress), 2), 4)
        # told (blue), warned (orange: red was the same as black to red-green colour
        # blindness on the dark bar), busy analysing (blue)
        tokens = macroboxstyle.current().UI
        if self.alarm_color == 'blue':
            color_left = wx.Colour(tokens.ACCENT)
        elif self.alarm_color == 'red':
            color_left = wx.Colour(tokens.WARN)
        else:
            color_left = wx.Colour(tokens.BAR_TEXT)
        if self.proc != 0:
            color_right = wx.Colour(tokens.BAR_TEXT)
        else:
            color_right = wx.Colour(tokens.BAR_TEXT_DIM)
        dc.DrawTextList(self.messages, xys, foregrounds=(color_left, color_right))

    def OnSize(self, event=None):
        self.DirectDraw()
