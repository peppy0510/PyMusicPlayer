# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import ctypes
import folders
import glob
import images
import library
import listimages
import macroboxstyle
import math
import mfeats
import os
import radio
import stat
import sys
import threading
import time
import uikit
import webbrowser
import wx

from coverbox import copy_cover
from coverbox import draw_spinner
from coverbox import has_copied_cover
from coverbox import look_up_cover
from coverbox import paste_cover
from coverbox import read_cover_of
from itemeditbox import ItemEditBox
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
from macroboxlib import NativeComboBox
from macroboxlib import DialogBox
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
from macroboxlib import ItemTextEdit
from macroboxlib import ListBoxColumn
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
