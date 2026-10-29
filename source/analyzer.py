# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import ctypes
import math
import numpy
import pybass
import time

from collections import deque


# ANALYZER's readings (analyzerbox draws them), PyWinAudio's analyzer's measures read from
# the playing stream as it is heard (after MASTER, before the volume): the levels (peak, RMS,
# their hold), the loudness (BS.1770: momentary, short-term, integrated over the song), the
# stereo (correlation, balance, the goniometer's dots), the spectrum and the spectrogram.
# read once a frame from the stream's buffer (BASS_ChannelGetData: what is about to be
# heard, not taken from it)
FFT_SIZE = 8192
FLOOR = -60.0
PEAK_FALL = 24.0
HOLD_TIME = 1.5
HOLD_FALL = 30.0
RMS_TIME = 0.3
STEREO_TIME = 0.3
CLIP_LEVEL = 0.999

# ITU-R BS.1770 K-weighting (its 48 kHz filters, read at the true frequencies), its blocks
K_STAGES = (
    ((1.53512485958697, -2.69169618940638, 1.19839281085285),
     (1.0, -1.69065929318241, 0.73248077421585)),
    ((1.0, -2.0, 1.0), (1.0, -1.99004745483398, 0.99007225036621)),
)
LOUDNESS_FLOOR = -70.0
MOMENTARY = 0.4
SHORT = 3.0
GATE_EVERY = 0.1
ABSOLUTE_GATE = -70.0
RELATIVE_GATE = -10.0

# the spectrum: bands of a sixteenth of an octave from 20 Hz to 20 kHz (a curve's points),
# tilted +3 dB an octave around 1 kHz so music reads flat; falling at SPECTRUM_FALL, its
# peak line held a while
SPECTRUM_LOW = 20.0
SPECTRUM_HIGH = 20000.0
SPECTRUM_BANDS = 160
SPECTRUM_FLOOR = -90.0
SPECTRUM_TILT = 3.0
SPECTRUM_FALL = 40.0
# a band's level the mean of its bins' power, followed this share a frame (PyWinAudio's: the
# bins' peak followed at once, before, drew the curve 20 dB higher than it)
SPECTRUM_SMOOTH = 0.35
PEAK_LINE_HOLD = 1.0
PEAK_LINE_FALL = 12.0

# the spectrogram: a column a frame, rows on the same log scale, kept this many columns
GRAM_ROWS = 96
GRAM_COLUMNS = 2560
GRAM_LOW = -84.0
GRAM_HIGH = -12.0
# inferno: brightness only rises, so red-green colour blindness still reads it
GRAM_STOPS = ((0.0, '#111215'), (0.125, '#1f0c48'), (0.25, '#57106e'), (0.375, '#8a226a'),
              (0.5, '#bc3754'), (0.625, '#e45a31'), (0.75, '#f98e09'), (0.875, '#f6d746'),
              (1.0, '#fcffa4'))

# the goniometer: its picture's side, what is kept of it a frame, the samples a frame
SCOPE_SIDE = 96
SCOPE_PERSIST = 0.55
SCOPE_SAMPLES = 2048


# the spectrum's bars, PyWinAudio's (meterview: a bar a semitone, its FFT 0.1 s long at
# 10 Hz a bin, read from the last 75 ms; an autogain following the sound above 5 kHz)
BAR_LOW_PAD = (2, 3, 4, 5, 6, 7)
BAR_NOTES = [8.0, 8.41536811017449] + [8.91577193817796 * 2 ** (step / 12)
                                       for step in range(127)]
BAR_REACH = 3
BAR_SET = 103
BAR_PITCH = 3
AUTOGAIN_DEFAULT = 0.4
AUTOGAIN_RANGE = (0.05, 4.0)
AUTOGAIN_FOLLOW = 2.0
# the oscilloscope's columns kept (a frame each: its highest, lowest and RMS)
WAVE_COLUMNS = 2560


def get_bar_points(rate):
    # (the frame read, the FFT's length) at this rate
    return int(rate * 0.075 / 4), int(rate * 0.1)


def get_firwin(taps, cutoff, highpass):
    # scipy.signal.firwin (Hamming) without scipy
    middle = numpy.arange(taps) - (taps - 1) / 2
    if highpass:
        response = numpy.sinc(middle) - cutoff * numpy.sinc(cutoff * middle)
    else:
        response = cutoff * numpy.sinc(cutoff * middle)
    response *= numpy.hamming(taps)
    return response / (response * numpy.cos(numpy.pi * middle * (1.0 if highpass else 0.0))).sum()


def get_autogain_weights(rate):
    _, points = get_bar_points(rate)
    nyquist = rate / 2
    freqs = numpy.arange(1, points // 2) * (rate / points)

    def respond(taps, cutoff, highpass):
        coefficients = get_firwin(taps, cutoff / nyquist, highpass)
        phase = numpy.exp(-2j * numpy.pi * numpy.outer(freqs / rate, numpy.arange(taps)))
        return phase @ coefficients

    chain = (respond(15, 500, True) * respond(7, 1000, True) * respond(5, 1000, True) *
             respond(5, 5000, True))
    if nyquist > 21000:
        chain = chain * respond(45, 20000, False)
        chain = chain + chain * respond(5, 15000, True) * 0.5
    return numpy.abs(chain) ** 2


def to_db(value, floor=-120.0):
    return max(floor, 20.0 * math.log10(max(value, 1e-12)))


def to_lufs(power):
    return max(LOUDNESS_FLOOR, -0.691 + 10.0 * math.log10(max(power, 1e-12)))


def get_k_weights(size, rate):
    freqs = numpy.fft.rfftfreq(size, 1.0 / rate)
    z = numpy.exp(-2j * numpy.pi * freqs / 48000.0)
    response = numpy.ones(len(freqs), dtype=complex)
    for (b0, b1, b2), (a0, a1, a2) in K_STAGES:
        response *= (b0 + b1 * z + b2 * z * z) / (a0 + a1 * z + a2 * z * z)
    return numpy.abs(response) ** 2


def get_gram_colours():
    stops = [(at, numpy.array([int(tone[k:k + 2], 16) for k in (1, 3, 5)], dtype=float))
             for at, tone in GRAM_STOPS]
    table = numpy.zeros((256, 3), dtype=numpy.uint8)
    for index in range(256):
        ratio = index / 255.0
        for (a, ca), (b, cb) in zip(stops, stops[1:]):
            if ratio <= b:
                table[index] = ca + (cb - ca) * ((ratio - a) / max(b - a, 1e-9))
                break
    return table


GRAM_COLOURS = get_gram_colours()


def get_band_edges(count, low=SPECTRUM_LOW, high=SPECTRUM_HIGH):
    return numpy.geomspace(low, high, count + 1)


def read_samples(hstream, channels, count):
    '''(count x 2) float samples about to be heard, None when there are none (stopped)'''
    if not hstream or pybass.BASS_ChannelIsActive(hstream) != pybass.BASS_ACTIVE_PLAYING:
        return None
    channels = max(int(channels or 2), 1)
    data = numpy.zeros(count * channels, dtype=numpy.float32)
    got = audio.get_channel_data(hstream, data.ctypes.data_as(ctypes.c_void_p),
                                     (count * channels * 4) | pybass.BASS_DATA_FLOAT)
    if got in (0, 0xFFFFFFFF):
        return None
    data = data[:got // 4 // channels * channels].reshape(-1, channels)
    if len(data) == 0:
        return None
    if channels == 1:
        return numpy.repeat(data, 2, axis=1)
    return data[:, :2]


class Analyzer():

    def __init__(self):
        self.Reset()

    def Reset(self):
        # a new song: the hold, the loudness and the pictures from nothing
        self.lap = None
        self.peak = [FLOOR, FLOOR]
        self.hold = [FLOOR, FLOOR]
        self.hold_lap = [0.0, 0.0]
        self.rms = [FLOOR, FLOOR]
        self.squares = [0.0, 0.0]
        self.clip = [False, False]
        self.correlation = 0.0
        self.balance = 0.0
        self.powers = deque()
        self.gated = []
        self.gate_lap = 0.0
        self.loudness = (LOUDNESS_FLOOR, LOUDNESS_FLOOR, LOUDNESS_FLOOR)
        self.spectrum = numpy.full(SPECTRUM_BANDS, SPECTRUM_FLOOR)
        self.peak_line = numpy.full(SPECTRUM_BANDS, SPECTRUM_FLOOR)
        self.peak_line_lap = numpy.zeros(SPECTRUM_BANDS)
        self.gram = numpy.zeros((GRAM_ROWS, GRAM_COLUMNS), dtype=numpy.uint8)
        self.gram_index = 0
        self.scope = numpy.zeros((SCOPE_SIDE, SCOPE_SIDE), dtype=numpy.float32)
        self.bars = None
        self.autogain = AUTOGAIN_DEFAULT
        self.wave = numpy.zeros((3, WAVE_COLUMNS))
        self.wave_index = 0
        self.rate = 0
        self.k_weights = {}
        self.bins = {}
        self.bar_cache = {}
        # the bars' strip's width (the GUI's: a bar every BAR_PITCH px, its notes split as
        # many times as it is wider than BAR_SET bars)
        self.bar_scale = getattr(self, 'bar_scale', 1)

    def GetKWeights(self, size, rate):
        key = (size, rate)
        if key not in self.k_weights:
            # (a frame's size is its time's: one more nearly every frame, kept without end)
            if len(self.k_weights) >= 256:
                self.k_weights.clear()
            self.k_weights[key] = get_k_weights(size, rate)
        return self.k_weights[key]

    def GetBins(self, rate, count):
        # the FFT's bins of each band (a band narrower than a bin takes the nearest one)
        key = (rate, count)
        if key not in self.bins:
            freqs = numpy.fft.rfftfreq(FFT_SIZE, 1.0 / rate)
            edges = get_band_edges(count)
            starts = numpy.searchsorted(freqs, edges[:-1])
            ends = numpy.maximum(numpy.searchsorted(freqs, edges[1:]), starts + 1)
            starts = numpy.minimum(starts, len(freqs) - 1)
            ends = numpy.minimum(ends, len(freqs))
            middles = numpy.sqrt(edges[:-1] * edges[1:])
            tilt = SPECTRUM_TILT * numpy.log2(middles / 1000.0)
            self.bins[key] = (starts, ends, tilt)
        return self.bins[key]

    def Update(self, samples, rate, whole=True):
        '''a frame's readings from samples (n x 2, about to be heard; None: silence, the
        meters falling and the pictures still; whole False: the levels and the loudness
        only, the pictures falling as in silence)'''
        now = time.perf_counter()
        elapsed = 0.0 if self.lap is None else min(now - self.lap, 0.25)
        self.lap = now
        if samples is None or rate <= 0:
            self.Fall(elapsed, now)
            return
        self.rate = rate
        # what is heard until the next frame: its levels, its loudness, its stereo
        part = samples[:max(int(rate * max(elapsed, 1.0 / 60)), 64)].astype(numpy.float64)
        self.UpdateLevels(part, elapsed, now)
        self.UpdateLoudness(part, rate, now)
        if whole is False:
            self.FallPictures(elapsed)
            return
        self.UpdateStereo(part, elapsed)
        self.UpdateSpectrum(samples, rate, elapsed, now)
        self.UpdateScope(samples[:SCOPE_SAMPLES])
        self.UpdateBars(samples, rate, elapsed)
        self.UpdateWave(part)

    def IsSettled(self):
        # nothing left falling (stopped a while): no frame needed
        return max(self.peak + self.rms + self.hold) <= FLOOR\
            and float(self.spectrum.max()) <= SPECTRUM_FLOOR\
            and float(self.peak_line.max()) <= SPECTRUM_FLOOR and float(self.scope.max()) < 0.01\
            and (self.bars is None or float(self.bars.max()) < 1e-3)\
            and abs(self.correlation) < 0.005 and abs(self.balance) < 0.01

    def Fall(self, elapsed, now):
        for c in (0, 1):
            self.peak[c] = max(self.peak[c] - PEAK_FALL * elapsed, FLOOR)
            self.rms[c] = max(self.rms[c] - PEAK_FALL * elapsed, FLOOR)
            if now - self.hold_lap[c] > HOLD_TIME:
                self.hold[c] = max(self.hold[c] - HOLD_FALL * elapsed, FLOOR)
        self.FallPictures(elapsed)
        # the stereo's readings back to their middle and the loudness's gone (they held their
        # last after a pause, "the meters do not come back", the user); the song's gated
        # momentaries kept, its integrated loudness going on from them when it plays again
        self.correlation *= max(0.0, 1.0 - elapsed * 8)
        self.balance *= max(0.0, 1.0 - elapsed * 8)
        self.loudness = (LOUDNESS_FLOOR, LOUDNESS_FLOOR, LOUDNESS_FLOOR)

    def FallPictures(self, elapsed):
        self.spectrum = numpy.maximum(self.spectrum - SPECTRUM_FALL * elapsed, SPECTRUM_FLOOR)
        self.peak_line = numpy.maximum(self.peak_line - PEAK_LINE_FALL * elapsed,
                                       SPECTRUM_FLOOR)
        self.scope *= SCOPE_PERSIST
        if self.bars is not None:
            self.bars = self.bars * max(0.0, 1.0 - elapsed * 8)

    def UpdateLevels(self, part, elapsed, now):
        share = 1.0 - math.exp(-elapsed / RMS_TIME) if elapsed > 0 else 1.0
        for c in (0, 1):
            top = float(numpy.abs(part[:, c]).max())
            if top >= CLIP_LEVEL:
                self.clip[c] = True
            db = to_db(top, FLOOR)
            self.peak[c] = db if db >= self.peak[c] else max(self.peak[c] - PEAK_FALL * elapsed, db)
            if db >= self.hold[c]:
                self.hold[c] = db
                self.hold_lap[c] = now
            elif now - self.hold_lap[c] > HOLD_TIME:
                self.hold[c] = max(self.hold[c] - HOLD_FALL * elapsed, db)
            self.squares[c] += (float((part[:, c] ** 2).mean()) - self.squares[c]) * share
            self.rms[c] = to_db(math.sqrt(max(self.squares[c], 0.0)), FLOOR)

    def UpdateLoudness(self, part, rate, now):
        # the part's K-weighted power, kept by time: the momentary and the short-term are
        # its means over their windows, the integrated the gated momentaries of the song
        spectrum = numpy.abs(numpy.fft.rfft(part, axis=0)) ** 2
        spectrum[1:-1] *= 2
        weights = self.GetKWeights(len(part), rate)
        power = float((spectrum * weights[:, None]).sum()) / len(part) ** 2
        self.powers.append((now, power))
        while self.powers and now - self.powers[0][0] > SHORT:
            self.powers.popleft()

        def mean(window):
            values = [p for at, p in self.powers if now - at <= window]
            return sum(values) / len(values) if values else 0.0

        momentary = mean(MOMENTARY)
        if now - self.gate_lap >= GATE_EVERY:
            self.gate_lap = now
            if to_lufs(momentary) > ABSOLUTE_GATE:
                self.gated.append(momentary)
        integrated = LOUDNESS_FLOOR
        if self.gated:
            gated = numpy.array(self.gated)
            threshold = to_lufs(float(gated.mean())) + RELATIVE_GATE
            kept = gated[-0.691 + 10 * numpy.log10(numpy.maximum(gated, 1e-12)) > threshold]
            if len(kept):
                integrated = to_lufs(float(kept.mean()))
        self.loudness = (to_lufs(momentary), to_lufs(mean(SHORT)), integrated)

    def UpdateStereo(self, part, elapsed):
        left, right = part[:, 0], part[:, 1]
        ll, rr, lr = float((left ** 2).sum()), float((right ** 2).sum()), float((left * right).sum())
        share = 1.0 - math.exp(-elapsed / STEREO_TIME) if elapsed > 0 else 1.0
        if ll > 1e-9 and rr > 1e-9:
            self.correlation += (lr / math.sqrt(ll * rr) - self.correlation) * share
            balance = 10.0 * math.log10(rr / ll)
            self.balance += (min(max(balance, -12.0), 12.0) - self.balance) * share

    def UpdateSpectrum(self, samples, rate, elapsed, now):
        mono = samples[:FFT_SIZE].mean(axis=1)
        if len(mono) < FFT_SIZE:
            mono = numpy.concatenate((mono, numpy.zeros(FFT_SIZE - len(mono))))
        window = numpy.hanning(FFT_SIZE)
        # a full scale sine's bin at 0 dB
        magnitude = numpy.abs(numpy.fft.rfft(mono * window)) / (window.sum() / 2.0)
        starts, ends, tilt = self.GetBins(rate, SPECTRUM_BANDS)
        power = magnitude ** 2
        cumulative = numpy.concatenate(([0.0], numpy.cumsum(power)))
        means = (cumulative[ends] - cumulative[starts]) / numpy.maximum(ends - starts, 1)
        levels = 10.0 * numpy.log10(numpy.maximum(means, 1e-12)) + tilt
        levels = numpy.maximum(levels, SPECTRUM_FLOOR)
        self.spectrum = self.spectrum + (levels - self.spectrum) * SPECTRUM_SMOOTH
        # the peak line over the curve as drawn (the raw frame's above it by 20 dB)
        levels = self.spectrum
        rising = levels >= self.peak_line
        self.peak_line_lap[rising] = now
        held = now - self.peak_line_lap <= PEAK_LINE_HOLD
        self.peak_line = numpy.where(rising, levels, numpy.where(
            held, self.peak_line, numpy.maximum(self.peak_line - PEAK_LINE_FALL * elapsed, levels)))
        # the spectrogram's column on its own rows, its colour index
        g_starts, g_ends, g_tilt = self.GetBins(rate, GRAM_ROWS)
        g_means = (cumulative[g_ends] - cumulative[g_starts]) / numpy.maximum(g_ends - g_starts, 1)
        rows = 10.0 * numpy.log10(numpy.maximum(g_means, 1e-12)) + g_tilt
        index = numpy.clip((rows - GRAM_LOW) / (GRAM_HIGH - GRAM_LOW) * 255.0, 0, 255)
        self.gram[:, self.gram_index] = index[::-1].astype(numpy.uint8)
        self.gram_index = (self.gram_index + 1) % GRAM_COLUMNS

    def UpdateScope(self, samples):
        # mid up, side across: a mono sound a line upright, out of phase one lying
        self.scope *= SCOPE_PERSIST
        left, right = samples[:, 0], samples[:, 1]
        mid, side = (left + right) * 0.5, (right - left) * 0.5
        half = SCOPE_SIDE / 2.0
        x = numpy.clip((half + side * half * 0.95).astype(int), 0, SCOPE_SIDE - 1)
        y = numpy.clip((half - mid * half * 0.95).astype(int), 0, SCOPE_SIDE - 1)
        numpy.add.at(self.scope, (y, x), 0.35)
        numpy.minimum(self.scope, 1.0, out=self.scope)

    def GetBarBins(self, rate):
        # the bars' FFT bins: the notes, split bar_scale times (PyWinAudio's get_bar_bins)
        key = ('bins', rate, self.bar_scale)
        if key not in self.bar_cache:
            _, points = get_bar_points(rate)
            limit = points // 2 - 1
            bins = list(BAR_LOW_PAD) + [freq for freq in BAR_NOTES
                                        if 8 < freq < limit + len(BAR_LOW_PAD) + 1] + [limit]
            for index in range(len(bins) - 1, 0, -1):
                step = (bins[index] - bins[index - 1]) / self.bar_scale
                for part in range(self.bar_scale - 1, 0, -1):
                    bins.insert(index, bins[index - 1] + step * part)
            self.bar_cache[key] = bins
        return self.bar_cache[key]

    def GetBarWeights(self, rate, size):
        key = ('weights', rate, self.bar_scale, size)
        if key not in self.bar_cache:
            bins = self.GetBarBins(rate)
            lows, highs, logs, roots, powers = [], [], [], [], []
            for index, value in enumerate(bins[:-1]):
                low = max(0, int(value) - BAR_REACH)
                lows.append(low)
                highs.append(min(size, max(int(bins[index + 1]) + 1, int(value) + BAR_REACH + 1)))
                logs.append(math.log(1 + value, 2))
                roots.append(value ** 0.25)
                powers.append(1.4 * ((2 + index) / (1 + index)))
            lows, highs = numpy.array(lows), numpy.array(highs)
            reach = lows[:, None] + numpy.arange((highs - lows).max())[None, :]
            reach = numpy.minimum(reach, highs[:, None] - 1)
            self.bar_cache[key] = (reach, numpy.array(logs), numpy.array(roots),
                                   numpy.array(powers))
        return self.bar_cache[key]

    def UpdateBars(self, samples, rate, elapsed):
        # the bars' levels (0 to about 2.5: a bar's half height its share of the strip's)
        frame, points = get_bar_points(rate)
        left = samples[:frame, 0].astype(numpy.float64)
        raw = numpy.abs(numpy.fft.fft(left, points))[1:points // 2]
        key = ('autogain', rate)
        if key not in self.bar_cache:
            self.bar_cache[key] = get_autogain_weights(rate)
        energy = 2.0 * float((raw ** 2 * self.bar_cache[key]).sum()) / points / frame
        rms = math.sqrt(energy) * 3
        if rms >= 1e-4:
            low, high = AUTOGAIN_RANGE
            target = min(high, max(low, 0.14 / rms))
            self.autogain += (target - self.autogain) * min(1.0, elapsed / AUTOGAIN_FOLLOW)
        amplify = (self.autogain * (1.0 / 0.4) * 2 * (rate / 44100.0) * 1.25 *
                   math.sqrt(min(self.bar_scale, 3)))
        spectrum = raw * 32768.0 * amplify / points / 8192
        reach, logs, roots, powers = self.GetBarWeights(rate, len(spectrum))
        levels = spectrum[reach].max(axis=1) * logs * roots
        self.bars = (levels ** powers) * 1.5

    def UpdateWave(self, part):
        # the oscilloscope's column: the frame's highest, lowest and RMS (mono)
        mono = part.mean(axis=1)
        self.wave[:, self.wave_index] = (float(mono.max()), float(mono.min()),
                                         float(numpy.sqrt((mono ** 2).mean())))
        self.wave_index = (self.wave_index + 1) % WAVE_COLUMNS

    def GetWave(self, columns):
        # the last columns, oldest first: (3 x columns) highest, lowest, RMS
        columns = min(columns, WAVE_COLUMNS)
        order = (numpy.arange(WAVE_COLUMNS - columns, WAVE_COLUMNS) + self.wave_index)\
            % WAVE_COLUMNS
        return self.wave[:, order]

    def GetGram(self, columns):
        # the last columns, oldest first (rows: high frequencies at the top)
        columns = min(columns, GRAM_COLUMNS)
        order = (numpy.arange(GRAM_COLUMNS - columns, GRAM_COLUMNS) + self.gram_index)\
            % GRAM_COLUMNS
        return self.gram[:, order]
