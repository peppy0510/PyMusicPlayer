# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import ctypes
import math
import pybass

from ctypes import wintypes
from macroboxlib import GetPreference
from macroboxlib import SetPreference
from pybass import pybass_vst


# MASTER: Auto Master's settings kept (automaster_values: its 17 parameters, 0 to 1) and put
# on every stream it is on, its levels read from the plugin's shared memory (PyMusicPlayer's
# own name, plugin/automaster.c), and its A/B there (the original at the same loudness)
# (index, name, group, kind): kind 'switch' (on or off) or 'knob' (0 to 1)
PARAMS = (
    (0, 'AGC', 'AGC', 'switch'), (1, 'Target', 'AGC', 'knob'),
    (2, 'Max Gain', 'AGC', 'knob'), (3, 'Speed', 'AGC', 'knob'),
    (4, 'Balance', 'Stereo', 'switch'), (5, 'Phase Fix', 'Stereo', 'switch'),
    (6, 'Width Limit', 'Stereo', 'switch'), (7, 'Max Width', 'Stereo', 'knob'),
    (8, 'Bass Mono', 'Stereo', 'switch'), (9, 'Mono Wide', 'Stereo', 'switch'),
    (10, 'Wide Target', 'Stereo', 'knob'), (11, 'Air', 'Stereo', 'knob'),
    (12, 'Limiter', 'Limiter', 'switch'), (13, 'Ceiling', 'Limiter', 'knob'),
    (14, 'Drive', 'Limiter', 'knob'), (15, 'Smooth', 'Limiter', 'switch'),
    (16, 'Attack', 'Limiter', 'knob'))
GROUPS = ('AGC', 'Stereo', 'Limiter')
# the plugin's own first values (PARAM_DEFAULTS), and the player's: the limiter pushed to
# the ceiling as the PyWinAudio rack runs it (about LoudMax's sound)
PLUGIN_DEFAULTS = (1.0, 0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 12.0 / 14.0, 1.0, 1.0, 10.5 / 18.0,
                   8.0 / 12.0, 1.0, 5.0 / 6.0, 0.0, 0.0, 1.0 / 9.0)
DEFAULTS = PLUGIN_DEFAULTS[:13] + (1.0, 1.0, 1.0) + PLUGIN_DEFAULTS[16:]

GetParam = pybass_vst.func_type(ctypes.c_float, ctypes.c_ulong, ctypes.c_int)(
    ('BASS_VST_GetParam', pybass_vst.bass_vst_module))


def get_values():
    values = GetPreference('automaster_values')
    if not isinstance(values, (list, tuple)) or len(values) != len(DEFAULTS):
        return list(DEFAULTS)
    return list(values)


def set_value(index, value, handles=()):
    # kept, and put on the streams it is on now
    values = get_values()
    values[index] = min(max(float(value), 0.0), 1.0)
    SetPreference('automaster_values', values)
    for handle in handles:
        if handle:
            pybass.BASS_VST_SetParam(handle, index, values[index])
    return values


def is_on(value):
    return value >= 0.5


class Probe():

    '''a value told as the plugin tells it (-16.0 LUFS): a silent stream of nothing with
    the plugin on it, made once, used only for its parameters' texts'''

    def __init__(self):
        self.handle = 0
        self.vst = 0
        self.texts = {}

    def Text(self, index, value):
        key = (index, round(value, 4))
        if key in self.texts:
            return self.texts[key]
        if not self.vst:
            self.handle = pybass.BASS_StreamCreate(44100, 2, pybass.BASS_STREAM_DECODE,
                                                   pybass.STREAMPROC_DUMMY, None)
            self.vst = audio.set_automaster(self.handle, True) if self.handle else 0
            if not self.vst:
                return '%d%%' % (round(value * 100))
        pybass.BASS_VST_SetParam(self.vst, index, value)
        info = pybass_vst.BASS_VST_PARAM_INFO()
        pybass.BASS_VST_GetParamInfo(self.vst, index, ctypes.byref(info))
        text = ('%s %s' % (info.display.decode('ascii', 'replace').strip(),
                           info.unit.decode('ascii', 'replace').strip())).strip()
        self.texts[key] = text
        return text


PROBE = Probe()


# the levels, as PyWinAudio reads them (automastermeter.py): the plugin's slots in its
# shared memory, the one that sounded last
MAGIC = 0x4D415750
SLOTS = 8
NAMES = ('Global\\PyMusicPlayerAutoMaster.v4', 'Local\\PyMusicPlayerAutoMaster.v4')
FILE_MAP_WRITE = 0x0002
FILE_MAP_READ = 0x0004
STALE_MS = 1500


class Slot(ctypes.Structure):
    _fields_ = [('owner', ctypes.c_int64), ('tick', ctypes.c_int64),
                ('agc_db', ctypes.c_float), ('balance_db', ctypes.c_float),
                ('side_db', ctypes.c_float), ('fill_db', ctypes.c_float),
                ('limiter_db', ctypes.c_float), ('loudness', ctypes.c_float),
                ('sounding', ctypes.c_int32), ('phase_flip', ctypes.c_int32),
                ('fill_band_db', ctypes.c_float * 3), ('phase_delay_ms', ctypes.c_float),
                ('band_width_db', ctypes.c_float * 3), ('band_target_db', ctypes.c_float * 3)]


class Block(ctypes.Structure):
    _fields_ = [('magic', ctypes.c_uint32), ('version', ctypes.c_uint32),
                ('bypass', ctypes.c_int32), ('reserved', ctypes.c_uint32),
                ('slots', Slot * SLOTS)]


kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenFileMappingW.restype = wintypes.HANDLE
kernel32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.c_size_t]
kernel32.MapViewOfFile.restype = ctypes.c_void_p
kernel32.GetTickCount64.restype = ctypes.c_uint64


class Meters():

    def __init__(self):
        self.block = None
        self.handle = None

    def Open(self):
        for name in NAMES:
            handle = kernel32.OpenFileMappingW(FILE_MAP_READ | FILE_MAP_WRITE, False, name)
            if not handle:
                continue
            address = kernel32.MapViewOfFile(handle, FILE_MAP_READ | FILE_MAP_WRITE, 0, 0,
                                             ctypes.sizeof(Block))
            if address:
                self.block = Block.from_address(address)
                self.handle = handle
                return True
        return False

    def Read(self):
        '''{agc, limiter, side, balance, loudness} of the slot that sounded last, None when
        none did lately (the plugin not on, or silent)'''
        if self.block is None and not self.Open():
            return None
        if self.block.magic != MAGIC:
            return None
        now = kernel32.GetTickCount64()
        best = None
        for slot in self.block.slots:
            if not slot.owner or not slot.tick or now - slot.tick > STALE_MS:
                continue
            key = (slot.sounding, slot.tick)
            if best is None or key > best[0]:
                best = (key, slot)
        if best is None:
            return None
        slot = best[1]
        return dict(agc=slot.agc_db, limiter=slot.limiter_db, side=slot.side_db,
                    balance=slot.balance_db, loudness=slot.loudness,
                    sounding=bool(slot.sounding))

    def IsCompared(self):
        return bool(self.block is not None and self.block.bypass)

    def SetCompared(self, on):
        # A/B: the original at the same loudness and the same delay
        if self.block is None and not self.Open():
            return False
        self.block.bypass = 1 if on else 0
        return True


METERS = Meters()


def get_output_db(handle):
    # the stream's peak as it plays (after the plugin), dBFS; None when it does not play
    if not handle:
        return None
    level = audio.get_channel_level(handle)
    if level in (-1, 0xFFFFFFFF):
        return None
    peak = max(level & 0xFFFF, (level >> 16) & 0xFFFF) / 32768.0
    return 20 * math.log10(max(peak, 1e-5))
