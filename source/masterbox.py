# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import master
import math
import uikit
import wx

from rackbox import KNOB_DRAG
from rackbox import KNOB_RADIUS
from rackbox import KNOB_WHEEL
from rackbox import RackModule
from rackbox import colour
from rackbox import get_font


# MASTER's module in the rack (rackbox), a plug-in's plate: its header (whether it works,
# A/B), the levels (segmented meters with their readouts) and the controls (LED switches and
# knobs in the plugin's three sections); shown from the MASTER row's arrow; kept
# (master_panel)
METERS = 42
CONTROLS = 118
# (key, label, low, high, kind): kind 'level' (lit from the low end), 'reduce' (from 0
# down to low, in the warning colour), 'gain' (from low)
METER_SPECS = (('loudness', 'LOUDNESS IN', -40.0, 0.0, 'level'),
               ('agc', 'AGC GAIN', -12.0, 18.0, 'gain'),
               ('limiter', 'LIMITER', -12.0, 0.0, 'reduce'),
               ('side', 'WIDTH', -12.0, 0.0, 'reduce'),
               ('output', 'OUTPUT PEAK', -40.0, 0.0, 'level'))


class MasterPanel(RackModule):

    TITLE = 'AUTO MASTER'
    PREFERENCE = 'master_panel'
    PARTS = (('meters', 'METERS', METERS), ('controls', 'CONTROLS', CONTROLS))

    def __init__(self, parent):
        self.drag = None
        self.levels = None
        self.compact = False
        RackModule.__init__(self, parent)

    # what it shows

    def IsActive(self):
        # MASTER on (not passed by); not known while the player is being made
        return hasattr(self.parent, 'cue') and self.parent.IsLoudOn()

    def GetVst(self):
        control = getattr(self.parent, 'AudioControl', None)
        return control.vstHandle if control is not None else 0

    def ReadLevels(self):
        # (nothing sounding: none, its meters at rest; read on, they held their last)
        if self.parent.IsVisualPlaying() is False:
            return None
        levels = master.METERS.Read() if self.IsActive() else None
        if levels is not None and self.parent.IsVisualPlaying():
            levels['output'] = master.get_output_db(self.parent.GetVisualStream()[0])
        return levels

    def GetState(self):
        if master.METERS.IsCompared():
            return ('A/B: ORIGINAL', True)
        return ('ACTIVE' if self.IsActive() else 'BYPASSED', False)

    def GetChips(self):
        # A/B: the original at the same loudness, warned while it is heard
        return [('ab', 'A/B', master.METERS.IsCompared(), True)]

    def OnChip(self, key):
        if key == 'ab':
            master.METERS.SetCompared(not master.METERS.IsCompared())
            self.reInitBuffer = True

    # drawn

    # narrower than this, its labels and readouts a step smaller (uikit.MICRO): the stereo
    # section's five switches, the knobs' readouts and the meters' names did not fit at 700
    COMPACT_WIDTH = 860

    def LabelFont(self):
        return get_font(uikit.MICRO if self.compact else uikit.LABEL, bold=True)

    def ReadoutFont(self):
        return get_font(uikit.MICRO + 1 if self.compact else uikit.READOUT, mono=True)

    def DrawPart(self, gc, key, x, y, width):
        self.compact = width < self.COMPACT_WIDTH
        if key == 'meters':
            self.levels = self.ReadLevels()
            self.DrawMeters(gc, x, y, width)
        elif key == 'controls':
            self.DrawControls(gc, x, y, width)

    def DrawMeters(self, gc, x, y, width):
        st = self.parent.st
        tokens = uikit.ui()
        levels = self.levels
        # a row of them, or METERS_A_ROW a row when narrow
        count = self.GetMeterCount(width)
        gap = 14
        cell = (width - gap * (count - 1)) / float(count)
        top = y
        for k, (key, label, low, high, kind) in enumerate(METER_SPECS):
            cx = x + (k % count) * (cell + gap)
            y = top + (k // count) * METERS
            value = None if levels is None else levels.get(key)
            text = '--'
            if value is not None:
                unit = 'LUFS' if key == 'loudness' else 'dB'
                text = '%+.1f %s' % (value, unit) if kind == 'gain' else '%.1f %s' % (value, unit)
            # the readout on a display's ground, at the cell's right
            gc.SetFont(self.ReadoutFont(), colour(st.LCD_TEXT_COLOR))
            tw, th = gc.GetTextExtent(text)[:2]
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.LCD_BG_COLOR))))
            gc.DrawRoundedRectangle(cx + cell - tw - 10, y + 3, tw + 10, th + 4, uikit.RADIUS)
            # its name left of the readout, cut where it would run under it
            gc.Clip(cx, y, max(cell - tw - 16, 1), 24)
            gc.SetFont(self.LabelFont(), colour(st.RACK_LABEL_COLOR))
            gc.DrawText(label, cx, y + 6)
            gc.ResetClip()
            gc.SetFont(self.ReadoutFont(), colour(st.LCD_TEXT_COLOR))
            gc.DrawText(text, cx + cell - tw - 5, y + 5)
            # the segments: lit from where the kind starts
            share = 0.0
            if value is not None:
                if kind == 'reduce':
                    share = min(max(value / low, 0.0), 1.0)
                else:
                    share = min(max((value - low) / (high - low), 0.0), 1.0)
            segment, spacing = uikit.METER_SEGMENT, uikit.METER_GAP
            n = max(int((cell + spacing) / (segment + spacing)), 1)
            lit = int(round(share * n))
            for s in range(n):
                on = s < lit
                hot = kind == 'reduce' or (key == 'output' and s >= n - 2)
                if on:
                    fill = colour(tokens.WARN if hot else tokens.ACCENT)
                else:
                    fill = colour(st.METER_OFF_COLOR)
                gc.SetBrush(gc.CreateBrush(wx.Brush(fill)))
                # (as tall as OUT's: its bottom where the 8 rows' was)
                gc.DrawRectangle(int(cx) + s * (segment + spacing), y + 30, segment,
                                 uikit.METER_BAR)

    # a section's switches a row more each when they do not fit its width (a small
    # window): the knobs under them, the part as much taller
    SWITCH_ROW = 21
    # the Stereo section's five switches need the most room (half of it)
    WEIGHTS = (3.0, 6.0, 3.0)

    def GetSections(self):
        return [(group, [v for v in master.PARAMS if v[2] == group]) for group in master.GROUPS]

    def GetSwitchWidth(self, gc, name, compact):
        # the LED (6 px) 5 px in, 6 px to the name (4 was cramped), 7 px after it (compact:
        # 5 after the name, 3 between: the LED's 6 to the name kept)
        gc.SetFont(get_font(uikit.MICRO if compact else uikit.LABEL, bold=True), wx.BLACK)
        return 5 + 6 + 6 + gc.GetTextExtent(name.upper())[0] + (5 if compact else 7)

    def GetSwitchRows(self, width):
        # the most rows a section's switches take at this inner width
        compact = width < self.COMPACT_WIDTH
        key = (int(width), compact)
        if getattr(self, 'rows_cache', (None,))[0] == key:
            return self.rows_cache[1]
        bitmap = wx.Bitmap(1, 1)
        dc = wx.MemoryDC(bitmap)
        gc = wx.GraphicsContext.Create(dc)
        total = float(sum(self.WEIGHTS))
        most = 1
        for k, (group, params) in enumerate(self.GetSections()):
            room = width * self.WEIGHTS[k] / total - 12
            rows, used = 1, 0
            for index, name, _, kind in params:
                if kind != 'switch':
                    continue
                rw = self.GetSwitchWidth(gc, name, compact)
                if used and used + rw > room:
                    rows, used = rows + 1, 0
                used += rw + (3 if compact else 4)
            most = max(most, rows)
        del gc
        dc.SelectObject(wx.NullBitmap)
        self.rows_cache = (key, most)
        return most

    # the knobs' least cell (their readouts, -16.0 LUFS, ran into each other under it) and
    # a row of them; the meters' least cell (a name and a readout side by side), 3 a row
    # under it
    # (compact, the readouts a step smaller: 52)
    KNOB_LEAST = 64
    KNOB_LEAST_COMPACT = 52
    KNOB_ROW = 58
    METER_LEAST = 128
    METERS_A_ROW = 3

    def GetKnobsARow(self, room, count, width=None):
        compact = (width if width is not None else room * 4) < self.COMPACT_WIDTH
        least = self.KNOB_LEAST_COMPACT if compact else self.KNOB_LEAST
        return max(1, min(count, int(room // least)))

    def GetKnobRows(self, width):
        total = float(sum(self.WEIGHTS))
        most = 1
        for k, (group, params) in enumerate(self.GetSections()):
            count = len([v for v in params if v[3] == 'knob'])
            if count:
                per = self.GetKnobsARow(width * self.WEIGHTS[k] / total - 12, count, width)
                most = max(most, -(-count // per))
        return most

    def GetMeterCount(self, width):
        # the meters a row
        count = len(METER_SPECS)
        cell = (width - 14 * (count - 1)) / float(count)
        return count if cell >= self.METER_LEAST else self.METERS_A_ROW

    def GetPartHeight(self, key, height):
        width = self.parent.GetClientSize().width - 16
        if key == 'meters':
            per = self.GetMeterCount(width)
            return height * -(-len(METER_SPECS) // per)
        if key != 'controls':
            return height
        return height + (self.GetSwitchRows(width) - 1) * self.SWITCH_ROW\
            + (self.GetKnobRows(width) - 1) * self.KNOB_ROW

    def DrawControls(self, gc, x, y, width):
        # the plugin's sections side by side, as wide as their knobs and switches need
        st = self.parent.st
        values = master.get_values()
        extra = (self.GetSwitchRows(width) - 1) * self.SWITCH_ROW
        self.inner_width = width
        total = float(sum(self.WEIGHTS))
        left = x
        for k, (group, params) in enumerate(self.GetSections()):
            sw = width * self.WEIGHTS[k] / total
            if k:
                gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
                bottom = y + CONTROLS + extra + (self.GetKnobRows(width) - 1) * self.KNOB_ROW
                gc.StrokeLine(left - 6.5, y + 8, left - 6.5, bottom - 8)
            self.DrawSection(gc, group, params, values, left, y, sw - 12, extra)
            left += sw

    def DrawSection(self, gc, group, params, values, x, y, width, extra=0):
        st = self.parent.st
        tokens = uikit.ui()
        gc.SetFont(self.LabelFont(), colour(st.RACK_LABEL_COLOR))
        gc.DrawText(group.upper(), x, y + 7)
        # the switches: an LED (lit, or a ring) and its name
        sx, sy = x, y + 24
        font = self.LabelFont()
        for index, name, _, kind in params:
            if kind != 'switch':
                continue
            label = name.upper()
            size = 6
            rw = self.GetSwitchWidth(gc, name, self.compact)
            if sx + rw > x + width and sx > x:
                # a row more (GetSwitchRows counted it)
                sx, sy = x, sy + self.SWITCH_ROW
            on = master.is_on(values[index])
            hovered = self.hovered == ('switch', index)
            # a hardware key (uikit.draw_face), lighter under the mouse
            face = colour(st.KNOB_RING_COLOR if hovered else st.KNOB_FACE_COLOR)
            uikit.draw_face(gc, (sx, sy, rw, 17), face)
            if on:
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(tokens.ACCENT))))
            else:
                gc.SetPen(wx.Pen(colour(st.RACK_LABEL_COLOR), 1))
                gc.SetBrush(wx.NullGraphicsBrush)
            # the LED's middle on the chip's 17 rows (16 and its border), where the capitals'
            # is: drawn from a whole row (the renderer puts shapes half a pixel down, so from
            # half a row it was lit heavier at the bottom: measured 97 against 54)
            gc.DrawEllipse(sx + 5, sy + 5, size, size)
            gc.SetFont(font, colour(st.RACK_TEXT_COLOR if on else st.RACK_LABEL_COLOR))
            gc.DrawText(label, sx + 5 + size + 6, uikit.get_caps_top(font, sy, 17))
            self.hits.append((wx.Rect(int(sx), int(sy), int(rw), 16), 'switch', index))
            sx += rw + (3 if self.compact else 4)
        # the knobs: a ring of the range, the value's arc in the accent, its readout and
        # name under it
        knobs = [v for v in params if v[3] == 'knob']
        if not knobs:
            return
        # a row more when they do not fit (GetKnobRows counted it)
        per = self.GetKnobsARow(width, len(knobs), self.inner_width)
        cell = min(width / float(per), 86)
        for k, (index, name, _, _) in enumerate(knobs):
            cx = x + cell * (k % per) + cell / 2.0
            # 9 px under the switches' row to the knob's arc (3 was cramped); under their
            # rows more
            cy = y + 64 + extra + (k // per) * self.KNOB_ROW
            self.DrawKnob(gc, cx, cy, values[index], self.hovered == ('knob', index))
            text = master.PROBE.Text(index, values[index])
            gc.SetFont(self.ReadoutFont(), colour(st.LCD_TEXT_COLOR))
            tw = gc.GetTextExtent(text)[0]
            gc.DrawText(text, cx - tw / 2.0, cy + KNOB_RADIUS + 4)
            gc.SetFont(self.LabelFont(), colour(st.RACK_LABEL_COLOR))
            label = name.upper()
            tw = gc.GetTextExtent(label)[0]
            gc.DrawText(label, cx - tw / 2.0, cy + KNOB_RADIUS + 19)
            self.hits.append((wx.Rect(int(cx - cell / 2.0), int(cy - KNOB_RADIUS - 4),
                                      int(cell), KNOB_RADIUS * 2 + 36), 'knob', index))

    # handled

    def SetValue(self, index, value):
        master.set_value(index, value, (self.GetVst(),))
        self.reInitBuffer = True

    def IsDragging(self):
        return self.drag is not None

    def HandleDrag(self, event):
        # a knob turned by an up or down drag until the button is let go
        if self.drag is None:
            return False
        if event.LeftIsDown:
            index, y0, v0 = self.drag
            self.SetValue(index, min(max(v0 + (y0 - event.y) / float(KNOB_DRAG), 0.0), 1.0))
        else:
            self.drag = None
        return True

    def HandleHit(self, event, hit):
        kind, key = hit
        if event.LeftDClick and kind == 'knob':
            # its first value back
            self.SetValue(key, master.DEFAULTS[key])
            return
        # (a quick second click: a double click only, pressed as the first was)
        if event.LeftDown is False and event.LeftDClick is False:
            return
        if kind == 'switch':
            value = master.get_values()[key]
            self.SetValue(key, 0.0 if master.is_on(value) else 1.0)
        elif kind == 'knob':
            self.drag = (key, event.y, master.get_values()[key])

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        hit = self.GetHit(wx.Point(int(event.X), int(event.Y)))
        if hit is None or hit[0] != 'knob':
            return
        step = KNOB_WHEEL if event.WheelRotation > 0 else -KNOB_WHEEL
        self.SetValue(hit[1], min(max(master.get_values()[hit[1]] + step, 0.0), 1.0))
