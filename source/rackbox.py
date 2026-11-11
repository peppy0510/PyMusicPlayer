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


# the rack: modules one under another over the deck, each a header over its parts
# module header: chips CHIP high, centred between the lines
HEADER = 32
# header keys as tall as master's mute key
CHIP = 19
# chip names when the header is too narrow (GetChipLayout)
SHORT_LABELS = {'CONTROLS': 'CTRL', 'SPECTRUM': 'SPEC', 'SPECTROGRAM': 'GRAM',
                'LIMITER': 'LIMIT', 'METERS': 'METER'}


def colour(value):
    return wx.Colour(*value) if isinstance(value, (tuple, list)) else wx.Colour(value)


# cached per size and weight: making fonts per call stalls the frames
@functools.lru_cache(maxsize=64)
def get_font(pixels, bold=False, mono=False):
    face = FONT_PLAYINFO if mono else uikit.FONT_FACE
    return wx.Font(wx.Size(0, int(round(pixels))), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                   wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL, faceName=face)


def draw_well(gc, st, rect, edge=None, width=1, radius=None):
    '''a display set into the plate: inner shadow at top, light below'''
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


def draw_rule(gc, st, x, y, width):
    # a line between rack parts, a whole row in the edge colour
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.RACK_EDGE_COLOR))))
    gc.DrawRectangle(x, y, width, 1)


class Rack():

    '''the rack's modules at the player's top, master first'''

    def __init__(self, parent, modules):
        self.parent = parent
        self.modules = list(modules)

    def GetHeight(self):
        return sum(module.GetHeight() for module in self.modules)

    def GetTop(self):
        return 0

    def OnSize(self):
        y = self.GetTop()
        width = self.parent.GetClientSize().width
        before = self.GetHeight()
        for module in self.modules:
            module.Place(y, width)
            y += module.GetHeight()
        # parts rewrapped at this width: relayout once sizing is done
        if self.GetHeight() != before and not getattr(self, 'relayout_due', False):
            self.relayout_due = True
            wx.CallAfter(self.RelayoutDue)

    def RelayoutDue(self):
        self.relayout_due = False
        self.Relayout()

    def Relayout(self):
        # player as tall as the rack needs, the list under it
        mainpanel = self.parent.parent
        frame = mainpanel.parent
        if frame.IsPlayerOnlyModeOn():
            frame.SetPlayerOnlyHeight()
        else:
            frame.FitRackRoom()
        mainpanel.OnSize()
        self.parent.OnSize()
        # repaint the window and children or stale pixels stay
        wx.GetTopLevelParent(self.parent).Refresh()

    def CatchEvent(self, event):
        for module in self.modules:
            module.CatchEvent(event)


# knob radius; drag pixels for the full range, wheel notch step
KNOB_RADIUS = 12
KNOB_DRAG = 160
KNOB_WHEEL = 0.02

class RackModule(RectBox):

    # (key, chip label, height[, weight]); ROW: side by side by weight
    TITLE = ''
    PREFERENCE = None
    PARTS = ()
    ROW = False
    ROW_GAP = 14
    # side by side: lines between parts; extra side inset
    ROW_LINES = True
    ROW_INSET = 0

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.buffer.fps = 30
        kept = GetPreference(self.PREFERENCE) or {}
        self.shown = kept.get('shown', False)
        # folded: header alone
        self.folded = bool(kept.get('folded', False))
        self.parts = dict((part[0], kept.get(part[0], True)) for part in self.PARTS)
        self.hits = []
        self.hovered = None
        self.tips = uikit.CutTips(self)
        self.SetBackgroundColour(self.parent.st.RACK_BG_COLOR)
        self.InitBuffer()

    # what a module tells and does

    def IsActive(self):
        # led lit
        return True

    def GetState(self):
        # (text, warned) beside its name, or None
        return None

    def GetChips(self):
        # own chips at the header's right: [(key, label, on, warned)]
        return []

    def OnChip(self, key):
        pass

    def IsChipEnabled(self, key):
        return True

    # power key (master), else an icon (analyzer)
    POWER = False

    def IsPowered(self):
        return self.IsActive()

    def OnPower(self):
        pass

    def DrawIcon(self, gc, cx, cy):
        pass

    # what it shows after its state on the header
    def GetSummaryWidth(self, dc):
        return 0

    def DrawSummary(self, gc, x, cy):
        pass

    def GetSmallTextRows(self, font, bar):
        '''(text y, bar top): small header text centred on the title's middle'''
        offset, ink = uikit.get_caps_ink(font)
        middle = HEADER / 2.0
        return int(round(middle - offset - ink / 2.0)), int(middle - bar / 2.0 + 0.5)

    def DrawPart(self, gc, key, x, y, width):
        pass

    def DrawKnob(self, gc, cx, cy, value, hovered, radius=KNOB_RADIUS, origin=0.0,
                 tint=None, ticks=0):
        # origin: where the arc starts; tint: arc colour; ticks: scale marks
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
        # hardware knob: soft shadow, cap with darker skirt, top rim light
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
        # track and value arc just outside it, crisp
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
        # pointer: a line to the rim, a dot at its end
        angle = start + sweep * value
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(st.RACK_TEXT_COLOR)).Width(2)
                               .Cap(wx.CAP_ROUND)))
        gc.StrokeLine(cx + math.cos(angle) * (cap * 0.3), cy + math.sin(angle) * (cap * 0.3),
                      cx + math.cos(angle) * (cap - 2), cy + math.sin(angle) * (cap - 2))

    def GetPartMost(self, key):
        # ROW: widest a part is drawn; None: its whole share
        return None

    def IsDragging(self):
        # a hand on a control: keep the hover
        return False

    def HandleDrag(self, event):
        # True while the drag is its own
        return False

    def HandleHit(self, event, hit):
        pass

    # its parts

    def GetHeight(self):
        if self.shown is False:
            return 0
        if self.folded:
            return HEADER
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
        '''side by side parts in rows: [[(part, x, width)]]'''
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
        # part height, as tall as its contents at this width
        return height

    def IsPartShown(self, key):
        return self.parts.get(key, False)

    def Keep(self):
        kept = dict(self.parts)
        kept['shown'] = self.shown
        kept['folded'] = self.folded
        SetPreference(self.PREFERENCE, kept)

    def ToggleFold(self):
        self.folded = not self.folded
        self.Keep()
        self.parent.Rack.Relayout()

    def Toggle(self):
        # shown or folded, parts as they were
        self.shown = not self.shown
        self.Keep()
        self.parent.Rack.Relayout()

    def TogglePart(self, key):
        self.parts[key] = not self.parts[key]
        self.Keep()
        self.parent.Rack.Relayout()

    def Place(self, y, width):
        # layout width first: the height depends on it
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
        self.DrawHeader(dc, gc, w)
        if not self.folded:
            self.DrawParts(gc, w)
        # bottom line only, drawn last, a whole row tall
        draw_rule(gc, st, 0, h - 1, w)

    def DrawParts(self, gc, w):
        st = self.parent.st
        shown = [part for part in self.PARTS if self.parts[part[0]]]
        # lines after the parts: a part's picture would hide them
        lines = []
        if self.ROW:
            # side by side, a line between; rows a line apart
            y = HEADER
            for r, row in enumerate(self.GetRowLayout(w)):
                height = max(self.GetPartHeight(part[0], part[2]) for part, _, _ in row)
                if r and self.ROW_LINES:
                    lines.append((8, y + 0.5, w - 8, y + 0.5))
                for k, (part, x, width) in enumerate(row):
                    if k and self.ROW_LINES:
                        lines.append((x - self.ROW_GAP / 2.0, y + 6,
                                      x - self.ROW_GAP / 2.0, y + height - 8))
                    self.DrawPart(gc, part[0], int(x), y, int(width))
                y += height
        else:
            y = HEADER
            for k, part in enumerate(shown):
                if k:
                    lines.append((8, y + 0.5, w - 8, y + 0.5))
                self.DrawPart(gc, part[0], 8, y, w - 16)
                y += self.GetPartHeight(part[0], part[2])
        gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
        for line in lines:
            gc.StrokeLine(*line)

    # header left as PyWinAudio's rack: chevron, power key or icon, name
    FOLD_X = 14
    ICON_X = 33
    TITLE_X = 46
    HEAD_KEY = 18

    def DrawHeadKeys(self, gc):
        # chevron (down: open, right: folded), power key or icon; hits 'fold', 'power'
        st = self.parent.st
        tokens = uikit.ui()
        cy = HEADER / 2.0
        size = self.HEAD_KEY
        for kind, cx in (('fold', self.FOLD_X), ('power', self.ICON_X)):
            if kind == 'power' and not self.POWER:
                continue
            rect = wx.Rect(int(cx - size / 2), int(cy - size / 2), size, size)
            pressed = getattr(self, 'key_down', None) == (kind, None)
            if self.hovered == (kind, None) or pressed:
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(tokens.CONTROL_DOWN if pressed
                                                           else tokens.CONTROL_HOVER))))
                gc.DrawRoundedRectangle(rect.x, rect.y, rect.width, rect.height, uikit.RADIUS)
            self.hits.append((rect, kind, None))
        hovered = self.hovered == ('fold', None)
        ink = colour(st.RACK_TEXT_COLOR if hovered else st.RACK_LABEL_COLOR)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.5).Cap(wx.CAP_ROUND)
                               .Join(wx.JOIN_ROUND)))
        gc.SetBrush(wx.NullGraphicsBrush)
        cx, half = self.FOLD_X, 5.0
        if self.folded:
            points = [(cx - half * 0.35, cy - half * 0.7), (cx + half * 0.35, cy),
                      (cx - half * 0.35, cy + half * 0.7)]
        else:
            points = [(cx - half * 0.7, cy - half * 0.35), (cx, cy + half * 0.35),
                      (cx + half * 0.7, cy - half * 0.35)]
        gc.StrokeLines(points)
        if not self.POWER:
            self.DrawIcon(gc, self.ICON_X, cy)
            return
        # power glyph: ring open at the top, a line into it
        on = self.IsPowered()
        ink = colour(tokens.ACCENT if on else st.RACK_TEXT_COLOR if
                     self.hovered == ('power', None) else st.RACK_LABEL_COLOR)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.6).Cap(wx.CAP_ROUND)))
        gc.SetBrush(wx.NullGraphicsBrush)
        r, cx = 5.5, self.ICON_X
        arc = gc.CreatePath()
        arc.AddArc(cx, cy + 0.5, r, math.radians(-60), math.radians(240), True)
        gc.StrokePath(arc)
        gc.StrokeLine(cx, cy - r - 0.5, cx, cy - 1)

    def DrawHeader(self, dc, gc, w):
        st = self.parent.st
        tokens = uikit.ui()
        self.DrawHeadKeys(gc)
        left = self.TITLE_X
        # chips at the right: actions, stage switches, part tabs
        chips = [chip if len(chip) == 5 else tuple(chip) + ('action',)
                 for chip in self.GetChips()]
        # a single-part module: nothing to fold
        if len(self.PARTS) > 1:
            chips += [(part[0], part[1], self.parts[part[0]], False, 'view')
                      for part in reversed(self.PARTS)]
        font = get_font(10, bold=True)
        title_font = get_font(uikit.BODY, bold=True)
        # state a step smaller and dimmed on the title's line
        state_font = get_font(uikit.LABEL)
        dc.SetFont(title_font)
        tw = dc.GetTextExtent(self.TITLE)[0]
        state = self.GetState()
        dc.SetFont(state_font)
        sw = dc.GetTextExtent(state[0])[0] + 10 if state is not None else 0
        # summary kept at every width
        summary = self.GetSummaryWidth(dc)
        kept = summary + 10 if summary else 0
        # right side reserved first, then chips, so the title is not cut
        # chip width plus the gaps around them
        span = 0
        if chips:
            first = self.GetChipLayout(dc, chips, w, font, 0)
            span = w - 8 - first[-1][0][0] + 10 + 16
        right = self.DrawHeaderRight(gc, w, left + tw + kept + span)
        # narrow: drop the state, tighten keys, short names, then cut the title
        for level in range(4):
            layout = self.GetChipLayout(dc, chips, right + 8, font, level)
            room = layout[-1][0][0] if layout else right
            if room - 10 >= left + tw + kept + (sw if level == 0 else 0):
                break
        title = self.TITLE
        dc.SetFont(title_font)
        while len(title) > 1 and left + dc.GetTextExtent(title)[0] + kept > room - 10:
            title = title[:-2] + '\u2026'
        uikit.set_font(gc, title_font, colour(st.RACK_TEXT_COLOR))
        tw, th = gc.GetTextExtent(title)[:2]
        gc.DrawText(title, left, (HEADER - th) / 2.0)
        self.tips.Clear()
        self.tips.Add((left, 0, int(tw) + 1, HEADER), self.TITLE, title)
        if state is not None and level == 0:
            text, warned = state
            uikit.set_font(gc, state_font, colour(tokens.WARN if warned else st.RACK_LABEL_COLOR))
            gc.DrawText(text, left + tw + 10, self.GetSmallTextRows(state_font, 0)[0])
        if summary:
            x = left + tw + 10
            if state is not None and level == 0:
                x += gc.GetTextExtent(state[0])[0] + 10
            self.DrawSummary(gc, x, HEADER / 2.0)
        compact = level >= 2
        for rect, (key, label, on, warned, kind), corners in layout:
            hover = self.hovered == key
            enabled = self.IsChipEnabled(key)
            whole = label
            if compact and level >= 3:
                label = SHORT_LABELS.get(label, label)
            self.tips.Add(rect, whole, label)
            if kind == 'switch':
                self.DrawSwitchChip(dc, rect, label, on, hover, font, compact)
            else:
                uikit.draw_button(dc, rect, label=label, on=on and not warned,
                                  warn=on and warned, hover=hover, font=font, corners=corners,
                                  down=getattr(self, 'key_down', None) == key,
                                  disabled=not enabled)
            self.hits.append((wx.Rect(*rect), 'chip', key))

    def DrawHeaderRight(self, gc, w, least):
        # module's own at the header's right end, from least
        return w - 8

    def GetChipLayout(self, dc, chips, w, font, level):
        '''[(rect, chip, corners)] right to left from the header's right'''
        compact = level >= 2
        pad, gap, apart = (10, 3, 8) if compact else (16, 6, 14)
        dc.SetFont(font)
        layout = []
        x = w - 8
        for k, chip in enumerate(chips):
            key, label, on, warned, kind = chip
            if level >= 3:
                label = SHORT_LABELS.get(label, label)
            cw = dc.GetTextExtent(label)[0] + pad + (11 if kind == 'switch' else 0)
            x -= cw
            before = chips[k - 1][4] if k else None
            after = chips[k + 1][4] if k + 1 < len(chips) else None
            corners = 'all'
            if kind == 'view' and 'view' in (before, after):
                # right to left: the group's rightmost first
                corners = 'none' if before == after == 'view' else\
                    'right' if before != 'view' else 'left'
            layout.append(((x, (HEADER - CHIP) // 2, cw, CHIP), chip, corners))
            x += 1 if kind == after == 'view' else -gap if kind == after else -apart
        return layout

    def DrawSwitchChip(self, dc, rect, label, on, hover, font, compact=False):
        # stage switch in the header: led and name on a key
        st = self.parent.st
        gc = wx.GraphicsContext.Create(dc)
        x, y, w, h = rect
        uikit.draw_face(gc, rect, colour(st.KNOB_RING_COLOR if hover else st.KNOB_FACE_COLOR))
        if on:
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(uikit.ui().ACCENT))))
        else:
            gc.SetPen(wx.Pen(colour(st.RACK_LABEL_COLOR), 1))
            gc.SetBrush(wx.NullGraphicsBrush)
        # from a whole row, as the controls' leds
        left = 5 if compact else 7
        gc.DrawEllipse(x + left, y + (h - 6) // 2, 6, 6)
        uikit.set_font(gc, font, colour(st.RACK_TEXT_COLOR if on else st.RACK_LABEL_COLOR))
        gc.DrawText(label, x + left + 12, uikit.get_caps_top(font, y, h))

    # handled

    def GetHit(self, point):
        for rect, kind, key in self.hits:
            if rect.Contains(point):
                return kind, key
        return None

    def CATCH_EVT_GLOBAL(self, event):
        if self.IsShown() is False:
            return
        held = event.LeftIsDown or event.RightIsDown
        self.tips.Update((event.X, event.Y) if self.onClient and held is False else None)
        point = wx.Point(int(event.X), int(event.Y))
        hit = self.GetHit(point) if self.onClient else None
        hovered = hit[1] if hit and hit[0] == 'chip' else hit
        if hovered != self.hovered and self.IsDragging() is False:
            self.hovered = hovered
            # repaint now where the module can
            repaint = getattr(self, 'Repaint', None)
            if repaint is not None:
                # hover only: kept pictures stay
                self.hover_only = True
                repaint()
                self.hover_only = False
            else:
                self.reInitBuffer = True
        # header key acts on release over it, face down while held
        header = hit is not None and hit[0] in ('fold', 'power', 'chip')
        down = getattr(self, 'key_down', None)
        if down is not None:
            if event.LeftIsDown is False:
                self.key_down = None
                self.reInitBuffer = True
                if header and self.onClient and hovered == down:
                    self.OnHeaderKey(hit)
            return
        if header and self.onClient and (event.LeftDown or event.LeftDClick):
            self.key_down = hovered
            self.reInitBuffer = True
            return
        if self.HandleDrag(event):
            return
        if self.onClient is False or hit is None or header:
            return
        self.HandleHit(event, hit)

    def OnHeaderKey(self, hit):
        if hit[0] == 'fold':
            self.ToggleFold()
        elif hit[0] == 'power':
            self.OnPower()
            self.reInitBuffer = True
        elif hit[1] in self.parts:
            self.TogglePart(hit[1])
        elif self.IsChipEnabled(hit[1]):
            self.OnChip(hit[1])
