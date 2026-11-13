# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import images
import io
import listimages
import macroboxstyle
import math
import mfeats
import mutagen
import os
import radio
import threading
import uikit
import webbrowser
import webinfo
import wx

from macroboxlib import Button
from macroboxlib import ConfirmDialogBox
from macroboxlib import DialogBox
from macroboxlib import DIALOG_BUTTON_HEIGHT
from macroboxlib import DIALOG_GAP
from macroboxlib import DIALOG_PAD
from macroboxlib import DIALOG_ROW
from macroboxlib import make_check
from macroboxlib import GetPreference
from macroboxlib import GetPreferences
from macroboxlib import SetPreference
from macroboxlib import StaticText
from macroboxlib import TextCtrl


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
    # iTunes and NetEase with no key; Discogs and Last.fm with theirs
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
