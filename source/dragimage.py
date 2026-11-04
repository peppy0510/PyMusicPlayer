# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import ctypes
import ctypes.wintypes
import io
import macroboxstyle
import numpy
import os
import uikit
import wx

from PIL import Image
from PIL import ImageOps
from utilities import get_user_docapp_path


# drag picture: covers stacked as cards, how many on a badge
# its own layered window the pointer and the drop go through (WS_EX_TRANSPARENT)
CARD = 64
STEP = 5
CARDS_MOST = 3
# room for the shadow and the badge
MARGIN = 10
SHADOW = 2
# a little see-through
ALPHA = 225
# above the pointer's tip: the row under it left in sight
OVER_POINTER = 8
PLAYLIST_TYPES = ('m3u', 'm3u8', 'pls')

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
HANDLE = ctypes.c_void_p
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
HWND_TOPMOST = HANDLE(-1)
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
ULW_ALPHA = 2


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [('BlendOp', ctypes.c_ubyte), ('BlendFlags', ctypes.c_ubyte),
                ('SourceConstantAlpha', ctypes.c_ubyte), ('AlphaFormat', ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', ctypes.wintypes.DWORD), ('biWidth', ctypes.wintypes.LONG),
                ('biHeight', ctypes.wintypes.LONG), ('biPlanes', ctypes.wintypes.WORD),
                ('biBitCount', ctypes.wintypes.WORD), ('biCompression', ctypes.wintypes.DWORD),
                ('biSizeImage', ctypes.wintypes.DWORD), ('biXPelsPerMeter', ctypes.wintypes.LONG),
                ('biYPelsPerMeter', ctypes.wintypes.LONG), ('biClrUsed', ctypes.wintypes.DWORD),
                ('biClrImportant', ctypes.wintypes.DWORD)]


# without argtypes 64-bit handles are cut to 32 bits, the call failing silently
user32.GetDC.restype = HANDLE
user32.GetDC.argtypes = [HANDLE]
user32.ReleaseDC.argtypes = [HANDLE, HANDLE]
user32.GetWindowLongW.argtypes = [HANDLE, ctypes.c_int]
user32.SetWindowLongW.argtypes = [HANDLE, ctypes.c_int, ctypes.c_long]
user32.SetWindowPos.argtypes = [HANDLE, HANDLE, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_uint]
user32.UpdateLayeredWindow.argtypes = [
    HANDLE, HANDLE, ctypes.POINTER(ctypes.wintypes.POINT),
    ctypes.POINTER(ctypes.wintypes.SIZE), HANDLE, ctypes.POINTER(ctypes.wintypes.POINT),
    ctypes.wintypes.DWORD, ctypes.POINTER(BLENDFUNCTION), ctypes.wintypes.DWORD]
gdi32.CreateCompatibleDC.restype = HANDLE
gdi32.CreateCompatibleDC.argtypes = [HANDLE]
gdi32.CreateDIBSection.restype = HANDLE
gdi32.CreateDIBSection.argtypes = [HANDLE, ctypes.POINTER(BITMAPINFOHEADER), ctypes.c_uint,
                                   ctypes.POINTER(ctypes.c_void_p), HANDLE,
                                   ctypes.wintypes.DWORD]
gdi32.SelectObject.restype = HANDLE
gdi32.SelectObject.argtypes = [HANDLE, HANDLE]
gdi32.DeleteObject.argtypes = [HANDLE]
gdi32.DeleteDC.argtypes = [HANDLE]


def get_kind(path):
    if audio.is_stream_path(path):
        return 'station'
    if os.path.isdir(path):
        return 'folder'
    if os.path.splitext(path)[1][1:].lower() in PLAYLIST_TYPES:
        return 'playlist'
    return 'song'


def read_picture(path):
    '''a song's cover as a CARD square, or None'''
    from listimages import read_cover
    data = None
    try:
        data = read_cover(path)
    except Exception:
        data = None
    if data is None:
        mdx = audio.makemdx(path)
        thumbnail = os.path.join(get_user_docapp_path(), 'covers', f'{mdx}.png')
        if mdx and os.path.isfile(thumbnail) and os.path.getsize(thumbnail) > 0:
            with open(thumbnail, 'rb') as f:
                data = f.read()
    if data is None:
        return None
    try:
        picture = Image.open(io.BytesIO(data)).convert('RGB')
    except Exception:
        return None
    picture = ImageOps.fit(picture, (CARD, CARD), Image.LANCZOS)
    return wx.Bitmap.FromBuffer(CARD, CARD, picture.tobytes())


def draw_card(gc, kind, x, y):
    '''a card without a cover'''
    st = macroboxstyle.current().PLAYBOX
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(st.CHIP_BG_COLOR))))
    gc.DrawRoundedRectangle(x, y, CARD, CARD, uikit.RADIUS)
    cx, cy = x + CARD / 2.0, y + CARD / 2.0
    if kind in ('song', 'station'):
        r = CARD * 0.3
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(st.APIC_PN_COLOR))))
        gc.DrawEllipse(cx - r, cy - r, r * 2, r * 2)
        return
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(macroboxstyle.current().UI.TEXT_FAINT))
                           .Width(2)))
    gc.SetBrush(wx.NullGraphicsBrush)
    if kind == 'folder':
        path = gc.CreatePath()
        path.MoveToPoint(cx - 15, cy - 10)
        for px, py in ((-5, -10), (-2, -7), (15, -7), (15, 11), (-15, 11)):
            path.AddLineToPoint(cx + px, cy + py)
        path.CloseSubpath()
        gc.StrokePath(path)
    else:
        for k in (-8, 0, 8):
            gc.StrokeLine(cx - 13, cy + k, cx + 13, cy + k)


def make_picture(paths):
    '''the stack's picture (a wx.Image with alpha) and the front card's middle on it'''
    paths = list(paths)
    shown = paths[:CARDS_MOST]
    depth = (len(shown) - 1) * STEP
    width = MARGIN + CARD + depth + MARGIN
    height = MARGIN + depth + CARD + MARGIN
    image = wx.Image(width, height)
    image.SetData(bytes(width * height * 3))
    image.SetAlpha(bytes(width * height))
    gc = wx.GraphicsContext.Create(image)
    tokens = macroboxstyle.current().UI
    # from the last one behind to the front one
    front = (MARGIN, MARGIN + depth)
    for k in range(len(shown) - 1, -1, -1):
        x, y = front[0] + k * STEP, front[1] - k * STEP
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(0, 0, 0, 90))))
        gc.DrawRoundedRectangle(x + 1, y + SHADOW, CARD, CARD, 4)
        kind = get_kind(shown[k])
        picture = read_picture(shown[k]) if kind == 'song' else None
        if picture is not None:
            gc.DrawBitmap(picture, x, y, CARD, CARD)
        else:
            draw_card(gc, kind, x, y)
        if k > 0:
            # the ones behind dimmed
            gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(0, 0, 0, 70))))
            gc.SetPen(wx.NullGraphicsPen)
            gc.DrawRectangle(x, y, CARD, CARD)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(255, 255, 255, 70)).Width(1)))
        gc.SetBrush(wx.NullGraphicsBrush)
        gc.DrawRectangle(x + 0.5, y + 0.5, CARD - 1, CARD - 1)
    if len(paths) > 1:
        # badge over the front card's top right corner, digits centered by ink
        font = uikit.get_font(11, bold=True)
        text = f'{len(paths)}'
        offset, ink_width = uikit.get_text_ink(font, text)
        ink = uikit.get_caps_ink(font)[1]
        bh = ink + 8
        bw = max(bh, ink_width + 12)
        bx = min(front[0] + CARD - bw // 2, width - bw - 1)
        by = max(front[1] - bh // 2, 1)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(tokens.ACCENT))))
        gc.DrawRoundedRectangle(bx, by, bw, bh, bh / 2.0)
        gc.SetFont(font, wx.Colour(255, 255, 255))
        gc.DrawText(text, bx + (bw - ink_width) / 2.0 - offset, uikit.get_caps_top(font, by, bh))
    del gc
    return image, (front[0] + CARD // 2, front[1] + CARD)


class DragImage():

    '''the dragged paths' picture following the pointer, till Close'''

    def __init__(self, paths):
        image, self.anchor = make_picture(paths)
        self.size = (image.GetWidth(), image.GetHeight())
        self.frame = wx.Frame(None, size=self.size, style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP
                              | wx.BORDER_NONE | wx.FRAME_TOOL_WINDOW)
        self.hwnd = HANDLE(self.frame.GetHandle())
        style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                              | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        self.Paint(image)
        self.Follow()
        self.frame.ShowWithoutActivating()

    def Paint(self, image):
        # BGRA, premultiplied by alpha
        width, height = self.size
        rgb = numpy.frombuffer(bytes(image.GetData()), dtype=numpy.uint8)
        rgb = rgb.reshape(height, width, 3).astype(numpy.uint16)
        alpha = numpy.frombuffer(bytes(image.GetAlpha()), dtype=numpy.uint8)
        alpha = alpha.reshape(height, width)
        bgra = numpy.empty((height, width, 4), dtype=numpy.uint8)
        for k in range(3):
            bgra[:, :, 2 - k] = (rgb[:, :, k] * alpha // 255).astype(numpy.uint8)
        bgra[:, :, 3] = alpha
        screen = user32.GetDC(None)
        memory = gdi32.CreateCompatibleDC(screen)
        info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0,
                                0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(memory, ctypes.byref(info), 0, ctypes.byref(bits),
                                        None, 0)
        try:
            ctypes.memmove(bits, bgra.tobytes(), width * height * 4)
            old = gdi32.SelectObject(memory, bitmap)
            size = ctypes.wintypes.SIZE(width, height)
            source = ctypes.wintypes.POINT(0, 0)
            blend = BLENDFUNCTION(0, 0, ALPHA, 1)
            x, y = self.GetPlace()
            place = ctypes.wintypes.POINT(x, y)
            user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(place), ctypes.byref(size),
                                       memory, ctypes.byref(source), 0, ctypes.byref(blend),
                                       ULW_ALPHA)
            gdi32.SelectObject(memory, old)
        finally:
            gdi32.DeleteObject(bitmap)
            gdi32.DeleteDC(memory)
            user32.ReleaseDC(None, screen)

    def GetPlace(self):
        # the front card's middle over the pointer
        x, y = wx.GetMousePosition()
        return x - self.anchor[0], y - self.anchor[1] - OVER_POINTER

    def Follow(self):
        x, y = self.GetPlace()
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)

    def Close(self):
        if self.frame:
            self.frame.Destroy()


class DragSource(wx.DropSource):

    '''the drag's source moving its picture with the pointer (asked at every move)'''

    def __init__(self, image):
        wx.DropSource.__init__(self, None)
        self.image = image

    def GiveFeedback(self, effect):
        if self.image is not None:
            self.image.Follow()
        # the system's pointers kept
        return False
