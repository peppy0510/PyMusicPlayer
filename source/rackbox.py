# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import functools
import math
import uikit
import wx

from macroboxlib import FONT_PLAYINFO
from macroboxlib import GetPreference
from macroboxlib import RectBox
from macroboxlib import SetPreference


# the rack: the player's zone over the deck (its header and waveforms), its modules
# one under another as a plug-in's plates (MASTER, ANALYZER
# and MIXER). a module: a header (its LED, its name, its state, its own chips and its parts')
# over its parts, each part folded on its own, the whole module from the control row; what
# is shown kept (each module's PREFERENCE)
HEADER = 24


def colour(value):
    return wx.Colour(*value) if isinstance(value, (tuple, list)) else wx.Colour(value)


# (made once a size and weight: made at every call, the rack's modules spent their frames
# making fonts, and the window stopped answering the mouse)
@functools.lru_cache(maxsize=64)
def get_font(pixels, bold=False, mono=False):
    face = FONT_PLAYINFO if mono else uikit.FONT_FACE
    return wx.Font(wx.Size(0, int(round(pixels))), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                   wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL, faceName=face)


def draw_well(gc, st, rect, edge=None, width=1, radius=None):
    '''a display set into the rack's plates (an LCD, a meter's, a scope's): darker at its
    top as a hole's shadow falls, a line of shadow along its top inside, a line of light
    along its bottom outside; edge: its rim's colour (the mouse on it, a device's colour)'''
    x, y, w, h = rect
    radius = uikit.RADIUS if radius is None else radius
    lcd = colour(st.LCD_BG_COLOR)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(
        edge if edge is not None else uikit.mix(lcd, (0, 0, 0), 0.5)).Width(width)))
    gc.SetBrush(gc.CreateLinearGradientBrush(x, y, x, y + h, uikit.mix(lcd, (0, 0, 0), 0.35),
                                             lcd))
    gc.DrawRoundedRectangle(x + 0.5, y + 0.5, w - 1, h - 1, radius)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(0, 0, 0, 110)).Width(1)))
    gc.StrokeLine(x + 2, y + 1.5, x + w - 2, y + 1.5)
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(255, 255, 255, 16)).Width(1)))
    gc.StrokeLine(x + 2, y + h + 0.5, x + w - 2, y + h + 0.5)


class Rack():

    '''the rack's modules (made by the player box, its parent) placed at its top, over
    the header, the first at the top; the zone's height the shown modules' together'''

    def __init__(self, parent, modules):
        self.parent = parent
        self.modules = list(modules)

    def GetHeight(self):
        return sum(module.GetHeight() for module in self.modules)

    def GetTop(self):
        # under its bar
        return RackBar.HEIGHT

    def OnSize(self):
        y = self.GetTop()
        width = self.parent.GetClientSize().width
        before = self.GetHeight()
        for module in self.modules:
            module.Place(y, width)
            y += module.GetHeight()
        # (a module's parts wrapped to more rows or fewer at this width: the player as tall
        # as the rack is now, once the sizing is done)
        if self.GetHeight() != before and not getattr(self, 'relayout_due', False):
            self.relayout_due = True
            wx.CallAfter(self.RelayoutDue)

    def RelayoutDue(self):
        self.relayout_due = False
        self.Relayout()

    def Relayout(self):
        # the player as tall as the rack needs, the list under it
        mainpanel = self.parent.parent
        frame = mainpanel.parent
        if frame.IsPlayerOnlyModeOn():
            frame.SetPlayerOnlyHeight()
        else:
            frame.FitRackRoom()
        mainpanel.OnSize()
        self.parent.OnSize()
        # (all of the window painted again, its children too: what stood where the rack
        # grew or folded stayed on screen, a copy of the tempo strip among it)
        wx.GetTopLevelParent(self.parent).Refresh()

    def CatchEvent(self, event):
        for module in self.modules:
            module.CatchEvent(event)


# a knob (RackModule.DrawKnob): its radius; its whole range this many pixels of an up or
# down drag, a wheel's notch this much of it
KNOB_RADIUS = 12
KNOB_DRAG = 160
KNOB_WHEEL = 0.02

class RackModule(RectBox):

    # its name in the header, where what it shows is kept, and its parts top to bottom:
    # (key, the chip's label, height[, weight]); ROW: side by side instead, as wide as
    # their weights, the row as tall as the tallest
    TITLE = ''
    PREFERENCE = None
    PARTS = ()
    ROW = False
    ROW_GAP = 14
    # side by side parts: a line between them or not (a module drawing its own plates);
    # room kept at the sides past the usual 8 (for those plates)
    ROW_LINES = True
    ROW_INSET = 0

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        kept = GetPreference(self.PREFERENCE) or {}
        self.shown = kept.get('shown', False)
        self.parts = dict((part[0], kept.get(part[0], True)) for part in self.PARTS)
        self.hits = []
        self.hovered = None
        self.SetBackgroundColour(self.parent.st.RACK_BG_COLOR)
        self.InitBuffer()

    # what a module tells and does (its own)

    def IsActive(self):
        # its LED lit
        return True

    def GetState(self):
        # (text, warned) beside its name, or None
        return None

    def GetChips(self):
        # its own chips at the header's right, right to left: [(key, label, on, warned)]
        return []

    def OnChip(self, key):
        pass

    def DrawPart(self, gc, key, x, y, width):
        pass

    def DrawKnob(self, gc, cx, cy, value, hovered, radius=KNOB_RADIUS, origin=0.0,
                 tint=None, ticks=0):
        # (MASTER's, INSTRUMENTS' and MIXER's: theirs a size smaller; origin: where its
        # value's arc starts, a pan's at its centre; tint: its arc's colour (a machine's
        # own); ticks: marks round it, a hardware knob's scale)
        st = self.parent.st
        tokens = uikit.ui()
        r = radius
        start, sweep = math.radians(135), math.radians(270)
        if ticks:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(
                colour(st.RACK_LABEL_COLOR), colour(st.RACK_BG_COLOR).Get()[:3], 0.45))
                .Width(1)))
            for k in range(ticks):
                angle = start + sweep * k / float(ticks - 1)
                gc.StrokeLine(cx + math.cos(angle) * (r + 6), cy + math.sin(angle) * (r + 6),
                              cx + math.cos(angle) * (r + 8), cy + math.sin(angle) * (r + 8))
        # a hardware knob, matte as the keys (uikit.draw_face): seated in the panel by a
        # soft shadow under it, its cap one colour with a darker skirt round it and a faint
        # rim of light along its top (lit from above, as the plates), lighter under the mouse
        face = colour(st.KNOB_RING_COLOR if hovered else st.KNOB_FACE_COLOR)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateRadialGradientBrush(
            cx, cy + 2, cx, cy + 2, r + 3, wx.Colour(0, 0, 0, 120), wx.Colour(0, 0, 0, 0)))
        gc.DrawEllipse(cx - r - 3, cy - r - 1, (r + 3) * 2, (r + 3) * 2)
        skirt = uikit.mix(face, (0, 0, 0), 0.45)
        gc.SetBrush(gc.CreateBrush(wx.Brush(skirt)))
        gc.DrawEllipse(cx - r, cy - r, r * 2, r * 2)
        cap = r - max(r * 0.16, 1.5)
        gc.SetBrush(gc.CreateLinearGradientBrush(
            cx, cy - cap, cx, cy + cap, uikit.mix(face, (255, 255, 255), 0.07),
            uikit.mix(face, (0, 0, 0), 0.08)))
        gc.DrawEllipse(cx - cap, cy - cap, cap * 2, cap * 2)
        rim = gc.CreatePath()
        rim.AddArc(cx, cy, cap - 0.5, math.radians(200), math.radians(340), True)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(face, (255, 255, 255), 0.12))
                               .Width(1)))
        gc.StrokePath(rim)
        # the range's track and the value's arc just outside it (crisp: a glow read as
        # a haze)
        low, high = min(origin, value), max(origin, value)
        ink = colour(tint or tokens.ACCENT)
        for since, upto, pen in ((0.0, 1.0, wx.GraphicsPenInfo(colour(st.METER_OFF_COLOR))
                                  .Width(2.5)),
                                 (low, high, wx.GraphicsPenInfo(ink).Width(2.5))):
            if upto - since <= 0:
                continue
            path = gc.CreatePath()
            path.AddArc(cx, cy, r + 3, start + sweep * since, start + sweep * upto, True)
            gc.SetPen(gc.CreatePen(pen.Cap(wx.CAP_BUTT)))
            gc.StrokePath(path)
        # its pointer: a line from near its centre to its rim, a dot at the rim's end
        angle = start + sweep * value
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(st.RACK_TEXT_COLOR)).Width(2)
                               .Cap(wx.CAP_ROUND)))
        gc.StrokeLine(cx + math.cos(angle) * (cap * 0.3), cy + math.sin(angle) * (cap * 0.3),
                      cx + math.cos(angle) * (cap - 2), cy + math.sin(angle) * (cap - 2))

    def GetPartMost(self, key):
        # side by side (ROW): the widest a part is drawn (its share of a wider rack left
        # empty at its right); None: its whole share
        return None

    def IsDragging(self):
        # a hand on one of its controls: the hover kept where it is
        return False

    def HandleDrag(self, event):
        # True while a drag is its own (nothing else handled)
        return False

    def HandleHit(self, event, hit):
        pass

    # its parts

    def GetHeight(self):
        if self.shown is False:
            return 0
        heights = [self.GetPartHeight(part[0], part[2]) for part in self.PARTS
                   if self.parts[part[0]]]
        if self.ROW:
            rows = self.GetRowLayout(self.GetLayoutWidth())
            return HEADER + sum(max(self.GetPartHeight(part[0], part[2])
                                    for part, _, _ in row) for row in rows)
        return HEADER + sum(heights)

    def GetLayoutWidth(self):
        width = getattr(self, 'layout_width', 0) or self.GetSize()[0]
        return width or self.parent.GetSize()[0]

    def GetRowLayout(self, w):
        '''side by side parts in rows: [[(part, x, width)]]. parts with a widest
        (GetPartMost) kept at it, the next row taken when the room ends (a narrow window:
        they were squeezed past use); the others sharing one row by their weights'''
        shown = [part for part in self.PARTS if self.parts[part[0]]]
        if not shown:
            return []
        room = w - 16
        mosts = [self.GetPartMost(part[0]) for part in shown]
        if any(most is None for most in mosts):
            total = float(sum(part[3] for part in shown)) or 1.0
            share = room - self.ROW_GAP * (len(shown) - 1)
            row, x = [], 8.0
            for part in shown:
                width = share * part[3] / total
                row.append((part, x, width))
                x += width + self.ROW_GAP
            return [row]
        inset = 8.0 + self.ROW_INSET
        room -= 2 * self.ROW_INSET
        rows, row, x = [], [], inset
        for part, most in zip(shown, mosts):
            if row and x + most > inset + room:
                rows.append(row)
                row, x = [], inset
            width = min(most, room)
            row.append((part, x, width))
            x += width + self.ROW_GAP
        rows.append(row)
        return rows

    def GetPartHeight(self, key, height):
        # a part's height (its own, PARTS'), as tall as its contents at this width
        return height

    def IsPartShown(self, key):
        return self.parts.get(key, False)

    def Keep(self):
        kept = dict(self.parts)
        kept['shown'] = self.shown
        SetPreference(self.PREFERENCE, kept)

    def Toggle(self):
        # shown or folded away, its parts as they were
        self.shown = not self.shown
        self.Keep()
        self.parent.Rack.Relayout()

    def TogglePart(self, key):
        self.parts[key] = not self.parts[key]
        self.Keep()
        self.parent.Rack.Relayout()

    def Place(self, y, width):
        # (its rows as wide as it will be: its height with them)
        self.layout_width = width
        height = self.GetHeight()
        if height == 0:
            self.SetRect((0, 0, 0, 0))
            self.Hide()
            return
        self.SetRect((0, y, width, height))
        self.Show()
        self.DirectDraw()

    # drawn

    def SetRectDraw(self, dc):
        st = self.parent.st
        w, h = self.GetSize()
        self.hits = []
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
        gc.StrokeLine(0, 0.5, w, 0.5)
        gc.StrokeLine(0, h - 0.5, w, h - 0.5)
        self.DrawHeader(dc, gc, w)
        shown = [part for part in self.PARTS if self.parts[part[0]]]
        if self.ROW:
            # side by side, a line between them; rows (GetRowLayout) a line apart
            y = HEADER
            for r, row in enumerate(self.GetRowLayout(w)):
                height = max(self.GetPartHeight(part[0], part[2]) for part, _, _ in row)
                gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
                if r and self.ROW_LINES:
                    gc.StrokeLine(8, y + 0.5, w - 8, y + 0.5)
                for k, (part, x, width) in enumerate(row):
                    if k and self.ROW_LINES:
                        gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
                        gc.StrokeLine(x - self.ROW_GAP / 2.0, y + 6,
                                      x - self.ROW_GAP / 2.0, y + height - 8)
                    self.DrawPart(gc, part[0], int(x), y, int(width))
                y += height
            return
        y = HEADER
        for k, part in enumerate(shown):
            if k:
                # a line between its parts
                gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
                gc.StrokeLine(8, y + 0.5, w - 8, y + 0.5)
            self.DrawPart(gc, part[0], 8, y, w - 16)
            y += self.GetPartHeight(part[0], part[2])

    def DrawHeader(self, dc, gc, w):
        st = self.parent.st
        tokens = uikit.ui()
        # the LED: lit (the accent) while it works, a ring while it does not
        # (8 px from the window's edges, as everything along them)
        cx, cy = 14, HEADER / 2.0
        if self.IsActive():
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(tokens.ACCENT))))
        else:
            gc.SetPen(wx.Pen(colour(st.RACK_LABEL_COLOR), 1))
            gc.SetBrush(wx.NullGraphicsBrush)
        gc.DrawEllipse(cx - 4, cy - 4, 8, 8)
        gc.SetFont(get_font(uikit.BODY, bold=True), colour(st.RACK_TEXT_COLOR))
        tw, th = gc.GetTextExtent(self.TITLE)[:2]
        gc.DrawText(self.TITLE, 26, (HEADER - th) / 2.0)
        state = self.GetState()
        if state is not None:
            text, warned = state
            gc.SetFont(get_font(10), colour(tokens.WARN if warned else st.RACK_LABEL_COLOR))
            sh = gc.GetTextExtent(text)[1]
            gc.DrawText(text, 26 + tw + 10, (HEADER - sh) / 2.0)
        # the chips at the right: its own, then its parts' (shown or folded)
        chips = list(self.GetChips())
        # (a module of one part: none, nothing to fold)
        if len(self.PARTS) > 1:
            chips += [(part[0], part[1], self.parts[part[0]], False)
                      for part in reversed(self.PARTS)]
        x = w - 8
        font = get_font(10, bold=True)
        for key, label, on, warned in chips:
            dc.SetFont(font)
            cw = dc.GetTextExtent(label)[0] + 16
            x -= cw
            rect = (x, 4, cw, HEADER - 8)
            uikit.draw_button(dc, rect, label=label, on=on and not warned, warn=on and warned,
                              hover=self.hovered == key, font=font)
            self.hits.append((wx.Rect(*rect), 'chip', key))
            x -= 6

    # handled

    def GetHit(self, point):
        for rect, kind, key in self.hits:
            if rect.Contains(point):
                return kind, key
        return None

    def CATCH_EVT_GLOBAL(self, event):
        if self.IsShown() is False:
            return
        point = wx.Point(int(event.X), int(event.Y))
        hit = self.GetHit(point) if self.onClient else None
        hovered = hit[1] if hit and hit[0] == 'chip' else hit
        if hovered != self.hovered and self.IsDragging() is False:
            self.hovered = hovered
            # (at once where a module can: at the clock's next frame it came late)
            repaint = getattr(self, 'Repaint', None)
            if repaint is not None:
                # (the mouse alone: nothing edited, INSTRUMENTS' kept pictures kept)
                self.hover_only = True
                repaint()
                self.hover_only = False
            else:
                self.reInitBuffer = True
        if self.HandleDrag(event):
            return
        if self.onClient is False or hit is None:
            return
        if hit[0] == 'chip':
            if event.LeftDown or event.LeftDClick:
                if hit[1] in self.parts:
                    self.TogglePart(hit[1])
                else:
                    self.OnChip(hit[1])
            return
        self.HandleHit(event, hit)


class RackBar(RectBox):

    '''the rack's bar at the player's top, always there: a key for each module, its name (a
    LED before it lit while the module works) and its arrow (shown or folded under the bar).
    MASTER's name turns it on or off (its plugin on the sound), ANALYZER's shows it as its
    arrow does'''

    HEIGHT = 30
    KEY_HEIGHT = 19
    ARROW = 20
    LED = 6
    # the output at the bar's right, as a rack's meter: L and R in segments (blue, orange
    # over -12 dB), the short-term loudness on a display
    # (120 at most, 60 at least as the room is: 150 fixed before)
    METER_WIDTH = 120
    METER_LEAST = 60
    # between the bars and the loudness's display (10 before)
    METER_GAP = 14
    METER_LOW = -48.0
    METER_WARN = -12.0

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        self.hits = []
        self.hovered = None
        self.downed = None
        self.state = None
        self.SetBackgroundColour(self.parent.st.RACK_BG_COLOR)
        self.InitBuffer()

    def GetKeys(self):
        # (module, its name, lit, whether its name powers it)
        parent = self.parent
        # (in the rack's order: the signal's from the top down, what reads the output, the
        # output, the mixer, its sources)
        keys = []
        analyzer = getattr(parent, 'Analyzer', None)
        if analyzer is not None:
            keys.append((analyzer, 'ANALYZER', analyzer.shown and analyzer.IsActive(), False))
        master = getattr(parent, 'Master', None)
        if master is not None:
            lit = hasattr(parent, 'cue') and parent.IsLoudOn()
            keys.append((master, 'MASTER', lit, True))
        # MIXER: lit while something sounds through it, its name shows or folds it (as
        # ANALYZER's)
        mixer = getattr(parent, 'Mixer', None)
        if mixer is not None:
            keys.append((mixer, 'MIXER', mixer.shown and mixer.IsActive(), False))
        return keys

    def GetState(self):
        return tuple((label, lit, module.shown) for module, label, lit, _ in self.GetKeys())

    def OnSize(self, event=None):
        self.SetRect((0, 0, self.parent.GetClientSize().width, self.HEIGHT))
        self.DirectDraw()

    def SetRectDraw(self, dc):
        st = self.parent.st
        tokens = uikit.ui()
        w, h = self.GetSize()
        self.hits = []
        dc.SetPen(wx.Pen(st.RACK_EDGE_COLOR, 1))
        dc.DrawLine(0, h - 1, w, h - 1)
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        font = uikit.get_font(10, bold=True)
        x, y = 8, (h - 1 - self.KEY_HEIGHT) // 2
        for module, label, lit, power in self.GetKeys():
            # the name's key: its LED and its name, as MASTER's switches
            gc.SetFont(font, colour(st.RACK_TEXT_COLOR))
            tw = int(math.ceil(gc.GetTextExtent(label)[0]))
            kw = 7 + self.LED + 6 + tw + 9
            hovered = self.hovered == (module, 'name')
            downed = self.downed == (module, 'name')
            face = colour(tokens.CONTROL_DOWN if downed else tokens.CONTROL_HOVER
                          if hovered else tokens.CONTROL_BG)
            # joined to its arrow, their edge shared (an input group's)
            uikit.draw_face(gc, (x, y, kw, self.KEY_HEIGHT), face, pressed=downed,
                            corners='left')
            ly = y + (self.KEY_HEIGHT - self.LED) // 2
            if lit:
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(tokens.ACCENT))))
            else:
                gc.SetPen(wx.Pen(colour(st.RACK_LABEL_COLOR), 1))
                gc.SetBrush(wx.NullGraphicsBrush)
            gc.DrawEllipse(x + 7, ly, self.LED, self.LED)
            gc.SetFont(font, colour(tokens.BAR_TEXT if lit else tokens.CONTROL_FG))
            gc.DrawText(label, x + 7 + self.LED + 6,
                        uikit.get_caps_top(font, y, self.KEY_HEIGHT))
            self.hits.append((wx.Rect(x, y, kw, self.KEY_HEIGHT), (module, 'name'), power))
            x += kw - 1
            # its arrow: the module under the bar (up while it is shown)
            uikit.draw_button(dc, (x, y, self.ARROW, self.KEY_HEIGHT),
                              icon='up' if module.shown else 'down',
                              on=module.shown, hover=self.hovered == (module, 'arrow'),
                              down=self.downed == (module, 'arrow'), corners='right')
            self.hits.append((wx.Rect(x + 1, y, self.ARROW - 1, self.KEY_HEIGHT),
                              (module, 'arrow'), power))
            # 8 px to the next module's key (13 before), the window's gap
            x += self.ARROW + 8
        self.DrawMeter(gc, x, w, h)

    def DrawMeter(self, gc, left, w, h):
        # read here while ANALYZER is folded (its readings are the same: drawn, it reads)
        analyzer = getattr(self.parent, 'Analyzer', None)
        if analyzer is None:
            return
        if analyzer.IsShown() is False:
            analyzer.Read()
        a = analyzer.analyzer
        st = self.parent.st
        tokens = uikit.ui()
        short = a.loudness[1]
        text = '%5.1f LUFS' % short if short > -70.0 else '  --  LUFS'
        font = get_font(uikit.READOUT, mono=True)
        gc.SetFont(font, colour(st.LCD_TEXT_COLOR))
        tw, th = gc.GetTextExtent('-00.0 LUFS')[:2]
        cw, ch = tw + 12, self.KEY_HEIGHT
        cx, cy = w - 8 - cw, (h - 1 - ch) // 2
        # the loudness's display left out in a very small window (the bars kept): the room
        # OUT and its bars at their least need
        least = 34 + self.METER_LEAST
        lufs = cx - self.METER_GAP - left >= least
        if lufs is False:
            cx = w - 8 + self.METER_GAP
        # its bars as wide as the room is (METER_WIDTH at most, METER_LEAST at least: a fixed
        # 150 left OUT out of a small window)
        room = cx - self.METER_GAP - 34 - 13 - left
        width = int(max(self.METER_LEAST, min(self.METER_WIDTH, room)))
        bx = cx - self.METER_GAP - width
        if bx - 34 < left:
            return
        if lufs:
            gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.LCD_BG_COLOR))))
            gc.DrawRoundedRectangle(cx + 0.5, cy + 0.5, cw - 1, ch - 1, uikit.RADIUS)
            gc.DrawText(text, cx + 6, cy + (ch - th) / 2.0)
        # OUT, then the channels' bars one over the other
        label = get_font(uikit.LABEL, bold=True)
        gc.SetFont(label, colour(st.RACK_LABEL_COLOR))
        lw = gc.GetTextExtent('OUT')[0]
        gc.DrawText('OUT', bx - 8 - lw, uikit.get_caps_top(label, cy, ch))
        segment, spacing, bar = uikit.METER_SEGMENT, uikit.METER_GAP, uikit.METER_BAR
        count = int((width + spacing) / (segment + spacing))
        # on whole pixels (the cell's width is a text's: a segment fell between two)
        bx = int(bx)
        warn_from = int(round((self.METER_WARN - self.METER_LOW) / -self.METER_LOW * count))
        top = cy + (ch - bar * 2 - 3) // 2
        gc.SetPen(wx.NullGraphicsPen)
        for c in (0, 1):
            share = max(min((a.peak[c] - self.METER_LOW) / -self.METER_LOW, 1.0), 0.0)
            lit = int(round(share * count))
            by = top + c * (bar + 3)
            for k in range(count):
                if k < lit:
                    fill = tokens.WARN if k >= warn_from else tokens.ACCENT
                else:
                    fill = st.METER_OFF_COLOR
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(fill))))
                gc.DrawRectangle(bx + k * (segment + spacing), by, segment, bar)

    def GetHit(self, point):
        for rect, key, power in self.hits:
            if rect.Contains(point):
                return key, power
        return None, None

    def CATCH_EVT_GLOBAL(self, event):
        state = self.GetState()
        if state != self.state:
            self.state = state
            self.reInitBuffer = True
        key, power = self.GetHit(wx.Point(int(event.X), int(event.Y))) if self.onClient\
            else (None, None)
        if key != self.hovered:
            self.hovered = key
            self.reInitBuffer = True
        if (event.LeftDown or event.LeftDClick) and key is not None:
            self.downed = key
            self.reInitBuffer = True
            module, part = key
            if part == 'arrow' or power is False:
                self.ToggleModule(module)
            else:
                # MASTER on or off
                if self.parent.IsLoudOn():
                    self.parent.SetLoudOff()
                else:
                    self.parent.SetLoudOn()
        elif event.LeftIsDown is False and self.downed is not None:
            self.downed = None
            self.reInitBuffer = True

    def ToggleModule(self, module):
        frame = self.parent.parent.parent
        if module is getattr(self.parent, 'Analyzer', None):
            # with the View menu's check
            frame.SetAnalyzerShow(not module.shown)
        else:
            module.Toggle()
