# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import ctypes
import functools
import macroboxstyle
import math
import wx


# one control look: rounded face, icon or label, state by face
RADIUS = 3
# level meter look: 1 px segments 2 apart; blue, orange, red-orange
METER_SEGMENT = 1
METER_GAP = 2
METER_BAR = 6
METER_TONES = ((-3.0, '#ff8e52'), (-9.0, '#ffc47a'), (None, '#d2e6ff'))
METER_DIM = 0.84
METER_STRIPS = {}
FONT_FACE = 'Segoe UI'
# type steps in pixels: title, body, readout, label; MICRO for graph scales
TITLE = 16
BODY = 12
READOUT = 11
LABEL = 10
MICRO = 9


def ui():
    return macroboxstyle.current().UI


# Windows draws its own check in the system's blue
CHECK_MARKS = {}


def get_check_mark():
    accent = tuple(colour(ui().ACCENT).Get(False))
    try:
        size = ctypes.windll.user32.GetSystemMetrics(71) or 15
    except Exception:
        size = 15
    key = (accent, size)
    if key not in CHECK_MARKS:
        image = wx.Image(size, size)
        image.InitAlpha()
        image.SetAlpha(bytes(size * size))
        bitmap = wx.Bitmap(image, 32)
        dc = wx.MemoryDC(bitmap)
        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(*accent)).Width(max(1.6, size / 8.0))
                               .Cap(wx.CAP_ROUND).Join(wx.JOIN_ROUND)))
        # at the mark's right: Windows keeps a fixed gap after the mark
        path = gc.CreatePath()
        path.MoveToPoint(size * 0.38, size * 0.52)
        path.AddLineToPoint(size * 0.58, size * 0.72)
        path.AddLineToPoint(size * 0.91, size * 0.30)
        gc.StrokePath(path)
        del gc
        dc.SelectObject(wx.NullBitmap)
        CHECK_MARKS[key] = bitmap
    return CHECK_MARKS[key]


def mark_menu_checks(menu):
    mark = get_check_mark()
    for item in menu.GetMenuItems():
        if item.GetSubMenu() is not None:
            mark_menu_checks(item.GetSubMenu())
        elif item.GetKind() == wx.ITEM_CHECK:
            item.SetBitmaps(mark, wx.NullBitmap)


def get_style_version():
    # style classes stay the same objects when the accent changes
    return macroboxstyle.VERSION


def colour(value):
    return wx.Colour(*value) if isinstance(value, (tuple, list)) else wx.Colour(value)


# cached per size and weight: GDI+ makes a new one at each SetFont
@functools.lru_cache(maxsize=64)
def get_font(pixels, bold=False):
    font = wx.Font(wx.Size(0, pixels), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                   wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL, faceName=FONT_FACE)
    return font


# renderer fonts cached by font and colour: gc.SetFont makes one per call
GRAPHICS_FONTS = {}


def set_font(gc, font, ink):
    ink = wx.Colour(ink)
    key = (font.GetNativeFontInfoDesc(), ink.GetRGBA())
    made = GRAPHICS_FONTS.get(key)
    if made is None:
        made = GRAPHICS_FONTS[key] = gc.CreateFont(font, ink)
    gc.SetFont(made)


# capitals' ink (top offset, height), cached per font
CAPS_INK = {}


def get_caps_ink(font):
    # draw a capital H, find its lit rows
    key = (font.GetPixelSize().height, font.GetWeight(), font.GetFaceName())
    if key in CAPS_INK:
        return CAPS_INK[key]
    size = font.GetPixelSize().height * 2 + 4
    bitmap = wx.Bitmap(size, size)
    dc = wx.MemoryDC(bitmap)
    dc.SetBackground(wx.Brush(wx.BLACK))
    dc.Clear()
    gc = wx.GraphicsContext.Create(dc)
    gc.SetFont(font, wx.WHITE)
    gc.DrawText('H', 2, 0)
    del gc
    dc.SelectObject(wx.NullBitmap)
    image = bitmap.ConvertToImage()
    rows = [y for y in range(size) if any(image.GetRed(x, y) > 128 for x in range(size))]
    CAPS_INK[key] = (rows[0], rows[-1] - rows[0] + 1) if rows else (0, size // 2)
    return CAPS_INK[key]


# text ink across (offset, width), cached per font and text
TEXT_INK = {}
TEXT_INK_MOST = 500


def get_text_ink(font, text):
    # lit columns: side bearings keep digits off their middle
    key = (font.GetPixelSize().height, font.GetWeight(), font.GetFaceName(), text)
    if key in TEXT_INK:
        return TEXT_INK[key]
    height = font.GetPixelSize().height * 2 + 4
    width = height * (len(text) + 1)
    bitmap = wx.Bitmap(width, height)
    dc = wx.MemoryDC(bitmap)
    dc.SetBackground(wx.Brush(wx.BLACK))
    dc.Clear()
    gc = wx.GraphicsContext.Create(dc)
    gc.SetFont(font, wx.WHITE)
    gc.DrawText(text, 2, 0)
    del gc
    dc.SelectObject(wx.NullBitmap)
    image = bitmap.ConvertToImage()
    cols = [x for x in range(width) if any(image.GetRed(x, y) > 128 for y in range(height))]
    if len(TEXT_INK) >= TEXT_INK_MOST:
        TEXT_INK.clear()
    TEXT_INK[key] = (cols[0] - 2, cols[-1] - cols[0] + 1) if cols else (0, 0)
    return TEXT_INK[key]


def get_caps_top(font, top, height):
    # y for capitals centred on the box, not the text box
    offset, ink = get_caps_ink(font)
    return top + (height - ink) / 2.0 - offset


def get_face(on=False, down=False, hover=False, warn=False, disabled=False):
    # (face, ink) for a state; disabled: flat, faint label
    tokens = ui()
    if disabled:
        return colour(tokens.CONTROL_BG), colour(tokens.BAR_TEXT_DIM)
    if warn:
        return colour(tokens.WARN), colour(tokens.WARN_FG)
    if on:
        # lit, a shade lighter on hover
        face = colour(tokens.ACCENT)
        if hover and not down:
            face = mix(face, (255, 255, 255), 0.14)
        return face, colour(tokens.ACCENT_FG)
    if down:
        return colour(tokens.CONTROL_DOWN), colour(tokens.BAR_TEXT)
    if hover:
        return colour(tokens.CONTROL_HOVER), colour(tokens.BAR_TEXT)
    return colour(tokens.CONTROL_BG), colour(tokens.CONTROL_FG)


# button mark: gap, stroke and size against the capitals
MARK_GAP = 4
MARK_WEIGHT = 1.6
MARK_SCALE = 0.75


def draw_button(dc, rect, label=None, icon=None, on=False, down=False, hover=False,
                warn=False, font=None, disabled=False, corners='all', mark=None):
    # corners: 'left'/'right' joined to a neighbour, 'none' between two
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    if disabled:
        on = down = hover = warn = False
    face, ink = get_face(on, down, hover, warn, disabled)
    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        return
    gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
    pressed = down
    # unlit key's edge: a darkened accent edge reads as face
    seat = colour(ui().CONTROL_BG) if on or warn else None
    draw_face(gc, (x, y, w, h), face, pressed=pressed, flat=disabled, corners=corners, seat=seat)
    # pressed: ink a pixel down
    sink = 1 if pressed else 0
    if icon is not None:
        draw_icon(gc, icon, (x, y + sink, w, h), ink)
    if label:
        # one weight on and off: bold would shift the label
        font = font or get_font(10, bold=True)
        set_font(gc, font, ink)
        tw = gc.GetTextExtent(label)[0]
        # centre the capitals' ink, not the text box
        top = get_caps_top(font, y, h) + sink
        # mark: a drawn plus or minus, MARK_SCALE of the capitals
        size = round(get_caps_ink(font)[1] * MARK_SCALE) if mark else 0
        gap = MARK_GAP if mark else 0
        left = x + (w - tw - gap - size) / 2.0
        gc.DrawText(label, left, top)
        if mark:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(MARK_WEIGHT)
                                   .Cap(wx.CAP_BUTT)))
            mx, my = left + tw + gap, y + h / 2.0 + sink
            gc.StrokeLine(mx, my, mx + size, my)
            if mark == 'plus':
                gc.StrokeLine(mx + size / 2.0, my - size / 2.0, mx + size / 2.0, my + size / 2.0)


def mix(c, other, share):
    return wx.Colour(*[int(a + (b - a) * share) for a, b in zip(c.Get()[:3], other)])


def get_meter_tone(db):
    for least, tone in METER_TONES:
        if least is None or db >= least:
            return tone


def get_meter_strips(gc, width, height, ground, low=-48.0, high=0.0, tone=None):
    '''(unlit, lit) segment pictures, cached per size'''
    ground = tuple(colour(ground).Get()[:3])
    key = (width, height, ground, low, high, tone)
    if key not in METER_STRIPS:
        pitch = METER_SEGMENT + METER_GAP
        pictures = []
        for lit in (False, True):
            bitmap = wx.Bitmap(max(width, 1), max(height, 1))
            dc = wx.MemoryDC(bitmap)
            dc.SetBackground(wx.Brush(wx.Colour(*ground)))
            dc.Clear()
            dc.SetPen(wx.TRANSPARENT_PEN)
            for x in range(0, width, pitch):
                db = low + (high - low) * (x + METER_SEGMENT / 2.0) / max(width, 1)
                face = colour(tone or get_meter_tone(db))
                dc.SetBrush(wx.Brush(face if lit else mix(face, ground, METER_DIM)))
                dc.DrawRectangle(x, 0, METER_SEGMENT, height)
            dc.SelectObject(wx.NullBitmap)
            pictures.append(gc.CreateBitmap(bitmap))
        METER_STRIPS[key] = tuple(pictures)
    return METER_STRIPS[key]


def draw_meter(gc, x, y, width, height, share, ground, low=-48.0, high=0.0, tone=None,
               start=0.0, unlit=True):
    # lit to share on whole segments; start: lit from there
    x, y, width, height = int(x), int(y), int(width), int(height)
    faint, lit = get_meter_strips(gc, width, height, ground, low, high, tone)
    if unlit:
        gc.DrawBitmap(faint, x, y, width, height)
    pitch = METER_SEGMENT + METER_GAP
    ends = [int(round(min(max(v, 0.0), 1.0) * width / pitch)) * pitch for v in (start, share)]
    left, right = min(ends), max(ends)
    if right > left:
        gc.Clip(x + left, y, right - left, height)
        gc.DrawBitmap(lit, x, y, width, height)
        gc.ResetClip()


def draw_face(gc, rect, face, pressed=False, flat=False, corners='all', seat=None):
    # hardware key's matte face, seated by a darker edge
    x, y, w, h = rect
    if pressed:
        face = mix(face, (0, 0, 0), 0.18)
    edge = mix(seat or face, (0, 0, 0), 0.3 if flat else 0.5)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(edge).Width(1)))
    gc.SetBrush(gc.CreateBrush(wx.Brush(face)))
    # the renderer draws lines half a pixel down and right: w - 1 wide
    if corners == 'all':
        gc.DrawRoundedRectangle(x, y, w - 1, h - 1, RADIUS)
        return
    # rounded on one side only, square where it joins
    left, right = corners == 'left', corners == 'right'
    x2, y2, r = x + w - 1, y + h - 1, RADIUS
    path = gc.CreatePath()
    path.MoveToPoint(x + (r if left else 0), y)
    if right:
        path.AddArcToPoint(x2, y, x2, y + r, r)
    else:
        path.AddLineToPoint(x2, y)
    if right:
        path.AddArcToPoint(x2, y2, x2 - r, y2, r)
    else:
        path.AddLineToPoint(x2, y2)
    if left:
        path.AddArcToPoint(x, y2, x, y2 - r, r)
    else:
        path.AddLineToPoint(x, y2)
    if left:
        path.AddArcToPoint(x, y, x + r, y, r)
    else:
        path.AddLineToPoint(x, y)
    path.CloseSubpath()
    gc.DrawPath(path)


def draw_icon(gc, icon, rect, ink):
    # play, pause, prev, next, loop: about half the face height
    x, y, w, h = rect
    size = min(w, h) * 0.5
    cx, cy = x + w / 2.0, y + h / 2.0
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(ink)))
    half = size / 2.0
    if icon == 'play':
        path = gc.CreatePath()
        path.MoveToPoint(cx - half * 0.8, cy - half)
        path.AddLineToPoint(cx + half, cy)
        path.AddLineToPoint(cx - half * 0.8, cy + half)
        path.CloseSubpath()
        gc.FillPath(path)
    elif icon == 'pause':
        bar = size * 0.32
        gc.DrawRectangle(cx - half * 0.85, cy - half, bar, size)
        gc.DrawRectangle(cx + half * 0.85 - bar, cy - half, bar, size)
    elif icon in ('down', 'up'):
        # chevron: down folded, up open; a menu's arrow
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.4)))
        gc.SetBrush(wx.NullGraphicsBrush)
        sign = 1 if icon == 'down' else -1
        path = gc.CreatePath()
        path.MoveToPoint(cx - half * 0.62, cy - sign * half * 0.28)
        path.AddLineToPoint(cx, cy + sign * half * 0.36)
        path.AddLineToPoint(cx + half * 0.62, cy - sign * half * 0.28)
        gc.StrokePath(path)
    elif icon in ('star', 'starred'):
        # star: outlined, filled while on
        path = gc.CreatePath()
        for k in range(10):
            radius = half * 1.25 if k % 2 == 0 else half * 0.52
            angle = math.pi / 2 + k * math.pi / 5
            px, py = cx + radius * math.cos(angle), cy + 0.5 - radius * math.sin(angle)
            if k == 0:
                path.MoveToPoint(px, py)
            else:
                path.AddLineToPoint(px, py)
        path.CloseSubpath()
        if icon == 'starred':
            gc.FillPath(path)
        else:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.2)))
            gc.SetBrush(wx.NullGraphicsBrush)
            gc.StrokePath(path)
    elif icon == 'menu':
        # three bars: the sidebar
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.4)))
        for k in (-0.6, 0.0, 0.6):
            gc.StrokeLine(cx - half * 1.0, cy + half * k, cx + half * 1.0, cy + half * k)
    elif icon in ('speaker', 'mute'):
        # speaker: waves, or a cross while muted
        body = gc.CreatePath()
        body.MoveToPoint(cx - half * 1.0, cy - half * 0.4)
        body.AddLineToPoint(cx - half * 0.5, cy - half * 0.4)
        body.AddLineToPoint(cx + half * 0.1, cy - half * 0.95)
        body.AddLineToPoint(cx + half * 0.1, cy + half * 0.95)
        body.AddLineToPoint(cx - half * 0.5, cy + half * 0.4)
        body.AddLineToPoint(cx - half * 1.0, cy + half * 0.4)
        body.CloseSubpath()
        gc.FillPath(body)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.4)))
        gc.SetBrush(wx.NullGraphicsBrush)
        if icon == 'mute':
            gc.StrokeLine(cx + half * 0.45, cy - half * 0.4, cx + half * 1.15, cy + half * 0.4)
            gc.StrokeLine(cx + half * 0.45, cy + half * 0.4, cx + half * 1.15, cy - half * 0.4)
        else:
            for r in (0.55, 1.0):
                path = gc.CreatePath()
                path.AddArc(cx + half * 0.1, cy, half * r, math.radians(-50),
                            math.radians(50), True)
                gc.StrokePath(path)
    elif icon in ('loop', 'loop_one'):
        # repeat: a loop with an arrow at each end; loop_one adds a 1
        if icon == 'loop_one':
            font = get_font(9, bold=True)
            set_font(gc, font, ink)
            one = gc.GetTextExtent('1')[0]
            cx -= (one + 2) / 2.0
            offset, caps = get_caps_ink(font)
            gc.DrawText('1', cx + half * 0.9 + 2, y + (h - caps) / 2.0 - offset)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.6).Cap(wx.CAP_BUTT)))
        gc.SetBrush(wx.NullGraphicsBrush)
        left, right = cx - half * 0.9, cx + half * 0.9
        top, bottom, r = cy - half * 0.62, cy + half * 0.62, half * 0.32
        for sign in (1, -1):
            # upper half rightward, lower half leftward
            start, end = (left, right) if sign > 0 else (right, left)
            edge = top if sign > 0 else bottom
            path = gc.CreatePath()
            path.MoveToPoint(start, cy + sign * half * 0.2)
            path.AddArcToPoint(start, edge, start + sign * r, edge, r)
            path.AddLineToPoint(end - sign * half * 0.42, edge)
            gc.StrokePath(path)
            head = gc.CreatePath()
            head.MoveToPoint(end + sign * half * 0.1, edge)
            head.AddLineToPoint(end - sign * half * 0.48, edge - half * 0.48)
            head.AddLineToPoint(end - sign * half * 0.48, edge + half * 0.48)
            head.CloseSubpath()
            gc.SetBrush(gc.CreateBrush(wx.Brush(ink)))
            gc.FillPath(head)
            gc.SetBrush(wx.NullGraphicsBrush)
    elif icon in ('prev', 'next'):
        sign = 1 if icon == 'next' else -1
        for k in (0, 1):
            tip = cx + sign * (half * (1.0 - k))
            back = tip - sign * half
            path = gc.CreatePath()
            path.MoveToPoint(back, cy - half * 0.8)
            path.AddLineToPoint(tip, cy)
            path.AddLineToPoint(back, cy + half * 0.8)
            path.CloseSubpath()
            gc.FillPath(path)
        edge = cx + sign * half
        gc.DrawRectangle(min(edge, edge + sign * 1.6), cy - half * 0.8, 1.6, half * 1.6)


# texts drawn cut short: the whole one the window's tip under the mouse
class CutTips():

    def __init__(self, window):
        self.window = window
        self.cuts = dict()
        self.tip = None

    def Clear(self):
        self.cuts.clear()

    def Add(self, rect, text, shown):
        # drawn again: its old cut replaced, or gone when it fits now
        rect = wx.Rect(*rect)
        key = tuple(rect.Get())
        text = f'{text}'
        if shown == text:
            self.cuts.pop(key, None)
        else:
            self.cuts[key] = (rect, text)

    def Forget(self):
        # the window's tip set by another
        self.tip = None

    def Update(self, point=None):
        # point: in the window, None off it
        text = None
        if point is not None:
            point = wx.Point(*point)
            for rect, whole in self.cuts.values():
                if rect.Contains(point):
                    text = whole
        if text == self.tip:
            return
        self.tip = text
        if text is None:
            self.window.UnsetToolTip()
        else:
            self.window.SetToolTip(text)
