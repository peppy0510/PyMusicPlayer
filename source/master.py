# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import ctypes
import pybass

from ctypes import wintypes
from macroboxlib import GetPreference
from macroboxlib import SetPreference
from pybass import pybass_vst


# Auto Master parameters, levels and A/B
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
# plugin defaults, and the player's with the limiter pushed to the ceiling
PLUGIN_DEFAULTS = (1.0, 0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 12.0 / 14.0, 1.0, 1.0, 10.5 / 18.0,
                   8.0 / 12.0, 1.0, 5.0 / 6.0, 0.0, 0.0, 1.0 / 9.0)
DEFAULTS = PLUGIN_DEFAULTS[:13] + (1.0, 1.0, 1.0) + PLUGIN_DEFAULTS[16:]

GetParam = pybass_vst.func_type(ctypes.c_float, ctypes.c_ulong, ctypes.c_int)(
    ('BASS_VST_GetParam', pybass_vst.bass_vst_module))


# cached: GetPreference opens the settings at every call
values_kept = None


def get_values():
    global values_kept
    if values_kept is None:
        values = GetPreference('automaster_values')
        if not isinstance(values, (list, tuple)) or len(values) != len(DEFAULTS):
            values = DEFAULTS
        values_kept = list(values)
    return list(values_kept)


def set_value(index, value, handles=()):
    global values_kept
    values = get_values()
    values[index] = min(max(float(value), 0.0), 1.0)
    values_kept = list(values)
    SetPreference('automaster_values', values)
    for handle in handles:
        if handle:
            pybass.BASS_VST_SetParam(handle, index, values[index])
    return values


def is_on(value):
    return value >= 0.5


# stage switches, toggled as one
STAGE_SWITCHES = dict(agc=(0,), stereo=(4, 5, 6, 8, 9), limiter=(12,))


def is_stage_on(stage, values=None):
    values = get_values() if values is None else values
    return any(is_on(values[index]) for index in STAGE_SWITCHES[stage])


def toggle_stage(stage, handles=()):
    '''stage off, or back on as kept (all on when none kept)'''
    values = get_values()
    switches = STAGE_SWITCHES[stage]
    kept = GetPreference('automaster_stages')
    kept = kept if isinstance(kept, dict) else {}
    if is_stage_on(stage, values):
        kept[stage] = [values[index] for index in switches]
        SetPreference('automaster_stages', kept)
        turned = [0.0] * len(switches)
    else:
        turned = kept.get(stage)
        if not isinstance(turned, list) or len(turned) != len(switches)\
                or not any(is_on(value) for value in turned):
            turned = [1.0] * len(switches)
    for index, value in zip(switches, turned):
        values = set_value(index, value, handles)
    return values


class Probe():

    '''parameter texts from the plugin on a silent dummy stream'''

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
                return f'{round(value * 100)}%'
        pybass.BASS_VST_SetParam(self.vst, index, value)
        info = pybass_vst.BASS_VST_PARAM_INFO()
        pybass.BASS_VST_GetParamInfo(self.vst, index, ctypes.byref(info))
        text = (f'{info.display.decode("ascii", "replace").strip()} '
                f'{info.unit.decode("ascii", "replace").strip()}').strip()
        self.texts[key] = text
        return text


PROBE = Probe()


# plugin levels in shared memory (plugin/automaster.c)
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

    def Read(self, vst=0):
        '''levels of this handle's slot, else the last sounding one; None when stale'''
        if self.block is None and not self.Open():
            return None
        if self.block.magic != MAGIC:
            return None
        now = kernel32.GetTickCount64()
        owner = get_owner(vst)
        best = None
        for slot in self.block.slots:
            if not slot.owner or not slot.tick or now - slot.tick > STALE_MS:
                continue
            if owner and slot.owner != owner:
                continue
            key = (slot.sounding, slot.tick)
            if best is None or key > best[0]:
                best = (key, slot)
        if best is None:
            return None
        slot = best[1]
        return dict(agc=slot.agc_db, limiter=slot.limiter_db, side=slot.side_db,
                    balance=slot.balance_db, loudness=slot.loudness,
                    phase=slot.phase_delay_ms, phase_flip=bool(slot.phase_flip),
                    bands=[dict(width=slot.band_width_db[k], fill=slot.fill_band_db[k],
                                target=slot.band_target_db[k]) for k in range(3)],
                    sounding=bool(slot.sounding))

    def IsCompared(self):
        return bool(self.block is not None and self.block.bypass)

    def SetCompared(self, on):
        # A/B: the original at the same loudness
        if self.block is None and not self.Open():
            return False
        self.block.bypass = 1 if on else 0
        return True


METERS = Meters()


def get_owner(vst, kept={}):
    # plugin instance (aeffect) of a BASS_VST handle, 0 when unknown
    if not vst:
        return 0
    if vst not in kept:
        info = pybass_vst.BASS_VST_INFO()
        found = pybass_vst.BASS_VST_GetInfo(vst, ctypes.byref(info))
        kept.clear()
        kept[vst] = (info.aeffect or 0) if found else 0
    return kept[vst]
