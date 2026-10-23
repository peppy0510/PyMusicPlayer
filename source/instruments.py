# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audiograph
import collections
import copy
import ctypes
import math
import numpy
import os
import pybass
import synth
import threading
import time
import wave

from scipy import signal

from pybass import pybassmix as mix


# a push stream's proc: BASS's own (-1), not pybass's STREAMPROC_PUSH (a Python function
# wrapped: the stream made with it is no push stream, its data refused, the hits silent)
STREAMPROC_PUSH = ctypes.cast(ctypes.c_void_p(2 ** 64 - 1), pybass.STREAMPROC)


# the instruments' decks (audiograph's sources): a sampler playing pads on a pattern, in
# time with the song playing (its beat grid, its tempo), joining on its next sixteenth
# (the pattern where the bar is: on the next bar, PLAY was heard 2 s late at 126 BPM). the
# old machines taken as a flavour, not copied, under names of the player's own: RT909 (a
# drum machine: its kit a 909's punch or an 808's boom, KITS), PS1200 (a sampler: a bar
# of the song cut into its pads, crunched as a 12 bit one kept them) and BT303 (a bass
# line in the song's key, BassSource)

# DEBUG(hang): how often costly things run (mainapp's watchdog writes them); removed
# once found
COUNTS = collections.Counter()

RATE = audiograph.MIX_RATE
CHANS = audiograph.MIX_CHANS
# a pattern's steps a bar (sixteenths)
STEPS = 16
# how far ahead its hits are put in its mixer (seconds of what is heard): late enough
# to be sure of the song's position, early enough to be put in before they are mixed
LOOKAHEAD = 0.25
# the decks' levels when turned on (their channel's gain: a song mastered loud, a kit's
# peaks at full scale) at first: MIXER changes them (AudioControl.SetChannel)
DECK_GAIN = {'rt909': 0.55, 'ps1200': 0.7, 'bt303': 0.5}
# the song's clock eased this much a reading (Steady), taken as read past a jump this big
CLOCK_EASE = 0.05
CLOCK_JUMP = 0.05
# the crunch: the old samplers' rate and bits (26.04 kHz, 12), no filter before the rate
# falls (its aliasing is the sound)
CRUNCH_RATE = 26040.0
CRUNCH_BITS = 12


def envelope(count, decay):
    return numpy.exp(-numpy.arange(count) / (decay * RATE))


# RT909's voices: each pad a voice of its own made from its settings (render_voice), in
# one of two engines, the way the soft drum machines do it rather than any old circuit:
# - 'analog' (Microtonic's way): an oscillator (sine, triangle, saw, or 'metal': six
#   squares out of tune, an 808's cymbal) its pitch swept down from BEND semitones above,
#   and a noise through a filter (low, band or high pass) with its own decay ('exp', or
#   'clap': three bursts and a tail), mixed, driven into a soft clip
# - 'modal' (Drumaxx's way, physical): a membrane's modes (a circular drum's: its
#   overtones out of harmony) struck by a mallet (harder: its high modes louder), its
#   tension pitching it up as it is struck, damped (TONE: its high modes ringing as long
#   as its low or dying sooner), snare wires buzzing as it rings
ENGINES = ('analog', 'modal')
WAVES = ('sine', 'tri', 'saw', 'metal')
FILTERS = ('lp', 'bp', 'hp')
NOISE_ENVELOPES = ('exp', 'clap')
# a voice's knobs: (key, label, low, high, log) its value's range (log: in octaves)
ANALOG_KNOBS = (('pitch', 'PITCH', 20.0, 2000.0, True), ('bend', 'BEND', 0.0, 48.0, False),
                ('sweep', 'SWEEP', 0.002, 0.3, True), ('decay', 'DECAY', 0.01, 2.0, True),
                ('noise_freq', 'N FREQ', 80.0, 16000.0, True),
                ('noise_q', 'N RES', 0.5, 12.0, True),
                ('noise_decay', 'N DECAY', 0.005, 1.5, True), ('mix', 'MIX', 0.0, 1.0, False),
                ('drive', 'DRIVE', 0.0, 1.0, False), ('level', 'LEVEL', 0.0, 1.0, False))
MODAL_KNOBS = (('pitch', 'PITCH', 20.0, 1200.0, True), ('bend', 'BEND', 0.0, 24.0, False),
               ('decay', 'DECAY', 0.02, 3.0, True), ('tone', 'TONE', 0.0, 1.0, False),
               ('mallet', 'MALLET', 0.0, 1.0, False), ('wires', 'WIRES', 0.0, 1.0, False),
               ('drive', 'DRIVE', 0.0, 1.0, False), ('level', 'LEVEL', 0.0, 1.0, False))
# a circular membrane's modes: their frequencies to its first (Bessel's zeros)
MEMBRANE = (1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501, 3.600, 3.652)
# an 808's metal: six square waves out of tune with each other (to its PITCH at 400)
METAL = (205.3, 304.4, 369.6, 522.7, 540.0, 800.0)
# the longest a voice rings (seconds)
VOICE_MOST = 3.0


def make_voice(**values):
    # a voice's settings, those not given at their middle
    voice = dict(engine='analog', wave='sine', filter='hp', noise_env='exp', pitch=200.0,
                 bend=0.0, sweep=0.02, decay=0.2, noise_freq=4000.0, noise_q=0.7,
                 noise_decay=0.05, mix=0.0, drive=0.0, level=0.8, tone=0.5, mallet=0.5,
                 wires=0.0)
    voice.update(values)
    return voice


def get_knobs(voice):
    return MODAL_KNOBS if voice.get('engine') == 'modal' else ANALOG_KNOBS


def to_knob(spec, value):
    # a setting as its knob's turn (0 to 1)
    _, _, low, high, log = spec
    if log:
        return math.log(max(value, low) / low) / math.log(high / low)
    return (value - low) / float(high - low)


def from_knob(spec, turn):
    _, _, low, high, log = spec
    turn = min(max(turn, 0.0), 1.0)
    if log:
        return low * (high / low) ** turn
    return low + (high - low) * turn


def biquad(data, mode, freq, q):
    # a 2 pole filter (the cookbook's), low, band or high pass, or a notch
    w = 2.0 * math.pi * min(max(freq, 20.0), RATE * 0.45) / RATE
    alpha = math.sin(w) / (2.0 * max(q, 0.1))
    cos = math.cos(w)
    if mode == 'lp':
        b = ((1 - cos) / 2, 1 - cos, (1 - cos) / 2)
    elif mode == 'bp':
        b = (alpha, 0.0, -alpha)
    elif mode == 'notch':
        b = (1.0, -2 * cos, 1.0)
    else:
        b = ((1 + cos) / 2, -(1 + cos), (1 + cos) / 2)
    a = (1 + alpha, -2 * cos, 1 - alpha)
    return signal.lfilter(numpy.array(b) / a[0], numpy.array(a) / a[0], data)


# PS1200's filter: its kinds, its slopes (dB an octave: 24 two stages, the first flat
# (Butterworth's), the resonance on the second)
SLICE_FILTERS = ('lp', 'hp', 'bp', 'notch')
SLOPES = (12, 24)
BUTTERWORTH_FIRST = 0.541
BUTTERWORTH_SECOND = 1.307


def slope_filter(data, mode, freq, q, slope=12):
    if slope != 24:
        return biquad(data, mode, freq, q)
    data = biquad(data, mode, freq, BUTTERWORTH_FIRST if mode in ('lp', 'hp') else q)
    return biquad(data, mode, freq, q * BUTTERWORTH_SECOND / 0.707
                  if mode in ('lp', 'hp') else q)


def soft_clip(data, drive):
    if drive <= 0:
        return data
    gain = 1.0 + drive * 8.0
    return numpy.tanh(data * gain) / math.tanh(gain)


def normalize(data):
    peak = numpy.abs(data).max() if len(data) else 0.0
    return data / peak if peak > 1e-9 else data


def render_voice(voice):
    '''a voice's sound (mono, the mixer's rate) from its settings (make_voice)'''
    if voice.get('engine') == 'modal':
        out = render_modal(voice)
    else:
        out = render_analog(voice)
    out = soft_clip(normalize(out), voice['drive']) * voice['level']
    # a few ms faded at its end (no click where it stops)
    tail = min(int(0.005 * RATE), len(out))
    out[-tail:] *= numpy.linspace(1.0, 0.0, tail)
    return out


def render_analog(voice):
    decay, noise_decay = voice['decay'], voice['noise_decay']
    if voice['noise_env'] == 'clap':
        noise_decay += 0.03
    n = int(min(max(decay * (1.0 - voice['mix']), noise_decay * voice['mix'], 0.01) * 5.0,
                VOICE_MOST) * RATE)
    t = numpy.arange(n) / RATE
    osc = numpy.zeros(n)
    if voice['mix'] < 1.0:
        freq = voice['pitch'] * 2.0 ** (voice['bend'] / 12.0 * numpy.exp(-t / voice['sweep']))
        phase = numpy.cumsum(freq) / RATE
        wave = voice['wave']
        if wave == 'tri':
            osc = 2.0 * numpy.abs(2.0 * (phase % 1.0) - 1.0) - 1.0
        elif wave == 'saw':
            osc = 2.0 * (phase % 1.0) - 1.0
        elif wave == 'metal':
            osc = sum(numpy.sign(numpy.sin(2.0 * math.pi * f / 400.0 * phase))
                      for f in METAL) / len(METAL)
            # its highs alone (an 808's hats)
            osc = biquad(osc, 'hp', 6000.0, 0.7)
        else:
            osc = numpy.sin(2.0 * math.pi * phase)
        osc = normalize(osc) * envelope(n, decay)
    noise = numpy.zeros(n)
    if voice['mix'] > 0.0:
        noise = biquad(numpy.random.default_rng(7).standard_normal(n), voice['filter'],
                       voice['noise_freq'], voice['noise_q'])
        if voice['noise_env'] == 'clap':
            shape = numpy.zeros(n)
            for start in (0.0, 0.011, 0.022):
                k = int(start * RATE)
                shape[k:] += envelope(n - k, 0.004)
            k = int(0.03 * RATE)
            shape[k:] += envelope(n - k, voice['noise_decay']) * 0.6
        else:
            shape = envelope(n, noise_decay)
        noise = normalize(noise) * shape
    return osc * (1.0 - voice['mix']) + noise * voice['mix']


def render_modal(voice):
    decay = voice['decay']
    n = int(min(decay * 5.0, VOICE_MOST) * RATE)
    t = numpy.arange(n) / RATE
    # the strike's tension: up BEND semitones at first, settling in 30 ms
    bend = 2.0 ** (voice['bend'] / 12.0 * numpy.exp(-t / 0.03))
    base = 2.0 * math.pi * numpy.cumsum(voice['pitch'] * bend) / RATE
    hard = voice['mallet']
    out = numpy.zeros(n)
    for k, ratio in enumerate(MEMBRANE):
        # a soft mallet: the high modes faint; TONE: they ring as long as the first
        level = (1.0 / (k + 1)) ** (2.0 - 1.6 * hard)
        ring = decay / (1.0 + (1.0 - voice['tone']) * 3.0 * (ratio - 1.0))
        out += numpy.sin(base * ratio) * envelope(n, ring) * level
    # the mallet's knock: a short noise, brighter and shorter the harder it is
    knock = min(int((0.004 - 0.0035 * hard) * RATE) + 8, n)
    click = numpy.random.default_rng(9).standard_normal(knock) * numpy.linspace(1, 0, knock)
    click = biquad(click, 'lp', 1500.0 + 9000.0 * hard, 0.7)
    out[:knock] += normalize(click) * 0.4 * (0.3 + hard)
    if voice['wires'] > 0:
        # the wires buzzing while the head moves (its first mode's ring)
        wires = biquad(numpy.random.default_rng(11).standard_normal(n), 'bp', 5000.0, 0.8)
        out += normalize(wires) * envelope(n, min(decay, 0.25)) * voice['wires'] * 0.9
    return out


# the crunch's output filter (an old sampler's own, after its converter): without it the
# held samples' images sizzled
CRUNCH_OUT = 11000.0


def crunch(mono, rate=CRUNCH_RATE, bits=CRUNCH_BITS):
    '''the sound as an old sampler kept it: held at its lower rate (no filter before:
    aliased), rounded to its bits, back to the mixer's rate by holding each sample, then
    its output filter's low-pass'''
    step = RATE / rate
    idx = (numpy.floor(numpy.arange(len(mono)) / step) * step).astype(int)
    held = mono[numpy.minimum(idx, len(mono) - 1)]
    levels = 2 ** (bits - 1)
    out = numpy.round(numpy.clip(held, -1.0, 1.0) * levels) / levels
    return biquad(out, 'lp', CRUNCH_OUT, 0.6)


class Pad():

    '''a sound: its samples (mono, the mixer's rate), or a voice it is made from (RT909's,
    render_voice); gain, pitch (a rate: 2.0 an octave up, shorter, as on the old samplers),
    crunched or not; a slice's (PS1200's) reversed, its decay (seconds, None: as cut), a
    filter over it (SLICE_FILTERS' kind, None: none; its cutoff Hz, resonance and slope).
    made again when set'''

    def __init__(self, name, mono=None, gain=1.0, pitch=1.0, crunched=False, voice=None):
        self.name = name
        self.voice = voice
        self.source = numpy.asarray(render_voice(voice) if voice is not None else mono,
                                    dtype=numpy.float32)
        self.gain = gain
        self.pitch = pitch
        self.crunched = crunched
        self.reverse = False
        self.decay = None
        self.filter = None
        self.cutoff = None
        self.resonance = 0.7
        self.slope = 12
        # a slice's: seconds of it before its grid point (its cut moved to its hit), so it
        # plays where it was in the song
        self.lead = 0.0
        # an RT909 slot's: what it shows, its choke group (CHOKE_GROUPS, None: none)
        self.label = name.upper()
        self.choke = None
        self.Render()

    def Render(self):
        if self.source.ndim == 2:
            # (a synth's: rendered stereo, as it plays)
            self.data = numpy.ascontiguousarray(numpy.clip(self.source * self.gain, -1.0, 1.0),
                                                dtype=numpy.float32)
            return
        mono = self.source[::-1] if self.reverse else self.source
        if self.decay is not None:
            mono = mono * envelope(len(mono), self.decay)
        if self.filter in SLICE_FILTERS and self.cutoff is not None:
            mono = slope_filter(mono, self.filter, self.cutoff, self.resonance, self.slope)
        if self.crunched:
            mono = crunch(mono)
        stereo = numpy.repeat(numpy.clip(mono * self.gain, -1.0, 1.0)[:, None], CHANS, axis=1)
        self.data = numpy.ascontiguousarray(stereo, dtype=numpy.float32)

    def SetCrunch(self, on):
        self.crunched = bool(on)
        self.Render()

    def SetVoice(self, **values):
        # its voice's settings changed: its sound made again
        self.voice.update(values)
        self.source = numpy.asarray(render_voice(self.voice), dtype=numpy.float32)
        self.Render()


def write_wav(path, mono):
    # a mono sound as a 16 bit WAV (a rendered grab's, read back as a song's)
    data = (numpy.clip(mono, -1.0, 1.0) * 32767).astype(numpy.int16)
    with wave.open(path, 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(RATE)
        file.writeframes(data.tobytes())


def read_mono(path, start, length):
    '''length seconds of a file from start, mono at the mixer's rate (its own resampled),
    None when it does not open'''
    # (scanned whole first, as the deck's stream is: a compressed file's seek landed some
    # ms off without it, and a grabbed bar played against the song combed it)
    handle = pybass.BASS_StreamCreateFile(
        False, path, 0, 0,
        pybass.BASS_UNICODE | pybass.BASS_SAMPLE_FLOAT | pybass.BASS_STREAM_DECODE
        | pybass.BASS_STREAM_PRESCAN)
    if not handle:
        return None
    try:
        info = pybass.BASS_CHANNELINFO()
        pybass.BASS_ChannelGetInfo(handle, ctypes.byref(info))
        fs, chans = info.freq, max(info.chans, 1)
        pybass.BASS_ChannelSetPosition(
            handle, pybass.BASS_ChannelSeconds2Bytes(handle, max(start, 0.0)),
            pybass.BASS_POS_BYTE)
        frames = int(length * fs)
        data = numpy.zeros(frames * chans, dtype=numpy.float32)
        got = pybass.BASS_ChannelGetData(handle, data.ctypes.data_as(ctypes.c_void_p),
                                         data.nbytes | pybass.BASS_DATA_FLOAT)
        if got in (-1, 0xFFFFFFFF) or got <= 0:
            return None
        mono = data[:got // 4 // chans * chans].reshape(-1, chans).mean(axis=1)
    finally:
        pybass.BASS_StreamFree(handle)
    if fs != RATE:
        mono = numpy.interp(numpy.arange(int(len(mono) * RATE / fs)) * fs / RATE,
                            numpy.arange(len(mono)), mono)
    return mono


# a grab's cuts moved to the hit nearest their grid point (its attack, a ms before it)
# within SNAP_WINDOW: a grid a few ms off cut no kick in half; a hit counted where the
# highs' rise (a ms a frame) is SNAP_FLOOR times its usual and a tenth of the bar's
# strongest at least (its usual alone: a bar of clean hits found only its first)
SNAP_WINDOW = 0.015
SNAP_HOP = 0.001
SNAP_FLOOR = 4.0
SNAP_RISE = 2.0


def snap_cuts(mono, cuts):
    hop = max(int(SNAP_HOP * RATE), 1)
    high = numpy.diff(mono, prepend=mono[:1])
    frames = len(high) // hop
    if frames < 3:
        return list(cuts)
    energy = numpy.sqrt((high[:frames * hop].reshape(frames, hop) ** 2).mean(axis=1))
    flux = numpy.maximum(numpy.diff(energy, prepend=energy[:1]), 0.0)
    floor = max(float(numpy.median(flux)) * SNAP_FLOOR, float(flux.max()) * 0.1, 1e-9)
    window = int(SNAP_WINDOW * RATE)
    snapped = []
    for cut in cuts:
        a = max((cut - window) // hop, 0)
        b = min((cut + window) // hop + 1, frames)
        k = a + int(numpy.argmax(flux[a:b])) if b > a else None
        # (a hit: the level after it up by SNAP_RISE on the level before; a steady sound's
        # wobble moved the cuts off each other, and the slices crossfaded out of phase)
        rise = k is not None and energy[min(k + 3, frames - 1)]\
            > energy[max(k - 3, 0)] * SNAP_RISE + 1e-9
        moved = cut if k is None or flux[k] <= floor or not rise else max((k - 1) * hop, 0)
        # (in order, a few ms apart at least)
        if snapped:
            moved = max(moved, snapped[-1] + 4 * hop)
        snapped.append(moved)
    return snapped


def grab_slices(path, start, bpm, bars=1, slices=STEPS, crunched=True):
    '''a part of a song as an old sampler's pads: bars of it from start (its grid's
    downbeat), cut in slices (a sixteenth each, at 16 a bar; each cut moved to its hit,
    snap_cuts), each a pad ('slice 1'...), and the pattern playing them back in order (the
    part as it was, in time with the song; changed, a beat of its own). crunched: as a 12
    bit sampler kept it. (pads, pattern, the part as it is on the grid: to be seen)'''
    bar = 4 * 60.0 / bpm
    # (a little before and after it: its first and last cuts' room to move)
    before = min(SNAP_WINDOW, max(start, 0.0))
    mono = read_mono(path, start - before,
                     bar * bars + before + SNAP_WINDOW + bar / STEPS * SLICE_TAIL)
    if mono is None:
        return None, None, None
    count = slices * bars
    offset = int(before * RATE)
    size = int(bar * bars * RATE) // count
    if offset + size * count > len(mono):
        size = (len(mono) - offset) // count
    if size <= 0:
        return None, None, None
    # (each at its own place to the fraction: a whole sample's size a slice put the bar's
    # last ones 8 samples off the song)
    exact = [offset + k * bar * bars * RATE / count for k in range(count + 1)]
    cuts = snap_cuts(mono, [int(round(at)) for at in exact[:count]])
    cuts.append(min(int(round(exact[count])), len(mono)))
    # (each to SLICE_TAIL steps past its own: the part read on past the bar for the last)
    ends = [min(cuts[min(k + 1, count)] + SLICE_TAIL * size, len(mono)) for k in range(count)]
    pads, pattern = [], {}
    for k in range(count):
        name = 'slice %d' % (k + 1)
        piece = mono[cuts[k]:max(ends[k], cuts[k] + 1)].copy()
        # faded in over CHOKE_FADE (the one before fading out over it: one sound across
        # the cut), out over a few ms at its end (no click where it was cut)
        fade_in = min(int(CHOKE_FADE * RATE), len(piece) // 4)
        fade = min(int(0.003 * RATE), len(piece) // 4)
        if fade_in:
            piece[:fade_in] *= numpy.linspace(0, 1, fade_in)
        if fade:
            piece[-fade:] *= numpy.linspace(1, 0, fade)
        pad = Pad(name, piece, crunched=crunched)
        pad.lead = (exact[k] - cuts[k]) / float(RATE)
        pads.append(pad)
        steps = [0] * STEPS
        if k < STEPS:
            steps[k] = 1.0
        pattern[name] = steps
    return pads, pattern, mono[offset:offset + count * size]


# RT909's kits: its five pads' voices (the same names in each: a pattern kept when the
# kit changes). '909': a short hard kick, a bright snare, noise hats; '808': a long low
# kick, a rounder snare, metal hats; 'PHY': struck membranes (the modal engine), a real
# kit's spirit
KIT_VOICES = {
    '909': dict(
        kick=dict(pitch=52.0, bend=24.0, sweep=0.022, decay=0.12, mix=0.12, filter='lp',
                  noise_freq=3000.0, noise_decay=0.004, drive=0.35, level=1.0),
        snare=dict(wave='tri', pitch=185.0, bend=5.0, sweep=0.01, decay=0.05, mix=0.6,
                   noise_freq=1800.0, noise_decay=0.11, drive=0.1, level=0.85),
        clap=dict(mix=1.0, filter='bp', noise_freq=1200.0, noise_q=1.5, noise_env='clap',
                  noise_decay=0.09, level=0.75),
        hat=dict(mix=1.0, noise_freq=7500.0, noise_decay=0.018, level=0.5),
        tom=dict(pitch=110.0, bend=7.0, sweep=0.03, decay=0.2, mix=0.08, filter='lp',
                 noise_freq=2500.0, noise_decay=0.01, drive=0.2, level=0.85),
        rim=dict(wave='tri', pitch=1700.0, decay=0.012, mix=0.35, filter='bp',
                 noise_freq=3200.0, noise_q=2.0, noise_decay=0.01, level=0.7),
        cowbell=dict(wave='metal', pitch=560.0, decay=0.09, level=0.55),
        cymbal=dict(mix=0.7, wave='metal', pitch=480.0, decay=0.6, noise_freq=8000.0,
                    noise_decay=0.7, level=0.4),
        **{'open hat': dict(mix=1.0, noise_freq=7000.0, noise_decay=0.12, level=0.45)}),
    '808': dict(
        kick=dict(pitch=46.0, bend=12.0, sweep=0.02, decay=0.42, mix=0.04, filter='lp',
                  noise_freq=2000.0, noise_decay=0.003, level=1.0),
        snare=dict(pitch=238.0, bend=2.0, sweep=0.01, decay=0.06, mix=0.45,
                   noise_freq=1500.0, noise_decay=0.05, level=0.8),
        clap=dict(mix=1.0, filter='bp', noise_freq=1000.0, noise_q=1.2, noise_env='clap',
                  noise_decay=0.14, level=0.7),
        hat=dict(wave='metal', pitch=400.0, decay=0.022, level=0.55),
        tom=dict(pitch=95.0, bend=5.0, sweep=0.04, decay=0.35, mix=0.02, filter='lp',
                 noise_freq=2000.0, noise_decay=0.004, level=0.85),
        rim=dict(wave='sine', pitch=1650.0, decay=0.01, mix=0.2, filter='hp',
                 noise_freq=4000.0, noise_decay=0.006, level=0.7),
        cowbell=dict(wave='metal', pitch=540.0, decay=0.14, level=0.55),
        cymbal=dict(wave='metal', pitch=400.0, decay=0.9, level=0.4),
        **{'open hat': dict(wave='metal', pitch=400.0, decay=0.16, level=0.45)}),
    'PHY': dict(
        kick=dict(engine='modal', pitch=58.0, bend=4.0, decay=0.35, tone=0.15, mallet=0.45,
                  level=1.0),
        snare=dict(engine='modal', pitch=185.0, bend=1.5, decay=0.16, tone=0.55,
                   mallet=0.75, wires=0.85, level=0.85),
        clap=dict(mix=1.0, filter='bp', noise_freq=1200.0, noise_q=1.5, noise_env='clap',
                  noise_decay=0.12, level=0.7),
        hat=dict(wave='metal', pitch=520.0, decay=0.03, level=0.5),
        tom=dict(engine='modal', pitch=120.0, bend=3.0, decay=0.4, tone=0.3, mallet=0.5,
                 level=0.9),
        rim=dict(engine='modal', pitch=900.0, bend=0.5, decay=0.05, tone=0.8, mallet=1.0,
                 level=0.7),
        cowbell=dict(wave='metal', pitch=600.0, decay=0.12, level=0.5),
        cymbal=dict(wave='metal', pitch=520.0, decay=1.2, level=0.35),
        **{'open hat': dict(wave='metal', pitch=520.0, decay=0.22, level=0.4)}),
}
# the sounds a slot can take (any slot any of them, from any kit); a new RT909's slots
PAD_TYPES = ('kick', 'snare', 'clap', 'hat', 'open hat', 'tom', 'rim', 'cowbell', 'cymbal')
PAD_NAMES = ('kick', 'snare', 'clap', 'hat', 'open hat')
# its slots at most (a row each)
SLOTS_MOST = 8
# choke groups a slot can be in (a hit in one cuts the others' sounds)
CHOKE_GROUPS = ('A', 'B')


def make_kit(kit='909'):
    return [make_kit_pad(name, kit) for name in PAD_NAMES]


def make_kit_pad(kind, kit, name=None):
    '''a slot's pad: a sound (PAD_TYPES) from a kit, its voice telling both (a kit of its
    own, a slot at a time); its name the slot's id, its label what it shows (the sound's
    till renamed), a closed and an open hat choking each other'''
    voices = KIT_VOICES.get(kit, KIT_VOICES['909'])
    pad = Pad(name or kind, voice=make_voice(kit=kit, kind=kind, **voices[kind]))
    pad.label = kind.upper()
    pad.choke = 'A' if kind in ('hat', 'open hat') else None
    return pad


KITS = ('909', '808', 'PHY')


# a step's velocity: on, accented (louder; its cell marked)
STEP_ON = 0.75
STEP_ACCENT = 1.0
# pads cut by the next hit of their group (its sound faded out over CHOKE_FADE): RT909's
# hats (a closed one cuts the open one, a 909's way); PS1200's slices when MONO (each cuts
# the one before, an SP-1200's way)
CHOKE_FADE = 0.002
# PS1200's sources: the deck's song (its file), a machine's bar (rendered), the deck and
# the machines together
GRAB_SOURCES = ('deck', 'rt909', 'bt303', 'sy4', 'vr1', 'mp60', 'mix')

# a slice's sound past its step (PS1200's: it rings till the next slice cuts it, crossfaded
# over CHOKE_FADE; cut at its step and faded at both ends, a bar of them ticked sixteen
# times)
SLICE_TAIL = 4
# swing: where the off sixteenths fall in their pair (0.5 straight, 0.66 a triplet's)
SWINGS = (0.5, 0.54, 0.58, 0.62, 0.66)


def is_accent(velocity):
    return velocity >= STEP_ACCENT - 0.05


def make_pattern():
    # a bar: four on the floor (its first accented), the claps on two and four, the hats
    # between
    pattern = {'kick': [0] * STEPS, 'snare': [0] * STEPS, 'clap': [0] * STEPS,
               'hat': [0] * STEPS, 'open hat': [0] * STEPS}
    for k in (0, 4, 8, 12):
        pattern['kick'][k] = STEP_ACCENT if k == 0 else STEP_ON
    for k in (4, 12):
        pattern['clap'][k] = STEP_ON
    for k in (2, 6, 10, 14):
        pattern['open hat'][k] = 0.6
    for k in range(0, STEPS, 2):
        pattern['hat'][k] = 0.4 if k % 4 else 0.55
    return pattern


class SamplerSource(audiograph.Source):

    '''a deck playing its pads on its pattern: a decoding mixer of its own, each hit a
    stream put in it at the sample it is due (BASS_Mixer_StreamAddChannelEx's delay), so
    the beat is the mixer's, not Python's. Tick (often, any thread) puts in the hits due
    within LOOKAHEAD, their times from clock: {position, bpm, anchor, rate} of the song (its
    seconds, its grid's beat and downbeat, its playing speed), None when it does not play'''

    KIND = 'sampler'
    LIVE = True
    SPLIT = True

    def __init__(self, clock, pads=None, pattern=None):
        audiograph.Source.__init__(self)
        self.clock = clock
        self.pads = dict((pad.name, pad) for pad in (make_kit() if pads is None else pads))
        self.pattern = make_pattern() if pattern is None else pattern
        # RT909's kit (KITS), None for another deck
        self.kit = '909' if pads is None else None
        # PS1200's: the bar grabbed (mono) its slices were cut from, every pad's pitch
        # moved by these semitones
        self.sample = None
        self.shift = 0.0
        # PS1200's: each slice cutting the one before; the bar it was grabbed from (path,
        # start, bpm, bars: grabbed again when its settings come back)
        # (PS1200's slices mono unless MONO is turned off: poly, they ring over each other)
        self.mono = pads is not None and len(pads) == 0
        self.grab = None
        # where PS1200 grabs from (GRAB_SOURCES)
        self.grab_from = 'deck'
        # the presets last loaded or saved (their names shown on its plate), None: its own
        self.sound_name = None
        self.pattern_name = None
        # pads muted, pads soloed (while any is, only they play)
        self.muted = set()
        self.soloed = set()
        self.lock = threading.Lock()
        self.next_step = None
        self.last = None
        self.armed = False
        self.history = []
        # its hits' streams lately put in (freed on STOP; freed by BASS once played, a
        # free of one gone does nothing)
        self.pending = collections.deque(maxlen=64)
        # the song's position as a line on the wall clock (position = offset + rate *
        # now), its offset eased toward each reading: read alone it moves in the mixer's
        # update steps (hits 10 ms off the grid at worst), eased it is steady
        self.offset = None

    def Open(self):
        self.handle = mix.BASS_Mixer_StreamCreate(
            RATE, CHANS, pybass.BASS_SAMPLE_FLOAT | pybass.BASS_STREAM_DECODE
            | mix.BASS_MIXER_NONSTOP)
        return self.handle

    def SetPads(self, pads, pattern=None):
        # new sounds (a kit, a song's slices), their pattern with them or kept
        with self.lock:
            self.pads = dict((pad.name, pad) for pad in pads)
            if pattern is not None:
                self.pattern = pattern

    # a pattern and its pads changed (a screen's, later): at once, from the next hit put in

    def SetStep(self, name, index, velocity):
        with self.lock:
            steps = self.pattern.setdefault(name, [0] * STEPS)
            steps[index % STEPS] = min(max(float(velocity), 0.0), 1.0)

    def ClearPattern(self):
        with self.lock:
            for steps in self.pattern.values():
                steps[:] = [0] * STEPS

    def SetPad(self, name, gain=None, pitch=None, crunched=None):
        with self.lock:
            pad = self.pads.get(name)
            if pad is None:
                return
            if gain is not None:
                pad.gain = gain
            if pitch is not None:
                pad.pitch = pitch
            if crunched is not None:
                pad.crunched = bool(crunched)
            pad.Render()

    def SetVoice(self, name, **values):
        # a pad's voice's settings (RT909's knobs): its sound made again
        with self.lock:
            pad = self.pads.get(name)
            if pad is not None and pad.voice is not None:
                pad.SetVoice(**values)

    def SetSample(self, pads, pattern, mono):
        # a bar grabbed (PS1200): its slices, its pattern, the bar to be seen
        with self.lock:
            self.pads = dict((pad.name, pad) for pad in pads)
            self.pattern = pattern
            self.sample = mono

    def SetSlice(self, name, **values):
        '''a slice's own (PS1200's): semis (its pitch in semitones), gain, decay (seconds,
        None: as cut), reverse'''
        with self.lock:
            pad = self.pads.get(name)
            if pad is None:
                return
            if 'semis' in values:
                # (whole semitones, as an old sampler's: a drag's fraction detuned a slice
                # against the song, a flanger)
                pad.pitch = 2.0 ** (round(values.pop('semis')) / 12.0)
            for key, value in values.items():
                setattr(pad, key, value)
            pad.Render()

    def SetFilter(self, **values):
        # the filter over every pad (PS1200's): filter (SLICE_FILTERS', None: none),
        # cutoff, resonance, slope
        with self.lock:
            for pad in self.pads.values():
                for key, value in values.items():
                    setattr(pad, key, value)
                pad.Render()

    def SetOffset(self, offset):
        '''the bar grabbed cut again offset seconds from its grid's downbeat (later: on);
        its slices' own settings and its pattern kept'''
        grab = self.grab
        if not grab:
            return False
        pads, _, mono = grab_slices(grab['path'], grab['start'] + offset, grab['bpm'],
                                    grab.get('bars', 1))
        if pads is None:
            return False
        self.TakeSlices(pads, None, mono, dict(grab, offset=offset))
        return True

    def TakeSlices(self, pads, pattern, mono, grab):
        '''slices cut (grab_slices) its pads: each one's own settings and the filter as they
        were; pattern None: its own kept'''
        old = dict(self.pads)
        for pad in pads:
            before = old.get(pad.name)
            if before is not None:
                for key in ('pitch', 'gain', 'decay', 'reverse', 'crunched', 'filter',
                            'cutoff', 'resonance', 'slope'):
                    setattr(pad, key, getattr(before, key))
                pad.Render()
        if pattern is None:
            pattern = dict((pad.name, list(self.pattern.get(pad.name, [0] * STEPS)))
                           for pad in pads)
        self.SetSample(pads, pattern, mono)
        self.grab = grab

    # RT909's slots: a pad each (its id its name), in their order; any sound from any kit
    # in any of them, added, taken away, moved, renamed

    def GetSlotKind(self, name):
        pad = self.pads.get(name)
        voice = pad.voice if pad is not None and pad.voice is not None else {}
        return voice.get('kind') or (name if name in PAD_TYPES else 'kick')

    def SetSlotSound(self, name, kit, kind):
        # a slot's sound (a kit's kick, its snare...), its label kept when renamed, its
        # choke kept
        if kit not in KITS or kind not in PAD_TYPES or name not in self.pads:
            return
        old = self.pads[name]
        pad = make_kit_pad(kind, kit, name)
        if old.label != self.GetSlotKind(name).upper():
            pad.label = old.label
        pad.choke = old.choke if self.GetSlotKind(name) == kind else pad.choke
        with self.lock:
            self.pads[name] = pad

    def SetPadKit(self, name, kit):
        # one slot's sound from another kit (an 808's kick under a 909's snare)
        self.SetSlotSound(name, kit, self.GetSlotKind(name))

    def SetKit(self, kit):
        # every slot's sound from a kit, each its own sound, the pattern kept
        if kit in KITS:
            for name in list(self.pads):
                self.SetSlotSound(name, kit, self.GetSlotKind(name))
            self.kit = kit

    def AddSlot(self, kind='kick', kit='909'):
        if len(self.pads) >= SLOTS_MOST or kind not in PAD_TYPES:
            return None
        number = 1
        while 'slot %d' % number in self.pads:
            number += 1
        name = 'slot %d' % number
        pad = make_kit_pad(kind, kit, name)
        with self.lock:
            self.pads[name] = pad
            self.pattern[name] = [0] * STEPS
        return name

    def RemoveSlot(self, name):
        with self.lock:
            self.pads.pop(name, None)
            self.pattern.pop(name, None)
            self.muted.discard(name)
            self.soloed.discard(name)

    def MoveSlot(self, name, index):
        # (its place among them: the pads' and the pattern's order, the rows')
        names = [n for n in self.pads if n != name]
        if name not in self.pads:
            return
        names.insert(min(max(index, 0), len(names)), name)
        with self.lock:
            self.pads = dict((n, self.pads[n]) for n in names)
            self.pattern = dict((n, self.pattern.get(n, [0] * STEPS)) for n in names)

    def RenameSlot(self, name, label):
        pad = self.pads.get(name)
        if pad is not None and label.strip():
            pad.label = label.strip()[:12].upper()

    def SetSlotChoke(self, name, group):
        pad = self.pads.get(name)
        if pad is not None:
            pad.choke = group if group in CHOKE_GROUPS else None

    def Start(self):
        # from the next sixteenth (TickLocked)
        with self.lock:
            self.armed = True
            self.next_step = None

    def Stop(self):
        # its hits already put in its mixer (LOOKAHEAD ahead) cut too: heard 0.25 s after
        # STOP, they were
        with self.lock:
            self.armed = False
            self.next_step = None
            for stream in self.pending:
                pybass.BASS_StreamFree(stream)
            self.pending.clear()

    def GetLead(self):
        # seconds the mixer has decoded beyond what is heard of it (its hits put in that
        # far ahead of now): heard where it is in its bus (out: a splitter, with sends)
        if not self.handle:
            return 0.0
        decoded = pybass.BASS_ChannelGetPosition(self.handle, pybass.BASS_POS_BYTE)
        heard = mix.BASS_Mixer_ChannelGetPosition(getattr(self, 'out', 0) or self.handle,
                                                  pybass.BASS_POS_BYTE)
        if heard in (-1, 0xFFFFFFFFFFFFFFFF):
            return 0.0
        return max(pybass.BASS_ChannelBytes2Seconds(self.handle, decoded - heard), 0.0)

    def Tick(self):
        with self.lock:
            self.TickLocked()

    def TickLocked(self):
        state = self.clock() if self.armed and self.handle else None
        if not state or state.get('bpm', 0) <= 0:
            self.next_step = None
            return
        rate = max(state.get('rate', 1.0), 0.01)
        position = self.Steady(state['position'], rate)
        step = 60.0 / state['bpm'] / 4.0
        anchor = state.get('anchor', 0.0)
        now = (position - anchor) / step
        # the first tick or a jump (a seek, SHORT's cut): on from the next step, the
        # pattern where the bar is
        if self.next_step is None or self.last is None\
                or abs(position - self.last) > 1.0:
            self.next_step = int(math.ceil(now - 1e-6))
        self.last = position
        lead = self.GetLead()
        horizon = position + LOOKAHEAD * rate
        # the off sixteenths later by the swing (their pair's share)
        swing = (min(max(state.get('swing', 0.5), 0.5), 0.75) - 0.5) * 2.0 * step
        # a grabbed bar's (PS1200's) speed: the tempo now on the tempo it was grabbed at
        # (the deck's rate when it plays, the global tempo's alone); at its own while the
        # deck played faster, a slice drifted off the song through its length (a flanger)
        grab = getattr(self, 'grab', None)
        self.speed = state['bpm'] * rate / grab['bpm'] if grab and grab.get('bpm') else 1.0
        while anchor + self.next_step * step < horizon:
            due = anchor + self.next_step * step + (swing if self.next_step % 2 else 0.0)
            # real seconds from now (the song's at its playing speed), less what the mixer
            # has decoded ahead
            delay = (due - position) / rate - lead
            if delay >= 0:
                self.PlayStep(self.next_step % self.GetLength(), delay, step / rate)
            self.next_step += 1

    def Steady(self, read, rate):
        now = time.perf_counter()
        seen = read - rate * now
        if self.offset is None or abs(seen - self.offset) > CLOCK_JUMP\
                or rate != getattr(self, 'offset_rate', rate):
            # first, a jump (a seek, a cut) or a new speed: taken as read
            self.offset = seen
        else:
            self.offset += (seen - self.offset) * CLOCK_EASE
        self.offset_rate = rate
        return self.offset + rate * now

    def GetLength(self):
        # its pattern's steps (a bar's; a synth's, its bars')
        return STEPS

    def IsHeard(self, name):
        if name in self.muted:
            return False
        return not self.soloed or name in self.soloed

    def PlayStep(self, index, delay, step=None):
        speed = getattr(self, 'speed', 1.0) or 1.0
        for name, steps in self.pattern.items():
            velocity = steps[index] if index < len(steps) else 0
            pad = self.pads.get(name)
            if velocity and pad is not None and self.IsHeard(name):
                # (a slice from where it was in the song: its lead before its step)
                start = delay - pad.lead / speed
                cut = self.GetCut(name, index) if step else None
                if cut is not None:
                    ahead, following = cut
                    nxt = self.pads.get(following)
                    # cut where the next one starts (its own lead before its step)
                    cut = ahead * step - ((nxt.lead if nxt is not None else 0.0)
                                          - pad.lead) / speed
                elif step and self.grab is not None and not self.mono:
                    # a slice not mono: its own sixteenth only (its tail, past it, is the
                    # next slices' sound: rung over them, a little off, it flanged)
                    cut = step + pad.lead / speed
                self.Hit(pad, velocity, max(start, 0.0), cut)

    def GetChoke(self, name):
        if self.mono:
            return 'mono'
        pad = self.pads.get(name)
        return pad.choke if self.kit is not None and pad is not None else None

    def GetCut(self, name, index):
        # steps till the next hit of its choke group (its sound cut there), None: not cut
        group = self.GetChoke(name)
        if group is None:
            return None
        names = [n for n in self.pattern if self.GetChoke(n) == group]
        length = self.GetLength()
        for ahead in range(1, length + 1):
            k = (index + ahead) % length
            hits = [n for n in names if self.pattern[n][k]]
            if hits:
                return ahead, hits[0]
        return None

    def Hit(self, pad, velocity, delay=0.0, cut=None):
        stream = pybass.BASS_StreamCreate(
            RATE, CHANS, pybass.BASS_SAMPLE_FLOAT | pybass.BASS_STREAM_DECODE,
            STREAMPROC_PUSH, None)
        if not stream:
            return False
        data = pad.data
        pitch = pad.pitch * 2.0 ** (self.shift / 12.0) * (getattr(self, 'speed', 1.0) or 1.0)
        if cut is not None and cut * pitch * RATE < len(data):
            # choked: its sound cut where the next of its group comes (seconds of its own
            # data: its pitch plays it faster), faded out over CHOKE_FADE from there (the
            # next one fading in over it); on a copy (a mixer envelope,
            # BASS_Mixer_ChannelSetEnvelope, hung bassmix's decoding)
            end = max(int(cut * pitch * RATE), 1)
            fade = int(CHOKE_FADE * RATE)
            data = data[:end + fade].copy()
            fade = len(data) - end
            if fade > 0:
                data[end:] *= numpy.linspace(1.0, 0.0, fade, dtype=numpy.float32)[:, None]
        pybass.BASS_StreamPutData(stream, data.ctypes.data_as(ctypes.c_void_p),
                                  data.nbytes | pybass.BASS_STREAMPROC_END)
        pybass.BASS_ChannelSetAttribute(stream, pybass.BASS_ATTRIB_VOL, float(velocity))
        if pitch != 1.0:
            pybass.BASS_ChannelSetAttribute(stream, pybass.BASS_ATTRIB_FREQ, RATE * pitch)
        start = pybass.BASS_ChannelSeconds2Bytes(self.handle, max(delay, 0.0))
        # where in the mixer it lands (seconds decoded): its timing told (tests)
        self.history.append(pybass.BASS_ChannelBytes2Seconds(
            self.handle, pybass.BASS_ChannelGetPosition(self.handle, pybass.BASS_POS_BYTE))
            + max(delay, 0.0))
        del self.history[:-256]
        self.pending.append(stream)
        return bool(mix.BASS_Mixer_StreamAddChannelEx(
            self.handle, stream, pybass.BASS_STREAM_AUTOFREE | mix.BASS_MIXER_NORAMPIN,
            start, 0))

    def RenderBar(self, bpm, swing=0.5, bars=2):
        '''its pattern as it sounds (mono, the mixer's rate), bars of it at bpm: its pads
        where their steps are (swung), at their velocities, their pitch, choked as they
        are, its muted ones out; PS1200's grab of a machine (no recording: exact, at once)'''
        with self.lock:
            step = 60.0 / bpm / 4.0
            late = (min(max(swing, 0.5), 0.75) - 0.5) * 2.0 * step
            count = STEPS * bars
            length = self.GetLength()
            out = numpy.zeros(int((count + SLICE_TAIL) * step * RATE) + RATE)
            for k in range(count):
                index = k % length
                at = int((k * step + (late if k % 2 else 0.0)) * RATE)
                for name, steps in self.pattern.items():
                    velocity = steps[index] if index < len(steps) else 0
                    pad = self.pads.get(name)
                    if not velocity or pad is None or not self.IsHeard(name):
                        continue
                    sound = pad.data[:, 0].astype(numpy.float64)
                    pitch = pad.pitch * 2.0 ** (self.shift / 12.0)
                    if pitch != 1.0:
                        sound = numpy.interp(numpy.arange(0, len(sound) - 1, pitch),
                                             numpy.arange(len(sound)), sound)
                    cut = self.GetCut(name, index)
                    if cut is not None:
                        end = int(cut[0] * step * RATE)
                        fade = int(CHOKE_FADE * RATE)
                        sound = sound[:end + fade].copy()
                        if len(sound) > end:
                            sound[end:] *= numpy.linspace(1.0, 0.0, len(sound) - end)
                    room = min(len(sound), len(out) - at)
                    if room > 0:
                        out[at:at + room] += sound[:room] * velocity
            return out

    # presets (presets.py): its sound and its pattern apart, as data a file keeps

    def GetSoundData(self):
        spec = self.GetSpec()
        if self.kit is not None:
            # RT909's: its slots, their voices, labels and chokes, in their order
            return dict(kind='rt909', slots=[
                dict(label=kept.get('label'), choke=kept.get('choke'), gain=kept.get('gain'),
                     voice=kept.get('voice')) for kept in spec['pads'].values()])
        # PS1200's: its bar (where from), its slices' settings, its pitch, mono, crunch
        return dict(kind='ps1200', grab=spec['grab'], grab_from=spec['grab_from'],
                    shift=spec['shift'], poly=spec['poly'], pads=spec['pads'])

    def SetSoundData(self, data):
        if self.kit is not None:
            if data.get('kit') in KITS:
                slots = [dict(voice=make_kit_pad(kind, data['kit']).voice)
                         for kind in PAD_NAMES]
            else:
                slots = data.get('slots') or []
            # (the rows' steps kept a row each, in order: a kit under the pattern)
            rows = list(self.pattern.values())
            names = list(self.pads)
            pads, pattern = [], {}
            for k, slot in enumerate(slots[:SLOTS_MOST]):
                voice = dict(slot.get('voice') or {})
                kind = voice.get('kind', 'kick')
                kit = voice.get('kit') if voice.get('kit') in KITS else '909'
                name = names[k] if k < len(names) else 'slot %d' % (k + 1)
                while name in pattern:
                    name += "'"
                pad = make_kit_pad(kind if kind in PAD_TYPES else 'kick', kit, name)
                if voice:
                    pad.SetVoice(**voice)
                if slot.get('label'):
                    pad.label = slot['label']
                if 'choke' in slot:
                    pad.choke = slot['choke']
                if slot.get('gain') is not None:
                    pad.gain = slot['gain']
                    pad.Render()
                pads.append(pad)
                pattern[name] = list(rows[k]) if k < len(rows) else [0] * STEPS
            with self.lock:
                self.pads = dict((pad.name, pad) for pad in pads)
                self.pattern = pattern
                self.muted &= set(self.pads)
                self.soloed &= set(self.pads)
            return
        spec = dict(data)
        spec.pop('pattern', None)
        pattern = dict(self.pattern)
        self.SetSpec(spec)
        with self.lock:
            if set(pattern) == set(self.pads):
                self.pattern = pattern

    def GetPatternData(self):
        if self.kit is not None:
            return dict(kind='rt909', rows=[
                dict(kind=self.GetSlotKind(name), steps=list(steps))
                for name, steps in self.pattern.items()])
        # PS1200's: the slice each step plays (1 to 16, 0 none)
        order = []
        for k in range(STEPS):
            hits = [name for name, steps in self.pattern.items() if steps[k]]
            order.append(int(hits[0].split()[-1]) if hits else 0)
        return dict(kind='ps1200', order=order)

    def SetPatternData(self, data):
        if self.kit is not None:
            # a row to the first slot of its sound not yet taken (a slot added for it
            # when there is none and there is room), the others' steps cleared
            taken = {}
            for row in data.get('rows') or []:
                kind = row.get('kind', 'kick')
                name = next((n for n in self.pads if n not in taken
                             and self.GetSlotKind(n) == kind), None)
                if name is None:
                    kit = next(iter(self.pads.values())).voice.get('kit', '909')\
                        if self.pads else '909'
                    name = self.AddSlot(kind if kind in PAD_TYPES else 'kick', kit)
                if name is not None:
                    taken[name] = (list(row.get('steps') or []) + [0] * STEPS)[:STEPS]
            with self.lock:
                for name in self.pattern:
                    self.pattern[name] = taken.get(name, [0] * STEPS)
            return
        order = (list(data.get('order') or []) + [0] * STEPS)[:STEPS]
        with self.lock:
            for name in self.pattern:
                number = int(name.split()[-1])
                self.pattern[name] = [1.0 if order[k] == number else 0 for k in range(STEPS)]

    PAD_SETTINGS = ('gain', 'pitch', 'crunched', 'reverse', 'decay', 'filter', 'cutoff',
                    'resonance', 'slope', 'label', 'choke')

    def GetSpec(self):
        '''its settings, kept (AudioControl.KeepInstruments): its pattern, its kit and its
        pads' (a voice's settings, a slice's), the bar it grabbed; its sounds are made
        again from them (SetSpec)'''
        with self.lock:
            pads = {}
            for name, pad in self.pads.items():
                pads[name] = dict((key, getattr(pad, key)) for key in self.PAD_SETTINGS)
                if pad.voice is not None:
                    pads[name]['voice'] = dict(pad.voice)
            return dict(kind=self.KIND, kit=self.kit, shift=self.shift, poly=not self.mono,
                        grab_from=self.grab_from, sound_name=self.sound_name,
                        pattern_name=self.pattern_name,
                        grab=self.grab, pads=pads, muted=sorted(self.muted),
                        soloed=sorted(self.soloed),
                        pattern=dict((name, list(steps))
                                     for name, steps in self.pattern.items()))

    def SetSpec(self, spec):
        if self.kit is not None and spec.get('pads'):
            # its slots as kept, in their order (each its voice; a kept one from before
            # slots: its name its sound)
            pads = []
            for name, kept in spec['pads'].items():
                voice = dict(kept.get('voice') or {})
                kind = voice.get('kind') or (name if name in PAD_TYPES else 'kick')
                kit = voice.get('kit', '909') if voice.get('kit') in KITS else '909'
                pad = make_kit_pad(kind, kit, name)
                if voice:
                    voice.setdefault('kind', kind)
                    pad.SetVoice(**voice)
                pads.append(pad)
            self.SetPads(pads[:SLOTS_MOST])
            self.kit = spec.get('kit') if spec.get('kit') in KITS else '909'
        grab = spec.get('grab')
        if grab and self.kit is None:
            pads, pattern, mono = grab_slices(grab['path'],
                                              grab['start'] + grab.get('offset', 0.0),
                                              grab['bpm'], grab.get('bars', 1))
            if pads is not None:
                self.SetSample(pads, pattern, mono)
                self.grab = grab
        with self.lock:
            for name, kept in spec.get('pads', {}).items():
                pad = self.pads.get(name)
                if pad is None:
                    continue
                for key in self.PAD_SETTINGS:
                    if key in kept:
                        setattr(pad, key, kept[key])
                # (kept before the filter's kinds: a cutoff a low-pass's)
                if 'filter' not in kept and kept.get('cutoff') is not None:
                    pad.filter = 'lp'
                pad.Render()
            if self.kit is None:
                # (a slice's pitch kept off a semitone before it snapped: snapped)
                for pad in self.pads.values():
                    pad.pitch = 2.0 ** (round(12.0 * math.log2(max(pad.pitch, 1e-3))) / 12.0)
            pattern = spec.get('pattern')
            if pattern:
                self.pattern = dict((name, (list(steps) + [0] * STEPS)[:STEPS])
                                    for name, steps in pattern.items() if name in self.pads)
            self.shift = spec.get('shift', self.shift)
            self.grab_from = spec.get('grab_from', self.grab_from)
            self.sound_name = spec.get('sound_name', self.sound_name)
            self.pattern_name = spec.get('pattern_name', self.pattern_name)
            # (kept as 'poly': settings from before kept 'mono' off by default, choppy)
            self.mono = not spec.get('poly', not self.mono)
            self.muted = set(spec.get('muted') or ()) & set(self.pads)
            self.soloed = set(spec.get('soloed') or ()) & set(self.pads)


# the bass deck: a TB-303's spirit (a saw through a resonant low-pass, its cutoff falling
# on each note, accented ones brighter and louder), its line in the song's key. each note
# rendered once (numpy) and played as a pad: no synthesis while it plays

NOTE_NAMES = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B')
# a line a bar: (degree of the scale, accent) a step, None a rest; minor and major scales
# in semitones
MINOR = (0, 2, 3, 5, 7, 8, 10)
MAJOR = (0, 2, 4, 5, 7, 9, 11)
BASS_LINE = ((0, True), (0, False), (7, False), (0, False), None, (0, True), (2, False),
             (0, False), (0, True), None, (4, False), (0, False), (5, True), (4, False),
             (2, False), (1, False))
BASS_OCTAVE = 36  # C2


def parse_key(key):
    '''(root semitone 0-11, minor) of a key as the analysis tells it ('Am', 'C#m', 'F',
    'Gb'...), (9, True) (A minor) when it can not be read'''
    text = ('%s' % (key or '')).strip()
    if not text:
        return 9, True
    minor = text.endswith('m') and not text.endswith('maj')
    name = text[:-1] if minor else text
    name = name.replace('b', '#') if len(name) > 1 and name[1] == 'b' else name
    flats = {'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'}
    name = flats.get(text[:2], name)
    if name not in NOTE_NAMES:
        return 9, True
    return NOTE_NAMES.index(name), minor


# BT303's knobs: (key, label, low, high, log), as RT909's voices' (to_knob, from_knob):
# the filter's cutoff (its floor), resonance, how far its envelope opens it (Hz above the
# floor) and how fast that falls, the notes' decay, an accent's lift
BASS_KNOBS = (('cutoff', 'CUTOFF', 60.0, 2000.0, True), ('resonance', 'RES', 0.0, 0.95, False),
              ('env', 'ENV MOD', 0.0, 6000.0, False), ('env_decay', 'ENV DEC', 0.02, 1.0, True),
              ('decay', 'DECAY', 0.05, 1.0, True), ('accent', 'ACCENT', 0.0, 1.0, False))
BASS_TONE = dict(cutoff=180.0, resonance=0.7, env=1320.0, env_decay=0.09, decay=0.25,
                 accent=0.5)
# its line moved by these at most: octaves, semitones
BASS_OCTAVES = (-2, -1, 0, 1, 2)
BASS_TRANSPOSE = tuple(range(-12, 13))


# a slide's glide to its next note (seconds: the time constant of its pitch's move)
SLIDE_TIME = 0.03


def render_note(midi, length, accent=False, tone=None, glide=(), step=None):
    '''a saw (its rate's own, bandlimited enough by the filter after it) through a 2 pole
    resonant low-pass whose cutoff falls from bright to dark over the note. glide: the
    notes it slides on to (a step each, held: not struck again), its pitch moving to each
    as it comes (a 303's slide)'''
    tone = dict(BASS_TONE, **(tone or {}))
    n = int((length + (step or 0.0) * len(glide)) * RATE)
    target = numpy.full(n, float(midi))
    for k, after in enumerate(glide):
        target[int((k + 1) * step * RATE):] = after
    if len(glide):
        ease = 1.0 - math.exp(-1.0 / (SLIDE_TIME * RATE))
        target = signal.lfilter([ease], [1.0, ease - 1.0], target - midi) + midi
    freq = 440.0 * 2 ** ((target - 69) / 12.0)
    phase = numpy.cumsum(freq) / RATE % 1.0
    saw = 2.0 * phase - 1.0
    lift = tone['accent'] if accent else 0.0
    top = tone['cutoff'] + tone['env'] * (1.0 + lift)
    cutoff = tone['cutoff'] + (top - tone['cutoff']) * numpy.exp(
        -numpy.arange(n) / (tone['env_decay'] * RATE))
    resonance = min(tone['resonance'] + 0.25 * lift, 0.97)
    out = numpy.empty(n)
    low = band = 0.0
    damp = 2.0 * (1.0 - resonance)
    for i in range(n):
        f = 2.0 * math.sin(math.pi * min(cutoff[i], RATE / 6.0) / RATE)
        high = saw[i] - low - damp * band
        band += f * high
        low += f * band
        out[i] = low
    amp = envelope(n, tone['decay']) * (0.7 + 0.3 * lift / max(tone['accent'], 1e-6)
                                         if accent else 0.7)
    tail = min(int(0.004 * RATE), n)
    amp[-tail:] *= numpy.linspace(1, 0, tail)
    peak = max(numpy.abs(out).max(), 1e-6)
    return out / peak * amp * 0.8


def read_note(note):
    # (degree, accent, slide) of a line's step ((degree, accent) before slides), None a rest
    if note is None:
        return None
    return int(note[0]), bool(note[1]), bool(note[2]) if len(note) > 2 else False


def degree_to_midi(degree, root, scale):
    return BASS_OCTAVE + root + scale[degree % 7] + 12 * (degree // 7)


def make_bass(key, bpm, line=BASS_LINE, tone=None, shift=0):
    '''(pads, pattern) of the line in the key: a pad a note it plays (rendered for a step's
    length), the pattern its steps; a note sliding (its slide on, a note after it) held
    into the next with its pitch gliding there, that one not struck: a pad of its own.
    shift: every note moved these semitones (its octave's and its transpose's)'''
    COUNTS['make_bass'] += 1
    root, minor = parse_key(key)
    scale = MINOR if minor else MAJOR
    step = 60.0 / max(bpm, 40.0) / 4.0
    notes = [read_note(note) for note in (list(line) + [None] * STEPS)[:STEPS]]
    pads, pattern = {}, {}
    k = 0
    while k < STEPS:
        if notes[k] is None:
            k += 1
            continue
        degree, accent, slide = notes[k]
        midi = degree_to_midi(degree, root, scale) + shift
        glide, j = [], k
        while notes[j][2] and j + 1 < STEPS and notes[j + 1] is not None:
            j += 1
            glide.append(degree_to_midi(notes[j][0], root, scale) + shift)
        if glide:
            name = 's%d' % k
            pads[name] = Pad(name, render_note(midi, step * 0.95, accent, tone, glide, step))
        else:
            name = 'n%d%s' % (midi, 'a' if accent else '')
            if name not in pads:
                pads[name] = Pad(name, render_note(midi, step * 0.95, accent, tone))
        pattern.setdefault(name, [0] * STEPS)[k] = 1.0
        k = j + 1
    return list(pads.values()), pattern


class BassSource(SamplerSource):

    '''the bass deck: a sampler whose pads are its line's notes, made again when the
    song's key or tempo changes (Follow)'''

    KIND = 'bass'

    def __init__(self, clock, key='Am', bpm=120.0, line=BASS_LINE):
        self.key, self.bpm = key, bpm
        self.line = tuple(read_note(note) for note in line)
        self.tone = dict(BASS_TONE)
        # every note moved: octaves (BASS_OCTAVES), semitones (BASS_TRANSPOSE)
        self.octave = 0
        self.transpose = 0
        pads, pattern = make_bass(key, bpm, line, self.tone)
        SamplerSource.__init__(self, clock, pads, pattern)

    def GetShift(self):
        return 12 * self.octave + self.transpose

    def Render(self):
        pads, pattern = make_bass(self.key, self.bpm, self.line, self.tone, self.GetShift())
        self.SetPads(pads, pattern)

    def SetPitch(self, octave=None, transpose=None):
        # its notes an octave or a semitone up or down (the line as it is)
        if octave is not None:
            self.octave = min(max(int(octave), BASS_OCTAVES[0]), BASS_OCTAVES[-1])
        if transpose is not None:
            self.transpose = min(max(int(transpose), BASS_TRANSPOSE[0]), BASS_TRANSPOSE[-1])
        self.Render()

    def ShiftLine(self, steps):
        # its line moved steps later (earlier: below 0), round the bar
        steps %= STEPS
        line = (list(self.line) + [None] * STEPS)[:STEPS]
        self.SetLine(line[-steps:] + line[:-steps] if steps else line)

    def SetLine(self, line):
        # a line of its own ((degree, accent, slide) or None a step), its notes rendered
        self.line = tuple(read_note(note) for note in line)[:STEPS]
        self.Render()

    def SetTone(self, **values):
        # its knobs (BASS_KNOBS): its notes rendered again
        self.tone.update(values)
        self.Render()

    def Follow(self, key, bpm):
        # the song's key and tempo (a new song): the notes rendered again
        if (key, round(bpm, 1)) == (self.key, round(self.bpm, 1)) or bpm <= 0:
            return False
        self.key, self.bpm = key, bpm
        self.Render()
        return True

    def GetSpec(self):
        return dict(kind=self.KIND, key=self.key, bpm=self.bpm, tone=dict(self.tone),
                    octave=self.octave, transpose=self.transpose,
                    line=[list(note) if note is not None else None for note in self.line],
                    sound_name=self.sound_name, pattern_name=self.pattern_name)

    def GetSoundData(self):
        return dict(kind='bt303', tone=dict(self.tone))

    def SetSoundData(self, data):
        self.SetTone(**(data.get('tone') or {}))

    def GetPatternData(self):
        return dict(kind='bt303', line=[list(note) if note is not None else None
                                        for note in self.line])

    def SetPatternData(self, data):
        if data.get('line'):
            self.SetLine(data['line'])

    def SetSpec(self, spec):
        self.sound_name = spec.get('sound_name')
        self.pattern_name = spec.get('pattern_name')
        self.tone.update(spec.get('tone') or {})
        self.octave = spec.get('octave', 0)
        self.transpose = spec.get('transpose', 0)
        if spec.get('line'):
            self.SetLine(spec['line'])
        else:
            self.SetTone()


# the synths (SY-4, VR-1): notes on a piano roll ([midi, start step, steps held, velocity]
# over its bars), each group of notes starting together rendered (synth.render_group) as a
# pad of its own, played on its step; made again when its notes, its patch or the tempo
# change (in a thread of its own: a knob turned, the sound before kept till the new one
# is made)

SYNTH_BARS = (1, 2, 4)
# made again when the tempo moves this far (BPM: a tempo fader's every move did)
SYNTH_TEMPO_MOVE = 0.5
# a chord's root: this octave's (C3) and the key's root over it
CHORD_OCTAVE = 48
LEAD_OCTAVE = 60


def progression_notes(chords, key, octave=CHORD_OCTAVE):
    '''a progression ([degree, chord kind, start, steps held, octaves up], the key's own
    degrees) as notes in a key'''
    root, minor = parse_key(key)
    scale = MINOR if minor else MAJOR
    notes = []
    for degree, kind, start, length, up in chords:
        base = octave + root + scale[degree % 7] + 12 * (degree // 7) + 12 * up
        for midi in synth.chord_notes(kind, base, root, scale):
            notes.append([midi, start, length, 0.85])
    return notes


def line_notes(line, key, octave=LEAD_OCTAVE):
    # a line ([degree, start, steps held, accent]) as notes in a key
    root, minor = parse_key(key)
    scale = MINOR if minor else MAJOR
    return [[octave + root + scale[degree % 7] + 12 * (degree // 7), start, length,
             1.0 if accent else 0.75] for degree, start, length, accent in line]


class NoteSource(SamplerSource):

    KIND = 'notes'

    def __init__(self, clock, machine='sy4', key='Am', bpm=120.0):
        self.machine = machine
        self.key, self.bpm = key, bpm
        self.patch = synth.merge_patch(None, synth.FIRST_PATCHES.get(machine))
        self.bars = 4 if machine == 'sy4' else 1
        self.notes = []
        self.render_flags = threading.Lock()
        self.rendering = False
        self.dirty = False
        SamplerSource.__init__(self, clock, [], {})
        self.kit = None
        if machine == 'sy4':
            self.notes = progression_notes(
                [[0, 'triad', 0, 16, 0], [5, 'triad', 16, 16, 0], [2, 'triad', 32, 16, 0],
                 [6, 'triad', 48, 16, 0]], key)
        else:
            self.notes = line_notes([[0, k, 1, k % 4 == 0] for k in range(0, 16, 2)], key,
                                    LEAD_OCTAVE - 24)
        self.Render(wait=True)

    def GetLength(self):
        return STEPS * self.bars

    # its notes, its patch

    def SetNotes(self, notes):
        length = self.GetLength()
        kept = []
        for note in notes:
            midi, start, held, velocity = (list(note) + [0.85])[:4]
            if 0 <= int(start) < length:
                kept.append([min(max(int(midi), 12), 120), int(start),
                             min(max(int(held), 1), length), min(max(float(velocity), 0.05), 1.0)])
        self.notes = sorted(kept, key=lambda note: (note[1], note[0]))
        self.Render()

    def SetBars(self, bars):
        if bars in SYNTH_BARS:
            self.bars = bars
            self.SetNotes([note for note in self.notes if note[1] < self.GetLength()])

    def MoveNotes(self, semis=0, steps=0):
        # every note moved: semitones (an octave's 12), steps later (round its bars)
        length = self.GetLength()
        self.SetNotes([[midi + semis, (start + steps) % length, held, velocity]
                       for midi, start, held, velocity in self.notes])

    def GetParam(self, path):
        place = self.patch
        for key in path:
            place = place[key]
        return place

    def SetParam(self, path, value):
        place = self.patch
        for key in path[:-1]:
            place = place[key]
        place[path[-1]] = value
        self.Render()

    def Follow(self, key, bpm):
        # the song's tempo: its notes made again (its key: the chords stamped in it, a
        # preset's progression put in it)
        self.key = key
        if bpm <= 0 or abs(bpm - self.bpm) < SYNTH_TEMPO_MOVE:
            return False
        self.bpm = bpm
        self.Render()
        return True

    # made

    def Render(self, wait=False):
        '''its pads made again from its notes and patch: in a thread (a render running: once
        more after it, with what is then); wait: here, at once'''
        if wait:
            self.TakeRender(*self.MakePads())
            return
        with self.render_flags:
            if self.rendering:
                self.dirty = True
                return
            self.rendering = True
        threading.Thread(target=self.RenderLoop, daemon=True).start()

    def RenderLoop(self):
        while True:
            try:
                self.TakeRender(*self.MakePads())
            except Exception:
                pass
            with self.render_flags:
                if not self.dirty:
                    self.rendering = False
                    return
                self.dirty = False

    def TakeRender(self, pads, pattern, mono):
        with self.lock:
            self.pads = dict((pad.name, pad) for pad in pads)
            self.pattern = pattern
            self.mono = mono

    def MakePads(self):
        patch = copy.deepcopy(self.patch)
        notes = [list(note) for note in self.notes]
        step = 60.0 / max(self.bpm, 40.0) / 4.0
        length = self.GetLength()
        mono = bool(patch.get('mono'))
        groups = collections.OrderedDict()
        for midi, start, held, velocity in notes:
            groups.setdefault(start, []).append((midi, held, velocity))
        pads, pattern = [], {}
        before = None
        for start, group in groups.items():
            if mono:
                # (one voice: its highest note, slid to from the one before)
                group = [max(group)]
            name = 'g%d' % start
            sound = synth.render_group(group, patch, step, at=(start % STEPS) * step,
                                       glide_from=before if mono else None, seed=start)
            before = group[0][0]
            pads.append(Pad(name, sound))
            steps = [0] * length
            steps[start] = 1.0
            pattern[name] = steps
        return pads, pattern, mono

    def Audition(self, midi, held=2, velocity=0.85):
        # a note heard now (the piano roll's keys), as its patch makes it
        step = 60.0 / max(self.bpm, 40.0) / 4.0
        sound = synth.render_group([(midi, held, velocity)], copy.deepcopy(self.patch), step)
        self.Hit(Pad('audition', sound), 1.0)

    # kept, presets

    def GetSpec(self):
        return dict(kind=self.KIND, machine=self.machine, patch=copy.deepcopy(self.patch),
                    notes=[list(note) for note in self.notes], bars=self.bars,
                    sound_name=self.sound_name, pattern_name=self.pattern_name)

    def SetSpec(self, spec):
        self.sound_name = spec.get('sound_name')
        self.pattern_name = spec.get('pattern_name')
        self.patch = synth.merge_patch(None, spec.get('patch'))
        self.bars = spec.get('bars', self.bars) if spec.get('bars') in SYNTH_BARS else self.bars
        if spec.get('notes') is not None:
            self.SetNotes(spec['notes'])
        else:
            self.Render()

    def GetSoundData(self):
        return dict(kind=self.machine, patch=copy.deepcopy(self.patch))

    def SetSoundData(self, data):
        self.patch = synth.merge_patch(None, data.get('patch'))
        self.Render()

    def GetPatternData(self):
        return dict(kind=self.machine, bars=self.bars,
                    notes=[list(note) for note in self.notes])

    def SetPatternData(self, data):
        # a progression or a line (a built-in's: in the song's key), or notes
        if data.get('bars') in SYNTH_BARS:
            self.bars = data['bars']
        if data.get('chords'):
            self.SetNotes(progression_notes(data['chords'], self.key,
                                            data.get('octave', CHORD_OCTAVE)))
        elif data.get('line'):
            self.SetNotes(line_notes(data['line'], self.key, data.get('octave', LEAD_OCTAVE)))
        elif data.get('notes') is not None:
            self.SetNotes(data['notes'])


# MP-60: a pad sampler in an MPC's spirit: sixteen pads, each a sound from anywhere (a
# beat of the song playing, sampled where it is; a file; a kit's voice, its first ones),
# each its own steps (the picked pad's programmed; the others' seen lit), poly, swung

PAD_COUNT = 16
# a pad's sound sampled from the deck: this many beats of it at most
SAMPLE_BEATS = (1, 2, 4)
# the first pads: the 909's and the 808's (ready to play)
FIRST_PAD_SOUNDS = (('kick', '909'), ('snare', '909'), ('clap', '909'), ('hat', '909'),
                    ('open hat', '909'), ('tom', '909'), ('rim', '909'), ('cowbell', '808'),
                    ('kick', '808'), ('snare', '808'), ('clap', '808'), ('hat', '808'),
                    ('open hat', '808'), ('tom', '808'), ('rim', '808'), ('cymbal', '909'))


def pad_name(number):
    return 'pad %d' % number


class PadSource(SamplerSource):

    KIND = 'pads'
    PAD_SETTINGS = ('gain', 'pitch', 'reverse', 'decay', 'label')

    def __init__(self, clock):
        pads = []
        for k, (kind, kit) in enumerate(FIRST_PAD_SOUNDS):
            pad = make_kit_pad(kind, kit, pad_name(k + 1))
            pad.label = ('%s %s' % (kit, kind)).upper()
            pad.choke = None
            pads.append(pad)
        pattern = dict((pad.name, [0] * STEPS) for pad in pads)
        SamplerSource.__init__(self, clock, pads, pattern)
        self.kit = None
        self.mono = False
        # where each pad's sound came from: ('voice', kind, kit) or ('file', path, start,
        # seconds)
        self.origins = dict((pad_name(k + 1), ('voice', kind, kit))
                            for k, (kind, kit) in enumerate(FIRST_PAD_SOUNDS))

    def LoadPad(self, name, path, start, seconds, label=None):
        '''a pad's sound from a file (seconds of it from start): its own settings kept;
        False when it does not open'''
        mono = read_mono(path, max(start, 0.0), seconds)
        if mono is None or not len(mono):
            return False
        fade = min(int(0.003 * RATE), len(mono) // 4)
        if fade:
            mono[-fade:] *= numpy.linspace(1, 0, fade)
        pad = Pad(name, mono)
        old = self.pads.get(name)
        if old is not None:
            pad.gain, pad.pitch, pad.reverse, pad.decay = old.gain, old.pitch, old.reverse,\
                old.decay
            pad.Render()
        pad.label = (label or os.path.splitext(os.path.basename(path))[0])[:24].upper()
        with self.lock:
            self.pads[name] = pad
        self.origins[name] = ('file', path, start, seconds)
        return True

    def SetPadSound(self, name, kind, kit):
        # a kit's voice on a pad
        pad = make_kit_pad(kind, kit, name)
        pad.label = ('%s %s' % (kit, kind)).upper()
        pad.choke = None
        with self.lock:
            self.pads[name] = pad
        self.origins[name] = ('voice', kind, kit)

    def SetPadSetting(self, name, **values):
        with self.lock:
            pad = self.pads.get(name)
            if pad is None:
                return
            if 'semis' in values:
                pad.pitch = 2.0 ** (round(values.pop('semis')) / 12.0)
            for key, value in values.items():
                setattr(pad, key, value)
            if pad.voice is not None and pad.reverse:
                pad.reverse = False
            pad.Render()

    # kept, presets

    def GetSpec(self):
        with self.lock:
            pads = dict((name, dict((key, getattr(pad, key)) for key in self.PAD_SETTINGS))
                        for name, pad in self.pads.items())
            return dict(kind=self.KIND, origins=dict((k, list(v)) for k, v in
                                                     self.origins.items()),
                        pads=pads, muted=sorted(self.muted), soloed=sorted(self.soloed),
                        sound_name=self.sound_name, pattern_name=self.pattern_name,
                        pattern=dict((name, list(steps))
                                     for name, steps in self.pattern.items()))

    def SetSpec(self, spec):
        self.SetSoundData(spec)
        self.SetPatternData(spec)
        self.muted = set(spec.get('muted') or [])
        self.soloed = set(spec.get('soloed') or [])
        self.sound_name = spec.get('sound_name')
        self.pattern_name = spec.get('pattern_name')

    def GetSoundData(self):
        spec = self.GetSpec()
        return dict(kind='mp60', origins=spec['origins'], pads=spec['pads'])

    def SetSoundData(self, data):
        for name, origin in (data.get('origins') or {}).items():
            if name not in self.pads:
                continue
            if origin and origin[0] == 'file':
                self.LoadPad(name, origin[1], origin[2], origin[3])
            elif origin and origin[0] == 'voice' and origin[1] in PAD_TYPES:
                self.SetPadSound(name, origin[1], origin[2] if origin[2] in KITS else '909')
        for name, kept in (data.get('pads') or {}).items():
            pad = self.pads.get(name)
            if pad is None:
                continue
            with self.lock:
                for key in self.PAD_SETTINGS:
                    if key in kept:
                        setattr(pad, key, kept[key])
                pad.Render()

    def GetPatternData(self):
        with self.lock:
            return dict(kind='mp60', steps=dict((name, list(steps))
                                                for name, steps in self.pattern.items()))

    def SetPatternData(self, data):
        steps = data.get('steps') or data.get('pattern') or {}
        with self.lock:
            for name in self.pads:
                row = steps.get(name)
                self.pattern[name] = (list(row) + [0] * STEPS)[:STEPS] if row else [0] * STEPS
