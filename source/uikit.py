# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import macroboxstyle
import math
import wx


# the controls drawn in one way (the control strip, VOL, TEMPO): a rounded face, a vector
# icon or a label, its state by its face. on is the accent's face with its own text: told
# from off by brightness as well as hue (red-green colour blindness), not by colour alone
RADIUS = 3
# a level meter's segments, every meter's (OUT, MASTER's, ANALYZER's): this wide, this far
# apart, this tall a channel (MASTER's were 4, 1.5 and 8, OUT's 3, 1 and 4)
METER_SEGMENT = 3
METER_GAP = 1
METER_BAR = 4
FONT_FACE = 'Segoe UI'
# the type's four steps (pixels): a title, the body, a readout (in the monospace), a label
# (in capitals, bold); graphs' scales MICRO
TITLE = 16
BODY = 12
READOUT = 11
LABEL = 10
MICRO = 9


def ui():
    return macroboxstyle.current().UI


def colour(value):
    return wx.Colour(*value) if isinstance(value, (tuple, list)) else wx.Colour(value)


def get_font(pixels, bold=False):
    font = wx.Font(wx.Size(0, pixels), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                   wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL, faceName=FONT_FACE)
    return font


# a font's capitals' ink (from the top the text is drawn at, their height), measured once
CAPS_INK = {}


def get_caps_ink(font):
    # a capital H drawn by the same renderer, its lit rows found
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


def get_caps_top(font, top, height):
    # where text in capitals is drawn for its letters' middle on the box's middle (the
    # whole text box, its descent under the capitals, centred them low)
    offset, ink = get_caps_ink(font)
    return top + (height - ink) / 2.0 - offset


def get_face(on=False, down=False, hover=False, warn=False, disabled=False):
    # (face, ink) of a control in its state; disabled: flat, its label faint
    tokens = ui()
    if disabled:
        return colour(tokens.CONTROL_BG), colour(tokens.BAR_TEXT_DIM)
    if warn:
        return colour(tokens.WARN), colour(tokens.WARN_FG)
    if on:
        # lit, under the mouse a shade lighter (pressed: draw_face's darker), as an unlit
        # key's are (a lit key showed neither)
        face = colour(tokens.ACCENT)
        if hover and not down:
            face = mix(face, (255, 255, 255), 0.14)
        return face, colour(tokens.ACCENT_FG)
    if down:
        return colour(tokens.CONTROL_DOWN), colour(tokens.BAR_TEXT)
    if hover:
        return colour(tokens.CONTROL_HOVER), colour(tokens.BAR_TEXT)
    return colour(tokens.CONTROL_BG), colour(tokens.CONTROL_FG)


def draw_button(dc, rect, label=None, icon=None, on=False, down=False, hover=False,
                warn=False, font=None, disabled=False, corners='all'):
    # corners: 'left' or 'right' for a key joined to another (an input group's: a toggle
    # and its menu's arrow), its square side the one they share
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
    draw_face(gc, (x, y, w, h), face, pressed=pressed, flat=disabled, corners=corners)
    # pressed, the ink a pixel down as a key pushed in
    sink = 1 if pressed else 0
    if icon is not None:
        draw_icon(gc, icon, (x, y + sink, w, h), ink)
    if label:
        # one weight on and off (bold when on, the label widened and shifted as it toggled):
        # the state is the face's
        font = font or get_font(10, bold=True)
        gc.SetFont(font, ink)
        tw = gc.GetTextExtent(label)[0]
        # the capitals' ink centred, not the text's box (its descent under them): in mixed
        # case too (Filename sat a row low by its box, 7 rows over and 5 under), a
        # descender hanging under the middle as type does
        top = get_caps_top(font, y, h) + sink
        gc.DrawText(label, x + (w - tw) / 2.0, top)


def mix(c, other, share):
    return wx.Colour(*[int(a + (b - a) * share) for a, b in zip(c.Get()[:3], other)])


def draw_face(gc, rect, face, pressed=False, flat=False, corners='all'):
    # a hardware key's matte face: one even colour (no shine, no bulge), seated in the panel
    # by a darker edge; pressed, the face a shade darker; disabled, the same without its
    # edge darkened as much
    x, y, w, h = rect
    if pressed:
        face = mix(face, (0, 0, 0), 0.18)
    edge = mix(face, (0, 0, 0), 0.3 if flat else 0.5)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(edge).Width(1)))
    gc.SetBrush(gc.CreateBrush(wx.Brush(face)))
    # the renderer draws a shape's lines half a pixel down and right: from (x, y), w - 1
    # wide, its edge is on the rect's own outer rows and columns (measured)
    if corners == 'all':
        gc.DrawRoundedRectangle(x, y, w - 1, h - 1, RADIUS)
        return
    # rounded on one side only (corners: that side), square where it joins its neighbour
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
    # play, pause, prev, next: about half the face's height, centred
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
        # a chevron: the panel under the button folded (down) or open (up), a menu's
        # arrow; thinner and smaller than it was (1.8 px, 0.8 of the half wide)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.4)))
        gc.SetBrush(wx.NullGraphicsBrush)
        sign = 1 if icon == 'down' else -1
        path = gc.CreatePath()
        path.MoveToPoint(cx - half * 0.62, cy - sign * half * 0.28)
        path.AddLineToPoint(cx, cy + sign * half * 0.36)
        path.AddLineToPoint(cx + half * 0.62, cy - sign * half * 0.28)
        gc.StrokePath(path)
    elif icon == 'menu':
        # three bars: the sidebar
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.4)))
        for k in (-0.6, 0.0, 0.6):
            gc.StrokeLine(cx - half * 1.0, cy + half * k, cx + half * 1.0, cy + half * k)
    elif icon in ('speaker', 'mute'):
        # a speaker; its waves, or a cross while muted
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
