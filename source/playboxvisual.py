# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import images
import math
import numpy
import mfeats
import radio
import threading
import time
import uikit
import wx

from macroboxlib import FONT_PLAYINFO
from macroboxlib import GetPreference
from macroboxlib import RectBox
from playboxlib import PlayBoxDnD
from playboxlib import SCRATCH_PIXELS_PER_SECOND
from utilities import Struct


def get_span_text(seconds):
    # 2.1 s, 45 s, 3:20
    if seconds < 10:
        return f'{seconds:.1f} s'
    if seconds < 60:
        return f'{round(seconds)} s'
    return f'{int(seconds // 60)}:{int(seconds % 60):02d}'


def draw_live_trace(dc, parent, rect, seconds, spread=audio.WAVEFORM_BAND_SPREAD):
    '''a station's last seconds as a scrolling waveform, False for a file'''
    if parent.IsStreamTrack() is False:
        return False
    trace = parent.GetLiveTrace()
    x, y, w, h = rect
    if parent.GetLiveMessage() is not None:
        # nothing to play: a message instead (PlayBox.DrawLiveMessage)
        return True
    if trace is None or len(trace) == 0 or w <= 0 or h <= 0:
        return True
    count = len(trace)
    end = count
    start = end - seconds / mfeats.WAVEFORM_COLUMN_SECONDS
    image = audio.paint_waveform_3band(
        trace, w, h, ground=numpy.array(parent.st.PLAY_BG_COLOR, dtype=float),
        start=start, end=end, spread=spread)
    dc.DrawBitmap(wx.Bitmap.FromBuffer(w, h, image.tobytes()), x, y)
    return True


# the lanes over what plays: the ground this share to the accent
LANE_PLAYED = 0.4


def draw_snap_flash(dc, x, top, height, share):
    # a snapped seek's line: the accent, 3 px, fading by share
    gc = wx.GraphicsContext.Create(dc)
    if gc is None:
        return
    accent = uikit.colour(uikit.ui().ACCENT)
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(accent.Red(), accent.Green(), accent.Blue(),
                                                  int(230 * share)))))
    gc.DrawRectangle(x - 1, top, 3, height)


def get_lane_played(st):
    ground = wx.Colour(st.PLAY_BG_COLOR)
    accent = uikit.colour(uikit.ui().ACCENT)
    return tuple(int(g + (a - g) * LANE_PLAYED) for g, a in
                 zip(ground.Get()[:3], accent.Get()[:3]))


class PlayBoxSpectrum(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.scale = 1
        self.max_scale = 3
        # 300 at most
        self.max_width = 300
        self.width = 320 * self.scale
        self.height = 30
        self.resolution = 1
        self.saturation = 0.1
        self.bar_pitch = 3
        self.bar_width = 1

        fps = GetPreference('spectrum_fps')
        if fps is None:
            fps = 60
        self.buffer.fps = fps

        self.ground = ((0, 0, 0, 0),)
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        # self.InitGround()
        self.InitBuffer()

    def InitGround(self):
        w, h = (self.width, self.height)
        len_spectrum = 103 * self.scale
        spLength = len_spectrum - 1
        sw = int(1.0 * w / spLength)
        offset = (w - sw * spLength) * 0.5
        ground = [(sw * i + offset + 1, h / 2 - 1) for i in range(len_spectrum)]
        ground += [(sw * i + offset + 1, h / 2) for i in range(len_spectrum)]
        self.ground = ground

    def SetRectPre(self):
        pass

    def CATCH_EVT_GLOBAL(self, event):
        # while playing the visual clock draws it (PlayBoxVisualClock)
        if self.parent.IsVisualPlaying() is False:
            self.DirectDraw()

    def GetSpectrumVectorScope(self):
        if self.parent.IsVisualPlaying() is False:
            return None, None
        if self.IsShown() is False and self.parent.VectorScope.IsShown() is False:
            return None, None
        hstream, channel, autogain = self.parent.GetVisualStream()
        return audio.get_stream_spectrum_vectorscope(
            hstream, self.parent.VectorScope.size, channel, autogain,
            spectrum_scale=self.scale)

    def SetRectDraw(self, dc):
        spectrum, vectorscope = self.GetSpectrumVectorScope()
        if spectrum is None:
            self.DrawSpectrumGround(dc)
            return
        self.DrawSpectrumHTB(dc, spectrum)
        if hasattr(self.parent, 'VectorScope'):
            self.parent.VectorScope.SetSamples(vectorscope)

    def DrawSpectrumGround(self, dc):
        color = self.parent.st.SPECTRUM_BG_COLOR
        dc.DrawRectangleList(self.ground, pens=wx.Pen(color, 1),
                             brushes=wx.Brush(color))

    def DrawSpectrumHTB(self, dc, spectrum):
        # the ground and the bars as one picture
        w, h = self.GetSize()
        if w <= 0 or h <= 0:
            return
        scale = 0.4
        xs = numpy.array(self.GetBarSlots(w))
        levels = self.FitBarLevels(spectrum, len(xs))
        talls = (levels * h * scale).astype(int)
        # no bar under 2 px
        talls[talls < 2] = 0
        tops = ((h - levels * h * scale) * 0.5).astype(int)
        image = numpy.empty((h, w, 3), dtype=numpy.uint8)
        image[:] = wx.Colour(self.GetBackgroundColour()).Get()[:3]
        top = int(h / 2 - 1)
        for x in range(self.bar_width):
            image[top:top + 2, xs + x] = wx.Colour(self.parent.st.SPECTRUM_BG_COLOR).Get()[:3]
        rows = numpy.arange(h)[:, None]
        bars = (rows >= tops) & (rows < tops + talls)
        for x in range(self.bar_width):
            columns = image[:, xs + x]
            columns[bars] = wx.Colour(self.parent.st.SPECTRUM_FG_COLOR).Get()[:3]
            image[:, xs + x] = columns
        dc.DrawBitmap(wx.Bitmap.FromBuffer(w, h, image.tobytes()), 0, 0)

    def GetBarSlots(self, w):
        # a bar every bar_pitch pixels across the box
        count = max(2, int(w - 1) // self.bar_pitch + 1)
        offset = (int(w) - 1 - self.bar_pitch * (count - 1)) // 2
        return [offset + self.bar_pitch * i for i in range(count)]

    def FitBarLevels(self, levels, count):
        # more slots than bins: joined linearly between neighbours,
        # fewer: the largest of the bins falling into each slot
        levels = numpy.asarray(levels, dtype=float)
        length = len(levels)
        if length < 2:
            return numpy.resize(levels, count)
        if count >= length:
            return numpy.interp(numpy.linspace(0, length - 1, count),
                                numpy.arange(length), levels)
        edges = numpy.linspace(0, length, count + 1).astype(int)
        return numpy.maximum.reduceat(levels, edges[:-1])

    def OnSize(self, event=None):
        # in ANALYZER's BARS part (PlayBox.LayoutAnalyzerVisuals)
        self.parent.LayoutAnalyzerVisuals()

    def Place(self, rect):
        if rect is None:
            self.SetRect((0, 0, 0, 0))
            self.Hide()
            return
        width, height = rect.width, rect.height
        # the bins follow the width, the bars fitted to it (FitBarLevels)
        scale = int(round(width / 320.0))
        scale = 1 if scale < 1 else scale
        scale = self.max_scale if scale > self.max_scale else scale
        if self.scale != scale or self.width != width or self.height != height:
            self.scale = scale
            self.width = width
            self.height = height
            self.InitGround()
        self.SetRect(rect)
        self.Show()
        w, h = self.GetSize()
        self.ground = [wx.Rect(x, int(h / 2 - 1), self.bar_width, 2)
                       for x in self.GetBarSlots(w)]
        self.DirectDraw()


class PlayBoxVectorScope(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        fps = GetPreference('vectorscope_fps')
        if fps is None:
            fps = 60
        self.buffer.fps = fps
        # a square, the L and R axes as an X
        self.size = 56
        self.margin = 2
        self.vectorscope = None
        # earlier frames fade like a phosphor screen (rates at 30 fps);
        # the gain follows the track slowly to fill the scope
        self.persist = 0.55
        self.dot = 0.30
        self.gain = 1.0
        self.glow = None
        self.glow_lap = 0
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def GetVectorScope(self):
        if self.parent.IsVisualPlaying() is False:
            self.vectorscope = None
            return
        if self.parent.Spectrum.IsShown() is False:
            # the spectrum hidden: read its frame here for the samples
            _, samples = self.parent.Spectrum.GetSpectrumVectorScope()
            self.SetSamples(samples)
        return self.vectorscope

    def SetSamples(self, samples):
        if samples is None:
            self.glow = None
            self.vectorscope = None
            return
        w = h = self.size
        now = time.time()
        frames = 1.0
        if self.glow is None or self.glow.shape != (h, w):
            self.glow = numpy.zeros((h, w), dtype='float32')
        else:
            frames = min(6.0, max(0.0, now - self.glow_lap) * 30)
        self.glow_lap = now
        persist = self.persist ** frames
        self.glow *= persist
        left, right = samples
        energy = float(numpy.sqrt((left ** 2 + right ** 2).mean()))
        target = min(8.0, 0.35 / max(energy, 1e-4))
        self.gain += (target - self.gain) * (1 - 0.85 ** frames)
        if energy >= 1e-5:
            radius = (0.5 * w - 2) * self.gain
            side = (right - left) * 0.7071 * radius
            mid = (right + left) * 0.7071 * radius
            xs = numpy.clip(0.5 * w + side, 0, w - 1).astype(int)
            ys = numpy.clip(0.5 * h - mid, 0, h - 1).astype(int)
            hits = numpy.bincount(ys * w + xs, minlength=w * h).reshape(h, w)
            dot = self.dot * (1 - persist) / (1 - self.persist)
            self.glow += hits * dot
            numpy.minimum(self.glow, 1.0, out=self.glow)
        self.vectorscope = None if self.glow.max() < 0.02 else self.GetGlowBitmap()

    def GetGlowBitmap(self):
        # one bitmap of the brightness, not a point at a time
        h, w = self.glow.shape
        bgcolor = wx.Colour(self.parent.st.VECTORSCOPE_BG_COLOR).Get()[:3]
        fgcolor = wx.Colour(self.parent.st.VECTORSCOPE_FG_COLOR).Get()[:3]
        bgcolor = numpy.array(bgcolor, dtype='float32')
        fgcolor = numpy.array(fgcolor, dtype='float32')
        rgb = (bgcolor + (fgcolor - bgcolor) * self.glow[..., None]).astype('uint8')
        alpha = (numpy.minimum(1.0, self.glow * 4) * 255).astype('uint8')
        return wx.Bitmap.FromBufferRGBA(w, h, numpy.dstack([rgb, alpha[..., None]]).tobytes())

    def SetRectDraw(self, dc):
        if self.parent.IsVisualPlaying() is False:
            self.SetSamples(None)
            self.DrawVectorScope(dc, None)
            return
        self.DrawVectorScope(dc, self.GetVectorScope())

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.IsVisualPlaying() is False:
            self.DirectDraw()

    def DrawVectorScope(self, dc, vectorscope):
        bgcolor = self.parent.st.VECTORSCOPE_BG_COLOR
        pncolor = self.parent.st.VECTORSCOPE_PN_COLOR
        w, h = (self.size, self.size)
        dc.SetBrush(wx.Brush(bgcolor))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle(0, 0, w, h)
        dc.SetPen(wx.Pen(pncolor, 1))
        dc.DrawLine(0, 0, w, h)
        dc.DrawLine(w - 1, 0, -1, h)
        if vectorscope is None:
            return
        dc.DrawBitmap(vectorscope, 0, 0, True)

    def OnSize(self, event=None):
        # in ANALYZER's BARS part (PlayBox.LayoutAnalyzerVisuals)
        self.parent.LayoutAnalyzerVisuals()

    def Place(self, rect):
        if rect is None:
            self.SetRect((0, 0, 0, 0))
            self.Hide()
            return
        # as big as the part is tall (its picture's size: SetSamples)
        self.size = rect.width
        self.SetRect(rect)
        self.Show()
        self.DirectDraw()


class PlayBoxWave(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.position = 0.0
        self.height = 40
        self.margin = 5
        self.buffer.fps = 60
        self.cursor_width = 4
        self.highlight_dim = 0.45
        self.wave_rect = (0, 0, 0, 0)
        self.wave_bitmaps = None
        self.wave_exact = None
        self.wave_source = None
        self.wave_job = 0
        self.ahead = None
        self.resize_timer = None
        self.last_size = self.GetSize()
        self.rectHighlight = (0, 0, 0, 0)
        self.SetDropTarget(PlayBoxDnD(self.parent))
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.InitBuffer()

    def OnSize(self, event):
        if self.parent.parent.parent.IsPlayerSideShowOn():
            if self.parent.parent.parent.IsPlayerTopShowOn():
                # apic_pad = self.parent.Apic.GetSize().width+10
                apic_pad = 119 + 13
            else:
                apic_pad = 59 + 13
        else:
            apic_pad = 0
        apic_pad = 0
        _, cy, _, ch = self.parent.ControlButton.GetRect()
        w, h = self.parent.GetSize()
        # vol_align = 12
        isTopShowOn = self.parent.parent.parent.IsPlayerTopShowOn()
        isSideShowOn = self.parent.parent.parent.IsPlayerSideShowOn()
        # leftPad, rightPad = (13, 25 + 5)
        leftPad, rightPad = (13, 10)
        if isSideShowOn:
            leftPad = 8
        elif isSideShowOn and isTopShowOn:
            leftPad = 13

        # the frame 8 px from the window's edges or the tempo strip
        leftPad = 12
        self.height = self.parent.parent.parent.GetWaveformHeight()
        rightPad = self.parent.GetClientSize().width - self.parent.GetDeckRight() + 4

        # over the control row
        x, y = (leftPad, self.parent.GetControlTop() - self.parent.WAVE_BOTTOM_GAP - self.height)
        # x, y = (leftPad, cy-self.height-15)
        if self.parent.Apic.left:
            rect = (x + apic_pad, y, w - (leftPad + rightPad + apic_pad), self.height)
        else:
            rect = (x, y, w - (leftPad + rightPad + apic_pad), self.height)
        if rect == self.last_size:
            return
        same_width = len(self.last_size) == 4 and self.last_size[2] == rect[2]
        self.last_size = rect
        self.SetRect(rect)
        # while resizing the last waveform is stretched, painted after
        if self.wave_exact is None:
            self.parent.reInitWave = True
        elif same_width:
            # its height alone: painted now from the kept columns
            if self.resize_timer is not None:
                self.resize_timer.Stop()
            self.SetRectWave(now=True)
            self.SetRectHighlight()
            self.InitBuffer()
        else:
            self.StretchWave()
            if self.resize_timer is None:
                self.resize_timer = wx.CallLater(150, self.OnResized)
            else:
                self.resize_timer.Start(150)
        self.DirectDraw()

    def SettleNow(self):
        # a single step's new width: painted now, no stretch
        if self.resize_timer is not None:
            self.resize_timer.Stop()
        if self.wave_source is not None:
            self.SetRectWave(now=True)
            self.SetRectHighlight()
        self.InitBuffer()
        self.Refresh(False)
        self.parent.WaveDetail.InitBuffer()
        self.parent.WaveDetail.Refresh(False)

    def OnResized(self):
        # the window can be gone by then
        if not self:
            return
        self.parent.reInitWave = True
        self.InitBuffer()
        self.Refresh(False)
        self.parent.WaveDetail.InitBuffer()
        self.parent.WaveDetail.Refresh(False)

    def IsResizing(self):
        return self.resize_timer is not None and self.resize_timer.IsRunning()

    def GetWaveRect(self):
        # with the grid shown, a lane above and below for its ticks
        w, h = self.GetSize()
        x, y = (self.margin, 2)
        lane = PlayBoxWaveDetail.GRID_LANE if self.parent.IsGridShown() else 0
        return (x, y + lane, w - x * 2, h - y * 2 - 1 - lane * 2)

    def StretchWave(self):
        x, y, w, h = self.GetWaveRect()
        if w <= 0 or h <= 0:
            return
        self.wave_rect = (x, y, w, h)
        self.wave_bitmaps = [wx.Bitmap(bitmap.ConvertToImage().Scale(w, h, wx.IMAGE_QUALITY_NORMAL))
                             for bitmap in self.wave_exact]
        self.SetRectHighlight()

    def SetRectPre(self):
        if self.parent.reInitWave is True:
            self.parent.reInitWave = False
            self.SetRectWave()
            self.SetRectHighlight()

    def SetRectDraw(self, dc):
        # a station: the last half minute of what it plays
        if draw_live_trace(dc, self.parent, self.wave_rect, radio.TRACE_SECONDS):
            return
        draw_highlight = self.parent.IsHighlightKnown()\
            and self.parent.IsHighlightOn()\
            and self.parent.IsHighlightSkipOn() is False
        if draw_highlight:
            self.DrawHighlightWave(dc)
        elif self.parent.IsRadioEditActive() and self.wave_bitmaps is not None:
            self.DrawEditWave(dc)
        else:
            self.DrawNormalWave(dc)
        self.DrawPlayedLanes(dc)
        self.DrawGridLines(dc)
        self.DrawSnapFlash(dc)
        self.DrawCursor(dc)
        self.DrawPressMarker(dc)

    def DrawSnapFlash(self, dc):
        # the line a seek snapped to, lit till it fades
        flash = self.parent.GetSnapFlash()
        duration = self.parent.GetDurationTime()
        if flash is None or duration <= 0:
            return
        x, y, w, h = self.wave_rect
        draw_snap_flash(dc, int(math.ceil(x + flash[0] * w / duration)), 0,
                        self.GetSize().height, flash[1])
        self.redraw_next = True

    def DrawPlayedLanes(self, dc):
        # the grid's lanes over what plays, tinted (LANE_PLAYED)
        ranges = self.parent.GetPlayedRanges()
        duration = self.parent.GetDurationTime()
        if not ranges or duration <= 0 or self.parent.IsGridShown() is False:
            return
        x, y, w, h = self.wave_rect
        lane = PlayBoxWaveDetail.GRID_LANE
        colour = wx.Colour(*get_lane_played(self.parent.st))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(colour))
        for a, b in ranges:
            left = int(math.ceil(a * w / duration))
            right = min(int(math.ceil(b * w / duration)), w)
            if right <= left:
                continue
            dc.DrawRectangle(x + left, y - lane, right - left, lane)
            dc.DrawRectangle(x + left, y + h, right - left, lane)

    def DrawGridLines(self, dc):
        # every 16 bars across, brighter in the lanes; every 4 bars in the
        # lanes when 6 px apart; from the first phrase, else the downbeat
        grid = self.parent.GetGrid()
        duration = self.parent.GetDurationTime()
        if grid is None or duration <= 0 or self.wave_bitmaps is None\
                or self.parent.IsGridShown() is False:
            return
        known = self.parent.IsGridPhraseKnown()
        anchor = self.parent.GetGridPhraseStart() if known else self.parent.GetGridDownbeat()
        # lines cached per song, size and theme, drawn a list a pen
        key = (grid.bpm, anchor, known, duration, tuple(self.wave_rect),
               tuple(self.parent.st.PLAY_BG_COLOR))
        cache = getattr(self, 'grid_lines', None)
        if cache is None or cache[0] != key:
            cache = self.grid_lines = (key, self.MakeGridLines(grid, anchor, known, duration))
        for pen, lines in cache[1]:
            if lines:
                dc.DrawLineList(lines, pens=pen)

    def MakeGridLines(self, grid, anchor, known, duration):
        # [(pen, [(x1, y1, x2, y2), ...])]: across, in the lanes, 4 bars
        x, y, w, h = self.wave_rect
        span = 60.0 / grid.bpm * 64
        if span / duration * w < 6:
            return []
        bg = wx.Colour(self.parent.st.PLAY_BG_COLOR)

        def light(share):
            return wx.Pen(wx.Colour(*[int(v + (255 - v) * share)
                                      for v in (bg.Red(), bg.Green(), bg.Blue())]), 1)

        across, lanes, fours = [], [], []
        lane = PlayBoxWaveDetail.GRID_LANE
        bottom = y + h
        # 4 bars a step
        phrase = span / 4
        seconds = anchor % phrase
        index = -int(round((anchor - seconds) / phrase))
        # DrawLineList leaves out the last pixel too
        while seconds < duration:
            lx = int(x + seconds * w / duration)
            if index % 4 == 0:
                if known:
                    across.append((lx, y, lx, bottom))
                lanes.append((lx, y - lane, lx, y))
                lanes.append((lx, bottom, lx, bottom + lane))
            elif phrase / duration * w >= 6:
                fours.append((lx, y - lane, lx, y - lane // 2))
                fours.append((lx, bottom + lane // 2, lx, bottom + lane))
            seconds += phrase
            index += 1
        return [(light(0.35), across), (light(0.9), lanes), (light(0.5), fours)]

    def DrawNormalWave(self, dc):
        if self.wave_bitmaps is None:
            self.DrawFlatWave(dc, self.parent.st.WAVEFORM_FG_COLOR)
            return
        x, y, w, h = self.wave_rect
        dc.DrawBitmap(self.wave_bitmaps[0], x, y)

    def DrawFlatWave(self, dc, color):
        x, y, w, h = self.wave_rect
        cy = int(h * 0.5 + y)
        dc.SetPen(wx.Pen(color, 1))
        dc.DrawLine(x, cy, x + w, cy)

    def DrawClippedWave(self, dc, bitmap, start, end):
        x, y, w, h = self.wave_rect
        start, end = (max(int(start), 0), min(int(end), w))
        if end <= start:
            return
        dc.SetClippingRegion(x + start, y, end - start, h)
        dc.DrawBitmap(bitmap, x, y)
        dc.DestroyClippingRegion()

    def SetRectHighlight(self):
        # none left from the track before
        self.rectHighlight = (0, 0, 0, 0)
        if self.parent.IsHighlightKnown() is False:
            return
        duration = self.parent.GetDurationTime()
        if duration <= 0.0:
            return
        offset, period = self.parent.GetHighlightTime()
        if offset is None or period is None:
            return
        _, _, width, _ = self.wave_rect
        # rounded as DrawCursor (ceil)
        x = int(math.ceil(offset * width / duration))
        if period == 0:
            xw = width
        else:
            xw = min(int(math.ceil((offset + period) * width / duration)), width)
        # if x == 0:
        #     x = 1
        _, height = self.GetSize()
        self.rectHighlight = (x + self.margin, 0, xw - x, height)

    def DrawEditWave(self, dc):
        # SHORT: what it skips dimmed, what it plays in full
        x, y, w, h = self.wave_rect
        duration = self.parent.GetDurationTime()
        dc.DrawBitmap(self.wave_bitmaps[1], x, y)
        if duration <= 0:
            return
        start, end, cuts = self.parent.GetRadioEdit()
        bounds = [start] + [v for cut in cuts for v in cut] + [end]
        # what it plays on the highlight's ground
        color = self.parent.st.HIGHLIGHT_BG_COLOR
        dc.SetPen(wx.Pen(color, 1))
        dc.SetBrush(wx.Brush(color))
        for a, b in zip(bounds[0::2], bounds[1::2]):
            left, right = math.ceil(a * w / duration), math.ceil(b * w / duration)
            if right > left:
                dc.DrawRectangle(int(x + left), 0, int(right - left), self.GetSize().height)
            self.DrawClippedWave(dc, self.wave_bitmaps[2], left, right)

    def DrawHighlightWave(self, dc):
        if self.wave_bitmaps is None:
            self.DrawFlatWave(dc, self.parent.st.HIGHLIGHT_PN_COLOR)
            return
        # outside dimmed, inside in full on the highlight ground
        x, y, w, h = self.wave_rect
        dc.DrawBitmap(self.wave_bitmaps[1], x, y)
        start = max(self.rectHighlight[0] - self.margin, 0)
        end = min(start + self.rectHighlight[2], w)
        if end <= start:
            return
        color = self.parent.st.HIGHLIGHT_BG_COLOR
        dc.SetPen(wx.Pen(color, 1))
        dc.SetBrush(wx.Brush(color))
        dc.DrawRectangle(int(x + start), 0, int(end - start), self.GetSize().height)
        self.DrawClippedWave(dc, self.wave_bitmaps[2], start, end)

    def DrawCursor(self, dc):
        w, h = self.GetSize()
        slidable = w - self.margin * 2
        position = self.parent.GetPositionTime()
        duration = self.parent.GetDurationTime()
        if duration == 0:
            x_ratio = 0.0
        else:
            x_ratio = 1.0 * position / duration

        bgcolor = self.parent.st.PLAYCURSOR_BG_COLOR
        fgcolor = self.parent.st.PLAYCURSOR_FG_COLOR
        stroke = self.parent.st.PLAYCURSOR_STROKE
        dc.SetBrush(wx.Brush(bgcolor))
        dc.SetPen(wx.Pen(fgcolor, stroke))
        x = math.ceil(self.margin + slidable * x_ratio)
        dc.DrawRectangle(int(x - self.cursor_width * 0.5), 0, int(self.cursor_width), int(h))

    def SetRectWave(self, now=False):
        # now: painted on this thread at once, not stretched first
        x, y, w, h = self.GetWaveRect()
        self.wave_rect = (x, y, w, h)
        waveform = self.parent.GetWaveform()
        self.wave_job += 1
        if audio.is_waveform_3band(waveform) is False or w <= 0 or h <= 0:
            self.wave_bitmaps = None
            self.wave_exact = None
            self.wave_source = None
            return
        # painted on a thread: a long mix blocked the window; till then the
        # same song's last waveform is stretched, a new song's is flat
        if self.wave_source is waveform and self.wave_exact is not None:
            self.StretchWave()
        else:
            self.wave_bitmaps = None
            self.wave_exact = None
        self.wave_source = waveform
        grounds = self.GetWaveGrounds()
        job = self.wave_job
        ahead = self.ahead
        if ahead is not None and ahead[0] is waveform and ahead[1] == (w, h, grounds):
            # painted while the stream opened (PaintAhead)
            self.ahead = None
            self.SetWaveImages(job, (x, y, w, h), ahead[2])
            return

        def paint():
            images = [audio.paint_waveform_3band(waveform, w, h, ground=ground, dim=dim).tobytes()
                      for ground, dim in grounds]
            if now:
                self.SetWaveImages(job, (x, y, w, h), images)
            else:
                wx.CallAfter(self.SetWaveImages, job, (x, y, w, h), images)

        if now:
            paint()
            return
        threading.Thread(target=paint, daemon=True).start()

    def GetWaveGrounds(self):
        # normal, dimmed outside the highlight, on the highlight ground
        bgcolor = self.parent.st.PLAY_BG_COLOR
        hlcolor = self.parent.st.HIGHLIGHT_BG_COLOR
        return ((bgcolor, 1.0), (bgcolor, self.highlight_dim), (hlcolor, 1.0))

    def PaintAhead(self, waveform):
        # on the prefetch thread: painted at the last size for SetRectWave
        if audio.is_waveform_3band(waveform) is False:
            return
        _, _, w, h = self.wave_rect
        if w <= 0 or h <= 0:
            return
        grounds = self.GetWaveGrounds()
        images = [audio.paint_waveform_3band(waveform, w, h, ground=ground, dim=dim).tobytes()
                  for ground, dim in grounds]
        self.ahead = (waveform, (w, h, grounds), images)

    def SetWaveImages(self, job, rect, images):
        # a song or a size since: painted again for that one already
        if not self or job != self.wave_job:
            return
        x, y, w, h = rect
        self.wave_bitmaps = [wx.Bitmap.FromBuffer(w, h, image) for image in images]
        self.wave_exact = self.wave_bitmaps
        if self.GetWaveRect() != rect:
            self.StretchWave()
        self.InitBuffer()
        self.Refresh(False)

    def CATCH_EVT_GLOBAL(self, event):
        if self.parent.parent.HasToSkipEvent() is False:
            self.HandleEventLeftIsDown(event)
            self.HandleEventHighlight(event)
            self.HandleEventGridMenu(event)
        if self.parent.IsPlaying() is False:
            self.DirectDraw()

    def HandleEventGridMenu(self, event):
        # the grid's menu, at the time clicked on the whole song
        if event.RightUp is False or event.rectIdx is None or self.parent.IsGridShown() is False:
            return
        width = max(self.GetSize().width - self.margin * 2, 1)
        share = min(max(1.0 * (event.X - self.margin) / width, 0.0), 1.0)
        seconds = share * self.parent.GetDurationTime()
        self.parent.parent.SetPopupMenu(PlayBoxPopupGrid(self.parent, seconds), (event.x, event.y))

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        if event.WheelRotation > 0:
            self.parent.OnFastRewind()
        else:
            self.parent.OnFastForward()

    def HandleEventHighlight(self, event):
        if event.rectIdx is None:
            return
        if event.LeftDown is False:
            return
        if self.parent.IsHighlightKnown() is False:
            return
        if self.parent.IsHighlightOn() is False:
            return
        if self.IsInRect(self.rectHighlight, (event.X, event.Y)):
            return
        self.parent.SetHighlightSkipOn()

    def HandleEventLeftIsDown(self, event):
        # pressed: a marker follows the drag; let go: plays from the snapped point
        if event.LeftDown and event.rectIdx is not None:
            self.press_x = event.X
            self.reInitBuffer = True
            return
        if getattr(self, 'press_x', None) is None:
            return
        if event.LeftIsDown:
            if event.X != self.press_x:
                self.press_x = event.X
                self.reInitBuffer = True
            return
        x, self.press_x = self.press_x, None
        self.OnClickWave(Struct(X=x))
        self.reInitBuffer = True

    def GetPressTime(self):
        # where the press or the drag is now, unsnapped, or None
        x = getattr(self, 'press_x', None)
        duration = self.parent.GetDurationTime()
        if x is None or duration <= 0:
            return None
        width, _ = self.GetSize()
        ratio = min(max(1.0 * (x - 5) / max(width - 5 * 2, 1), 0.0), 0.999999)
        return duration * ratio

    def DrawPressMarker(self, dc):
        seconds = self.GetPressTime()
        if seconds is None:
            return
        w, h = self.GetSize()
        x = int(math.ceil(self.margin + (w - self.margin * 2) * seconds /
                          self.parent.GetDurationTime()))
        accent = uikit.ui().ACCENT
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(accent))
        dc.DrawRectangle(x - 1, 0, 2, h)

    def OnClickWave(self, event):
        width, height = self.GetSize()
        x = event.X - 5
        slidable = width - 5 * 2
        posRatio = 1.0 * x / slidable
        if posRatio <= 0.0:
            posRatio = 0.0
        elif posRatio >= 1.0:
            posRatio = 0.999999
        duration = self.parent.GetDurationTime()
        # on the grid as SNAP says
        new_position = self.parent.GetSnappedTime(duration * posRatio)
        # into the edit's intro or outro: the whole song for this play
        self.parent.LeaveRadioEdit(new_position)
        if self.parent.IsPlaying():
            self.parent.SetPositionTime(new_position)
        else:
            self.parent.SetResumeTime(new_position)
            self.reInitBuffer = True


class PlayBoxWaveDetail(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.height = 40
        self.gap = 6
        self.margin = 5
        self.buffer.fps = 60
        # seconds across at first: fine enough to scratch
        # self.span = 12.0
        self.span = 5.0
        self.span_least = 1.5
        self.span_most = 3 * 60 * 60
        self.span_step = 1.25
        self.drag_least = 4
        self.highlight_dim = 0.45
        self.drag = None
        # the strip is the record: playing, a press stops it and a drag
        # scratches; paused, a drag seeks. a click alone does not seek
        self.scratching = None
        self.last_key = None
        self.last_step = 0
        self.last_bitmap = None
        # the zoom chip's left, the bar numbers kept off it
        self.chips_left = None
        self.SetDropTarget(PlayBoxDnD(self.parent))
        color = self.parent.st.PLAY_BG_COLOR
        self.SetBackgroundColour(color)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnScratchDown)
        self.Bind(wx.EVT_MOTION, self.OnScratchMotion)
        self.Bind(wx.EVT_LEFT_UP, self.OnScratchUp)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnScratchCaptureLost)
        self.InitBuffer()

    def IsScratchable(self):
        return self.parent.IsWaveformScratchOn() and self.parent.IsPlaying()\
            and self.parent.AudioControl.IsScratchable()

    def OnScratchDown(self, event):
        if self.IsScratchable() is False:
            event.Skip()
            return
        self.CaptureMouse()
        self.drag = None
        self.scratching = Struct(x=event.GetX(), time=time.time(), moved=False,
                                 start=self.parent.GetPositionTime(), path=self.parent.cue.path)
        # the hand is read off the cursor (ScratchPress), at the view's scale
        # but no coarser than the scale heard clean
        width = max(self.GetSize().width - self.margin * 2, 1)
        seconds_per_pixel = min(1.0 * self.GetSpan() / width, 1.0 / SCRATCH_PIXELS_PER_SECOND)
        self.parent.AudioControl.ScratchEventAt(self.ClientToScreen(event.GetPosition()).x)
        self.parent.AudioControl.ScratchPress(seconds_per_pixel)

    def OnScratchMotion(self, event):
        if self.scratching is None:
            event.Skip()
            return
        if abs(event.GetX() - self.scratching.x) >= self.drag_least:
            self.scratching.moved = True
        self.parent.AudioControl.ScratchEventAt(self.ClientToScreen(event.GetPosition()).x)

    def OnScratchUp(self, event):
        if self.scratching is None:
            event.Skip()
            return
        scratching = self.scratching
        self.scratching = None
        if self.HasCapture():
            self.ReleaseMouse()
        self.parent.AudioControl.ScratchRelease()
        # if scratching.moved or time.time() - scratching.time > self.click_seconds:
        #     return
        # if scratching.path != self.parent.cue.path:
        #     return
        # width = max(self.GetSize().width - self.margin * 2, 1)
        # self.SeekTo(scratching.start + (1.0 * (scratching.x - self.margin) / width - 0.5) * self.GetSpan())

    def OnScratchCaptureLost(self, event):
        self.scratching = None
        self.parent.AudioControl.ScratchRelease()

    def OnSize(self, event=None):
        # hidden when off or while a message takes the waveforms' place
        if self.parent.parent.parent.IsWaveformDetailShowOn() is False\
                or getattr(self.parent, 'live_message', None) is not None:
            self.drag = None
            self.Hide()
            return
        self.Show()
        self.height = self.parent.parent.parent.GetWaveformHeight('detail')
        x, y, w, h = self.parent.Wave.GetRect()
        self.SetRect((x, y - self.height - self.gap, w, self.height))
        # not painted here: a new width is a new key (DrawDetailWave)
        self.DirectDraw()

    def GetSpan(self):
        duration = self.parent.GetDurationTime()
        if duration <= 0:
            return self.span
        return min(self.span, duration)

    def GetCentre(self):
        # a drag belongs to the track it began on
        if self.drag is not None and self.drag.path != self.parent.cue.path:
            self.drag = None
        if self.drag is not None and self.drag.moved:
            return self.drag.time
        return self.parent.GetPositionTime()

    def IsHighlightDrawn(self):
        return self.parent.IsHighlightKnown()\
            and self.parent.IsHighlightOn()\
            and self.parent.IsHighlightSkipOn() is False

    def GetHighlightPeriod(self):
        if self.IsHighlightDrawn() is False:
            return None
        offset, period = self.parent.GetHighlightTime()
        if offset is None or period is None:
            return None
        if period == 0:
            return (offset, self.parent.GetDurationTime())
        return (offset, offset + period)

    # the zoom chip: bars across when the grid is known, else seconds
    CHIP_TOP = 3
    CHIP_HEIGHT = 17

    # least pixels between numbered bars
    NUMBER_SPACING = 64

    def SetRectDraw(self, dc):
        self.DrawStrip(dc)
        self.DrawChips(dc)
        self.DrawBarNumbers(dc)

    def DrawBarNumbers(self, dc):
        # bar numbers by their lines: every bar, 4 or 16 by the zoom
        grid = self.parent.GetGrid()
        duration = self.parent.GetDurationTime()
        if grid is None or duration <= 0 or self.parent.IsGridShown() is False\
                or self.parent.IsStreamTrack() or self.parent.GetLiveMessage() is not None:
            return
        w, h = self.GetSize()
        w -= self.margin * 2
        if w <= 0:
            return
        span = self.GetSpan()
        pixel = span / w
        start = round((self.GetCentre() - span * 0.5) / pixel) * pixel
        period = 60.0 / grid.bpm
        bar = period * 4
        downbeat = self.parent.GetGridDownbeat()
        every = 1
        if bar / pixel < self.NUMBER_SPACING:
            every = 4 if bar * 4 / pixel >= self.NUMBER_SPACING else 16
        # from the phrase's first bar when it is known, else from bar 1
        anchor = self.parent.GetGridPhraseBars() if self.parent.IsGridPhraseKnown() else 0
        first = int(math.floor((start - downbeat) / bar))
        last = int(math.ceil((start + span - downbeat) / bar))
        st = self.parent.st
        # small and dimmed
        dc.SetFont(wx.Font(wx.Size(0, 9), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                           wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO))
        for index in range(max(first, 0), last + 1):
            if every > 1 and (index - anchor) % every:
                continue
            x = int(self.margin + (downbeat + index * bar - start) / pixel)
            if x < self.margin or x > self.margin + w - 8:
                continue
            text = f'{index + 1}'
            tw, th = dc.GetTextExtent(text)
            if self.chips_left is not None and x + tw + 6 >= self.chips_left\
                    and 2 + th >= self.CHIP_TOP:
                continue
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(st.PLAY_BG_COLOR))
            dc.DrawRectangle(x + 2, 1, tw + 4, th + 1)
            dc.SetTextForeground(st.TITLE_DIM_COLOR)
            dc.DrawText(text, x + 4, 1)

    def GetZoomText(self):
        span = self.GetSpan()
        if self.parent.IsStreamTrack():
            return get_span_text(min(self.span, radio.TRACE_SECONDS))
        grid = self.parent.GetGrid()
        if grid is None or not grid.bpm:
            return get_span_text(span)
        bars = span * grid.bpm / 240.0
        value = f'{round(bars)}' if bars >= 10 else (f'{bars:.1f}').rstrip('0').rstrip('.')
        return f'{value} BAR{"" if value == "1" else "S"}'

    def DrawChips(self, dc):
        self.chips_left = None
        w, h = self.GetSize()
        if w < 200 or h < 20:
            return
        st = self.parent.st
        y, ch = self.CHIP_TOP, self.CHIP_HEIGHT
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        # a readout on the waveform, its ground a little see-through
        text = self.GetZoomText()
        font = wx.Font(wx.Size(0, 11), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL, faceName=FONT_PLAYINFO)
        uikit.set_font(gc, font, wx.Colour(st.CHIP_FG_COLOR))
        tw, th = gc.GetTextExtent(text)[:2]
        cw = int(tw) + 14
        x = w - self.margin - 4 - cw
        face = wx.Colour(st.CHIP_BG_COLOR)
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(face.Red(), face.Green(), face.Blue(), 225))))
        gc.DrawRoundedRectangle(x, y, cw, ch, uikit.RADIUS)
        gc.DrawText(text, x + 7, y + (ch - th) / 2.0)
        self.chips_left = x

    def DrawStrip(self, dc):
        w, h = self.GetSize()
        w -= self.margin * 2
        if w <= 0 or h <= 0:
            return
        # a station: its last seconds at the strip's zoom
        if draw_live_trace(dc, self.parent, (self.margin, 0, w, h),
                           min(self.span, radio.TRACE_SECONDS), spread=0):
            return
        waveform = self.parent.GetWaveform()
        duration = self.parent.GetDurationTime()
        if audio.is_waveform_3band(waveform) and duration > 0:
            self.DrawDetailWave(dc, waveform, duration, w, h)
        else:
            # the waveform bar's flat line colour
            if self.IsHighlightDrawn():
                color = self.parent.st.HIGHLIGHT_PN_COLOR
            else:
                color = self.parent.st.WAVEFORM_FG_COLOR
            dc.SetPen(wx.Pen(color, 1))
            dc.DrawLine(self.margin, int(h * 0.5), self.margin + w, int(h * 0.5))
        # the line a seek snapped to, lit till it fades
        flash = self.parent.GetSnapFlash()
        if flash is not None:
            fx = self.margin + w * (0.5 + (flash[0] - self.GetCentre()) / self.GetSpan())
            if self.margin <= fx <= self.margin + w:
                draw_snap_flash(dc, int(math.ceil(fx)), 0, h, flash[1])
            self.redraw_next = True
        # the same cursor as the waveform bar's
        cursor_width = self.parent.Wave.cursor_width
        dc.SetBrush(wx.Brush(self.parent.st.PLAYCURSOR_BG_COLOR))
        dc.SetPen(wx.Pen(self.parent.st.PLAYCURSOR_FG_COLOR, self.parent.st.PLAYCURSOR_STROKE))
        x = math.ceil(self.margin + w * 0.5)
        dc.DrawRectangle(int(x - cursor_width * 0.5), 0, int(cursor_width), int(h))

    def DrawDetailWave(self, dc, waveform, duration, w, h):
        span = self.GetSpan()
        centre = self.GetCentre()
        period = self.GetHighlightPeriod()
        # on whole pixels, or the picture shimmers as it scrolls; while
        # resizing the strip keeps its scale, painted after
        if self.last_key is not None and self.parent.Wave.IsResizing()\
                and self.last_key[:4] == (id(waveform), duration, span, period):
            kept = self.last_key[4]
            step = round((centre - span * 0.5) / (span / kept))
            if kept // 4 <= step - self.last_step <= kept * 2 - kept // 4:
                dc.SetClippingRegion(self.margin, 0, w, h)
                dc.DrawBitmap(self.last_bitmap,
                              self.margin + (w - kept) // 2 - (step - self.last_step), 0)
                dc.DestroyClippingRegion()
                return
        pixel = span / w
        step = round((centre - span * 0.5) / pixel)
        # a strip three windows wide, painted again only near its ends
        grid = self.parent.GetGrid()
        gridkey = None if grid is None or self.parent.IsGridShown() is False\
            else (grid.bpm, grid.downbeat, grid.shift, grid.phrase, grid.phrase_shift,
                  grid.phrase_set)
        played = tuple(self.parent.GetPlayedRanges())
        key = (id(waveform), duration, span, period, w, h, gridkey, played)
        if key != self.last_key or not w // 4 <= step - self.last_step <= w * 2 - w // 4:
            self.last_step = step - w
            start = self.last_step * pixel
            times = start + (numpy.arange(w * 3) + 0.5) * span / w
            bgcolor = numpy.array(self.parent.st.PLAY_BG_COLOR, dtype=float)
            ground, dim = (bgcolor, 1.0)
            # what plays on the highlight's ground, the rest dimmed
            if played:
                inside = numpy.zeros(len(times), dtype=bool)
                for a, b in played:
                    inside |= (times >= a) & (times < b)
                hlcolor = numpy.array(self.parent.st.HIGHLIGHT_BG_COLOR, dtype=float)
                ground = numpy.where(inside[:, None], hlcolor, bgcolor)
                dim = numpy.where(inside, 1.0, self.highlight_dim)
            columns = len(waveform) / duration
            # with the grid shown, a lane above and below for its ticks
            lane = self.GRID_LANE if gridkey is not None and h > self.GRID_LANE * 4 else 0
            image = audio.paint_waveform_3band(
                waveform, w * 3, h - lane * 2, ground=ground, dim=dim,
                start=start * columns, end=(start + span * 3) * columns, spread=0)
            if lane:
                band = numpy.broadcast_to(numpy.array(ground, dtype=float), (w * 3, 3))
                if played:
                    # over what plays, tinted (LANE_PLAYED)
                    inside = numpy.zeros(w * 3, dtype=bool)
                    for a, b in played:
                        inside |= (times >= a) & (times < b)
                    tint = numpy.array(get_lane_played(self.parent.st), dtype=float)
                    band = numpy.where(inside[:, None], tint, band)
                band = numpy.repeat(band[None, :, :].astype(numpy.uint8), lane, axis=0)
                image = numpy.concatenate((band, image, band), axis=0)
            self.PaintGridLines(image, start, pixel, lane)
            self.last_bitmap = wx.Bitmap.FromBuffer(w * 3, h, image.tobytes())
            self.last_key = key
        dc.SetClippingRegion(self.margin, 0, w, h)
        dc.DrawBitmap(self.last_bitmap, self.margin - (step - self.last_step), 0)
        dc.DestroyClippingRegion()

    # the grid's tick lanes above and below the waveform (px)
    GRID_LANE = 4

    def PaintGridLines(self, image, start, pixel, lane=0):
        # the beat grid lightened in: beats left out under 4 px apart;
        # ticks in the lanes: a beat's half the lane, a bar's all of it
        height, width, _ = image.shape
        lines = self.parent.GetGridLines(start, start + width * pixel)
        if lines == []:
            return
        beat_pixels = 60.0 / self.parent.GetGrid().bpm / pixel
        for seconds, level in lines:
            if level == 0 and beat_pixels < 4:
                continue
            x = int((seconds - start) / pixel)
            strength, thick = ((0.22, 1), (0.5, 1), (0.75, 2))[level]
            left, right = max(x, 0), min(x + thick, width)
            if right <= left:
                continue
            part = image[:, left:right].astype(numpy.float32)
            image[:, left:right] = (part + (255 - part) * strength).astype(numpy.uint8)
            if lane:
                tick = lane // 2 if level == 0 else lane
                bright = (0.5, 0.8, 0.95)[level]
                for rows in (slice(0, tick), slice(height - tick, height)):
                    part = image[rows, left:right].astype(numpy.float32)
                    image[rows, left:right] = (part + (255 - part) * bright).astype(numpy.uint8)

    def CATCH_EVT_GLOBAL(self, event):
        if self.IsShown() is False:
            return
        if self.parent.parent.HasToSkipEvent() is False:
            self.HandleEventDrag(event)
            self.HandleEventGridMenu(event)
        if self.parent.IsPlaying() is False:
            self.DirectDraw()

    def CATCH_EVT_MOUSEWHEEL(self, event):
        if self.onClient is False:
            return
        # up narrows, down widens; kept as chosen (GetSpan fits it)
        duration = self.parent.GetDurationTime()
        if duration <= 0:
            return
        if event.WheelRotation > 0:
            span = min(self.span, duration) / self.span_step
        else:
            span = min(self.span * self.span_step, max(duration, self.span))
        # most = max(self.parent.GetDurationTime(), self.span_least)
        # self.span = min(max(span, self.span_least), most)
        self.span = min(max(span, self.span_least), self.span_most)
        self.reInitBuffer = True

    def HandleEventDrag(self, event):
        # a drag seeks, let go where it should play; a scratch has the press
        if self.scratching is not None:
            return
        if event.LeftDown and event.rectIdx is not None:
            if self.IsScratchable():
                return
            centre = self.parent.GetPositionTime()
            self.drag = Struct(x=event.X, start=centre, time=centre, moved=False,
                               path=self.parent.cue.path)
            return
        if self.drag is not None and self.drag.path != self.parent.cue.path:
            self.drag = None
        if self.drag is None:
            return
        width = max(self.GetSize().width - self.margin * 2, 1)
        if event.LeftIsDown:
            dx = event.X - self.drag.x
            if abs(dx) >= self.drag_least:
                self.drag.moved = True
            if self.drag.moved:
                # free while it moves; snapped when let go (SeekTo)
                self.drag.time = self.drag.start - 1.0 * dx / width * self.GetSpan()
            return
        drag = self.drag
        self.drag = None
        if drag.moved:
            position = drag.time
        elif self.parent.GetWaveformMode() == 'seek':
            # seek mode: a click plays from where it is
            position = drag.start + (1.0 * (drag.x - self.margin) / width - 0.5) * self.GetSpan()
        else:
            return
        self.SeekTo(position)

    def HandleEventGridMenu(self, event):
        if event.RightUp is False or event.rectIdx is None or self.parent.IsGridShown() is False:
            return
        width = max(self.GetSize().width - self.margin * 2, 1)
        seconds = self.GetCentre() + (1.0 * (event.X - self.margin) / width - 0.5) * self.GetSpan()
        self.parent.parent.SetPopupMenu(PlayBoxPopupGrid(self.parent, seconds), (event.x, event.y))

    def SeekTo(self, position):
        duration = self.parent.GetDurationTime()
        # on the grid as SNAP says
        position = self.parent.GetSnappedTime(position)
        position = min(max(position, 0.0), duration * 0.999999)
        period = self.GetHighlightPeriod()
        if period is not None and (position < period[0] or position >= period[1]):
            self.parent.SetHighlightSkipOn()
        self.parent.LeaveRadioEdit(position)
        if self.parent.IsPlaying():
            self.parent.SetPositionTime(position)
        else:
            self.parent.SetResumeTime(position)
            self.parent.Wave.reInitBuffer = True
        self.reInitBuffer = True


class PlayBoxPopupGrid(wx.Menu):

    def __init__(self, parent, seconds):
        # parent: the PlayBox; seconds: where the strip was clicked
        wx.Menu.__init__(self)
        self.parent = parent
        self.seconds = seconds
        grid = self.parent.GetGrid()
        if grid is None:
            item = self.Append(wx.ID_ANY, 'No beat grid yet')
            item.Enable(False)
            return
        # the time clicked, shown in the labels
        at = f'{int(seconds // 60)}:{seconds % 60:04.1f}'
        labels = (f'Bar starts on this beat ({at})', 'Bar starts at the play position',
                  'Bar one beat earlier', 'Bar one beat later', 'Bar as analyzed')
        for label, handler in zip(labels, (self.OnHere, self.OnHerePlaying, self.OnEarlier,
                                           self.OnLater, self.OnAnalyzed)):
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        labels = (f'Phrase starts on this bar ({at})', 'Phrase starts at the play position',
                  'Phrase as analyzed')
        for label, handler in zip(labels, (self.OnPhraseHere, self.OnPhraseHerePlaying,
                                           self.OnPhraseAnalyzed)):
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        source = 'Beat This!' if grid.source.startswith('beatthis') else 'the beats alone'
        if grid.source.endswith('+changes'):
            source += ', moved by the song\'s changes'
        item = self.Append(wx.ID_ANY, f'{grid.bpm:.3f} BPM, bar from {source}')
        item.Enable(False)
        self.AppendSeparator()
        scale = grid.bpm_scale or 1.0
        labels = [(f'Tempo x2 ({grid.bpm * 2:.2f} BPM)', self.OnTempoDouble),
                  (f'Tempo /2 ({grid.bpm / 2:.2f} BPM)', self.OnTempoHalf)]
        if scale != 1.0:
            labels.append((f'Tempo as analyzed ({grid.bpm / scale:.2f} BPM)',
                           self.OnTempoAnalyzed))
        for label, handler in labels:
            self.Bind(wx.EVT_MENU, handler, self.Append(wx.ID_ANY, label))
        self.AppendSeparator()
        if grid.phrase_set:
            phrase = 'Phrase set by you'
        elif self.parent.IsGridPhraseKnown():
            phrase = 'Phrase from the song\'s changes'
        else:
            phrase = 'Phrase unsure, not drawn: set it on a bar above'
        item = self.Append(wx.ID_ANY, phrase)
        item.Enable(False)

    def OnHere(self, event):
        self.parent.SetGridBarAt(self.seconds)

    def OnHerePlaying(self, event):
        self.parent.SetGridBarAt(self.parent.GetPositionTime())

    def OnPhraseHerePlaying(self, event):
        self.parent.SetGridPhraseAt(self.parent.GetPositionTime())

    def OnEarlier(self, event):
        self.parent.SetGridShift((self.parent.GetGrid().shift or 0) - 1)

    def OnLater(self, event):
        self.parent.SetGridShift((self.parent.GetGrid().shift or 0) + 1)

    def OnAnalyzed(self, event):
        self.parent.SetGridShift(0)

    def OnPhraseHere(self, event):
        self.parent.SetGridPhraseAt(self.seconds)

    def OnTempoDouble(self, event):
        self.parent.SetGridScale(2.0)

    def OnTempoHalf(self, event):
        self.parent.SetGridScale(0.5)

    def OnTempoAnalyzed(self, event):
        self.parent.SetGridScale(None)

    def OnPhraseAnalyzed(self, event):
        self.parent.SetGridPhraseShift(0, set_by_user=False)
