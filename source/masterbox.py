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


# MASTER's module in the rack (rackbox), a plug-in's plate: its header (whether it works,
# A/B) and the plugin's three sections, each its stage's key (on or off), its levels
# (segmented meters with their readouts) and its controls (LED switches and knobs); the
# levels apart from their sections before, and the stages' keys in the header ("each its
# own", the user); shown from the MASTER row's arrow; kept (master_panel)
CONTROLS = 118
# its meters, all in a band over the sections (a grid, as PyWinAudio's rack: each on its
# section's key's row and the stereo's five under its key before, AGC's and LIMITER's
# sections left with a block empty, "not clean", the user), in the plugin's order: (key,
# label, low, high, kind): 'gain' (lit from low), 'reduce' (from 0 down to low, in the
# warning colour), 'bipolar' (from the middle), 'phase' (the delay between the channels,
# ms), 'band' (a band's width as it came, as filled, and its target, S/M dB); the output's
# peak the rack bar's OUT
# (LOUDNESS IN left out: the AGC's gain says it, the target less the input; with AGC off
# the rack bar's LUFS reads the song as it is)
BAND_METERS = (('agc', 'AGC', -12.0, 18.0, 'gain'),
               ('side', 'WIDTH', -12.0, 0.0, 'reduce'),
               ('balance', 'BALANCE', -6.0, 6.0, 'bipolar'),
               ('phase', 'PHASE', -2.0, 2.0, 'phase'),
               ('limiter', 'LIMITER', -12.0, 0.0, 'reduce'),
               (0, 'LOW 150\u2013600', -30.0, 0.0, 'band'),
               (1, 'MID 600\u20133K', -30.0, 0.0, 'band'),
               (2, 'HIGH 3K+', -30.0, 0.0, 'band'))

class MasterPanel(RackModule):

    # (MASTER as the rack bar's key, the View menu and the keys call it: AUTO MASTER here
    # alone, the user)
    TITLE = 'MASTER'
    PREFERENCE = 'master_panel'
    PARTS = (('controls', 'CONTROLS', CONTROLS),)

    def __init__(self, parent):
        self.drag = None
        self.levels = None
        self.compact = False
        RackModule.__init__(self, parent)
        # always there, folded or open (its header the rack's bar: the meter, the volume)
        self.shown = True

    def Toggle(self):
        # (hidden no more: folded)
        self.ToggleFold()

    def ToggleFold(self):
        RackModule.ToggleFold(self)
        # (the View menu's Master checked while it is open)
        menu = getattr(wx.GetTopLevelParent(self), 'MenuBar', None)
        item = getattr(menu, 'itemMasterShow', None)
        if item is not None:
            item.Check(not self.folded)

    # what it shows

    def IsActive(self):
        # MASTER on (not passed by); not known while the player is being made
        return hasattr(self.parent, 'cue') and self.parent.IsLoudOn()

    # its power key: MASTER on or off, as the rack bar's key
    POWER = True

    def OnPower(self):
        if self.parent.IsLoudOn():
            self.parent.SetLoudOff()
        else:
            self.parent.SetLoudOn()
        # (drawn again now: stopped, nothing draws it at the next frame)
        self.reInitBuffer = True

    def GetVst(self):
        control = getattr(self.parent, 'AudioControl', None)
        return control.vstHandle if control is not None else 0

    def ReadLevels(self):
        # (nothing sounding: none, its meters at rest; read on, they held their last)
        if self.parent.IsVisualPlaying() is False:
            return None
        return master.METERS.Read(self.GetVst()) if self.IsActive() else None

    def GetState(self):
        if not self.IsActive():
            return ('BYPASSED', False)
        if master.METERS.IsCompared():
            return ('A/B: ORIGINAL', True)
        # its AGC's and limiter's meters small in place of ACTIVE (their numbers alone before,
        # "a meter, small, would be good", the user)
        if self.IsSummaryShown():
            return None
        return ('ACTIVE', False)

    # the header's meters: (spec as BAND_METERS'), each its name and a bar (its value too
    # before: "without the numbers", the user)
    # (the plugin's three stages, in its order; STEREO's the width it cuts, as WIDTH's in
    # the band: AGC and LIM alone before, "and the stereo?", the user)
    SUMMARY = (('agc', 'AGC', -12.0, 18.0, 'gain'), ('side', 'STEREO', -12.0, 0.0, 'reduce'),
               ('limiter', 'LIM', -12.0, 0.0, 'reduce'))
    # its bars 40 px, shorter as the window narrows (20 at the least): at the window's
    # least width (480) all of them and OUT's on one header (OUT left out before, "why was
    # OUT taken out?", the user)
    SUMMARY_BAR = 40
    SUMMARY_LEAST = 18

    def GetSummaryBar(self):
        width = self.GetSize().width or self.GetLayoutWidth()
        return int(max(self.SUMMARY_LEAST, min(self.SUMMARY_BAR, (width - 400) / 4.0)))

    def IsSummaryShown(self):
        # open or folded (folded alone before; the header's loudness display in its place
        # since, "rather AGC and LIM at its left", the user)
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

    # the header's right: A/B, a line, the output's meter (OUT and a bar), a line, the
    # volume (VolumeSlider, its child: volume_at); the rack bar's before
    OUT_GAP = 8
    # a small bar, one for both channels (the louder): whether it sounds, the rest
    # ANALYZER's meters' (two bars 120 px wide before, the same as theirs, the user); as
    # long as the summary's (GetSummaryBar)
    METER_LEAST = 18
    METER_LOW = -48.0

    def PlaceVolume(self, x, y):
        # (moved at once: after the event, the header drawn at its new width first, the
        # volume and its mute key shook as the window was sized, the user)
        if (x, y) != getattr(self, 'volume_at', None):
            self.volume_at = (x, y)
            volume = getattr(self.parent, 'VolumeSlider', None)
            if volume is not None:
                volume.OnSize()

    def Place(self, y, width):
        # the volume put where the header keeps it as the module is placed, in the same
        # step (its drawing can wait a frame; shown, it the module's child)
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
        '''the output as ANALYZER reads it (its own thread, folded or not): OUT and a small
        bar, from no further left than left to right; where it starts (right when there is
        no room)'''
        analyzer = getattr(self.parent, 'Analyzer', None)
        if analyzer is None:
            return right
        a = analyzer.analyzer
        st = self.parent.st
        # (the short-term loudness's display beside it before: ANALYZER's meters have it,
        # AGC and LIM at the header's left in its room, the user)
        label = get_font(uikit.LABEL, bold=True)
        uikit.set_font(gc, label, colour(st.RACK_LABEL_COLOR))
        lw = gc.GetTextExtent('OUT')[0]
        # (its room by its name's own width: 34 and 13 more held before, OUT left out of the
        # least window with room for it)
        # (as long as AGC's, STEREO's and LIM's at the header's left: 48 at most before, "as
        # small as the three", the user)
        width = int(max(self.METER_LEAST, min(self.GetSummaryBar(),
                                              right - lw - self.OUT_GAP - left)))
        bx = right - width
        if bx - self.OUT_GAP - lw < left:
            return right
        segment, spacing, bar = uikit.METER_SEGMENT, uikit.METER_GAP, uikit.METER_BAR
        count = int((width + spacing) / (segment + spacing))
        # on whole pixels, their last against the right
        bx = int(bx + width - (count * (segment + spacing) - spacing))
        text_y, top = self.GetSmallTextRows(label, uikit.METER_BAR)
        gc.DrawText('OUT', bx - self.OUT_GAP - lw, text_y)
        span = count * (segment + spacing) - spacing
        peak = max(a.peak[0], a.peak[1])
        share = max(min((peak - self.METER_LOW) / -self.METER_LOW, 1.0), 0.0)
        uikit.draw_meter(gc, bx, top, span, bar, share, st.RACK_BG_COLOR, self.METER_LOW)
        return int(bx - self.OUT_GAP - lw)

    # each section's stage, its key at the section's top (DrawStageKey): a song heard
    # without one (its loudness as it is without AGC, its stereo without STEREO, its peaks
    # without LIMITER)
    STAGES = dict(AGC='agc', Stereo='stereo', Limiter='limiter')

    def GetChips(self):
        # A/B: the original at the same loudness, warned while it is heard
        return [('ab', 'A/B', self.IsActive() and master.METERS.IsCompared(), True)]

    def IsChipEnabled(self, key):
        return key != 'ab' or self.IsActive()

    def OnChip(self, key):
        if key == 'ab' and self.IsChipEnabled(key):
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
        if key == 'controls':
            self.levels = self.ReadLevels()
            self.DrawControls(gc, x, y, width)

    # a section (the plugin's: AGC, Stereo, Limiter): its stage's key (its name, on or off)
    # first in its row of switches, its knobs under them spread over its width; the
    # sections side by side, each as wide as it needs and the room shared as they need it,
    # or one under another when they do not fit (GetControlLayout)
    SWITCH_ROW = 21
    # the section's key and switches KEY_TOP under its top, its knobs 13 under them (13
    # over the switches and 6 under them read the other way: the user)
    KEY_TOP = 6
    SECTION_TOP = 36
    # a line over the sections (side by side, one; one under another, over each) and each
    # this much lower under it (its key 6 px under the line was tight; side by side, none
    # under the header: the user)
    STACK_PAD = 6
    SECTION_GAP = 12
    SECTION_BOTTOM = 8
    # the meters' band: PAD over and under its rows (a row each SWITCH_ROW), its meters
    # GAP apart in a row, a meter's bar at least BAR_LEAST
    BAND_PAD = 8
    BAND_GAP = 24
    BAR_LEAST = 48
    # a meter's cell at most (its bar about 100 px): from the left, the rest of a wide
    # module's row left empty (as wide as the module, the bars ran long: the user)
    BAND_CELL_MOST = 240

    def GetSections(self):
        # (its params but its stage's own switch, AGC's or Limiter's: its key now)
        own = set(indexes[0] for indexes in master.STAGE_SWITCHES.values()
                  if len(indexes) == 1)
        return [(group, [v for v in master.PARAMS if v[2] == group and v[0] not in own])
                for group in master.GROUPS]

    def GetSwitchWidth(self, gc, name, compact):
        # the LED (6 px) 5 px in, 6 px to the name (4 was cramped), 7 px after it (compact:
        # 5 after the name, 3 between: the LED's 6 to the name kept)
        uikit.set_font(gc, get_font(uikit.MICRO if compact else uikit.LABEL, bold=True), wx.BLACK)
        return 5 + 6 + 6 + gc.GetTextExtent(name.upper())[0] + (5 if compact else 7)

    # the knobs' least cell (their readouts, -16.0 LUFS, ran into each other under it) and
    # a row of them
    # (compact, the readouts a step smaller: 52)
    KNOB_LEAST = 64
    KNOB_LEAST_COMPACT = 52
    # (a row of knobs under another: 58 put the name under one on the next one's ring)
    KNOB_ROW = 70

    # side by side, a section's switches this many a row (Stereo's five three and two: the
    # same at any width, "always two rows", the user); a knob's cell (its readout and name
    # under it)
    SWITCHES_A_ROW = 3
    KNOB_CELL = 80

    def GetControlLayout(self, width):
        '''(side by side, [(group, params, x, width, its switches a row (0: as many as
        fit), knobs a row, height, its controls' top, its switches' rows)]) at this inner
        width: each its switches across it over its knobs (at its left, in one row or two,
        they changed with the width: "not consistent", the user), the sections side by side
        their knobs from one line'''
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
            # (its key first in its row of switches)
            switches = [self.GetSwitchWidth(gc, group, compact)]
            switches += [self.GetSwitchWidth(gc, name, compact)
                         for _, name, _, kind in params if kind == 'switch']
            knobs = len([v for v in params if v[3] == 'knob'])
            # its widest row of switches, or its knobs at their least
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
        # side by side, each as wide as it needs from the left, what is left at the right
        # (the room shared, their knobs spread over it, it read uneven: "leave the right
        # of LIMITER empty, to the left", the user)
        widths = needs if side else [width] * len(sections)
        if side and max(needs) * len(needs) + gaps <= width:
            # as wide as one another when they fit (three even columns)
            widths = [max(needs)] * len(needs)
        if side:
            a_row = self.SWITCHES_A_ROW
            # (their knobs from one line: the most rows of them all)
            rows = max(-(-len(switches) // a_row) for _, _, switches, _, _ in sections)
            counts = [rows] * len(sections)
        else:
            # one under another: as many a row as fit (all five in one, the room there)
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
        # the rows switches of these widths take flowing in room
        rows, used = 1, 0
        for rw in widths:
            if used and used + rw > room:
                rows, used = rows + 1, 0
            used += rw + (3 if compact else 4)
        return rows

    def GetKnobTop(self, rows, lead):
        # the knobs' rings' top under its key's and switches' rows, from the section's top
        return self.KEY_TOP + rows * self.SWITCH_ROW - 4 + 13 if rows else lead

    def GetBandLayout(self, width):
        '''(meters a row, rows, the names' width, the readouts' width) of the meters' band
        at this inner width: as many a row as fit at their least, the rows as even as they
        go (four and four, not five and three)'''
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
        '''drawn once into a picture, put there at every frame, drawn again when a value,
        the mouse over it, its width or the theme changes: its names, readouts, knobs and
        switches drawn at every frame took 220 ms a second (MASTER and ANALYZER open, a
        click waited up to 60 ms); its meters drawn over it at every frame'''
        values = master.get_values()
        # (the mouse over the header's chips not one of its own)
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
        # the meters in rows across the module, each its name, its bar from one place
        # (after the longest name) and its readout on a display at its cell's right; a line
        # over them, the header's (none: the header read as one with them, the user)
        draw_rule(gc, self.parent.st, x, y, width)
        per, rows, names, readout = self.GetBandLayout(width)
        cell = min((width - self.BAND_GAP * (per - 1)) / float(per), self.BAND_CELL_MOST)
        for k, spec in enumerate(BAND_METERS):
            row, column = divmod(k, per)
            self.DrawBandMeter(gc, spec, x + column * (cell + self.BAND_GAP),
                               y + self.BAND_PAD + row * self.SWITCH_ROW, names, cell)

    def GetMeterValue(self, spec):
        # (readout text, the share it is lit from, to, its second tone's (from, to) or None,
        # its target's share or None) of a meter; None when nothing is read
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
            # the band's width as it came and as filled (powers added), dB
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
            # (lit from 0 down to low)
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
        # the readout's display at the right, as DrawMeter's
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
        # on the names' capitals' middle (from (17 - 6) // 2 it sat a pixel over it)
        by = y + (17 - uikit.METER_BAR + 1) // 2
        # a gain by its dB, a reduction in the warning's orange, the rest in a neutral tone
        # (amounts, not levels near the top)
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
            # what the fill added to the band, in the accent
            uikit.draw_meter(gc, bx, by, bw, uikit.METER_BAR, second[1], st.RACK_BG_COLOR,
                             tone=uikit.ui().ACCENT, start=second[0], unlit=False)
        # a mark: the bipolar's middle, a band's target
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
        # the lines between the plugin's sections a step fainter than those between the
        # module's parts (the same lines, the smaller division read as the larger), as long
        # (8 px shorter at each end, they looked cut short)
        edge = colour(self.parent.st.RACK_EDGE_COLOR)
        return gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(edge.Red(), edge.Green(),
                                                         edge.Blue(), 120)).Width(1))

    def DrawSections(self, gc, x, y, width, values):
        # the plugin's sections (GetControlLayout), a faint line between them
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
        # its key first in its row of switches (a_row a row, 0: as many as fit), its knobs
        # under them from its left (rows: the sections' most, their knobs on one line)
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
        # the section's stage on or off (master.toggle_stage: Stereo's five switches as one),
        # an LED and its name on a key as its switches
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
        # a section's switches: an LED (lit, or a ring) and its name on a key, rows of them
        # in width (first: the room its key takes at the first row's start)
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
                # a row more (one a row in a section: GetControlLayout counted them)
                sx, sy, in_row = x, sy + self.SWITCH_ROW, 0
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
            uikit.set_font(gc, font, colour(st.RACK_TEXT_COLOR if on else st.RACK_LABEL_COLOR))
            gc.DrawText(label, sx + 5 + size + 6, uikit.get_caps_top(font, sy, 17))
            self.hits.append((wx.Rect(int(sx), int(sy), int(rw), 16), 'switch', index))
            sx += rw + (3 if self.compact else 4)
            in_row += 1
        return (sy - y) // self.SWITCH_ROW + 1

    def DrawKnobCell(self, gc, index, name, values, cx, cy, cell):
        # a knob: a ring of the range, the value's arc in the accent, its readout and name
        # under it
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
