# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import ctypes
import math
import pybass


# MIXER's inserts: bass_fx's effects (bundled with the player, its DLL loaded by
# audio.load_bass_fx), on a channel's handle (a deck's in its mixer, a bus's) by
# BASS_ChannelSetFX. each its knobs (key, label, low, high, log, first value) in their
# units; MIX its dry and wet (those with both: the others all wet). an insert's settings are
# its knobs' values by key (audiograph.FxSlot's params, its path 'bfx:' and its name)

CHANALL = -1
f, d, i = ctypes.c_float, ctypes.c_ulong, ctypes.c_int


class FREEVERB(ctypes.Structure):
    _fields_ = [('fDryMix', f), ('fWetMix', f), ('fRoomSize', f), ('fDamp', f), ('fWidth', f),
                ('lMode', d), ('lChannel', i)]


class ECHO4(ctypes.Structure):
    _fields_ = [('fDryMix', f), ('fWetMix', f), ('fFeedback', f), ('fDelay', f),
                ('bStereo', i), ('lChannel', i)]


class CHORUS(ctypes.Structure):
    _fields_ = [('fDryMix', f), ('fWetMix', f), ('fFeedback', f), ('fMinSweep', f),
                ('fMaxSweep', f), ('fRate', f), ('lChannel', i)]


class PHASER(ctypes.Structure):
    _fields_ = [('fDryMix', f), ('fWetMix', f), ('fFeedback', f), ('fRate', f), ('fRange', f),
                ('fFreq', f), ('lChannel', i)]


class AUTOWAH(PHASER):
    pass


class DISTORTION(ctypes.Structure):
    _fields_ = [('fDrive', f), ('fDryMix', f), ('fWetMix', f), ('fFeedback', f), ('fVolume', f),
                ('lChannel', i)]


class COMPRESSOR2(ctypes.Structure):
    _fields_ = [('fGain', f), ('fThreshold', f), ('fRatio', f), ('fAttack', f), ('fRelease', f),
                ('lChannel', i)]


class BQF(ctypes.Structure):
    _fields_ = [('lFilter', i), ('fCenter', f), ('fGain', f), ('fBandwidth', f), ('fQ', f),
                ('fS', f), ('lChannel', i)]


MIX = ('mix', 'MIX', 0.0, 1.0, False, 0.3)


def wet(values):
    return dict(fDryMix=1.0 - values['mix'], fWetMix=values['mix'])


def bqf(kind, v, q=None):
    # (BQF's lFilter: 0 low pass, 1 high, 3 band (its Q), 4 notch)
    return dict(lFilter=kind, fCenter=v['cutoff'], fGain=0.0, fBandwidth=0.0,
                fQ=v['q'] if q is None else q, fS=0.0, lChannel=CHANALL)


# a 24 dB slope: two of them, the first flat (Butterworth's), the resonance on the second
BUTTERWORTH_FIRST = 0.541
BUTTERWORTH_SECOND = 1.307 / 0.707

# name: (label, its bass_fx type, its structure, its knobs, its structure's values: a
# list of them for stages in a row, an effect each)
EFFECTS = dict(
    reverb=('REVERB', 0x10016, FREEVERB,
            (MIX, ('size', 'SIZE', 0.0, 1.0, False, 0.6), ('damp', 'DAMP', 0.0, 1.0, False, 0.5),
             ('width', 'WIDTH', 0.0, 1.0, False, 1.0)),
            lambda v: dict(wet(v), fRoomSize=v['size'], fDamp=v['damp'], fWidth=v['width'],
                           lMode=0, lChannel=CHANALL)),
    delay=('DELAY', 0x10014, ECHO4,
           (MIX, ('time', 'TIME', 0.02, 1.5, True, 0.375),
            ('feedback', 'FEEDBACK', 0.0, 0.9, False, 0.35)),
           lambda v: dict(wet(v), fFeedback=v['feedback'], fDelay=v['time'], bStereo=0,
                          lChannel=CHANALL)),
    chorus=('CHORUS', 0x1000d, CHORUS,
            (MIX, ('rate', 'RATE', 0.05, 5.0, True, 0.6), ('depth', 'DEPTH', 1.0, 20.0, True, 6.0),
             ('feedback', 'FEEDBACK', -0.5, 0.5, False, 0.1)),
            lambda v: dict(wet(v), fFeedback=v['feedback'], fMinSweep=1.0,
                           fMaxSweep=1.0 + v['depth'], fRate=v['rate'], lChannel=CHANALL)),
    phaser=('PHASER', 0x1000b, PHASER,
            (MIX, ('rate', 'RATE', 0.05, 5.0, True, 0.4), ('range', 'RANGE', 1.0, 8.0, False, 4.0),
             ('freq', 'FREQ', 100.0, 3000.0, True, 500.0),
             ('feedback', 'FEEDBACK', -0.9, 0.9, False, 0.3)),
            lambda v: dict(wet(v), fFeedback=v['feedback'], fRate=v['rate'], fRange=v['range'],
                           fFreq=v['freq'], lChannel=CHANALL)),
    autowah=('AUTO WAH', 0x10009, AUTOWAH,
             (MIX, ('rate', 'RATE', 0.1, 8.0, True, 2.0), ('range', 'RANGE', 1.0, 8.0, False, 4.3),
              ('freq', 'FREQ', 100.0, 3000.0, True, 50.0 * 10)),
             lambda v: dict(wet(v), fFeedback=0.5, fRate=v['rate'], fRange=v['range'],
                            fFreq=v['freq'], lChannel=CHANALL)),
    distortion=('DISTORTION', 0x10010, DISTORTION,
                (MIX, ('drive', 'DRIVE', 0.0, 5.0, False, 1.0),
                 ('volume', 'VOLUME', 0.0, 2.0, False, 0.45)),
                lambda v: dict(fDrive=v['drive'], fDryMix=1.0 - v['mix'], fWetMix=v['mix'],
                               fFeedback=0.1, fVolume=v['volume'], lChannel=CHANALL)),
    lowpass=('LOW PASS 12', 0x10013, BQF,
             (('cutoff', 'CUTOFF', 40.0, 18000.0, True, 2000.0),
              ('q', 'RES', 0.5, 10.0, True, 0.7)),
             lambda v: bqf(0, v)),
    lowpass24=('LOW PASS 24', 0x10013, BQF,
               (('cutoff', 'CUTOFF', 40.0, 18000.0, True, 2000.0),
                ('q', 'RES', 0.5, 10.0, True, 0.7)),
               lambda v: [bqf(0, v, BUTTERWORTH_FIRST), bqf(0, v, v['q'] * BUTTERWORTH_SECOND)]),
    highpass=('HIGH PASS 12', 0x10013, BQF,
              (('cutoff', 'CUTOFF', 20.0, 8000.0, True, 120.0),
               ('q', 'RES', 0.5, 10.0, True, 0.7)),
              lambda v: bqf(1, v)),
    highpass24=('HIGH PASS 24', 0x10013, BQF,
                (('cutoff', 'CUTOFF', 20.0, 8000.0, True, 120.0),
                 ('q', 'RES', 0.5, 10.0, True, 0.7)),
                lambda v: [bqf(1, v, BUTTERWORTH_FIRST),
                           bqf(1, v, v['q'] * BUTTERWORTH_SECOND)]),
    bandpass=('BAND PASS', 0x10013, BQF,
              (('cutoff', 'FREQ', 60.0, 12000.0, True, 1000.0),
               ('q', 'Q', 0.3, 10.0, True, 1.0)),
              lambda v: bqf(3, v)),
    notch=('NOTCH', 0x10013, BQF,
           (('cutoff', 'FREQ', 40.0, 16000.0, True, 1000.0),
            ('q', 'Q', 0.3, 10.0, True, 1.0)),
           lambda v: bqf(4, v)),
    compressor=('COMPRESSOR', 0x10011, COMPRESSOR2,
                (('threshold', 'THRESH', -40.0, 0.0, False, -15.0),
                 ('ratio', 'RATIO', 1.0, 20.0, True, 3.0),
                 ('attack', 'ATTACK', 0.5, 100.0, True, 10.0),
                 ('release', 'RELEASE', 20.0, 1000.0, True, 200.0),
                 ('gain', 'GAIN', 0.0, 20.0, False, 3.0)),
                lambda v: dict(fGain=v['gain'], fThreshold=v['threshold'], fRatio=v['ratio'],
                               fAttack=v['attack'], fRelease=v['release'], lChannel=CHANALL)),
)
# (an insert's row: its short name)
SHORT = dict(reverb='REVERB', delay='DELAY', chorus='CHORUS', phaser='PHASER', autowah='WAH',
             distortion='DIST', lowpass='LPF 12', lowpass24='LPF 24', highpass='HPF 12',
             highpass24='HPF 24', bandpass='BPF', notch='NOTCH', compressor='COMP')
ORDER = ('reverb', 'delay', 'chorus', 'phaser', 'autowah', 'distortion', 'lowpass',
         'lowpass24', 'highpass', 'highpass24', 'bandpass', 'notch', 'compressor')


def get_name(path):
    # an insert's path ('bfx:reverb') its effect's name, None for a VST's
    if isinstance(path, str) and path.startswith('bfx:'):
        name = path[4:]
        return name if name in EFFECTS else None
    return None


def get_knobs(name):
    return EFFECTS[name][3]


def first_values(name):
    return dict((knob[0], knob[5]) for knob in get_knobs(name))


def to_turn(knob, value):
    _, _, low, high, log, _ = knob
    if log:
        return math.log(max(value, low) / low) / math.log(high / low)
    return (value - low) / float(high - low)


def from_turn(knob, turn):
    _, _, low, high, log, _ = knob
    turn = min(max(turn, 0.0), 1.0)
    return low * (high / low) ** turn if log else low + (high - low) * turn


def get_stages(name, values):
    # its structure's values, a stage each
    merged = first_values(name)
    merged.update(values or {})
    stages = EFFECTS[name][4](merged)
    return stages if isinstance(stages, list) else [stages]


def apply(handle, name, values, priority):
    '''the effect on a handle (bass_fx loaded first), its settings set; its handle (a
    tuple of them for stages: one after another at the same priority), 0 when it can not
    be'''
    if not handle or name not in EFFECTS:
        return 0
    audio.load_bass_fx()
    kind = EFFECTS[name][1]
    fxs = []
    for _ in get_stages(name, values):
        fx = pybass.BASS_ChannelSetFX(handle, kind, priority)
        if not fx:
            for made in fxs:
                pybass.BASS_ChannelRemoveFX(handle, made)
            return 0
        fxs.append(fx)
    fx = fxs[0] if len(fxs) == 1 else tuple(fxs)
    set_values(fx, name, values)
    return fx


def set_values(fx, name, values):
    structure = EFFECTS[name][2]
    fxs = fx if isinstance(fx, tuple) else (fx,)
    done = True
    for one, stage in zip(fxs, get_stages(name, values)):
        settings = structure(**stage)
        done = bool(pybass.BASS_FXSetParameters(one, ctypes.byref(settings))) and done
    return done


def remove(handle, fx):
    if handle and fx:
        for one in (fx if isinstance(fx, tuple) else (fx,)):
            pybass.BASS_ChannelRemoveFX(handle, one)


def format_value(knob, value):
    key = knob[0]
    if key in ('mix', 'size', 'damp', 'width'):
        return '%d%%' % round(value * 100)
    if key in ('time', 'attack', 'release'):
        seconds = value if key == 'time' else value / 1000.0
        return '%d ms' % round(seconds * 1000) if seconds < 1 else '%.2f s' % seconds
    if key in ('freq', 'cutoff'):
        return '%.1fk' % (value / 1000.0) if value >= 1000 else '%d' % round(value)
    if key in ('threshold', 'gain'):
        return '%+.1f dB' % value
    if key == 'ratio':
        return '%.1f:1' % value
    if key == 'rate':
        return '%.2f Hz' % value
    if key == 'depth':
        return '%.1f ms' % value
    return '%.2f' % value
