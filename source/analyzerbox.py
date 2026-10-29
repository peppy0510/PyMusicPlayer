# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import analyzer
import audio
import math
import numpy
import threading
import time
import uikit
import wx

from rackbox import HEADER
from rackbox import RackModule
from rackbox import draw_rule


# ANALYZER's module in the rack (rackbox), PyWinAudio's analyzer on the playing song, drawn as
# PyWinAudio draws it (meterview: its sizes, its colours, its order): one screen, its parts one
# under another a line apart, METERS (a goniometer, the channels' levels, their scale, the
# spectrum's bars, the correlation and the balance; their values at the right), SPECTRUM,
# SCOPE (an oscilloscope) and SPECTROGRAM. (its parts side by side before, each its own well,
# the spectrum's bars in the header's window: the least finished screen, the user.) shown from
# the View menu or a click on the header's spectrum or scope; kept (analyzer_panel)

# PyWinAudio's rack palette (rackui.RACK) and meterview's tones
LCD = '#111215'
LCD_RIM = '#2b2e33'
LCD_GRID = '#1e2126'
LCD_AXIS = '#343840'
LCD_TEXT = '#7d828a'
TEXT = '#e6e7e9'
DIM = '#8b8f96'
FAINT = '#5a5e65'
BAND = '#17181b'
METER_BLUE = '#d2e6ff'
TRACE_BLUE = '#a3cbff'
METER_MID = '#ffc47a'
METER_HIGH = '#ff8e52'
CLIP = '#ff7a33'
LOUDNESS_COLOURS = {'M': '#4c9aff', 'S': '#8cc8ff', 'I': '#ffb04d'}
LOUDNESS_NAMES = {'M': 'MOM', 'S': 'SHORT', 'I': 'INT'}
PHASE_NAMES = {'correlation': 'CORR', 'balance': 'BAL'}
SEGMENT_OFF = 0.84

# a part's height, its inside's room, the meters' sizes (meterview's)
SECTION = 118
LCD_PAD = 8
BAR = 6
ROW = 12
METER_FLOOR = -48.0
METER_SCALE = (0, -3, -6, -9, -12, -18, -24, -30, -36, -42, -48)
SEGMENT = 1
SEGMENT_GAP = 2
NAME_WIDTH = 12
CLIP_GAP = 4
CLIP_WIDTH = 4
NAME_GAP = 4
READOUT = 34
STRIP_HEIGHT = 24
SCOPE_SIDE = 104
# METERS no wider than this (stretched across a wide rack its rows ran 800 px long; 440,
# PyWinAudio's screen as the user keeps it, too narrow), on the screen's middle (at its left,
# the rest of it empty at the right)
METERS_MOST = 600
BALANCE_RANGE = 6.0
BAR_HEIGHT = 0.4
BAR_PITCH = analyzer.BAR_PITCH
SPECTRUM_FREQS = (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000)
SPECTRUM_DBS = (0, -12, -24, -36, -48, -60, -72, -84)
GRAM_FREQS = (100, 1000, 10000)
NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
FONTS = {}


def get_font(size, bold=False, mono=False):
    # in points, as PyWinAudio's (wx.FontInfo takes their fractions)
    key = (size, bold, mono)
    if key not in FONTS:
        info = wx.FontInfo(size).FaceName('Consolas' if mono else 'Segoe UI')
        FONTS[key] = wx.Font(info.Bold() if bold or mono else info)
    return FONTS[key]


def mix(one, other, share):
    a, b = wx.Colour(one), wx.Colour(other)
    return wx.Colour(*[int(x + (y - x) * share) for x, y in zip(a.Get()[:3], b.Get()[:3])])


def get_short_hz(value):
    if value >= 1000:
        return ('%.1f' % (value / 1000)).rstrip('0').rstrip('.') + 'k'
    return '%d' % round(value)


def get_meter_colour(db):
    if db >= -3:
        return METER_HIGH
    if db >= -9:
        return METER_MID
    return METER_BLUE


def fill(gc, tone, x, y, w, h, radius=0):
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(tone))))
    if radius:
        gc.DrawRoundedRectangle(x, y, w, h, radius)
    else:
        gc.DrawRectangle(x, y, w, h)


def text(gc, words, x, y, size, tone, bold=False, mono=False, align='left'):
    uikit.set_font(gc, get_font(size, bold, mono), wx.Colour(tone))
    width, height = gc.GetTextExtent(words)[:2]
    if align == 'center':
        x -= width / 2.0
    elif align == 'right':
        x -= width
    gc.DrawText(words, x, y)
    return width, height


class AnalyzerPanel(RackModule):

    TITLE = 'ANALYZER'
    PREFERENCE = 'analyzer_panel'
    # one under another, PyWinAudio's order; SCOPE ('bars', the key it was kept by) its
    # oscilloscope
    PARTS = (('meters', 'METERS', SECTION), ('spectrum', 'SPECTRUM', SECTION),
             ('bars', 'SCOPE', SECTION), ('gram', 'SPECTROGRAM', SECTION))

    def __init__(self, parent):
        self.analyzer = analyzer.Analyzer()
        self.path = None
        # the readings made on a thread of their own (Run): the samples read, the FFTs and
        # the spectrogram's picture off the GUI's thread, which only draws them, under the
        # lock (they took 60 ms a second of it, ANALYZER open or the rack bar's OUT)
        self.lock = threading.Lock()
        self.version = 0
        self.drawn_version = -1
        self.gram_size = None
        self.gram_picture = None
        self.running = True
        RackModule.__init__(self, parent)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        threading.Thread(target=self.Run, daemon=True).start()

    def OnDestroy(self, event):
        # (its own: the visualizers laid on it send theirs here too)
        if event.GetEventObject() is self:
            self.running = False
        event.Skip()

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
            with self.lock:
                self.analyzer.Reset()
            self.reInitBuffer = True

    def Run(self):
        # the readings at the module's pace (its fps), read by it and by the rack bar's OUT
        while self.running:
            due = time.perf_counter() + 1.0 / max(self.buffer.fps, 1)
            try:
                self.Measure()
            except Exception:
                # (the player being made or closed under it: the next one)
                pass
            time.sleep(max(due - time.perf_counter(), 0.002))

    def Measure(self):
        '''(the thread's) the playing stream's next samples read; a new song starts the
        readings again; nothing done once they have fallen to rest with nothing playing'''
        if hasattr(self.parent, 'cue') is False:
            return
        path = self.parent.cue.path
        samples, rate = None, 0
        if self.IsActive():
            hstream, channels, _ = self.parent.GetVisualStream()
            rate = audio.get_native_fs(hstream) if hstream else 0
            samples = analyzer.read_samples(hstream, channels, analyzer.FFT_SIZE)
        with self.lock:
            if path != self.path:
                self.path = path
                self.analyzer.Reset()
            elif samples is None and self.analyzer.IsSettled():
                return
            self.analyzer.Update(samples, rate)
            self.MakeGram()
            self.version += 1

    def MakeGram(self):
        # (the thread's) the spectrogram's picture at the size it was last drawn: a column
        # a frame, the newest at the right, its rows stretched to the height
        if self.gram_size is None or self.parts.get('gram') is False:
            return
        iw, ih = self.gram_size
        columns = self.analyzer.GetGram(iw)
        rows = numpy.linspace(0, analyzer.GRAM_ROWS - 1, ih).astype(int)
        rgb = numpy.ascontiguousarray(analyzer.GRAM_COLOURS[columns][rows])
        self.gram_picture = (rgb.shape[1], rgb.shape[0], rgb.tobytes())

    def DirectDraw(self):
        # a frame only when the readings moved on, its size changed, or another change asked
        # for one (the mouse, a part folded); (resized with nothing playing it was left
        # white: no reading moved on)
        if self.version == self.drawn_version and self.reInitBuffer is False\
                and tuple(self.GetSize()) == getattr(self, 'drawn_size', None):
            return
        RackModule.DirectDraw(self)

    # the screen: its parts one under another, a line between them

    def GetSections(self):
        # (none while it is folded: its header alone)
        if self.folded:
            return []
        return [part[0] for part in self.PARTS if self.parts[part[0]]]

    def DrawIcon(self, gc, cx, cy):
        # a meter's three bars (PyWinAudio's meter view's), dimmed
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(self.parent.st.RACK_LABEL_COLOR))))
        bottom = cy + 6
        for k, height in enumerate((6, 11, 8)):
            gc.DrawRoundedRectangle(cx - 5 + k * 4, bottom - height, 2, height, 1)

    def GetHeight(self):
        if self.shown is False:
            return 0
        count = len(self.GetSections())
        return HEADER + (1 + count * SECTION + (count - 1) + LCD_PAD + 1 if count else 0)

    def GetScreen(self, w):
        count = len(self.GetSections())
        return wx.Rect(9, HEADER + 1, w - 18, count * SECTION + count - 1)

    def SetRectDraw(self, dc):
        '''its header and its screen's still grounds one picture (made again when they
        change: its size, its parts, its state, the mouse on a key), the moving readings drawn
        over it, a plain DC's (bitmaps and rectangles) but the spectrum's curve; (every frame
        drawn whole, the header's keys, the grids, the segments one by one: 13 ms a frame, 380
        a second at 30 fps)'''
        with self.lock:
            self.drawn_version = self.version
            w, h = self.GetSize()
            self.drawn_size = (w, h)
            sections = self.GetSections()
            # (its header a picture of its own, made again when the mouse moves over its keys
            # or its state changes: in the screen's, the whole of it was made again, 27 to
            # 31 ms each time the mouse went over a key, the keys slow to answer, the user)
            key = (w, h, tuple(sections), self.folded, uikit.get_style_version())
            if getattr(self, 'background', None) is None or self.background[0] != key:
                self.background = (key,) + self.MakeBackground(w, h, sections)
            dc.Blit(0, 0, w, h, self.background_dc, 0, 0)
            _, _, header_dc, hits = self.GetHeaderPicture(w)
            # (its bottom row left: folded, the line under it is there)
            dc.Blit(0, 0, w, min(HEADER, h - 1), header_dc, 0, 0)
            self.hits = list(hits)
            self.regions = dict()
            y = HEADER + 1
            for name in sections:
                rect = wx.Rect(9, y, w - 18, SECTION)
                if name == 'meters':
                    self.DrawMeters(dc, rect)
                elif name == 'spectrum':
                    self.DrawSpectrum(dc, rect)
                elif name == 'bars':
                    self.DrawWave(dc, rect)
                elif name == 'gram':
                    self.DrawGram(dc, rect)
                y += SECTION + 1
        # the header's bars and dots, laid on BARS before: hidden (the bars in METERS now)
        if getattr(self, 'bars_laid', 0) is not None:
            self.bars_laid = None
            wx.CallAfter(self.parent.LayoutAnalyzerVisuals)

    def GetHeaderPicture(self, w):
        # (key, its picture, a DC with it, its keys' hits)
        key = (w, self.GetState(), self.IsActive(), self.hovered, getattr(self, 'key_down', None),
               self.folded, uikit.get_style_version())
        cache = getattr(self, 'header_cache', None)
        if cache is None or cache[0] != key:
            bitmap = wx.Bitmap(max(w, 1), HEADER)
            dc = wx.MemoryDC(bitmap)
            dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
            dc.Clear()
            gc = wx.GraphicsContext.Create(dc)
            self.hits = []
            self.DrawHeader(dc, gc, w)
            del gc
            cache = self.header_cache = (key, bitmap, dc, list(self.hits))
        return cache

    def MakeBackground(self, w, h, sections):
        bitmap = wx.Bitmap(max(w, 1), max(h, 1))
        dc = wx.MemoryDC(bitmap)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        draw_rule(gc, self.parent.st, 0, h - 1, w)
        # (its header drawn over it: GetHeaderPicture)
        if sections:
            self.PaintScreen(gc, self.GetScreen(w), sections)
        del gc
        dc.SelectObject(wx.NullBitmap)
        # the meters' lit segments over a copy of it (a frame copies the spans it needs); the
        # goniometer's ground, its pixels, its dots mixed into them (a clear picture laid
        # over it: 1.6 ms)
        self.lit = self.MakeLit(bitmap, w) if 'meters' in sections else None
        self.scope_ground = None
        if 'meters' in sections:
            g = self.GetMetersLayout(wx.Rect(9, HEADER + 1, w - 18, SECTION))
            scope, side = g['scope'], analyzer.SCOPE_SIDE
            rect = wx.Rect(scope.x + (scope.width - side) // 2,
                           scope.y + (scope.height - side) // 2, side, side)
            # (none while it is smaller than its screen: its first frame's, 20 px)
            if wx.Rect(0, 0, w, h).Contains(rect):
                image = bitmap.GetSubBitmap(rect).ConvertToImage()
                self.scope_ground = (rect, numpy.frombuffer(bytes(image.GetData()),
                                                            dtype='uint8')
                                     .reshape(side, side, 3).astype('float32'))
        # (kept in a DC: blitted at every frame, the spectrum's ground copied from it; put
        # in it after the copies above were taken: a bitmap in a DC copied black)
        self.background_dc = wx.MemoryDC(bitmap)
        self.spectrum_canvas = None
        return bitmap, []

    def PaintScreen(self, gc, rect, sections):
        # its rim, its ground, the lines between its parts, each part's still ground
        fill(gc, LCD_RIM, rect.x - 1, rect.y - 1, rect.width + 2, rect.height + 2, 3)
        fill(gc, LCD, rect.x, rect.y, rect.width, rect.height, 2)
        y = rect.y
        for k, key in enumerate(sections):
            if k:
                fill(gc, LCD_RIM, rect.x, y - 1, rect.width, 1)
            part = wx.Rect(rect.x, y, rect.width, SECTION)
            if key == 'meters':
                self.PaintMetersGround(gc, part)
            elif key == 'spectrum':
                self.PaintSpectrumGround(gc, part)
            elif key == 'bars':
                self.PaintWaveGround(gc, part)
            y += SECTION + 1

    def SetDC(self, dc, tone):
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Colour(tone)))

    def DrawText(self, dc, words, right, y, size, tone, mono=True):
        # right-aligned at right (the readouts')
        dc.SetFont(get_font(size, mono=mono))
        dc.SetTextForeground(wx.Colour(tone))
        dc.DrawText(words, int(right - dc.GetTextExtent(words)[0]), int(y))

    # METERS

    def GetMetersLayout(self, section):
        '''meterview's layout_level: the goniometer at its left, a line, the rows (L, R, their
        scale, the bars' strip over M, S and I's rows, C, B) between equal wings, their names
        and values at the right'''
        width = min(section.width, METERS_MOST)
        narrowed = width < section.width
        section = wx.Rect(section.x + (section.width - width) // 2, section.y, width,
                          section.height)
        key = (tuple(section), narrowed)
        cached = getattr(self, 'meters_layout', None)
        if cached is not None and cached[0] == key:
            return cached[1]
        g = dict()
        side = min(SCOPE_SIDE, section.height)
        readout = (CLIP_GAP + CLIP_WIDTH + NAME_GAP + NAME_WIDTH + NAME_GAP + READOUT * 2 +
                   LCD_PAD)
        wing = max(readout, side + 1 + LCD_PAD)
        g['scope'] = wx.Rect(section.x + 4, section.y + (section.height - side) // 2 + 4,
                             side - 8, side - 8)
        g['scope_divider'] = wx.Rect(section.x + side, section.y + LCD_PAD, 1,
                                     section.height - LCD_PAD * 2)
        # on the screen's middle: a line at either side of it, as the goniometer's
        g['edges'] = [wx.Rect(x, section.y + LCD_PAD, 1, section.height - LCD_PAD * 2)
                      for x in (section.x, section.x + section.width - 1)] if narrowed else []
        pitch = SEGMENT + SEGMENT_GAP
        x0 = section.x + wing
        x1 = section.x + section.width - wing
        count = max(1, (x1 - x0 + SEGMENT_GAP) // pitch)
        x0 += (x1 - x0 - (count * pitch - SEGMENT_GAP)) // 2
        x1 = x0 + count * pitch
        body = wx.Rect(section.x + side + 1, section.y, section.width - side - 1, section.height)
        inner = wx.Rect(body.x + LCD_PAD, body.y + LCD_PAD, body.width - LCD_PAD * 2,
                        body.height - LCD_PAD * 2)
        rows, boxes = dict(), dict()
        y = inner.y
        for name in ('L', 'R', None, 'M', 'S', 'I', '', 'C', 'B'):
            if name is None:
                g['scale_y'] = y
                y += ROW + 4
                continue
            if name == '':
                y += 4
                continue
            rows[name] = wx.Rect(x0, y + (ROW - BAR) // 2, x1 - x0, BAR)
            y += ROW
        right = inner.x + inner.width
        for name in ('L', 'R'):
            row = rows[name]
            boxes[name + 'pk'] = wx.Rect(right - READOUT * 2, row.y - 3, READOUT, BAR + 6)
            boxes[name + 'rms'] = wx.Rect(right - READOUT, row.y - 3, READOUT, BAR + 6)
        for name in ('M', 'S', 'I', 'C', 'B'):
            row = rows[name]
            boxes[name] = wx.Rect(right - READOUT * 2, row.y - 3, READOUT, BAR + 6)
        g['correlation'], g['balance'] = rows.pop('C'), rows.pop('B')
        top, bottom = rows['M'].y - 3, rows['I'].y + BAR + 3
        middle = (top + bottom) // 2
        g['strip'] = wx.Rect(x0 - LCD_PAD, middle - STRIP_HEIGHT // 2 - 6,
                             x1 - SEGMENT_GAP - x0 + LCD_PAD * 2, STRIP_HEIGHT + 12)
        for name in ('M', 'S', 'I'):
            rows.pop(name)
        g['rows'], g['boxes'], g['right'] = rows, boxes, right
        g['name_x'] = x1 - SEGMENT_GAP + CLIP_GAP + CLIP_WIDTH + NAME_GAP
        g['clips'] = [wx.Rect(x1 - SEGMENT_GAP + CLIP_GAP, rows[name].y, CLIP_WIDTH, BAR)
                      for name in ('L', 'R')]
        g['xs'] = [x0 + k * pitch for k in range(count)]
        self.meters_layout = (key, g)
        return g

    def ToX(self, row, db):
        share = (min(max(db, METER_FLOOR), 0.0) - METER_FLOOR) / -METER_FLOOR
        return row.x + row.width * share

    def FromX(self, row, x):
        share = (x - row.x) / float(max(1, row.width))
        return METER_FLOOR + -METER_FLOOR * min(max(share, 0.0), 1.0)

    def GetBarsInner(self, strip):
        return wx.Rect(strip.x + LCD_PAD, strip.y + 6, strip.width - LCD_PAD * 2, strip.height - 12)

    def PaintMetersGround(self, gc, section):
        g = self.GetMetersLayout(section)
        rows = g['rows']
        first, last = rows['L'], rows['R']
        # the goniometer's line and its axes: M up, L and R the diagonals
        for divider in [g['scope_divider']] + g['edges']:
            fill(gc, LCD_GRID, divider.x, divider.y, divider.width, divider.height)
        scope = g['scope']
        cx, cy = scope.x + scope.width / 2.0, scope.y + scope.height / 2.0
        radius = min(scope.width, scope.height) / 2.0 - 5
        gc.SetPen(wx.Pen(wx.Colour(LCD_GRID), 1))
        gc.StrokeLine(cx, cy - radius, cx, cy + radius)
        gc.StrokeLine(cx - radius * 0.7, cy - radius * 0.7, cx + radius * 0.7, cy + radius * 0.7)
        gc.StrokeLine(cx + radius * 0.7, cy - radius * 0.7, cx - radius * 0.7, cy + radius * 0.7)
        text(gc, 'L', cx - radius * 0.7 - 2, cy - radius * 0.7 - 6, 7, LCD_TEXT, align='right')
        text(gc, 'R', cx + radius * 0.7 + 2, cy - radius * 0.7 - 6, 7, LCD_TEXT)
        # the scale: its lines across the channels' rows, its numbers under them
        drawn = None
        for value in METER_SCALE:
            x = round(self.ToX(first, value))
            fill(gc, LCD_AXIS if value == 0 else LCD_GRID, x, first.y - 2, 1,
                 last.y + last.height + 2 - (first.y - 2))
            least = value == METER_SCALE[-1]
            if drawn is None or drawn - x >= (26 if least else 18):
                text(gc, str(value), x, g['scale_y'] + 1, 6.5, LCD_TEXT,
                     align='left' if least else 'center')
                drawn = x
        # the segments dark, the names
        for name, row in rows.items():
            for x in g['xs']:
                tone = get_meter_colour(self.FromX(row, x + SEGMENT / 2.0))
                fill(gc, mix(tone, LCD, SEGMENT_OFF), x, row.y, SEGMENT, row.height)
            text(gc, name, g['name_x'] + NAME_WIDTH / 2.0, row.y - 4, 7.5, LCD_TEXT, bold=True,
                 align='center')
        for clip in g['clips']:
            fill(gc, LCD_GRID, clip.x, clip.y, clip.width, clip.height)
        # the values' names, flush with their numbers' right
        boxes = g['boxes']
        names = [(boxes['Lpk'].x + boxes['Lpk'].width, g['scale_y'] + 1, 'PK'),
                 (boxes['Lrms'].x + boxes['Lrms'].width, g['scale_y'] + 1, 'RMS')]
        names += [(boxes[k].x + boxes[k].width * 2, boxes[k].y + 1, v)
                  for k, v in LOUDNESS_NAMES.items()]
        names += [(boxes[k[0].upper()].x + boxes[k[0].upper()].width * 2,
                   boxes[k[0].upper()].y + 1, v) for k, v in PHASE_NAMES.items()]
        for x, y, words in names:
            text(gc, words, x, y, 6.5, FAINT, mono=True, align='right')
        # the bars' strip: its bars dark (dots), the correlation's and the balance's
        # segments dark, their middles marked
        bars = self.GetBarsInner(g['strip'])
        xs, halves, middle = self.GetBarSpans(bars, numpy.zeros(2), 1)
        for x, half in zip(xs, halves):
            fill(gc, mix(METER_BLUE, LCD, SEGMENT_OFF), x, middle - half, 1, half * 2)
        centre = g['xs'][len(g['xs']) // 2]
        for name in ('correlation', 'balance'):
            bar = g[name]
            for x in g['xs']:
                fill(gc, mix(METER_BLUE, LCD, SEGMENT_OFF), x, bar.y, SEGMENT, bar.height)
            fill(gc, LCD_AXIS, centre, bar.y - 2, SEGMENT, 2)
            fill(gc, LCD_AXIS, centre, bar.y + bar.height, SEGMENT, 2)

    def GetBarSpans(self, rect, levels, floor):
        # (xs, halves, middle) of the bars across rect from the levels (meterview's
        # get_bar_spans: resampled to a bar every BAR_PITCH px, on the strip's middle)
        count = max(2, rect.width // BAR_PITCH + 1)
        levels = numpy.asarray(levels, dtype='float64')
        source = len(levels)
        if source < 2:
            levels = numpy.resize(levels, count)
        elif count >= source:
            levels = numpy.interp(numpy.linspace(0, source - 1, count), numpy.arange(source),
                                  levels)
        else:
            edges = numpy.linspace(0, source, count + 1).astype(int)
            edges[1:] = numpy.maximum(edges[1:], edges[:-1] + 1)
            levels = numpy.maximum.reduceat(levels, numpy.minimum(edges[:-1], source - 1))
        offset = (rect.width - BAR_PITCH * (count - 1)) // 2
        middle = rect.y + rect.height // 2
        halves = numpy.maximum(floor, numpy.round(levels * rect.height * BAR_HEIGHT / 2)).astype(int)
        return rect.x + BAR_PITCH * numpy.arange(count) + offset, halves, middle

    def MakeLit(self, background, w):
        # (a DC on the background with every channel and the phase's segments lit in their
        # tones, one with the phase's in METER_MID: a frame blits the spans it needs)
        g = self.GetMetersLayout(wx.Rect(9, HEADER + 1, w - 18, SECTION))
        sources = []
        for phase in (METER_BLUE, METER_MID):
            dc = wx.MemoryDC(background.GetSubBitmap(wx.Rect(0, 0, background.GetWidth(),
                                                             background.GetHeight())))
            dc.SetPen(wx.TRANSPARENT_PEN)
            for row in g['rows'].values():
                for x in g['xs']:
                    dc.SetBrush(wx.Brush(wx.Colour(
                        get_meter_colour(self.FromX(row, x + SEGMENT / 2.0)))))
                    dc.DrawRectangle(x, row.y, SEGMENT, row.height)
            dc.SetBrush(wx.Brush(wx.Colour(phase)))
            for name in ('correlation', 'balance'):
                bar = g[name]
                for x in g['xs']:
                    dc.DrawRectangle(x, bar.y, SEGMENT, bar.height)
            sources.append(dc)
        return sources

    def DrawMeters(self, dc, section):
        a = self.analyzer
        g = self.GetMetersLayout(section)
        rows = g['rows']
        lit, mid = self.lit
        # the channels: lit to the higher of the peak and the RMS, the hold a tick, a clip lamp
        for c, name in enumerate(('L', 'R')):
            row = rows[name]
            level = max(a.peak[c], a.rms[c])
            end = int(round(self.ToX(row, level))) if level > METER_FLOOR else row.x
            if end > row.x:
                dc.Blit(row.x, row.y, end - row.x, row.height, lit, row.x, row.y)
            if a.hold[c] > METER_FLOOR:
                self.SetDC(dc, '#f2f4f6')
                dc.DrawRectangle(int(round(self.ToX(row, a.hold[c]))) - 1, row.y - 2, 2,
                                 row.height + 4)
            if a.clip[c]:
                clip = g['clips'][c]
                self.SetDC(dc, CLIP)
                dc.DrawRectangle(clip)
        # the goniometer's dots, kept a while, mixed into its ground's pixels (its picture
        # its own size: no scaling)
        glow = numpy.clip(a.scope, 0.0, 1.0)
        if float(glow.max()) >= 0.02 and self.scope_ground is not None:
            rect, ground = self.scope_ground
            base = numpy.array(wx.Colour(LCD).Get()[:3], dtype='float32')
            dot = numpy.array(wx.Colour(TRACE_BLUE).Get()[:3], dtype='float32')
            rgb = base + (dot - base) * glow[..., None]
            share = numpy.minimum(1.0, glow * 4)[..., None]
            image = (ground + (rgb - ground) * share).astype('uint8')
            dc.DrawBitmap(wx.Bitmap.FromBuffer(rect.width, rect.height, image), rect.x, rect.y)
        # the spectrum's bars, one picture (meterview's draw_bars)
        bars = self.GetBarsInner(g['strip'])
        self.analyzer.bar_scale = max(1, int(round(bars.width / float(analyzer.BAR_SET * BAR_PITCH))))
        if a.bars is not None and bars.width > 0 and bars.height > 0:
            xs, halves, middle = self.GetBarSpans(bars, numpy.minimum(a.bars, 1.0 / BAR_HEIGHT), 0)
            inside = (xs >= bars.x) & (xs < bars.x + bars.width)
            xs, halves = xs[inside] - bars.x, halves[inside]
            rows_ = numpy.arange(bars.y, bars.y + bars.height)[:, None]
            # opaque: the ground, the dark dots of the bars at rest, the bars (a clear picture
            # laid over the ground cost a ms)
            image = numpy.empty((bars.height, bars.width, 3), dtype='uint8')
            image[:] = list(wx.Colour(LCD).Get()[:3])
            rest = (rows_ >= middle - 1) & (rows_ < middle + 1)
            image[:, xs] = numpy.where(rest[..., None],
                                       list(mix(METER_BLUE, LCD, SEGMENT_OFF).Get()[:3]),
                                       image[:, xs])
            on = (rows_ >= middle - halves[None, :]) & (rows_ < middle + halves[None, :])
            columns = image[:, xs]
            columns[on] = list(wx.Colour(METER_BLUE).Get()[:3])
            image[:, xs] = columns
            bitmap = getattr(self, 'bars_bitmap', None)
            if bitmap is None or tuple(bitmap.GetSize()) != (bars.width, bars.height):
                bitmap = self.bars_bitmap = wx.Bitmap.FromBuffer(bars.width, bars.height, image)
            else:
                bitmap.CopyFromBuffer(image, wx.BitmapBufferFormat_RGB)
            dc.DrawBitmap(bitmap, bars.x, bars.y)
        # the correlation and the balance: lit from the middle to the value, a bright tick
        # at its end
        xs = g['xs']
        centre = len(xs) // 2
        for name, share, value, tone in (
                ('correlation', (a.correlation + 1) / 2.0,
                 '%+.2f' % a.correlation if abs(a.correlation) >= 0.005 else '0.00',
                 METER_BLUE if a.correlation >= 0 else METER_MID),
                ('balance', 0.5 + max(-1.0, min(1.0, a.balance / BALANCE_RANGE)) / 2.0,
                 '%+.1f' % a.balance if abs(a.balance) >= 0.05 else '0.0', METER_BLUE)):
            bar = g[name]
            reach = int(round((share - 0.5) * 2 * centre))
            end = min(max(centre + reach, 0), len(xs) - 1)
            low, high = min(centre, end), max(centre, end)
            dc.Blit(xs[low], bar.y, xs[high] + SEGMENT - xs[low], bar.height,
                    lit if tone == METER_BLUE else mid, xs[low], bar.y)
            self.SetDC(dc, mix(tone, '#ffffff', 0.45).GetAsString(wx.C2S_HTML_SYNTAX))
            dc.DrawRectangle(xs[end], bar.y - 1, SEGMENT, bar.height + 2)
            box = g['boxes']['C' if name == 'correlation' else 'B']
            self.DrawText(dc, value, box.x + box.width, box.y, 7.5, TEXT)
        # the values: PK and RMS a channel, the loudness in its colours
        momentary, short, integrated = a.loudness
        values = {'Lpk': (a.hold[0], analyzer.FLOOR), 'Rpk': (a.hold[1], analyzer.FLOOR),
                  'Lrms': (a.rms[0], analyzer.FLOOR), 'Rrms': (a.rms[1], analyzer.FLOOR),
                  'M': (momentary, analyzer.LOUDNESS_FLOOR),
                  'S': (short, analyzer.LOUDNESS_FLOOR),
                  'I': (integrated, analyzer.LOUDNESS_FLOOR)}
        for key, box in g['boxes'].items():
            if key not in values:
                continue
            value, floor = values[key]
            words = '--' if value <= floor else '%.1f' % value
            if key.endswith('pk'):
                tone = CLIP if value > -0.1 else TEXT
            elif key.endswith('rms'):
                tone = DIM
            else:
                tone = LOUDNESS_COLOURS[key]
            self.DrawText(dc, words, box.x + box.width, box.y, 7.5, tone)

    # SPECTRUM

    def GetInner(self, rect):
        return wx.Rect(rect.x + LCD_PAD, rect.y + LCD_PAD, rect.width - LCD_PAD * 2,
                       rect.height - LCD_PAD * 2)

    def FreqX(self, inner, freq):
        return inner.x + inner.width * math.log(min(max(freq, 20.0), 20000.0) / 20.0) /\
            math.log(1000.0)

    def DbYs(self, inner, dbs):
        floor = analyzer.SPECTRUM_FLOOR
        share = (numpy.clip(dbs, floor, 0.0) - floor) / -floor
        return inner.y + inner.height * (1 - share)

    def PaintSpectrumGround(self, gc, section):
        inner = self.GetInner(section)
        for freq in SPECTRUM_FREQS:
            fill(gc, LCD_GRID, round(self.FreqX(inner, freq)), inner.y, 1, inner.height)
        for db in SPECTRUM_DBS:
            fill(gc, LCD_AXIS if db == 0 else LCD_GRID, inner.x, round(float(self.DbYs(inner, db))),
                 inner.width, 1)

    def GetSpectrumNames(self, dc, section):
        # (x, y, words) of its frequencies under it and its dB at its right, worked out once
        # a size (drawn as text over the curve: a clear picture laid over it cost a ms)
        key = tuple(section)
        cached = getattr(self, 'spectrum_names', None)
        if cached is not None and cached[0] == key:
            return cached[1]
        inner = self.GetInner(section)
        bottom = inner.y + inner.height
        last, right, names = len(SPECTRUM_FREQS) - 1, None, []
        dc.SetFont(get_font(6.5))
        for index, freq in enumerate(SPECTRUM_FREQS):
            x = round(self.FreqX(inner, freq))
            words = get_short_hz(freq)
            w, h = dc.GetTextExtent(words)
            left = x + 3 if index == 0 else x - w - 3 if index == last else x - w // 2
            # (a name touching the one before it left out: narrow, 10k20k)
            if right is not None and left < right + 4:
                continue
            names.append((left, bottom - h - 2, words))
            right = left + w
        step = 2 if float(self.DbYs(inner, -12) - self.DbYs(inner, 0)) < 16 else 1
        for db in SPECTRUM_DBS[:-1][::step]:
            y = round(float(self.DbYs(inner, db)))
            words = str(db)
            w, h = dc.GetTextExtent(words)
            names.append((inner.x + inner.width - w - 4, y + 1 if db == 0 else y - h, words))
        self.spectrum_names = (key, names)
        return names

    def DrawSpectrumNames(self, dc, section):
        names = self.GetSpectrumNames(dc, section)
        dc.SetFont(get_font(6.5))
        dc.SetTextForeground(wx.Colour(LCD_TEXT))
        for x, y, words in names:
            dc.DrawText(words, int(x), int(y))

    def DrawSpectrum(self, dc, section):
        '''its curve on a picture of its own, its GraphicsContext kept (made at every frame, a
        ms of it), its ground copied from the background; its names over it'''
        a = self.analyzer
        inner = self.GetInner(section)
        self.regions['spectrum'] = inner
        count = len(a.spectrum)
        xs = (inner.x + inner.width * (numpy.arange(count) + 0.5) / count).tolist()
        canvas = getattr(self, 'spectrum_canvas', None)
        if canvas is None or canvas[0] != tuple(section):
            bitmap = wx.Bitmap(max(section.width, 1), max(section.height, 1))
            mdc = wx.MemoryDC(bitmap)
            gc = wx.GraphicsContext.Create(mdc)
            gc.Translate(-section.x, -section.y)
            canvas = self.spectrum_canvas = (tuple(section), bitmap, mdc, gc)
        _, bitmap, mdc, gc = canvas
        mdc.Blit(0, 0, section.width, section.height, self.background_dc, section.x, section.y)
        if float(a.spectrum.max()) > analyzer.SPECTRUM_FLOOR\
                or float(a.peak_line.max()) > analyzer.SPECTRUM_FLOOR:
            ys = self.DbYs(inner, a.spectrum)
            bottom = inner.y + inner.height
            points = list(zip(xs, ys.tolist()))
            gc.Clip(inner.x, inner.y, inner.width, inner.height)
            tone = wx.Colour(TRACE_BLUE)
            top = float(ys.min())
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateLinearGradientBrush(
                0, top, 0, bottom, wx.Colour(tone.Red(), tone.Green(), tone.Blue(), 150),
                wx.Colour(tone.Red(), tone.Green(), tone.Blue(), 12)))
            gc.DrawLines([(points[0][0], bottom)] + points + [(points[-1][0], bottom)])
            gc.SetBrush(wx.NullGraphicsBrush)
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(tone).Width(1.4).Join(wx.JOIN_ROUND)))
            gc.StrokeLines(points)
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(200, 204, 210, 110)).Width(1)))
            gc.StrokeLines(list(zip(xs, self.DbYs(inner, a.peak_line).tolist())))
            gc.ResetClip()
            gc.Flush()
        mdc.SetDeviceOrigin(-section.x, -section.y)
        self.DrawSpectrumNames(mdc, section)
        mdc.SetDeviceOrigin(0, 0)
        dc.Blit(section.x, section.y, section.width, section.height, mdc, 0, 0)
        self.DrawHover(dc, inner, xs)

    def DrawHover(self, dc, inner, xs):
        # under the mouse: its frequency, its note and the level there
        pointer = getattr(self, 'pointer', None)
        if pointer is None or inner.Contains(pointer) is False:
            return
        x = pointer.x
        freq = 20.0 * 1000.0 ** ((x - inner.x) / float(max(1, inner.width)))
        db = float(numpy.interp(x, xs, self.analyzer.spectrum))
        midi = int(round(12 * math.log2(freq / 440.0) + 69))
        hz = '%.0f Hz' % freq if freq < 1000 else '%.2f kHz' % (freq / 1000)
        words = '%s  %s%d  %.1f dB' % (hz, NOTE_NAMES[midi % 12], midi // 12 - 1, db)
        self.SetDC(dc, LCD_AXIS)
        dc.DrawRectangle(x, inner.y, 1, inner.height)
        dc.SetFont(get_font(7.5, mono=True))
        w, h = dc.GetTextExtent(words)
        box = wx.Rect(int(x + 6), inner.y + 4, int(w + 12), int(h + 6))
        if box.x + box.width > inner.x + inner.width:
            box.x = int(x - 6 - box.width)
        dc.SetPen(wx.Pen(wx.Colour(LCD_RIM), 1))
        dc.SetBrush(wx.Brush(wx.Colour(BAND)))
        dc.DrawRectangle(box)
        dc.SetTextForeground(wx.Colour(TEXT))
        dc.DrawText(words, box.x + 6, box.y + 3)

    def CATCH_EVT_GLOBAL(self, event):
        # where the mouse is, for the spectrum's readout (drawn again as it moves over it)
        pointer = wx.Point(int(event.X), int(event.Y)) if self.onClient else None
        if pointer != getattr(self, 'pointer', None):
            inner = getattr(self, 'regions', {}).get('spectrum')
            if inner is not None and (inner.Contains(pointer or wx.Point(-1, -1)) or
                                      inner.Contains(getattr(self, 'pointer', None)
                                                     or wx.Point(-1, -1))):
                self.reInitBuffer = True
            self.pointer = pointer
        RackModule.CATCH_EVT_GLOBAL(self, event)

    # SCOPE (the oscilloscope)

    def PaintWaveGround(self, gc, section):
        inner = self.GetInner(section)
        for y in (inner.y + inner.height // 4, inner.y + inner.height * 3 // 4):
            fill(gc, LCD_GRID, inner.x, y, inner.width, 1)
        fill(gc, LCD_AXIS, inner.x, inner.y + inner.height // 2, inner.width, 1)

    def PaintWave(self, image, wave):
        # columns of the oscilloscope: the highest to the lowest dim, the RMS bright
        height = image.shape[0]
        middle = height / 2.0
        high, low, rms = wave
        rows = numpy.arange(height)[:, None]
        top = numpy.floor(middle - numpy.clip(high, -1, 1) * (middle - 1))[None, :]
        bottom = numpy.ceil(middle - numpy.clip(low, -1, 1) * (middle - 1))[None, :]
        reach = numpy.clip(rms, 0, 1) * (middle - 1)
        inside = (rows >= numpy.floor(middle - reach)[None, :]) &\
            (rows <= numpy.ceil(middle + reach)[None, :])
        silent = (numpy.abs(high) < 1e-4) & (numpy.abs(low) < 1e-4)
        # its ground and grid in it (opaque: a clear picture laid over the ground cost a ms)
        image[:] = list(wx.Colour(LCD).Get()[:3])
        for y in (height // 4, height * 3 // 4):
            image[y] = list(wx.Colour(LCD_GRID).Get()[:3])
        image[height // 2] = list(wx.Colour(LCD_AXIS).Get()[:3])
        image[((rows >= top) & (rows <= bottom)) & ~silent[None, :]] =\
            list(mix(TRACE_BLUE, LCD, 0.45).Get()[:3])
        image[inside & (reach[None, :] > 0.5)] = list(wx.Colour(TRACE_BLUE).Get()[:3])

    def DrawWave(self, dc, section):
        # its picture moved on by the columns read since the last frame, they alone painted
        # (meterview's draw_wave; painted whole every frame, 2 ms)
        inner = self.GetInner(section)
        width, height = inner.width, inner.height
        if width <= 3 or height <= 3:
            return
        a = self.analyzer
        index = a.wave_index
        image = getattr(self, 'wave_image', None)
        new = (index - getattr(self, 'wave_seen', index)) % analyzer.WAVE_COLUMNS
        if image is None or image.shape[:2] != (height, width) or new >= width:
            image = self.wave_image = numpy.zeros((height, width, 3), dtype='uint8')
            self.PaintWave(image, a.GetWave(width))
            self.wave_bitmap = wx.Bitmap.FromBuffer(width, height, image)
        elif new:
            image[:, :-new] = image[:, new:]
            self.PaintWave(image[:, -new:], a.GetWave(new))
            self.wave_bitmap.CopyFromBuffer(image, wx.BitmapBufferFormat_RGB)
        self.wave_seen = index
        dc.DrawBitmap(self.wave_bitmap, inner.x, inner.y)

    # SPECTROGRAM

    def DrawGram(self, dc, section):
        inner = self.GetInner(section)
        iw, ih = inner.width, inner.height
        if iw <= 3 or ih <= 3:
            return
        # its picture made on the readings' thread (MakeGram) at this size, copied into a
        # bitmap kept (a new one every frame before)
        self.gram_size = (int(iw), int(ih))
        picture = self.gram_picture
        if picture is not None and picture[1] == int(ih) and picture[0] == int(iw):
            pw, ph, data = picture
            bitmap = getattr(self, 'gram_bitmap', None)
            if bitmap is None or tuple(bitmap.GetSize()) != (pw, ph):
                bitmap = self.gram_bitmap = wx.Bitmap.FromBuffer(pw, ph, data)
            elif getattr(self, 'gram_drawn', None) is not picture:
                bitmap.CopyFromBuffer(data, wx.BitmapBufferFormat_RGB)
            self.gram_drawn = picture
            dc.DrawBitmap(bitmap, inner.x, inner.y)
        self.DrawGramNames(dc, section)

    def DrawGramNames(self, dc, section):
        # at its left, inside it (the right edge would hide the sound coming in)
        inner = self.GetInner(section)
        dc.SetFont(get_font(6.5))
        dc.SetTextForeground(wx.Colour(LCD_TEXT))
        for freq in GRAM_FREQS:
            share = math.log(min(max(freq, 20.0), 20000.0) / 20.0) / math.log(1000.0)
            y = round(inner.y + inner.height - 1 - (inner.height - 1) * share)
            words = get_short_hz(freq)
            dc.DrawText(words, inner.x + 4, int(y - dc.GetTextExtent(words)[1] // 2))
