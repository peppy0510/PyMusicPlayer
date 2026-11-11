# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import ctypes
import folders
import glob
import images
import io
import library
import listimages
import macroboxstyle
import math
import mfeats
import mutagen
import os
import radio
import stat
import sys
import threading
import time
import uikit
import urllib.parse
import webbrowser
import webinfo
import wx

from listboxlib import FileOpenDialog
from listboxlib import FileSaveDialog
from listboxlib import ListBoxListDnD
from listboxlib import ListControl
from listboxtab import ListBoxPopupFolder
from listboxtab import ListBoxPopupTab
from listboxtab import ListBoxPopupTabAdd
from listboxtab import ListBoxTab
from listboxtab import ListBoxTabDnD
from listboxtab import ListBoxTabSliderV
from listboxtab import TabRenameBox
from macroboxlib import Button
from macroboxlib import COLOR_STATUS_BG
from macroboxlib import ComboBox
from macroboxlib import ConfirmDialogBox
from macroboxlib import NativeComboBox
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
from macroboxlib import DIALOG_BUTTON_HEIGHT
from macroboxlib import DIALOG_GAP
from macroboxlib import DIALOG_PAD
from macroboxlib import DIALOG_ROW
from macroboxlib import fit_name_column
from macroboxlib import make_check
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
        # drawn just above: no idle redraw, or a sash drag draws it twice
        self.List.reInitBuffer = False
        self.Header.reInitBuffer = False
        self.SliderH.reInitBuffer = False
        self.SliderV.reInitBuffer = False
        self.Thaw()

    def __del__(self):
        pass


# files whose comment was read, once a session
COMMENTS_READ = set()


def fill_comments(listbox):
    '''read the comment column of the rows on a thread, in every tab'''
    paths = []
    for inner in listbox.innerList:
        keys = [v.key for v in inner.columns]
        if 'comment' not in keys or 'path' not in keys:
            continue
        pathIdx = keys.index('path')
        paths += [item[pathIdx] for item in inner.items
                  if item[pathIdx] not in COMMENTS_READ
                  and not audio.is_stream_path(item[pathIdx])]
    paths = list(dict.fromkeys(paths))
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
    # star or unstar songs, the favorites tab refreshed
    starred = library.toggle_favorite_tracks(paths)
    # refilled in place: selecting it made the list jump at each star
    if any(v.title == library.FAVORITES_TITLE for v in listbox.innerList):
        library.show_favorites(listbox, select=False)
    listbox.reInitBuffer = True
    listbox.List.reInitBuffer = True
    mainpanel = listbox.parent
    mainpanel.ListTab.TabList.reInitBuffer = True
    radio.tell(mainpanel, 'Added to Favorite tracks' if starred else 'Removed from Favorite tracks')


def find_similar(listbox, path, values):
    # rank the library against the song on a thread into Similar
    mainpanel = listbox.parent
    songs = library.collect(listbox)
    target = [v for v in songs if v.path == path]
    if target == []:
        # a song in no playlist (folder tab): use its row
        target = [library.make_song(values, library.get_grid_tempi())]
    mainpanel.StatusBox.alarm = f'Finding songs like {os.path.basename(path)} ...'
    mainpanel.StatusBox.alarm_timer = 0

    def work():
        found = library.similar(songs, target[0])
        wx.CallAfter(done, found)

    def done(found):
        show_library_results(mainpanel, library.SIMILAR_TITLE, [target[0]] + found)
        mainpanel.StatusBox.alarm = f'{len(found)} songs like it in the Similar tab'
        mainpanel.StatusBox.alarm_timer = 0

    threading.Thread(target=work, daemon=True).start()


def get_shared_gc(dc, shared):
    # one GraphicsContext shared by a list's rows: one a row is slow
    if not shared:
        shared.append(wx.GraphicsContext.Create(dc))
    return shared[0]


def draw_analysis_icon(dc, cx, cy, working, r=4.0, alpha=255, shared=None):
    # analysis icon: an accent arc while running, dimmed dots while waiting
    tokens = macroboxstyle.current().UI

    def ink(name):
        c = uikit.colour(getattr(tokens, name))
        return wx.Colour(c.Red(), c.Green(), c.Blue(), alpha)
    gc = wx.GraphicsContext.Create(dc) if shared is None else get_shared_gc(dc, shared)
    if gc is None:
        return
    if working:
        # turning
        start = math.radians((time.time() % 1.2) / 1.2 * 360.0)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink('ACCENT')).Width(1.8)))
        path = gc.CreatePath()
        path.AddArc(cx, cy, r, start, start + math.radians(270), True)
        gc.StrokePath(path)
    else:
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(ink('BAR_TEXT_DIM'))))
        dots = 8 if r <= 4.0 else 12
        for k in range(dots):
            angle = math.radians(k * 360.0 / dots)
            gc.DrawEllipse(cx + r * math.cos(angle) - 0.9, cy + r * math.sin(angle) - 0.9, 1.8,
                           1.8)
    if shared is not None:
        # flushed: the playing mark drawn next goes over it
        gc.Flush()


def draw_waiting_icons(dc, points, r=4.0, shared=None):
    '''waiting rings at points [(cx, cy)] in one path'''
    if not points:
        return
    gc = wx.GraphicsContext.Create(dc) if shared is None else get_shared_gc(dc, shared)
    if gc is None:
        return
    c = uikit.colour(macroboxstyle.current().UI.BAR_TEXT_DIM)
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(c.Red(), c.Green(), c.Blue(), 255))))
    dots = 8 if r <= 4.0 else 12
    path = gc.CreatePath()
    for cx, cy in points:
        for k in range(dots):
            angle = math.radians(k * 360.0 / dots)
            path.AddEllipse(cx + r * math.cos(angle) - 0.9, cy + r * math.sin(angle) - 0.9, 1.8,
                            1.8)
    gc.FillPath(path)
    if shared is not None:
        gc.Flush()


def draw_star_outlines(dc, points, r, colour, shared=None):
    '''star outlines at points [(cx, cy)] in one path'''
    if not points:
        return
    gc = wx.GraphicsContext.Create(dc) if shared is None else get_shared_gc(dc, shared)
    if gc is None:
        return
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour).Width(1)))
    path = gc.CreatePath()
    for cx, cy in points:
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
    if shared is not None:
        gc.Flush()


def draw_folder_icons(dc, points, colour, shared=None):
    '''folder icons, 11 px across, at points [(cx, cy)] in one path'''
    if not points:
        return
    gc = wx.GraphicsContext.Create(dc) if shared is None else get_shared_gc(dc, shared)
    if gc is None:
        return
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour).Width(1.2)))
    gc.SetBrush(wx.NullGraphicsBrush)
    path = gc.CreatePath()
    for cx, cy in points:
        path.MoveToPoint(cx - 5.5, cy - 4)
        for x, y in ((-1.5, -4), (0, -2.5), (5.5, -2.5), (5.5, 4), (-5.5, 4)):
            path.AddLineToPoint(cx + x, cy + y)
        path.CloseSubpath()
    gc.StrokePath(path)
    if shared is not None:
        gc.Flush()


def draw_star(dc, cx, cy, r, colour):
    # filled five-pointed star
    points = []
    for k in range(10):
        radius = r if k % 2 == 0 else r * 0.45
        angle = math.pi / 2 + k * math.pi / 5
        points.append((int(round(cx + radius * math.cos(angle))),
                       int(round(cy - radius * math.sin(angle)))))
    dc.SetPen(wx.Pen(colour, 1))
    dc.SetBrush(wx.Brush(colour))
    dc.DrawPolygon(points)


# cached text pictures by (font, text, ink, ground)
TEXT_PICTURES = {}


class ListBoxList(RectBox):

    # drawn first among pending boxes (macroboxlib.DrawPending)
    PENDING_FIRST = True

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
        self.tips = uikit.CutTips(self)
        bgcolor = self.parent.GetBackgroundColour()
        self.SetBackgroundColour(bgcolor)

        self.bmp = Struct(playing=Struct())
        self.bmp.playing.black = images.listbox_playing_black.GetBitmap()
        self.bmp.playing.white = images.listbox_playing_white.GetBitmap()
        # half see-through: a folder's mark while its song is not sounding
        self.bmp.playing.dimmed = {
            light: wx.Bitmap(bmp.ConvertToImage().AdjustChannels(1.0, 1.0, 1.0, 0.5))
            for light, bmp in ((True, self.bmp.playing.white),
                               (False, self.bmp.playing.black))}
        self.InitBuffer()
        # mouse back button opens the parent folder, as Backspace
        # a quick second press comes as a double click
        self.Bind(wx.EVT_MOUSE_AUX1_DOWN, self.OnBackButton)
        self.Bind(wx.EVT_MOUSE_AUX1_DCLICK, self.OnBackButton)

    def OnBackButton(self, event):
        if folders.is_folder_view(self.parent) is False:
            event.Skip()
            return
        folders.go_up(self.parent.parent)

    # Draw ListBoxList

    def SetRectDraw(self, dc):
        self.DrawListItem(dc)
        self.DrawInsertItemLine(dc)
        self.DrawTextEdit(dc)
        if folders.is_opening():
            w, h = self.GetClientSize()
            draw_spinner(dc, w / 2.0, h / 2.0, 14, (time.time() % 1.2) / 1.2 * math.pi * 2,
                         macroboxstyle.current().UI.ACCENT)

    def InitBuffer(self):
        # redraw only the changed rows when nothing else changed
        state = self.GetDrawnState()
        last, self.drawn_state = getattr(self, 'drawn_state', None), state
        if state is not None and last is not None and self.DrawChangedRows(last, state):
            self.reInitBuffer = getattr(self, 'redraw_next', False)
            self.redraw_next = False
            return
        RectBox.InitBuffer(self)

    def GetDrawnState(self):
        '''(whole, scroll, {item: row state}), or None to draw whole'''
        lb = self.parent
        if hasattr(lb, 'innerList') is False or len(lb.innerList) == 0:
            return None
        listIdx = lb.selectedList
        inner = lb.innerList[listIdx]
        columns = lb.GetShownColumns()
        if any(getattr(column, 'key', None) in ('cover', 'wave') for column in columns)\
                or getattr(self, 'spinning', False) or folders.is_opening()\
                or self.TextEdit is not None\
                or self.FileDrop.insertItemIdx is not None or self.buffer.bmp is None:
            return None
        playbox = lb.parent.PlayBox
        mfeats = lb.parent.MFEATS
        if inner.title in (radio.BROWSE_TITLE, radio.RECENT_TITLE):
            favorites = tuple(sorted(radio.get_favorite_urls(lb)))
        elif inner.title not in radio.RADIO_TABS:
            favorites = tuple(library.get_favorite_tracks())
        else:
            favorites = ()
        whole = (tuple(self.GetSize()), tuple(self.buffer.bmp.GetSize()), lb.GetRowsHeight(),
                 listIdx, inner.Id, inner.title, id(inner.items), len(inner.items),
                 lb.GetVirtualPositionX(), tuple(lb.GetShownColumnsIdx()),
                 tuple(column.width for column in columns), lb.font.GetNativeFontInfoDesc(),
                 id(lb.st), favorites, getattr(self, 'star_hover', None),
                 getattr(self, 'star_down', None), tuple(mfeats.GetProcPath()),
                 frozenset(mfeats.GetTaskPath()))
        pathIdx = lb.GetColumnKeyToIdx('path')
        # folder tab only: a station's tab has no status
        browsing = inner.title == library.FOLDER_TITLE
        if browsing:
            statusIdx = lb.GetColumnKeyToIdx('status')
            nameIdx = lb.GetColumnKeyToIdx('filename')
        cue = playbox.cue
        here = cue.listId == inner.Id or audio.is_stream_path(cue.path)
        rows = {}
        selected = inner.selectedItems
        for item in lb.GetShownItemsIdx():
            if item >= len(inner.items):
                continue
            row = inner.items[item]
            playing = None
            if here and row[pathIdx] == cue.path:
                # the playing mark, as DrawListItem draws it
                playing = (playbox.IsStreamWaiting(), playbox.IsPlaying(),
                           playbox.AudioControl.pending, playbox.GetStreamConnecting(),
                           self.pending.SkipStopIcon)
            elif browsing and here and cue.path and row[statusIdx] == folders.FOLDER_STATUS\
                    and row[nameIdx] != folders.PARENT_NAME\
                    and folders.is_under(cue.path, row[pathIdx]):
                # a folder's mark: DrawFolderPlayingMark
                playing = (playbox.IsPlaying(), playbox.AudioControl.pending)
            rows[item] = (id(row), item in selected, playing)
        return whole, lb.GetVirtualPositionY(), rows

    def DrawChangedRows(self, last, state):
        '''redraw only the changed rows; False when it must be drawn whole'''
        whole, vpy, rows = state
        last_whole, last_vpy, last_rows = last
        row_size = self.parent.GetRowsHeight()
        dy = vpy - last_vpy
        if whole != last_whole or dy % row_size != 0:
            return False
        w, h = self.GetSize()
        if abs(dy) >= h:
            return False
        if dy != 0 and max(rows, default=-1) >= len(
                self.parent.innerList[self.parent.selectedList].items) - 1:
            # list end in sight: the ground under it moved too
            return False
        changed = [item for item, row in rows.items() if last_rows.get(item) != row]
        if dy != 0:
            # rows cut by the edge last time kept the old strip under them
            strip = (h + dy, h) if dy < 0 else (0, dy)
            changed += [item for item in rows if item not in changed
                        and item * row_size + vpy < strip[1]
                        and item * row_size + vpy + row_size > strip[0]]
        if dy == 0 and len(changed) == 0:
            return True
        dc = wx.BufferedDC(None, self.buffer.bmp)
        if dy != 0:
            dc.Blit(0, max(dy, 0), w, h - abs(dy), dc, 0, max(-dy, 0))
        region = wx.Region()
        for item in changed:
            region.Union(0, int(item * row_size + vpy), w, row_size)
        dc.SetDeviceClippingRegion(region)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.SetBackgroundMode(wx.TRANSPARENT)
        dc.Clear()
        self.DrawListItem(dc, only=set(changed))
        dc.DestroyClippingRegion()
        del dc
        return True

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
                    # the editor's ground under the cell
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

    def DrawListItem(self, dc, only=None):
        # only: the items to draw (DrawChangedRows), the rest left as drawn
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
        if only is None:
            self.tips.Clear()
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
        # numeric columns in monospace so digits line up
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
        ct = self.parent.st.LIST_BG_CONTRAST
        r, g, b = self.parent.st.LIST_BG_COLOR
        bgcolor_odd = [min(max(v, 0), 255) for v in (r - ct, g - ct, b - ct)]
        bgcolor_even = [min(max(v, 0), 255) for v in (r + ct, g + ct, b + ct)]
        # each text's row ground, for its cached picture
        n_grounds, s_grounds, m_grounds, ms_grounds = [], [], [], []
        selected_ground = tuple(self.parent.st.SELECTED_BG_COLOR)[:3]
        browsing_folder = self.parent.innerList[listIdx].title == library.FOLDER_TITLE
        for row, item in enumerate(shownItemIdx):
            if only is not None and item not in only:
                continue
            ground = tuple(bgcolor_odd if item % 2 == 0 else bgcolor_even)

            for i, col in enumerate(shownColIdx):
                column = columns[i]
                if item > len(self.parent.innerList[listIdx].items):
                    continue
                # cover or waveform drawn after the text, over the row's ground
                if listColumns[col].key in ('cover', 'wave'):
                    if browsing_folder and folders.is_folder_item(self.parent, item, listIdx):
                        continue
                    pictures.append((listColumns[col].key, row, item, column))
                    continue

                string = self.parent.innerList[listIdx].items[item][col]
                right_align = self.parent.innerList[listIdx].columns[col].right_align
                if col == statusIdx:
                    continue
                # limitedString = self.LimitTextLength(\
                #   dc, string, column.width-left_margin-15, tww)
                if right_align:
                    # cut in the monospace it is drawn in, not the list font
                    string = f'{string}'
                    fits = max(int((column.width - left_margin - 8) // mono_width), 0)
                    limitedString = string if len(string) <= fits\
                        else string[:max(fits - 1, 0)] + '\u2026'
                    self.tips.Add((column.x, row_size * row + rect.y - row_offset, column.width,
                                   row_size), string, limitedString)
                    tw = mono_width * len(limitedString)
                    txy = (column.x + column.width - left_margin - tw,
                           row_size * row + rect.y + top_margin - row_offset + mono_shift)
                    texts, xys, grounds = (ms_texts, ms_xys, ms_grounds)\
                        if self.parent.IsHighlightedItem(item) else (m_texts, m_xys, m_grounds)
                    texts.append(limitedString)
                    xys.append(txy)
                    grounds.append(selected_ground if grounds is ms_grounds else ground)
                    continue
                limitedString = self.LimitTextLength(
                    dc, string, column.width - left_margin - 8, tww)
                self.tips.Add((column.x, row_size * row + rect.y - row_offset, column.width,
                               row_size), string, limitedString)
                txy = (column.x + left_margin,
                       row_size * row + rect.y + top_margin - row_offset)
                if self.parent.IsHighlightedItem(item):
                    s_texts.append(limitedString)
                    s_xys.append(txy)
                    s_grounds.append(selected_ground)
                else:
                    n_texts.append(limitedString)
                    n_xys.append(txy)
                    n_grounds.append(ground)

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

        if shownItemIdx != [] and only is None:
            lines.append((rect.x, row_size * (row + 1) + rect.y - row_offset,
                          width, row_size * (row + 1) + rect.y - row_offset))

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
        # selection bar at the left
        bar = self.parent.st.SELECTED_BAR_COLOR
        dc.DrawRectangleList([(x, y, 3, h) for x, y, w, h in s_rects],
                             pens=wx.Pen(bar, 1), brushes=wx.Brush(bar))

        sel_bgcolor = self.parent.st.SELECTED_BG_COLOR
        fg, sel_fg = self.parent.st.LIST_FG_COLOR, self.parent.st.SELECTED_FG_COLOR
        self.DrawTexts(dc, self.parent.font, n_texts, n_xys, n_grounds, fg)
        self.DrawTexts(dc, self.parent.font, s_texts, s_xys, s_grounds, sel_fg)
        self.DrawTexts(dc, mono, m_texts, m_xys, m_grounds, fg)
        self.DrawTexts(dc, mono, ms_texts, ms_xys, ms_grounds, sel_fg)
        dc.SetFont(self.parent.font)
        color = self.parent.st.LIST_PN_COLOR
        dc.DrawLineList(lines, pens=wx.Pen(color, 0))
        self.DrawPictures(dc, pictures, listIdx, row_size, rect.y - row_offset,
                          bgcolor_odd, bgcolor_even, shownItemIdx)

        # draw status column
        procpath = self.parent.parent.MFEATS.GetProcPath()
        # queued: waits again even if analyzed by an older version
        taskpath = set(self.parent.parent.MFEATS.GetTaskPath())
        pathIdx = self.parent.GetColumnKeyToIdx('path')
        # starred: radio favorites (Browse) or favorite tracks
        favorites = set()
        # not starred: a faint outline
        outline = None
        if self.parent.innerList[listIdx].title != radio.RADIO_TITLE:
            bg = wx.Colour(self.parent.st.LIST_BG_COLOR)
            fg = wx.Colour(self.parent.st.LIST_FG_COLOR)
            outline = wx.Colour(*[int(a + (b - a) * 0.22) for a, b in
                                  zip(bg.Get()[:3], fg.Get()[:3])])
        if self.parent.innerList[listIdx].title in (radio.BROWSE_TITLE, radio.RECENT_TITLE,
                                                    radio.RADIO_TITLE):
            favorites = radio.get_favorite_urls(self.parent)
        elif self.parent.innerList[listIdx].title not in radio.RADIO_TABS:
            favorites = set(library.get_favorite_tracks())
        # stars and rings share one GraphicsContext (get_shared_gc)
        shared = []
        self.spinning = False
        # outlines and waiting rings drawn after the rows, one path each
        outlines, waiting = [], []
        playing_path = self.parent.parent.PlayBox.cue.path
        # folder songs: a waiting ring only when queued
        browsed = folders.is_browsed_only(self.parent.innerList[listIdx])
        # folder tab: folder icons where a song's star is
        folder_marks = []
        for row, item in enumerate(shownItemIdx):
            if only is not None and item not in only:
                continue
            for i, col in enumerate(shownColIdx):
                if col != orderIdx:
                    continue
                # 5 px right of the playing mark's ring (MARK_X)
                cx = columns[i].x + self.STAR_X
                # 1 px above the middle: a star's ink sits low in its box
                cy = row_size * row + rect.y - row_offset + row_size // 2
                star = 4 if item == getattr(self, 'star_down', None) else 5
                if self.parent.innerList[listIdx].items[item][statusIdx]\
                        == folders.FOLDER_STATUS:
                    folder_marks.append((cx + 0.5, cy + 0.5))
                    self.DrawFolderPlayingMark(dc, listIdx, item, columns[i].x + self.MARK_X,
                                               row_size * row + rect.y - row_offset
                                               + int((row_size - 8) * 0.5))
                    continue
                if self.parent.innerList[listIdx].items[item][pathIdx] in favorites:
                    draw_star(dc, cx, cy, star, macroboxstyle.current().UI.WARN)
                elif item == getattr(self, 'star_hover', None):
                    # under the pointer: where a click stars it
                    draw_star(dc, cx, cy, star, macroboxstyle.current().UI.BAR_TEXT_DIM)
                elif outline is not None:
                    outlines.append((cx + 0.5, cy + 0.5))
                # analyzing status
                status = self.parent.innerList[listIdx].items[item][statusIdx]
                # rects = (columns[i].x+1, row_size*row+rect.y-row_offset+1,\
                #   columns[i].width-2-22, row_size-1)
                rects = (columns[i].x + 1, row_size * row +
                         rect.y - row_offset + 1, 4, row_size - 1)
                # elif status == 'analyzing':
                #   dc.DrawRectangleList((rects,), pens=wx.Pen((80,80,255), 0),\
                #       brushes=wx.Brush(wx.Colour(100,100,255)))
                # analysis icons where the playing mark goes, none on the playing row
                path = self.parent.innerList[listIdx].items[item][pathIdx]
                # on the play mark's centre
                cy = row_size * row + rect.y - row_offset + int((row_size - 8) * 0.5) + 4.5
                unanalyzed = status == '' and browsed is False
                analysing = path in procpath or unanalyzed or path in taskpath
                if path in procpath:
                    draw_analysis_icon(dc, columns[i].x + self.MARK_X + 4, cy, True,
                                       shared=shared)
                    self.spinning = True
                elif unanalyzed or path in taskpath:
                    if path == playing_path:
                        # the playing mark goes over it
                        draw_analysis_icon(dc, columns[i].x + self.MARK_X + 4, cy, False,
                                           shared=shared)
                    else:
                        waiting.append((columns[i].x + self.MARK_X + 4, cy))
                elif status == 'error':
                    if self.parent.IsHighlightedItem(item):
                        bmp = images.listbox_brokenlink_black.GetBitmap()
                    else:
                        bmp = images.listbox_brokenlink_red.GetBitmap()
                    m = int((row_size - bmp.GetHeight()) * 0.5) - 1
                    dc.DrawBitmap(bmp, rects[0], rects[1] + m, useMask=False)
                # playing status: in its own tab; a station's in every tab
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
                # mark held while a file opens or a station connects, or it flickers
                playbox = self.parent.parent.PlayBox
                starting = playbox.AudioControl.pending\
                    or playbox.GetStreamConnecting() is not None
                if playbox.IsStreamWaiting():
                    # station connecting or buffering: a turning ring in the mark's place
                    self.pending.SkipStopIcon = False
                    offset = int((row_size - 8) * 0.5)
                    draw_analysis_icon(dc, column.x + self.MARK_X + 4,
                                       row_size * row + rect.y - row_offset + offset + 4.5, True,
                                       shared=shared)
                    self.spinning = True
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
                        # cut out of the analysis icon by a pixel of the row's ground
                        halo = self.GetHalo(bmp, self.GetRowGround(item, row, shownItemIdx,
                                                                   bgcolor_odd, bgcolor_even))
                        for dx, dy in self.HALO_STEPS:
                            dc.DrawBitmap(halo, mx + dx, my + dy, useMask=False)
                    dc.DrawBitmap(bmp, mx, my, useMask=False)
                else:
                    # centred on the play mark (9 px, MARK_X + 4)
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
        draw_star_outlines(dc, outlines, 5, outline, shared=shared)
        draw_folder_icons(dc, folder_marks, macroboxstyle.current().UI.BAR_TEXT_DIM,
                          shared=shared)
        draw_waiting_icons(dc, waiting, shared=shared)

    def DrawTexts(self, dc, font, texts, xys, grounds, ink):
        '''texts at xys; non-Latin ones from cached pictures (GDI font lookup is slow)'''
        dc.SetFont(font)
        latin = [(text, xy) for text, xy in zip(texts, xys) if text.isascii()]
        if latin:
            dc.DrawTextList([v[0] for v in latin], [v[1] for v in latin],
                            foregrounds=wx.Colour(*ink))
        others = [(text, xy, ground) for text, xy, ground in zip(texts, xys, grounds)
                  if not text.isascii()]
        if not others:
            return
        ink = tuple(ink)[:3]
        desc = font.GetNativeFontInfoDesc()
        source = wx.MemoryDC()
        for text, (x, y), ground in others:
            key = (desc, text, ink, ground)
            bmp = TEXT_PICTURES.get(key)
            if bmp is None:
                if len(TEXT_PICTURES) > 20000:
                    TEXT_PICTURES.clear()
                tw, th = dc.GetTextExtent(text)
                bmp = wx.Bitmap(max(tw, 1) + 4, max(th, 1) + 2)
                source.SelectObject(bmp)
                source.SetBackground(wx.Brush(wx.Colour(*ground)))
                source.Clear()
                source.SetBackgroundMode(wx.TRANSPARENT)
                source.SetFont(font)
                source.SetTextForeground(wx.Colour(*ink))
                source.DrawText(text, 2, 0)
                source.SelectObject(wx.NullBitmap)
                TEXT_PICTURES[key] = bmp
            source.SelectObject(bmp)
            dc.Blit(x - 2, y, bmp.GetWidth(), bmp.GetHeight(), source, 0, 0)
        source.SelectObject(wx.NullBitmap)

    def DrawFolderPlayingMark(self, dc, listIdx, item, x, y):
        # subfolder of the playing song: its mark, dimmed when silent, not on '..'
        inner = self.parent.innerList[listIdx]
        playbox = self.parent.parent.PlayBox
        path = playbox.cue.path
        if playbox.cue.listId != inner.Id or not path or audio.is_stream_path(path):
            return
        row = inner.items[item]
        if row[self.parent.GetColumnKeyToIdx('filename', listIdx)] == folders.PARENT_NAME:
            return
        if folders.is_under(path, row[self.parent.GetColumnKeyToIdx('path', listIdx)]) is False:
            return
        font_color = self.parent.st.SELECTED_FG_COLOR if self.parent.IsHighlightedItem(item)\
            else self.parent.st.LIST_FG_COLOR
        bmp = self.bmp.playing.white if sum(font_color[:3]) / 3.0 > 125\
            else self.bmp.playing.black
        if (playbox.IsPlaying() or playbox.AudioControl.pending) is False:
            bmp = self.bmp.playing.dimmed[bmp is self.bmp.playing.white]
        dc.DrawBitmap(bmp, x, y, useMask=False)

    # the playing mark's cut-out: its shape grown by a pixel
    HALO_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1))

    def GetRowGround(self, item, row, shownItemIdx, odd, even):
        # the row's ground: selected or striped
        if self.parent.IsHighlightedItem(item):
            return wx.Colour(self.parent.st.SELECTED_BG_COLOR)
        return wx.Colour(*(odd if shownItemIdx[row] % 2 == 0 else even)[:3])

    def GetHalo(self, bmp, ground):
        # the mark's shape in the ground's colour, cached by mark and ground
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
    ORDER_GAP = 10

    def KeepOrderRoom(self, columns, orderIdx, digit, margin):
        # the # column widened for its numbers, the room from the file name's;
        # one width for every tab or the columns jump on a tab change
        if orderIdx is None or orderIdx < 0:
            return
        lists = self.parent.innerList
        current = lists[self.parent.selectedList]
        if current.title in radio.RADIO_TABS:
            tabs = [current]
        else:
            tabs = [v for v in lists if v.title not in radio.RADIO_TABS]
        count = max(len(v.items) for v in tabs)
        need = self.STAR_X + 5 + self.ORDER_GAP + digit * len(str(max(count, 1))) + margin
        if columns[orderIdx].show is False or columns[orderIdx].width >= need:
            return
        for inner in tabs:
            for column in inner.columns:
                if column.key == 'order' and column.width < need:
                    column.width = need
        # drawn before the header exists
        header = getattr(self.parent, 'Header', None)
        if header is not None:
            wx.CallAfter(header.SetAutoColumnWidth)

    # the # column's marks: the playing mark's left, the star's centre
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
        # waveforms dimmed but the playing song's
        cue = self.parent.parent.PlayBox.cue
        playing = cue.path if cue.listId == self.parent.innerList[listIdx].Id else None
        square = self.parent.parent.parent.IsCoverSquareOn()
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
                                           width, height, ground, square=square)
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
        # the star's x span in the # column, None without it
        x = self.parent.GetVirtualPositionX()
        for column in self.parent.GetShownColumns():
            if column.key == 'order':
                return (x + self.STAR_X - 7, x + self.STAR_X + 8)
            x += column.width
        return None

    def GetStarItem(self, event):
        # the song or station under the pointer in the star's span, else None
        if self.onClient is False:
            return None
        span = self.GetStarSpan()
        if span is None or not span[0] <= event.X <= span[1]:
            return None
        item = self.parent.PosY2Item(event.Y)
        if item < 0 or item >= self.parent.GetItemsLength():
            return None
        # folder rows are never starred
        if folders.is_folder_view(self.parent) and folders.is_folder_item(self.parent, item):
            return None
        return item

    def HandleEventStar(self, event):
        # a star click toggles it, not the selection; True when it was the star's
        # drawn pressed while held
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
        if self.parent.innerList[self.parent.selectedList].title in (
                radio.BROWSE_TITLE, radio.RECENT_TITLE, radio.RADIO_TITLE):
            radio.toggle_favorite(self.parent.parent, path)
        else:
            toggle_favorite_tracks(self.parent, [path])
        return True

    # redraw interval while icons turn
    SPIN_INTERVAL = 1.0 / 30

    def CATCH_EVT_GLOBAL(self, event):
        # only when a turning icon was in the rows last drawn
        turning = getattr(self, 'spinning', False) or folders.is_opening()
        if turning and time.time() - getattr(self, 'spin_lap', 0.0) >= self.SPIN_INTERVAL:
            self.spin_lap = time.time()
            self.reInitBuffer = True
        if self.parent.parent.HasToSkipEvent():
            return
        # a cut cell's whole text, not while a button is held
        held = event.LeftIsDown or event.RightIsDown
        self.tips.Update((event.X, event.Y) if self.onClient and held is False else None)
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
        selected = folders.get_drag_paths(self.parent, selected)
        if not selected:
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

    def IsOwnPlace(self, insert):
        # one block: before, in or right after it
        rows = sorted(self.parent.GetSelectedItems())
        if len(rows) == 0 or rows[-1] - rows[0] + 1 != len(rows):
            return False
        return rows[0] <= insert <= rows[-1] + 1

    def HandleEventFileDropPending(self, event):
        if self.parent.IsFilteredAll():
            return
        # the folder tab takes no drop: no insert line
        if folders.is_folder_view(self.parent):
            self.FileDrop.insertItemIdx = None
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
        insert = event.insertItemIdx
        if self.FileDrop.itemDrag and self.IsOwnPlace(insert):
            insert = None
        self.FileDrop.insertItemIdx = insert
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
            # with Ctrl, rows added to the selection
            self.parent.ShiftSelectItems(event.itemIdx, add=event.ControlDown)
            self.pending.SkipControlSelectItem = event.ControlDown

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

        if event.ControlDown and event.isSelectedItem and event.ShiftDown is False\
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
        self.ShowItemMenu(event.itemIdx, (event.x, event.y))

    def ShowItemMenu(self, item, xy):
        '''the row's menu at a screen xy; a folder row gets its own'''
        if folders.is_folder_view(self.parent):
            inner = self.parent.innerList[self.parent.selectedList]
            if folders.is_folder_item(self.parent, item):
                self.parent.SelectAndFocusItem(item)
                path = self.parent.GetItemValueByColumnKey(item, 'path')
                parent = self.parent.GetItemValueByColumnKey(item, 'filename')\
                    == folders.PARENT_NAME
                entry = Struct(kind='row', item=item, path=path, parent=parent)
                self.DirectDraw()
                self.parent.parent.SetPopupMenu(ListBoxPopupFolder(self.parent.parent, entry),
                                                xy)
                return
            inner.selectedItems = [v for v in inner.selectedItems
                                   if folders.is_folder_item(self.parent, v) is False]
        self.DirectDraw()
        self.parent.parent.SetPopupMenu(ListBoxPopupItem(self), xy)

    def ShowSelectedItemMenu(self):
        # context menu key: the selected row's menu, scrolled into view
        listbox = self.parent
        selected = listbox.GetSelectedItems()
        if not selected:
            return
        focused = listbox.GetFocusedItem()
        item = focused if focused in selected else selected[-1]
        if item < 0 or item >= listbox.GetItemsLength():
            return
        if listbox.IsItemInViewRange(item) is False:
            listbox.FocusItem(item)
        row = listbox.GetRowsHeight()
        # under the row, past the star and the number
        y = listbox.GetVirtualPositionY() + 1 + (item + 1) * row
        x = min(self.STAR_X + 48, self.GetClientSize().width - 1)
        self.ShowItemMenu(item, tuple(self.ClientToScreen((x, y))))

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

        # menu key or Shift+F10: the selected row's menu, not in a text field
        menu_key = event.KeyCode == wx.WXK_WINDOWS_MENU\
            or (event.ShiftDown and event.KeyCode == wx.WXK_F10)
        if menu_key and namespace is None and self.TextEdit is None\
                and isinstance(wx.Window.FindFocus(), wx.TextCtrl) is False:
            self.ShowSelectedItemMenu()

        # folder tab: Enter opens or plays, Backspace opens the parent
        if folders.is_folder_view(self.parent):
            if event.KeyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and namespace is None:
                self.parent.LeftDoubleClick(None)
            if event.KeyCode == wx.WXK_BACK and namespace is None:
                folders.go_up(self.parent.parent)
            if namespace in self.SONG_KEYS and folders.get_selected_folders(self.parent):
                namespace = None

        if namespace == 'playlist_toggle':
            self.parent.parent.parent.ToggleListTabShow()

        if namespace == 'open_id3tageditor':
            self.OpenItemEditBox(event)

        if namespace == 'look_up_cover':
            # as the menu's Look Up Cover
            look_up_cover(self.parent)

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

    SONG_KEYS = ('open_id3tageditor', 'look_up_cover', 'open_websearch_1', 'open_websearch_2',
                 'open_websearch_3')

    def OpenScriptEditBox(self, event):
        self.parent.parent.parent.OnScriptEditor(event)

    def OpenItemEditBox(self, event):
        self.parent.parent.parent.DialogBox = ItemEditBox(self)
        x, y, w, h = self.parent.parent.parent.GetRect()
        width, height = self.parent.parent.parent.DialogBox.GetSize()
        self.parent.parent.parent.DialogBox.SetRect(
            (x + (w - width) // 2, y + (h - height) // 2, width, height))
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
        # drawn when idle: the list box lays out right after a resize
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
        self.tips = uikit.CutTips(self)
        self.pending = Struct(autoColumnWidthIdx=None, downColumnIdx=None,
                              insertColumnIdx=None, dragColumnWidth=None, ColumnSortDown=False,
                              LeftDoubleClick=False)
        self.InitBuffer()

    # least file name width; the rest is scrolled to
    FILENAME_LEAST = 160

    def SetAutoColumnWidth(self):
        # the file name column takes the room the other shown columns leave
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
        # fit the shown column idx to its widest text
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
            string = f'{self.parent.innerList[self.parent.selectedList].items[item][cid]}'
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
        self.parent.SyncColumnsToAll()

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
        # column names as rack labels: capitals, dimmed, centred
        font = uikit.get_font(10)
        dc.SetFont(font)
        tw, th = FONT_ITEM_SIZE
        # from under the top line to the first row, the capitals centred
        height = self.GetClientSize().height + 1
        margin_top = int(round(uikit.get_caps_top(font, 2, height - 2)))
        # shownColumns = self.parent.GetShownColumns()
        shownColumnsIdx = self.parent.GetShownColumnsIdx()
        lastSortedColumn = self.parent.GetLastSortedColumn()
        sortedIdx = [i for i, v in enumerate(shownColumnsIdx) if v == lastSortedColumn[0]]
        xys = list()
        texts = list()
        self.tips.Clear()
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
            self.tips.Add(rect, name, title)
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
        held = event.LeftIsDown or event.RightIsDown
        self.tips.Update((event.X, event.Y) if self.onClient and held is False else None)
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
        # resize cursor over a column edge and while dragging
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
            if event.drag.splitterIdx is not None:
                self.parent.SyncColumnsToAll()
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
        self.parent.SyncColumnsToAll()
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
        # search Browse or the library now; a filter follows the typing
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
        # select by label: the hidden combo keeps the choices
        self.SetStringSelection(label)
        self.parent.reInitBuffer = True
        if self.parent.browse_mode:
            # radio Browse: the directory by the chosen category
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
        # drawn instead: the combo keeps the choices hidden
        self.SearchComboFilter.Hide()
        self.field_rect = self.clear_rect = self.chooser_rect = wx.Rect(0, 0, 0, 0)
        self.sidebar_rect = wx.Rect(0, 0, 0, 0)
        # the star: starred songs only, for this session
        self.star_rect = wx.Rect(0, 0, 0, 0)
        self.starred = False
        self.scope_rects = []
        self.chooser_width = 96
        self.drawn = None
        # the selected tab's search state (SetMode)
        self.mode = 'playlist'
        self.scope = GetPreference('search_scope') or 'list'
        self.browse_mode = False
        self.browse_choices = []
        self.live_search = None
        self.searched = None
        # the playlist searched from, restored when the field empties
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
        # hint and scope parts kept; the mode set again only on a change
        self.SetMode(self.mode, force=True)
        self.InitBuffer()

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        for i in range(len(self.rects[:-1])):
            if self.IsInRect(self.rects[i], xy):
                return i
        return None

    # what the field searches, by the selected tab
    FAVORITE_KEYS = (('Name', 'filename'), ('Tags', 'genre'))
    SCOPES = (('list', 'THIS LIST'), ('library', 'LIBRARY'))
    LIVE_SEARCH_MS = 600
    LIBRARY_SEARCH_MS = 350
    LIVE_SEARCH_LEAST = 2

    def IsLibraryScope(self):
        return self.mode == 'playlist' and self.scope == 'library'

    def SetScope(self, scope):
        # playlist search: filter released for the library scope, and back
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
        # library search: results in the Search tab
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
        self.parent.StatusBox.alarm = f'{len(found)} found for "{text}" in the library'
        self.parent.StatusBox.alarm_color = 'blue'
        self.parent.ListTab.TabList.reInitBuffer = True
        listbox.reInitBuffer = True

    def GetMode(self):
        listbox = self.parent.ListBox
        title = listbox.innerList[listbox.selectedList].title
        if title == radio.BROWSE_TITLE:
            return 'browse'
        if title == library.FOLDER_TITLE:
            return 'folder'
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
            # release the filter: it would hide the directory's rows
            text.ChangeValue('')
            self.parent.ListBox.SetFilterOffAll()
            self.SetHints('Station name, searched as you type', 'Station name')
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
            # recent stations too
            self.SetHints('Filter stations by name or tags', 'Filter stations')
            combo.Set([label for label, _ in self.FAVORITE_KEYS])
            combo.SetSelection(0)
            self.query_columnKey = self.FAVORITE_KEYS[0][1]
            self.chooser_width = 96
        elif mode == 'folder':
            self.SetFolderHints()
            self.query_columnKey = getattr(self, 'playlist_key', 'filename')
            combo.Set(list(combo.choices))
            combo.SetStringSelection(self.query_columnKey.capitalize()
                                     if self.query_columnKey.capitalize() in combo.choices
                                     else combo.choices[0])
            self.chooser_width = 96
        elif self.scope == 'library':
            self.SetHints('Search all playlists (found in the Search tab)',
                          'Search all playlists')
            # chooser kept in place but shown off, so the field width stays
            self.chooser_width = 96
        else:
            self.SetHints('Filter this playlist', 'Filter')
            self.query_columnKey = getattr(self, 'playlist_key', 'filename')
            combo.Set(list(combo.choices))
            combo.SetStringSelection(self.query_columnKey.capitalize()
                                     if self.query_columnKey.capitalize() in combo.choices
                                     else combo.choices[0])
            self.chooser_width = 96
        self.OnSize()

    def OnSearchTyped(self, event):
        # Browse and library searched once typing pauses; filters follow typing
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
        # field emptied: back to the playlist searched from
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
        radio.browse(self.parent, f'Name: {text}', lambda: radio.get_stations(name=text))

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.HasToSkipEvent():
            return
        mode = self.GetMode()
        if mode != self.mode:
            self.SetMode(mode)
        self.HandleEventDrawnControls(event)
        if mode == 'browse' or self.IsLibraryScope():
            # directory and library rows are not filtered
            return
        if self.onClient and event.LeftDown\
                and self.parent.ListBox.List.TextEdit is not None:
            self.parent.ListBox.List.TextEdit.CommitText()
        self.OverrideEventFromParent(event)
        self.HandleEventFilterQuery(event)
        self.HandleEventButtonColor(event)
        value = self.SearchText.GetValue()
        if len(value) > 0 or self.starred:
            if self.parent.ListBox.IsFilteredAll() is False:
                # turned on: rows filtered at the next event
                self.last_query = None
            self.parent.ListBox.SetFilterOnAll()
        elif len(value) == 0:
            self.parent.ListBox.SetFilterOffAll()
        # self.HandleEventSearchPopup(event)

    def ToggleStarred(self):
        # starred songs only, with or without the text filter
        self.starred = not self.starred
        listbox = self.parent.ListBox
        listbox.filter_starred = self.starred
        value = self.SearchText.GetValue()
        if self.starred or value:
            listbox.SetFilterOnAll()
            listbox.FilterItemsAll(self.query_columnKey, value)
            self.last_query = value
        else:
            listbox.SetFilterOffAll()
        listbox.reInitBuffer = True
        listbox.List.reInitBuffer = True
        listbox.SliderV.reInitBuffer = True
        self.reInitBuffer = True
        radio.tell(self.parent, 'Starred tracks only' if self.starred else 'All tracks')

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
        # rows drawn by the inner list, not the box around it
        self.parent.ListBox.reInitBuffer = True
        self.parent.ListBox.List.reInitBuffer = True
        self.parent.ListBox.SliderV.reInitBuffer = True
        self.reInitBuffer = True

    # Draw ListBoxList

    # field spacing, magnifier and clear mark widths
    FIELD_PAD = 8
    MAGNIFIER = 9
    MARK = 7

    def SetRectDraw(self, dc):
        # rounded field: magnifier, text box, clear mark; accent edge when focused
        tokens = macroboxstyle.current().UI
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        x, y, w, h = self.field_rect
        # whole pixels: a half-pixel edge blurs over two rows
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(tokens.CONTROL_BG)))
        gc.DrawRoundedRectangle(x, y, w, h, uikit.RADIUS)
        if self.SearchText.onClient:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(tokens.ACCENT)).Width(1)))
            gc.SetBrush(wx.NullGraphicsBrush)
            gc.DrawRoundedRectangle(x, y, w - 1, h - 1, uikit.RADIUS)
        ink = wx.Colour(tokens.BAR_TEXT_DIM)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.4)))
        gc.SetBrush(wx.NullGraphicsBrush)
        # magnifier 7 across, a row above the field's middle, FIELD_PAD in
        cx, cy = x + self.FIELD_PAD + 3.5, y + h / 2.0 - 1
        gc.DrawEllipse(cx - 3.5, cy - 3.5, 7, 7)
        gc.StrokeLine(cx + 2.5, cy + 2.5, cx + 5.2, cy + 5.2)
        if self.SearchText.GetValue():
            # MARK across, FIELD_PAD from the edge
            half = self.MARK / 2.0
            cx, cy = x + w - self.FIELD_PAD - half, y + h / 2.0
            gc.StrokeLine(cx - half, cy - half, cx + half, cy + half)
            gc.StrokeLine(cx - half, cy + half, cx + half, cy - half)
        pointer = self.ScreenToClient(wx.GetMousePosition())
        if self.chooser_rect.width > 0:
            if self.IsLibraryScope():
                uikit.draw_button(dc, self.chooser_rect, label='All fields', disabled=True)
            else:
                label = self.SearchComboFilter.GetStringSelection()
                uikit.draw_button(dc, self.chooser_rect, label=f'{label}  \u25be',
                                  hover=self.IsInRect(self.chooser_rect, pointer))
        uikit.draw_button(dc, self.sidebar_rect, icon='menu',
                          on=self.parent.parent.IsListTabShowOn(),
                          hover=self.IsInRect(self.sidebar_rect, pointer))
        # off in the library scope: not filtered
        uikit.draw_button(dc, self.star_rect, icon='starred' if self.starred else 'star',
                          on=self.starred, disabled=self.IsLibraryScope(),
                          hover=self.IsInRect(self.star_rect, pointer))
        # playlist scope: this list or the library, the lit one drawn last
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
        # keys 21 rows tall: odd so the capitals centre
        # 6 rows above and below them, as at the ends and between
        top = gap = 6
        right = w - gap
        self.chooser_rect = wx.Rect(right - chooser, top, chooser, h - 11)
        if chooser:
            right -= chooser + gap
        # the scope switch left of the chooser, for a playlist
        self.scope_rects = []
        if self.mode == 'playlist':
            for key, label in self.SCOPES[::-1]:
                width = 74
                right -= width
                self.scope_rects.insert(0, (key, wx.Rect(right, top, width, h - 11), label))
                # joined: a segmented switch sharing its edge
                right += 1
            right -= 1 + gap
        # sidebar key at the left, then the star, then the field
        self.sidebar_rect = wx.Rect(gap, top, 26, h - 11)
        left = gap + 26 + gap
        self.star_rect = wx.Rect(0, 0, 0, 0)
        if self.mode in ('playlist', 'folder'):
            self.star_rect = wx.Rect(left, top, 26, h - 11)
            left += 26 + gap
        # as tall as the keys and on their rows
        self.field_rect = wx.Rect(left, top, max(0, right - left), h - 11)
        x, y, fw, fh = self.field_rect
        # FIELD_PAD between edge, magnifier, text, clear mark and edge
        self.clear_rect = wx.Rect(x + fw - self.FIELD_PAD * 2 - self.MARK, y,
                                  self.FIELD_PAD * 2 + self.MARK, fh)
        tokens = macroboxstyle.current().UI
        self.SearchText.SetBackgroundColour(tokens.CONTROL_BG)
        self.SearchText.SetForegroundColour(tokens.BAR_TEXT)
        # no text control margins
        self.SearchText.SetMargins(0, 0)
        th = min(self.SearchText.GetBestSize().height, fh - 2)
        left = self.FIELD_PAD + self.MAGNIFIER + self.FIELD_PAD
        right = self.FIELD_PAD + self.MARK + self.FIELD_PAD
        # a row above the box's middle: the capitals on the magnifier's rows
        self.SearchText.SetRect((x + left, y + (fh - th) // 2 - 1, max(0, fw - left - right),
                                 th))
        self.FitHint()
        self.text_best = self.SearchText.GetBestSize().height
        self.text_xys = ((10, 5),)
        self.DirectDraw()

    def SetFolderHints(self):
        # the open folder in the hint, filtered as a playlist
        path = folders.get_current() or ''
        self.SetHints(f'Filter {path}' if path else 'Filter this folder',
                      f'Filter {folders.get_name(path)}' if path else 'Filter')

    def SetHints(self, full, short):
        # the field's hint, its short one when the field is narrow (FitHint)
        self.hints = (full, short)
        self.FitHint()

    def FitHint(self):
        '''the hint whole, else short, else ellipsized, else none'''
        hints = getattr(self, 'hints', None)
        if hints is None:
            return
        room = self.SearchText.GetSize().width - 8
        hint = ''
        for text in hints:
            if self.SearchText.GetTextExtent(text)[0] <= room:
                hint = text
                break
        else:
            text = hints[-1]
            while len(text) > 1 and self.SearchText.GetTextExtent(text + '\u2026')[0] > room:
                text = text[:-1].rstrip()
            if len(text) > 1:
                hint = text + '\u2026'
        if hint != self.SearchText.GetHint():
            self.SearchText.SetHint(hint)
            if hint in hints:
                self.SearchText.UnsetToolTip()
            else:
                self.SearchText.SetToolTip(hints[-1])

    def HandleEventDrawnControls(self, event):
        # chooser opens a menu, clear mark empties, elsewhere focuses the text
        point = (event.X, event.Y)
        state = (self.IsInRect(self.chooser_rect, point) and self.onClient,
                 self.IsInRect(self.sidebar_rect, point) and self.onClient,
                 self.parent.parent.IsListTabShowOn(),
                 self.IsInRect(self.star_rect, point) and self.onClient, self.starred,
                 [self.IsInRect(rect, point) and self.onClient for _, rect, _ in
                  self.scope_rects], self.scope,
                 self.SearchText.onClient, bool(self.SearchText.GetValue()),
                 self.SearchComboFilter.GetStringSelection())
        if state != self.drawn:
            self.drawn = state
            # asked till drawn: a DirectDraw too soon after the last does nothing
            self.reInitBuffer = True
            self.DirectDraw()
        if event.LeftDown is False or self.onClient is False:
            return
        if self.IsInRect(self.sidebar_rect, point):
            self.parent.parent.ToggleListTabShow()
            return
        if self.IsInRect(self.star_rect, point):
            if self.IsLibraryScope() is False:
                self.ToggleStarred()
            return
        for key, rect, _ in self.scope_rects:
            if self.IsInRect(rect, point):
                self.SetScope(key)
                return
        if self.chooser_rect.width > 0 and self.IsLibraryScope() is False\
                and self.IsInRect(self.chooser_rect, point):
            menu = wx.Menu()
            for label in self.SearchComboFilter.GetStrings():
                item = menu.AppendCheckItem(wx.ID_ANY, label)
                item.Check(label == self.SearchComboFilter.GetStringSelection())
                menu.Bind(wx.EVT_MENU, lambda e, label=label: self.SearchComboFilter.Choose(label),
                          item)
            # under the chooser, from its left
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


class CoverDrop(wx.FileDropTarget):

    def __init__(self, field):
        wx.FileDropTarget.__init__(self)
        self.field = field

    def OnDropFiles(self, x, y, filenames):
        self.field.ChooseFile(filenames[0])
        return True


# every cover's menu items, in this order
COVER_ITEMS = ('Copy Cover', 'Fix Scan', 'Crop to Square', 'Edit Cover...', 'Undo Cover Change')
COVER_PRESETS = {'Fix Scan': 'scan', 'Crop to Square': 'square'}
COVER_TIP = 'Click to edit the cover; right-click for more'
COVER_HOVER_WORD = 'Edit'


def draw_cover_edge(gc, x, y, w, h, hover, ground):
    # quiet edge; hovered: dimmed, an Edit pill
    ui = macroboxstyle.current().UI
    # the picture's corners cut back to the ground, inside the line
    corners = gc.CreatePath()
    corners.AddRectangle(x, y, w + 1, h + 1)
    corners.AddRoundedRectangle(x + 0.5, y + 0.5, w, h, uikit.RADIUS)
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(ground)))
    gc.FillPath(corners, wx.ODDEVEN_RULE)
    if hover:
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(0, 0, 0, 60))))
        gc.DrawRoundedRectangle(x, y, w, h, uikit.RADIUS)
        uikit.set_font(gc, uikit.get_font(uikit.LABEL, bold=True), wx.WHITE)
        tw, th = gc.GetTextExtent(COVER_HOVER_WORD)[:2]
        pw, ph = tw + 20, th + 10
        px, py = x + (w - pw) / 2.0, y + (h - ph) / 2.0
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(0, 0, 0, 170))))
        gc.DrawRoundedRectangle(px, py, pw, ph, ph / 2.0)
        gc.DrawText(COVER_HOVER_WORD, px + 10, py + 5)
    gc.SetBrush(wx.NullGraphicsBrush)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(ui.FIELD_EDGE)).Width(1)))
    gc.DrawRoundedRectangle(x, y, w, h, uikit.RADIUS)


class CoverPicture(wx.Window):

    '''a cover picture, hovered as every cover'''

    def __init__(self, parent, size):
        wx.Window.__init__(self, parent, size=size, style=wx.BORDER_NONE)
        self.bitmap = None
        self.hover = False
        self.active = False
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self.SetHover(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.SetHover(False))

    def SetBitmap(self, bitmap):
        self.bitmap = bitmap
        self.Refresh()

    def SetActive(self, active):
        if active == self.active:
            return
        self.active = active
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND if active else wx.CURSOR_ARROW))
        self.SetToolTip(COVER_TIP if active else '')
        self.Refresh()

    def SetHover(self, hover):
        self.hover = hover
        self.Refresh()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        if self.bitmap is not None and self.bitmap.IsOk():
            dc.DrawBitmap(self.bitmap, (w - self.bitmap.GetWidth()) // 2,
                          (h - self.bitmap.GetHeight()) // 2)
        draw_cover_edge(wx.GraphicsContext.Create(dc), 0, 0, w - 1, h - 1,
                        self.hover and self.active, self.GetParent().GetBackgroundColour())


def append_cover_items(menu, shown, changed, act):
    '''COVER_ITEMS into menu, act(name) after it'''
    picture = shown is not None and listimages.is_square(shown) is not None
    for name in COVER_ITEMS:
        enable = changed if name == 'Undo Cover Change' else picture
        if name == 'Crop to Square':
            enable = picture and listimages.is_square(shown) is False
        item = menu.Append(wx.ID_ANY, name)
        item.Enable(enable)
        menu.Bind(wx.EVT_MENU, lambda e, name=name: wx.CallAfter(act, name), item)


def preset_cover(source, edit, preset, autos=None):
    '''the edit with Fix Scan or Crop to Square in it, None if not a picture'''
    picture = listimages.open_picture(source)
    if picture is None:
        return None
    return listimages.preset_edit(picture, edit, preset, autos)


class CoverField(wx.Window):

    '''the editor's cover: the song's or a chosen one, marked NEW or REMOVE'''

    WILDCARD = 'Images (*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.gif)|' \
        '*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.gif'

    def __init__(self, parent, pos, size):
        wx.Window.__init__(self, parent, pos=pos, size=size, style=wx.BORDER_NONE)
        self.data = None
        self.chosen = None
        self.remove = False
        self.path = None
        self.note = ''
        self.bitmap = None
        self.hover = False
        # (picture, edit, edited picture) of the last edit made here
        self.edited = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetToolTip(wx.ToolTip(f'{COVER_TIP}\nWithout one: click to choose an image, or drop'
                                   ' one here. Changed in the file\'s tags when saved.'))
        self.SetDropTarget(CoverDrop(self))
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_UP, self.OnClick)
        self.Bind(wx.EVT_RIGHT_UP, self.OnMenu)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self.SetHover(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.SetHover(False))

    def SetHover(self, hover):
        self.hover = hover
        self.Refresh()

    def SetSong(self, path):
        # the song's own cover, nothing chosen
        try:
            data = listimages.read_cover(path)
        except Exception:
            data = None
        self.path = path
        self.chosen = None
        self.remove = False
        self.edited = None
        self.SetData(data, '' if data else 'No cover')

    def SetData(self, data, note=''):
        self.data, self.note, self.bitmap = data, note, None
        if data:
            try:
                image = wx.Image(io.BytesIO(data))
            except Exception:
                image = None
            if image is not None and image.IsOk():
                w, h = self.GetClientSize()
                scale = min((w - 2) / float(image.GetWidth()), (h - 2) / float(image.GetHeight()))
                self.bitmap = wx.Bitmap(image.Scale(max(1, int(image.GetWidth() * scale)),
                                                    max(1, int(image.GetHeight() * scale)),
                                                    wx.IMAGE_QUALITY_HIGH))
        self.Refresh()

    def SetChosen(self, data):
        # a picture to be put in the tags (the page saved)
        if listimages.make_cover(data) is None:
            self.SetNote('Not an image')
            return
        self.chosen = data
        self.remove = False
        self.SetData(data)

    def SetRemove(self):
        # the tags' pictures to be taken out (the page saved)
        self.chosen = None
        self.remove = True
        self.SetData(None, 'No cover')

    def HasChange(self):
        return self.chosen is not None or self.remove

    def SetNote(self, note):
        # a word over the cover (loading, a failure), the cover kept
        self.note = note
        self.Refresh()

    def Saved(self):
        self.chosen = None
        self.remove = False
        self.Refresh()

    def OnMenu(self, event):
        # the editor's menu (ItemEditBox.MakeMenu), the cover's items in it
        self.GetTopLevelParent().ShowMenu(self)

    def GetShown(self):
        return self.chosen if self.chosen is not None else None if self.remove else self.data

    def AppendMenu(self, menu):
        # what puts a picture here, then the items every cover has
        choose = menu.Append(wx.ID_ANY, 'Choose Cover Image...')
        menu.Bind(wx.EVT_MENU, lambda e: self.ChooseImage(), choose)
        paste = menu.Append(wx.ID_ANY, 'Paste Cover')
        paste.Enable(has_copied_cover())
        menu.Bind(wx.EVT_MENU, lambda e: self.SetChosen(copied_cover['data']), paste)
        remove = menu.Append(wx.ID_ANY, 'Remove Cover')
        remove.Enable(bool(self.data) and not self.remove or self.chosen is not None)
        menu.Bind(wx.EVT_MENU, lambda e: self.SetRemove(), remove)
        menu.AppendSeparator()
        shown = self.GetShown()
        append_cover_items(menu, shown, self.HasChange() and self.path is not None,
                           lambda name: self.DoCoverItem(name, shown))

    def DoCoverItem(self, name, shown):
        if name == 'Copy Cover':
            # the main panel
            copy_cover(self.GetTopLevelParent().parent.parent.parent, self.path, shown)
        elif name in COVER_PRESETS:
            source, edit = self.GetEditSource(shown)
            edit = preset_cover(source, edit, COVER_PRESETS[name])
            result = None if edit is None else listimages.edit_cover(source, edit)
            self.SetEdit(source, edit, result)
        elif name == 'Edit Cover...':
            self.EditByHand(shown)
        elif name == 'Undo Cover Change':
            # back to the song's own, the change not saved
            self.SetSong(self.path)

    def GetEditSource(self, data):
        # (picture, edit): an edit of ours opened again from its own picture
        if self.edited is not None and self.edited[2] == data:
            return self.edited[:2]
        return data, None

    def SetEdit(self, source, edit, result=None):
        if result is None:
            self.SetNote('Not an image')
            return
        self.SetChosen(result)
        self.edited = (source, edit, result)

    def EditByHand(self, data):
        source, edit = self.GetEditSource(data)
        made = edit_cover_by_hand(self.GetTopLevelParent(), source, edit)
        if made is not None:
            self.SetEdit(source, made[1], made[0])

    def ChooseFile(self, path):
        try:
            with open(path, 'rb') as file:
                data = file.read()
        except OSError as error:
            self.SetNote(error.strerror or 'Not read')
            return
        self.SetChosen(data)

    def OnClick(self, event):
        shown = self.GetShown()
        if shown is not None:
            wx.CallAfter(self.EditByHand, shown)
        else:
            self.ChooseImage()

    def ChooseImage(self):
        dialog = wx.FileDialog(self.GetTopLevelParent(), 'Choose a cover image',
                               wildcard=self.WILDCARD, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            self.ChooseFile(dialog.GetPath())
        dialog.Destroy()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        ui = macroboxstyle.current().UI
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        gc = wx.GraphicsContext.Create(dc)
        edge = ui.ACCENT if self.chosen is not None else ui.WARN if self.remove else ui.FIELD_EDGE
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(edge)).Width(1)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.FIELD_BG))))
        gc.DrawRoundedRectangle(0, 0, w - 1, h - 1, uikit.RADIUS)
        if self.bitmap is not None:
            bw, bh = self.bitmap.GetSize()
            gc.DrawBitmap(self.bitmap, (w - bw) // 2, (h - bh) // 2, bw, bh)
            # as every cover; its own edge (NEW, REMOVE) drawn again over it
            draw_cover_edge(gc, 0, 0, w - 1, h - 1, self.hover,
                            self.GetParent().GetBackgroundColour())
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(edge)).Width(1)))
            gc.DrawRoundedRectangle(0, 0, w - 1, h - 1, uikit.RADIUS)
        if self.chosen is not None or self.remove:
            # NEW or REMOVE in a chip at the top left, not by colour alone
            chip, face, ink = ('NEW', ui.ACCENT, uikit.colour(ui.ACCENT_FG)) \
                if self.chosen is not None else ('REMOVE', ui.WARN, uikit.colour(ui.WARN_FG))
            uikit.set_font(gc, uikit.get_font(uikit.MICRO, bold=True), ink)
            tw, th = gc.GetTextExtent(chip)[:2]
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(face))))
            gc.DrawRoundedRectangle(6, 6, tw + 10, th + 4, uikit.RADIUS)
            gc.DrawText(chip, 11, 8)
        hint = '' if self.bitmap else 'Saved without one' if self.remove else 'Click or drop an image'
        lines = [v for v in (self.note, hint) if v]
        if lines:
            # in a band across its bottom over a cover, on its middle without one
            uikit.set_font(gc, uikit.get_font(uikit.LABEL), uikit.colour(ui.BAR_TEXT_DIM))
            heights = [gc.GetTextExtent(v)[1] for v in lines]
            total = sum(heights) + 4 * (len(lines) - 1)
            y = (h - total) / 2.0
            if self.bitmap is not None:
                y = h - total - 10
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(0, 0, 0, 170))))
                gc.DrawRectangle(1, y - 6, w - 2, total + 12)
                uikit.set_font(gc, uikit.get_font(uikit.LABEL), wx.WHITE)
            for line, lh in zip(lines, heights):
                gc.DrawText(line, (w - gc.GetTextExtent(line)[0]) / 2.0, y)
                y += lh + 4


class CoverEditCanvas(wx.Window):

    '''the picture and its crop box'''

    HANDLE = 9
    # least side, view picture px
    LEAST = 12

    def __init__(self, parent, square, changed):
        wx.Window.__init__(self, parent, style=wx.BORDER_NONE | wx.WANTS_CHARS)
        self.image = None
        self.size = (1, 1)
        self.box = [0.0, 0.0, 1.0, 1.0]
        self.square = square
        self.changed = changed
        self.grid = True
        self.bitmap = None
        self.drag = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKey)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda e: self.OnUp(None))

    def SetPicture(self, image, box=None):
        # a new view picture (wx.Image); box (its px) when its shape changed
        self.image = image
        self.size = (image.GetWidth(), image.GetHeight())
        if box is not None:
            self.box = [float(v) for v in box]
        self.bitmap = None
        self.Refresh()

    def GetShares(self):
        pw, ph = self.size
        left, top, right, bottom = self.box
        return (left / pw, top / ph, right / pw, bottom / ph)

    def GetFit(self):
        # (scale, left, top) of the picture in the window
        w, h = self.GetClientSize()
        pw, ph = self.size
        scale = max(min((w - 2.0) / pw, (h - 2.0) / ph), 1e-6)
        return scale, (w - pw * scale) / 2.0, (h - ph * scale) / 2.0

    def ToPicture(self, x, y):
        scale, ox, oy = self.GetFit()
        pw, ph = self.size
        return (min(max((x - ox) / scale, 0.0), pw), min(max((y - oy) / scale, 0.0), ph))

    def GetScreenBox(self):
        scale, ox, oy = self.GetFit()
        left, top, right, bottom = self.box
        return (ox + left * scale, oy + top * scale, ox + right * scale, oy + bottom * scale)

    def GetCorners(self):
        # top left, top right, bottom right, bottom left
        left, top, right, bottom = self.GetScreenBox()
        return ((left, top), (right, top), (right, bottom), (left, bottom))

    def HitTest(self, x, y):
        for i, (cx, cy) in enumerate(self.GetCorners()):
            if abs(x - cx) <= self.HANDLE and abs(y - cy) <= self.HANDLE:
                return ('corner', i)
        left, top, right, bottom = self.GetScreenBox()
        if left <= x <= right and top <= y <= bottom:
            return ('move', None)
        return ('new', None)

    def SetBox(self, box):
        self.box = [float(v) for v in box]
        self.Refresh()
        self.changed()

    def SetSquare(self, square):
        self.square = square
        if square:
            # the shorter side kept, on the same middle
            left, top, right, bottom = self.box
            side = min(right - left, bottom - top)
            self.SetBox(self.Clamp(((left + right - side) / 2.0, (top + bottom - side) / 2.0,
                                    (left + right + side) / 2.0, (top + bottom + side) / 2.0)))

    def SetGrid(self, grid):
        self.grid = grid
        self.Refresh()

    def Clamp(self, box):
        # moved inside the picture, its size kept
        pw, ph = self.size
        left, top, right, bottom = box
        bw, bh = min(right - left, pw), min(bottom - top, ph)
        left = min(max(left, 0.0), pw - bw)
        top = min(max(top, 0.0), ph - bh)
        return (left, top, left + bw, top + bh)

    def SizeFrom(self, anchor, point):
        # the box from a fixed corner to the pointer, square when asked
        pw, ph = self.size
        ax, ay = anchor
        px, py = point
        sx = 1 if px >= ax else -1
        sy = 1 if py >= ay else -1
        roomx = pw - ax if sx > 0 else ax
        roomy = ph - ay if sy > 0 else ay
        w = min(max(abs(px - ax), self.LEAST), roomx)
        h = min(max(abs(py - ay), self.LEAST), roomy)
        if self.square:
            w = h = min(max(w, h), roomx, roomy)
        x2, y2 = ax + sx * w, ay + sy * h
        return (min(ax, x2), min(ay, y2), max(ax, x2), max(ay, y2))

    def OnDown(self, event):
        self.SetFocus()
        kind, corner = self.HitTest(*event.GetPosition())
        point = self.ToPicture(*event.GetPosition())
        left, top, right, bottom = self.box
        if kind == 'corner':
            # the opposite corner stays
            anchor = ((right, bottom), (left, bottom), (left, top), (right, top))[corner]
            self.drag = ('size', anchor)
        elif kind == 'move':
            self.drag = ('move', (point[0] - left, point[1] - top))
        else:
            self.drag = ('size', point)
        self.CaptureMouse()

    def OnUp(self, event):
        self.drag = None
        if self.HasCapture():
            self.ReleaseMouse()

    def OnMotion(self, event):
        x, y = event.GetPosition()
        if self.drag is None:
            kind, corner = self.HitTest(x, y)
            cursor = wx.CURSOR_CROSS
            if kind == 'corner':
                cursor = wx.CURSOR_SIZENWSE if corner in (0, 2) else wx.CURSOR_SIZENESW
            elif kind == 'move':
                cursor = wx.CURSOR_SIZING
            self.SetCursor(wx.Cursor(cursor))
            return
        point = self.ToPicture(x, y)
        kind, value = self.drag
        if kind == 'move':
            left, top, right, bottom = self.box
            nx, ny = point[0] - value[0], point[1] - value[1]
            self.SetBox(self.Clamp((nx, ny, nx + right - left, ny + bottom - top)))
        else:
            self.SetBox(self.SizeFrom(value, point))

    def Grow(self, factor):
        # sized on its middle, inside the picture
        pw, ph = self.size
        left, top, right, bottom = self.box
        bw, bh = right - left, bottom - top
        most = min(pw / bw, ph / bh)
        least = max(self.LEAST / bw, self.LEAST / bh)
        factor = min(max(factor, least), most)
        bw, bh = bw * factor, bh * factor
        mx, my = (left + right) / 2.0, (top + bottom) / 2.0
        self.SetBox(self.Clamp((mx - bw / 2.0, my - bh / 2.0, mx + bw / 2.0, my + bh / 2.0)))

    def OnWheel(self, event):
        self.Grow(1.05 ** (event.GetWheelRotation() / float(event.GetWheelDelta() or 120)))

    def OnKey(self, event):
        step = 10 if event.ShiftDown() else 1
        moves = {wx.WXK_LEFT: (-step, 0), wx.WXK_RIGHT: (step, 0),
                 wx.WXK_UP: (0, -step), wx.WXK_DOWN: (0, step)}
        key = event.GetKeyCode()
        if key in moves:
            dx, dy = moves[key]
            left, top, right, bottom = self.box
            self.SetBox(self.Clamp((left + dx, top + dy, right + dx, bottom + dy)))
        elif key in (ord('+'), ord('='), wx.WXK_NUMPAD_ADD):
            self.Grow(1.05)
        elif key in (ord('-'), wx.WXK_NUMPAD_SUBTRACT):
            self.Grow(1 / 1.05)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.GetParent().OnApply(None)
        elif key == ord('G') and event.HasAnyModifiers() is False:
            self.GetParent().OnGrid(not self.grid)
        else:
            event.Skip()

    def OnSize(self, event):
        self.bitmap = None
        self.Refresh()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        ui = macroboxstyle.current().UI
        dc.SetBackground(wx.Brush(uikit.colour(ui.FIELD_BG)))
        dc.Clear()
        if self.image is None:
            return
        scale, ox, oy = self.GetFit()
        pw, ph = self.size
        if self.bitmap is None:
            self.bitmap = wx.Bitmap(self.image.Scale(max(1, int(pw * scale)),
                                                     max(1, int(ph * scale)),
                                                     wx.IMAGE_QUALITY_HIGH))
        dc.DrawBitmap(self.bitmap, int(ox), int(oy))
        gc = wx.GraphicsContext.Create(dc)
        left, top, right, bottom = self.GetScreenBox()
        bx, by, bw, bh = ox, oy, self.bitmap.GetWidth(), self.bitmap.GetHeight()
        # the part cut away dimmed
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(0, 0, 0, 150))))
        gc.DrawRectangle(bx, by, bw, top - by)
        gc.DrawRectangle(bx, bottom, bw, by + bh - bottom)
        gc.DrawRectangle(bx, top, left - bx, bottom - top)
        gc.DrawRectangle(right, top, bx + bw - right, bottom - top)
        # thirds when the grid is on, then the edge in the accent
        if self.grid:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(255, 255, 255, 70)).Width(1)))
            for i in (1, 2):
                x = left + (right - left) * i / 3.0
                y = top + (bottom - top) * i / 3.0
                gc.StrokeLine(x, top, x, bottom)
                gc.StrokeLine(left, y, right, y)
        gc.SetBrush(wx.NullGraphicsBrush)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(ui.ACCENT)).Width(2)))
        gc.DrawRectangle(left, top, right - left, bottom - top)
        # the corners, white edged so they show on any picture
        size = self.HANDLE
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.WHITE).Width(1)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.ACCENT))))
        for cx, cy in self.GetCorners():
            gc.DrawRectangle(cx - size / 2.0, cy - size / 2.0, size, size)


class ValueSlider(wx.Window):

    '''a whole value from least to most, filled from zero; double-click back to zero'''

    HEIGHT = 22
    KNOB = 12
    # the knob's path in from each end, the knob kept inside
    INSET = KNOB // 2 + 1

    def __init__(self, parent, least, most, value, changed, width):
        wx.Window.__init__(self, parent, size=(width, self.HEIGHT),
                           style=wx.BORDER_NONE | wx.WANTS_CHARS)
        self.least, self.most, self.value = least, most, value
        self.changed = changed
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnDown)
        self.Bind(wx.EVT_LEFT_DCLICK, lambda e: self.SetValue(0, tell=True))
        self.Bind(wx.EVT_LEFT_UP, self.OnUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSEWHEEL, lambda e: self.SetValue(
            self.value + (1 if e.GetWheelRotation() > 0 else -1), tell=True))
        self.Bind(wx.EVT_KEY_DOWN, self.OnKey)
        self.Bind(wx.EVT_SET_FOCUS, lambda e: self.Refresh())
        self.Bind(wx.EVT_KILL_FOCUS, lambda e: self.Refresh())
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda e: None)

    def SetValue(self, value, tell=False):
        value = int(min(max(round(value), self.least), self.most))
        if value == self.value:
            return
        self.value = value
        self.Refresh()
        if tell:
            self.changed(value)

    def GetTrack(self):
        # (left, right) of the knob's path
        w = self.GetClientSize().width
        return self.INSET, w - self.INSET

    def ToX(self, value):
        left, right = self.GetTrack()
        return left + (right - left) * (value - self.least) / float(self.most - self.least)

    def FromX(self, x):
        left, right = self.GetTrack()
        return self.least + (x - left) / max(right - left, 1.0) * (self.most - self.least)

    def OnDown(self, event):
        self.SetFocus()
        self.CaptureMouse()
        self.SetValue(self.FromX(event.GetX()), tell=True)

    def OnMotion(self, event):
        if self.HasCapture() and event.LeftIsDown():
            self.SetValue(self.FromX(event.GetX()), tell=True)

    def OnUp(self, event):
        if self.HasCapture():
            self.ReleaseMouse()

    def OnKey(self, event):
        step = 10 if event.ShiftDown() else 1
        key = event.GetKeyCode()
        if key in (wx.WXK_LEFT, wx.WXK_DOWN):
            self.SetValue(self.value - step, tell=True)
        elif key in (wx.WXK_RIGHT, wx.WXK_UP):
            self.SetValue(self.value + step, tell=True)
        elif key == wx.WXK_HOME:
            self.SetValue(0, tell=True)
        else:
            event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        ui = macroboxstyle.current().UI
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        h = self.GetClientSize().height
        left, right = self.GetTrack()
        cy = h / 2.0
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.FIELD_EDGE))))
        gc.DrawRoundedRectangle(left, cy - 2, right - left, 4, 2)
        zero, x = self.ToX(0), self.ToX(self.value)
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.ACCENT))))
        gc.DrawRectangle(min(zero, x), cy - 2, abs(x - zero), 4)
        # the zero mark, the knob ringed while focused
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.BAR_TEXT_DIM))))
        gc.DrawRectangle(zero - 0.5, cy - 5, 1, 10)
        ring = ui.ACCENT if self.HasFocus() else ui.FIELD_EDGE
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(ring)).Width(1.5)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.TEXT))))
        gc.DrawEllipse(x - self.KNOB / 2.0, cy - self.KNOB / 2.0, self.KNOB, self.KNOB)


class CoverEditBox(DialogBox):

    '''the cover turned, leveled, cut and toned by hand'''

    VIEW = 480
    SIDE = 250
    # the view picture's longer side
    WORK = 720
    # (key, name, least, most, its auto's key): straighten in tenths of a degree
    ROWS = (('angle', 'Straighten', -int(listimages.STRAIGHTEN_MOST * 10),
             int(listimages.STRAIGHTEN_MOST * 10), 'auto_angle'),
            ('brightness', 'Brightness', -listimages.SLIDER_MOST, listimages.SLIDER_MOST,
             'auto_brightness'),
            ('contrast', 'Contrast', -listimages.SLIDER_MOST, listimages.SLIDER_MOST,
             'auto_contrast'),
            ('saturation', 'Color', -listimages.SLIDER_MOST, listimages.SLIDER_MOST,
             'auto_color'))
    FIELD = 50
    FIELD_TIPS = dict(angle='Degrees, clockwise; Up and Down by 0.1 (Shift: 1)',
                      brightness='Up and Down by 1 (Shift: 10)',
                      contrast='Up and Down by 1 (Shift: 10)',
                      saturation='Up and Down by 1 (Shift: 10)')
    TIPS = dict(angle=f'Turn it level; Auto finds a tilt up to {listimages.TILT_MOST:g} degrees',
                brightness='Auto lifts a dark picture or lowers a bright one',
                contrast='Auto stretches the darkest and lightest to the ends',
                saturation='The slider sets how strong the colors are; Auto balances them')
    # (changed, unchanged) words for each Auto
    NOTES = dict(brightness=('adjusted', 'already even'), contrast=('stretched', 'already full'),
                 saturation=('balanced', 'already neutral'))

    def __init__(self, parent, picture, edit, square):
        DialogBox.__init__(self, parent)
        self.SetTitle('Edit Cover')
        self.picture = picture
        self.full_size = picture.size
        self.work = picture.copy()
        self.work.thumbnail((self.WORK, self.WORK))
        # found tilts by quarter turns
        self.tilts = dict()
        self.edit = dict(edit, square=square)
        if self.edit['tilt'] is None:
            self.edit['tilt'] = self.FindTilt() if self.edit['auto_angle'] else 0.0
        self.picked = None
        self.rendering = None
        self.shape = None
        self.SetClientSize((DIALOG_PAD * 3 + self.VIEW + self.SIDE,
                            DIALOG_PAD * 2 + self.VIEW + self.GetFooterHeight()))
        self.Canvas = CoverEditCanvas(self, square, self.OnBoxChanged)
        self.Canvas.SetRect((DIALOG_PAD, DIALOG_PAD, self.VIEW, self.VIEW))
        self.Canvas.SetGrid(GetPreference('cover_edit_grid') is not False)
        self.Canvas.SetToolTip(wx.ToolTip(
            'Drag inside to move, a corner to size, outside for a new box.\n'
            'Wheel or +/- sizes it, arrows move it (Shift: by 10), G shows or hides the grid.'))
        self.MakeSide(square)
        self.ResetButton = Button(self, label='Reset')
        self.ResetButton.Bind(wx.EVT_BUTTON, self.OnReset)
        self.ApplyButton = Button(self, label='Apply', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CloseButton = Button(self, label='Cancel')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.PlaceButtons(right=(self.ApplyButton, self.CloseButton), left=(self.ResetButton,))
        self.Render()
        self.Canvas.SetFocus()

    def MakeHead(self, label, x, y):
        head = StaticText(self, label=label.upper(), pos=(x, y))
        head.SetFont(uikit.get_font(10))
        head.SetForegroundColour(macroboxstyle.current().UI.BAR_TEXT_DIM)
        return head.GetBestSize().height

    def MakeSide(self, square):
        x = DIALOG_PAD * 2 + self.VIEW
        width = self.SIDE
        y = DIALOG_PAD
        y += self.MakeHead('Rotate', x, y) + DIALOG_GAP
        half = (width - DIALOG_GAP) // 2
        for k, (label, step) in enumerate((('Rotate Left', -1), ('Rotate Right', 1))):
            button = Button(self, label=label, pos=(x + k * (half + DIALOG_GAP), y),
                            size=(half, DIALOG_BUTTON_HEIGHT))
            button.Bind(wx.EVT_BUTTON, lambda e, step=step: self.Turn(step))
        y += DIALOG_BUTTON_HEIGHT + DIALOG_PAD
        y += self.MakeHead('Adjust', x, y) + DIALOG_GAP
        # between a slider and the next row's name
        row_gap = DIALOG_GAP + 4
        self.sliders = dict()
        self.values = dict()
        self.autos = dict()
        self.notes = dict()
        for key, name, least, most, auto in self.ROWS:
            text = StaticText(self, label=name, pos=(x, y))
            text.SetToolTip(self.TIPS[key])
            # what its Auto did, by the name
            self.notes[key] = StaticText(self, label='', pos=(
                x + text.GetBestSize().width + DIALOG_GAP, y))
            self.notes[key].SetForegroundColour(macroboxstyle.current().UI.BAR_TEXT_DIM)
            made = set(self.GetChildren())
            check, used = make_check(self, 'Auto', (0, y), self.edit[auto],
                                     lambda value, auto=auto: self.SetAuto(auto, value))
            # the Auto check from the value field's left, a column with it
            for window in set(self.GetChildren()) - made:
                px, py = window.GetPosition()
                window.SetPosition((px + x + width - max(self.FIELD, used), py))
            self.autos[auto] = check
            y += DIALOG_ROW
            value = int(round(self.edit[key] * 10)) if key == 'angle' else self.edit[key]
            # its path flush with the names, GAP short of the field; the knob past it
            slider = ValueSlider(self, least, most, value,
                                 lambda value, key=key: self.SetSlider(key, value),
                                 width - self.FIELD - DIALOG_GAP + ValueSlider.INSET * 2)
            slider.SetPosition((x - ValueSlider.INSET, y))
            slider.SetToolTip(f'{self.TIPS[key]}\nDouble-click: back to 0')
            self.sliders[key] = slider
            field = TextCtrl(self, pos=(x + width - self.FIELD, y),
                             size=(self.FIELD, ValueSlider.HEIGHT),
                             style=wx.TE_RIGHT | wx.TE_PROCESS_ENTER)
            field.SetToolTip(self.FIELD_TIPS[key])
            field.Bind(wx.EVT_TEXT_ENTER, lambda e, key=key: self.TypeValue(key))
            field.Bind(wx.EVT_KILL_FOCUS, lambda e, key=key: (self.TypeValue(key), e.Skip()))
            field.Bind(wx.EVT_KEY_DOWN, lambda e, key=key: self.OnValueKey(key, e))
            self.values[key] = field
            y += ValueSlider.HEIGHT + row_gap
        line = text.GetBestSize().height
        # PAD under every part, then its head
        y += DIALOG_PAD - row_gap
        y += self.MakeHead('Crop', x, y) + DIALOG_GAP
        self.Square, used = make_check(self, 'Square', (x, y), square, self.OnSquare)
        self.Info = StaticText(self, label='', pos=(x + used + DIALOG_PAD, y))
        self.Info.SetForegroundColour(macroboxstyle.current().UI.BAR_TEXT_DIM)
        y += line + DIALOG_PAD
        # how the picture is shown here, nothing written
        y += self.MakeHead('View', x, y) + DIALOG_GAP
        self.Grid, _ = make_check(self, 'Grid', (x, y), self.Canvas.grid, self.OnGrid)
        self.ShowValues()

    def ShowValues(self):
        for key in self.sliders:
            value = self.sliders[key].value
            text = f'{value / 10.0:.1f}' if key == 'angle' else f'{value}'
            if self.values[key].GetValue() != text:
                self.values[key].ChangeValue(text)

    def TypeValue(self, key):
        # kept in the slider's range; not a number: the value back
        text = self.values[key].GetValue().replace('°', '').replace('+', '').strip()
        try:
            value = float(text)
        except ValueError:
            self.ShowValues()
            return
        self.sliders[key].SetValue(value * 10 if key == 'angle' else value, tell=True)
        self.ShowValues()

    def OnValueKey(self, key, event):
        steps = {wx.WXK_UP: 1, wx.WXK_DOWN: -1, wx.WXK_NUMPAD_UP: 1, wx.WXK_NUMPAD_DOWN: -1}
        code = event.GetKeyCode()
        if code not in steps:
            event.Skip()
            return
        self.TypeValue(key)
        slider = self.sliders[key]
        slider.SetValue(slider.value + steps[code] * (10 if event.ShiftDown() else 1), tell=True)
        self.ShowValues()

    def ShowNotes(self, measure):
        notes = listimages.get_tone_notes(
            measure, self.edit['auto_contrast'], self.edit['auto_brightness'],
            self.edit['auto_color'])
        words = dict(angle='')
        if self.edit['auto_angle']:
            tilt = -self.edit['tilt']
            words['angle'] = f'found {tilt:+.1f}°' if tilt != 0 else 'already level'
        for key, name in (('brightness', 'brightness'), ('contrast', 'contrast'),
                          ('saturation', 'color')):
            words[key] = '' if name not in notes else self.NOTES[key][0 if notes[name] else 1]
        for key, word in words.items():
            if self.notes[key].GetLabel() != word:
                self.notes[key].SetLabel(word)
                self.notes[key].SetSize(self.notes[key].GetBestSize())

    def ShowSize(self):
        size = listimages.get_turned_size(self.full_size, self.edit)
        left, top, right, bottom = listimages.get_edit_box(self.edit, size)
        self.Info.SetLabel(f'{right - left} x {bottom - top} px')
        self.Info.SetSize(self.Info.GetBestSize())

    # changes

    def Turn(self, step):
        # the box turned with the picture
        left, top, right, bottom = self.GetBox()
        if step > 0:
            box = (1 - bottom, left, 1 - top, right)
        else:
            box = (top, 1 - right, bottom, 1 - left)
        self.edit['turns'] = (self.edit['turns'] + step) % 4
        self.edit['box'] = box
        if self.edit['auto_angle']:
            self.edit['tilt'] = self.FindTilt()
        self.Render()

    def GetBox(self):
        return listimages.WHOLE_BOX if self.edit['box'] is None else self.edit['box']

    def FindTilt(self):
        turns = self.edit['turns'] % 4
        if turns not in self.tilts:
            self.tilts[turns] = listimages.find_edit_tilt(self.work, turns)
        return self.tilts[turns]

    def SetAuto(self, auto, value):
        self.edit[auto] = value
        if auto == 'auto_angle' and value:
            self.edit['tilt'] = self.FindTilt()
        self.Render()

    def SetSlider(self, key, value):
        self.edit[key] = value / 10.0 if key == 'angle' else value
        self.ShowValues()
        self.Render()

    def OnBoxChanged(self):
        self.edit['box'] = self.Canvas.GetShares()
        self.ShowSize()
        # autos measured on the cut
        self.Render()

    def OnSquare(self, square):
        SetPreference('cover_crop_square', square)
        self.edit['square'] = square
        self.Canvas.SetSquare(square)
        self.Canvas.SetFocus()

    def OnGrid(self, grid):
        # kept for the next time; not part of the edit
        SetPreference('cover_edit_grid', grid)
        self.Grid.SetValue(grid)
        self.Canvas.SetGrid(grid)
        self.Canvas.SetFocus()

    def OnReset(self, event):
        square = self.Square.GetValue()
        self.edit = listimages.new_edit()
        self.edit['box'] = listimages.get_first_box(self.picture, square)
        self.edit['square'] = square
        for slider in self.sliders.values():
            slider.SetValue(0)
        for check in self.autos.values():
            check.SetValue(False)
        self.ShowValues()
        self.Render()
        self.Canvas.SetFocus()

    def Render(self):
        # soon, once for a run of changes
        if self.rendering is None:
            self.rendering = wx.CallLater(15, self.RenderNow)

    def RenderNow(self):
        self.rendering = None
        if not self:
            return
        turned = listimages.turn_picture(self.work, self.edit)
        box = listimages.get_box_pixels(self.edit['box'], turned.size)
        measure = turned.crop(box)
        toned = listimages.tone_picture(turned, self.edit, measure).convert('RGB')
        self.ShowNotes(measure)
        image = wx.Image(toned.width, toned.height, toned.tobytes())
        # the box placed again only when the picture's shape changed
        shape = (self.edit['turns'] % 4, listimages.get_edit_angle(self.edit))
        if shape != self.shape:
            self.shape = shape
            pw, ph = turned.size
            left, top, right, bottom = self.GetBox()
            self.Canvas.SetPicture(image, (left * pw, top * ph, right * pw, bottom * ph))
        else:
            self.Canvas.SetPicture(image)
        self.ShowSize()

    def OnApply(self, event):
        self.edit['box'] = self.Canvas.GetShares()
        self.picked = dict(self.edit)
        self.EndModal(wx.ID_OK)

    def OnClose(self, event):
        if self.rendering is not None:
            self.rendering.Stop()
            self.rendering = None
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)


def pick_cover_edit(parent, data, edit=None, autos=None):
    '''the edit made in CoverEditBox, None when let go'''
    picture = listimages.open_picture(data)
    if picture is None:
        return None
    square = GetPreference('cover_crop_square') is not False
    if edit is None:
        edit = listimages.new_edit(autos)
        edit['box'] = listimages.get_first_box(picture, square)
        # CoverEditBox finds it
        edit['tilt'] = None
    else:
        # a kept box as it was, square or not
        size = listimages.get_turned_size(picture.size, edit)
        left, top, right, bottom = listimages.get_box_pixels(edit['box'], size)
        square = square and abs((right - left) - (bottom - top)) <= 1
    dialog = CoverEditBox(parent, picture, edit, square)
    dialog.ShowModal()
    picked = dialog.picked
    dialog.Destroy()
    return picked


def edit_cover_by_hand(parent, data, edit=None):
    '''(edited picture, its edit), None when let go'''
    picked = pick_cover_edit(parent, data, edit)
    if picked is None:
        return None
    result = listimages.edit_cover(data, picked)
    return None if result is None else (result, picked)


class ItemEditPanel(DialogPanel):

    def __init__(self, parent, pos=(0, 0)):
        DialogPanel.__init__(self, parent)
        self.Show(False)
        self.parent = parent
        x, y = pos
        width, height = self.parent.GetClientSize()
        self.SetRect((x, y, width, self.GetContentHeight()))
        self.labels = ('Path', 'Filename', 'Duration', 'Size', 'Bitrate',
                       'Channel', 'Artist', 'Title', 'Album', 'Genre', 'Key', 'Tempo')
        self.disables = ('Duration', 'Type', 'Size', 'Bitrate', 'Channel', 'Path')
        # keep the file's modified date on save (KEEP), read once
        keep = GetPreference('item_editor_keep_modified')
        self.keep_modified = keep is not False

    # fields and footer in the dialogs' spacing (macroboxlib.DIALOG_PAD)
    PAD = DIALOG_PAD
    ROW = DIALOG_ROW
    ROW_GAP = DIALOG_GAP
    LABEL = 50
    LABEL_GAP = DIALOG_GAP
    # Modified shown, not a list column; KEEP across two columns
    ROWS = (('Path',), ('Filename',), ('Duration', 'Size', 'Bitrate', 'Channel'),
            ('Modified', None, 'KEEP', None),
            ('Artist',), ('Title',), ('Album',), ('Genre', None, 'Key', 'Tempo'))
    RIGHT = ('Duration', 'Size', 'Bitrate', 'Channel', 'Tempo')
    # the fields' width; the cover (CoverField) at their left, as tall as their rows
    GRID = 552

    @classmethod
    def GetCoverSize(cls):
        return len(cls.ROWS) * cls.ROW + (len(cls.ROWS) - 1) * cls.ROW_GAP

    @classmethod
    def GetContentHeight(cls):
        return cls.PAD * 2 + cls.GetCoverSize()

    @classmethod
    def GetContentWidth(cls):
        return cls.PAD * 3 + cls.GetCoverSize() + cls.GRID

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
                # read-only
                self.TextCtrls[i].SetReadOnly()
        path = self.parent.parent.parent.GetItemValueByColumnKey(item_idx, 'path')
        self.Cover.SetSong(path)
        self.SetModified(path)
        self.Refresh()

    def InitTextCtrls(self):
        width, height = self.GetClientSize()
        size = self.GetCoverSize()
        self.Cover = CoverField(self, (self.PAD, self.PAD), (size, size))
        start = self.PAD * 2 + size
        right = width - self.PAD
        column = (right - start - self.PAD * 3) / 4.0
        fields = dict()
        y = self.PAD
        for row in self.ROWS:
            for k, label in enumerate(row):
                if label is None:
                    continue
                x = int(round(start + k * (column + self.PAD)))
                left = x + self.LABEL + self.LABEL_GAP
                # the last of a row to the right edge; Genre across two
                last = k == len(row) - 1
                spans = 2 if k + 1 < len(row) and row[k + 1] is None else 1
                end = right if last else int(round(
                    start + (k + spans) * (column + self.PAD) - self.PAD))
                if label == 'KEEP':
                    self.KeepModified, _ = make_check(
                        self, 'Keep the modified date on save', (left, y + 3),
                        self.keep_modified, self.OnKeepModified)
                    continue
                style = wx.ALIGN_RIGHT if label in self.RIGHT else 0
                text = StaticText(self, label=label, pos=(x, y + 3),
                                  size=(self.LABEL, 20), style=wx.ALIGN_RIGHT)
                fields[label] = (text, TextCtrl(self, pos=(left, y),
                                                size=(end - left, self.ROW), style=style))
            y += self.ROW + self.ROW_GAP
        self.StaticTexts = [fields[v][0] for v in self.labels]
        self.TextCtrls = [fields[v][1] for v in self.labels]
        # editable fields mark changes as typed; their own menu
        for i, label in enumerate(self.labels):
            if label in self.disables:
                continue
            text = self.TextCtrls[i]
            text.Bind(wx.EVT_TEXT, lambda e: (self.parent.UpdateMarks(), e.Skip()))
            text.Bind(wx.EVT_CONTEXT_MENU, lambda e, i=i: self.parent.ShowFieldMenu(i))
        self.Modified = fields['Modified'][1]
        self.Modified.SetReadOnly()
        # the names dimmed, the values (and the fields) brighter
        for text, _ in fields.values():
            text.SetForegroundColour(macroboxstyle.current().UI.BAR_TEXT_DIM)
        # the editor's menu on its ground and names too; fields keep their own
        for window in [self] + [c for c in self.GetChildren() if isinstance(c, wx.StaticText)]:
            window.Bind(wx.EVT_RIGHT_UP, lambda e, window=window:
                        self.parent.ShowMenu(window))

    def OnKeepModified(self, value):
        self.keep_modified = value
        SetPreference('item_editor_keep_modified', value)

    def SetModified(self, path):
        try:
            stamp = os.stat(path).st_mtime
        except OSError:
            self.Modified.SetValue('')
            return
        self.Modified.SetValue(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp)))

    def OnClose(self, event):
        self.Destroy()


class ItemEditBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(600, 320))
        self.parent = parent
        self.SetTitle('Track Information Editor')
        self.selectedList = self.parent.parent.selectedList
        self.selectedItems = self.parent.parent.GetSelectedItems()
        self.total_items = len(self.selectedItems)
        self.selected_idx = 0
        # changes held till Save, let go by Cancel, close or Esc:
        # {item: dict(fields={name: value}, cover=('chosen'|'remove', ...))}
        self.pending = dict()
        self.lookups = dict()
        # the fields (ItemEditPanel), the footer under them
        self.SetClientSize((ItemEditPanel.GetContentWidth(),
                            ItemEditPanel.GetContentHeight() + self.GetFooterHeight()))
        self.SaveButton = Button(self, label='Save', primary=True)
        self.SaveButton.Bind(wx.EVT_BUTTON, self.OnSave)
        self.CancelButton = Button(self, label='Cancel')
        self.CancelButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.NextButton = Button(self, label='Next')
        self.NextButton.Bind(wx.EVT_BUTTON, self.OnNext)
        self.PrevButton = Button(self, label='Prev')
        self.PrevButton.Bind(wx.EVT_BUTTON, self.OnPrev)
        self.LookUpButton = Button(self, label='Look Up')
        self.LookUpButton.Bind(wx.EVT_BUTTON, self.OnLookUp)
        top = self.PlaceButtons(right=(self.PrevButton, self.NextButton, self.SaveButton,
                                       self.CancelButton),
                                left=(self.LookUpButton,))
        # page number PAD before Prev, on the buttons' middle
        label = f'{int(self.selected_idx + 1)} / {int(self.total_items)}'
        self.PageNumber = StaticText(self, label=label, pos=(
            self.PrevButton.GetPosition().x - DIALOG_PAD - 160, top + 5), size=(160, 20),
            style=wx.ALIGN_RIGHT)
        self.LookUpButton.SetToolTip(wx.ToolTip(
            'Find artist, title, album and genre on Discogs, Last.fm and AcoustID.'
            '\nThe keys are set in Preference > Web Services.'))
        self.ItemEditPanel = ItemEditPanel(self)
        self.SetPage()
        self.ItemEditPanel.Show(True)
        for window in (self, self.PageNumber):
            window.Bind(wx.EVT_RIGHT_UP, lambda e, window=window: self.ShowMenu(window))

    def ShowMenu(self, window):
        # the editor's menu where asked: the cover's items, Look Up
        menu = wx.Menu()
        self.ItemEditPanel.Cover.AppendMenu(menu)
        menu.AppendSeparator()
        look = menu.Append(wx.ID_ANY, 'Look Up...')
        look.Enable(self.LookUpButton.IsEnabled())
        menu.Bind(wx.EVT_MENU, self.OnLookUp, look)
        cover = menu.Append(wx.ID_ANY, 'Look Up Cover...')
        menu.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(self.OnLookUpCover), cover)
        uikit.mark_menu_checks(menu)
        window.PopupMenu(menu)
        menu.Destroy()

    def GetFieldText(self, label):
        return self.ItemEditPanel.TextCtrls[self.ItemEditPanel.labels.index(label)]

    def OnLookUp(self, event):
        keys = dict(zip(webinfo.PREFERENCE_KEYS, GetPreferences(webinfo.PREFERENCE_KEYS)))
        if not any(keys.values()):
            show_notice(self, 'Look Up', 'Set a key in Preference > Web Services first.')
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

    def OnLookUpCover(self):
        # the cover chosen there put in the cover field, written with the page
        itemIdx = self.selectedItems[self.selected_idx]
        value = self.parent.parent.GetItemValueByColumnKey
        path = value(itemIdx, 'path')
        track = dict(path=path, mdx=value(itemIdx, 'mdx'),
                     artist=self.GetFieldText('Artist').GetValue().strip(),
                     title=self.GetFieldText('Title').GetValue().strip(),
                     label=os.path.basename(path))
        selected_idx = self.selected_idx

        def use(results):
            if self and selected_idx == self.selected_idx and len(results) > 0:
                self.ItemEditPanel.Cover.SetChosen(results[0][2])
        look_up_cover_for(self.parent.parent, [track], use=use, parent=self)

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
        # rows kept: each field's values to choose from
        self.lookups[itemIdx] = candidates
        self.UpdateMarks()
        dialog = WebInfoBox(self, candidates, errors, length, use=self.UseLookUpValue)
        answer = dialog.ShowModal()
        SetPreference('lookup_size', tuple(dialog.GetClientSize()))
        if answer == wx.ID_OK and dialog.selected is not None:
            chosen = candidates[dialog.selected]
            # only the ticked fields
            for label in self.LOOKUP_FIELDS:
                if dialog.apply[label.lower()] and chosen[label.lower()]:
                    self.GetFieldText(label).SetValue(chosen[label.lower()])
            if dialog.apply['cover'] and chosen['image']:
                self.UseLookUpValue('Cover', dialog.GetCoverValue(chosen['image']))
        dialog.Destroy()

    # the fields Look Up fills (its rows' keys, in lower case)
    LOOKUP_FIELDS = ('Artist', 'Title', 'Album', 'Genre')

    def UseLookUpValue(self, label, value):
        # one value of a Look Up row in its field, held as a change
        if label != 'Cover':
            self.GetFieldText(label).SetValue(value)
            return
        if isinstance(value, tuple):
            # edited there: the picture, its edit and what it made
            self.ItemEditPanel.Cover.SetEdit(*value)
            return
        self.ItemEditPanel.Cover.SetNote('Loading...')
        thread = threading.Thread(target=self.FetchCoverThread,
                                  args=(self.selected_idx, value))
        thread.daemon = True
        thread.start()

    def FetchCoverThread(self, selected_idx, url):
        try:
            data, note = webinfo.fetch_image(url), ''
        except Exception as error:
            data, note = None, str(error)
        wx.CallAfter(self.OnCoverFetched, selected_idx, data, note)

    def OnCoverFetched(self, selected_idx, data, note):
        if not self or selected_idx != self.selected_idx:
            return
        if data:
            self.ItemEditPanel.Cover.SetChosen(data)
        else:
            self.ItemEditPanel.Cover.SetNote(note or 'No cover')

    def KeepModified(self, itemIdx, before):
        # restore the modified and accessed dates after writing (KEEP)
        if before is None or not self.ItemEditPanel.keep_modified:
            return
        path = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
        try:
            if os.stat(path).st_mtime_ns != before.st_mtime_ns:
                with mfeats.tags_written(path):
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        except OSError as error:
            show_notice(self, 'Modified', f'The modified date was not kept.\n{error}')

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
                newValue = f'{0.1 * round(newValue * 10):05.1f}'
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

    # held

    def StashPage(self):
        # the page's changes (its fields and cover against the file's) held for Save
        panel = self.ItemEditPanel
        itemIdx = self.selectedItems[self.selected_idx]
        fields = dict()
        for i, label in enumerate(panel.labels):
            if label in panel.disables:
                continue
            value = panel.TextCtrls[i].GetValue()
            if value != panel.restore_value[i]:
                fields[label] = value
        cover = panel.Cover
        change = ('remove', None) if cover.remove else\
            ('chosen', cover.chosen) if cover.chosen is not None else None
        if fields or change is not None:
            self.pending[itemIdx] = dict(fields=fields, cover=change)
        else:
            self.pending.pop(itemIdx, None)

    def UpdateMarks(self):
        # changed field: accent name and a left bar; a mark when Look Up has values
        panel = getattr(self, 'ItemEditPanel', None)
        # not while a page loads: its fields are set one at a time
        if panel is None or getattr(self, 'loading', False):
            return
        ui = macroboxstyle.current().UI
        for i, label in enumerate(panel.labels):
            if label in panel.disables:
                continue
            text = panel.TextCtrls[i]
            changed = text.GetValue() != panel.restore_value[i]
            text.frame.SetChanged(changed)
            name = panel.StaticTexts[i]
            colour = wx.Colour(ui.ACCENT if changed else ui.BAR_TEXT_DIM)
            if name.GetForegroundColour() != colour:
                name.SetForegroundColour(colour)
                name.Refresh()
            text.frame.SetMark((lambda i=i: self.ShowFieldMenu(i)) if self.GetPicks(label)
                               else None)
        self.StashPage()
        label = f'{int(self.selected_idx + 1)} / {int(self.total_items)}'
        if self.total_items > 1 and self.pending:
            label = f'{len(self.pending)} changed   {label}'
        if self.PageNumber.GetLabelText() != label:
            size = self.PageNumber.GetSize()
            self.PageNumber.SetLabelText(label)
            self.PageNumber.SetInitialSize(size)

    def GetPicks(self, label):
        # [(value, its sources)] Look Up found for this field of the page's track
        if label not in self.LOOKUP_FIELDS:
            return []
        rows = self.lookups.get(self.selectedItems[self.selected_idx]) or []
        picks = dict()
        for row in rows:
            value = (row.get(label.lower()) or '').strip()
            if value:
                sources = picks.setdefault(value, [])
                if row['source'] not in sources:
                    sources.append(row['source'])
        return list(picks.items())

    def ShowFieldMenu(self, i):
        # field menu: Look Up values, Revert, Apply to All, edit items
        panel = self.ItemEditPanel
        label, text = panel.labels[i], panel.TextCtrls[i]
        menu = wx.Menu()

        def add(name, action, enable=True):
            item = menu.Append(wx.ID_ANY, name)
            item.Enable(enable)
            menu.Bind(wx.EVT_MENU, lambda e: action(), item)

        picks = self.GetPicks(label)
        for value, sources in picks:
            shown = value if len(value) <= 60 else value[:57] + '...'
            add(f'{shown.replace("&", "&&")}\t{", ".join(sources)}',
                lambda value=value: text.SetValue(value))
        if picks:
            menu.AppendSeparator()
        original = panel.restore_value[i]
        add('Revert', lambda: text.SetValue(original), text.GetValue() != original)
        if self.total_items > 1 and label != 'Filename':
            add(f'Apply to All {int(self.total_items)} Tracks',
                lambda: self.ApplyToAll(label, text.GetValue()))
        menu.AppendSeparator()
        add('Cut', text.Cut, text.CanCut())
        add('Copy', text.Copy, text.CanCopy())
        add('Paste', text.Paste, text.CanPaste())
        add('Select All', text.SelectAll)
        uikit.mark_menu_checks(menu)
        text.frame.PopupMenu(menu)
        menu.Destroy()

    def ApplyToAll(self, label, value):
        # this value for every track, held as each page's change
        listbox = self.parent.parent
        current = self.selectedItems[self.selected_idx]
        for itemIdx in self.selectedItems:
            if itemIdx == current:
                continue
            change = self.pending.setdefault(itemIdx, dict(fields=dict(), cover=None))
            own = listbox.GetItemValueByColumnKey(itemIdx, label.lower())
            own = str(own) if isinstance(own, (int, float)) else own
            if value == own:
                change['fields'].pop(label, None)
            else:
                change['fields'][label] = value
            if not change['fields'] and change['cover'] is None:
                self.pending.pop(itemIdx, None)
        self.UpdateMarks()

    # saved

    def OnSave(self, event):
        # every track's changes written, then closed
        self.StashPage()
        for itemIdx in [v for v in self.selectedItems if v in self.pending]:
            self.WriteItem(itemIdx, self.pending.pop(itemIdx))
        self.parent.parent.List.DirectDraw()
        self.EndModal(wx.ID_OK)

    def WriteItem(self, itemIdx, change):
        # rename first, then tags and cover; the playing song paused meanwhile
        listbox = self.parent.parent
        playbox = listbox.parent.PlayBox
        path = listbox.GetItemValueByColumnKey(itemIdx, 'path')
        try:
            before = os.stat(path)
        except OSError:
            before = None
        playing = playbox.IsPlaying() and path == playbox.GetPlayingItemInfo('path')
        if playing:
            playbox.OnPause()
        renamed = None
        for label in self.ItemEditPanel.labels:
            if label not in change['fields']:
                continue
            value = change['fields'][label]
            columnIdx = listbox.GetColumnKeyToIdx(label.lower())
            if label == 'Filename':
                name = listbox.LimitFileName(value)
                base = os.path.sep.join(path.split(os.path.sep)[:-1])
                newPath = os.path.sep.join([base, name]) + os.path.splitext(path)[-1]
                if newPath != path and listbox.RenameFileByItemIdx(itemIdx, newPath) is not False:
                    renamed = newPath
            elif listbox.IsID3TAGColumnByColumnIdx(columnIdx):
                if label == 'Tempo':
                    try:
                        value = f'{0.1 * round(float(value) * 10):05.1f}'
                    except Exception:
                        value = ''
                listbox.RenameID3TAGByColumnItemIdx(columnIdx, itemIdx, value)
        if change['cover'] is not None:
            self.WriteCover(itemIdx, *change['cover'])
        self.KeepModified(itemIdx, before)
        if playing:
            if renamed:
                playbox.cue.path = renamed
                playbox.cue.mdx = playbox.GetMDX(renamed)
                playbox.cue.item = MakeMusicFileItem(renamed, 0, ListBoxColumn())
            playbox.OnResume()

    def WriteCover(self, itemIdx, kind, data):
        # write or remove the cover in the tags, then reload list and player
        listbox = self.parent.parent
        path = listbox.GetItemValueByColumnKey(itemIdx, 'path')
        try:
            if kind == 'remove':
                listimages.remove_cover(path)
            else:
                listimages.write_cover(path, data)
        except Exception as error:
            show_notice(self, 'Cover', f'The cover was not saved.\n{error}')
            return
        images = getattr(self.parent, 'images', None)
        if images is not None:
            images.Forget(listbox.GetItemValueByColumnKey(itemIdx, 'mdx'), 'cover')
        playbox = listbox.parent.PlayBox
        if playbox.cue.path == path:
            playbox.Apic.HandleApicChange(forced=True)

    # paged

    def OnPrev(self, event):
        if self.selected_idx > 0:
            self.StashPage()
            self.selected_idx -= 1
            self.SetPage()

    def OnNext(self, event):
        if self.selected_idx < self.total_items - 1:
            self.StashPage()
            self.selected_idx += 1
            self.SetPage()

    def SetPage(self):
        # the track's fields as its file has them, its held changes over them
        self.Freeze()
        self.loading = True
        self.AutoSeButtonState()
        itemIdx = self.selectedItems[self.selected_idx]
        panel = self.ItemEditPanel
        panel.SetPage(itemIdx)
        change = self.pending.get(itemIdx)
        if change is not None:
            for label, value in change['fields'].items():
                panel.TextCtrls[panel.labels.index(label)].SetValue(value)
            if change['cover'] is not None:
                kind, data = change['cover']
                if kind == 'remove':
                    panel.Cover.SetRemove()
                else:
                    panel.Cover.SetChosen(data)
        self.loading = False
        self.UpdateMarks()
        self.Thaw()

    def OnClose(self, event):
        # Cancel, close or Esc: changes let go, asked first if any
        self.StashPage()
        if self.pending and not confirm_discard_edits(self, len(self.pending)):
            return
        self.pending.clear()
        self.EndModal(wx.ID_CANCEL)


class DiscardEditsBox(ConfirmDialogBox):

    # discard the editor's changes, or go back to them
    def __init__(self, parent, count, answer):
        ConfirmDialogBox.__init__(self, parent)
        self.answer = answer
        self.SetTitle('Discard Changes')
        self.ApplyButton.SetLabelText('Discard')
        self.CloseButton.SetLabelText('Keep Editing')
        self.Message.Hide()
        tracks = 'this track' if count == 1 else f'{int(count)} tracks'
        self.Text = wx.StaticText(self, label=f'Discard the changes to {tracks}?\nNothing has been '
                                  'written to the files.',
                                  style=wx.ALIGN_CENTER_HORIZONTAL | wx.ST_NO_AUTORESIZE)
        self.Text.SetForegroundColour(macroboxstyle.current().UI.TEXT)
        self.Text.SetFont(uikit.get_font(uikit.BODY))
        self.SetClientSize((340, DIALOG_PAD * 2 + 40 + self.GetFooterHeight()))
        self.OnSize(None)

    def OnSize(self, event):
        ConfirmDialogBox.OnSize(self, event)
        if getattr(self, 'Text', None) is not None:
            width, height = self.GetClientSize()
            self.Text.SetRect((DIALOG_PAD, DIALOG_PAD, width - DIALOG_PAD * 2, 40))

    def OnApply(self, event):
        self.answer.append(True)
        self.OnClose(event)


def confirm_discard_edits(parent, count):
    # True when the editor's changes are to be let go (asked over it)
    answer = []
    box = DiscardEditsBox(parent, count, answer)
    x, y, w, h = parent.GetRect()
    bw, bh = box.GetSize()
    box.SetPosition((x + (w - bw) // 2, y + (h - bh) // 2))
    box.ShowModal()
    return bool(answer)


class NoticeBox(ConfirmDialogBox):

    # a short message with OK, in the dialogs' look
    def __init__(self, parent, title, message):
        ConfirmDialogBox.__init__(self, parent)
        self.SetTitle(title)
        # OK at the footer's right end, in the accent
        self.ApplyButton.Hide()
        self.CloseButton.SetLabelText('OK')
        self.CloseButton.primary = True
        self.Message.Hide()
        self.Text = wx.StaticText(self, label=message,
                                  style=wx.ALIGN_CENTER_HORIZONTAL | wx.ST_NO_AUTORESIZE)
        self.Text.SetForegroundColour(macroboxstyle.current().UI.TEXT)
        self.Text.SetFont(uikit.get_font(uikit.BODY))
        self.Text.Wrap(340 - DIALOG_PAD * 2)
        self.text_height = max(40, self.Text.GetBestSize().height)
        self.SetClientSize((340, DIALOG_PAD * 2 + self.text_height + self.GetFooterHeight()))
        self.OnSize(None)
        self.CloseButton.SetFocus()

    def OnSize(self, event):
        ConfirmDialogBox.OnSize(self, event)
        if getattr(self, 'Text', None) is not None:
            width, height = self.GetClientSize()
            self.Text.SetRect((DIALOG_PAD, DIALOG_PAD, width - DIALOG_PAD * 2, self.text_height))


def show_notice(parent, title, message):
    # asked over parent, centred, as confirm_discard_edits
    box = NoticeBox(parent, title, message)
    x, y, w, h = parent.GetRect()
    bw, bh = box.GetSize()
    box.SetPosition((x + (w - bw) // 2, y + (h - bh) // 2))
    box.ShowModal()


def show_library_results(mainpanel, title, songs):
    # the found songs in their tab, the tab chosen and drawn as a new one is
    library.show_results(mainpanel.ListBox, title, songs)
    mainpanel.ListBox.Header.SetAutoColumnWidth()
    mainpanel.ListBox.reInitBuffer = True
    mainpanel.ListBox.List.reInitBuffer = True
    mainpanel.ListTab.reInitBuffer = True
    mainpanel.ListTab.TabList.DirectDraw()


class LibrarySearchBox(DialogBox):

    # search the library by words, BPM range, key and genre into Search
    TOLERANCES = (1, 2, 3, 5, 8)
    TOLERANCE = 3
    ANY = 'Any'

    def __init__(self, parent, mainpanel):
        DialogBox.__init__(self, parent, size=(440, 250))
        self.mainpanel = mainpanel
        self.SetTitle('Find in Library')
        self.songs = library.collect(self.mainpanel.ListBox)
        # the dialogs' spacing: names right-aligned (fit_name_column)
        name, step = 70, DIALOG_ROW + DIALOG_GAP
        x, y = DIALOG_PAD + name + DIALOG_GAP, DIALOG_PAD
        width = x + 320 + DIALOG_PAD
        self.SetClientSize((width, DIALOG_PAD + step * 3 + DIALOG_ROW + DIALOG_PAD
                            + self.GetFooterHeight()))
        style = wx.TE_PROCESS_ENTER

        def label(text, y):
            StaticText(self, label=text, pos=(DIALOG_PAD, y + 3), size=(name, -1),
                       style=wx.ALIGN_RIGHT)
        label('Words', y)
        self.Words = TextCtrl(self, pos=(x, y), size=(320, DIALOG_ROW), style=style)
        y += step
        # BPM and a tolerance (3% at first), half and double too
        label('BPM', y)
        self.Tempo = TextCtrl(self, pos=(x, y), size=(60, DIALOG_ROW), style=style)
        StaticText(self, label='\u00b1', pos=(x + 60 + DIALOG_GAP, y + 3), size=(10, -1))
        self.Tolerance = ComboBox(self, value=f'{int(self.TOLERANCE)}%',
                                  choices=[f'{int(v)}%' for v in self.TOLERANCES],
                                  pos=(x + 60 + DIALOG_GAP * 2 + 10, y), size=(64, DIALOG_ROW),
                                  style=wx.CB_READONLY)
        # the check boxes a group past the fields, one column
        cx = x + 60 + DIALOG_GAP * 2 + 10 + 64 + DIALOG_PAD
        self.Octave, _ = make_check(self, 'Half and double too', (cx, y + 3), False,
                                    lambda value: None)
        y += step
        # the 24 keys in Options' key format
        label('Key', y)
        self.Key = ComboBox(self, value=self.ANY, choices=[self.ANY] + self.GetKeys(),
                            pos=(x, y), size=(60 + DIALOG_GAP * 2 + 10 + 64, DIALOG_ROW),
                            style=wx.CB_READONLY)
        self.Compatible, _ = make_check(self, 'Compatible keys too', (cx, y + 3), False,
                                        lambda value: None)
        y += step
        # the genres the library's songs have
        label('Genre', y)
        self.Genre = ComboBox(self, value=self.ANY, choices=[self.ANY] + self.GetGenres(),
                              pos=(x, y), size=(320, DIALOG_ROW), style=wx.CB_READONLY)
        for control in (self.Words, self.Tempo):
            control.Bind(wx.EVT_TEXT_ENTER, self.OnSearch)
        shift = fit_name_column(self, DIALOG_PAD, name)
        width -= shift
        self.SetClientSize((width, self.GetClientSize().height))
        self.PlayingButton = Button(self, label='From playing song', size=(130, 26))
        self.PlayingButton.Bind(wx.EVT_BUTTON, self.OnPlaying)
        self.SearchButton = Button(self, label='Search', primary=True)
        self.SearchButton.Bind(wx.EVT_BUTTON, self.OnSearch)
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        top = self.PlaceButtons(right=(self.SearchButton, self.CloseButton),
                                left=(self.PlayingButton,))
        # the result's words between the buttons, PAD from either, on their middle
        left = self.PlayingButton.GetRect().GetRight() + 1 + DIALOG_PAD
        self.Status = StaticText(self, label='', pos=(left, top + 5),
                                 size=(self.SearchButton.GetPosition().x - DIALOG_PAD - left, 18),
                                 style=wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)

    def GetKeyFormat(self):
        # Options' key format: flat, sharp (the first one) or Camelot
        kind = GetPreference('key_format_type')
        return kind if kind in (0, 1, 2) else 1

    def GetKeys(self):
        # the 24 keys: Camelot by the wheel, else major and minor per root
        names = mfeats.get_chord_type_definition()[self.GetKeyFormat()]
        if self.GetKeyFormat() == 2:
            return sorted(names, key=lambda v: (int(v[:-1]), v[-1]))
        return [v for k in range(12) for v in (names[k], names[k + 12])]

    def GetGenres(self):
        # genres from the songs' tags, once whatever the case, by name
        genres = dict()
        for song in self.songs:
            genre = str(song.values.get('genre', '') or '').strip()
            if genre:
                genres.setdefault(genre.lower(), genre)
        return sorted(genres.values(), key=lambda v: v.lower())

    def OnPlaying(self, event):
        playbox = self.mainpanel.PlayBox
        self.FromSong(playbox.GetPlayingTempo(), playbox.GetPlayingKey())

    def FromSong(self, tempo, key):
        # tempo within 3% (half and double too), key with compatible ones
        tempo = library.to_float(tempo)
        if tempo > 0:
            self.Tempo.SetValue(f'{tempo:.1f}')
            self.Tolerance.SetValue(f'{int(self.TOLERANCE)}%')
            self.Octave.SetValue(True)
        key = (key or '').strip()
        if key and key not in ('-', ' '):
            key = mfeats.convert_chord_type(key.strip(), self.GetKeyFormat())
            if key in self.GetKeys():
                self.Key.SetValue(key)
                self.Compatible.SetValue(True)

    def OnSearch(self, event):
        tempo = library.to_float(self.Tempo.GetValue())
        share = int(self.Tolerance.GetValue().rstrip('%')) / 100.0
        low, high = (tempo * (1 - share), tempo * (1 + share)) if tempo > 0 else (0.0, 0.0)
        key, genre = self.Key.GetValue(), self.Genre.GetValue()
        # the library as it is now (its genres as it was opened)
        self.songs = library.collect(self.mainpanel.ListBox)
        found = library.search(
            self.songs, text=self.Words.GetValue(), low=low, high=high,
            octave=self.Octave.GetValue(), key='' if key == self.ANY else key,
            compatible=self.Compatible.GetValue(), genre='' if genre == self.ANY else genre)
        show_library_results(self.mainpanel, library.SEARCH_TITLE, found)
        self.Status.SetLabel(f'{len(found)} of {len(self.songs)} songs')

    def OnClose(self, event):
        self.Destroy()


class LookUpList(wx.Window):

    '''columns: [(title, width, flexible)]; cells(row); picture(row, column)'''

    HEADER = 26
    ROW = 26
    PAD = 8
    PICTURE_GAP = 6
    BAR = 3
    SCROLL = 6
    # a column's least width when its edge is dragged; the edge's grip each side of it
    LEAST = 40
    GRIP = 4

    def __init__(self, parent, columns, cells, picture=None):
        wx.Window.__init__(self, parent, style=wx.WANTS_CHARS | wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.columns = columns
        self.cells = cells
        self.picture = picture
        self.count = 0
        self.selected = -1
        self.offset = 0
        self.sort = None
        self.drag = None
        self.widths = []
        self.hidden = set()
        # dragged widths per column or None; the drag: (column, x, widths)
        self.custom = None
        self.resize = None
        # horizontal scroll when wider than the list; bar drag: (x, hoffset)
        self.hoffset = 0
        self.hdrag = None
        # told: on_select(row), on_activate(row), on_menu(row, column), on_sort(column),
        # on_columns(hidden), on_widths(custom)
        self.on_select = self.on_activate = self.on_menu = self.on_sort = None
        self.on_columns = self.on_widths = None
        frame = wx.GetApp().GetTopWindow()
        listbox = getattr(getattr(frame, 'MainPanel', None), 'ListBox', None)
        self.font = getattr(listbox, 'font', None) or self.GetFont()
        self.tips = uikit.CutTips(self)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.tips.Update())
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnCaptureLost)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def SetCount(self, count):
        self.count = count
        self.selected = min(self.selected, count - 1)
        self.Scroll(self.offset)

    def GetSelected(self):
        return self.selected

    def Select(self, row, tell=False):
        if not 0 <= row < self.count:
            return
        self.selected = row
        self.EnsureVisible(row)
        self.Refresh(False)
        if tell and self.on_select:
            self.on_select(row)

    def SetSort(self, column, ascending):
        self.sort = (column, ascending)
        self.Refresh(False)

    # the horizontal bar's strip below the rows
    HBAR = 12

    def HasHBar(self):
        return sum(self.widths) > self.GetClientSize().width

    def GetView(self):
        strip = self.HBAR if self.HasHBar() else 0
        return max(self.GetClientSize().height - self.HEADER - strip, 0)

    def Scroll(self, offset):
        most = max(self.count * self.ROW - self.GetView(), 0)
        self.offset = int(min(max(offset, 0), most))
        self.Refresh(False)

    def EnsureVisible(self, row):
        top, bottom = row * self.ROW, (row + 1) * self.ROW
        if top < self.offset:
            self.Scroll(top)
        elif bottom > self.offset + self.GetView():
            self.Scroll(bottom - self.GetView())

    def GetWidths(self, width):
        shown = [k not in self.hidden for k in range(len(self.columns))]
        if self.custom is not None:
            widths = [w if on else 0 for w, on in zip(self.custom, shown)]
            last = max((k for k, on in enumerate(shown) if on), default=None)
            if last is not None:
                widths[last] = max(width - sum(widths) + widths[last], self.LEAST)
            return widths
        fixed = sum(w for (_, w, flexible), on in zip(self.columns, shown) if on and not flexible)
        shares = sum(w for (_, w, flexible), on in zip(self.columns, shown) if on and flexible)
        room = max(width - fixed, 0)
        # flexible columns never under 0.6 of their width nor LEAST
        widths = [0 if not on else max(int(room * w / shares), int(w * 0.6), self.LEAST)
                  if flexible else w for (_, w, flexible), on in zip(self.columns, shown)]
        last = max((k for k, on in enumerate(shown) if on), default=None)
        if last is not None and sum(widths) < width:
            widths[last] += width - sum(widths)
        return widths

    def ScrollH(self, hoffset):
        most = max(sum(self.widths) - self.GetClientSize().width, 0)
        self.hoffset = int(min(max(hoffset, 0), most))
        self.Refresh(False)

    def GetHThumb(self):
        # in its strip, clear of the sides and of the upright bar's corner
        w, h = self.GetClientSize()
        total = sum(self.widths)
        if total <= w or w <= 0:
            return None
        track = w - 4 - (self.SCROLL + 4 if self.count * self.ROW > self.GetView() else 0)
        width = max(int(track * w / total), 24)
        left = 2 + int((track - width) * self.hoffset / (total - w))
        return wx.Rect(left, h - self.HBAR + (self.HBAR - self.SCROLL) // 2, width,
                       self.SCROLL)

    def SetHidden(self, hidden):
        hidden = set(k for k in hidden if 0 <= k < len(self.columns))
        if len(hidden) < len(self.columns):
            self.hidden = hidden
            self.Refresh(False)

    def ShowColumnMenu(self):
        menu = wx.Menu()
        for k, (title, _, _) in enumerate(self.columns):
            item = menu.AppendCheckItem(wx.ID_ANY, title)
            item.Check(k not in self.hidden)
            item.Enable(k in self.hidden or len(self.hidden) < len(self.columns) - 1)
            menu.Bind(wx.EVT_MENU, lambda e, k=k: self.ToggleColumn(k), item)
        menu.AppendSeparator()
        item = menu.Append(wx.ID_ANY, 'Reset column widths')
        item.Enable(self.custom is not None)
        menu.Bind(wx.EVT_MENU, lambda e: self.ResetWidths(), item)
        uikit.mark_menu_checks(menu)
        self.PopupMenu(menu)
        menu.Destroy()

    def ToggleColumn(self, k):
        self.SetHidden(self.hidden ^ {k})
        if self.on_columns:
            self.on_columns(set(self.hidden))

    def SetCustomWidths(self, custom):
        # None, or a width for every column
        if custom is not None and len(custom) != len(self.columns):
            custom = None
        self.custom = custom
        self.Refresh(False)

    def ResetWidths(self):
        self.SetCustomWidths(None)
        if self.on_widths:
            self.on_widths(None)

    def GetEdge(self, x):
        # the column whose right edge is under x (the last shown one has none), or None
        last = max((k for k, w in enumerate(self.widths) if w), default=-1)
        x += self.hoffset
        right = 0
        for k, w in enumerate(self.widths):
            right += w
            if w and k < last and abs(x - right) <= self.GRIP:
                return k
        return None

    def HitTest(self, point):
        # (row or -1, column or -1); -2 for the header row
        x, y = point
        x += self.hoffset
        column, left = -1, 0
        for k, w in enumerate(self.widths):
            if left <= x < left + w:
                column = k
                break
            left += w
        if y < self.HEADER:
            return -2, column
        row = int((y - self.HEADER + self.offset) // self.ROW)
        return (row if 0 <= row < self.count else -1), column

    def GetThumb(self):
        view, total = self.GetView(), self.count * self.ROW
        if total <= view or view <= 0:
            return None
        w, track = self.GetClientSize().width, view - 4
        height = max(int(track * view / total), 24)
        top = self.HEADER + 2 + int((track - height) * self.offset / (total - view))
        return wx.Rect(w - self.SCROLL - 2, top, self.SCROLL, height)

    def OnSize(self, event):
        self.Scroll(self.offset)
        event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        st = macroboxstyle.current().LISTBOX
        w, h = self.GetClientSize()
        self.widths = self.GetWidths(w)
        self.hoffset = int(min(self.hoffset, max(sum(self.widths) - w, 0)))
        dc.SetBackground(wx.Brush(wx.Colour(*st.LIST_BG_COLOR)))
        dc.Clear()
        self.tips.Clear()
        self.DrawRows(dc, st, w, h)
        self.DrawHeader(dc, st, w)
        for thumb in (self.GetThumb(), self.GetHThumb()):
            if thumb is None:
                continue
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(*st.SCROLLBAR_PN_COLOR)))
            dc.DrawRoundedRectangle(thumb, self.SCROLL / 2.0)

    def DrawRows(self, dc, st, w, h):
        ct = st.LIST_BG_CONTRAST
        grounds = [wx.Colour(*[min(max(v + d, 0), 255) for v in st.LIST_BG_COLOR[:3]])
                   for d in (-ct, ct)]
        dc.SetFont(self.font)
        th = dc.GetTextExtent('Ag')[1]
        first = self.offset // self.ROW
        last = min(self.count, (self.offset + self.GetView()) // self.ROW + 1)
        dc.SetClippingRegion(0, self.HEADER, w, self.GetView())
        for row in range(first, last):
            y = self.HEADER + row * self.ROW - self.offset
            selected = row == self.selected
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(*st.SELECTED_BG_COLOR) if selected
                                 else grounds[row % 2]))
            dc.DrawRectangle(0, y, w, self.ROW)
            if selected:
                dc.SetBrush(wx.Brush(wx.Colour(*st.SELECTED_BAR_COLOR)))
                dc.DrawRectangle(0, y, self.BAR, self.ROW)
            dc.SetTextForeground(wx.Colour(*(st.SELECTED_FG_COLOR if selected
                                             else st.LIST_FG_COLOR)))
            x = -self.hoffset
            for column, (text, width) in enumerate(zip(self.cells(row), self.widths)):
                if not width:
                    continue
                bitmap = self.picture(row, column) if self.picture else None
                left = x + self.PAD
                if bitmap is not None and bitmap.IsOk():
                    dc.DrawBitmap(bitmap, left, y + (self.ROW - bitmap.GetHeight()) // 2)
                    left += bitmap.GetWidth() + self.PICTURE_GAP
                if text:
                    shown = wx.Control.Ellipsize(str(text), dc, wx.ELLIPSIZE_END,
                                                 max(x + width - self.PAD - left, 1))
                    dc.DrawText(shown, left, y + (self.ROW - th) // 2)
                    # the row's part in the view
                    top = max(y, self.HEADER)
                    bottom = min(y + self.ROW, self.HEADER + self.GetView())
                    if bottom > top:
                        self.tips.Add((x, top, width, bottom - top), text, shown)
                x += width
        dc.DestroyClippingRegion()

    def DrawHeader(self, dc, st, w):
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Colour(*st.HEADER_BG_COLOR)))
        dc.DrawRectangle(0, 0, w, self.HEADER)
        font = uikit.get_font(10)
        dc.SetFont(font)
        top = int(round(uikit.get_caps_top(font, 0, self.HEADER)))
        dim = [int(v * 0.62 + g * 0.38) for v, g in zip(st.HEADER_FG_COLOR, st.HEADER_BG_COLOR)]
        dc.SetTextForeground(wx.Colour(*dim))
        dc.SetPen(wx.Pen(wx.Colour(*st.HEADER_PN_COLOR), 1))
        dc.DrawLine(0, self.HEADER - 1, w, self.HEADER - 1)
        x = -self.hoffset
        last = max((k for k, w in enumerate(self.widths) if w), default=-1)
        for column, ((title, _, _), width) in enumerate(zip(self.columns, self.widths)):
            if not width:
                continue
            sorted_here = self.sort is not None and self.sort[0] == column
            room = width - self.PAD * 2 - (12 if sorted_here else 0)
            shown = wx.Control.Ellipsize(title.upper(), dc, wx.ELLIPSIZE_END, max(room, 1))
            dc.DrawText(shown, x + self.PAD, top)
            self.tips.Add((x, 0, width, self.HEADER), title.upper(), shown)
            if sorted_here:
                cx, cy, size = x + width - self.PAD - 3, self.HEADER // 2, 3
                down = [(cx - size, cy - 1), (cx + size, cy - 1), (cx, cy + 2)]
                up = [(cx - size, cy + 2), (cx + size, cy + 2), (cx, cy - 1)]
                points = up if self.sort[1] else down
                dc.SetBrush(wx.Brush(wx.Colour(*st.HEADER_FG_COLOR)))
                dc.SetPen(wx.Pen(wx.Colour(*st.HEADER_FG_COLOR), 1))
                dc.DrawPolygon(points)
                dc.SetPen(wx.Pen(wx.Colour(*st.HEADER_PN_COLOR), 1))
            x += width
            if column < last:
                dc.DrawLine(x, 5, x, self.HEADER - 5)

    def OnLeftDown(self, event):
        self.SetFocus()
        hthumb = self.GetHThumb()
        if hthumb is not None and event.GetY() >= hthumb.y - 2:
            if hthumb.Contains(event.GetPosition()):
                self.hdrag = (event.GetX(), self.hoffset)
                self.CaptureMouse()
            else:
                w = self.GetClientSize().width
                self.ScrollH(self.hoffset + (w if event.GetX() > hthumb.x else -w))
            return
        thumb = self.GetThumb()
        if thumb is not None and event.GetX() >= thumb.x - 2:
            if thumb.Contains(event.GetPosition()):
                self.drag = (event.GetY(), self.offset)
                self.CaptureMouse()
            else:
                page = self.GetView() if event.GetY() > thumb.y else -self.GetView()
                self.Scroll(self.offset + page)
            return
        row, column = self.HitTest(event.GetPosition())
        edge = self.GetEdge(event.GetX()) if row == -2 else None
        if edge is not None:
            self.resize = (edge, event.GetX(), list(self.widths))
            self.CaptureMouse()
        elif row == -2:
            if column >= 0 and self.on_sort:
                self.on_sort(column)
        elif row >= 0:
            self.Select(row, tell=True)

    def OnLeftUp(self, event):
        if self.hdrag is not None:
            self.hdrag = None
            if self.HasCapture():
                self.ReleaseMouse()
        if self.resize is not None:
            self.resize = None
            if self.HasCapture():
                self.ReleaseMouse()
            if self.on_widths:
                self.on_widths(list(self.custom))
        if self.drag is not None:
            self.drag = None
            if self.HasCapture():
                self.ReleaseMouse()

    def DragEdge(self, x):
        # widen from the next columns (nearest first), narrow into the next
        column, start, widths = self.resize
        widths = list(widths)
        after = [k for k in range(column + 1, len(widths)) if widths[k]]
        spare = sum(widths[k] - self.LEAST for k in after if widths[k] > self.LEAST)
        moved = int(min(max(x - start, self.LEAST - widths[column]), spare))
        widths[column] += moved
        if moved < 0:
            widths[after[0]] -= moved
        for k in after:
            if moved <= 0:
                break
            given = min(max(widths[k] - self.LEAST, 0), moved)
            widths[k] -= given
            moved -= given
        custom = list(self.custom) if self.custom is not None\
            else [w for _, w, _ in self.columns]
        for k, w in enumerate(widths):
            if w:
                custom[k] = w
        self.custom = custom
        self.Refresh(False)

    def OnMotion(self, event):
        if self.hdrag is not None and event.LeftIsDown():
            thumb = self.GetHThumb()
            if thumb is not None:
                x, hoffset = self.hdrag
                w, total = self.GetClientSize().width, sum(self.widths)
                self.ScrollH(hoffset + (event.GetX() - x) * (total - w) / max(w - thumb.width, 1))
            return
        if self.resize is not None and event.LeftIsDown():
            self.DragEdge(event.GetX())
            return
        if self.drag is None:
            over = event.GetY() < self.HEADER and self.GetEdge(event.GetX()) is not None
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE if over else wx.CURSOR_ARROW))
            self.tips.Update(None if over else event.GetPosition())
        if self.drag is None or not event.LeftIsDown():
            return
        thumb = self.GetThumb()
        if thumb is None:
            return
        y, offset = self.drag
        total, view = self.count * self.ROW, self.GetView()
        moved = (event.GetY() - y) * (total - view) / max(view - 4 - thumb.height, 1)
        self.Scroll(offset + moved)

    def OnCaptureLost(self, event):
        self.drag = None
        self.resize = None
        self.hdrag = None

    def OnLeftDClick(self, event):
        row, _ = self.HitTest(event.GetPosition())
        if row >= 0 and self.on_activate:
            self.Select(row)
            self.on_activate(row)

    def OnRightDown(self, event):
        self.SetFocus()
        row, column = self.HitTest(event.GetPosition())
        if row == -2:
            self.ShowColumnMenu()
        elif row >= 0:
            self.Select(row, tell=True)
            if self.on_menu:
                self.on_menu(row, column)

    def OnWheel(self, event):
        # sideways with a tilted wheel or with Shift
        step = event.GetWheelRotation() / 120.0
        if event.GetWheelAxis() == wx.MOUSE_WHEEL_HORIZONTAL:
            self.ScrollH(self.hoffset + step * 60)
        elif event.ShiftDown():
            self.ScrollH(self.hoffset - step * 60)
        else:
            self.Scroll(self.offset - step * 3 * self.ROW)

    TRACK_MOVES = {'previous_track': -1, 'next_track': 1}

    def GetTrackMove(self, event):
        frame = wx.GetApp().GetTopWindow()
        if not hasattr(frame, 'GetNameSpaceByRawKeyFlag'):
            return None
        namespace = frame.GetNameSpaceByRawKeyFlag(
            event.GetRawKeyFlags(), event.CmdDown() or event.ControlDown(), event.ShiftDown())
        return self.TRACK_MOVES.get(namespace)

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        page = max(self.GetView() // self.ROW - 1, 1)
        moves = {wx.WXK_UP: -1, wx.WXK_DOWN: 1, wx.WXK_PAGEUP: -page, wx.WXK_PAGEDOWN: page}
        track = self.GetTrackMove(event)
        if track is not None:
            self.Select(min(max(self.selected + track, 0), self.count - 1), tell=True)
        elif key in moves:
            self.Select(min(max(self.selected + moves[key], 0), self.count - 1), tell=True)
        elif key == wx.WXK_HOME:
            self.Select(0, tell=True)
        elif key == wx.WXK_END:
            self.Select(self.count - 1, tell=True)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if self.selected >= 0 and self.on_activate:
                self.on_activate(self.selected)
        else:
            event.Skip()


class WebInfoBox(DialogBox):

    COVER = 200

    def __init__(self, parent, candidates, errors, length='', use=None):
        # resizable by its edges, size kept (lookup_size)
        DialogBox.__init__(self, parent, size=(1150, 340), style=wx.RESIZE_BORDER)
        self.built = False
        # use(field, value): one cell's value put in the editor's field (its menu)
        self.use = use
        # not composited (WS_EX_COMPOSITED): Windows' list repaints endlessly
        self.SetDoubleBuffered(False)
        title = f'Look Up: {len(candidates)} found'
        if length:
            title += f', this file {length}'
        self.SetTitle(title)
        self.candidates = candidates
        self.selected = None
        # every row's cover fetched in turn, the chosen row first, by address
        self.covers = dict()
        self.cover_first = 0
        self.closing = False
        # by address: the pictures, the edits made here and what they make
        self.datas = dict()
        self.edits = dict()
        self.edited = dict()
        self.shown_url = None
        # as tall as the cover and its note
        self.SetClientSize((self.GetClientSize().width, DIALOG_PAD + self.COVER + DIALOG_GAP
                            + 18 + DIALOG_PAD + self.GetFooterHeight()))
        # no smaller than made, but for a narrower list
        least = self.GetClientSize()
        self.SetMinClientSize((least.width - 300, least.height))
        kept = GetPreference('lookup_size')
        if isinstance(kept, tuple) and len(kept) == 2:
            self.SetClientSize((max(kept[0], least.width - 300), max(kept[1], least.height)))
        # Cover: none -, fetching ..., failed Failed
        # Cover as wide as a size and ratio text
        columns = (('Source', 72, False), ('Cover', 160, False), ('Artist', 120, True),
                   ('Title', 130, True), ('Album', 110, True), ('Release', 170, True),
                   ('Genre', 90, False), ('Length', 64, False), ('Year', 62, False),
                   ('Score', 64, False))
        self.List = LookUpList(self, columns, self.GetRowCells, self.GetRowPicture)
        self.thumbs = dict()
        # shown order as indexes into candidates; header click sorts, again reverses
        self.order = list(range(len(candidates)))
        self.sort_column = None
        self.sort_ascending = True
        # Cover text by address; picture sizes for sorting
        self.cover_cells = dict()
        self.cover_sizes = dict()
        self.List.SetCount(len(candidates))
        self.List.on_sort = self.OnColumnClick
        self.List.on_activate = lambda row: self.OnApply(None)
        self.List.on_menu = self.OnRowMenu
        self.List.on_select = self.OnSelected
        titles = [title for title, _, _ in columns]
        hidden = GetPreference('lookup_hidden_columns') or []
        self.List.SetHidden([titles.index(v) for v in hidden if v in titles])
        self.List.on_columns = lambda hidden: SetPreference(
            'lookup_hidden_columns', [titles[k] for k in sorted(hidden)])
        # the widths its edges were dragged to, kept by title for the next Look Up
        kept = GetPreference('lookup_column_widths')
        if isinstance(kept, dict):
            self.List.SetCustomWidths([kept.get(title, w) for title, w, _ in columns])
        self.List.on_widths = lambda custom: SetPreference(
            'lookup_column_widths', None if custom is None else dict(zip(titles, custom)))
        # as every cover: click to edit, the cover items on right-click
        self.Cover = CoverPicture(self, (self.COVER, self.COVER))
        self.Cover.Bind(wx.EVT_LEFT_UP, lambda e: wx.CallAfter(self.DoCoverItem, 'Edit Cover...'))
        self.Cover.Bind(wx.EVT_RIGHT_UP, lambda e: self.OnCoverMenu())
        self.CoverText = StaticText(self, label='', style=wx.ALIGN_CENTER)
        self.ApplyButton = Button(self, label='Apply', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CancelButton = Button(self, label='Cancel')
        self.CancelButton.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.SetCover(None, '')
        self.Errors = None
        if errors:
            self.Errors = StaticText(self, label=' / '.join(errors), size=(-1, 18))
        self.PageButton = Button(self, label='Open Page')
        self.PageButton.Bind(wx.EVT_BUTTON, lambda e: self.OpenPage(self.GetChosen()))
        self.PageButton.SetToolTip(wx.ToolTip('Open the chosen release on its service'))
        self.YouTubeButton = Button(self, label='YouTube')
        self.YouTubeButton.Bind(wx.EVT_BUTTON, lambda e: self.SearchYouTube(self.GetChosen()))
        self.YouTubeButton.SetToolTip(wx.ToolTip('Look for its artist and title on YouTube'))
        top = self.PlaceButtons(right=(self.PageButton, self.YouTubeButton, self.ApplyButton,
                                       self.CancelButton))
        made = set(self.GetChildren())
        # off until a row is chosen (OnSelected): with nothing found, never on
        self.PageButton.Disable()
        self.YouTubeButton.Disable()
        # fields Apply takes from the row, each on its own, and its cover
        tags = GetPreference('lookup_apply_tags') is not False
        self.apply = dict()
        for key in self.APPLY_KEYS:
            kept = GetPreference(f'lookup_apply_{key}')
            self.apply[key] = (tags if key != 'cover' else True) if kept is None else bool(kept)
        x = DIALOG_PAD
        for key in self.APPLY_KEYS:
            _, used = make_check(self, key.capitalize(), (x, top + 5), self.apply[key],
                                 lambda value, key=key: self.SetApply(key, value))
            x += used + DIALOG_PAD
        # the checks and their names, how far under the buttons' top (on the footer's row)
        self.checks = [(v, v.GetPosition().y - top) for v in self.GetChildren()
                       if v not in made]
        self.built = True
        self.PlaceParts()
        self.candidates_found = bool(candidates)
        if candidates:
            self.List.Select(0, tell=True)
            self.List.SetFocus()
        self.SetApply()
        if any(v['image'] for v in candidates):
            threading.Thread(target=self.FetchCovers, daemon=True).start()

    # Apply's checks, in the list's order
    APPLY_KEYS = ('artist', 'title', 'album', 'genre', 'cover')

    def OnSize(self, event):
        # asked while the dialog is made, before its parts
        if getattr(self, 'built', False):
            self.PlaceParts()
            self.Refresh(False)
        if event is not None:
            event.Skip()

    def PlaceParts(self):
        # the dialogs' spacing: list and cover PAD in and apart
        width, height = self.GetClientSize()
        bottom = self.GetContentBottom()
        rows = DIALOG_ROW + DIALOG_GAP if self.Errors is not None else 0
        cx = width - DIALOG_PAD - self.COVER
        self.List.SetRect((DIALOG_PAD, DIALOG_PAD, cx - DIALOG_PAD * 2,
                           bottom - DIALOG_PAD - rows))
        self.Cover.SetRect((cx, DIALOG_PAD, self.COVER, self.COVER))
        self.CoverText.SetRect((cx, DIALOG_PAD + self.COVER + DIALOG_GAP, self.COVER, 18))
        if self.Errors is not None:
            self.Errors.SetRect((DIALOG_PAD, bottom - DIALOG_ROW + 3, cx - DIALOG_PAD * 2, 18))
        top = self.PlaceButtons(right=(self.PageButton, self.YouTubeButton, self.ApplyButton,
                                       self.CancelButton))
        for window, below in self.checks:
            window.SetPosition((window.GetPosition().x, top + below))

    def GetRowValues(self, k):
        v = self.candidates[k]
        score = '' if v['score'] is None else f'{v["score"]:.2f}'
        cover = self.cover_cells.get(v['image'], '...') if v['image'] else '-'
        return (v['source'], cover, v['artist'], v['title'], v['album'], v['release'],
                v['genre'], webinfo.format_duration(v['duration']), v['year'], score)

    def GetRowCells(self, row):
        return self.GetRowValues(self.order[row])

    def GetRowPicture(self, row, column):
        if column != 1:
            return None
        return self.thumbs.get(self.candidates[self.order[row]]['image'])

    def FillRows(self):
        self.List.Refresh(False)

    def GetSortKey(self, k, column):
        # Length, Year, Score numeric, Cover by size, the rest text; None last
        v = self.candidates[k]
        if column == 7:
            return v['duration'] or None
        if column == 8:
            return int(v['year'][:4]) if v['year'][:4].isdigit() else None
        if column == 9:
            return v['score']
        if column == 1:
            size = self.cover_sizes.get(v['image'])
            return size[0] * size[1] if size else None
        text = self.GetRowValues(k)[column]
        return text.casefold() if text else None

    def OnColumnClick(self, column):
        if column < 0:
            return
        ascending = not self.sort_ascending if column == self.sort_column else True
        self.sort_column, self.sort_ascending = column, ascending
        row = self.List.GetSelected()
        chosen = self.order[row] if row >= 0 else None
        keys = dict((k, self.GetSortKey(k, column)) for k in self.order)
        present = sorted([k for k in self.order if keys[k] is not None], key=keys.get,
                         reverse=not ascending)
        self.order = present + [k for k in self.order if keys[k] is None]
        self.List.SetSort(column, ascending)
        # the chosen row stays chosen where it has moved to
        if chosen is not None:
            self.List.Select(self.order.index(chosen))
        self.FillRows()

    def OnRowMenu(self, idx, column):
        # row menu: values into fields, copy the cell, open its page
        row = self.candidates[self.order[idx]]
        menu = wx.Menu()

        def add(name, action, enable=True):
            item = menu.Append(wx.ID_ANY, name.replace('&', '&&'))
            item.Enable(enable)
            menu.Bind(wx.EVT_MENU, lambda e: action(), item)

        for key in self.APPLY_KEYS:
            value = row['image'] if key == 'cover' else row[key]
            if not value:
                continue
            shown = 'its cover' if key == 'cover' else\
                (value if len(value) <= 50 else value[:47] + '...')
            if key == 'cover':
                value = self.GetCoverValue(value)
                shown = 'its cover, edited' if isinstance(value, tuple) else shown
            add(f'Use {key.capitalize()}: {shown}',
                lambda key=key, value=value: self.use(key.capitalize(), value),
                self.use is not None)
        menu.AppendSeparator()
        cell = self.GetRowCells(idx)[column] if column >= 0 else ''
        shown = cell if len(cell) <= 40 else f'{cell[:37]}...'
        add(f'Copy "{shown}"' if cell else 'Copy',
            lambda: self.CopyText(cell), bool(cell))
        add('Open Source Page', lambda: self.OpenPage(row), bool(row['url']))
        add('Search on YouTube', lambda: self.SearchYouTube(row),
            bool(row['artist'] or row['title']))
        uikit.mark_menu_checks(menu)
        self.List.PopupMenu(menu)
        menu.Destroy()

    def CopyText(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()

    def SetApply(self, key=None, value=None):
        if key is not None:
            self.apply[key] = value
            SetPreference(f'lookup_apply_{key}', value)
        self.ApplyButton.Enable(self.candidates_found and any(self.apply.values()))

    def OnApply(self, event):
        idx = self.List.GetSelected()
        if idx < 0 or not any(self.apply.values()):
            return
        self.selected = self.order[idx]
        self.EndModal(wx.ID_OK)

    def MakeCover(self, data):
        # picture fitted in the cover square, or the ground alone
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
            return wx.Bitmap(image), (w, h)
        bmp = wx.Bitmap(self.COVER, self.COVER)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(macroboxstyle.current().UI.RAISED_BG))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)
        return bmp, None

    def MakeThumb(self, data):
        side = LookUpList.ROW - 6
        try:
            image = wx.Image(io.BytesIO(data))
        except Exception:
            return None
        if not image.IsOk():
            return None
        w, h = image.GetSize()
        scale = min(side / w, side / h)
        return wx.Bitmap(image.Scale(max(1, int(w * scale)), max(1, int(h * scale)),
                                     wx.IMAGE_QUALITY_HIGH))

    def SetCover(self, data, label, bitmap=None):
        self.Cover.SetBitmap(bitmap or self.MakeCover(data)[0])
        self.CoverText.SetLabel(label)

    def OnSelected(self, row):
        # its cover at once when fetched, else fetched next
        idx = self.order[row]
        self.cover_first = idx
        self.ShowCover(idx)
        chosen = self.candidates[idx]
        if hasattr(self, 'PageButton'):
            self.PageButton.Enable(bool(chosen['url']))
            self.YouTubeButton.Enable(bool(chosen['artist'] or chosen['title']))

    def GetChosen(self):
        row = self.List.GetSelected()
        return self.candidates[self.order[row]] if row >= 0 else None

    def OpenPage(self, chosen):
        if chosen and chosen['url']:
            webbrowser.open(chosen['url'])

    def GetYouTubeURL(self, chosen):
        words = ' '.join(v for v in (chosen['artist'], chosen['title']) if v)
        return 'https://www.youtube.com/results?search_query=' + urllib.parse.quote_plus(words)

    def SearchYouTube(self, chosen):
        if chosen and (chosen['artist'] or chosen['title']):
            webbrowser.open(self.GetYouTubeURL(chosen))

    def ShowCover(self, idx):
        # idx: the candidate's, not its row's
        url = self.candidates[idx]['image']
        self.shown_url = url
        self.Cover.SetActive(url in self.datas)
        if url in self.edited:
            bitmap, size = self.MakeCover(self.edited[url])
            label = '' if size is None else f'Edited to {format_picture_size(size)}'
            self.SetCover(None, label, bitmap)
        elif not url:
            self.SetCover(None, 'No cover')
        elif url in self.covers:
            bitmap, label = self.covers[url]
            self.SetCover(None, label, bitmap)
        else:
            self.SetCover(None, 'Loading...')

    def FetchCovers(self):
        # covers one at a time, the chosen row first; from disk when cached
        done = set()
        while not self.closing:
            order = [self.cover_first] + list(range(len(self.candidates)))
            todo = [k for k in order if self.candidates[k]['image']
                    and self.candidates[k]['image'] not in done]
            if not todo:
                return
            idx = todo[0]
            url = self.candidates[idx]['image']
            done.add(url)
            try:
                data, label = webinfo.fetch_image(url), ''
            except Exception as error:
                data, label = None, str(error)
            if self.closing:
                return
            wx.CallAfter(self.OnCoverLoaded, url, data, label)

    def OnCoverLoaded(self, url, data, label):
        if not self or self.closing:
            return
        bitmap, size = self.MakeCover(data)
        self.covers[url] = (bitmap, label or (format_picture_size(size) if size else 'Not an image'))
        if size:
            self.datas[url] = data
        # one cover may be several releases'
        self.cover_cells[url] = format_picture_size(size) if size else 'Failed'
        if size:
            self.cover_sizes[url] = size
        if size:
            self.thumbs[url] = self.MakeThumb(data)
        self.FillRows()
        idx = self.List.GetSelected()
        if idx >= 0 and self.candidates[self.order[idx]]['image'] == url:
            self.ShowCover(self.order[idx])

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnClose(self, event):
        self.EndModal(wx.ID_CANCEL)

    # the shared cover items, on the shown row's cover

    def OnCoverMenu(self):
        url = self.shown_url
        menu = wx.Menu()
        shown = self.edited[url] if url in self.edited else self.datas.get(url)
        append_cover_items(menu, shown, url in self.edited, self.DoCoverItem)
        uikit.mark_menu_checks(menu)
        self.Cover.PopupMenu(menu)
        menu.Destroy()

    def DoCoverItem(self, name):
        url = self.shown_url
        if not self or url not in self.datas:
            return
        data = self.datas[url]
        idx = [k for k, c in enumerate(self.candidates) if c['image'] == url][0]
        if name == 'Copy Cover':
            keep_copied_cover(self.edited.get(url, data), get_cover_label(self.candidates[idx]))
            return
        made = None
        if name == 'Undo Cover Change':
            self.edits.pop(url, None)
            self.edited.pop(url, None)
        elif name in COVER_PRESETS:
            edit = preset_cover(data, self.edits.get(url), COVER_PRESETS[name])
            made = None if edit is None else (listimages.edit_cover(data, edit), edit)
        elif name == 'Edit Cover...':
            made = edit_cover_by_hand(self, data, self.edits.get(url))
        if made is not None and made[0] is not None:
            self.edited[url], self.edits[url] = made
        self.ShowCover(idx)

    def GetCoverValue(self, url):
        # the address, or (picture, edit, edited) when edited here
        if url in self.edited:
            return (self.datas[url], self.edits[url], self.edited[url])
        return url

    def Destroy(self):
        # cover fetching ends with it
        self.closing = True
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


def draw_spinner(dc, cx, cy, radius, angle, colour):
    # a loading mark: three quarters of a ring, turned by angle (radians)
    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        return
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(colour)).Width(3)
                           .Cap(wx.CAP_ROUND)))
    path = gc.CreatePath()
    path.AddArc(cx, cy, radius, angle, angle + math.pi * 1.5, True)
    gc.StrokePath(path)


# the ratios told by name (Look Up's covers), the rest as one to 1
NAMED_RATIOS = ((1, 1), (4, 3), (3, 4), (3, 2), (2, 3), (16, 9), (9, 16), (5, 4), (4, 5))


def format_picture_size(size):
    # '640 x 480 (4:3)'; near a named ratio: '600 x 598 (~1:1)'
    w, h = size
    if not w or not h:
        return f'{w} x {h}'
    for a, b in NAMED_RATIOS:
        if w * b == h * a:
            return f'{w} x {h} ({a}:{b})'
    for a, b in NAMED_RATIOS:
        if abs(w / h - a / b) < 0.01:
            return f'{w} x {h} (\u2248{a}:{b})'
    return f'{w} x {h} ({w / h:.2f}:1)'


def fit_picture(data, side, ground):
    '''fit data in a square on ground: (bitmap, size) or (None, None)'''
    image, size = fit_image(data, side, ground)
    return (None, None) if image is None else (wx.Bitmap(image), size)


def fit_image(data, side, ground):
    # fit_picture's, as an image
    image = None
    if data:
        try:
            image = wx.Image(io.BytesIO(data))
        except Exception:
            image = None
    if image is None or not image.IsOk():
        return None, None
    w, h = image.GetSize()
    scale = min(side / w, side / h)
    image = image.Scale(max(1, int(w * scale)), max(1, int(h * scale)), wx.IMAGE_QUALITY_HIGH)
    image.Resize((side, side), ((side - image.GetWidth()) // 2,
                                (side - image.GetHeight()) // 2), *ground)
    return image, (w, h)


class CoverCards(wx.Window):

    '''covers as cards in rows: picture(k), lines(k), one chosen'''

    # cards no narrower than CARD, GAP apart, widened to fill the row
    CARD = 170
    GAP = 10
    TEXT = 38
    SCROLL = 6

    def __init__(self, parent, count, picture, lines):
        wx.Window.__init__(self, parent, style=wx.WANTS_CHARS | wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.count = count
        self.picture = picture
        self.lines = lines
        self.selected = -1
        self.hover = -1
        self.offset = 0
        self.drag = None
        self.empty = ''
        self.bitmaps = dict()
        # set by the box: loading(k), searching, the loading marks' angle
        self.loading = lambda k: False
        self.searching = False
        self.angle = 0.0
        # told: on_select(k), on_activate(k), on_menu(k), on_page(step: Page Up, Down)
        self.on_select = self.on_activate = self.on_menu = self.on_page = None
        self.tips = uikit.CutTips(self)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Scroll(self.offset), e.Skip()))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: (self.SetHover(-1), self.tips.Update()))
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda e: setattr(self, 'drag', None))
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)

    def OnRightDown(self, event):
        self.SetFocus()
        k = self.HitTest(event.GetPosition())
        if k >= 0 and self.on_menu:
            self.on_menu(k)

    def GetColumns(self):
        # cards a row and their side; room kept for the bar
        w = self.GetClientSize().width - self.SCROLL
        columns = max(1, (w - self.GAP) // (self.CARD + self.GAP))
        return columns, max(int((w - self.GAP * (columns + 1)) / columns), 1)

    def GetCardRect(self, k):
        columns, side = self.GetColumns()
        row, column = divmod(k, columns)
        return wx.Rect(self.GAP + column * (side + self.GAP),
                       self.GAP + row * (side + self.TEXT + self.GAP) - self.offset,
                       side, side + self.TEXT)

    def GetTotal(self):
        columns, side = self.GetColumns()
        rows = (self.count + columns - 1) // columns
        return self.GAP + rows * (side + self.TEXT + self.GAP)

    def GetBitmap(self, k, side):
        # its picture at the card size, made once a size
        image = self.picture(k)
        if image is None or not image.IsOk():
            return None
        key = (k, side, id(image))
        if key not in self.bitmaps:
            if len(self.bitmaps) > 200:
                self.bitmaps.clear()
            self.bitmaps[key] = image.Scale(side, side, wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()
        return self.bitmaps[key]

    def Scroll(self, offset):
        most = max(self.GetTotal() - self.GetClientSize().height, 0)
        self.offset = int(min(max(offset, 0), most))
        self.Refresh(False)

    def EnsureVisible(self, k):
        rect = self.GetCardRect(k)
        h = self.GetClientSize().height
        if rect.y < self.GAP:
            self.Scroll(self.offset + rect.y - self.GAP)
        elif rect.GetBottom() > h - self.GAP:
            self.Scroll(self.offset + rect.GetBottom() - h + self.GAP)

    def Select(self, k, tell=True):
        if not 0 <= k < self.count:
            return
        self.selected = k
        self.EnsureVisible(k)
        self.Refresh(False)
        if tell and self.on_select:
            self.on_select(k)

    def SetHover(self, k):
        if k != self.hover:
            self.hover = k
            self.Refresh(False)

    def HitTest(self, point):
        for k in range(self.count):
            if self.GetCardRect(k).Contains(point):
                return k
        return -1

    def GetThumb(self):
        w, h = self.GetClientSize()
        total = self.GetTotal()
        if total <= h or h <= 0:
            return None
        track = h - 4
        height = max(int(track * h / total), 24)
        top = 2 + int((track - height) * self.offset / (total - h))
        return wx.Rect(w - self.SCROLL - 2, top, self.SCROLL, height)

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        st = macroboxstyle.current().LISTBOX
        ui = macroboxstyle.current().UI
        w, h = self.GetClientSize()
        dc.SetBackground(wx.Brush(wx.Colour(*st.LIST_BG_COLOR)))
        dc.Clear()
        dc.SetFont(uikit.get_font(uikit.BODY))
        th = dc.GetTextExtent('Ag')[1]
        self.tips.Clear()
        if self.count == 0 and self.searching:
            draw_spinner(dc, w / 2.0, h / 2.0 - 18, 14, self.angle, ui.ACCENT)
            text = 'Looking up covers...'
            tw, _ = dc.GetTextExtent(text)
            dc.SetTextForeground(wx.Colour(ui.BAR_TEXT_DIM))
            dc.DrawText(text, (w - tw) // 2, h // 2 + 8)
        elif self.count == 0 and self.empty:
            dc.SetTextForeground(wx.Colour(ui.BAR_TEXT_DIM))
            tw, _ = dc.GetTextExtent(self.empty)
            dc.DrawText(self.empty, (w - tw) // 2, (h - th) // 2)
        for k in range(self.count):
            rect = self.GetCardRect(k)
            if rect.GetBottom() < 0 or rect.y > h:
                continue
            side = rect.width
            picture = self.GetBitmap(k, side)
            if picture is not None:
                dc.DrawBitmap(picture, rect.x, rect.y)
            else:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.Brush(wx.Colour(ui.RAISED_BG)))
                dc.DrawRectangle(rect.x, rect.y, side, side)
                if self.loading(k):
                    draw_spinner(dc, rect.x + side / 2.0, rect.y + side / 2.0, 12,
                                 self.angle, ui.BAR_TEXT_DIM)
            # chosen: the accent round it; under the pointer: a lighter line
            if k == self.selected or k == self.hover:
                edge = ui.ACCENT if k == self.selected else ui.CONTROL_HOVER
                width = 3 if k == self.selected else 2
                dc.SetPen(wx.Pen(wx.Colour(edge), width))
                dc.SetBrush(wx.TRANSPARENT_BRUSH)
                inset = width // 2
                dc.DrawRectangle(rect.x - inset - 1, rect.y - inset - 1,
                                 side + width + 1, side + width + 1)
            first, second = self.lines(k)
            for n, (text, colour) in enumerate(((first, ui.TEXT), (second, ui.BAR_TEXT_DIM))):
                if not text:
                    continue
                dc.SetTextForeground(wx.Colour(colour))
                shown = wx.Control.Ellipsize(text, dc, wx.ELLIPSIZE_END, side)
                dc.DrawText(shown, rect.x, rect.y + side + 4 + n * (th + 2))
                self.tips.Add((rect.x, rect.y + side + 4 + n * (th + 2), side, th + 2), text,
                              shown)
        thumb = self.GetThumb()
        if thumb is not None:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(*st.SCROLLBAR_PN_COLOR)))
            dc.DrawRoundedRectangle(thumb, self.SCROLL / 2.0)

    def OnLeftDown(self, event):
        self.SetFocus()
        thumb = self.GetThumb()
        if thumb is not None and event.GetX() >= thumb.x - 2:
            if thumb.Contains(event.GetPosition()):
                self.drag = (event.GetY(), self.offset)
                self.CaptureMouse()
            else:
                page = self.GetClientSize().height
                self.Scroll(self.offset + (page if event.GetY() > thumb.y else -page))
            return
        k = self.HitTest(event.GetPosition())
        if k >= 0:
            self.Select(k)

    def OnLeftUp(self, event):
        if self.drag is not None:
            self.drag = None
            if self.HasCapture():
                self.ReleaseMouse()

    def OnMotion(self, event):
        if self.drag is not None and event.LeftIsDown():
            thumb = self.GetThumb()
            if thumb is not None:
                y, offset = self.drag
                h, total = self.GetClientSize().height, self.GetTotal()
                self.Scroll(offset + (event.GetY() - y) * (total - h)
                            / max(h - 4 - thumb.height, 1))
            return
        self.SetHover(self.HitTest(event.GetPosition()))
        self.tips.Update(event.GetPosition())

    def OnLeftDClick(self, event):
        k = self.HitTest(event.GetPosition())
        if k >= 0:
            self.Select(k)
            if self.on_activate:
                self.on_activate(k)

    def OnWheel(self, event):
        self.Scroll(self.offset - event.GetWheelRotation() / 120.0 * 80)

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        columns, _ = self.GetColumns()
        moves = {wx.WXK_LEFT: -1, wx.WXK_RIGHT: 1, wx.WXK_UP: -columns, wx.WXK_DOWN: columns}
        if key in moves and self.count:
            moved = self.selected + moves[key] if self.selected >= 0 else 0
            self.Select(min(max(moved, 0), self.count - 1))
        elif key == wx.WXK_HOME and self.count:
            self.Select(0)
        elif key == wx.WXK_END and self.count:
            self.Select(self.count - 1)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if self.selected >= 0 and self.on_activate:
                self.on_activate(self.selected)
        elif key in (wx.WXK_PAGEUP, wx.WXK_PAGEDOWN) and self.on_page:
            self.on_page(-1 if key == wx.WXK_PAGEUP else 1)
        else:
            event.Skip()


class CoverDetails(wx.Window):

    '''the chosen cover's preview over its release's fields'''

    LINES = 3
    SCROLL = 6
    # picture and text kept clear of the bar
    GUTTER = SCROLL + 6

    def __init__(self, parent):
        wx.Window.__init__(self, parent, style=wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.fields = []
        self.preview = None
        # set by the box: a loading mark at angle while its picture comes
        self.loading = False
        self.angle = 0.0
        # scrolled when taller than it is: offset, drawn height, bar drag
        self.offset = 0
        self.total = 0
        self.drag = None
        # set by the box: told when the preview is clicked, right-clicked
        self.on_preview = self.on_preview_menu = None
        self.over_preview = False
        self.Bind(wx.EVT_RIGHT_UP, self.OnRightUp)
        self.tips = uikit.CutTips(self)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: (self.SetPreviewHover(False), self.tips.Update()))
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Scroll(self.offset), e.Skip()))
        self.Bind(wx.EVT_MOUSEWHEEL, lambda e: self.Scroll(
            self.offset - e.GetWheelRotation() / 120.0 * 60))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda e: setattr(self, 'drag', None))

    def Scroll(self, offset):
        most = max(self.total - self.GetClientSize().height, 0)
        self.offset = int(min(max(offset, 0), most))
        self.Refresh(False)

    def GetThumb(self):
        w, h = self.GetClientSize()
        if self.total <= h or h <= 0:
            return None
        track = h - 4
        height = max(int(track * h / self.total), 24)
        top = 2 + int((track - height) * self.offset / (self.total - h))
        return wx.Rect(w - self.SCROLL, top, self.SCROLL, height)

    def SetPreviewHover(self, over):
        if over == self.over_preview:
            return
        self.over_preview = over
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND if over else wx.CURSOR_ARROW))
        self.SetToolTip(COVER_TIP if over else '')
        self.Refresh(False)

    def OnRightUp(self, event):
        if self.on_preview_menu is not None and self.IsOverPreview(event.GetPosition()):
            wx.CallAfter(self.on_preview_menu)

    def IsOverPreview(self, point):
        if self.preview is None or self.preview.IsOk() is False:
            return False
        x, y = point
        return 0 <= x < self.preview.GetWidth() and \
            0 <= y + self.offset < self.preview.GetHeight()

    def OnLeftDown(self, event):
        thumb = self.GetThumb()
        off_bar = thumb is None or event.GetX() < thumb.x - 2
        if off_bar and self.on_preview is not None and self.IsOverPreview(event.GetPosition()):
            # after the click: the edit window is modal
            wx.CallAfter(self.on_preview)
            return
        if off_bar:
            return
        if thumb.Contains(event.GetPosition()):
            self.drag = (event.GetY(), self.offset)
            self.CaptureMouse()
        else:
            page = self.GetClientSize().height
            self.Scroll(self.offset + (page if event.GetY() > thumb.y else -page))

    def OnLeftUp(self, event):
        if self.drag is not None:
            self.drag = None
            if self.HasCapture():
                self.ReleaseMouse()

    def OnMotion(self, event):
        thumb = self.GetThumb()
        over = self.on_preview is not None and self.IsOverPreview(event.GetPosition())
        if self.drag is None:
            self.SetPreviewHover(over)
            # the preview's own tip there
            if over:
                self.tips.Forget()
            else:
                self.tips.Update(event.GetPosition())
        if self.drag is None or thumb is None or not event.LeftIsDown():
            return
        y, offset = self.drag
        h = self.GetClientSize().height
        self.Scroll(offset + (event.GetY() - y) * (self.total - h) / max(h - 4 - thumb.height, 1))

    def SetFields(self, fields):
        # [(name, value)]
        self.fields = [(name, str(value)) for name, value in fields if value not in (None, '')]
        self.offset = 0
        self.Refresh(False)

    def SetPreview(self, bitmap):
        self.preview = bitmap
        self.Refresh(False)

    def Wrap(self, dc, text, width):
        lines, line = [], ''
        for word in text.split():
            joined = f'{line} {word}' if line else word
            if line and dc.GetTextExtent(joined)[0] > width:
                lines.append(line)
                line = word
            else:
                line = joined
        lines.append(line)
        if len(lines) > self.LINES:
            lines = lines[:self.LINES - 1] + [' '.join(lines[self.LINES - 1:])]
        return [wx.Control.Ellipsize(v, dc, wx.ELLIPSIZE_END, width) for v in lines]

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        ui = macroboxstyle.current().UI
        w, h = self.GetClientSize()
        dc.SetBackground(wx.Brush(wx.Colour(ui.DIALOG_BG)))
        dc.Clear()
        small, body = uikit.get_font(10), uikit.get_font(uikit.BODY)
        # text clear of the bar always, so lines do not rewrap
        tw = w - self.GUTTER
        y = -self.offset
        self.tips.Clear()
        if self.preview is not None and self.preview.IsOk():
            dc.DrawBitmap(self.preview, 0, y)
            if self.on_preview is not None:
                draw_cover_edge(wx.GraphicsContext.Create(dc), 0, y, self.preview.GetWidth() - 1,
                                self.preview.GetHeight() - 1, self.over_preview,
                                wx.Colour(ui.DIALOG_BG))
            y += self.preview.GetHeight() + DIALOG_GAP + 4
        elif self.loading:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(ui.RAISED_BG)))
            dc.DrawRectangle(0, y, tw, tw)
            draw_spinner(dc, tw / 2.0, y + tw / 2.0, 14, self.angle, ui.BAR_TEXT_DIM)
            y += tw + DIALOG_GAP + 4
        for name, value in self.fields:
            dc.SetFont(small)
            dc.SetTextForeground(wx.Colour(ui.BAR_TEXT_DIM))
            dc.DrawText(name.upper(), 0, y)
            y += dc.GetTextExtent('Ag')[1] + 2
            dc.SetFont(body)
            dc.SetTextForeground(wx.Colour(ui.TEXT))
            th = dc.GetTextExtent('Ag')[1]
            lines, top = self.Wrap(dc, value, tw), y
            for line in lines:
                dc.DrawText(line, 0, y)
                y += th + 1
            shown = ' '.join(lines)
            self.tips.Add((0, top, tw, y - top), value,
                          value if shown == ' '.join(value.split()) else shown)
            y += DIALOG_GAP + 2
        total = y + self.offset
        if total != self.total:
            self.total = total
            # offset held in the new height
            wx.CallAfter(lambda: self and self.Scroll(self.offset))
        thumb = self.GetThumb()
        if thumb is not None:
            st = macroboxstyle.current().LISTBOX
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(*st.SCROLLBAR_PN_COLOR)))
            dc.DrawRoundedRectangle(thumb, self.SCROLL / 2.0)


class CoverLookUpBox(DialogBox):

    # covers for tracks as cards, paged by track; Apply writes the chosen

    def __init__(self, parent, tracks, keys, start=0):
        # tracks: [dict(path, mdx, artist, title, label)]
        DialogBox.__init__(self, parent, size=(900, 600), style=wx.RESIZE_BORDER)
        self.built = False
        # not composited (as WebInfoBox): Windows' painting slows the player
        self.SetDoubleBuffered(False)
        self.keys = keys
        self.tracks = [dict(v, candidates=None, errors=[], chosen=None, asked=False)
                       for v in tracks]
        self.multi = len(self.tracks) > 1
        self.index = min(max(start, 0), len(self.tracks) - 1)
        # the shown track's covers (None: still looked up)
        self.candidates = []
        self.results = []
        self.closing = False
        self.fetching = False
        # by address: bytes, card, size text ('Failed'), output (GetOutput)
        self.data = dict()
        self.outputs = dict()
        self.pictures = dict()
        self.notes = dict()
        self.Cards = CoverCards(self, 0, self.GetPicture, self.GetLines)
        self.Cards.empty = 'No covers found'
        self.Cards.loading = lambda k: self.candidates[k]['image'] not in self.notes
        self.Cards.on_select = self.OnCardSelected
        self.Cards.on_activate = self.OnCardActivated
        self.Cards.on_menu = self.OnCardMenu
        if self.multi:
            self.Cards.on_page = self.MoveTrack
        # what the chosen cover is; its preview clicked to edit it
        self.Details = CoverDetails(self)
        self.Details.on_preview = self.EditChosen
        self.Details.on_preview_menu = self.OnPreviewMenu
        # by address: the edit made by hand, in place of the checks
        self.edits = dict()
        self.Note = None
        self.PageButton = Button(self, label='Open Page')
        self.PageButton.Bind(wx.EVT_BUTTON, self.OnOpenPage)
        self.PageButton.SetToolTip(wx.ToolTip('Open the chosen release on its service'))
        self.PrevButton = Button(self, label='Prev')
        self.PrevButton.Bind(wx.EVT_BUTTON, lambda e: self.MoveTrack(-1))
        self.NextButton = Button(self, label='Next')
        self.NextButton.Bind(wx.EVT_BUTTON, lambda e: self.MoveTrack(1))
        # shown off for one track too, as the tag editor's
        self.ApplyButton = Button(self, label='Apply', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.ApplyButton.SetToolTip(wx.ToolTip(
            'Write the chosen cover to each track that has one' if self.multi
            else 'Write the chosen cover to the track'))
        self.CancelButton = Button(self, label='Cancel')
        self.CancelButton.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.PageButton.Disable()
        self.ApplyButton.Disable()
        # covers not square cut square on their subject when written; kept
        self.square = GetPreference('cover_lookup_square') is not False
        top = self.PlaceButtons(right=self.GetButtons())
        made = set(self.GetChildren())
        _, square_width = make_check(self, 'Square', (DIALOG_PAD, top + 5), self.square,
                                     self.SetSquare)
        self.checks = [(v, v.GetPosition().y - top) for v in self.GetChildren()
                       if v not in made]
        # keep the files' modified date (the editor's KEEP setting)
        self.keep = GetPreference('item_editor_keep_modified') is not False
        made = set(self.GetChildren())
        _, self.keep_width = make_check(self, 'Keep modified date', (0, top + 5), self.keep,
                                        self.SetKeep)
        self.keep_check = [(v, v.GetPosition().x, v.GetPosition().y - top)
                           for v in self.GetChildren() if v not in made]
        # one cover for every track, under the chosen one's details; off for one
        self.same = False
        made = set(self.GetChildren())
        make_check(self, f'Same cover for all {len(self.tracks)} tracks' if self.multi
                   else 'Same cover for all tracks', (0, 0), False, self.SetSame)
        self.same_check = [(v, v.GetPosition()) for v in self.GetChildren() if v not in made]
        if not self.multi:
            # box off, name faint rather than Windows' disabled grey
            for window, _ in self.same_check:
                if isinstance(window, wx.StaticText):
                    window.SetForegroundColour(macroboxstyle.current().UI.TEXT_FAINT)
                    window.Unbind(wx.EVT_LEFT_DOWN)
                else:
                    window.Disable()
        # no narrower than the footer's parts apart, nor than a card by the details;
        # no lower than the details' preview and a few of its lines
        buttons = self.GetButtons()
        footer = DIALOG_PAD * 6 + square_width + self.keep_width + DIALOG_GAP * (
            len(buttons) - 1) + sum(v.GetSize().width for v in buttons)
        cards = DIALOG_PAD * 3 + CoverCards.CARD + CoverCards.GAP * 2 + CoverCards.SCROLL \
            + self.DETAILS
        least = (max(footer, cards), 440)
        self.SetMinClientSize(least)
        kept = GetPreference('cover_lookup_size')
        if isinstance(kept, tuple) and len(kept) == 2:
            self.SetClientSize((max(kept[0], least[0]), max(kept[1], least[1])))
        else:
            self.SetClientSize((max(1080, least[0]), 720))
        self.built = True
        self.PlaceParts()
        self.Spin = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnSpin, self.Spin)
        # however it closes, Esc too: no more turns asked of it
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.ShowTrack(self.index)

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.closing = True
            self.Spin.Stop()
        event.Skip()

    DETAILS = 230

    def GetButtons(self):
        return (self.PageButton, self.PrevButton, self.NextButton, self.ApplyButton,
                self.CancelButton)

    # tracks

    def ShowTrack(self, index):
        # a track's covers (looked up first when not yet), its chosen one shown chosen
        self.index = index
        track = self.tracks[index]
        self.candidates = list(track['candidates'] or [])
        chosen = track['chosen']
        if chosen is not None and chosen['image'] not in [v['image'] for v in self.candidates]:
            # one used for all tracks, not among this one's
            self.candidates.append(chosen)
        self.SetNote(track['errors'])
        self.Cards.searching = track['candidates'] is None
        self.Cards.count = len(self.candidates)
        urls = [v['image'] for v in self.candidates]
        self.Cards.selected = urls.index(chosen['image']) if chosen is not None else -1
        self.Cards.hover = -1
        self.Cards.Scroll(0)
        if self.Cards.selected >= 0:
            self.Cards.EnsureVisible(self.Cards.selected)
        self.Cards.SetFocus()
        self.PrevButton.Enable(index > 0)
        self.NextButton.Enable(index < len(self.tracks) - 1)
        self.ShowDetails()
        self.UpdateTitle()
        self.UpdateApply()
        if track['candidates'] is None:
            self.LookUp(index)
        elif index + 1 < len(self.tracks):
            # the next one looked up meanwhile
            self.LookUp(index + 1)
        self.EnsureFetching()
        self.Spin.Start(33)

    def MoveTrack(self, step):
        index = self.index + step
        if 0 <= index < len(self.tracks):
            self.ShowTrack(index)

    def LookUp(self, index):
        # a track's covers looked up on a thread (once), told back by OnFound
        track = self.tracks[index]
        if track['asked']:
            return
        track['asked'] = True
        keys = self.keys

        def work():
            try:
                candidates, errors = webinfo.lookup_covers(
                    track['path'], track['artist'].strip(), track['title'].strip(), keys,
                    webinfo.Cache())
            except Exception as error:
                candidates, errors = list(), [str(error)]
            wx.CallAfter(self.OnFound, index, candidates, errors)

        threading.Thread(target=work, daemon=True).start()

    def OnFound(self, index, candidates, errors):
        # each cover once; a single track's first one chosen
        if not self or self.closing:
            return
        seen = set()
        found = []
        for v in candidates:
            if v['image'] and v['image'] not in seen:
                seen.add(v['image'])
                found.append(v)
        track = self.tracks[index]
        track['candidates'], track['errors'] = found, errors
        if not self.multi and found and track['chosen'] is None:
            track['chosen'] = found[0]
        if index == self.index:
            self.ShowTrack(index)

    def SetNote(self, errors):
        # the services' errors a row under the cards, alone, when there are
        text = ' / '.join(errors)
        if text and self.Note is None:
            self.Note = StaticText(self, label='', size=(-1, 18))
        if self.Note is not None:
            # & as itself, not a mnemonic
            self.Note.SetLabel(text.replace('&', '&&'))
            self.Note.Show(bool(text))
        self.PlaceParts()

    def UpdateTitle(self):
        # the track named in the title, its count and chosen ones
        track = self.tracks[self.index]
        title = f'Look Up Cover: {track["label"]}'
        if track['candidates'] is not None:
            title += f' ({len(track["candidates"])} found)'
        if self.multi:
            chosen = sum(1 for v in self.tracks if v['chosen'] is not None)
            title += f'  |  Track {self.index + 1} of {len(self.tracks)}, {chosen} chosen'
        self.SetTitle(title)

    def UpdateApply(self):
        # on when a cover is chosen and every chosen one has come
        chosen = [v['chosen']['image'] for v in self.tracks if v['chosen'] is not None]
        self.ApplyButton.Enable(bool(chosen) and all(url in self.data for url in chosen))

    # cards

    def SetSame(self, value):
        # on: the shown track's chosen cover for them all (or the next one chosen)
        self.same = value
        chosen = self.tracks[self.index]['chosen']
        if value and chosen is not None:
            for track in self.tracks:
                track['chosen'] = chosen
        self.ShowTrack(self.index)

    def OnCardSelected(self, k):
        if self.same:
            for track in self.tracks:
                track['chosen'] = self.candidates[k]
        self.tracks[self.index]['chosen'] = self.candidates[k]
        self.ShowDetails()
        self.UpdateTitle()
        self.UpdateApply()
        self.EnsureFetching()

    def OnCardActivated(self, k):
        # a single track's (or one for them all): written at once; a page's: on to the next
        if self.multi and not self.same and self.index < len(self.tracks) - 1:
            self.MoveTrack(1)
        else:
            self.OnApply(None)

    def OnCardMenu(self, k):
        menu = wx.Menu()

        def add(name, action, enable=True):
            item = menu.Append(wx.ID_ANY, name)
            item.Enable(enable)
            menu.Bind(wx.EVT_MENU, lambda e: action(), item)

        add('Use for This Track', lambda: self.Cards.Select(k))
        if self.multi:
            add(f'Use for All {len(self.tracks)} Tracks', lambda: self.UseForAll(k))
            add('Clear Choice', self.ClearChoice, self.tracks[self.index]['chosen'] is not None)
        menu.AppendSeparator()
        url = self.candidates[k]['image']
        shown = self.GetOutput(url)[0] if url in self.data else None
        append_cover_items(menu, shown, url in self.edits,
                           lambda name: self.DoCoverItem(name, k))
        menu.AppendSeparator()
        add('Open Source Page', lambda: webbrowser.open(self.candidates[k]['url']),
            bool(self.candidates[k]['url']))
        uikit.mark_menu_checks(menu)
        self.Cards.PopupMenu(menu)
        menu.Destroy()

    def UseForAll(self, k):
        # one cover for every track
        for track in self.tracks:
            track['chosen'] = self.candidates[k]
        self.ShowTrack(self.index)

    def ClearChoice(self):
        self.tracks[self.index]['chosen'] = None
        self.ShowTrack(self.index)

    def DoCoverItem(self, name, k):
        # on the card's picture as it will be written
        url = self.candidates[k]['image']
        if url not in self.data:
            return
        if name == 'Copy Cover':
            keep_copied_cover(self.GetOutput(url)[0], get_cover_label(self.candidates[k]))
            return
        if name == 'Undo Cover Change':
            self.KeepEdit(url, None)
            return
        # chosen for this track first
        if self.Cards.selected != k:
            self.Cards.Select(k)
        if name in COVER_PRESETS:
            edit = preset_cover(self.data[url], self.edits.get(url), COVER_PRESETS[name])
            if edit is not None:
                self.KeepEdit(url, edit)
        elif name == 'Edit Cover...':
            self.EditChosen()

    def OnPreviewMenu(self):
        chosen = self.tracks[self.index]['chosen']
        urls = [v['image'] for v in self.candidates]
        if chosen is not None and chosen['image'] in urls:
            self.OnCardMenu(urls.index(chosen['image']))

    def EditChosen(self):
        chosen = self.tracks[self.index]['chosen']
        if chosen is None or chosen['image'] not in self.data:
            return
        url = chosen['image']
        edit = pick_cover_edit(self, self.data[url], self.edits.get(url))
        if edit is not None:
            self.KeepEdit(url, edit)
        self.Cards.SetFocus()

    def KeepEdit(self, url, edit):
        if edit is None:
            self.edits.pop(url, None)
        else:
            self.edits[url] = edit
        self.outputs.pop(url, None)
        self.ShowDetails()
        self.Cards.Refresh(False)

    def ShowDetails(self):
        # the shown track's chosen cover: as it will be written, its release's fields
        chosen = self.tracks[self.index]['chosen']
        if chosen is None:
            self.PageButton.Disable()
            self.Details.loading = False
            self.Details.SetPreview(None)
            self.Details.SetFields((('Cover', 'None chosen' if self.multi else ''),))
            return
        v = chosen
        url = v['image']
        self.PageButton.Enable(bool(v['url']))
        cover = self.notes.get(url, 'Loading...')
        preview = None
        if url in self.data:
            data, size, changed = self.GetOutput(url)
            ground = wx.Colour(macroboxstyle.current().UI.RAISED_BG).Get()[:3]
            preview, _ = fit_picture(data, self.DETAILS - CoverDetails.GUTTER, ground)
            if size and changed:
                cover = f'{cover} to {format_picture_size(size)}'
        self.Details.loading = url not in self.notes
        self.Details.SetPreview(preview)
        self.Details.SetFields((
            ('Artist', v['artist']), ('Title', v['title']), ('Album', v['album']),
            ('Release', v['release']), ('Genre', v['genre']), ('Year', v['year']),
            ('Length', webinfo.format_duration(v['duration']) if v['duration'] else ''),
            ('Source', v['source']), ('Cover', cover)))

    def GetPicture(self, k):
        return self.pictures.get(self.candidates[k]['image'])

    def GetLines(self, k):
        v = self.candidates[k]
        first = ' - '.join(x for x in (v['artist'], v['album']) if x) or v['title']
        size = self.notes.get(v['image'], 'Loading...')
        second = '  '.join(x for x in (v['source'], str(v['year'] or ''), size) if x)
        return first, second

    # pictures

    def EnsureFetching(self):
        if not self.fetching and not self.closing:
            self.fetching = True
            threading.Thread(target=self.FetchCovers, daemon=True).start()

    def FetchCovers(self):
        # one at a time: the shown track's chosen one first, then the rest
        done = set()
        while not self.closing:
            chosen = self.tracks[self.index]['chosen']
            urls = ([chosen['image']] if chosen is not None else [])\
                + [v['image'] for v in list(self.candidates)]\
                + [v['chosen']['image'] for v in self.tracks if v['chosen'] is not None]
            todo = [url for url in urls if url not in done and url not in self.notes]
            if not todo:
                self.fetching = False
                return
            url = todo[0]
            done.add(url)
            try:
                data = webinfo.fetch_image(url)
            except Exception:
                data = None
            if self.closing:
                return
            wx.CallAfter(self.OnCoverLoaded, url, data)
        self.fetching = False

    def OnCoverLoaded(self, url, data):
        if not self or self.closing:
            return
        ground = wx.Colour(macroboxstyle.current().UI.RAISED_BG).Get()[:3]
        # larger than a card: the cards grow with the window
        picture, size = fit_image(data, CoverCards.CARD * 2, ground)
        if picture is not None:
            self.data[url] = data
            self.pictures[url] = picture
            self.notes[url] = format_picture_size(size)
        else:
            self.notes[url] = 'Failed'
        chosen = self.tracks[self.index]['chosen']
        if chosen is not None and chosen['image'] == url:
            self.ShowDetails()
        self.UpdateApply()
        self.Cards.Refresh(False)

    def IsLoading(self):
        chosen = [v['chosen']['image'] for v in self.tracks if v['chosen'] is not None]
        return self.Cards.searching or any(
            url not in self.notes for url in [v['image'] for v in self.candidates] + chosen)

    def OnSpin(self, event):
        # loading marks turn once a second, stop when all have come
        if not self or self.closing:
            return
        if not self.IsLoading():
            self.Spin.Stop()
        else:
            self.EnsureFetching()
        angle = (self.Cards.angle + math.pi * 2 / 30) % (math.pi * 2)
        self.Cards.angle = self.Details.angle = angle
        self.Cards.Refresh(False)
        if self.Details.loading:
            self.Details.Refresh(False)

    # layout and settings

    def OnSize(self, event):
        if getattr(self, 'built', False):
            self.PlaceParts()
            self.Refresh(False)
        if event is not None:
            event.Skip()

    def PlaceParts(self):
        # cards PAD in, details at their right, errors under, then the footer
        if not getattr(self, 'built', False):
            return
        width, height = self.GetClientSize()
        bottom = self.GetContentBottom()
        top = bottom - DIALOG_PAD
        if self.Note is not None and self.Note.IsShown():
            top -= DIALOG_ROW + DIALOG_GAP
            self.Note.SetRect((DIALOG_PAD, bottom - DIALOG_ROW + 3, width - DIALOG_PAD * 2, 18))
        dx = width - DIALOG_PAD - self.DETAILS
        self.Cards.SetRect((DIALOG_PAD, DIALOG_PAD, dx - DIALOG_PAD * 2, top))
        # details above the all-tracks check
        self.Details.SetRect((dx, DIALOG_PAD, self.DETAILS, top - DIALOG_ROW - DIALOG_GAP))
        for window, (x, y) in self.same_check:
            window.SetPosition((dx + x, DIALOG_PAD + top - DIALOG_ROW + 3 + y))
        top = self.PlaceButtons(right=self.GetButtons())
        for window, below in self.checks:
            window.SetPosition((window.GetPosition().x, top + below))
        # KEEP two PADs left of the buttons
        x = self.PageButton.GetPosition().x - DIALOG_PAD * 2 - self.keep_width
        for window, offset, below in self.keep_check:
            window.SetPosition((x + offset, top + below))

    def SetKeep(self, value):
        self.keep = value
        SetPreference('item_editor_keep_modified', value)

    def SetSquare(self, value):
        self.square = value
        SetPreference('cover_lookup_square', value)
        self.outputs.clear()
        self.ShowDetails()

    def GetOutput(self, url):
        # picture to write: (bytes, size, changed), cached
        if url in self.outputs:
            return self.outputs[url]
        data = self.data[url]
        edit = self.edits.get(url)
        changed = edit is not None
        if edit is not None:
            # edited by hand: the Square check left out
            edited = listimages.edit_cover(data, edit)
            data = data if edited is None else edited
        elif self.square and listimages.is_square(data) is False:
            data = listimages.square_cover(data)
            changed = True
        try:
            size = wx.Image(io.BytesIO(data)).GetSize()
        except Exception:
            size = None
        self.outputs[url] = (data, size, changed)
        return self.outputs[url]

    # closed

    def OnOpenPage(self, event):
        chosen = self.tracks[self.index]['chosen']
        if chosen is not None and chosen['url']:
            webbrowser.open(chosen['url'])

    def OnApply(self, event):
        # each track's chosen cover, as it will be written: (path, mdx, bytes)
        results = [(v['path'], v['mdx'], self.GetOutput(v['chosen']['image'])[0])
                   for v in self.tracks
                   if v['chosen'] is not None and v['chosen']['image'] in self.data]
        if not results:
            return
        self.results = results
        self.closing = True
        self.Spin.Stop()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.closing = True
        self.Spin.Stop()
        self.EndModal(wx.ID_CANCEL)

    def OnClose(self, event):
        self.closing = True
        self.Spin.Stop()
        self.EndModal(wx.ID_CANCEL)


def look_up_cover(listbox):
    '''look up the selected tracks' covers, the focused one first'''
    items = sorted(listbox.GetSelectedItems())
    if not items:
        return
    focused = listbox.GetFocusedItem()
    value = listbox.GetItemValueByColumnKey
    # the rows' files now (the list may be sorted or changed while it looks)
    tracks = [dict(path=value(k, 'path'), mdx=value(k, 'mdx'),
                   artist=str(value(k, 'artist') or ''), title=str(value(k, 'title') or ''),
                   label=str(value(k, 'filename') or os.path.basename(value(k, 'path'))))
              for k in items]
    look_up_cover_for(listbox, tracks, items.index(focused) if focused in items else 0)


def look_up_cover_for(listbox, tracks, start=0, use=None, parent=None):
    '''look up covers for tracks, chosen from cards and written (or handed to use)'''
    frame = wx.GetTopLevelParent(listbox) if parent is None else parent
    # iTunes with no key; Discogs and Last.fm with theirs
    keys = dict(zip(webinfo.PREFERENCE_KEYS, GetPreferences(webinfo.PREFERENCE_KEYS)))
    # the window first, its cards when found
    dialog = CoverLookUpBox(frame, tracks, keys, start)
    answer = dialog.ShowModal()
    SetPreference('cover_lookup_size', tuple(dialog.GetClientSize()))
    results, keep = dialog.results, dialog.keep
    dialog.Destroy()
    if answer == wx.ID_OK and len(results) > 0 and use is not None:
        use(results)
    elif answer == wx.ID_OK and results and listbox:
        write_covers(listbox, results, keep)


def write_covers(listbox, results, keep=None):
    # write each (path, mdx, picture); the playing song paused, dates kept
    playbox = listbox.parent.PlayBox
    images = getattr(listbox.List, 'images', None)
    if keep is None:
        keep = GetPreference('item_editor_keep_modified') is not False
    failed = []
    for path, mdx, data in results:
        playing = playbox.IsPlaying() and path == playbox.GetPlayingItemInfo('path')
        if playing:
            playbox.OnPause()
        try:
            before = os.stat(path)
            with mfeats.tags_written(path):
                listimages.write_cover(path, data)
                if keep:
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        except Exception as error:
            failed.append(f'{os.path.basename(path)}: {error}')
        if playing:
            playbox.OnResume()
        if images is not None:
            images.Forget(mdx, 'cover')
        if playbox.cue.path == path:
            playbox.Apic.HandleApicChange(forced=True)
    listbox.List.reInitBuffer = True
    if failed:
        show_notice(wx.GetTopLevelParent(listbox), 'Cover',
                    'The cover was not saved.\n' + '\n'.join(failed[:5]))
    else:
        done = 'the track' if len(results) == 1 else f'{len(results)} tracks'
        radio.tell(listbox.parent, f'Cover written to {done}')


# the cover kept by Copy Cover for Paste Cover
copied_cover = dict(data=None, label='')


def read_cover_of(path):
    # the song's cover bytes, None without one or unread
    if path is None or path == '' or audio.is_stream_path(path):
        return None
    try:
        return listimages.read_cover(path)
    except (OSError, mutagen.MutagenError):
        return None


def copy_cover(mainpanel, path, data=None):
    if data is None:
        data = read_cover_of(path)
    if data is None or len(data) == 0:
        radio.tell(mainpanel, 'This track has no cover', warn=True)
        return
    keep_copied_cover(data, os.path.basename(path), mainpanel)


def keep_copied_cover(data, label, mainpanel=None):
    copied_cover.update(data=data, label=label)
    # told in the player's status line, from any window
    if mainpanel is None:
        mainpanel = getattr(wx.GetApp().GetTopWindow(), 'MainPanel', None)
    if mainpanel is not None:
        radio.tell(mainpanel, f'Cover copied: {label}')


def get_cover_label(candidate):
    # a looked up cover's name for Paste Cover's question
    words = [v for v in (candidate['artist'], candidate['album'] or candidate['title']) if v]
    return ' - '.join(words) if len(words) > 0 else 'Look Up'


def has_copied_cover():
    return copied_cover['data'] is not None


class PasteCoverBox(ConfirmDialogBox):

    # the copied cover over the tracks' own, or not
    def __init__(self, parent, count, answer):
        ConfirmDialogBox.__init__(self, parent)
        self.answer = answer
        self.SetTitle('Paste Cover')
        self.ApplyButton.SetLabelText('Paste')
        self.Message.Hide()
        tracks = 'this track' if count == 1 else f'{int(count)} tracks'
        self.Text = wx.StaticText(self, label=f'Put the cover of {copied_cover["label"]} in '
                                  f'{tracks}?\nTheir front covers are replaced.',
                                  style=wx.ALIGN_CENTER_HORIZONTAL | wx.ST_NO_AUTORESIZE)
        self.Text.SetForegroundColour(macroboxstyle.current().UI.TEXT)
        self.Text.SetFont(uikit.get_font(uikit.BODY))
        self.Text.Wrap(340 - DIALOG_PAD * 2)
        self.text_height = max(40, self.Text.GetBestSize().height)
        self.SetClientSize((340, DIALOG_PAD * 2 + self.text_height + self.GetFooterHeight()))
        self.OnSize(None)

    def OnSize(self, event):
        ConfirmDialogBox.OnSize(self, event)
        if getattr(self, 'Text', None) is not None:
            width, height = self.GetClientSize()
            self.Text.SetRect((DIALOG_PAD, DIALOG_PAD, width - DIALOG_PAD * 2, self.text_height))

    def OnApply(self, event):
        self.answer.append(True)
        self.OnClose(event)


def paste_cover(listbox, tracks):
    '''the copied cover written to tracks, each (path, mdx), asked first'''
    data = copied_cover['data']
    tracks = [(path, mdx) for path, mdx in tracks
              if path != '' and audio.is_stream_path(path) is False]
    if data is None or len(tracks) == 0:
        return
    answer = []
    # centred over the player by DialogBox.ShowModal
    PasteCoverBox(wx.GetTopLevelParent(listbox), len(tracks), answer).ShowModal()
    if answer != []:
        write_covers(listbox, [(path, mdx, data) for path, mdx in tracks])


class ListBoxPopupHeader(wx.Menu):

    # header menu: shown columns and widths, synced to every tab

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

    def OnShow(self, index, show):
        listbox = self.parent.parent
        shown = [v for v in listbox.GetColumns() if v.show is True and v.private is False]
        if len(shown) == 1 and show is False:
            return
        listbox.SetColumn(index, show=show)
        if show and listbox.GetColumns()[index].key == 'comment':
            fill_comments(listbox)
        listbox.SyncColumnsToAll()
        # the file name's column gives the new one its room (or takes it back)
        self.parent.SetAutoColumnWidth()
        self.parent.DirectDraw()
        listbox.reInitBuffer = True

    def OnFit(self, event):
        # every shown column fitted to its widest text
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
        listbox.SyncColumnsToAll()
        # and the file name's over the room left, as when the list is resized
        self.parent.SetAutoColumnWidth()
        self.parent.DirectDraw()
        listbox.reInitBuffer = True


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
            field1 = eval(f'{parents}.GetSelectedItemsKeyValue(field1)[0]')
        if field2 != '':
            # exec('field2 = %s.GetSelectedItemsKeyValue(field2)[0]' % (parents))
            field2 = eval(f'{parents}.GetSelectedItemsKeyValue(field2)[0]')
        fields = '+'.join((field1, field2)).strip('+')
        if len(fields) < 3:
            # exec('filename = %s.GetSelectedItemsKeyValue("filename")[0]' % (parents))
            filename = eval(f'{parents}.GetSelectedItemsKeyValue("filename")[0]')
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
        # radio stations: play and delete only
        listbox = self.parent.parent
        rows = listbox.innerList[listbox.selectedList].items
        pathIdx = listbox.GetColumnKeyToIdx('path')
        selected = listbox.GetSelectedItems()
        stations = bool(selected) and all(
            audio.is_stream_path(rows[i][pathIdx]) for i in selected if i < len(rows))

        # grouped: play and keep | tags and analysis | similar | file | remove
        title = listbox.innerList[listbox.selectedList].title

        def add(idx, name):
            self.Append(wx.MenuItem(self, idx, name, wx.EmptyString, wx.ITEM_NORMAL))
            self.Bind(wx.EVT_MENU, self.OnCheck, self.MenuItems[len(self.MenuItems) - 1])

        def add_item(name, handler):
            item = wx.MenuItem(self, wx.ID_ANY, name, wx.EmptyString, wx.ITEM_NORMAL)
            self.Append(item)
            self.Bind(wx.EVT_MENU, handler, item)

        if single:
            add(1, 'Play')
        if not stations:
            # star or unstar a song in the favorite tracks
            paths = self.GetSelectedPaths()
            starred = set(library.get_favorite_tracks())
            add_item('Remove from Favorite tracks' if paths and all(v in starred for v in paths)
                     else 'Add to Favorite tracks', self.OnToggleFavoriteTracks)
        if stations and title != radio.RADIO_TITLE:
            # kept in the radio's favorites
            add_item('Add to Favorite stations', self.OnAddFavorites)
        if title == radio.RADIO_TITLE:
            add_item('Add Station URL...', self.OnAddStationURL)

        if not stations:
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

            self.AppendSeparator()
            # Edit Track Info, as the player's header names it
            add(2, 'Edit Track Info...')
            # cover only, chosen from cards
            add_item('Look Up Cover...', lambda e: look_up_cover(self.parent.parent))
            # one song's cover kept, then put in the selected songs
            if single:
                add_item('Copy Cover', self.OnCopyCover)
                self.MenuItems[-1].Enable(read_cover_of(self.GetSelectedPaths()[0]) is not None)
            add_item('Paste Cover', self.OnPasteCover)
            self.MenuItems[-1].Enable(has_copied_cover())
            add(4, 'Analyze')
            self.Append(8, 'Convert Tempo Range', self.itemConvertTempoRange)
            self.Append(9, 'Convert Key Format', self.itemConvertKeyFormat)
            if single:
                self.AppendSeparator()
                add(6, 'Find Similar')
                # Find in Library preset to this song's tempo and key
                add(7, 'Find in Library...')
                self.AppendSeparator()
                add(5, 'Open Containing Folder')

        self.AppendSeparator()
        # rows removed from the list, files kept
        add(3, 'Remove from List')

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

    def OnCopyCover(self, event):
        paths = self.GetSelectedPaths()
        if len(paths) == 1:
            copy_cover(self.parent.parent.parent, paths[0])

    def OnPasteCover(self, event):
        listbox = self.parent.parent
        value = listbox.GetItemValueByColumnKey
        tracks = [(value(i, 'path'), value(i, 'mdx')) for i in sorted(listbox.GetSelectedItems())]
        # after the menu: the question is modal
        wx.CallAfter(paste_cover, listbox, tracks)

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
        elif event.Id == 7:
            self.FindInLibrary()
        # elif event.Id == 7-diff:
        #   self.AnalyzeSelectedItems()
        # elif event.Id == 8-diff:
        #   self.AnalyzeSelectedItems(forced=True)
        # elif event.Id == 8-diff:
        #   self.CheckItemsConsistency()

    def FindInLibrary(self):
        listbox = self.parent.parent
        selected = listbox.GetSelectedItems()
        if selected == []:
            return
        song = (listbox.GetItemValueByColumnKey(selected[0], 'tempo'),
                listbox.GetItemValueByColumnKey(selected[0], 'key'))
        wx.GetTopLevelParent(listbox).OnFindInLibrary(None, song=song)

    def FindSimilar(self):
        listbox = self.parent.parent
        selected = listbox.GetSelectedItems()
        if selected == []:
            return
        inner = listbox.innerList[listbox.selectedList]
        find_similar(listbox, listbox.GetItemValueByColumnKey(selected[0], 'path'),
                     dict(zip([v.key for v in inner.columns], inner.items[selected[0]])))

    def EditSelectedItem(self):
        self.parent.parent.parent.DialogBox = ItemEditBox(self.parent)
        x, y, w, h = self.parent.parent.parent.parent.GetRect()
        width, height = self.parent.parent.parent.DialogBox.GetSize()
        self.parent.parent.parent.DialogBox.SetRect(
            (x + (w - width) // 2, y + (h - height) // 2, width, height))
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
        folders.show_in_explorer(self.parent.parent.GetSelectedItemsKeyValue('path')[0])


class StatusBox(RectBox):

    # messages start at the left edge
    MESSAGE_LEFT_X = 8
    PROGRESS_WIDTH = 80

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.SetBackgroundColour(macroboxstyle.current().UI.BAR_BG)
        self.messages = (u'', u'')
        self.proc = 0
        # analysis run: most tracks waiting and how many are done
        self.batch = 0
        self.progress = None
        self.alarm = None
        self.alarm_color = None
        self.alarm_timer = 0
        # a folder being opened or read: (text, done, total)
        self.reading = None
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
        elif self.reading is not None:
            message_left = self.reading[0]
        else:
            message_left = f'Selected {selected} / {total} tracks {filtered}'
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
        return f'Analyzing {current} of {batch}  \u00b7  {core} processes'

    def SetRectDraw(self, dc):
        message_left, message_right = self.messages
        w, h = self.parent.GetSize()
        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.NORMAL)
        font.SetPixelSize((6, 11))
        font.SetFaceName(FONT_ITEM)
        dc.SetFont(font)
        tw, th = dc.GetTextExtent(message_right)
        # 10 rows over the capitals and 9 under
        ty = 7
        xys = ((self.MESSAGE_LEFT_X, ty), (w - tw - 10, ty),)
        if self.progress is not None:
            # progress bar before its text, placed by the run's longest text
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
        # info blue, warning orange (not red: red-green blindness), busy blue
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
        if self.reading is not None and self.reading[2] and self.alarm is None:
            # the left text's own bar, as the analysis' on the right
            bx = self.MESSAGE_LEFT_X + dc.GetTextExtent(message_left)[0] + 10
            by = ty + th // 2 - 2
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(tokens.CONTROL_BG))
            dc.DrawRectangle(bx, by, self.PROGRESS_WIDTH, 4)
            dc.SetBrush(wx.Brush(tokens.ACCENT))
            done = self.reading[1] / self.reading[2]
            dc.DrawRectangle(bx, by, max(int(self.PROGRESS_WIDTH * done), 2), 4)

    def OnSize(self, event=None):
        self.DirectDraw()
