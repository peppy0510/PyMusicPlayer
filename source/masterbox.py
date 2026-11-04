# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import master
import math
import uikit
import wx

from rackbox import HEADER
from rackbox import KNOB_DRAG
from rackbox import KNOB_RADIUS
from rackbox import KNOB_WHEEL
from rackbox import RackModule
from rackbox import colour
from rackbox import draw_rule
from rackbox import get_font


# master module in the rack: header, then the plugin's three sections
CONTROLS = 118
# meters band: (key, label, low, high, kind)
# no loudness in: the agc gain says it
BAND_METERS = (('agc', 'AGC', -12.0, 18.0, 'gain'),
               ('side', 'WIDTH', -12.0, 0.0, 'reduce'),
               ('balance', 'BALANCE', -6.0, 6.0, 'bipolar'),
               ('phase', 'PHASE', -2.0, 2.0, 'phase'),
               ('limiter', 'LIMITER', -12.0, 0.0, 'reduce'),
               (0, 'LOW 150\u2013600', -30.0, 0.0, 'band'),
               (1, 'MID 600\u20133K', -30.0, 0.0, 'band'),
               (2, 'HIGH 3K+', -30.0, 0.0, 'band'))

class MasterPanel(RackModule):

    TITLE = 'MASTER'
    PREFERENCE = 'master_panel'
    PARTS = (('controls', 'CONTROLS', CONTROLS),)

    def __init__(self, parent):
        self.drag = None
        self.levels = None
        self.compact = False
        RackModule.__init__(self, parent)
        # always there: folded, its header is the rack bar
        self.shown = True

    def Toggle(self):
        self.ToggleFold()

    def ToggleFold(self):
        RackModule.ToggleFold(self)
        menu = getattr(wx.GetTopLevelParent(self), 'MenuBar', None)
        item = getattr(menu, 'itemMasterShow', None)
        if item is not None:
            item.Check(not self.folded)

    # what it shows

    def IsActive(self):
        # not known while the player is being made
        return hasattr(self.parent, 'cue') and self.parent.IsLoudOn()

    # power key: master on or off
    POWER = True

    def OnPower(self):
        if self.parent.IsLoudOn():
            self.parent.SetLoudOff()
        else:
            self.parent.SetLoudOn()
        # stopped: nothing redraws it next frame
        self.reInitBuffer = True

    def GetVst(self):
        control = getattr(self.parent, 'AudioControl', None)
        return control.vstHandle if control is not None else 0

    def ReadLevels(self):
        # nothing sounding: meters at rest
        if self.parent.IsVisualPlaying() is False:
            return None
        return master.METERS.Read(self.GetVst()) if self.IsActive() else None

    def GetState(self):
        if not self.IsActive():
            return ('BYPASSED', False)
        if master.METERS.IsCompared():
            return ('A/B: ORIGINAL', True)
        # small agc and limiter meters in place of ACTIVE
        if self.IsSummaryShown():
            return None
        return ('ACTIVE', False)

    # header meters, each its name and a bar
    # the plugin's three stages in order
    SUMMARY = (('agc', 'AGC', -12.0, 18.0, 'gain'), ('side', 'STEREO', -12.0, 0.0, 'reduce'),
               ('limiter', 'LIM', -12.0, 0.0, 'reduce'))
    # bar width shrinks with the window
    SUMMARY_BAR = 40
    SUMMARY_LEAST = 18

    def GetSummaryBar(self):
        width = self.GetSize().width or self.GetLayoutWidth()
        return int(max(self.SUMMARY_LEAST, min(self.SUMMARY_BAR, (width - 400) / 4.0)))

    def IsSummaryShown(self):
        return self.IsActive() and not master.METERS.IsCompared()

    def GetSummaryWidth(self, dc):
        if not self.IsSummaryShown():
            return 0
        dc.SetFont(get_font(uikit.LABEL, bold=True))
        names = sum(dc.GetTextExtent(spec[1])[0] for spec in self.SUMMARY)
        each = 6 + self.GetSummaryBar()
        return names + each * len(self.SUMMARY) + 14 * (len(self.SUMMARY) - 1)

    def DrawSummary(self, gc, x, cy):
        st = self.parent.st
        self.levels = self.ReadLevels()
        label = get_font(uikit.LABEL, bold=True)
        bar = self.GetSummaryBar()
        for spec in self.SUMMARY:
            key, name, low, high, kind = spec
            uikit.set_font(gc, label, colour(st.RACK_LABEL_COLOR))
            text_y, bar_y = self.GetSmallTextRows(label, uikit.METER_BAR)
            gc.DrawText(name, x, text_y)
            x += gc.GetTextExtent(name)[0] + 6
            reading = self.GetMeterValue(spec)
            tone = None if kind == 'gain' else uikit.METER_TONES[1][1]
            share = 0.0 if reading is None else reading[2]
            uikit.draw_meter(gc, x, bar_y, bar,
                             uikit.METER_BAR, share, st.RACK_BG_COLOR, low, high, tone=tone)
            x += bar + 14

    # header right: A/B, out meter, volume
    OUT_GAP = 8
    # one bar for both channels (the louder)
    METER_LEAST = 18
    METER_LOW = -48.0

    def PlaceVolume(self, x, y):
        # move at once or the volume shakes while sizing
        if (x, y) != getattr(self, 'volume_at', None):
            self.volume_at = (x, y)
            volume = getattr(self.parent, 'VolumeSlider', None)
            if volume is not None:
                volume.OnSize()

    def Place(self, y, width):
        # volume placed with the module in the same step
        RackModule.Place(self, y, width)
        volume = getattr(self.parent, 'VolumeSlider', None)
        if volume is not None:
            self.PlaceVolume(width - 8 - volume.LENGTH, (HEADER - volume.HEIGHT) // 2)
            volume.OnSize()

    def DrawSeparator(self, gc, x):
        gc.SetPen(wx.Pen(colour(self.parent.st.RACK_EDGE_COLOR), 1))
        gc.StrokeLine(x + 0.5, 8, x + 0.5, HEADER - 8)

    def DrawHeaderRight(self, gc, w, least):
        right = w - 8
        volume = getattr(self.parent, 'VolumeSlider', None)
        if volume is not None:
            self.PlaceVolume(right - volume.LENGTH, (HEADER - volume.HEIGHT) // 2)
            right -= volume.LENGTH + self.OUT_GAP
            self.DrawSeparator(gc, right)
            right -= self.OUT_GAP
        start = self.DrawOut(gc, least, right)
        if start < right:
            right = start - self.OUT_GAP
            self.DrawSeparator(gc, right)
            right -= self.OUT_GAP
        return right

    def DrawOut(self, gc, left, right):
        '''output meter: OUT and a small bar; returns where it starts'''
        analyzer = getattr(self.parent, 'Analyzer', None)
        if analyzer is None:
            return right
        a = analyzer.analyzer
        st = self.parent.st
        label = get_font(uikit.LABEL, bold=True)
        uikit.set_font(gc, label, colour(st.RACK_LABEL_COLOR))
        lw = gc.GetTextExtent('OUT')[0]
        width = int(max(self.METER_LEAST, min(self.GetSummaryBar(),
                                              right - lw - self.OUT_GAP - left)))
        bx = right - width
        if bx - self.OUT_GAP - lw < left:
            return right
        segment, spacing, bar = uikit.METER_SEGMENT, uikit.METER_GAP, uikit.METER_BAR
        count = int((width + spacing) / (segment + spacing))
        # on whole pixels, the last against the right
        bx = int(bx + width - (count * (segment + spacing) - spacing))
        text_y, top = self.GetSmallTextRows(label, uikit.METER_BAR)
        gc.DrawText('OUT', bx - self.OUT_GAP - lw, text_y)
        span = count * (segment + spacing) - spacing
        peak = max(a.peak[0], a.peak[1])
        share = max(min((peak - self.METER_LOW) / -self.METER_LOW, 1.0), 0.0)
        uikit.draw_meter(gc, bx, top, span, bar, share, st.RACK_BG_COLOR, self.METER_LOW)
        return int(bx - self.OUT_GAP - lw)

    # each section's stage key bypasses that stage
    STAGES = dict(AGC='agc', Stereo='stereo', Limiter='limiter')

    def GetChips(self):
        # A/B: the original at the same loudness
        return [('ab', 'A/B', self.IsActive() and master.METERS.IsCompared(), True)]

    def IsChipEnabled(self, key):
        return key != 'ab' or self.IsActive()

    def OnChip(self, key):
        if key == 'ab' and self.IsChipEnabled(key):
            master.METERS.SetCompared(not master.METERS.IsCompared())
            self.reInitBuffer = True

    # drawn

    # narrower than this, labels and readouts a step smaller
    COMPACT_WIDTH = 860

    def LabelFont(self):
        return get_font(uikit.MICRO if self.compact else uikit.LABEL, bold=True)

    def ReadoutFont(self):
        return get_font(uikit.MICRO + 1 if self.compact else uikit.READOUT, mono=True)

    def DrawPart(self, gc, key, x, y, width):
        self.compact = width < self.COMPACT_WIDTH
        if key == 'controls':
            self.levels = self.ReadLevels()
            self.DrawControls(gc, x, y, width)

    # sections side by side, or stacked when they do not fit
    SWITCH_ROW = 21
    # key and switches KEY_TOP under the section top
    KEY_TOP = 6
    SECTION_TOP = 36
    # a line over the sections, each this much under it
    STACK_PAD = 6
    SECTION_GAP = 12
    SECTION_BOTTOM = 8
    # meters band: PAD over and under, GAP between meters
    BAND_PAD = 8
    BAND_GAP = 24
    BAR_LEAST = 48
    # a meter cell at most
    BAND_CELL_MOST = 240

    def GetSections(self):
        # params without the stage's own switch
        own = set(indexes[0] for indexes in master.STAGE_SWITCHES.values()
                  if len(indexes) == 1)
        return [(group, [v for v in master.PARAMS if v[2] == group and v[0] not in own])
                for group in master.GROUPS]

    def GetSwitchWidth(self, gc, name, compact):
        # led 5 px in, 6 px to the name
        uikit.set_font(gc, get_font(uikit.MICRO if compact else uikit.LABEL, bold=True), wx.BLACK)
        return 5 + 6 + 6 + gc.GetTextExtent(name.upper())[0] + (5 if compact else 7)

    # least knob cell so readouts do not overlap
    KNOB_LEAST = 64
    KNOB_LEAST_COMPACT = 52
    # knob row height
    KNOB_ROW = 70

    # side by side: switches per row; knob cell
    SWITCHES_A_ROW = 3
    KNOB_CELL = 80

    def GetControlLayout(self, width):
        '''(side, [(group, params, x, width, a_row, knobs, height, top, rows)])'''
        compact = width < self.COMPACT_WIDTH
        key = (int(width), compact)
        if getattr(self, 'layout_cache', (None,))[0] == key:
            return self.layout_cache[1]
        bitmap = wx.Bitmap(1, 1)
        dc = wx.MemoryDC(bitmap)
        gc = wx.GraphicsContext.Create(dc)
        least = self.KNOB_LEAST_COMPACT if compact else self.KNOB_LEAST
        gap = 3 if compact else 4
        sections = []
        for group, params in self.GetSections():
            # key first in the switch row
            switches = [self.GetSwitchWidth(gc, group, compact)]
            switches += [self.GetSwitchWidth(gc, name, compact)
                         for _, name, _, kind in params if kind == 'switch']
            knobs = len([v for v in params if v[3] == 'knob'])
            # widest switch row, or knobs at their least
            rows = [switches[k:k + self.SWITCHES_A_ROW]
                    for k in range(0, len(switches), self.SWITCHES_A_ROW)]
            across = max([sum(row) + gap * (len(row) - 1) for row in rows] or [0])
            sections.append((group, params, switches, knobs,
                             max(across, knobs * (least if compact else self.KNOB_CELL))))
        del gc
        dc.SelectObject(wx.NullBitmap)
        needs = [v[4] for v in sections]
        gaps = self.SECTION_GAP * 2 * (len(sections) - 1)
        side = sum(needs) + gaps <= width
        # side by side: each as wide as it needs, rest left empty at right
        widths = needs if side else [width] * len(sections)
        if side and max(needs) * len(needs) + gaps <= width:
            # even columns when they fit
            widths = [max(needs)] * len(needs)
        if side:
            a_row = self.SWITCHES_A_ROW
            # knobs on one line: the most rows of all
            rows = max(-(-len(switches) // a_row) for _, _, switches, _, _ in sections)
            counts = [rows] * len(sections)
        else:
            # stacked: as many a row as fit
            a_row = 0
            counts = [self.CountRows(switches, w, compact)
                      for (_, _, switches, _, _), w in zip(sections, widths)]
        layout, x = [], 0
        lead = self.SECTION_TOP
        pad = self.STACK_PAD
        for (group, params, switches, knobs, _), w, rows in zip(sections, widths, counts):
            per = max(1, min(knobs, int(w // least))) if knobs else 1
            height = self.GetKnobTop(rows, lead)
            if knobs:
                height += KNOB_RADIUS * 2 + 31 + (-(-knobs // per) - 1) * self.KNOB_ROW
            layout.append((group, params, x if side else 0, w, a_row, per,
                           height + self.SECTION_BOTTOM + pad, lead, rows))
            x += w + self.SECTION_GAP * 2
        self.layout_cache = (key, (side, layout))
        return self.layout_cache[1]

    def CountRows(self, widths, room, compact):
        # rows these switch widths take in room
        rows, used = 1, 0
        for rw in widths:
            if used and used + rw > room:
                rows, used = rows + 1, 0
            used += rw + (3 if compact else 4)
        return rows

    def GetKnobTop(self, rows, lead):
        # knob ring top under the key and switch rows
        return self.KEY_TOP + rows * self.SWITCH_ROW - 4 + 13 if rows else lead

    def GetBandLayout(self, width):
        '''(per row, rows, name width, readout width) of the meters band'''
        key = (int(width), self.compact)
        if getattr(self, 'band_cache', (None,))[0] == key:
            return self.band_cache[1]
        bitmap = wx.Bitmap(1, 1)
        dc = wx.MemoryDC(bitmap)
        gc = wx.GraphicsContext.Create(dc)
        uikit.set_font(gc, self.LabelFont(), wx.BLACK)
        names = max(gc.GetTextExtent(spec[1])[0] for spec in BAND_METERS) + 8
        uikit.set_font(gc, self.ReadoutFont(), wx.BLACK)
        readout = gc.GetTextExtent('+00.0 dB')[0] + 12
        del gc
        dc.SelectObject(wx.NullBitmap)
        least = names + self.BAR_LEAST + 8 + readout
        count = len(BAND_METERS)
        fit = max(1, min(count, int((width + self.BAND_GAP) // (least + self.BAND_GAP))))
        rows = -(-count // fit)
        per = -(-count // rows)
        self.band_cache = (key, (per, rows, names, readout))
        return self.band_cache[1]

    def GetBandHeight(self, width):
        _, rows, _, _ = self.GetBandLayout(width)
        return self.BAND_PAD * 2 + rows * self.SWITCH_ROW - 4

    def GetPartHeight(self, key, height):
        width = self.parent.GetClientSize().width - 16
        if key != 'controls':
            return height
        self.compact = width < self.COMPACT_WIDTH
        side, layout = self.GetControlLayout(width)
        heights = [v[6] for v in layout]
        return self.GetBandHeight(width) + (max(heights) if side else sum(heights))

    def DrawControls(self, gc, x, y, width):
        '''cached picture, redrawn on value, hover, width or theme change'''
        values = master.get_values()
        # hover on the header's chips is not ours
        hovered = self.hovered if isinstance(self.hovered, tuple)\
            and self.hovered[0] in ('switch', 'knob', 'stage') else None
        key = (int(width), tuple(values), hovered, self.compact, uikit.get_style_version())
        cache = getattr(self, 'controls_cache', None)
        if cache is None or cache[0] != key:
            height = self.GetPartHeight('controls', CONTROLS)
            bitmap = wx.Bitmap(max(int(width), 1), max(int(height), 1))
            dc = wx.MemoryDC(bitmap)
            dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
            dc.Clear()
            hits, self.hits = self.hits, []
            picture = wx.GraphicsContext.Create(dc)
            self.DrawSections(picture, 0, self.GetBandHeight(width), width, values)
            del picture
            dc.SelectObject(wx.NullBitmap)
            drawn, self.hits = self.hits, hits
            cache = self.controls_cache = (key, gc.CreateBitmap(bitmap), bitmap.GetSize(),
                                           drawn)
        _, picture, (bw, bh), drawn = cache
        gc.DrawBitmap(picture, x, y, bw, bh)
        for rect, kind, value in drawn:
            self.hits.append((wx.Rect(rect.x + int(x), rect.y + int(y), rect.width,
                                      rect.height), kind, value))
        self.DrawBand(gc, x, y, width)

    def DrawBand(self, gc, x, y, width):
        # meters in rows: name, bar and readout
        draw_rule(gc, self.parent.st, x, y, width)
        per, rows, names, readout = self.GetBandLayout(width)
        cell = min((width - self.BAND_GAP * (per - 1)) / float(per), self.BAND_CELL_MOST)
        for k, spec in enumerate(BAND_METERS):
            row, column = divmod(k, per)
            self.DrawBandMeter(gc, spec, x + column * (cell + self.BAND_GAP),
                               y + self.BAND_PAD + row * self.SWITCH_ROW, names, cell)

    def GetMeterValue(self, spec):
        # (text, lit from, to, second tone or None, target or None)
        levels = self.levels
        key, label, low, high, kind = spec
        share = (lambda db: (min(max(db, low), high) - low) / (high - low))
        if levels is None:
            return None
        if kind == 'band':
            bands = levels.get('bands')
            if not bands:
                return None
            band = bands[key]
            # band width as it came and as filled, dB
            have = 10 ** (band['width'] / 10.0) if band['width'] > -100 else 0.0
            added = 10 ** (band['fill'] / 10.0) if band['fill'] > -100 else 0.0
            out = 10 * math.log10(have + added) if have + added > 1e-12 else -120.0
            text = f'{out:.1f} dB' if out > low else 'MONO'
            return (text, 0.0, share(band['width']), (share(band['width']), share(out)),
                    share(band['target']))
        value = levels.get(key)
        if value is None:
            return None
        shown = 0.0 if abs(value) < 0.05 else value
        if kind == 'reduce':
            # lit from 0 down to low
            return (f'{min(0.0, shown):.1f} dB', 0.0, min(max(value / low, 0.0), 1.0),
                    None, None)
        if kind == 'gain':
            return (f'{shown:+.1f} dB', 0.0, share(value), None, None)
        if kind == 'phase':
            delay = '' if shown == 0.0 else f'{shown:+.1f} ms'
            text = ('INV ' + delay).strip() if levels.get('phase_flip') else (delay or 'OK')
        else:
            text = f'{shown:+.1f} dB'
        return (text, share(0.0), share(value), None, None)

    def DrawBandMeter(self, gc, spec, x, y, names, width):
        st = self.parent.st
        label = spec[1]
        uikit.set_font(gc, self.LabelFont(), colour(st.RACK_LABEL_COLOR))
        gc.DrawText(label, x, uikit.get_caps_top(self.LabelFont(), y, 17))
        # readout display at the right
        uikit.set_font(gc, self.ReadoutFont(), colour(st.LCD_TEXT_COLOR))
        tw = gc.GetTextExtent('+00.0 dB')[0]
        cw = tw + 12
        rx = x + width - cw
        gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
        gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.LCD_BG_COLOR))))
        gc.DrawRoundedRectangle(rx + 0.5, y + 0.5, cw - 1, 16, uikit.RADIUS)
        reading = self.GetMeterValue(spec)
        text = '--' if reading is None else reading[0]
        gc.DrawText(text, rx + cw - 6 - gc.GetTextExtent(text)[0],
                    uikit.get_caps_top(self.ReadoutFont(), y, 17))
        bx = x + names
        bw = rx - 8 - bx
        if bw < 12:
            return
        # on the capitals' middle
        by = y + (17 - uikit.METER_BAR + 1) // 2
        # gain by dB, reduction in warning orange, the rest neutral
        key, label, low, high, kind = spec
        tone = None if kind == 'gain' else uikit.METER_TONES[1][1] if kind == 'reduce'\
            else uikit.METER_TONES[-1][1]
        if reading is None:
            uikit.draw_meter(gc, bx, by, bw, uikit.METER_BAR, 0.0, st.RACK_BG_COLOR, low,
                             high, tone=tone)
            return
        _, start, share, second, target = reading
        uikit.draw_meter(gc, bx, by, bw, uikit.METER_BAR, share, st.RACK_BG_COLOR, low, high,
                         tone=tone, start=start)
        if second is not None:
            # what the fill added, in the accent
            uikit.draw_meter(gc, bx, by, bw, uikit.METER_BAR, second[1], st.RACK_BG_COLOR,
                             tone=uikit.ui().ACCENT, start=second[0], unlit=False)
        # mark: bipolar middle, band target
        if kind not in ('bipolar', 'phase', 'band'):
            return
        mark = start if kind != 'band' else target
        if kind != 'band' or target is not None:
            mx = int(bx + bw * mark)
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.RACK_TEXT_COLOR if spec[4] == 'band'
                                                       else st.RACK_LABEL_COLOR))))
            gc.DrawRectangle(mx, by - 2, 1, uikit.METER_BAR + 4)

    def GetSectionPen(self, gc):
        # section lines a step fainter than the module's
        edge = colour(self.parent.st.RACK_EDGE_COLOR)
        return gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(edge.Red(), edge.Green(),
                                                         edge.Blue(), 120)).Width(1))

    def DrawSections(self, gc, x, y, width, values):
        # sections with a faint line between
        side, layout = self.GetControlLayout(width)
        height = max(v[6] for v in layout)
        top = y
        for k, (group, params, sx, sw, a_row, per, sh, lead, rows) in enumerate(layout):
            gc.SetPen(self.GetSectionPen(gc))
            if side and k:
                lx = x + sx - self.SECTION_GAP + 0.5
                gc.StrokeLine(lx, y + self.STACK_PAD + 8, lx, y + height - 8)
            elif not side or not k:
                gc.StrokeLine(x, top + 0.5, x + width, top + 0.5)
            self.DrawSection(gc, group, params, values, x + sx, top + self.STACK_PAD, sw,
                             a_row, per, lead, rows)
            if not side:
                top += sh

    def DrawSection(self, gc, group, params, values, x, y, width, a_row, per, lead, rows):
        # key first in the switch row, knobs under from the left
        key = self.DrawStageKey(gc, group, values, x, y + self.KEY_TOP)
        self.DrawSwitches(gc, params, values, x, y + self.KEY_TOP, width, a_row,
                          first=key + (3 if self.compact else 4))
        knobs = [v for v in params if v[3] == 'knob']
        first = y + self.GetKnobTop(rows, lead) + KNOB_RADIUS
        cell = min(width / float(per), self.KNOB_CELL)
        for k, (index, name, _, _) in enumerate(knobs):
            cx = x + cell * (k % per) + cell / 2.0
            cy = first + (k // per) * self.KNOB_ROW
            self.DrawKnobCell(gc, index, name, values, cx, cy, cell)

    def DrawStageKey(self, gc, group, values, x, y):
        # stage on or off, drawn as a switch
        st = self.parent.st
        stage = self.STAGES[group]
        on = master.is_stage_on(stage, values)
        label = group.upper()
        rw = self.GetSwitchWidth(gc, label, self.compact)
        hovered = self.hovered == ('stage', stage)
        uikit.draw_face(gc, (x, y, rw, 17),
                        colour(st.KNOB_RING_COLOR if hovered else st.KNOB_FACE_COLOR))
        if on:
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(uikit.ui().ACCENT))))
        else:
            gc.SetPen(wx.Pen(colour(st.RACK_LABEL_COLOR), 1))
            gc.SetBrush(wx.NullGraphicsBrush)
        gc.DrawEllipse(x + 5, y + 5, 6, 6)
        font = self.LabelFont()
        uikit.set_font(gc, font, colour(st.RACK_TEXT_COLOR if on else st.RACK_LABEL_COLOR))
        gc.DrawText(label, x + 17, uikit.get_caps_top(font, y, 17))
        self.hits.append((wx.Rect(int(x), int(y), int(rw), 16), 'stage', stage))
        return rw

    def DrawSwitches(self, gc, params, values, x, y, width, a_row=0, first=0):
        # switches: led and name on a key, in rows
        st = self.parent.st
        tokens = uikit.ui()
        sx, sy = x + first, y
        font = self.LabelFont()
        in_row = 1 if first else 0
        for index, name, _, kind in params:
            if kind != 'switch':
                continue
            label = name.upper()
            size = 6
            rw = self.GetSwitchWidth(gc, name, self.compact)
            if sx > x and (sx + rw > x + width or a_row and in_row >= a_row):
                # next row
                sx, sy, in_row = x, sy + self.SWITCH_ROW, 0
            on = master.is_on(values[index])
            hovered = self.hovered == ('switch', index)
            # hardware key, lighter on hover
            face = colour(st.KNOB_RING_COLOR if hovered else st.KNOB_FACE_COLOR)
            uikit.draw_face(gc, (sx, sy, rw, 17), face)
            if on:
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(tokens.ACCENT))))
            else:
                gc.SetPen(wx.Pen(colour(st.RACK_LABEL_COLOR), 1))
                gc.SetBrush(wx.NullGraphicsBrush)
            # from a whole row: the renderer puts shapes half a pixel down
            gc.DrawEllipse(sx + 5, sy + 5, size, size)
            uikit.set_font(gc, font, colour(st.RACK_TEXT_COLOR if on else st.RACK_LABEL_COLOR))
            gc.DrawText(label, sx + 5 + size + 6, uikit.get_caps_top(font, sy, 17))
            self.hits.append((wx.Rect(int(sx), int(sy), int(rw), 16), 'switch', index))
            sx += rw + (3 if self.compact else 4)
            in_row += 1
        return (sy - y) // self.SWITCH_ROW + 1

    def DrawKnobCell(self, gc, index, name, values, cx, cy, cell):
        # knob: range ring, value arc, readout and name
        st = self.parent.st
        self.DrawKnob(gc, cx, cy, values[index], self.hovered == ('knob', index))
        text = master.PROBE.Text(index, values[index])
        uikit.set_font(gc, self.ReadoutFont(), colour(st.LCD_TEXT_COLOR))
        tw = gc.GetTextExtent(text)[0]
        gc.DrawText(text, cx - tw / 2.0, cy + KNOB_RADIUS + 4)
        uikit.set_font(gc, self.LabelFont(), colour(st.RACK_LABEL_COLOR))
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
        # knob turned by vertical drag until release
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
            # double click resets
            self.SetValue(key, master.DEFAULTS[key])
            return
        # a quick second click counts as a double click only
        if event.LeftDown is False and event.LeftDClick is False:
            return
        if kind == 'stage':
            master.toggle_stage(key, (self.GetVst(),))
            self.reInitBuffer = True
        elif kind == 'switch':
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
