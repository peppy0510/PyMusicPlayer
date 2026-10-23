# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import math
import numpy

from scipy import signal


# the synths' engine (SY-4: a poly synth in Sylenth1's spirit; VR-1: a virtual analog in
# the Virus's): a group of notes starting together rendered at once as a stereo sound (the
# mixer's rate), played back as a pad (instruments.NoteSource). a patch: its oscillators
# (up to four, each its wave, octave, semitones, fine, unison voices and their detune, its
# level; FM from the one before it), two filters in a row (kind, slope, cutoff, resonance,
# drive, how far the mod envelope opens it), the amp and mod envelopes, an LFO (synced to
# the bar), the width of the unison and the level

RATE = 44100
WAVES = ('saw', 'square', 'tri', 'sine', 'noise', 'table')
FILTERS = (None, 'lp', 'hp', 'bp', 'notch')
SLOPES = (12, 24)
LFO_SHAPES = ('sine', 'tri', 'saw', 'square')
LFO_DESTS = ('cutoff', 'pitch', 'amp', 'pan')
# the LFO's rate: a cycle this many bars
LFO_RATES = (1 / 16.0, 1 / 8.0, 3 / 16.0, 1 / 4.0, 3 / 8.0, 1 / 2.0, 1.0, 2.0, 4.0)
LFO_RATE_NAMES = ('1/16', '1/8', '3/16', '1/4', '3/8', '1/2', '1 BAR', '2 BARS', '4 BARS')
# a unison's detune at its widest (cents, its outer voices'), the most voices
DETUNE_MOST = 60.0
VOICES_MOST = 9
# the filters' cutoff moved in blocks of this many samples (a coefficient each)
BLOCK = 64
BUTTERWORTH = (0.541, 1.307)


def make_osc(on=True, wave='saw', octave=0, semi=0, fine=0.0, voices=1, detune=0.3,
             level=0.7, shape=0.5, fm=0.0):
    # shape: a square's pulse width, a table's place (sine, tri, saw, square); fm: how far
    # the oscillator before it moves its phase
    return dict(on=on, wave=wave, octave=octave, semi=semi, fine=fine, voices=voices,
                detune=detune, level=level, shape=shape, fm=fm)


def make_filter(kind='lp', slope=24, cutoff=2400.0, res=0.2, drive=0.0, env=0.0):
    # env: octaves the mod envelope opens it at its top (below 0: closes it)
    return dict(kind=kind, slope=slope, cutoff=cutoff, res=res, drive=drive, env=env)


def make_patch(**values):
    patch = dict(
        osc=[make_osc(), make_osc(wave='saw', semi=0, voices=1, level=0.5, fine=7.0),
             make_osc(on=False), make_osc(on=False)],
        filters=[make_filter(), make_filter(kind=None)],
        amp=dict(a=0.005, d=0.3, s=0.8, r=0.25),
        mod=dict(a=0.005, d=0.4, s=0.2, r=0.3),
        lfo=dict(rate=6, shape='sine', dest='cutoff', depth=0.0),
        width=0.6, level=0.7, glide=0.0, mono=False)
    patch.update(values)
    return patch


def merge_patch(base, values):
    # a patch's settings over another (a preset's: its oscillators and filters by place)
    patch = make_patch()
    for key, value in (base or {}).items():
        patch[key] = value
    for key, value in (values or {}).items():
        if key in ('osc', 'filters') and isinstance(value, list):
            # (each given one whole from its maker's: a setting not given its first, not
            # the patch's before)
            kept = [dict(item) for item in patch[key]]
            make = make_osc if key == 'osc' else make_filter
            for k, item in enumerate(value[:len(kept)]):
                kept[k] = make(**dict(item or {}))
            patch[key] = kept
        elif key in ('amp', 'mod', 'lfo') and isinstance(value, dict):
            patch[key] = dict(patch[key], **value)
        else:
            patch[key] = value
    return patch


def midi_to_freq(midi):
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def poly_blep(t, dt):
    # the step's correction where a band-limited saw or square jumps (less aliasing); dt:
    # cycles a sample
    out = numpy.zeros_like(t)
    low = t < dt
    x = t[low] / dt
    out[low] = x + x - x * x - 1.0
    high = t > 1.0 - dt
    x = (t[high] - 1.0) / dt
    out[high] = x * x + x + x + 1.0
    return out


def oscillate(wave, phase, dt, shape=0.5, rng=None):
    '''a wave from its phase (0 to 1, any count of cycles) and its step (cycles a sample)'''
    t = phase % 1.0
    if wave == 'sine':
        return numpy.sin(2.0 * math.pi * t)
    if wave == 'tri':
        return 1.0 - 4.0 * numpy.abs(t - 0.5)
    if wave == 'noise':
        return (rng or numpy.random).uniform(-1.0, 1.0, len(t))
    if wave == 'square':
        width = min(max(shape, 0.05), 0.95)
        out = numpy.where(t < width, 1.0, -1.0)
        out += poly_blep(t, dt)
        out -= poly_blep((t - width) % 1.0, dt)
        return out
    if wave == 'table':
        # sine to tri to saw to square as its shape goes from 0 to 1
        place = min(max(shape, 0.0), 1.0) * 3.0
        names = ('sine', 'tri', 'saw', 'square')
        k = min(int(place), 2)
        mix = place - k
        return oscillate(names[k], phase, dt, 0.5) * (1.0 - mix)\
            + oscillate(names[k + 1], phase, dt, 0.5) * mix
    out = 2.0 * t - 1.0
    out -= poly_blep(t, dt)
    return out


def envelope(count, gate, env):
    '''an ADSR's level a sample: its attack, decay (seconds), sustain (level), release
    (seconds) after the gate (samples)'''
    a = max(int(env['a'] * RATE), 1)
    d = max(int(env['d'] * RATE), 1)
    s = min(max(env['s'], 0.0), 1.0)
    r = max(int(env['r'] * RATE), 1)
    out = numpy.empty(count)
    k = numpy.arange(count)
    attack = k < a
    out[attack] = k[attack] / float(a)
    decay = (k >= a) & (k < a + d)
    out[decay] = 1.0 - (1.0 - s) * (1.0 - numpy.exp(-5.0 * (k[decay] - a) / d)) / (
        1.0 - math.exp(-5.0))
    out[k >= a + d] = s
    # let go: from where it is at the gate, down over its release
    gate = min(max(int(gate), 1), count)
    held = out[gate - 1]
    tail = k >= gate
    out[tail] = held * numpy.exp(-5.0 * (k[tail] - gate) / r)
    return out


def coefficients(kind, freq, q):
    # a 2 pole filter's (b, a) (the cookbook's)
    w = 2.0 * math.pi * min(max(freq, 20.0), RATE * 0.45) / RATE
    alpha = math.sin(w) / (2.0 * max(q, 0.1))
    cos = math.cos(w)
    if kind == 'lp':
        b = ((1 - cos) / 2, 1 - cos, (1 - cos) / 2)
    elif kind == 'bp':
        b = (alpha, 0.0, -alpha)
    elif kind == 'notch':
        b = (1.0, -2 * cos, 1.0)
    else:
        b = ((1 + cos) / 2, -(1 + cos), (1 + cos) / 2)
    a0 = 1 + alpha
    return (numpy.array(b) / a0, numpy.array((1.0, -2 * cos / a0, (1 - alpha) / a0)))


def run_filter(sound, settings, opening):
    '''a filter over a stereo sound: its cutoff moved by opening (octaves a sample: the mod
    envelope's, the LFO's), in BLOCKs; 24 dB two stages (the first flat); drive: tanh
    before it (a Virus's grit)'''
    kind = settings.get('kind')
    if kind not in ('lp', 'hp', 'bp', 'notch'):
        return sound
    drive = settings.get('drive', 0.0)
    if drive > 0:
        gain = 1.0 + drive * 8.0
        sound = numpy.tanh(sound * gain) / math.tanh(gain) * (1.0 + drive * 0.5)
    q = 0.6 + settings.get('res', 0.0) ** 1.5 * 11.0
    stages = [q] if settings.get('slope', 12) != 24 else (
        [BUTTERWORTH[0], q * BUTTERWORTH[1] / 0.707] if kind in ('lp', 'hp') else [q, q])
    count = len(sound)
    out = numpy.empty_like(sound)
    states = [numpy.zeros((2, sound.shape[1])) for _ in stages]
    cutoff = settings.get('cutoff', 2000.0)
    for start in range(0, count, BLOCK):
        block = sound[start:start + BLOCK]
        freq = cutoff * 2.0 ** float(opening[min(start, count - 1)])
        for k, stage_q in enumerate(stages):
            b, a = coefficients(kind, freq, stage_q)
            block, states[k] = signal.lfilter(b, a, block, axis=0, zi=states[k])
        out[start:start + BLOCK] = block
    return out


def lfo_wave(shape, phase):
    t = phase % 1.0
    if shape == 'tri':
        return 1.0 - 4.0 * numpy.abs(t - 0.5)
    if shape == 'saw':
        return 1.0 - 2.0 * t
    if shape == 'square':
        return numpy.where(t < 0.5, 1.0, -1.0)
    return numpy.sin(2.0 * math.pi * t)


def render_group(notes, patch, step, at=0.0, glide_from=None, seed=0):
    '''notes starting together ([(midi, steps held, velocity)]) as a stereo float32 sound:
    each held its steps (step: seconds a step), let go over the amp's release. at: where
    in the bar they start (seconds: the LFO's place, synced to the bar); glide_from: the
    note before (mono: slid from it over the glide)'''
    if not notes:
        return numpy.zeros((1, 2), dtype=numpy.float32)
    amp, mod, lfo = patch['amp'], patch['mod'], patch['lfo']
    longest = max(length for _, length, _ in notes)
    gate = int(longest * step * RATE)
    count = gate + int(max(amp['r'], 0.01) * RATE) + BLOCK
    time = numpy.arange(count) / float(RATE)
    rng = numpy.random.RandomState(seed)
    # the LFO: a cycle LFO_RATES[rate] bars, its phase the bar's
    bar = step * 16.0
    period = bar * LFO_RATES[min(max(int(lfo.get('rate', 6)), 0), len(LFO_RATES) - 1)]
    depth = lfo.get('depth', 0.0)
    wobble = lfo_wave(lfo.get('shape', 'sine'), (at + time) / period) * depth\
        if depth else None
    dest = lfo.get('dest', 'cutoff')
    # pitch: a vibrato's (up to a semitone), a glide's; as a factor on the frequency
    bend = numpy.zeros(count)
    if wobble is not None and dest == 'pitch':
        bend += wobble * 1.0
    glide = patch.get('glide', 0.0)
    out = numpy.zeros((count, 2))
    width = min(max(patch.get('width', 0.5), 0.0), 1.0)
    for midi, length, velocity in notes:
        note_bend = bend
        if glide_from is not None and glide > 0:
            note_bend = bend + (glide_from - midi) * numpy.exp(-time / max(glide, 1e-3))
        factor = 2.0 ** (note_bend / 12.0)
        travelled = numpy.cumsum(factor) / RATE
        sound = numpy.zeros((count, 2))
        before = None
        for osc in patch['osc']:
            if not osc.get('on'):
                before = None
                continue
            freq = midi_to_freq(midi + 12 * osc.get('octave', 0) + osc.get('semi', 0)
                                + osc.get('fine', 0.0) / 100.0)
            voices = min(max(int(osc.get('voices', 1)), 1), VOICES_MOST)
            spread = osc.get('detune', 0.0) * DETUNE_MOST
            mono = numpy.zeros(count)
            left = numpy.zeros(count)
            right = numpy.zeros(count)
            for v in range(voices):
                place = 0.0 if voices == 1 else v / (voices - 1.0) * 2.0 - 1.0
                f = freq * 2.0 ** (place * spread / 1200.0)
                phase = rng.uniform(0, 1) if voices > 1 else 0.0
                phase = phase + f * travelled
                if before is not None and osc.get('fm', 0.0) > 0:
                    phase = phase + before * osc['fm'] * 2.0
                wave = oscillate(osc.get('wave', 'saw'), phase, f / RATE,
                                 osc.get('shape', 0.5), rng)
                pan = place * width
                left += wave * (1.0 - pan) * 0.5
                right += wave * (1.0 + pan) * 0.5
                mono += wave
            scale = osc.get('level', 0.7) / math.sqrt(voices)
            sound[:, 0] += left * scale
            sound[:, 1] += right * scale
            before = mono / voices
        held = int(length * step * RATE)
        sound *= (envelope(count, held, amp) * velocity)[:, None]
        out += sound
    # the filters in a row, their cutoffs opened by the mod envelope (the longest note's
    # gate) and the LFO
    opening_env = envelope(count, gate, mod)
    for settings in patch['filters']:
        opening = opening_env * settings.get('env', 0.0)
        if wobble is not None and dest == 'cutoff':
            opening = opening + wobble * 2.0
        out = run_filter(out, settings, opening)
    if wobble is not None and dest == 'amp':
        # (a tremolo down from full: as deep as the depth)
        out *= (1.0 - (abs(depth) - wobble * math.copysign(1.0, depth)) * 0.5)[:, None]
    if wobble is not None and dest == 'pan':
        out[:, 0] *= 1.0 - wobble
        out[:, 1] *= 1.0 + wobble
    out *= patch.get('level', 0.7) * 0.5
    # (no click where it ends)
    fade = min(BLOCK, len(out))
    out[-fade:] *= numpy.linspace(1.0, 0.0, fade)[:, None]
    return numpy.ascontiguousarray(numpy.clip(out, -1.0, 1.0), dtype=numpy.float32)


# chords stamped in the piano roll: their notes over a root, in semitones (a scale's
# third and fifth taken where the key says: triad/7th follow the song's key)
CHORDS = (('note', 'NOTE'), ('triad', 'TRIAD'), ('seventh', '7TH'), ('sus2', 'SUS2'),
          ('sus4', 'SUS4'), ('add9', 'ADD9'), ('power', 'POWER'), ('octave', 'OCT'))


def chord_notes(kind, root, key_root=None, scale=None):
    '''a chord's notes (midi) on a root: in the key (key_root, its scale's semitones) its
    third, fifth and seventh the key's own; off it (or no key) a major's'''
    def degree_up(steps):
        if scale is None or key_root is None:
            return {2: 4, 4: 7, 6: 10, 1: 2, 3: 5, 8: 14}[steps]
        place = (root - key_root) % 12
        if place not in scale:
            return {2: 4, 4: 7, 6: 10, 1: 2, 3: 5, 8: 14}[steps]
        k = scale.index(place)
        target = k + steps
        return scale[target % 7] + 12 * (target // 7) - place
    if kind == 'note':
        return [root]
    if kind == 'power':
        return [root, root + 7, root + 12]
    if kind == 'octave':
        return [root, root + 12]
    if kind == 'sus2':
        return [root, root + degree_up(1), root + degree_up(4)]
    if kind == 'sus4':
        return [root, root + degree_up(3), root + degree_up(4)]
    if kind == 'seventh':
        return [root, root + degree_up(2), root + degree_up(4), root + degree_up(6)]
    if kind == 'add9':
        return [root, root + degree_up(2), root + degree_up(4), root + degree_up(8)]
    return [root, root + degree_up(2), root + degree_up(4)]


# patches (their settings over make_patch's; oscillators and filters by place): SY-4's in
# Sylenth1's spirit, VR-1's in the Virus's (hypersaws, tables, FM, filters driven)

def osc(**values):
    return values


def lp(cutoff, res=0.2, slope=24, env=0.0, drive=0.0, kind='lp'):
    return dict(kind=kind, cutoff=cutoff, res=res, slope=slope, env=env, drive=drive)


OFF = dict(on=False)
NO_FILTER = dict(kind=None)

PATCHES = dict(sy4={
    'Supersaw Lead': dict(osc=[osc(wave='saw', voices=7, detune=0.45, level=0.7),
                               osc(wave='saw', octave=1, voices=7, detune=0.3, level=0.35),
                               OFF, OFF],
                          filters=[lp(5000, 0.15, env=1.0), NO_FILTER],
                          amp=dict(a=0.005, d=0.3, s=0.9, r=0.3), width=0.9),
    'Trance Pluck': dict(osc=[osc(wave='saw', voices=5, detune=0.35, level=0.7),
                              osc(wave='square', octave=1, level=0.3), OFF, OFF],
                         filters=[lp(600, 0.3, env=4.0), NO_FILTER],
                         mod=dict(a=0.001, d=0.18, s=0.0, r=0.15),
                         amp=dict(a=0.002, d=0.35, s=0.0, r=0.2), width=0.7),
    'Warm Pad': dict(osc=[osc(wave='saw', voices=5, detune=0.25, level=0.5),
                          osc(wave='saw', octave=-1, voices=3, detune=0.2, level=0.4), OFF, OFF],
                     filters=[lp(1400, 0.1, env=1.0), NO_FILTER],
                     mod=dict(a=1.2, d=2.0, s=0.6, r=1.5), amp=dict(a=0.8, d=1.0, s=0.9, r=1.5),
                     lfo=dict(rate=7, shape='sine', dest='cutoff', depth=0.15), width=0.8),
    'Sweep Pad': dict(osc=[osc(wave='saw', voices=7, detune=0.3, level=0.55),
                           osc(wave='square', voices=3, detune=0.2, level=0.3), OFF, OFF],
                      filters=[lp(500, 0.35), NO_FILTER], amp=dict(a=0.5, d=1.0, s=0.9, r=1.2),
                      lfo=dict(rate=7, shape='tri', dest='cutoff', depth=0.8), width=0.9),
    'House Organ': dict(osc=[osc(wave='sine', level=0.6), osc(wave='sine', octave=1, level=0.4),
                             osc(on=True, wave='sine', octave=2, level=0.25),
                             osc(on=True, wave='square', octave=1, level=0.08)],
                        filters=[lp(4000, 0.1, slope=12), NO_FILTER],
                        amp=dict(a=0.002, d=0.2, s=0.7, r=0.08), width=0.2),
    'Chord Stab': dict(osc=[osc(wave='saw', voices=3, detune=0.2, level=0.6),
                            osc(wave='square', level=0.4), OFF, OFF],
                       filters=[lp(900, 0.4, env=3.0), NO_FILTER],
                       mod=dict(a=0.001, d=0.15, s=0.0, r=0.1),
                       amp=dict(a=0.002, d=0.25, s=0.0, r=0.12), width=0.6),
    'Detuned Brass': dict(osc=[osc(wave='saw', voices=3, detune=0.15, level=0.6),
                               osc(wave='saw', fine=9.0, voices=3, detune=0.15, level=0.5),
                               OFF, OFF],
                          filters=[lp(700, 0.15, slope=12, env=2.5), NO_FILTER],
                          mod=dict(a=0.08, d=0.5, s=0.4, r=0.3),
                          amp=dict(a=0.03, d=0.3, s=0.85, r=0.2)),
    'Soft Keys': dict(osc=[osc(wave='tri', level=0.6), osc(wave='sine', octave=1, level=0.3),
                           OFF, OFF],
                      filters=[lp(3000, 0.1, slope=12), NO_FILTER],
                      amp=dict(a=0.002, d=0.9, s=0.2, r=0.4), width=0.3),
    'Hoover': dict(osc=[osc(wave='saw', voices=7, detune=0.8, level=0.6),
                        osc(wave='saw', octave=-1, voices=5, detune=0.6, level=0.5), OFF, OFF],
                   filters=[lp(1800, 0.2, slope=12), NO_FILTER], glide=0.08, width=1.0),
    'Sub Bass': dict(osc=[osc(wave='sine', octave=-1, level=0.9),
                          osc(wave='tri', octave=-1, level=0.3), OFF, OFF],
                     filters=[lp(400), NO_FILTER], amp=dict(a=0.003, d=0.3, s=0.8, r=0.1),
                     mono=True, glide=0.03, width=0.0),
    'Bell Pluck': dict(osc=[osc(wave='sine', octave=2, level=0.0),
                            osc(wave='sine', octave=1, fm=1.2, level=0.7), OFF, OFF],
                       filters=[NO_FILTER, NO_FILTER], amp=dict(a=0.001, d=0.8, s=0.0, r=0.6),
                       width=0.3),
    'Glass Pad': dict(osc=[osc(wave='table', shape=0.3, voices=5, detune=0.2, level=0.6),
                           OFF, OFF, OFF],
                      filters=[lp(6000, 0.1, slope=12), NO_FILTER],
                      amp=dict(a=0.6, d=1.0, s=0.9, r=1.2),
                      lfo=dict(rate=3, shape='sine', dest='amp', depth=0.2), width=0.8),
    'Square Lead': dict(osc=[osc(wave='square', level=0.6),
                             osc(wave='square', fine=8.0, level=0.5), OFF, OFF],
                        filters=[lp(3000, 0.25, env=1.0), NO_FILTER], mono=True, glide=0.05,
                        width=0.2),
    'Saw Bass': dict(osc=[osc(wave='saw', octave=-1, level=0.7),
                          osc(wave='square', octave=-1, fine=-6.0, level=0.5), OFF, OFF],
                     filters=[lp(500, 0.45, env=3.0), NO_FILTER],
                     mod=dict(a=0.001, d=0.25, s=0.1, r=0.1), mono=True, width=0.0),
    'Strings': dict(osc=[osc(wave='saw', voices=7, detune=0.25, level=0.5),
                         osc(wave='saw', octave=1, voices=5, detune=0.2, level=0.25), OFF, OFF],
                    filters=[lp(2800, 0.1, slope=12), NO_FILTER],
                    amp=dict(a=0.35, d=0.5, s=0.9, r=0.8),
                    lfo=dict(rate=3, shape='sine', dest='pitch', depth=0.05), width=0.9),
    'Gated Pad': dict(osc=[osc(wave='saw', voices=7, detune=0.4, level=0.7),
                           osc(wave='saw', octave=1, voices=5, detune=0.3, level=0.3), OFF, OFF],
                      filters=[lp(4000, 0.15), NO_FILTER],
                      lfo=dict(rate=0, shape='square', dest='amp', depth=0.95), width=0.9),
}, vr1={
    'Hypersaw': dict(osc=[osc(wave='saw', voices=9, detune=0.55, level=0.7),
                          osc(wave='saw', octave=1, voices=7, detune=0.4, level=0.35), OFF, OFF],
                     filters=[lp(4500, 0.2, drive=0.2), NO_FILTER], width=1.0),
    'Virus Bass': dict(osc=[osc(wave='saw', octave=-1, level=0.7),
                            osc(wave='square', octave=-1, shape=0.3, level=0.5), OFF, OFF],
                       filters=[lp(300, 0.55, env=3.5, drive=0.5), NO_FILTER],
                       mod=dict(a=0.001, d=0.2, s=0.05, r=0.1), mono=True, glide=0.04,
                       width=0.0),
    'Acid Lead': dict(osc=[osc(wave='saw', level=0.8), OFF, OFF, OFF],
                      filters=[lp(600, 0.75, env=4.0, drive=0.4), NO_FILTER],
                      mod=dict(a=0.001, d=0.15, s=0.1, r=0.1), mono=True, glide=0.06,
                      width=0.0),
    'FM Bell': dict(osc=[osc(wave='sine', octave=1, level=0.0),
                         osc(wave='sine', fm=1.5, level=0.7), OFF, OFF],
                    filters=[NO_FILTER, NO_FILTER], amp=dict(a=0.001, d=1.2, s=0.0, r=0.8)),
    'Wavetable Pad': dict(osc=[osc(wave='table', shape=0.55, voices=5, detune=0.3, level=0.6),
                               OFF, OFF, OFF],
                          filters=[lp(2500, 0.15, slope=12), NO_FILTER],
                          amp=dict(a=0.5, d=1.0, s=0.9, r=1.2),
                          lfo=dict(rate=7, shape='sine', dest='cutoff', depth=0.3), width=0.9),
    'Growl': dict(osc=[osc(wave='saw', level=0.6), osc(wave='table', shape=0.8, level=0.5),
                       OFF, OFF],
                  filters=[lp(500, 0.6, drive=0.7), NO_FILTER],
                  lfo=dict(rate=3, shape='saw', dest='cutoff', depth=1.2), mono=True,
                  width=0.2),
    'Reese Bass': dict(osc=[osc(wave='saw', octave=-1, voices=2, detune=0.25, level=0.6),
                            osc(wave='saw', octave=-1, fine=12.0, level=0.5), OFF, OFF],
                       filters=[lp(700, 0.2, drive=0.3), NO_FILTER], mono=True, glide=0.02,
                       width=0.3),
    'Talking Wah': dict(osc=[osc(wave='saw', voices=3, detune=0.2, level=0.7), OFF, OFF, OFF],
                        filters=[lp(900, 0.6, slope=12, env=2.0, kind='bp'), NO_FILTER],
                        lfo=dict(rate=5, shape='tri', dest='cutoff', depth=0.9)),
    'Pluck Lead': dict(osc=[osc(wave='square', shape=0.25, level=0.5),
                            osc(wave='saw', level=0.5), OFF, OFF],
                       filters=[lp(1200, 0.3, env=3.5), NO_FILTER],
                       mod=dict(a=0.001, d=0.2, s=0.0, r=0.1),
                       amp=dict(a=0.001, d=0.4, s=0.2, r=0.2)),
    'Dist Lead': dict(osc=[osc(wave='saw', voices=3, detune=0.2, level=0.6),
                           osc(wave='square', level=0.4), OFF, OFF],
                      filters=[lp(5000, 0.2, slope=12, drive=0.9), NO_FILTER], mono=True,
                      glide=0.03),
    'Sub Drop': dict(osc=[osc(wave='sine', octave=-1, level=0.9), OFF, OFF, OFF],
                     filters=[NO_FILTER, NO_FILTER], mono=True, glide=0.3, width=0.0),
    'Sync Lead': dict(osc=[osc(wave='table', shape=0.9, level=0.6),
                           osc(wave='square', fine=3.0, level=0.4), OFF, OFF],
                      filters=[lp(2500, 0.35, env=2.0, drive=0.3), NO_FILTER], mono=True,
                      glide=0.04),
})
FIRST_PATCHES = dict(sy4=PATCHES['sy4']['Supersaw Lead'], vr1=PATCHES['vr1']['Virus Bass'])
