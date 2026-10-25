# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import analyzer
import audio
import numpy
import uikit
import wx

from rackbox import RackModule
from rackbox import colour
from rackbox import draw_well
from rackbox import get_font


# ANALYZER's module in the rack (rackbox), PyWinAudio's analyzer on the playing song: its
# parts side by side, the meters (a goniometer, the channels' levels, the loudness, the
# correlation and the balance), the spectrum and the spectrogram. shown from the View menu
# or a click on the header's spectrum or scope; kept (analyzer_panel)
BODY = 112
METER_LOW = -48.0
METER_MARKS = (0, -6, -12, -24, -48)
# a meter's segments: blue to -12 dB, orange above (no green and red: colour blindness)
METER_WARN = -12.0
BALANCE_RANGE = 6.0
# the meters' least width beside the goniometer
METERS_LEAST = 170
SPECTRUM_TOP = 0.0
SPECTRUM_DBS = (0, -24, -48, -72)
# the spectrum's axis, and the spectrogram's few
AXIS_FREQS = ((20, '20'), (50, '50'), (100, '100'), (200, '200'), (500, '500'),
              (1000, '1k'), (2000, '2k'), (5000, '5k'), (10000, '10k'), (20000, '20k'))
SPECTRUM_FREQS = ((100, '100'), (1000, '1k'), (10000, '10k'))
# the curve (a steel blue, its ground fading down) and its peak line (lighter)
CURVE_LINE = (200, 214, 236)
CURVE_FILL = (111, 140, 184)
PEAK_LINE = (236, 240, 248)
NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')


def get_note(freq):
    # the nearest note's name (A4 at 440 Hz, D2 at 73.4 Hz)
    midi = int(round(69 + 12 * numpy.log2(freq / 440.0)))
    return '%s%d' % (NOTE_NAMES[midi % 12], midi // 12 - 1)


def get_freq_share(freq):
    return numpy.log(freq / analyzer.SPECTRUM_LOW) /\
        numpy.log(analyzer.SPECTRUM_HIGH / analyzer.SPECTRUM_LOW)


class AnalyzerPanel(RackModule):

    TITLE = 'ANALYZER'
    PREFERENCE = 'analyzer_panel'
    ROW = True
    # BARS: the header's own visualizers (PlayBoxSpectrum's bars, PlayBoxVectorScope's
    # dots), their windows laid on this part (PlayBox.LayoutAnalyzerVisuals), here since the
    # header and the rack bar gave them up
    PARTS = (('meters', 'METERS', BODY, 5.0), ('bars', 'BARS', BODY, 5.0),
             ('spectrum', 'SPECTRUM', BODY, 6.0), ('gram', 'SPECTROGRAM', BODY, 5.0))

    def __init__(self, parent):
        self.analyzer = analyzer.Analyzer()
        self.path = None
        RackModule.__init__(self, parent)

    def IsActive(self):
        return hasattr(self.parent, 'cue') and self.parent.IsVisualPlaying()

    def GetState(self):
        if self.IsActive() is False:
            return ('NO SIGNAL', False)
        # after MASTER when it is on: what is heard
        return ('AFTER MASTER' if self.parent.IsLoudOn() else 'DIRECT', False)

    def GetChips(self):
        return [('reset', 'RESET', False, False)]

    def OnChip(self, key):
        if key == 'reset':
            # the hold, the clip marks and the integrated loudness started again
            self.analyzer.Reset()
            self.reInitBuffer = True

    def Read(self, whole=True):
        # once a frame while shown: the playing stream's next samples; a new song starts
        # the readings again (whole False: its levels and loudness only, the rack bar's)
        if hasattr(self.parent, 'cue') is False:
            return
        if self.parent.cue.path != self.path:
            self.path = self.parent.cue.path
            self.analyzer.Reset()
        samples = None
        if self.IsActive():
            hstream, channels, _ = self.parent.GetVisualStream()
            rate = audio.get_native_fs(hstream) if hstream else 0
            samples = analyzer.read_samples(hstream, channels, analyzer.FFT_SIZE)
            self.analyzer.Update(samples, rate, whole=whole)
        else:
            self.analyzer.Update(None, 0)

    def SetRectDraw(self, dc):
        if self.shown:
            self.Read()
        self.bars_rect = None
        RackModule.SetRectDraw(self, dc)
        # BARS's windows put where the part is now (or hidden with it)
        rect = self.bars_rect if self.shown else None
        if rect != getattr(self, 'bars_laid', None):
            self.bars_laid = rect
            wx.CallAfter(self.parent.LayoutAnalyzerVisuals)

    # drawn

    def DrawPart(self, gc, key, x, y, width):
        if key == 'meters':
            self.DrawMeters(gc, x, y, width)
        elif key == 'bars':
            # its ground; the visualizers' windows over it, inside its edge
            self.DrawGround(gc, x, y + 6, width, BODY - 14)
            self.bars_rect = wx.Rect(int(x) + 1, int(y) + 7, int(width) - 2, BODY - 16)
        elif key == 'spectrum':
            self.DrawSpectrum(gc, x, y + 6, width, BODY - 14)
        elif key == 'gram':
            self.DrawGram(gc, x, y + 6, width, BODY - 14)

    def DrawGround(self, gc, x, y, w, h):
        # (a display set into the plate, as every module's: rackbox.draw_well)
        draw_well(gc, self.parent.st, (x, y, w, h))

    def DrawLabel(self, gc, text, x, y, right=False):
        st = self.parent.st
        gc.SetFont(get_font(uikit.LABEL, bold=True), colour(st.RACK_LABEL_COLOR))
        if right:
            x -= gc.GetTextExtent(text)[0]
        gc.DrawText(text, x, y)

    def DrawMeters(self, gc, x, y, width):
        a = self.analyzer
        st = self.parent.st
        side = BODY - 14
        top = y + 6
        # the goniometer: the dots kept a while, its axes faint; left out when the meters
        # would have too little room
        if width >= side + 12 + METERS_LEAST:
            self.DrawScope(gc, x, top, side)
            x, width = x + side + 12, width - side - 12
        self.DrawChannels(gc, x, top, width)

    def DrawScope(self, gc, x, top, side):
        a = self.analyzer
        st = self.parent.st
        self.DrawGround(gc, x, top, side, side)
        image = numpy.clip(a.scope, 0.0, 1.0)
        shape = analyzer.SCOPE_SIDE
        ground = numpy.array(colour(st.LCD_BG_COLOR).Get()[:3], dtype=float)
        dot = numpy.array(colour(st.LCD_TEXT_COLOR).Get()[:3], dtype=float)
        rgb = (ground + (dot - ground) * image[:, :, None]).astype(numpy.uint8)
        bitmap = wx.Bitmap.FromBuffer(shape, shape, rgb.tobytes())
        gc.DrawBitmap(bitmap, x + 1, top + 1, side - 2, side - 2)
        gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
        gc.StrokeLine(x + side / 2.0, top + 4, x + side / 2.0, top + side - 4)
        gc.StrokeLine(x + 4, top + side / 2.0, x + side - 4, top + side / 2.0)
        self.DrawLabel(gc, 'M', x + side / 2.0 + 3, top + 2)
        self.DrawLabel(gc, 'S', x + side - 10, top + side / 2.0 + 1)

    def DrawChannels(self, gc, mx, top, mw):
        # the channels: peak bars in segments, the RMS a line under them, the hold a tick
        a = self.analyzer
        st = self.parent.st
        readout = 52
        bw = mw - 14 - readout
        if bw < 40:
            return
        row = top + 2
        for c, name in enumerate(('L', 'R')):
            self.DrawLabel(gc, name, mx, row)
            self.DrawLevel(gc, mx + 14, row + 1, bw, 8, a.peak[c], a.rms[c], a.hold[c])
            text = 'CLIP' if a.clip[c] else ('%.1f' % a.hold[c] if a.hold[c] > analyzer.FLOOR else '--')
            self.DrawReadout(gc, text, mx + mw, row - 1, warned=a.clip[c])
            row += 14
        # the scale under them
        gc.SetFont(get_font(uikit.MICRO), colour(st.RACK_LABEL_COLOR))
        for mark in METER_MARKS:
            tx = mx + 14 + bw * (mark - METER_LOW) / -METER_LOW
            text = '%d' % mark
            gc.DrawText(text, tx - gc.GetTextExtent(text)[0] / 2.0, row - 3)
        row += 12
        # the loudness: momentary, short-term, integrated (LUFS)
        momentary, short, integrated = a.loudness
        lx = mx
        for name, value in (('M', momentary), ('S', short), ('I', integrated)):
            self.DrawLabel(gc, name, lx, row + 2)
            text = '%.1f' % value if value > analyzer.LOUDNESS_FLOOR else '--'
            cell = (mw - 8) / 3.0
            self.DrawReadout(gc, text, lx + cell - 6, row, warned=False)
            lx += cell + 4
        self.DrawLabel(gc, 'LUFS', mx + mw, row + 15, right=True)
        row += 30
        # the correlation (-1 to +1) and the balance (+-6 dB): a marker on a strip
        half = (mw - 10) / 2.0
        for k, (name, value, low, high, text) in enumerate((
                ('CORR', a.correlation, -1.0, 1.0, '%+.2f' % a.correlation),
                ('BAL', a.balance, -BALANCE_RANGE, BALANCE_RANGE, '%+.1f' % a.balance))):
            sx = mx + k * (half + 10)
            self.DrawLabel(gc, name, sx, row)
            self.DrawLabel(gc, text, sx + half, row, right=True)
            self.DrawStrip(gc, sx, row + 14, half, 6, (value - low) / (high - low),
                           warned=name == 'CORR' and value < 0)

    def DrawLevel(self, gc, x, y, w, h, peak, rms, hold):
        st = self.parent.st
        tokens = uikit.ui()
        segment, spacing = uikit.METER_SEGMENT, uikit.METER_GAP
        count = int((w + spacing) / (segment + spacing))
        x = int(x)
        share = max(min((peak - METER_LOW) / -METER_LOW, 1.0), 0.0)
        lit = int(round(share * count))
        warn_from = int(round((METER_WARN - METER_LOW) / -METER_LOW * count))
        gc.SetPen(wx.NullGraphicsPen)
        off = uikit.mix(colour(st.METER_OFF_COLOR), (0, 0, 0), 0.25)
        for s in range(count):
            if s < lit:
                fill = colour(tokens.WARN if s >= warn_from else tokens.ACCENT)
            else:
                fill = off
            gc.SetBrush(gc.CreateBrush(wx.Brush(fill)))
            # as tall as every meter's (uikit.METER_BAR; 5 rows here before)
            gc.DrawRectangle(x + s * (segment + spacing), y, segment, uikit.METER_BAR)
        # the RMS: a line a row under the segments
        rshare = max(min((rms - METER_LOW) / -METER_LOW, 1.0), 0.0)
        gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.RACK_TEXT_COLOR))))
        gc.DrawRectangle(x, y + uikit.METER_BAR + 1, int(w * rshare), 2)
        # the hold: a tick
        if hold > METER_LOW:
            hx = x + w * max(min((hold - METER_LOW) / -METER_LOW, 1.0), 0.0)
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.RACK_TEXT_COLOR))))
            gc.DrawRectangle(hx - 1, y - 1, 2, h + 1)

    def DrawReadout(self, gc, text, right, y, warned=False):
        st = self.parent.st
        tokens = uikit.ui()
        gc.SetFont(get_font(uikit.READOUT, mono=True),
                   colour(tokens.WARN if warned else st.LCD_TEXT_COLOR))
        tw, th = gc.GetTextExtent(text)[:2]
        draw_well(gc, st, (right - tw - 10, y - 1, tw + 10, th + 4))
        gc.SetFont(get_font(uikit.READOUT, mono=True),
                   colour(tokens.WARN if warned else st.LCD_TEXT_COLOR))
        gc.DrawText(text, right - tw - 5, y + 1)

    def DrawStrip(self, gc, x, y, w, h, share, warned=False):
        st = self.parent.st
        tokens = uikit.ui()
        # a slot set in the plate, its centre marked; the value a pill on it
        draw_well(gc, st, (x, y, w, h), radius=h / 2.0)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.RACK_LABEL_COLOR))))
        gc.DrawRectangle(x + w / 2.0 - 0.5, y - 2, 1, h + 4)
        mx = x + w * max(min(share, 1.0), 0.0)
        ink = colour(tokens.WARN if warned else tokens.ACCENT)
        gc.SetBrush(gc.CreateBrush(wx.Brush(ink)))
        gc.DrawRoundedRectangle(mx - 2.5, y - 2, 5, h + 4, 2.5)

    def DrawSpectrum(self, gc, x, y, w, h):
        # a curve through the bands, its ground fading down, the peak line over it; the dB
        # at the right, the frequencies under it; under the mouse its Hz, note and dB
        a = self.analyzer
        st = self.parent.st
        self.DrawGround(gc, x, y, w, h)
        ix, iy, iw, ih = (x + 4, y + 4, w - 30, h - 17)
        self.spectrum_inner = wx.Rect(int(ix), int(iy), int(iw), int(ih))
        floor = analyzer.SPECTRUM_FLOOR

        def to_y(db):
            return iy + ih * (SPECTRUM_TOP - min(max(db, floor), SPECTRUM_TOP)) /\
                (SPECTRUM_TOP - floor)

        # (its grid faint: the curve the thing to see)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(255, 255, 255, 18)).Width(1)))
        gc.SetFont(get_font(uikit.MICRO), colour(st.RACK_LABEL_COLOR))
        for db in SPECTRUM_DBS:
            ly = int(to_y(db)) + 0.5
            gc.StrokeLine(ix, ly, ix + iw, ly)
            text = '%d' % db
            gc.DrawText(text, x + w - 4 - gc.GetTextExtent(text)[0], ly - 6)
        right = None
        for freq, text in AXIS_FREQS:
            fx = ix + iw * get_freq_share(freq)
            gc.StrokeLine(int(fx) + 0.5, iy, int(fx) + 0.5, iy + ih)
            tw = gc.GetTextExtent(text)[0]
            tx = min(max(fx - tw / 2.0, ix), ix + iw - tw)
            # a name that would touch the one before it left out (narrow: 10k20k)
            if right is not None and tx < right + 6:
                continue
            gc.DrawText(text, tx, iy + ih + 1)
            right = tx + tw
        count = len(a.spectrum)
        xs = ix + iw * (numpy.arange(count) + 0.5) / count
        # the curve's ground: from the curve down, fading
        path = gc.CreatePath()
        path.MoveToPoint(xs[0], iy + ih)
        for px, db in zip(xs, a.spectrum):
            path.AddLineToPoint(px, to_y(db))
        path.AddLineToPoint(xs[-1], iy + ih)
        path.CloseSubpath()
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateLinearGradientBrush(
            0, iy, 0, iy + ih, wx.Colour(*CURVE_FILL, 150), wx.Colour(*CURVE_FILL, 10)))
        gc.FillPath(path)
        # the curve, the peak's thin over it
        for values, ink, width, alpha in ((a.spectrum, CURVE_LINE, 1.4, 255),
                                          (a.peak_line, PEAK_LINE, 1.0, 130)):
            line = gc.CreatePath()
            line.MoveToPoint(xs[0], to_y(values[0]))
            for px, db in zip(xs[1:], values[1:]):
                line.AddLineToPoint(px, to_y(db))
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(*ink, alpha)).Width(width)
                                   .Join(wx.JOIN_ROUND)))
            gc.StrokePath(line)
        self.DrawReadoutTip(gc, ix, iy, iw, ih, xs)

    def DrawReadoutTip(self, gc, ix, iy, iw, ih, xs):
        # under the mouse: the frequency, its note and the band's level
        pointer = getattr(self, 'pointer', None)
        if pointer is None or self.spectrum_inner.Contains(pointer) is False:
            return
        st = self.parent.st
        share = (pointer.x - ix) / float(iw)
        freq = analyzer.SPECTRUM_LOW * (analyzer.SPECTRUM_HIGH / analyzer.SPECTRUM_LOW) ** share
        index = int(min(max(share * len(xs), 0), len(xs) - 1))
        db = self.analyzer.spectrum[index]
        hz = '%.1f kHz' % (freq / 1000.0) if freq >= 1000 else '%d Hz' % (freq)
        text = '%s   %s   %s' % (hz, get_note(freq),
                                 '%.1f dB' % db if db > analyzer.SPECTRUM_FLOOR else '-- dB')
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(*PEAK_LINE, 90)).Width(1)))
        gc.StrokeLine(pointer.x + 0.5, iy, pointer.x + 0.5, iy + ih)
        gc.SetFont(get_font(uikit.READOUT, mono=True), colour(st.RACK_TEXT_COLOR))
        tw, th = gc.GetTextExtent(text)[:2]
        bw, bh = tw + 14, th + 6
        bx = min(max(pointer.x - bw / 2.0, ix), ix + iw - bw)
        gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
        gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.LCD_BG_COLOR))))
        gc.DrawRoundedRectangle(bx, iy + 2, bw, bh, 3)
        gc.DrawText(text, bx + 7, iy + 5)

    def CATCH_EVT_GLOBAL(self, event):
        # where the mouse is, for the spectrum's readout (drawn again as it moves)
        pointer = wx.Point(int(event.X), int(event.Y)) if self.onClient else None
        if pointer != getattr(self, 'pointer', None):
            inner = getattr(self, 'spectrum_inner', None)
            if inner is not None and (inner.Contains(pointer or wx.Point(-1, -1)) or
                                      inner.Contains(getattr(self, 'pointer', None)
                                                     or wx.Point(-1, -1))):
                self.reInitBuffer = True
            self.pointer = pointer
        RackModule.CATCH_EVT_GLOBAL(self, event)

    def DrawGram(self, gc, x, y, w, h):
        a = self.analyzer
        st = self.parent.st
        self.DrawGround(gc, x, y, w, h)
        ix, iy, iw, ih = (x + 1, y + 1, w - 2, h - 2)
        if iw <= 0 or ih <= 0:
            return
        # a column a frame, the newest at the right; its rows stretched to the height
        columns = a.GetGram(int(iw))
        rgb = analyzer.GRAM_COLOURS[columns]
        rows = numpy.linspace(0, analyzer.GRAM_ROWS - 1, int(ih)).astype(int)
        rgb = numpy.ascontiguousarray(rgb[rows])
        bitmap = wx.Bitmap.FromBuffer(rgb.shape[1], rgb.shape[0], rgb.tobytes())
        # (wider than its history: stretched over the part, not a blank at its left)
        gc.DrawBitmap(bitmap, ix, iy, iw, rgb.shape[0])
        # the frequencies at the left
        gc.SetFont(get_font(uikit.MICRO), colour(st.RACK_TEXT_COLOR))
        for freq, text in SPECTRUM_FREQS:
            fy = iy + ih * (1.0 - get_freq_share(freq))
            gc.DrawText(text, ix + 3, fy - 6)
