# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import effects
import math
import uikit
import wx

from rackbox import KNOB_DRAG
from rackbox import KNOB_WHEEL
from rackbox import RackModule
from rackbox import colour
from rackbox import get_font


# MIXER: a console, a strip each channel of the audio graph (AudioControl's: the deck's,
# the master's apart at the right), its effect editor after them. a strip a panel, its
# channel's colour on its cap, from
# the top: its name, its inserts (bass_fx's effects, effects.py: an empty one's click picks
# one, a click on one edits it at the right, a right click's menu changes, bypasses or
# removes it; the master's first Auto Master's), its pan, DECK's SYNC (MASTER's global
# tempo), its mute and solo, its fader (a scale beside it) with its meter (as heard: after
# its fader) and its dB. a double click puts a fader at 0 dB, a pan at the centre, an
# effect's knob at its first value. kept as they are let go

DECK = ('player', 'DECK')
MASTER = ('master', 'MASTER')
STRIP_WIDTH = 74
STRIP_GAP = 6
CAP = 3
NAME_TOP = 9
INSERT_TOP = 28
INSERT_HEIGHT = 15
INSERT_ROWS = 3
KNOB_RADIUS = 10
# a channel's sends (A, B: small knobs side by side), after its inserts
SEND_RADIUS = 7
SEND_CENTER = INSERT_TOP + INSERT_ROWS * (INSERT_HEIGHT + 2) + 6 + SEND_RADIUS + 2
PAN_CENTER = SEND_CENTER + SEND_RADIUS + 16 + KNOB_RADIUS + 6
# a line of their own: DECK's SYNC, MASTER's global tempo
TOOL_TOP = PAN_CENTER + KNOB_RADIUS + 18
TOOL_HEIGHT = 16
KEYS_TOP = TOOL_TOP + TOOL_HEIGHT + 6
KEY_HEIGHT = 16
KEY_WIDTH = 24
FADER_TOP = KEYS_TOP + KEY_HEIGHT + 12
FADER_HEIGHT = 84
CAP_WIDTH = 22
CAP_HEIGHT = 9
BODY = FADER_TOP + FADER_HEIGHT + 26
# the effect editor at the right: its knobs
EDITOR_MOST = 360
# its keys' width, a knob's room
FX_KEY = 58
EDITOR_CELL = 66
EDITOR_KNOB = 12
EDITOR_ROW = 62
# a fader's travel: its gain the square of its turn, doubled (0 dB at 0.707, +6 dB at the
# top: the low end spread wider than a line in dB would); its scale's marks
FADER_MOST = 2.0
SCALE = (6.0, 0.0, -6.0, -12.0, -24.0)
# its meter: -48 to +6 dB; past -12 dB in the warning colour (as the rack bar's)
METER_LOW = -48.0
METER_HIGH = 6.0
METER_WARN = -12.0
# the meters' fall a frame (as the rack bar's: a peak held a moment)
METER_FALL = 0.82
# the global tempo's drag (BPM a pixel) and wheel (a notch); a click on it types it, after
# this long without a second click (a double click: the deck's tempo)
TEMPO_DRAG = 0.1
TEMPO_WHEEL = 0.1
EDIT_AFTER_MS = 300
FX_DRAG = 220.0
FX_FINE = 0.2
# the channels' colours
CAPS = dict(player='#C9CED6', master='#E8E8E8', send='#8B909A')
# the send buses' returns (their strips before the master's)
RETURNS = (('send A', 'RET A'), ('send B', 'RET B'))


def gain_to_turn(gain):
    return min(math.sqrt(max(gain, 0.0) / FADER_MOST), 1.0)


def turn_to_gain(turn):
    return FADER_MOST * min(max(turn, 0.0), 1.0) ** 2


def to_db(value):
    return 20.0 * math.log10(value) if value > 1e-6 else -math.inf


def db_to_turn(db):
    return gain_to_turn(10.0 ** (db / 20.0))


def format_db(gain):
    db = to_db(gain)
    return '-INF' if db == -math.inf else '%+.1f' % db


def format_pan(pan):
    if abs(pan) < 0.005:
        return 'C'
    return '%s%d' % ('L' if pan < 0 else 'R', round(abs(pan) * 100))


class MixerPanel(RackModule):

    TITLE = 'MIXER'
    PREFERENCE = 'mixer_panel'
    PARTS = (('strips', 'STRIPS', BODY),)

    def __init__(self, parent):
        # (before the module's: it draws once made)
        self.drag = None
        self.levels = {}
        # the insert being edited: (channel, its index in the chain)
        self.editing = None
        RackModule.__init__(self, parent)
        self.buffer.fps = 30

    def GetControl(self):
        return getattr(self.parent, 'AudioControl', None)

    def GetStrips(self):
        return (DECK,)

    def GetReturns(self):
        control = self.GetControl()
        graph = control.graph if control is not None else None
        return tuple(ret for ret in RETURNS if graph is not None and ret[0] in graph.buses)

    def GetCapColour(self, channel_id):
        tokens = uikit.ui()
        kind = channel_id.split('-')[0].split()[0]
        tint = CAPS.get(channel_id) or CAPS.get(kind, '#C9CED6')
        return colour({'warn': tokens.WARN, 'accent': tokens.ACCENT}.get(tint, tint))

    def IsActive(self):
        # lit while anything sounds through it
        control = self.GetControl()
        return control is not None and control.mixed and control.graph is not None\
            and any(max(self.levels.get(key, (0.0, 0.0))) > 0.001
                    for key, _ in self.GetStrips() + (MASTER,))

    def GetState(self):
        control = self.GetControl()
        if control is None:
            return None
        if control.mixed is False:
            return ('AUDIO MIXER OFF (OPTION MENU)', True)
        hovered = self.hovered
        if isinstance(hovered, tuple) and hovered and hovered[0] == 'insert':
            return ('INSERT: CLICK EDIT (EMPTY: PICK ONE)  RIGHT-CLICK MENU', False)
        if isinstance(hovered, tuple) and hovered and hovered[0] == 'knob'\
                and hovered[1][0] == 'fx':
            return ('KNOB: DRAG  SHIFT FINE  WHEEL  DOUBLE-CLICK RESET', False)
        soloed = [label for key, label in self.GetStrips() if control.GetChannel(key)['solo']]
        if soloed:
            return ('SOLO ' + ' '.join(soloed), True)
        return None

    def GetChips(self):
        return []

    # drawn

    def DirectDraw(self):
        # its meters read at each of the clock's frames, drawn only when one of them
        # lights a segment more or less (or the mouse moves to another control)
        control = self.GetControl()
        if control is None:
            return
        self.ReadLevels(control)
        unit = uikit.METER_SEGMENT + uikit.METER_GAP
        count = int(FADER_HEIGHT // unit)
        frame = (tuple(self.GetLit(level, count) for levels in self.levels.values()
                       for level in levels), self.hovered, self.drag, self.editing,
                 control.GetGlobalTempo(), control.IsDeckSync(), tuple(self.GetSize()),
                 self.IsShown(), self.GetStrips())
        if frame == getattr(self, 'frame', None) and self.buffer.bmp is not None:
            return
        lap = self.buffer.lap
        RackModule.DirectDraw(self)
        # (kept only when drawn: the base skips a frame asked too soon)
        self.frame = frame if self.buffer.lap != lap else None

    def Repaint(self):
        # at once (an edit's: drawn when idle, a click felt late)
        self.frame = None
        self.reInitBuffer = False
        if self.IsShown() and self.GetSize()[0] > 0:
            self.InitBuffer()
            self.Refresh(False)
            self.Update()

    def GetLit(self, level, count):
        db = to_db(level)
        if db == -math.inf:
            return 0
        return int(round((min(max(db, METER_LOW), METER_HIGH) - METER_LOW)
                         / (METER_HIGH - METER_LOW) * count))

    def DrawPart(self, gc, key, x, y, width):
        control = self.GetControl()
        if control is None:
            return
        # the deck's strip from the left; the returns and MASTER held at the right; the
        # effect editor just before them
        sx = x
        for channel_id, label in self.GetStrips():
            self.DrawStrip(gc, control, channel_id, label, sx, y)
            sx += STRIP_WIDTH + STRIP_GAP
        strips_end = sx
        mx = x + width - STRIP_WIDTH
        self.DrawStrip(gc, control, MASTER[0], MASTER[1], mx, y)
        returns = self.GetReturns()
        rx = mx - 8 - len(returns) * (STRIP_WIDTH + STRIP_GAP)
        for k, (channel_id, label) in enumerate(returns):
            self.DrawStrip(gc, control, channel_id, label, rx + k * (STRIP_WIDTH + STRIP_GAP),
                           y)
        right = rx - 16
        editor = min(right - (strips_end + 10), EDITOR_MOST)
        self.DrawEditor(gc, control, right - editor, y, editor)

    def ReadLevels(self, control):
        # each strip's peak as heard, falling (METER_FALL) where it was higher
        for channel_id, _ in self.GetStrips() + self.GetReturns() + (MASTER,):
            now = control.GetPeak(channel_id)
            last = self.levels.get(channel_id, (0.0, 0.0))
            self.levels[channel_id] = tuple(max(n, l * METER_FALL) for n, l in zip(now, last))

    def DrawStrip(self, gc, control, channel_id, label, x, y):
        st = self.parent.st
        tokens = uikit.ui()
        spec = control.GetChannel(channel_id)
        cx = x + STRIP_WIDTH / 2.0
        ground = colour(st.RACK_BG_COLOR)
        face = uikit.mix(ground, (255, 255, 255), 0.045)
        cap = self.GetCapColour(channel_id)
        # its panel (lit from above as INSTRUMENTS' plates: lighter at its top, a highlight
        # along its top edge), its colour's cap
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(ground, (0, 0, 0), 0.6)).Width(1)))
        gc.SetBrush(gc.CreateLinearGradientBrush(
            x, y, x, y + BODY, uikit.mix(face, (255, 255, 255), 0.03),
            uikit.mix(face, (0, 0, 0), 0.12)))
        gc.DrawRoundedRectangle(x + 0.5, y + 2.5, STRIP_WIDTH - 1, BODY - 6, uikit.RADIUS + 1)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(cap)))
        gc.DrawRectangle(x + 2, y + 4, STRIP_WIDTH - 4, CAP)
        # its name
        here = channel_id in (MASTER[0], 'player') or channel_id in dict(RETURNS)
        gc.SetFont(get_font(uikit.LABEL, bold=True),
                   colour(st.RACK_TEXT_COLOR if here else st.RACK_LABEL_COLOR))
        text = label
        while len(text) > 1 and gc.GetTextExtent(text)[0] > STRIP_WIDTH - 8:
            text = text[:-1]
        tw = gc.GetTextExtent(text)[0]
        gc.DrawText(text, cx - tw / 2.0, y + NAME_TOP)
        self.DrawInserts(gc, control, channel_id, x, y, cap)
        # its pan
        cy = y + PAN_CENTER
        hit = ('pan', channel_id)
        self.DrawKnob(gc, cx, cy, (spec['pan'] + 1.0) / 2.0, self.hovered == ('knob', hit),
                      radius=KNOB_RADIUS, origin=0.5, tint=cap, ticks=11)
        gc.SetFont(get_font(uikit.MICRO, mono=True), colour(st.LCD_TEXT_COLOR))
        text = format_pan(spec['pan'])
        tw = gc.GetTextExtent(text)[0]
        gc.DrawText(text, cx - tw / 2.0, cy + KNOB_RADIUS + 5)
        self.hits.append((wx.Rect(int(x), int(cy - KNOB_RADIUS - 6), STRIP_WIDTH,
                                  KNOB_RADIUS * 2 + 22), 'knob', hit))
        # DECK's SYNC (its tempo to the global one), MASTER's global tempo (a drag or the
        # wheel moves it; a click types it; a double click takes the deck's)
        if channel_id == 'player':
            on = control.IsDeckSync()
            face_, ink = uikit.get_face(on=on, hover=self.hovered == ('key', ('sync', 'player')))
            rect = (int(cx - 24), y + TOOL_TOP, 48, TOOL_HEIGHT)
            uikit.draw_face(gc, rect, face_)
            font = get_font(uikit.MICRO, bold=True)
            gc.SetFont(font, ink)
            tw = gc.GetTextExtent('SYNC')[0]
            gc.DrawText('SYNC', cx - tw / 2.0, uikit.get_caps_top(font, y + TOOL_TOP,
                                                                  TOOL_HEIGHT))
            self.hits.append((wx.Rect(*rect), 'key', ('sync', 'player')))
        elif channel_id == MASTER[0]:
            tempo = control.GetGlobalTempo()
            rect = (int(x + 5), y + TOOL_TOP, STRIP_WIDTH - 10, TOOL_HEIGHT)
            hit = ('tempo', MASTER[0])
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(
                st.RACK_TEXT_COLOR if self.hovered == ('knob', hit) else st.RACK_EDGE_COLOR))
                .Width(1)))
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.LCD_BG_COLOR))))
            gc.DrawRoundedRectangle(rect[0] + 0.5, rect[1] + 0.5, rect[2] - 1, rect[3] - 1,
                                    uikit.RADIUS)
            gc.SetFont(get_font(uikit.MICRO, mono=True), colour(st.LCD_TEXT_COLOR))
            text = '--.--' if tempo is None else '%.2f' % tempo
            tw, th = gc.GetTextExtent(text)[:2]
            gc.DrawText(text, cx - tw / 2.0, y + TOOL_TOP + (TOOL_HEIGHT - th) / 2.0)
            self.hits.append((wx.Rect(*rect), 'knob', hit))
        # its mute and solo (the master: mute only)
        keys = [('mute', 'M')] + ([] if channel_id == MASTER[0]
                                  or channel_id in dict(RETURNS) else [('solo', 'S')])
        kx = cx - KEY_WIDTH * len(keys) / 2.0
        for k, (name, text) in enumerate(keys):
            corners = 'all' if len(keys) == 1 else ('left', 'right')[k]
            on = bool(spec[name])
            face_, ink = uikit.get_face(on=on, warn=on and name == 'mute',
                                        hover=self.hovered == ('key', (name, channel_id)))
            rect = (int(kx), y + KEYS_TOP, KEY_WIDTH, KEY_HEIGHT)
            uikit.draw_face(gc, rect, face_, corners=corners)
            font = get_font(uikit.MICRO, bold=True)
            gc.SetFont(font, ink)
            tw = gc.GetTextExtent(text)[0]
            gc.DrawText(text, kx + (KEY_WIDTH - tw) / 2.0,
                        uikit.get_caps_top(font, y + KEYS_TOP, KEY_HEIGHT))
            self.hits.append((wx.Rect(*rect), 'key', (name, channel_id)))
            kx += KEY_WIDTH
        # its fader: a scale at its left, a track, a cap where its turn is; its meter at its
        # right
        top = y + FADER_TOP
        tx = cx - 4
        gc.SetFont(get_font(8), colour(st.RACK_LABEL_COLOR))
        for db in SCALE:
            my = top + FADER_HEIGHT * (1.0 - db_to_turn(db))
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(st.RACK_EDGE_COLOR)).Width(1)))
            gc.StrokeLine(tx - 13, int(my) + 0.5, tx - 6, int(my) + 0.5)
            mark = '%d' % db if db else '0'
            mw, mh = gc.GetTextExtent(mark)[:2]
            gc.DrawText(mark, tx - 15 - mw, my - mh / 2.0)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.METER_OFF_COLOR))))
        gc.DrawRoundedRectangle(tx - 2, top, 4, FADER_HEIGHT, 2)
        turn = gain_to_turn(spec['gain'])
        capy = top + FADER_HEIGHT * (1.0 - turn) - CAP_HEIGHT / 2.0
        hit = ('fader', channel_id)
        face_, _ = uikit.get_face(hover=self.hovered == ('knob', hit) or self.IsDraggingFader(hit))
        uikit.draw_face(gc, (int(tx - CAP_WIDTH / 2.0), int(capy), CAP_WIDTH, CAP_HEIGHT),
                        face_)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(cap).Width(1)))
        gc.StrokeLine(tx - CAP_WIDTH / 2.0 + 3, int(capy + CAP_HEIGHT / 2.0) + 0.5,
                      tx + CAP_WIDTH / 2.0 - 4, int(capy + CAP_HEIGHT / 2.0) + 0.5)
        self.hits.append((wx.Rect(int(tx - CAP_WIDTH / 2.0 - 2), int(top - CAP_HEIGHT / 2.0),
                                  CAP_WIDTH + 4, int(FADER_HEIGHT + CAP_HEIGHT)), 'knob', hit))
        self.DrawMeter(gc, self.levels.get(channel_id, (0.0, 0.0)), tx + 14, top, tokens)
        # its gain in dB
        gc.SetFont(get_font(uikit.MICRO, mono=True), colour(st.LCD_TEXT_COLOR))
        text = format_db(spec['gain'])
        tw = gc.GetTextExtent(text)[0]
        gc.DrawText(text, cx - tw / 2.0, top + FADER_HEIGHT + 8)

    def DrawInserts(self, gc, control, channel_id, x, y, cap):
        '''its inserts' rows: an effect's name on an LCD (bypassed: dim), the one edited
        ringed in its colour, an empty one a +; the master's first Auto Master's'''
        st = self.parent.st
        rows = []
        if channel_id == MASTER[0]:
            rows.append(('auto', None))
        inserts = control.GetInserts(channel_id) if control.mixed else []
        rows += [('insert', (index, slot)) for index, slot in inserts]
        if len(rows) < INSERT_ROWS:
            rows.append(('empty', None))
        lcd = colour(st.LCD_BG_COLOR)
        for r, (kind, value) in enumerate(rows[:INSERT_ROWS]):
            ry = y + INSERT_TOP + r * (INSERT_HEIGHT + 2)
            rect = (x + 5, ry, STRIP_WIDTH - 10, INSERT_HEIGHT)
            if kind == 'auto':
                text, ink, hit = 'AUTO', st.LCD_TEXT_COLOR, None
                if not self.parent.IsLoudOn():
                    ink = st.RACK_LABEL_COLOR
            elif kind == 'insert':
                index, slot = value
                text = effects.SHORT[slot.GetEffect()]
                ink = st.RACK_LABEL_COLOR if slot.bypass else st.LCD_TEXT_COLOR
                hit = ('insert', (channel_id, index))
            else:
                text, ink, hit = '+', st.RACK_LABEL_COLOR, ('insert', (channel_id, None))
            edited = kind == 'insert' and self.editing == (channel_id, value[0])
            edge = cap if edited else (st.RACK_TEXT_COLOR if hit and self.hovered == hit
                                       else uikit.mix(lcd, (255, 255, 255), 0.12))
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(edge)).Width(1)))
            gc.SetBrush(gc.CreateBrush(wx.Brush(lcd)))
            gc.DrawRoundedRectangle(rect[0] + 0.5, rect[1] + 0.5, rect[2] - 1, rect[3] - 1,
                                    uikit.RADIUS)
            gc.SetFont(get_font(uikit.MICRO, bold=True), colour(ink))
            while len(text) > 1 and gc.GetTextExtent(text)[0] > rect[2] - 6:
                text = text[:-1]
            tw, th = gc.GetTextExtent(text)[:2]
            gc.DrawText(text, rect[0] + (rect[2] - tw) / 2.0, ry + (INSERT_HEIGHT - th) / 2.0)
            if hit is not None:
                self.hits.append((wx.Rect(*[int(v) for v in rect]), 'insert', hit[1]))

    def DrawEditor(self, gc, control, x, y, width):
        # the insert being edited: its channel's and its effect's names, BYPASS, REMOVE,
        # its knobs (MIX first, those with it)
        st = self.parent.st
        if width < 160:
            return
        slot = self.GetEditedSlot()
        if slot is None:
            gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
            gc.DrawText('EFFECT EDITOR', x, y + NAME_TOP)
            gc.SetFont(get_font(uikit.LABEL), colour(st.RACK_LABEL_COLOR))
            gc.DrawText('Pick an insert to edit it', x, y + INSERT_TOP + 4)
            return
        channel_id, index = self.editing
        cap = self.GetCapColour(channel_id)
        name = slot.GetEffect()
        label = dict(self.GetStrips() + self.GetReturns() + (MASTER,)).get(channel_id,
                                                                            channel_id)
        # its name and channel; BYPASS and REMOVE at the same row's right; a line in the
        # channel's colour under them
        gc.SetFont(get_font(13, bold=True), colour(st.RACK_TEXT_COLOR))
        title = effects.EFFECTS[name][0]
        tw, th = gc.GetTextExtent(title)[:2]
        gc.DrawText(title, x, y + NAME_TOP - 3)
        gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
        gc.DrawText('ON ' + label, x + tw + 8, y + NAME_TOP)
        kx = x + width - 2 * FX_KEY - 6
        for action, text, on in (('bypass', 'BYPASS', slot.bypass), ('remove', 'REMOVE', False)):
            hit = ('fxkey', action)
            face_, ink = uikit.get_face(on=on, warn=on, hover=self.hovered == hit)
            rect = (int(kx), y + NAME_TOP - 4, FX_KEY, KEY_HEIGHT)
            uikit.draw_face(gc, rect, face_)
            font = get_font(uikit.MICRO, bold=True)
            gc.SetFont(font, ink)
            mw = gc.GetTextExtent(text)[0]
            gc.DrawText(text, kx + (FX_KEY - mw) / 2.0,
                        uikit.get_caps_top(font, rect[1], KEY_HEIGHT))
            self.hits.append((wx.Rect(*rect), 'fxkey', action))
            kx += FX_KEY + 6
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(cap)))
        gc.DrawRectangle(x, y + NAME_TOP - 4 + KEY_HEIGHT + 5, width, 2)
        knobs = effects.get_knobs(name)
        # (a row of them, five at most, packed from the left: spread, they read as strays)
        per = min(len(knobs), 5)
        cell = min(width / float(per), EDITOR_CELL)
        values = effects.first_values(name)
        values.update(slot.params)
        for k, knob in enumerate(knobs):
            cx = x + cell * (k % per) + cell / 2.0
            cy = y + NAME_TOP + KEY_HEIGHT + 28 + EDITOR_KNOB + (k // per) * EDITOR_ROW
            hit = ('fx', knob[0])
            touched = self.hovered == ('knob', hit) or (self.drag is not None
                                                        and self.drag[0] == hit)
            self.DrawKnob(gc, cx, cy, min(max(effects.to_turn(knob, values[knob[0]]), 0.0), 1.0),
                          touched, radius=EDITOR_KNOB, tint=cap, ticks=11)
            for line, font, ink, dy in (
                    (effects.format_value(knob, values[knob[0]]),
                     get_font(uikit.MICRO, mono=True), st.LCD_TEXT_COLOR, 9),
                    (knob[1], get_font(uikit.MICRO, bold=True), st.RACK_LABEL_COLOR, 21)):
                gc.SetFont(font, colour(ink))
                tw = gc.GetTextExtent(line)[0]
                gc.DrawText(line, cx - tw / 2.0, cy + EDITOR_KNOB + dy)
            self.hits.append((wx.Rect(int(cx - cell / 2.0), int(cy - EDITOR_KNOB - 8),
                                      int(cell), EDITOR_ROW - 4), 'knob', hit))

    def DrawMeter(self, gc, levels, x, top, tokens):
        # left and right, in the rack's segments (uikit.METER_*), lit from the bottom
        st = self.parent.st
        unit = uikit.METER_SEGMENT + uikit.METER_GAP
        count = int(FADER_HEIGHT // unit)
        for side, level in enumerate(levels):
            lit = self.GetLit(level, count)
            bx = x + side * (uikit.METER_BAR + 2)
            for k in range(count):
                sy = top + FADER_HEIGHT - (k + 1) * unit + uikit.METER_GAP
                at = METER_LOW + (k + 0.5) / count * (METER_HIGH - METER_LOW)
                if k < lit:
                    fill = tokens.WARN if at > METER_WARN else tokens.ACCENT
                else:
                    fill = st.METER_OFF_COLOR
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(fill))))
                gc.DrawRectangle(bx, sy, uikit.METER_BAR, uikit.METER_SEGMENT)

    # the insert edited

    def GetEditedSlot(self):
        control = self.GetControl()
        if self.editing is None or control is None:
            return None
        channel_id, index = self.editing
        chain = control.GetInsertChain(channel_id)
        if chain is None or index >= len(chain.slots) or not chain.slots[index].GetEffect():
            self.editing = None
            return None
        return chain.slots[index]

    def ShowInsertMenu(self, channel_id, index):
        # an empty row's: an effect to put in; one's: another effect, bypass, remove
        control = self.GetControl()
        menu = wx.Menu()
        effects_menu = menu if index is None else wx.Menu()
        for name in effects.ORDER:
            item = effects_menu.Append(wx.ID_ANY, effects.EFFECTS[name][0].title())
            self.Bind(wx.EVT_MENU, lambda event, name=name: self.PutEffect(
                channel_id, index, name), item)
        if index is not None:
            menu.AppendSubMenu(effects_menu, 'Effect')
            chain = control.GetInsertChain(channel_id)
            slot = chain.slots[index]
            item = menu.AppendCheckItem(wx.ID_ANY, 'Bypass')
            item.Check(slot.bypass)
            self.Bind(wx.EVT_MENU, lambda event: self.Bypass(channel_id, index), item)
            item = menu.Append(wx.ID_ANY, 'Remove')
            self.Bind(wx.EVT_MENU, lambda event: self.RemoveInsert(channel_id, index), item)
        self.PopupMenu(menu)
        menu.Destroy()
        self.Repaint()

    def PutEffect(self, channel_id, index, name):
        control = self.GetControl()
        if index is None:
            slot = control.AddInsert(channel_id, name)
            if slot is not None:
                chain = control.GetInsertChain(channel_id)
                self.editing = (channel_id, chain.slots.index(slot))
        else:
            control.SetInsertEffect(channel_id, index, name)
            self.editing = (channel_id, index)
        self.Repaint()

    def Bypass(self, channel_id, index):
        control = self.GetControl()
        chain = control.GetInsertChain(channel_id)
        chain.slots[index].SetBypass(not chain.slots[index].bypass)
        control.KeepInserts(channel_id)
        self.Repaint()

    def RemoveInsert(self, channel_id, index):
        self.GetControl().RemoveInsert(channel_id, index)
        if self.editing == (channel_id, index):
            self.editing = None
        self.Repaint()

    # handled

    def IsDragging(self):
        return self.drag is not None

    def IsDraggingFader(self, hit):
        return self.drag is not None and self.drag[0] == hit

    def GetTempo(self):
        control = self.GetControl()
        tempo = control.GetGlobalTempo()
        return tempo if tempo is not None else (control.GetDeckTempo() or control.FREE_BPM)

    def GetTurn(self, hit):
        kind, key = hit
        if kind == 'tempo':
            return self.GetTempo()
        if kind == 'fx':
            slot = self.GetEditedSlot()
            if slot is None:
                return None
            knob = dict((k[0], k) for k in effects.get_knobs(slot.GetEffect()))[key]
            values = effects.first_values(slot.GetEffect())
            values.update(slot.params)
            return effects.to_turn(knob, values[key])
        if kind == 'send':
            return self.GetControl().GetSend(*key)
        spec = self.GetControl().GetChannel(key)
        if kind == 'pan':
            return (spec['pan'] + 1.0) / 2.0
        return gain_to_turn(spec['gain'])

    def SetTurn(self, hit, turn):
        kind, key = hit
        control = self.GetControl()
        if kind == 'tempo':
            # (a turn here: BPM)
            control.SetGlobalTempo(turn, keep=False)
            return
        turn = min(max(turn, 0.0), 1.0)
        if kind == 'fx':
            slot = self.GetEditedSlot()
            if slot is not None:
                knob = dict((k[0], k) for k in effects.get_knobs(slot.GetEffect()))[key]
                slot.SetParam(key, effects.from_turn(knob, turn))
            return
        if kind == 'send':
            control.SetSend(key[0], key[1], turn)
            return
        if kind == 'pan':
            pan = turn * 2.0 - 1.0
            # (held at the centre near it)
            control.SetChannel(key, pan=0.0 if abs(pan) < 0.02 else pan)
        else:
            control.SetChannel(key, gain=turn_to_gain(turn))

    def KeepTurn(self, hit):
        control = self.GetControl()
        if hit[0] == 'fx':
            if self.editing is not None:
                control.KeepInserts(self.editing[0])
        elif hit[0] in ('tempo', 'send'):
            control.KeepTempo()
        else:
            control.KeepChannels()

    def HandleDrag(self, event):
        # a pan or an effect's knob by an up or down drag (shift finer), a fader as the
        # mouse moves, the tempo; till let go: kept then
        if self.drag is None:
            return False
        if event.LeftIsDown:
            hit, y0, turn0 = self.drag
            if hit[0] == 'tempo':
                self.SetTurn(hit, turn0 + (y0 - event.y) * TEMPO_DRAG)
                self.Repaint()
                return True
            if hit[0] == 'fader':
                travel = float(FADER_HEIGHT)
            elif hit[0] == 'fx':
                travel = FX_DRAG
            else:
                travel = float(KNOB_DRAG)
            if getattr(event, 'ShiftDown', False):
                travel /= FX_FINE
            turn = min(max(turn0 + (y0 - event.y) / travel, 0.0), 1.0)
            self.drag = (hit, event.y, turn)
            self.SetTurn(hit, turn)
            self.Repaint()
        else:
            hit, y0, _ = self.drag
            self.drag = None
            self.KeepTurn(hit)
            if hit[0] == 'tempo' and abs(event.y - y0) < 2:
                # a click (no drag): typed in, unless a double click follows
                self.CancelEdit()
                self.edit_later = wx.CallLater(EDIT_AFTER_MS, self.EditTempo)
            self.Repaint()
        return True

    def CancelEdit(self):
        later = getattr(self, 'edit_later', None)
        if later is not None and later.IsRunning():
            later.Stop()
        self.edit_later = None

    def EditTempo(self):
        '''the global tempo typed: a field over its box, Enter (or leaving it) sets it,
        Esc leaves it as it was'''
        self.edit_later = None
        rects = [rect for rect, kind, key in self.hits if key == ('tempo', MASTER[0])]
        if not rects or getattr(self, 'editor', None):
            return
        st = self.parent.st
        rect = rects[0]
        editor = wx.TextCtrl(self, pos=rect.GetPosition(), size=rect.GetSize(),
                             style=wx.TE_PROCESS_ENTER | wx.TE_CENTRE | wx.BORDER_NONE)
        editor.SetBackgroundColour(colour(st.LCD_BG_COLOR))
        editor.SetForegroundColour(colour(st.LCD_TEXT_COLOR))
        editor.SetFont(get_font(uikit.MICRO + 1, mono=True))
        editor.SetValue('%.2f' % self.GetTempo())
        editor.SelectAll()
        editor.SetFocus()
        self.editor = editor
        editor.Bind(wx.EVT_TEXT_ENTER, lambda event: self.EndEdit(True))
        editor.Bind(wx.EVT_KILL_FOCUS, lambda event: (event.Skip(), self.EndEdit(True)))
        editor.Bind(wx.EVT_CHAR_HOOK, self.OnEditKey)

    def OnEditKey(self, event):
        # its keys its own: typed in it, not passed on to the player's shortcuts (a 1
        # typed played a cue)
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndEdit(False)
            return
        event.DoAllowNextEvent()

    def EndEdit(self, apply):
        editor = getattr(self, 'editor', None)
        if editor is None:
            return
        self.editor = None
        text = editor.GetValue().strip().replace(',', '.')
        wx.CallAfter(editor.Destroy)
        if apply:
            try:
                bpm = float(text)
            except ValueError:
                bpm = None
            if bpm is not None and bpm > 0:
                self.GetControl().SetGlobalTempo(bpm)
        self.Repaint()

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False or self.GetControl() is None:
            return
        hit = self.GetHit(wx.Point(int(event.X), int(event.Y)))
        if hit is None or hit[0] != 'knob':
            return
        up = event.WheelRotation > 0
        if hit[1][0] == 'tempo':
            self.SetTurn(hit[1], self.GetTurn(hit[1]) + (TEMPO_WHEEL if up else -TEMPO_WHEEL))
        else:
            turn = self.GetTurn(hit[1])
            if turn is None:
                return
            step = KNOB_WHEEL * (FX_FINE if getattr(event, 'ShiftDown', False) else 1.0)
            self.SetTurn(hit[1], turn + (step if up else -step))
        self.KeepTurn(hit[1])
        self.Repaint()

    def HandleHit(self, event, hit):
        control = self.GetControl()
        if control is None:
            return
        kind, value = hit
        if event.RightDown and kind == 'insert':
            self.ShowInsertMenu(*value)
            return
        if event.LeftDClick and kind == 'knob':
            # a fader at 0 dB, a pan at the centre, an effect's knob at its first value,
            # the global tempo the deck's
            if value[0] == 'tempo':
                self.CancelEdit()
                deck = control.GetDeckTempo()
                if deck is not None:
                    control.SetGlobalTempo(deck)
            elif value[0] == 'fx':
                slot = self.GetEditedSlot()
                if slot is not None:
                    slot.SetParam(value[1], effects.first_values(slot.GetEffect())[value[1]])
            elif value[0] == 'send':
                self.SetTurn(value, 0.0)
            else:
                self.SetTurn(value, gain_to_turn(1.0) if value[0] == 'fader' else 0.5)
            self.drag = None
            self.KeepTurn(value)
            self.Repaint()
            return
        # (a quick second click: a double click only, pressed as the first was)
        if event.LeftDown is False and event.LeftDClick is False:
            return
        if kind == 'knob':
            turn = self.GetTurn(value)
            if turn is not None:
                self.drag = (value, event.y, turn)
        elif kind == 'insert':
            channel_id, index = value
            if index is None:
                self.ShowInsertMenu(channel_id, None)
            else:
                self.editing = (channel_id, index)
        elif kind == 'fxkey':
            if self.editing is not None:
                channel_id, index = self.editing
                if value == 'bypass':
                    self.Bypass(channel_id, index)
                else:
                    self.RemoveInsert(channel_id, index)
        elif kind == 'key':
            name, channel_id = value
            if name == 'sync':
                control.SetDeckSync(not control.IsDeckSync())
            else:
                control.SetChannel(channel_id,
                                   **{name: not control.GetChannel(channel_id)[name]})
                control.KeepChannels()
        self.Repaint()
