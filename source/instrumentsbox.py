# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import effects
import instruments
import math
import numpy
import presets
import synth
import uikit
import wx

from macroboxlib import GetPreference
from macroboxlib import SetPreference
from rackbox import HEADER
from rackbox import RackModule
from rackbox import colour
from rackbox import draw_well
from rackbox import get_font


# INSTRUMENTS: a rack of devices to play along with the song (in time with its grid, from
# its next sixteenth), as many of each kind as wanted (AudioControl.GetDevices: added,
# taken away, moved by a drag of a device's left ear), each a plate of one standard width
# and height (an RT909 taller a row for each slot past five), its ears screwed to the rack:
# - its head: an LED (lit while it plays), its name, its SOUND and PATTERN (presets: built
#   in and saved, presets.py), PLAY
# - its keys and steps at the left (the step heard ringed; a click turns one on or off, a
#   drag paints those it passes), its knobs at the right (a drag turns one, shift finer, the
#   wheel, a double click back to its first value; its value over it while touched)
# kinds:
# - RT909, the drum machine: its slots (any sound from any kit in any slot: picked by a
#   click on its name, renamed by a double click, moved by a drag, a menu on a right click,
#   added at the bottom), a slot's voice (its kit, engine, wave, filter, envelope, knobs)
# - PS1200, the sampler: a bar grabbed from the deck, a machine or the mix, on its LCD cut
#   in sixteen slices (a click heard and picked: its pitch, level, decay, reverse its own)
# - BT303, the bass: its line on a roll in the song's key (a drag draws its notes, each
#   step the row under the mouse: Reason's Matrix's way), its accents and slides under it

EAR = 16
DEV_GAP = 6
HEAD = 30
# its contents from here under its head; its keys' line, its rows'
CT = HEAD + 8
KEY_HEIGHT = 20
KEY_WIDTH = 52
SMALL_KEY = 36
KEY_GAP = 6
ROWS = CT + KEY_HEIGHT + 8
ROW = 18
# a step's cell at most (smaller only when the window is narrow)
CELL_MOST = 22
GRID = CELL_MOST * instruments.STEPS
# RT909's slots' strip (a name each), their mute and solo keys after their steps
NAME_WIDTH = 92
PAD_KEY = 14
PAD_KEYS = 2 * PAD_KEY + 6
LEFT_MOST = NAME_WIDTH + GRID + PAD_KEYS
# the knobs at the right: two rows
KNOB_RADIUS = 12
KNOB_ROW = 70
# the knobs in sections, a frame each (its name and what it sets at its top)
SECTION_HEAD = 16
SECTION_GAP = 6
# a knob's room (its cluster as wide as its knobs: spread over the column, they read as
# strays)
KNOB_CELL = 72
KNOB_DRAG = 220.0
KNOB_FINE = 0.2
KNOB_WHEEL = 0.025
# a device's standard height (its contents for five slots: an RT909 a ROW taller a slot
# past them)
# its INSERTS at its bottom (its MIXER channel's: the same chain), under its own: a row of
# their chips (FX_ROW), their knobs under them while one is opened (FX_BAND)
FX_BAND = 64
FX_ROW = 30
DEV_HEIGHT = 216
# a device folded: its head alone
FOLDED_HEIGHT = 36
FOLD_KEY = 18
FX_KNOB = 10
FX_KEY = 62
SLOTS_SEEN = 5
SWITCH_HEIGHT = 18
WAVE_HEIGHT = 58
ROLL_DEGREES = 8
ROLL_ROW = 9
FLAG_ROW = 11
ROLL_NAMES = 26
SCREW = 2.5
NOTE_NAMES = instruments.NOTE_NAMES
# (name, what it is, its colour: a stripe, its steps, knobs and lit keys; told apart by
# its name too)
PLATES = dict(rt909=('RT-909', 'RHYTHM TRACKER', 'warn'),
              ps1200=('PS-1200', 'SAMPLING SLICER', 'accent'),
              bt303=('BT-303', 'BASS TRANSLATOR', '#C9CED6'),
              sy4=('SY-4', 'POLY SYNTH', '#A78BFA'),
              vr1=('VR-1', 'VIRTUAL ANALOG', '#2DD4BF'),
              mp60=('MP-60', 'PAD SAMPLER', '#E3B341'))
# the synths' (SY-4, VR-1) knob pages: a tab each at the knobs' left
SYNTH_PAGES = (('osc0', 'OSC 1'), ('osc1', 'OSC 2'), ('osc2', 'OSC 3'), ('osc3', 'OSC 4'),
               ('filter', 'FILTER'), ('env', 'ENV'), ('lfo', 'LFO'))
TAB_WIDTH = 54
TAB_HEIGHT = 19
# a synth knob's (its setting's last key): its label, its range, log, whole steps only
SYNTH_SPECS = dict(
    octave=('OCT', -2, 2, False, True), semi=('SEMI', -12, 12, False, True),
    fine=('FINE', -50.0, 50.0, False, False), voices=('VOICES', 1, synth.VOICES_MOST, False,
                                                      True),
    detune=('DETUNE', 0.0, 1.0, False, False), level=('LEVEL', 0.0, 1.0, False, False),
    shape=('SHAPE', 0.0, 1.0, False, False), fm=('FM', 0.0, 3.0, False, False),
    cutoff=('CUTOFF', 30.0, 18000.0, True, False), res=('RES', 0.0, 1.0, False, False),
    drive=('DRIVE', 0.0, 1.0, False, False), env=('ENV', -4.0, 4.0, False, False),
    a=('ATTACK', 0.001, 4.0, True, False), d=('DECAY', 0.005, 4.0, True, False),
    s=('SUSTAIN', 0.0, 1.0, False, False), r=('RELEASE', 0.005, 4.0, True, False),
    rate=('RATE', 0, len(synth.LFO_RATES) - 1, False, True),
    depth=('DEPTH', -1.5, 1.5, False, False), glide=('GLIDE', 0.0, 0.5, False, False),
    width=('WIDTH', 0.0, 1.0, False, False))
WAVE_KINDS = (('saw', 'SAW'), ('square', 'SQR'), ('tri', 'TRI'), ('sine', 'SINE'),
              ('noise', 'NOISE'), ('table', 'TABLE'))
LFO_SHAPES = tuple((shape, shape.upper()) for shape in synth.LFO_SHAPES)
LFO_DESTS = (('cutoff', 'CUTOFF'), ('pitch', 'PITCH'), ('amp', 'AMP'), ('pan', 'PAN'))
# a synth's notes seen at its left (a click: the piano roll on it)
OVERVIEW_HEIGHT = 104
MOVE_KEY = 46
# a file loaded into a pad: its first seconds at most
PAD_FILE_SECONDS = 4.0
# MP-60's: a pad's row in its steps, its pads' grid at the right
PAD_ROW = 10
PAD_SIDE = 56
PAD_TALL = 38
PAD_GAP = 5
# (its rows taller than a device's room: its plate this much taller)
PAD_EXTRA = 18
PAD_KNOBS = (('semis', 'TUNE', -12.0, 12.0, False), ('gain', 'LEVEL', 0.0, 1.5, False),
             ('decay', 'DECAY', 0.02, 2.0, True))

# PS1200's knobs: a slice's own and the whole's (key, label, low, high, log); a slice's
# decay at its knob's end: none (as cut)
SLICE_KNOBS = (('semis', 'S PITCH', -12.0, 12.0, False), ('gain', 'S LEVEL', 0.0, 1.5, False),
               ('decay', 'S DECAY', 0.02, 2.0, True))
# (START: where the bar is cut, a beat before or after its grid's downbeat at most)
SAMPLER_KNOBS = (('shift', 'PITCH', -12.0, 12.0, False),
                 ('cutoff', 'CUTOFF', 30.0, 20000.0, True),
                 ('q', 'RES', 0.5, 8.0, True),
                 ('start', 'START', -1.0, 1.0, False))
# its filter's kinds as its selector shows them, each one's cutoff when first picked
FILTER_KINDS = ((None, 'OFF'), ('lp', 'LP'), ('hp', 'HP'), ('bp', 'BP'), ('notch', 'NOTCH'))
FILTER_FIRST = dict(lp=2000.0, hp=300.0, bp=1000.0, notch=1000.0)
SLOPE_KINDS = ((12, '12 dB'), (24, '24 dB'))
# a START turned: cut again once it rests this long (a drag's every step not cut)
RECUT_MS = 120
# what a control does, told in the header while the mouse is on it
HINTS = dict(
    step='STEP: CLICK ON/OFF  RIGHT-CLICK ACCENT  DRAG TO PAINT',
    roll='NOTES: CLICK OR DRAG TO DRAW  CLICK A NOTE TO ERASE  WHEEL MOVES IT',
    flag='CLICK ON/OFF  DRAG TO PAINT',
    slot='SLOT: CLICK PICK  DOUBLE-CLICK RENAME  DRAG MOVE  RIGHT-CLICK MENU',
    slice='SLICE: CLICK TO PICK AND HEAR (THEN CLICK OR DRAG ON STEPS)',
    select='CLICK FOR ITS CHOICES  WHEEL FOR THE NEXT',
    knob='KNOB: DRAG  SHIFT FINE  WHEEL  DOUBLE-CLICK RESET',
    ear='DRAG TO MOVE THE DEVICE',
    remove='REMOVE THE DEVICE (ASKED IN A MENU)',
    menu='PRESETS: LOAD, SAVE, DELETE',
    addslot='ADD A SLOT',
    play='PLAY: JOINS ON THE NEXT SIXTEENTH',
    kit='KIT: THIS SLOT  SHIFT-CLICK ALL SLOTS',
    grab='GRAB THE BAR PLAYING FROM THE SOURCE BELOW',
    grab_from='WHERE GRAB TAKES ITS BAR FROM',
    mono='MONO: EACH SLICE CUTS THE ONE BEFORE',
    crunch='12 BIT: AN OLD SAMPLER GRIT',
    reverse='REVERSE THE PICKED SLICE',
    mode='ACC: CLICKS ON STEPS SET ACCENTS',
    roll_open='NOTES: CLICK TO EDIT THEM IN THE PIANO ROLL',
    fold='FOLD OR OPEN THE DEVICE',
    insert='INSERTS (ITS MIXER CHANNEL\'S): CLICK OPENS ITS KNOBS  RIGHT-CLICK MENU',
    synth_tab='A PAGE OF ITS KNOBS',
    synth_move='EVERY NOTE MOVED: AN OCTAVE, A SEMITONE, A STEP',
    synth_mono='MONO: ONE NOTE AT A TIME, SLID TO WITH THE GLIDE',
    synth_on='THIS OSCILLATOR ON OR OFF',
    mp_pad='PAD: CLICK TO PICK AND HEAR  ITS STEPS ARE THE ROW LIT',
    mp_sample='SAMPLE THE BEATS PLAYING ON THE DECK INTO THE PICKED PAD',
    mp_load='LOAD A FILE INTO THE PICKED PAD',
    mp_row='A PAD\'S ROW: CLICK TO PICK IT',
    pad_mute='MUTE THIS SLOT', pad_solo='SOLO THIS SLOT')


GRAIN = []


def get_grain():
    '''a brushed metal's grain (light streaks along its width, on nothing: drawn over a
    plate), made once'''
    if not GRAIN:
        width, height = 512, 128
        rng = numpy.random.RandomState(7)
        rows = rng.uniform(0, 1, (height, 1))
        streaks = numpy.convolve(rng.uniform(0, 1, width + 64), numpy.ones(32) / 32,
                                 'same')[32:32 + width]
        alpha = numpy.clip(rows * 6 + streaks[None, :] * 3 - 3, 0, 255).astype(numpy.uint8)
        rgb = numpy.full((height, width, 3), 255, dtype=numpy.uint8)
        bitmap = wx.Bitmap.FromBufferRGBA(width, height, numpy.dstack([rgb, alpha]).tobytes())
        GRAIN.append(bitmap)
    return GRAIN[0]


def format_value(key, value):
    # a knob's readout
    if value is None:
        return 'OFF'
    if key in ('pitch', 'noise_freq', 'cutoff', 'env'):
        return '%.1fk' % (value / 1000.0) if value >= 1000 else '%d' % round(value)
    if key in ('sweep', 'decay', 'noise_decay', 'env_decay'):
        return '%d ms' % round(value * 1000) if value < 1.0 else '%.2f s' % value
    if key in ('bend', 'semis', 'shift'):
        return '%+d' % round(value) if key != 'bend' else '%d st' % round(value)
    if key in ('noise_q', 'q'):
        return '%.1f' % value
    return '%d%%' % round(value * 100)


class InstrumentsPanel(RackModule):

    TITLE = 'INSTRUMENTS'
    PREFERENCE = 'instruments_panel'
    # (its devices drawn by it: a part of its own, no chips to fold)
    PARTS = (('rack', 'RACK', DEV_HEIGHT),)

    def __init__(self, parent):
        # (before the module's: it draws once made)
        self.steps = {}
        self.picked = {}
        # what a click on a step does besides on and off: RT909's accent (its key)
        self.modes = {}
        self.drag = None
        # steps painted by a drag: (device, row, mode, the state the first click left,
        # the steps passed); BT303's notes drawn by one: (device, place or erase, the
        # degree each step passed was set to)
        self.paint = None
        self.roll_paint = None
        # a device or a slot being moved by a drag: (device, its slot or None, the row or
        # place it would go to)
        self.moving = None
        self.move_from = 0
        self.shift_held = False
        self.pressed = None
        # the preset LCD the arrow keys walk (device, 'sound' or 'pattern'): the last one
        # clicked or loaded, till a click outside the rack or Esc; each one's preset loaded
        # last (its full name, built in or not)
        self.keyed = None
        self.walked = {}
        # a PS1200's START being turned (its offset, seconds) and the cut waiting for it
        self.offsets = {}
        self.recut = None
        # each device's insert being edited here (its index in its chain)
        self.fx_picked = {}
        # a synth's knob page shown, MP-60's beats a sample takes
        self.synth_pages = {}
        self.pad_beats = {}
        # each device's picture (GetDeviceKey: (key, bitmap, hits)), every edit's version,
        # where each device's steps are (its playhead: x, top, bottom, a step's width,
        # steps), MP-60's pads' rects
        self.device_cache = {}
        self.version = 0
        # devices folded to their heads, devices whose inserts' knobs are open
        self.folded = set((GetPreference(self.PREFERENCE) or {}).get('folded') or [])
        self.fx_open = {}
        self.playheads = {}
        self.pad_rects = {}
        self.slot_rows = {}
        self.selectors = {}
        self.tint = '#3D8BFD'
        self.device_rects = []
        self.slot_rows = {}
        # PS1200's waveform's columns (its bar, its width): drawn every frame
        self.peaks = (None, 0, None)
        self.editor = None
        # the selectors drawn: their hit's (value, options)
        self.selectors = {}
        RackModule.__init__(self, parent)
        self.buffer.fps = 30

    def GetControl(self):
        return getattr(self.parent, 'AudioControl', None)

    def Keep(self):
        RackModule.Keep(self)
        kept = dict(self.parts, shown=self.shown, folded=sorted(self.folded))
        SetPreference(self.PREFERENCE, kept)

    def ToggleFold(self, dev):
        self.folded ^= {dev}
        self.Keep()
        self.Relayout()

    def GetDevices(self):
        control = self.GetControl()
        return list(control.GetDevices()) if control is not None else []

    @staticmethod
    def Kind(dev):
        return (dev or '').split('-')[0]

    def GetSource(self, dev):
        control = self.GetControl()
        return control.GetInstrument(dev) if control is not None else None

    def GetMade(self, dev):
        # its source, made (not playing) when not yet: set before it plays
        source = self.GetSource(dev)
        control = self.GetControl()
        if source is None and control is not None:
            source = control.SetInstrument(dev, True, start=False)
        return source

    def IsRunning(self, dev):
        source = self.GetSource(dev)
        return source is not None and source.armed

    def IsActive(self):
        return any(self.IsRunning(dev) for dev in self.GetDevices())

    def GetPicked(self, dev):
        source = self.GetSource(dev)
        if self.Kind(dev) == 'rt909':
            names = list(source.pads) if source is not None else list(instruments.PAD_NAMES)
            name = self.picked.get(dev)
            return name if name in names else (names[0] if names else None)
        if self.Kind(dev) == 'ps1200':
            return self.picked.get(dev, 'slice 1')
        if self.Kind(dev) == 'mp60':
            return self.picked.get(dev, instruments.pad_name(1))
        return None

    def GetHeardAt(self, length):
        # the step heard in a pattern this long (a synth's bars)
        control = self.GetControl()
        clock = control.SongClock() if control is not None else None
        if clock is None:
            return None
        step = 60.0 / clock['bpm'] / 4.0
        return int((clock['position'] - clock['anchor']) // step) % length

    def GetState(self):
        control = self.GetControl()
        if control is None:
            return None
        # (a control under the mouse: what it does)
        hint = self.GetHint() or self.GetKeyedHint()
        if hint:
            return (hint, False)
        if control.mixed is False:
            return ('AUDIO MIXER OFF: PLAY TURNS IT ON', True)
        clock = control.SongClock()
        if control.free_clock is not None:
            return ('%.1f BPM  ALONE' % (clock['bpm'] * clock['rate']), False)
        key = control.GetSongKeyTempo()[0]
        return ('%.1f BPM  %s' % (clock['bpm'] * clock['rate'],
                                  key if key not in ('-', ' ', '') else '--'), False)

    def GetHint(self):
        hovered = self.hovered
        if not isinstance(hovered, tuple) or len(hovered) != 2:
            return None
        kind, value = hovered
        if kind == 'key':
            action = value[0]
            if action == 'voice' and value[1][1] == 'kit':
                return HINTS['kit']
            return HINTS.get(action)
        if kind == 'knob' and value[1:] == ('sampler', 'start'):
            return 'START: WHERE THE BAR IS CUT FROM ITS DOWNBEAT  SHIFT FINER  DOUBLE-CLICK 0'
        if kind == 'step' and value[1] in ('acc', 'slide'):
            return HINTS['flag']
        if kind == 'step' and self.Kind(value[0]) == 'ps1200':
            return 'STEP: CLICK OR DRAG PUTS THE PICKED SLICE  WHEEL CHANGES IT'
        return HINTS.get(kind)

    def GetKeyedHint(self):
        if self.keyed is None:
            return None
        return '%s: UP DOWN NEXT  PAGE UP DOWN GROUP  ESC DONE' % self.keyed[1].upper()

    def GetChips(self):
        control = self.GetControl()
        swing = control.GetSwing() if control is not None else 0.5
        devices = self.GetDevices()
        playing = any(self.IsRunning(dev) for dev in devices)
        folded = devices and all(dev in self.folded for dev in devices)
        return [('add', '+ ADD', False, False),
                ('swing', 'SWING %d%%' % round(swing * 100), swing > 0.5, False),
                ('fold', 'OPEN ALL' if folded else 'FOLD ALL', False, False),
                ('play', 'STOP ALL' if playing else 'PLAY ALL', playing, False)]

    def OnChip(self, key):
        control = self.GetControl()
        if control is None:
            return
        if key == 'play':
            # (all of them from the next sixteenth together, or all stopped)
            devices = self.GetDevices()
            on = not any(self.IsRunning(dev) for dev in devices)
            for dev in devices:
                source = self.GetSource(dev)
                # (a PS1200 with nothing grabbed: not grabbing a bar of its own here)
                if on and self.Kind(dev) == 'ps1200' and (source is None or not source.pads):
                    continue
                control.SetInstrument(dev, on)
            self.Repaint()
            return
        if key == 'fold':
            devices = self.GetDevices()
            self.folded = set() if all(dev in self.folded for dev in devices) else set(devices)
            self.Keep()
            self.Relayout()
            return
        if key == 'swing':
            swings = instruments.SWINGS
            now = control.GetSwing()
            at = min(range(len(swings)), key=lambda k: abs(swings[k] - now))
            control.SetSwing(swings[(at + 1) % len(swings)])
            self.Repaint()
        elif key == 'add':
            menu = wx.Menu()
            for kind in control.DEVICE_KINDS:
                name, what, _ = PLATES[kind]
                item = menu.Append(wx.ID_ANY, '%s  %s' % (name, what.title()))
                self.Bind(wx.EVT_MENU, lambda event, kind=kind: self.AddDevice(kind), item)
            self.PopupMenu(menu)
            menu.Destroy()

    def AddDevice(self, kind):
        control = self.GetControl()
        if control is not None and control.AddDevice(kind):
            self.Relayout()

    def Relayout(self):
        # (its height with its devices: the rack, the player and the window with it)
        self.version += 1
        self.frame = None
        self.parent.Rack.Relayout()

    # its height, its devices' places

    def GetDeviceHeight(self, dev):
        if dev in self.folded:
            return FOLDED_HEIGHT
        band = FX_BAND if self.fx_open.get(dev) else FX_ROW
        if self.Kind(dev) == 'rt909':
            source = self.GetSource(dev)
            count = len(source.pads) if source is not None else SLOTS_SEEN
            return DEV_HEIGHT + band + max(count - SLOTS_SEEN, 0) * ROW
        if self.Kind(dev) == 'mp60':
            return DEV_HEIGHT + band + PAD_EXTRA
        return DEV_HEIGHT + band

    def GetHeight(self):
        if self.shown is False:
            return 0
        devices = self.GetDevices()
        return HEADER + 6 + sum(self.GetDeviceHeight(dev) + DEV_GAP for dev in devices)\
            + (0 if devices else 40)

    def DirectDraw(self):
        # drawn at the clock's frames only when what it shows moves (a step heard, the
        # mouse over another control, a drag); its edits draw it at once (Repaint)
        frame = (tuple((dev, self.IsRunning(dev)) for dev in self.GetDevices()),
                 self.GetHeardStep() if self.IsActive() else None, self.hovered, self.drag,
                 self.moving, self.pressed, self.keyed, tuple(self.GetSize()),
                 self.IsShown())
        if frame == getattr(self, 'frame', None) and self.buffer.bmp is not None:
            return
        lap = self.buffer.lap
        RackModule.DirectDraw(self)
        # (kept only when drawn: the base skips a frame asked too soon)
        self.frame = frame if self.buffer.lap != lap else None

    def Repaint(self):
        # at once (an edit's: drawn when idle, a click felt late); its devices drawn again
        # (the mouse moved alone: only the one under it, GetDeviceKey)
        if not getattr(self, 'hover_only', False):
            self.version += 1
        self.frame = None
        self.reInitBuffer = False
        if self.IsShown() and self.GetSize()[0] > 0:
            self.InitBuffer()
            self.Refresh(False)
            self.Update()

    def GetHeardStep(self):
        control = self.GetControl()
        clock = control.SongClock() if control is not None else None
        if clock is None:
            return None
        step = 60.0 / clock['bpm'] / 4.0
        return int((clock['position'] - clock['anchor']) // step) % instruments.STEPS

    # drawn

    def SetRectDraw(self, dc):
        st = self.parent.st
        w, h = self.GetSize()
        self.hits = []
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        gc.SetPen(wx.Pen(colour(st.RACK_EDGE_COLOR), 1))
        gc.StrokeLine(0, 0.5, w, 0.5)
        gc.StrokeLine(0, h - 0.5, w, h - 0.5)
        self.DrawHeader(dc, gc, w)
        self.device_rects = []
        y = HEADER + 6
        devices = self.GetDevices()
        if not devices:
            gc.SetFont(get_font(uikit.LABEL), colour(st.RACK_LABEL_COLOR))
            gc.DrawText('NO DEVICES: + ADD ONE', 16, y + 8)
            return
        # each device's picture kept (GetDeviceKey): drawn again only when what it shows
        # changed (all of them drawn at every step heard, 34 ms for five: the clicks and
        # the mouse felt late); the step heard laid over them (DrawPlayheads)
        for dev in list(self.device_cache):
            if dev not in devices:
                del self.device_cache[dev]
        # (put down by the DC: a GraphicsContext's drawing of a bitmap this big took ms)
        del gc
        for dev in devices:
            height = self.GetDeviceHeight(dev)
            self.device_rects.append((dev, y, height))
            key = self.GetDeviceKey(dev, y, w, height)
            cached = self.device_cache.get(dev)
            if cached is None or cached[0] != key:
                cached = (key,) + self.RenderDevice(dev, y, w, height)
                self.device_cache[dev] = cached
            dc.DrawBitmap(cached[1], 0, y)
            self.hits.extend(cached[2])
            y += height + DEV_GAP
        gc = wx.GraphicsContext.Create(dc)
        self.DrawPlayheads(gc)
        if self.moving is not None and self.moving[1] is None and self.moving[2] is not None:
            # where a moved device would go: a line between them
            at = self.moving[2]
            line = HEADER + 6 + sum(r[2] + DEV_GAP for r in self.device_rects[:at]) - 3
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(uikit.ui().ACCENT)).Width(2)))
            gc.StrokeLine(8, line, w - 8, line)

    def RenderDevice(self, dev, y, width, height):
        # (its picture, its hits: as drawn where it is, in the panel's coordinates)
        bitmap = wx.Bitmap(int(width), int(height))
        dc = wx.MemoryDC(bitmap)
        dc.SetBackground(wx.Brush(self.parent.st.RACK_BG_COLOR))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        gc.Translate(0, -y)
        start = len(self.hits)
        self.DrawDevice(gc, dev, 8, y, width - 16, height, None)
        hits = self.hits[start:]
        del self.hits[start:]
        del gc
        dc.SelectObject(wx.NullBitmap)
        return bitmap, hits

    def DevOf(self, thing, devices=None):
        # the device a hit, a drag, a hover is on (its id inside it), None: none
        devices = self.GetDevices() if devices is None else devices
        if isinstance(thing, str):
            return thing if thing in devices else None
        if isinstance(thing, tuple):
            for item in thing:
                found = self.DevOf(item, devices)
                if found is not None:
                    return found
        return None

    def GetDeviceKey(self, dev, y, width, height):
        '''what a device's picture shows past its sounds and settings (those: version, moved
        by every edit and click): where it is, it playing, the mouse on it, its drag'''
        devices = self.GetDevices()

        def mine(thing):
            return thing if thing is not None and self.DevOf(thing, devices) == dev else None
        roll = getattr(self.parent, 'PianoRoll', None)
        rolled = roll is not None and roll.shown and roll.target == dev
        return (self.version, y, width, height, self.IsRunning(dev), mine(self.hovered),
                mine(self.drag), mine(self.moving), mine(self.pressed), mine(self.keyed),
                mine(self.paint), mine(self.roll_paint), rolled)

    def DrawPlayheads(self, gc):
        # the step heard over each playing device's steps (a light column), MP-60's pads
        # lit as they play
        for dev, top, height in self.device_rects:
            place = self.playheads.get(dev)
            if place is None or not self.IsRunning(dev):
                continue
            x0, head, bottom, column, length = place
            heard = self.GetHeardAt(length)
            if heard is None:
                continue
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(255, 255, 255, 38))))
            gc.DrawRectangle(x0 + heard * column, head, max(column - 1, 1.5), bottom - head)
            pads = self.pad_rects.get(dev)
            source = self.GetSource(dev)
            if pads and source is not None:
                # (a pad playing: its rubber tinted in the device's colour, even, and a bar
                # of it along its bottom: lit, not by a haze)
                tint = colour(self.GetTint(dev))
                for name, (px, py, pw, ph) in pads.items():
                    steps = source.pattern.get(name)
                    if not steps or not steps[heard % len(steps)]:
                        continue
                    gc.SetPen(wx.NullGraphicsPen)
                    gc.SetBrush(gc.CreateBrush(wx.Brush(wx.Colour(tint.Red(), tint.Green(),
                                                                  tint.Blue(), 70))))
                    gc.DrawRoundedRectangle(px + 0.5, py + 0.5, pw - 1, ph - 1, 4)
                    gc.SetBrush(gc.CreateBrush(wx.Brush(tint)))
                    gc.DrawRoundedRectangle(px + 4, py + ph - 4, pw - 8, 2, 1)

    def GetTint(self, dev):
        tokens = uikit.ui()
        tint = PLATES[self.Kind(dev)][2]
        return {'warn': tokens.WARN, 'accent': tokens.ACCENT}.get(tint, tint)

    def DrawDevice(self, gc, dev, x, y, width, height, heard):
        st = self.parent.st
        kind = self.Kind(dev)
        self.tint = self.GetTint(dev)
        source = self.GetSource(dev)
        running = self.IsRunning(dev)
        folded = dev in self.folded
        ground = colour(st.RACK_BG_COLOR)
        face = uikit.mix(ground, (255, 255, 255), 0.05)
        dark = uikit.mix(ground, (0, 0, 0), 0.6)
        # its plate: lit from above (lighter at its top, a highlight along its top edge, a
        # shadow along its bottom), its head a band of its own
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(dark).Width(1)))
        gc.SetBrush(gc.CreateLinearGradientBrush(
            x, y, x, y + height, uikit.mix(face, (255, 255, 255), 0.025),
            uikit.mix(face, (0, 0, 0), 0.12)))
        gc.DrawRoundedRectangle(x + 0.5, y + 0.5, width - 1, height - 1, uikit.RADIUS + 1)
        # (a faint brushed grain over it: a flat fill read as a drawing, not a part)
        grain = get_grain()
        gw, gh = grain.GetSize()
        for tx in range(int(x) + 1, int(x + width) - 1, gw):
            for ty in range(int(y) + 1, int(y + height) - 1, gh):
                gc.DrawBitmap(grain, tx, ty, min(gw, x + width - 1 - tx),
                              min(gh, y + height - 1 - ty))
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateLinearGradientBrush(
            x, y, x, y + HEAD, uikit.mix(face, (255, 255, 255), 0.06),
            uikit.mix(face, (255, 255, 255), 0.01)))
        gc.DrawRoundedRectangle(x + 1, y + 1, width - 2, HEAD - 3, uikit.RADIUS)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(face, (255, 255, 255), 0.12))
                               .Width(1)))
        gc.StrokeLine(x + 4, y + 1.5, x + width - 4, y + 1.5)
        # its ears: a screw at each end (one when folded), the left one's grip, the right
        # one's remove
        ear = uikit.mix(face, (255, 255, 255), 0.03)
        screws = (y + height / 2.0,) if folded else (y + 9, y + height - 9)
        for ex, hit in ((x, ('ear', dev)), (x + width - EAR, ('remove', dev))):
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(ear)))
            gc.DrawRectangle(ex + 1, y + 1, EAR - 1, height - 2)
            if not folded:
                for sy in screws:
                    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(dark).Width(1)))
                    gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.mix(face, (255, 255, 255),
                                                                  0.14))))
                    gc.DrawEllipse(ex + EAR / 2.0 - SCREW, sy - SCREW, SCREW * 2, SCREW * 2)
                    gc.StrokeLine(ex + EAR / 2.0 - SCREW + 1, sy, ex + EAR / 2.0 + SCREW - 1, sy)
            reach = (y + 4, height - 8) if folded else (y + 16, height - 32)
            self.hits.append((wx.Rect(int(ex), int(reach[0]), EAR, int(reach[1])), hit[0],
                              hit[1]))
        mid = y + (HEAD / 2.0 if folded else height / 2.0)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(
            st.RACK_TEXT_COLOR if self.hovered == ('ear', dev) else st.RACK_LABEL_COLOR))
            .Width(1)))
        for dy in (-4, 0, 4):
            gc.StrokeLine(x + 5, mid + dy + 0.5, x + EAR - 4, mid + dy + 0.5)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(
            st.RACK_TEXT_COLOR if self.hovered == ('remove', dev) else st.RACK_LABEL_COLOR))
            .Width(1.5)))
        cx = x + width - EAR / 2.0
        gc.StrokeLine(cx - 3, mid - 3, cx + 3, mid + 3)
        gc.StrokeLine(cx - 3, mid + 3, cx + 3, mid - 3)
        inner = x + EAR + 10
        inner_width = width - 2 * EAR - 20
        # its head: its fold, its LED, its name, what it is; its colour's stripe under it
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(colour(self.tint))))
        gc.DrawRectangle(x + EAR, y + HEAD - 4, width - 2 * EAR, 2)
        fold = ('fold', dev)
        fy = y + (HEAD - 4 - FOLD_KEY) / 2.0
        face_, ink = uikit.get_face(on=False, hover=self.hovered == fold)
        uikit.draw_face(gc, (inner, fy, FOLD_KEY, FOLD_KEY), face_)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1.5)))
        ax, ay = inner + FOLD_KEY / 2.0, fy + FOLD_KEY / 2.0
        if folded:
            gc.StrokeLine(ax - 2, ay - 4, ax + 2, ay)
            gc.StrokeLine(ax + 2, ay, ax - 2, ay + 4)
        else:
            gc.StrokeLine(ax - 4, ay - 2, ax, ay + 2)
            gc.StrokeLine(ax, ay + 2, ax + 4, ay - 2)
        self.hits.append((wx.Rect(int(inner), int(fy), FOLD_KEY, FOLD_KEY), 'fold', dev))
        lx = inner + FOLD_KEY + 8
        led = colour(self.tint) if running else uikit.mix(face, (0, 0, 0), 0.4)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(dark).Width(1)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(led)))
        gc.DrawEllipse(lx, y + HEAD / 2.0 - 5, 8, 8)
        control = self.GetControl()
        name = control.GetDeviceLabel(dev) if control is not None else dev
        gc.SetFont(get_font(14, bold=True), colour(st.RACK_TEXT_COLOR))
        nw, nh = gc.GetTextExtent(name)[:2]
        gc.DrawText(name, lx + 16, y + (HEAD - 4 - nh) / 2.0)
        what = PLATES[kind][1]
        gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
        ww, wh = gc.GetTextExtent(what)[:2]
        gc.DrawText(what, lx + 16 + nw + 8, y + (HEAD - 4 - wh) / 2.0 + 1)
        # PLAY at its right, its presets before it
        right = inner + inner_width
        self.DrawKey(gc, (int(right - KEY_WIDTH), int(y + 4), KEY_WIDTH, HEAD - 10),
                     'STOP' if running else 'PLAY', running, ('play', dev), tint=None)
        px = right - KEY_WIDTH - 8
        for what_ in ('pattern', 'sound'):
            label = getattr(source, what_ + '_name', None) if source is not None else None
            text = '%s  %s' % (what_.upper(), (label or 'OWN')[:18])
            px = self.DrawPresetButton(gc, dev, what_, text, px, y + 5)
            px -= 6
        if folded:
            self.playheads.pop(dev, None)
            return
        if kind == 'rt909':
            self.DrawDrums(gc, dev, source, inner, y, inner_width, heard)
        elif kind == 'ps1200':
            self.DrawSampler(gc, dev, source, inner, y, inner_width, heard)
        elif kind in ('sy4', 'vr1'):
            self.DrawSynth(gc, dev, source, inner, y, inner_width)
        elif kind == 'mp60':
            self.DrawPadSampler(gc, dev, source, inner, y, inner_width, heard)
        else:
            self.DrawBass(gc, dev, source, inner, y, inner_width, heard)
        band = FX_BAND if self.fx_open.get(dev) else FX_ROW
        self.DrawInserts(gc, dev, inner, y + height - band - 4, inner_width)

    # its MIXER channel's inserts (the same chain: put in, edited, taken out from here or
    # there, either one shown as the other has it)

    def GetInserts(self, dev):
        # [(its index in the chain, its slot)]; None: none can be (the audio mixer off)
        control = self.GetControl()
        if control is None or not control.mixed:
            return None
        # (not made yet: none; made by its first insert)
        if control.GetInstrument(dev) is None:
            return []
        return control.GetInserts(dev)

    def GetPickedInsert(self, dev):
        # (its index, its slot): the one picked, else its first; None: none
        inserts = self.GetInserts(dev) or []
        picked = self.fx_picked.get(dev)
        for index, slot in inserts:
            if index == picked:
                return index, slot
        return inserts[0] if inserts else None

    def DrawInserts(self, gc, dev, x, top, width):
        '''its inserts' band: a line over it; INSERTS, a chip each (its effect's name, OFF
        when bypassed; the one edited here edged in the device's colour), a + for another;
        BYPASS and REMOVE for the edited one under them; its knobs at the right'''
        st = self.parent.st
        left, gx, cell, rx, rw = self.GetGrid(x, width)
        ground = colour(st.RACK_BG_COLOR)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(ground, (255, 255, 255), 0.1))
                               .Width(1)))
        gc.StrokeLine(x, top - 0.5, x + width, top - 0.5)
        ry = top + 6
        self.DrawRowLabel(gc, 'INSERTS', x, ry, SWITCH_HEIGHT, bold=True)
        inserts = self.GetInserts(dev)
        if inserts is None:
            gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
            gc.DrawText('THE AUDIO MIXER IS OFF: PLAY TURNS IT ON', gx, ry + 4)
            return
        picked = self.GetPickedInsert(dev)
        most = self.GetControl().INSERTS_MOST
        room = left - NAME_WIDTH
        cw = min(110.0, (room - KEY_GAP * (most - 1)) / float(most))
        lcd = colour(st.LCD_BG_COLOR)
        # (its inserts, then one + while there is room: empty places not drawn, clutter)
        rows = [(index, slot) for index, slot in inserts]
        if len(rows) < most:
            rows.append((None, None))
        for k in range(len(rows)):
            cx = gx + k * (cw + KEY_GAP)
            rect = (cx, ry, cw, SWITCH_HEIGHT)
            if k < len(rows):
                index, slot = rows[k]
                hit = ('insert', (dev, index))
                if slot is not None:
                    text = effects.SHORT[slot.GetEffect()] + ('  OFF' if slot.bypass else '')
                    ink = st.RACK_LABEL_COLOR if slot.bypass else st.LCD_TEXT_COLOR
                else:
                    text, ink = '+  ADD', st.RACK_LABEL_COLOR
            else:
                hit, text, ink = None, '', st.RACK_LABEL_COLOR
            edited = picked is not None and hit is not None and hit[1][1] == picked[0]\
                and self.fx_open.get(dev)
            edge = colour(self.tint) if edited else (
                colour(st.RACK_TEXT_COLOR) if hit and self.hovered == hit else None)
            self.DrawWell(gc, (cx, ry, cw, SWITCH_HEIGHT), edge, 2 if edited else 1)
            if text:
                gc.SetFont(get_font(uikit.MICRO + 1, bold=True), colour(ink))
                tw, th = gc.GetTextExtent(text)[:2]
                gc.DrawText(text, cx + (cw - tw) / 2.0, ry + (SWITCH_HEIGHT - th) / 2.0)
            if hit is not None:
                self.hits.append((wx.Rect(int(cx), int(ry), int(cw), SWITCH_HEIGHT), 'insert',
                                  hit[1]))
        ky = ry + SWITCH_HEIGHT + 8
        # (its knobs only while one is opened: a click on its chip; a row of chips else)
        if picked is None or not self.fx_open.get(dev):
            return
        index, slot = picked
        kx = gx
        for action, label, on in (('bypass', 'BYPASS', slot.bypass), ('remove', 'REMOVE', False)):
            self.DrawKey(gc, (kx, ky, FX_KEY, SWITCH_HEIGHT), label, on,
                         ('fx', (dev, action)), size=9, tint=None, warn=on)
            kx += FX_KEY + KEY_GAP
        gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
        gc.DrawText(effects.EFFECTS[slot.GetEffect()][0], kx + 4, ky + 4)
        # its knobs: a row, packed from the left
        name = slot.GetEffect()
        knobs = effects.get_knobs(name)
        values = effects.first_values(name)
        values.update(slot.params)
        kcell = min(rw / float(max(len(knobs), 5)), KNOB_CELL)
        for k, knob in enumerate(knobs):
            cx = rx + kcell * k + kcell / 2.0
            cy = top + 20
            hit = (dev, 'insert', knob[0])
            touched = self.hovered == ('knob', hit) or (self.drag is not None and
                                                        self.drag[0] == ('knob', hit))
            self.DrawKnob(gc, cx, cy, min(max(effects.to_turn(knob, values[knob[0]]), 0.0),
                                          1.0), touched, radius=FX_KNOB, tint=self.tint,
                          ticks=11)
            label_y = cy + FX_KNOB + 2
            for line, font, ink in (
                    (effects.format_value(knob, values[knob[0]]),
                     get_font(uikit.MICRO, mono=True), st.LCD_TEXT_COLOR),
                    (knob[1], get_font(uikit.MICRO, bold=True), st.RACK_LABEL_COLOR)):
                gc.SetFont(font, colour(ink))
                while len(line) > 1 and gc.GetTextExtent(line)[0] > kcell - 3:
                    line = line[:-1]
                tw, th = gc.GetTextExtent(line)[:2]
                gc.DrawText(line, cx - tw / 2.0, label_y)
                label_y += th
            self.hits.append((wx.Rect(int(cx - kcell / 2.0), int(cy - FX_KNOB - 8),
                                      int(kcell), int(FX_BAND - 4)), 'knob', hit))

    def ShowInsertMenu(self, dev, index):
        # (MIXER's menu: an effect to put in; one's: another, bypass, remove)
        mixer = getattr(self.parent, 'Mixer', None)
        if mixer is not None:
            if self.GetControl().GetInstrument(dev) is None:
                self.GetMade(dev)
            mixer.ShowInsertMenu(dev, index)
        self.Repaint()

    def OpenInserts(self, dev, on):
        if bool(self.fx_open.get(dev)) != on:
            self.fx_open[dev] = on
            self.Relayout()

    def DoInsertKey(self, dev, action):
        picked = self.GetPickedInsert(dev)
        mixer = getattr(self.parent, 'Mixer', None)
        if picked is None or mixer is None:
            return
        if action == 'bypass':
            mixer.Bypass(dev, picked[0])
        else:
            mixer.RemoveInsert(dev, picked[0])
            self.fx_picked.pop(dev, None)
            if not self.GetInserts(dev):
                self.OpenInserts(dev, False)

    def PickInsert(self, dev, index):
        # (MIXER's editor on the same one)
        self.fx_picked[dev] = index
        mixer = getattr(self.parent, 'Mixer', None)
        if mixer is not None:
            mixer.editing = (dev, index)
            mixer.Repaint()

    # SY-4 and VR-1: their notes seen (the piano roll edits them), every note moved, their
    # patch's knobs on pages

    def DrawSynth(self, gc, dev, source, x, y, width):
        st = self.parent.st
        left, gx, cell, rx, rw = self.GetGrid(x, width)
        grid = cell * instruments.STEPS
        roll = getattr(self.parent, 'PianoRoll', None)
        rolled = roll is not None and roll.shown and roll.GetTarget() == dev
        kx = x
        self.DrawKey(gc, (kx, y + CT, 92, KEY_HEIGHT), 'PIANO ROLL', rolled, ('roll_open', dev),
                     tint=None)
        kx += 92 + KEY_GAP
        if source is None:
            return
        mono = bool(source.patch.get('mono'))
        self.DrawKey(gc, (kx, y + CT, 64, KEY_HEIGHT), 'MONO', mono, ('synth_mono', dev))
        kx += 64 + KEY_GAP
        self.DrawSelector(gc, (kx, y + CT + 1, 86, SWITCH_HEIGHT), 'BARS', source.bars,
                          [(b, str(b)) for b in instruments.SYNTH_BARS], ('synth_bars', (dev,)))
        # its notes, every bar of them, under the steps' columns (a bar a column's width
        # each sixteenth: its bars squeezed in), the step heard lit
        top = y + ROWS
        self.DrawRowLabel(gc, 'NOTES', x, top, OVERVIEW_HEIGHT, bold=True)
        lcd = colour(st.LCD_BG_COLOR)
        hovered = self.hovered == ('roll_open', dev)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(self.tint) if hovered else
                                                  uikit.mix(lcd, (255, 255, 255), 0.12))
                               .Width(1)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(lcd)))
        self.DrawWell(gc, (gx, top, grid, OVERVIEW_HEIGHT), colour(self.tint) if hovered else None)
        self.hits.append((wx.Rect(int(gx), int(top), int(grid), OVERVIEW_HEIGHT), 'roll_open',
                          dev))
        length = source.GetLength()
        column = (grid - 4) / float(length)
        heard = None
        self.playheads[dev] = (gx + 2, top + 1, top + OVERVIEW_HEIGHT - 1, column, length)
        for k in range(1, length):
            if k % 4:
                continue
            ink = uikit.mix(lcd, (255, 255, 255), 0.16 if k % 16 == 0 else 0.05)
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1)))
            gc.StrokeLine(gx + 2 + k * column, top + 3, gx + 2 + k * column,
                          top + OVERVIEW_HEIGHT - 3)
        if heard is not None:
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.mix(lcd, (255, 255, 255), 0.12))))
            gc.DrawRectangle(gx + 2 + heard * column, top + 1, max(column, 1.5),
                             OVERVIEW_HEIGHT - 2)
        notes = source.notes
        if notes:
            low = min(note[0] for note in notes) - 1
            high = max(note[0] for note in notes) + 1
            if high - low < 12:
                low -= (12 - (high - low)) // 2
                high = low + 12
            row = (OVERVIEW_HEIGHT - 8) / float(high - low + 1)
            gc.SetPen(wx.NullGraphicsPen)
            for midi, start, held, velocity in notes:
                playing = heard is not None and start <= heard < start + held
                ink = colour('#F2F2F2') if playing else uikit.mix(
                    colour(self.tint), lcd.Get()[:3], 0.15 + 0.35 * (1.0 - velocity))
                gc.SetBrush(gc.CreateBrush(wx.Brush(ink)))
                ny = top + 4 + (high - midi) * row
                gc.DrawRoundedRectangle(gx + 2 + start * column + 0.5, ny,
                                        max(held * column - 1.0, 1.5), max(row - 1.0, 1.5), 1.0)
        else:
            gc.SetFont(get_font(uikit.LABEL), colour(st.LCD_TEXT_COLOR))
            text = 'NO NOTES: CLICK TO DRAW THEM'
            tw, th = gc.GetTextExtent(text)[:2]
            gc.DrawText(text, gx + (grid - tw) / 2.0, top + (OVERVIEW_HEIGHT - th) / 2.0)
        # every note moved
        my = top + OVERVIEW_HEIGHT + 6
        self.DrawRowLabel(gc, 'MOVE', x, my, SWITCH_HEIGHT, bold=True)
        mx = gx
        for label, semis, steps in (('-OCT', -12, 0), ('+OCT', 12, 0), ('-1', -1, 0),
                                    ('+1', 1, 0), ('< STEP', 0, -1), ('STEP >', 0, 1)):
            self.DrawKey(gc, (mx, my, MOVE_KEY, SWITCH_HEIGHT), label, False,
                         ('synth_move', (dev, semis, steps)), size=9, tint=None)
            mx += MOVE_KEY + 4
        self.DrawSynthKnobs(gc, dev, source, rx, y, rw)

    def DrawSynthKnobs(self, gc, dev, source, x, y, width):
        # its pages' tabs at the left (an oscillator's LED lit when it is on), the page's
        # sections at their right
        st = self.parent.st
        page = self.synth_pages.get(dev, 'osc0')
        ty = y + CT - 4
        for key, label in SYNTH_PAGES:
            on = key == page
            rect = (x, ty, TAB_WIDTH, TAB_HEIGHT)
            hit = ('synth_tab', (dev, key))
            face, ink = uikit.get_face(on=False, hover=self.hovered == hit)
            uikit.draw_face(gc, rect, face)
            if on:
                gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(self.tint)).Width(1.5)))
                gc.SetBrush(wx.TRANSPARENT_BRUSH)
                gc.DrawRoundedRectangle(x + 0.75, ty + 0.75, TAB_WIDTH - 1.5, TAB_HEIGHT - 1.5,
                                        uikit.RADIUS)
            font = get_font(9, bold=True)
            gc.SetFont(font, colour(self.tint) if on else ink)
            tx = x + 8
            if key.startswith('osc'):
                lit = source.patch['osc'][int(key[3])].get('on')
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(self.tint) if lit else
                                                    uikit.mix(face, (0, 0, 0), 0.45))))
                gc.DrawEllipse(x + 5, ty + TAB_HEIGHT / 2.0 - 2.5, 5, 5)
                tx = x + 14
            gc.DrawText(label, tx, uikit.get_caps_top(font, ty, TAB_HEIGHT))
            self.hits.append((wx.Rect(*[int(v) for v in rect]), 'synth_tab', (dev, key)))
            ty += TAB_HEIGHT + 3
        sx = x + TAB_WIDTH + 8
        self.DrawKnobSections(gc, self.GetSynthSections(dev, source, page), sx, y + CT - 4,
                              width - TAB_WIDTH - 8)

    def SynthKnob(self, dev, source, path):
        spec = SYNTH_SPECS[path[-1]]
        value = source.GetParam(path)
        return (('knob', (dev, 'synth', path)), spec[0], self.SynthTurn(spec, value),
                self.SynthText(path[-1], value))

    def SynthTurn(self, spec, value):
        _, low, high, log, _ = spec
        if log:
            return math.log(max(value, low) / low) / math.log(high / low)
        return (value - low) / float(high - low)

    def SynthValue(self, spec, turn):
        _, low, high, log, whole = spec
        turn = min(max(turn, 0.0), 1.0)
        value = low * (high / low) ** turn if log else low + (high - low) * turn
        return int(round(value)) if whole else value

    def SynthText(self, key, value):
        if key in ('octave', 'semi'):
            return '%+d' % value if value else '0'
        if key == 'fine':
            return '%+d ct' % round(value)
        if key == 'voices':
            return '%d' % value
        if key == 'fm':
            return '%.2f' % value
        if key == 'cutoff':
            return '%.1fk' % (value / 1000.0) if value >= 1000 else '%d' % round(value)
        if key == 'env':
            return '%+.1f oct' % value
        if key in ('a', 'd', 'r', 'glide'):
            return '%d ms' % round(value * 1000) if value < 1.0 else '%.2f s' % value
        if key == 'rate':
            return synth.LFO_RATE_NAMES[int(value)]
        if key == 'depth':
            return '%+d%%' % round(value * 100)
        return '%d%%' % round(value * 100)

    def GetSynthSections(self, dev, source, page):
        patch = source.patch
        if page.startswith('osc'):
            k = int(page[3])
            osc = patch['osc'][k]
            on = bool(osc.get('on'))
            items = [('key', 'ON', on, ('synth_on', (dev, ('osc', k, 'on')))),
                     ('select', 'WAVE', osc.get('wave', 'saw'), WAVE_KINDS,
                      ('synth_sel', (dev, ('osc', k, 'wave'))))]
            items += [self.SynthKnob(dev, source, ('osc', k, key))
                      for key in ('octave', 'semi', 'fine', 'level', 'voices', 'detune',
                                  'shape', 'fm')]
            return [('OSC %d' % (k + 1), 'WHOLE DEVICE' if on else 'OFF', False, items, 5)]
        if page == 'filter':
            sections = []
            for k in range(2):
                f = patch['filters'][k]
                items = [('select', 'TYPE', f.get('kind'), FILTER_KINDS,
                          ('synth_sel', (dev, ('filters', k, 'kind')))),
                         ('select', 'SLOPE dB', f.get('slope', 12), ((12, '12'), (24, '24')),
                          ('synth_sel', (dev, ('filters', k, 'slope'))))]
                items += [self.SynthKnob(dev, source, ('filters', k, key))
                          for key in ('cutoff', 'res', 'drive', 'env')]
                sections.append(('FILTER %d' % (k + 1), 'IN A ROW' if k else 'WHOLE DEVICE',
                                 False, items, 6))
            return sections
        if page == 'env':
            return [(title, scope, False, [self.SynthKnob(dev, source, (env, key))
                                           for key in ('a', 'd', 's', 'r')], 6)
                    for env, title, scope in (('amp', 'AMP ENV', 'LEVEL'),
                                              ('mod', 'MOD ENV', 'FILTERS\' ENV'))]
        lfo = patch['lfo']
        return [('LFO', 'SYNCED TO THE BAR', False, [
            ('select', 'SHAPE', lfo.get('shape', 'sine'), LFO_SHAPES,
             ('synth_sel', (dev, ('lfo', 'shape')))),
            ('select', 'TO', lfo.get('dest', 'cutoff'), LFO_DESTS,
             ('synth_sel', (dev, ('lfo', 'dest')))),
            self.SynthKnob(dev, source, ('lfo', 'rate')),
            self.SynthKnob(dev, source, ('lfo', 'depth'))], 6),
            ('VOICE', 'WHOLE DEVICE', False, [
                self.SynthKnob(dev, source, ('glide',)),
                self.SynthKnob(dev, source, ('width',)),
                self.SynthKnob(dev, source, ('level',))], 6)]

    def GetSynthDefault(self, path):
        if path[0] == 'osc':
            return synth.make_osc()[path[-1]]
        if path[0] == 'filters':
            return synth.make_filter()[path[-1]]
        first = synth.make_patch()
        return first[path[0]][path[1]] if len(path) > 1 else first[path[0]]

    # MP-60: its pads' rows (the steps of every pad, each pad's sound named before it),
    # the sixteen pads at the right (lit as they play), the picked one's knobs

    def DrawPadSampler(self, gc, dev, source, x, y, width, heard):
        st = self.parent.st
        left, gx, cell, rx, rw = self.GetGrid(x, width)
        heard = heard if self.IsRunning(dev) else None
        picked = self.GetPicked(dev)
        kx = x
        for label, action, width_ in (('SAMPLE', 'mp_sample', 76), ('LOAD FILE', 'mp_load', 86)):
            self.DrawKey(gc, (kx, y + CT, width_, KEY_HEIGHT), label, False, (action, dev),
                         tint=None)
            kx += width_ + KEY_GAP
        beats = self.pad_beats.get(dev, 1)
        self.DrawSelector(gc, (kx, y + CT + 1, 96, SWITCH_HEIGHT), 'BEATS', beats,
                          [(b, str(b)) for b in instruments.SAMPLE_BEATS], ('mp_beats', (dev,)))
        if source is None:
            return
        top = y + ROWS
        names = [instruments.pad_name(k + 1) for k in range(instruments.PAD_COUNT)]
        self.playheads[dev] = (gx, top, top + instruments.PAD_COUNT * PAD_ROW, cell,
                               instruments.STEPS)
        self.pad_rects[dev] = {}
        lcd = colour(st.LCD_BG_COLOR)
        for r, name in enumerate(names):
            ry = top + r * PAD_ROW
            pad = source.pads.get(name)
            on = name == picked
            # its number in a column of its own, its sound's name after it
            gc.SetFont(get_font(uikit.MICRO, bold=True), colour(self.tint) if on else
                       colour(st.RACK_LABEL_COLOR))
            number = '%d' % (r + 1)
            nw, th = gc.GetTextExtent(number)[:2]
            gc.DrawText(number, x + 14 - nw, ry + (PAD_ROW - th) / 2.0)
            label = pad.label if pad is not None else ''
            gc.SetFont(get_font(uikit.MICRO, bold=on), colour(st.RACK_TEXT_COLOR) if on else
                       colour(st.RACK_LABEL_COLOR))
            while len(label) > 2 and gc.GetTextExtent(label)[0] > NAME_WIDTH - 30:
                label = label[:-1]
            gc.DrawText(label, x + 20, ry + (PAD_ROW - th) / 2.0)
            self.hits.append((wx.Rect(int(x), int(ry), NAME_WIDTH - 6, PAD_ROW), 'mp_row',
                              (dev, name)))
            steps = source.pattern.get(name, [0] * instruments.STEPS)
            # (the picked pad's row lit full, the others' fainter: dim)
            for k in range(instruments.STEPS):
                kx, kw = self.GetStepRect(gx, k, cell)
                self.DrawStepKey(gc, (kx, ry + 1, kw, PAD_ROW - 2), bool(steps[k]),
                                 colour(self.tint), dim=not on,
                                 hovered=self.hovered == ('step', (dev, name, k)), beat=k // 4,
                                 small=True)
                self.hits.append((wx.Rect(int(gx + k * cell), int(ry), int(cell), PAD_ROW),
                                  'step', (dev, name, k)))
        # the pads, 4 by 4 (1 at the bottom left, as an MPC's)
        px0, py0 = rx, y + CT - 4
        for k, name in enumerate(names):
            col, row = k % 4, 3 - k // 4
            px, py = px0 + col * (PAD_SIDE + PAD_GAP), py0 + row * (PAD_TALL + PAD_GAP)
            steps = source.pattern.get(name, [0] * instruments.STEPS)
            playing = heard is not None and steps[heard]
            hit = ('mp_pad', (dev, name))
            ink = colour(st.RACK_TEXT_COLOR)
            self.DrawRubberPad(gc, (px, py, PAD_SIDE, PAD_TALL), name == picked,
                               self.hovered == hit, self.pressed == hit)
            gc.SetFont(get_font(uikit.READOUT + 1, bold=True), colour(self.tint)
                       if name == picked else ink)
            gc.DrawText('%d' % (k + 1), px + 6, py + 4)
            pad = source.pads.get(name)
            if pad is not None:
                gc.SetFont(get_font(uikit.MICRO, bold=True), ink)
                text = pad.label
                while len(text) > 1 and gc.GetTextExtent(text)[0] > PAD_SIDE - 10:
                    text = text[:-1]
                th = gc.GetTextExtent(text)[1]
                gc.DrawText(text, px + 6, py + PAD_TALL - th - 4)
            self.hits.append((wx.Rect(int(px), int(py), PAD_SIDE, PAD_TALL), 'mp_pad',
                              (dev, name)))
            self.pad_rects[dev][name] = (px, py, PAD_SIDE, PAD_TALL)
        # the picked pad's knobs (REV with them)
        pad = source.pads.get(picked)
        items = []
        if pad is not None:
            values = dict(semis=12.0 * numpy.log2(pad.pitch), gain=pad.gain, decay=pad.decay)
            for spec in PAD_KNOBS:
                value = values[spec[0]]
                turn = 1.0 if value is None else instruments.to_knob(spec, value)
                items.append((('knob', (dev, 'pad', spec[0])), spec[1], turn,
                              format_value(spec[0], value)))
            items.append(('key', 'REV', pad.reverse, ('mp_reverse', dev)))
        sx = px0 + 4 * (PAD_SIDE + PAD_GAP) + 6
        self.DrawKnobSections(gc, [('PAD %s' % picked.split()[-1], 'SELECTED PAD', True, items,
                                    2)], sx, y + CT - 4, max(x + width - sx, 120))

    def DrawPresetButton(self, gc, dev, what, text, right, y):
        # an LCD of the preset loaded, its menu on a click (its right edge at right); the
        # one the arrow keys walk edged in the device's tint, its arrow up and down (not
        # by colour alone)
        st = self.parent.st
        gc.SetFont(get_font(uikit.MICRO + 1, mono=True), colour(st.LCD_TEXT_COLOR))
        tw, th = gc.GetTextExtent(text)[:2]
        w, h = tw + 24, HEAD - 12
        left = right - w
        hit = ('menu', (dev, what))
        keyed = self.keyed == (dev, what)
        if keyed:
            self.DrawWell(gc, (left, y, w, h), colour(self.GetTint(dev)), 2)
        else:
            self.DrawWell(gc, (left, y, w, h), colour(st.RACK_TEXT_COLOR)
                          if self.hovered == hit else None)
        gc.SetFont(get_font(uikit.MICRO + 1, mono=True), colour(st.LCD_TEXT_COLOR))
        gc.DrawText(text, left + 7, y + (h - th) / 2.0 + 1)
        ax, cy = left + w - 11, y + h / 2.0 + 0.5
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.LCD_TEXT_COLOR))))
        path = gc.CreatePath()
        if keyed:
            for top, tip in ((cy - 1.5, cy - 5), (cy + 1.5, cy + 5)):
                path.MoveToPoint(ax, top)
                path.AddLineToPoint(ax + 6, top)
                path.AddLineToPoint(ax + 3, tip)
                path.CloseSubpath()
        else:
            path.MoveToPoint(ax, cy - 1.5)
            path.AddLineToPoint(ax + 6, cy - 1.5)
            path.AddLineToPoint(ax + 3, cy + 2)
            path.CloseSubpath()
        gc.FillPath(path)
        self.hits.append((wx.Rect(int(left), int(y), int(w), int(h)), 'menu', (dev, what)))
        return left

    def GetGrid(self, x, width):
        '''(left column's width, its grid's x, its cell, the knobs' x, their width): one for
        every device, their sixteen steps' columns under each other (RT909's names' room
        before the grid on them all)'''
        left, rx, rw = self.GetColumns(x, width, LEFT_MOST)
        cell = min((left - NAME_WIDTH - PAD_KEYS) / float(instruments.STEPS), CELL_MOST)
        return left, x + NAME_WIDTH, cell, rx, rw

    def DrawRowLabel(self, gc, text, x, y, height, bold=False, ink=None):
        # a row's name, right against the grid (the names' column's end)
        st = self.parent.st
        gc.SetFont(get_font(9, bold=bold), ink or colour(st.RACK_LABEL_COLOR))
        tw, th = gc.GetTextExtent(text)[:2]
        gc.DrawText(text, x + NAME_WIDTH - 10 - tw, y + (height - th) / 2.0)

    def GetColumns(self, x, width, left_most):
        # (its left column's width: its steps' at most; the knobs' column the rest)
        left = min(left_most, int(width * 0.58))
        return left, x + left + 24, max(x + width - (x + left + 24), 120)

    def DrawDrums(self, gc, dev, source, x, y, width, heard):
        st = self.parent.st
        left, rx, rw = self.GetColumns(x, width, LEFT_MOST)
        pattern = source.pattern if source is not None else instruments.make_pattern()
        pads = source.pads if source is not None else {}
        cell = min((left - NAME_WIDTH - PAD_KEYS) / float(instruments.STEPS), CELL_MOST)
        picked = self.GetPicked(dev)
        heard = heard if self.IsRunning(dev) else None
        self.DrawKey(gc, (x, y + CT, SMALL_KEY, KEY_HEIGHT), 'ACC',
                     self.modes.get(dev) == 'accent', ('mode', (dev, 'accent')))
        names = list(pattern)
        rows = []
        for r, name in enumerate(names):
            ry = y + ROWS + r * ROW
            rows.append((name, ry))
            pad = pads.get(name)
            label = pad.label if pad is not None else name.upper()
            on = name == picked
            # its name's strip: picked, lit in its colour and bold (not by colour alone)
            ground = colour(st.METER_OFF_COLOR)
            strip = uikit.mix(ground, colour(self.tint).Get()[:3], 0.22) if on else ground
            if self.hovered == ('slot', (dev, name)):
                strip = uikit.mix(strip, (255, 255, 255), 0.08)
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(strip)))
            gc.DrawRoundedRectangle(x, ry + 1, NAME_WIDTH - 6, ROW - 3, 2)
            gc.SetBrush(gc.CreateBrush(wx.Brush(colour(self.tint) if on
                                                else uikit.mix(ground, (255, 255, 255), 0.15))))
            gc.DrawRectangle(x, ry + 1, 3, ROW - 3)
            gc.SetFont(get_font(uikit.LABEL, bold=on),
                       colour(st.RACK_TEXT_COLOR if on else st.RACK_LABEL_COLOR))
            text = label
            while len(text) > 1 and gc.GetTextExtent(text)[0] > NAME_WIDTH - 14:
                text = text[:-1]
            th = gc.GetTextExtent(text)[1]
            gc.DrawText(text, x + 7, ry + (ROW - 2 - th) / 2.0)
            self.hits.append((wx.Rect(int(x), int(ry), NAME_WIDTH - 6, ROW), 'slot', (dev, name)))
            heard_pad = source is None or source.IsHeard(name)
            self.DrawCells(gc, x + NAME_WIDTH, ry, cell, ROW, pattern[name], heard, (dev, name),
                           accents=[instruments.is_accent(v) for v in pattern[name]],
                           dim=not heard_pad)
            px = x + NAME_WIDTH + cell * instruments.STEPS + 6
            for k, (what, text) in enumerate((('mute', 'M'), ('solo', 'S'))):
                lit = source is not None and name in (source.muted if what == 'mute'
                                                      else source.soloed)
                self.DrawKey(gc, (int(px), int(ry + 1), PAD_KEY, ROW - 2), text, lit,
                             ('pad_' + what, (dev, name)), corners=('left', 'right')[k],
                             size=uikit.MICRO, warn=lit and what == 'mute', tint=None)
                px += PAD_KEY
        self.slot_rows[dev] = rows
        ay = y + ROWS + len(names) * ROW
        self.playheads[dev] = (x + NAME_WIDTH, y + ROWS, ay, cell, instruments.STEPS)
        if len(names) < instruments.SLOTS_MOST:
            hit = ('addslot', dev)
            gc.SetFont(get_font(uikit.MICRO, bold=True), colour(
                st.RACK_TEXT_COLOR if self.hovered == hit else st.RACK_LABEL_COLOR))
            gc.DrawText('+ ADD SLOT', x + 7, ay + 2)
            self.hits.append((wx.Rect(int(x), int(ay), NAME_WIDTH - 6, ROW), 'addslot', dev))
        if self.moving is not None and self.moving[0] == dev and self.moving[1] is not None\
                and self.moving[2] is not None:
            line = y + ROWS + self.moving[2] * ROW
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(self.tint)).Width(2)))
            gc.StrokeLine(x, line, x + left, line)
        # the picked slot's voice: its switches under the steps, its knobs at the right
        pad = pads.get(picked)
        voice = pad.voice if pad is not None and pad.voice is not None else\
            instruments.make_voice(**instruments.KIT_VOICES['909']['kick'])
        # its voice's choices as selectors (an LCD each: a click its menu, the wheel the
        # next; fourteen keys in a row before, half of them lit)
        sy = ay + ROW + 6
        groups = [('kit', 'KIT', instruments.KITS, ('909', '808', 'PHY')),
                  ('engine', 'ENG', instruments.ENGINES, ('ANALOG', 'MODAL'))]
        if voice['engine'] != 'modal':
            groups += [('wave', 'WAVE', instruments.WAVES, ('SINE', 'TRI', 'SAW', 'METAL')),
                       ('filter', 'FLT', instruments.FILTERS, ('LP', 'BP', 'HP')),
                       ('noise_env', 'ENV', instruments.NOISE_ENVELOPES, ('EXP', 'CLAP'))]
        # (the picked slot's, as its knobs' section is: its name before them in the
        # device's colour, they under the grid)
        if pad is not None:
            self.DrawRowLabel(gc, pad.label, x, sy, SWITCH_HEIGHT, bold=True,
                              ink=colour(self.tint))
        # (each as wide as its longest choice wants: KIT's short, ENG's ANALOG long)
        # (each as wide as its caption and its longest choice want, all of them narrowed
        # alike when the row has less room)
        room = left - NAME_WIDTH - KEY_GAP * (len(groups) - 1)
        wants = []
        for setting, caption, values, labels in groups:
            gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
            cw = gc.GetTextExtent(caption)[0]
            gc.SetFont(get_font(uikit.MICRO + 1, bold=True), colour(st.LCD_TEXT_COLOR))
            wants.append(cw + max(gc.GetTextExtent(label)[0] for label in labels) + 27)
        scale = min(room / float(sum(wants)), 1.0)
        sx = x + NAME_WIDTH
        for (setting, caption, values, labels), want in zip(groups, wants):
            sw = int(want * scale)
            self.DrawSelector(gc, (sx, sy, sw, SWITCH_HEIGHT), caption, voice.get(setting),
                              list(zip(values, labels)), ('voice', (dev, setting)))
            sx += sw + KEY_GAP
        knobs = [(('knob', (dev, 'voice', spec[0])), spec[1],
                  instruments.to_knob(spec, voice[spec[0]]),
                  format_value(spec[0], voice[spec[0]]))
                 for spec in instruments.get_knobs(voice)]
        self.DrawKnobSections(gc, [(pad.label if pad is not None else 'VOICE',
                                    'SELECTED SLOT', True, knobs, 5)], rx, y + CT - 4, rw)

    def DrawSampler(self, gc, dev, source, x, y, width, heard):
        st = self.parent.st
        left, gx, cell, rx, rw = self.GetGrid(x, width)
        grid = cell * instruments.STEPS
        kw = int(min(KEY_WIDTH, (left - 3 * KEY_GAP) / 4.0))
        kx = x
        heard = heard if self.IsRunning(dev) else None
        crunched = source is None or not source.pads\
            or any(pad.crunched for pad in source.pads.values())
        pad = self.GetPickedSlice(dev)
        # (the whole sampler's: S REV, a slice's own, in its section)
        for label, on, action in (('GRAB', False, 'grab'), ('12 BIT', crunched, 'crunch'),
                                  ('MONO', source is not None and source.mono, 'mono')):
            self.DrawKey(gc, (kx, y + CT, kw, KEY_HEIGHT), label, on, (action, dev))
            kx += kw + KEY_GAP
        top = y + ROWS
        # its LCD
        lcd = colour(st.LCD_BG_COLOR)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(lcd, (255, 255, 255), 0.12))
                               .Width(1)))
        gc.SetBrush(gc.CreateBrush(wx.Brush(lcd)))
        self.DrawWell(gc, (gx, top, grid, WAVE_HEIGHT))
        self.DrawRowLabel(gc, 'SAMPLE', x, top, WAVE_HEIGHT, bold=True)
        self.DrawRowLabel(gc, 'SLICES', x, top + WAVE_HEIGHT + 6, ROW + 2, bold=True)
        # where GRAB takes its bar from (under its steps)
        control = self.GetControl()
        sources = ['deck'] + [d for d in self.GetDevices()
                              if self.Kind(d) in ('rt909', 'bt303', 'sy4', 'vr1', 'mp60')]\
            + ['mix']
        what = source.grab_from if source is not None else 'deck'
        sy = top + WAVE_HEIGHT + 6 + ROW + 8
        options = [(key, {'deck': 'DECK', 'mix': 'MIX'}.get(key) or (
            control.GetDeviceLabel(key) if control else key)) for key in sources]
        sw = int(min(150, grid))
        self.DrawSelector(gc, (gx, sy, sw, SWITCH_HEIGHT), 'GRAB FROM', what,
                          options, ('grab_from', (dev,)))
        # its filter's kind and slope beside it (as room is)
        first = next(iter(source.pads.values())) if source is not None and source.pads\
            else None
        fx = gx + sw + 6
        for caption, value, kinds, width, hit in (
                ('FILTER', first.filter if first else None, FILTER_KINDS, 104,
                 ('filter', (dev,))),
                ('SLOPE', first.slope if first else 12, SLOPE_KINDS, 82, ('slope', (dev,)))):
            if first is None or fx + width > gx + grid:
                break
            self.DrawSelector(gc, (fx, sy, width, SWITCH_HEIGHT), caption, value, kinds, hit)
            fx += width + 6
        if source is None or source.sample is None or not source.pads:
            gc.SetFont(get_font(uikit.LABEL), colour(st.LCD_TEXT_COLOR))
            text = 'GRAB A BAR'
            tw, th = gc.GetTextExtent(text)[:2]
            gc.DrawText(text, gx + (grid - tw) / 2.0, top + (WAVE_HEIGHT - th) / 2.0)
        else:
            self.DrawWave(gc, dev, source, gx, top, grid, heard)
            cells = []
            for k in range(instruments.STEPS):
                hits = [n for n, steps in source.pattern.items() if steps[k]]
                cells.append(hits[0].replace('slice ', '') if hits else '')
            self.DrawCells(gc, gx, top + WAVE_HEIGHT + 6, cell, ROW + 2, cells, heard,
                           (dev, 'slices'))
            self.playheads[dev] = (gx, top, top + WAVE_HEIGHT + 6 + ROW + 2, cell,
                                   instruments.STEPS)
        # the picked slice's own (S REV with them), the whole sampler's under them
        mine, whole = [], []
        if pad is not None:
            values = dict(semis=12.0 * numpy.log2(pad.pitch), gain=pad.gain, decay=pad.decay)
            for spec in SLICE_KNOBS:
                value = values[spec[0]]
                turn = 1.0 if value is None else instruments.to_knob(spec, value)
                mine.append((('knob', (dev, 'slice', spec[0])), spec[1], turn,
                             format_value(spec[0], value)))
            mine.append(('key', 'S REV', pad.reverse, ('reverse', dev)))
        if source is not None and source.pads:
            for spec in SAMPLER_KNOBS:
                hit = (dev, 'sampler', spec[0])
                whole.append((('knob', hit), spec[1], self.GetKnobTurn(hit),
                              self.GetSamplerText(dev, source, spec[0])))
        per = len(SAMPLER_KNOBS)
        self.DrawKnobSections(gc, [
            ('SLICE %s' % (self.GetPicked(dev) or '').replace('slice ', ''),
             'SELECTED SLICE', True, mine, per),
            ('SAMPLER', 'ALL SLICES', False, whole, per)], rx, y + CT - 4, rw)

    def DrawWave(self, gc, dev, source, x, top, grid, heard):
        st = self.parent.st
        names = ['slice %d' % (k + 1) for k in range(instruments.STEPS)]
        playing = None
        if heard is not None:
            hits = [n for n, steps in source.pattern.items() if steps[heard]]
            playing = hits[0] if hits else None
        picked = self.GetPicked(dev)
        lcd = colour(st.LCD_BG_COLOR)
        lows, highs = self.GetPeaks(source.sample, int(grid))
        mid = top + WAVE_HEIGHT / 2.0
        half = WAVE_HEIGHT / 2.0 - 3
        width = grid / float(instruments.STEPS)
        for k, name in enumerate(names):
            sx = x + k * width
            if name == playing:
                gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.mix(lcd, (255, 255, 255), 0.12))))
                gc.SetPen(wx.NullGraphicsPen)
                gc.DrawRectangle(sx + 1, top + 1, width, WAVE_HEIGHT - 2)
            pad = source.pads.get(name)
            ink = colour(st.LCD_TEXT_COLOR) if name == picked else uikit.mix(
                colour(st.LCD_TEXT_COLOR), lcd.Get()[:3], 0.45)
            if pad is not None and pad.reverse:
                ink = colour(st.RACK_TEXT_COLOR)
            a, b = int(k * width), int((k + 1) * width)
            path = gc.CreatePath()
            scale = min(pad.gain if pad is not None else 1.0, 1.5) * half
            for px in range(a, min(b, len(lows))):
                path.MoveToPoint(x + px + 0.5, mid - highs[px] * scale)
                path.AddLineToPoint(x + px + 0.5, mid - lows[px] * scale + 1)
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(ink).Width(1)))
            gc.StrokePath(path)
            if k:
                gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(
                    uikit.mix(lcd, (255, 255, 255), 0.08 if k % 4 else 0.18)).Width(1)))
                gc.StrokeLine(int(sx) + 0.5, top + 1, int(sx) + 0.5, top + WAVE_HEIGHT - 1)
            self.hits.append((wx.Rect(int(sx), int(top), int(width), WAVE_HEIGHT), 'slice',
                              (dev, name)))
        k = names.index(picked) if picked in names else 0
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(st.LCD_TEXT_COLOR)).Width(1)))
        gc.SetBrush(wx.NullBrush)
        gc.DrawRectangle(x + k * width + 0.5, top + 0.5, width - 1, WAVE_HEIGHT - 1)

    def DrawBass(self, gc, dev, source, x, y, width, heard):
        st = self.parent.st
        tokens = uikit.ui()
        left, gx, cell, rx, rw = self.GetGrid(x, width)
        line = [instruments.read_note(note) for note in
                (list(source.line if source is not None else instruments.BASS_LINE)
                 + [None] * instruments.STEPS)[:instruments.STEPS]]
        control = self.GetControl()
        key_name = source.key if source is not None else (
            control.GetSongKeyTempo()[0] if control is not None else 'Am')
        root, minor = instruments.parse_key(key_name)
        scale = instruments.MINOR if minor else instruments.MAJOR
        top = y + CT
        off = colour(st.METER_OFF_COLOR)
        tint = colour(self.tint)
        heard = heard if self.IsRunning(dev) else None
        for row in range(ROLL_DEGREES):
            degree = ROLL_DEGREES - 1 - row
            ry = top + row * (ROLL_ROW + 1)
            # (its note's name as heard: moved with its transpose)
            moved = source.transpose if source is not None else 0
            name = NOTE_NAMES[(root + scale[degree % 7] + moved) % 12]
            gc.SetFont(get_font(9), colour(st.RACK_LABEL_COLOR))
            th = gc.GetTextExtent(name)[1]
            self.DrawRowLabel(gc, name, x, ry, ROLL_ROW)
            for k in range(instruments.STEPS):
                kx, kw = self.GetStepRect(gx, k, cell)
                note = line[k]
                shown = None if note is None else min(max(note[0], 0), ROLL_DEGREES - 1)
                on = shown == degree
                self.DrawStepKey(gc, (kx, ry, kw, ROLL_ROW), on, tint,
                                 hovered=self.hovered == ('roll', (dev, k, degree)),
                                 beat=k // 4, small=True)
                if on and note[0] != shown:
                    # (a note past the roll's rows: a dark edge on the side it is past)
                    gc.SetPen(wx.NullGraphicsPen)
                    gc.SetBrush(gc.CreateBrush(wx.Brush(colour('#0E1A2E'))))
                    edge = ry if note[0] > shown else ry + ROLL_ROW - 2
                    gc.DrawRectangle(kx + 1, edge, kw - 2, 2)
                self.hits.append((wx.Rect(int(gx + k * cell), int(ry), int(cell),
                                          ROLL_ROW + 1), 'roll',
                                  (dev, k, degree)))
        fy = top + ROLL_DEGREES * (ROLL_ROW + 1) + 4
        for name, label, index in (('acc', 'ACC', 1), ('slide', 'SLD', 2)):
            gc.SetFont(get_font(9, bold=True), colour(st.RACK_LABEL_COLOR))
            th = gc.GetTextExtent(label)[1]
            self.DrawRowLabel(gc, label, x, fy, FLAG_ROW + 2, bold=True)
            values = [bool(note is not None and note[index]) for note in line]
            self.DrawCells(gc, gx, fy, cell, FLAG_ROW + 2, [1 if v else 0 for v in values],
                           None, (dev, name), slides=values if name == 'slide' else None,
                           tint=tokens.WARN if name == 'acc' else None)
            fy += FLAG_ROW + 4
        self.playheads[dev] = (gx, top, fy - 4, cell, instruments.STEPS)
        # its whole line moved: octaves, semitones, a step later or earlier
        if source is not None:
            sy = fy + 6
            self.DrawRowLabel(gc, 'MOVE', x, sy, SWITCH_HEIGHT, bold=True)
            sx = gx
            for caption, setting, values, width in (
                    ('OCT', 'octave', instruments.BASS_OCTAVES, 76),
                    ('SEMI', 'transpose', instruments.BASS_TRANSPOSE, 84)):
                options = [(v, '%+d' % v if v else '0') for v in reversed(values)]
                self.DrawSelector(gc, (sx, sy, width, SWITCH_HEIGHT), caption,
                                  getattr(source, setting), options,
                                  ('bass_pitch', (dev, setting)))
                sx += width + KEY_GAP
            for label, steps in (('< STEP', -1), ('STEP >', 1)):
                self.DrawKey(gc, (sx, sy, 58, SWITCH_HEIGHT), label, False,
                             ('line_shift', (dev, steps)), size=9, tint=None)
                sx += 58 + KEY_GAP
        tone = source.tone if source is not None else instruments.BASS_TONE
        knobs = [(('knob', (dev, 'bass', spec[0])), spec[1],
                  instruments.to_knob(spec, tone[spec[0]]),
                  format_value(spec[0], tone[spec[0]])) for spec in instruments.BASS_KNOBS]
        self.DrawKnobSections(gc, [('TONE', 'WHOLE DEVICE', False, knobs, 3)], rx,
                              y + CT - 4, rw)

    def DrawRubberPad(self, gc, rect, picked=False, hovered=False, pressed=False):
        '''an MPC's pad: set in a well, its rubber dark and soft (lighter at its top, a line
        of light along its top edge), pressed darker and lower; the picked one ringed in
        the device's colour'''
        x, y, w, h = rect
        tint = colour(self.tint)
        self.DrawWell(gc, (x - 2, y - 2, w + 4, h + 4))
        if picked:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(tint).Width(1.5)))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            gc.DrawRoundedRectangle(x - 1, y - 1, w + 2, h + 2, 5)
        rubber = colour('#3A3D43')
        if hovered:
            rubber = uikit.mix(rubber, (255, 255, 255), 0.08)
        top, bottom = uikit.mix(rubber, (255, 255, 255), 0.1), uikit.mix(rubber, (0, 0, 0), 0.25)
        if pressed:
            top, bottom = uikit.mix(bottom, (0, 0, 0), 0.1), top
            y += 1
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(bottom, (0, 0, 0), 0.5)).Width(1)))
        gc.SetBrush(gc.CreateLinearGradientBrush(x, y, x, y + h, top, bottom))
        gc.DrawRoundedRectangle(x + 0.5, y + 0.5, w - 1, h - 1, 4)
        if not pressed:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(255, 255, 255, 34)).Width(1)))
            gc.StrokeLine(x + 4, y + 1.5, x + w - 4, y + 1.5)

    def GetStepRect(self, x, k, cell):
        # (a step's key in its column: a beat's four closer together, a wider gap between
        # beats, every device's columns the same)
        left = 1.5 + (1.0 if k % 4 == 0 else 0.0)
        right = 1.5 + (1.0 if k % 4 == 3 else 0.0)
        return x + k * cell + left, cell - left - right

    def DrawStepKey(self, gc, rect, on, tint, accent=False, dim=False, hovered=False,
                    pressed=False, beat=0, small=False):
        '''a sequencer's key, backlit: off, a dark rubber key (lighter at its top, a line of
        light along its top edge, its LED's lens dark), every other beat's a shade lighter;
        on, its face the device's colour, flat and crisp (no glow, no shine: they read as
        hazy), its lens lighter, accented a shade lighter (a dot too: not by colour alone);
        dim (a muted row's): faint; under the mouse lighter, pressed darker'''
        st = self.parent.st
        x, y, w, h = rect
        radius = 1.5 if small else 2.5
        ground = colour(st.METER_OFF_COLOR)
        face = ground if beat % 2 == 0 else uikit.mix(ground, (255, 255, 255), 0.05)
        if on and not dim:
            lit = uikit.mix(tint, (255, 255, 255), 0.18) if accent else\
                uikit.mix(tint, (0, 0, 0), 0.08)
            top, bottom = uikit.mix(lit, (255, 255, 255), 0.04), uikit.mix(lit, (0, 0, 0), 0.08)
        elif on:
            lit = uikit.mix(tint, ground.Get()[:3], 0.6)
            top, bottom = uikit.mix(lit, (255, 255, 255), 0.08), uikit.mix(lit, (0, 0, 0), 0.12)
        else:
            top, bottom = uikit.mix(face, (255, 255, 255), 0.07), uikit.mix(face, (0, 0, 0), 0.12)
        if hovered:
            top, bottom = uikit.mix(top, (255, 255, 255), 0.12), uikit.mix(bottom, (255, 255, 255),
                                                                         0.12)
        if pressed:
            top, bottom = uikit.mix(bottom, (0, 0, 0), 0.2), uikit.mix(top, (0, 0, 0), 0.2)
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(bottom, (0, 0, 0), 0.55)).Width(1)))
        gc.SetBrush(gc.CreateLinearGradientBrush(x, y, x, y + h, top, bottom))
        gc.DrawRoundedRectangle(x, y, w, h, radius)
        if not pressed and h > 6:
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(wx.Colour(255, 255, 255,
                                                                30 if on and not dim else 18))
                                   .Width(1)))
            gc.StrokeLine(x + radius, y + 1, x + w - radius, y + 1)
        if not small:
            # its LED's lens along its top
            lens = uikit.mix(tint, (255, 255, 255), 0.45) if on and not dim else\
                uikit.mix(bottom, (0, 0, 0), 0.4)
            if on and dim:
                lens = uikit.mix(tint, ground.Get()[:3], 0.4)
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(lens)))
            gc.DrawRoundedRectangle(x + 3, y + 3, max(w - 6, 2), 2, 1)
        if accent:
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.mix(tint, (0, 0, 0), 0.65))))
            gc.DrawEllipse(x + w / 2.0 - 2, y + h / 2.0, 4, 4)

    def DrawCells(self, gc, x, y, cell, row, cells, heard, hit, accents=None, slides=None,
                  dim=False, tint=None):
        '''a row of steps as a drum machine's keys (DrawStepKey); a slide a bar into the
        next; a step's text (PS1200's slice) on its key; dim: a muted slot's'''
        st = self.parent.st
        tint = colour(tint or self.tint)
        for k, value in enumerate(cells):
            on = bool(value)
            accent = on and accents is not None and accents[k]
            key = ('step', hit + (k,))
            kx, w = self.GetStepRect(x, k, cell)
            h = row - 3
            self.DrawStepKey(gc, (kx, y + 1.5, w, h), on, tint, accent, dim,
                             self.hovered == key, self.pressed == key, k // 4)
            if slides is not None and slides[k] and k + 1 < len(cells) and cells[k + 1]:
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(tint)))
                gc.DrawRectangle(kx + w - 1, y + row / 2.0 - 1, cell - w + 2, 3)
            if isinstance(value, str) and value:
                gc.SetFont(get_font(uikit.MICRO, bold=True), colour('#101114') if on and not dim
                           else colour(st.RACK_TEXT_COLOR))
                tw, th = gc.GetTextExtent(value)[:2]
                if tw < w:
                    gc.DrawText(value, kx + (w - tw) / 2.0, y + 3 + (h - 2 - th) / 2.0)
            self.hits.append((wx.Rect(int(x + k * cell), int(y), int(cell), int(row)), 'step',
                              hit + (k,)))

    def DrawKnobSections(self, gc, sections, x, y, width):
        '''knobs in sections stacked, a frame each: (its name, what it sets, picked, its
        items, a row's count). picked: it sets the one picked at the left (a slot, a slice):
        its frame and name in the device's colour, as that one is; the others the whole
        device (said at their right, not by colour alone). an item: a knob (its hit, name,
        turn, value), a key ('key', its name, on, its hit) or None (a place left). the one
        touched: its value large where what it sets is said'''
        st = self.parent.st
        per = max(section[4] for section in sections)
        cell = min(width / float(per), KNOB_CELL)
        ground = colour(st.RACK_BG_COLOR)
        # (a knob's value and name under it as tall as their fonts are on this screen: a
        # frame's bottom fixed in pixels cut them where the fonts were larger)
        value_font = get_font(uikit.MICRO + 1, mono=True)
        label_font = get_font(uikit.MICRO, bold=True)
        gc.SetFont(value_font, colour(st.LCD_TEXT_COLOR))
        value_h = gc.GetTextExtent('0')[1]
        gc.SetFont(label_font, colour(st.RACK_LABEL_COLOR))
        label_h = gc.GetTextExtent('A')[1]
        value_dy = 4
        label_dy = value_dy + value_h
        below = KNOB_RADIUS + label_dy + label_h + 5
        row_step = max(KNOB_ROW, below + KNOB_RADIUS + 14)
        top = y
        for title, scope, picked, items, per_row in sections:
            rows = max((len(items) + per_row - 1) // per_row, 1)
            height = SECTION_HEAD + 22 + (rows - 1) * row_step + below
            w = cell * per
            # a recessed panel (darker than the plate, its edge a shade lighter); the picked
            # one's a bar of the device's colour at its left (its name in it, SELECTED said:
            # not by colour alone). a whole frame in the colour shouted over the knobs
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(ground, (255, 255, 255), 0.07))
                                   .Width(1)))
            gc.SetBrush(gc.CreateLinearGradientBrush(
                x, top, x, top + height, uikit.mix(ground, (0, 0, 0), 0.28),
                uikit.mix(ground, (0, 0, 0), 0.16)))
            gc.DrawRoundedRectangle(x + 0.5, top + 0.5, w - 1, height - 1, uikit.RADIUS)
            if picked:
                gc.SetPen(wx.NullGraphicsPen)
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(self.tint))))
                gc.DrawRoundedRectangle(x + 1, top + 3, 3, height - 6, 1.5)
            gc.SetFont(get_font(uikit.MICRO, bold=True),
                       colour(self.tint) if picked else colour(st.RACK_TEXT_COLOR))
            gc.DrawText(title, x + 8, top + 4)
            bubble = None
            for k, item in enumerate(items):
                if item is None:
                    continue
                cx = x + cell * (k % per_row) + cell / 2.0
                cy = top + SECTION_HEAD + 22 + (k // per_row) * row_step
                if item[0] == 'key':
                    _, label, on, hit = item
                    kw = min(cell - 14, 64)
                    self.DrawKey(gc, (cx - kw / 2.0, cy - KEY_HEIGHT / 2.0, kw, KEY_HEIGHT),
                                 label, on, hit)
                    continue
                if item[0] == 'select':
                    # a choice on an LCD where a knob would be, its name under it as theirs
                    _, label, value, options, hit = item
                    sw = cell - 8
                    self.DrawSelector(gc, (cx - sw / 2.0, cy - SWITCH_HEIGHT / 2.0, sw,
                                           SWITCH_HEIGHT), '', value, options, hit)
                    gc.SetFont(label_font, colour(st.RACK_LABEL_COLOR))
                    tw = gc.GetTextExtent(label)[0]
                    gc.DrawText(label, cx - tw / 2.0, cy + KNOB_RADIUS + label_dy)
                    continue
                hit, label, turn, text = item
                touched = self.hovered == hit or (self.drag is not None and
                                                  self.drag[0] == hit)
                self.DrawKnob(gc, cx, cy, min(max(turn, 0.0), 1.0), touched,
                              radius=KNOB_RADIUS, tint=self.tint, ticks=11)
                for line, font, ink, dy in (
                        (text, value_font, st.LCD_TEXT_COLOR, value_dy),
                        (label, label_font, st.RACK_LABEL_COLOR, label_dy)):
                    gc.SetFont(font, colour(ink))
                    while len(line) > 1 and gc.GetTextExtent(line)[0] > cell - 3:
                        line = line[:-1]
                    tw = gc.GetTextExtent(line)[0]
                    gc.DrawText(line, cx - tw / 2.0, cy + KNOB_RADIUS + dy)
                self.hits.append((wx.Rect(int(cx - cell / 2.0), int(cy - KNOB_RADIUS - 8),
                                          int(cell), int(below + KNOB_RADIUS + 8)), hit[0],
                                  hit[1]))
                if touched:
                    bubble = '%s  %s' % (label, text)
            right = x + w - 8
            if bubble is not None:
                # (its value large on an LCD where what it sets is said)
                gc.SetFont(get_font(uikit.MICRO + 2, mono=True), colour(st.LCD_TEXT_COLOR))
                tw, th = gc.GetTextExtent(bubble)[:2]
                bw, bh = tw + 12, th + 4
                gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(self.tint)).Width(1)))
                gc.SetBrush(gc.CreateBrush(wx.Brush(colour(st.LCD_BG_COLOR))))
                gc.DrawRoundedRectangle(right - bw + 4.5, top + 2.5, bw, bh, uikit.RADIUS)
                gc.DrawText(bubble, right - bw + 10, top + 4.5)
            elif scope:
                gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
                tw = gc.GetTextExtent(scope)[0]
                gc.DrawText(scope, right - tw, top + 4)
            top += height + SECTION_GAP

    def DrawKey(self, gc, rect, label, on, hit, corners='all', size=10, warn=False,
                tint='device'):
        '''a matte key (uikit's faces). a device's toggle (tint 'device'): its face as off,
        an LED before its name lit in the device's colour and its name in it when on (filled
        in colour, every lit key shouted); tint None: the player's own (PLAY: filled), warn
        its warning's; lighter under the mouse, darker pressed'''
        x, y, w, h = rect
        hovered = self.hovered == ('key', hit)
        led = tint == 'device'
        face, ink = uikit.get_face(on=on and not led, warn=warn, hover=hovered)
        uikit.draw_face(gc, rect, face, pressed=self.pressed == ('key', hit), corners=corners)
        font = get_font(size, bold=True)
        tw = gc.GetTextExtent(label)[0] if False else None
        gc.SetFont(font, ink)
        tw = gc.GetTextExtent(label)[0]
        tx = x + (w - tw) / 2.0
        if led and w >= tw + 18:
            # its LED
            tx += 5
            lit = colour(self.tint) if on else uikit.mix(face, (0, 0, 0), 0.45)
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(lit)))
            gc.DrawEllipse(tx - 11, y + h / 2.0 - 3, 6, 6)
        if led and on:
            gc.SetFont(font, colour(self.tint))
        gc.DrawText(label, tx, uikit.get_caps_top(font, y, h))
        self.hits.append((wx.Rect(*[int(v) for v in rect]), 'key', hit))

    def DrawWell(self, gc, rect, edge=None, width=1):
        # (rackbox.draw_well: every module's displays the same)
        draw_well(gc, self.parent.st, rect, edge, width)

    def DrawSelector(self, gc, rect, caption, value, options, hit):
        '''a choice on an LCD: its caption dim, its value bright, a mark for its menu (a
        click: its options; the wheel: the next one)'''
        st = self.parent.st
        x, y, w, h = rect
        hovered = self.hovered == ('select', hit)
        self.DrawWell(gc, rect, colour(self.tint) if hovered else None)
        gc.SetFont(get_font(uikit.MICRO, bold=True), colour(st.RACK_LABEL_COLOR))
        cw, ch = gc.GetTextExtent(caption)[:2] if caption else (0, 0)
        gc.DrawText(caption, x + 6, y + (h - ch) / 2.0)
        label = dict(options).get(value, str(value).upper())
        gc.SetFont(get_font(uikit.MICRO + 1, bold=True), colour(st.LCD_TEXT_COLOR))
        # (its value's room: past its caption, before its mark)
        lx = x + 6 + (cw + 5 if caption else 0)
        room = x + w - 14 - lx
        while len(label) > 1 and gc.GetTextExtent(label)[0] > room:
            label = label[:-1]
        lw, lh = gc.GetTextExtent(label)[:2]
        gc.DrawText(label, lx, y + (h - lh) / 2.0)
        # its menu's mark
        mx, my = x + w - 9, y + h / 2.0
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(st.RACK_LABEL_COLOR)).Width(1.2)))
        gc.StrokeLine(mx - 3, my - 1.5, mx, my + 1.5)
        gc.StrokeLine(mx, my + 1.5, mx + 3, my - 1.5)
        self.selectors[hit] = (value, options)
        self.hits.append((wx.Rect(*[int(v) for v in rect]), 'select', hit))

    def GetPeaks(self, sample, width):
        # (lows, highs) of the bar a column, at most 1 (kept while the bar and width are)
        if self.peaks[0] is sample and self.peaks[1] == width:
            return self.peaks[2]
        count = max(len(sample) // max(width, 1), 1)
        cut = sample[:count * width].reshape(width, count) if width else sample[:0]
        peak = max(float(numpy.abs(sample).max()), 1e-6)
        result = (cut.min(axis=1) / peak, cut.max(axis=1) / peak)
        self.peaks = (sample, width, result)
        return result

    def GetPickedSlice(self, dev):
        source = self.GetSource(dev)
        if source is None:
            return None
        return source.pads.get(self.GetPicked(dev))

    # knobs

    def GetKnobSpec(self, hit):
        dev, kind, key = hit
        if kind == 'voice':
            source = self.GetSource(dev)
            pad = source.pads.get(self.GetPicked(dev)) if source is not None else None
            voice = pad.voice if pad is not None else instruments.make_voice()
            return dict((spec[0], spec) for spec in instruments.get_knobs(voice)).get(key)
        if kind == 'slice':
            return dict((spec[0], spec) for spec in SLICE_KNOBS).get(key)
        if kind == 'sampler':
            return dict((spec[0], spec) for spec in SAMPLER_KNOBS).get(key)
        return dict((spec[0], spec) for spec in instruments.BASS_KNOBS).get(key)

    def GetInsertKnob(self, dev, key):
        # (the edited insert's slot, its knob's spec, its value)
        picked = self.GetPickedInsert(dev)
        if picked is None:
            return None, None, None
        slot = picked[1]
        knob = dict((k[0], k) for k in effects.get_knobs(slot.GetEffect())).get(key)
        if knob is None:
            return None, None, None
        values = effects.first_values(slot.GetEffect())
        values.update(slot.params)
        return slot, knob, values[key]

    def GetKnobTurn(self, hit):
        dev, kind, key = hit
        if kind == 'synth':
            source = self.GetSource(dev)
            if source is None:
                return None
            return self.SynthTurn(SYNTH_SPECS[key[-1]], source.GetParam(key))
        if kind == 'pad':
            source = self.GetSource(dev)
            pad = source.pads.get(self.GetPicked(dev)) if source is not None else None
            if pad is None:
                return None
            spec = dict((s[0], s) for s in PAD_KNOBS)[key]
            value = dict(semis=12.0 * numpy.log2(pad.pitch), gain=pad.gain,
                         decay=pad.decay)[key]
            return 1.0 if value is None else instruments.to_knob(spec, value)
        if kind == 'insert':
            slot, knob, value = self.GetInsertKnob(dev, key)
            return effects.to_turn(knob, value) if slot is not None else None
        spec = self.GetKnobSpec(hit)
        if spec is None:
            return None
        if kind == 'voice':
            source = self.GetMade(dev)
            pad = source.pads.get(self.GetPicked(dev)) if source is not None else None
            return instruments.to_knob(spec, pad.voice[key]) if pad is not None else None
        if kind == 'slice':
            pad = self.GetPickedSlice(dev)
            if pad is None:
                return None
            value = dict(semis=12.0 * numpy.log2(pad.pitch), gain=pad.gain,
                         decay=pad.decay)[key]
            return 1.0 if value is None else instruments.to_knob(spec, value)
        if kind == 'sampler':
            source = self.GetSource(dev)
            if source is None or not source.pads:
                return None
            return instruments.to_knob(spec, self.GetSamplerValue(dev, source, key))
        source = self.GetMade(dev)
        tone = source.tone if source is not None else instruments.BASS_TONE
        return instruments.to_knob(spec, tone[key])

    def SetKnobTurn(self, hit, turn):
        dev, kind, key = hit
        if kind == 'synth':
            source = self.GetSource(dev)
            if source is not None:
                value = self.SynthValue(SYNTH_SPECS[key[-1]], turn)
                if value != source.GetParam(key):
                    source.SetParam(key, value)
            return
        if kind == 'pad':
            source = self.GetSource(dev)
            if source is not None:
                spec = dict((s[0], s) for s in PAD_KNOBS)[key]
                value = instruments.from_knob(spec, min(max(turn, 0.0), 1.0))
                if key == 'decay' and turn >= 0.995:
                    value = None
                source.SetPadSetting(self.GetPicked(dev), **{key: value})
            return
        if kind == 'insert':
            slot, knob, _ = self.GetInsertKnob(dev, key)
            if slot is not None:
                slot.SetParam(key, effects.from_turn(knob, min(max(turn, 0.0), 1.0)))
                self.RepaintMixer()
            return
        spec = self.GetKnobSpec(hit)
        if spec is None:
            return
        turn = min(max(turn, 0.0), 1.0)
        value = instruments.from_knob(spec, turn)
        if kind == 'voice':
            source = self.GetMade(dev)
            if source is not None:
                source.SetVoice(self.GetPicked(dev), **{key: value})
        elif kind == 'slice':
            source = self.GetSource(dev)
            if source is not None:
                if key == 'decay' and turn >= 0.995:
                    value = None
                source.SetSlice(self.GetPicked(dev), **{key: value})
        elif kind == 'sampler':
            source = self.GetSource(dev)
            if source is None or not source.pads:
                return
            if key == 'shift':
                source.shift = round(value)
            elif key == 'start':
                self.SetOffset(dev, value * self.GetBeat(source))
            else:
                # (turned with the filter off: a low-pass on)
                first = next(iter(source.pads.values()))
                source.SetFilter(filter=first.filter or 'lp',
                                 **{'cutoff' if key == 'cutoff' else 'resonance': value})
        else:
            source = self.GetMade(dev)
            if source is not None:
                source.SetTone(**{key: value})

    def ResetKnob(self, hit):
        # a knob's first value
        dev, kind, key = hit
        if kind == 'synth':
            source = self.GetSource(dev)
            if source is not None:
                source.SetParam(key, self.GetSynthDefault(key))
            return
        if kind == 'pad':
            source = self.GetSource(dev)
            if source is not None:
                source.SetPadSetting(self.GetPicked(dev), **{key: dict(
                    semis=0.0, gain=1.0, decay=None)[key]})
            return
        if kind == 'insert':
            slot, knob, _ = self.GetInsertKnob(dev, key)
            if slot is not None:
                slot.SetParam(key, effects.first_values(slot.GetEffect())[key])
                self.RepaintMixer()
            return
        if kind == 'voice':
            source = self.GetMade(dev)
            pad = source.pads.get(self.GetPicked(dev)) if source is not None else None
            if pad is None or pad.voice is None:
                return
            kit = pad.voice.get('kit', '909')
            first = instruments.make_voice(
                **instruments.KIT_VOICES.get(kit, instruments.KIT_VOICES['909'])[
                    source.GetSlotKind(pad.name)])
            source.SetVoice(pad.name, **{key: first[key]})
        elif kind == 'slice':
            source = self.GetSource(dev)
            if source is not None:
                first = dict(semis=0.0, gain=1.0, decay=None)
                source.SetSlice(self.GetPicked(dev), **{key: first[key]})
        elif kind == 'sampler':
            source = self.GetSource(dev)
            if source is None or not source.pads:
                return
            if key == 'shift':
                source.shift = 0.0
            elif key == 'start':
                self.SetOffset(dev, 0.0, at_once=True)
            elif key == 'q':
                source.SetFilter(resonance=0.7)
            else:
                pad = next(iter(source.pads.values()))
                source.SetFilter(cutoff=FILTER_FIRST.get(pad.filter, 2000.0))
        else:
            source = self.GetMade(dev)
            if source is not None:
                source.SetTone(**{key: instruments.BASS_TONE[key]})

    # PS1200's: its knobs' values, its START (cut again once it rests)

    def GetSamplerValue(self, dev, source, key):
        first = next(iter(source.pads.values()))
        if key == 'start':
            return self.GetOffset(dev, source) / self.GetBeat(source)
        if key == 'cutoff':
            return first.cutoff or FILTER_FIRST.get(first.filter, 2000.0)
        return dict(shift=source.shift, q=first.resonance)[key]

    def GetSamplerText(self, dev, source, key):
        if key == 'start':
            return '%+d ms' % round(self.GetOffset(dev, source) * 1000)
        value = self.GetSamplerValue(dev, source, key)
        first = next(iter(source.pads.values()))
        if key in ('cutoff', 'q') and first.filter is None:
            return 'OFF'
        return format_value(key, value)

    def GetBeat(self, source):
        grab = source.grab or {}
        return 60.0 / grab['bpm'] if grab.get('bpm') else 0.5

    def GetOffset(self, dev, source):
        if dev in self.offsets:
            return self.offsets[dev]
        return (source.grab or {}).get('offset', 0.0)

    def SetOffset(self, dev, offset, at_once=False):
        self.offsets[dev] = offset
        if self.recut is not None:
            self.recut.Stop()
            self.recut = None
        if at_once:
            self.Recut()
        else:
            self.recut = wx.CallLater(RECUT_MS, self.Recut)

    def Recut(self):
        self.recut = None
        offsets, self.offsets = self.offsets, {}
        for dev, offset in offsets.items():
            source = self.GetSource(dev)
            if source is not None and source.grab:
                source.SetOffset(offset)
        if offsets:
            self.KeepMachines()
            self.Repaint()

    def IsDragging(self):
        return self.drag is not None or self.paint is not None or self.moving is not None\
            or self.roll_paint is not None

    def HandleDrag(self, event):
        # a knob turned (shift finer: anchored where the mouse is, no jump), steps painted,
        # notes drawn, a device or a slot moved; till the button is let go (kept then)
        if self.pressed is not None and not event.LeftIsDown:
            self.pressed = None
        if self.paint is not None:
            return self.HandlePaint(event)
        if self.roll_paint is not None:
            return self.HandleRollPaint(event)
        if self.moving is not None:
            return self.HandleMove(event)
        if self.drag is None:
            return False
        if event.LeftIsDown:
            hit, y0, turn0 = self.drag
            speed = KNOB_FINE if getattr(event, 'ShiftDown', False) else 1.0
            turn = min(max(turn0 + (y0 - event.y) / KNOB_DRAG * speed, 0.0), 1.0)
            self.drag = (hit, event.y, turn)
            self.SetKnobTurn(hit[1], turn)
            self.Repaint()
        else:
            self.drag = None
            self.KeepMachines()
            self.Repaint()
        return True

    MOVE_AFTER = 4

    def HandleMove(self, event):
        '''a device or a slot moved by a drag (the panel's own y: event.Y; the screen's,
        event.y, put every one at the bottom), once the mouse has gone MOVE_AFTER pixels (a
        click alone picks)'''
        dev, slot, _ = self.moving
        if event.LeftIsDown:
            if abs(event.Y - self.move_from) < self.MOVE_AFTER and self.moving[2] is None:
                return True
            if slot is None:
                at = len(self.device_rects)
                for k, (_, top, height) in enumerate(self.device_rects):
                    if event.Y < top + height / 2.0:
                        at = k
                        break
            else:
                rows = self.slot_rows.get(dev, [])
                at = len(rows)
                for k, (_, ry) in enumerate(rows):
                    if event.Y < ry + ROW / 2.0:
                        at = k
                        break
            if at != self.moving[2]:
                self.moving = (dev, slot, at)
                self.Repaint()
            return True
        control = self.GetControl()
        at = self.moving[2]
        self.moving = None
        if control is not None and at is not None:
            if slot is None:
                order = self.GetDevices()
                index = order.index(dev)
                control.MoveDevice(dev, at - 1 if at > index else at)
            else:
                source = self.GetSource(dev)
                if source is not None:
                    names = list(source.pads)
                    index = names.index(slot) if slot in names else at
                    source.MoveSlot(slot, at - 1 if at > index else at)
                    self.KeepMachines()
        self.Repaint()
        return True

    def KeepMachines(self):
        control = self.GetControl()
        if control is not None:
            control.KeepInstruments()

    def CATCH_EVT_MOUSEWHEEL(self, event):
        # a knob turned (shift finer); a BT303 note a scale's step up or down (a rest: its
        # root)
        if self.onClient is False:
            return
        hit = self.GetHit(wx.Point(int(event.X), int(event.Y)))
        if hit is None:
            return
        up = event.WheelRotation > 0
        if hit[0] == 'knob':
            turn = self.GetKnobTurn(hit[1])
            if turn is not None:
                step = KNOB_WHEEL * (KNOB_FINE if getattr(event, 'ShiftDown', False) else 1)
                self.SetKnobTurn(hit[1], turn + (step if up else -step))
        elif hit[0] == 'select':
            self.HandleSelect(hit[1], -1 if up else 1)
        elif hit[0] == 'step' and self.Kind(hit[1][0]) == 'ps1200':
            self.StepSlice(hit[1][0], hit[1][2], up)
        elif hit[0] == 'roll':
            dev, index, _ = hit[1]
            source = self.GetMade(dev)
            if source is None:
                return
            line = self.GetLine(source)
            note = line[index]
            if note is None:
                line[index] = (0, False, False)
            else:
                degree, accent, slide = note
                line[index] = (min(max(degree + (1 if up else -1), -7), 14), accent, slide)
            source.SetLine(line)
        else:
            return
        self.KeepMachines()
        self.Repaint()

    # handled

    def HandleHit(self, event, hit):
        kind, value = hit
        control = self.GetControl()
        if control is None:
            return
        if event.RightDown:
            if kind == 'step':
                self.HandleStep(value, 'accent')
            elif kind == 'slot':
                self.ShowSlotMenu(*value)
            elif kind == 'insert':
                self.ShowInsertMenu(*value)
            self.Repaint()
            return
        if event.LeftDClick and kind in ('knob', 'slot'):
            if kind == 'knob':
                self.drag = None
                self.ResetKnob(value)
                self.KeepMachines()
            else:
                self.moving = None
                self.EditSlotName(*value)
            self.Repaint()
            return
        # (a quick second click comes as a double click only, no press: pressed as the
        # first was, not lost)
        if event.LeftDown is False and event.LeftDClick is False:
            return
        self.shift_held = bool(getattr(event, 'ShiftDown', False))
        if kind == 'knob':
            turn = self.GetKnobTurn(value)
            if turn is not None:
                self.drag = (hit, event.y, turn)
        elif kind == 'slot':
            # picked, heard; a drag from here moves it
            dev, name = value
            self.picked[dev] = name
            source = self.GetMade(dev)
            if source is not None and name in source.pads:
                source.Hit(source.pads[name], 1.0)
            self.moving = (dev, name, None)
            self.move_from = event.Y
        elif kind == 'slice':
            dev, name = value
            self.picked[dev] = name
            source = self.GetSource(dev)
            if source is not None and name in source.pads:
                source.Hit(source.pads[name], 1.0)
        elif kind == 'ear':
            self.moving = (value, None, None)
            self.move_from = event.Y
        elif kind == 'remove':
            self.AskRemove(value)
            return
        elif kind == 'insert':
            dev, index = value
            if index is None:
                count = len(self.GetInserts(dev) or [])
                self.ShowInsertMenu(dev, None)
                if len(self.GetInserts(dev) or []) > count:
                    # (put in: opened on it)
                    inserts = self.GetInserts(dev)
                    self.PickInsert(dev, inserts[-1][0])
                    self.OpenInserts(dev, True)
            elif self.fx_open.get(dev) and self.GetPickedInsert(dev)[0] == index:
                # (its chip again: closed)
                self.OpenInserts(dev, False)
            else:
                self.PickInsert(dev, index)
                self.OpenInserts(dev, True)
        elif kind == 'roll_open':
            self.OpenRoll(value)
        elif kind == 'fold':
            self.ToggleFold(value)
            return
        elif kind == 'synth_tab':
            self.synth_pages[value[0]] = value[1]
        elif kind in ('mp_pad', 'mp_row'):
            dev, name = value
            self.picked[dev] = name
            source = self.GetMade(dev)
            if source is not None and name in source.pads:
                source.Hit(source.pads[name], 1.0)
            if kind == 'mp_pad':
                self.pressed = hit
        elif kind == 'menu':
            self.keyed = value
            self.Repaint()
            self.ShowPresetMenu(*value)
        elif kind == 'select':
            self.shift_held = bool(getattr(event, 'ShiftDown', False))
            self.HandleSelect(value)
        elif kind == 'addslot':
            self.ShowAddSlotMenu(value)
        elif kind == 'key':
            self.pressed = hit
            self.HandleKey(control, *value)
        elif kind == 'step':
            self.pressed = hit
            self.HandleStep(value, self.GetStepMode(value), paint=True)
        elif kind == 'roll':
            self.StartRoll(*value)
        self.Repaint()

    def GetStepMode(self, value):
        dev, name, _ = value
        if self.Kind(dev) == 'bt303':
            return {'acc': 'accent', 'slide': 'slide'}.get(name)
        return self.modes.get(dev)

    def HandleKey(self, control, action, arg):
        if action == 'play':
            control.SetInstrument(arg, not self.IsRunning(arg))
            return
        if action == 'mode':
            dev, mode = arg
            self.modes[dev] = None if self.modes.get(dev) == mode else mode
            return
        if action == 'voice':
            dev, setting, value = arg
            source = self.GetMade(dev)
            if source is None:
                return
            picked = self.GetPicked(dev)
            if setting == 'kit':
                # this slot's sound from that kit (every slot's with shift), heard
                if self.shift_held:
                    source.SetKit(value)
                else:
                    source.SetPadKit(picked, value)
                if picked in source.pads:
                    source.Hit(source.pads[picked], 1.0)
            else:
                source.SetVoice(picked, **{setting: value})
        elif action in ('pad_mute', 'pad_solo'):
            dev, name = arg
            source = self.GetMade(dev)
            if source is not None:
                group = source.muted if action == 'pad_mute' else source.soloed
                group.symmetric_difference_update({name})
        elif action == 'grab':
            control.GrabBar(arg)
        elif action == 'crunch':
            source = self.GetSource(arg)
            if source is not None and source.pads:
                on = not any(pad.crunched for pad in source.pads.values())
                with source.lock:
                    for pad in source.pads.values():
                        pad.SetCrunch(on)
        elif action == 'reverse':
            pad = self.GetPickedSlice(arg)
            if pad is not None:
                self.GetSource(arg).SetSlice(pad.name, reverse=not pad.reverse)
        elif action == 'fx':
            self.DoInsertKey(*arg)
        elif action == 'roll_open':
            self.OpenRoll(arg)
        elif action == 'synth_on':
            dev, path = arg
            source = self.GetMade(dev)
            if source is not None:
                source.SetParam(path, not source.GetParam(path))
        elif action == 'synth_mono':
            source = self.GetMade(arg)
            if source is not None:
                source.SetParam(('mono',), not source.patch.get('mono'))
        elif action == 'synth_move':
            dev, semis, steps = arg
            source = self.GetMade(dev)
            if source is not None:
                source.MoveNotes(semis, steps)
                self.RepaintRoll()
        elif action == 'mp_sample':
            control.SamplePad(arg, self.GetPicked(arg), self.pad_beats.get(arg, 1))
        elif action == 'mp_load':
            self.LoadPadFile(arg)
        elif action == 'mp_reverse':
            source = self.GetMade(arg)
            pad = source.pads.get(self.GetPicked(arg)) if source is not None else None
            if pad is not None:
                source.SetPadSetting(pad.name, reverse=not pad.reverse)
        elif action == 'line_shift':
            dev, steps = arg
            source = self.GetMade(dev)
            if source is not None:
                source.ShiftLine(steps)
        elif action == 'mono':
            source = self.GetSource(arg)
            if source is not None:
                source.mono = not source.mono
        elif action == 'grab_from':
            dev, key = arg
            source = self.GetMade(dev)
            if source is not None:
                source.grab_from = key
        self.KeepMachines()

    # steps

    def HandlePaint(self, event):
        if not event.LeftIsDown:
            self.paint = None
            self.KeepMachines()
            self.Repaint()
            return True
        dev, name, mode, state, passed = self.paint
        hit = self.GetHit(wx.Point(int(event.X), int(event.Y)))
        if hit is None or hit[0] != 'step' or hit[1][0] != dev:
            return True
        _, row, index = hit[1]
        if self.Kind(dev) == 'bt303' and row != name:
            return True
        if (row, index) in passed:
            return True
        passed.add((row, index))
        source = self.GetMade(dev)
        if source is not None and self.IsStepOn(source, dev, row, index, mode) != state:
            self.ToggleStep(source, dev, row, index, mode)
            self.Repaint()
        return True

    def IsStepOn(self, source, dev, name, index, mode):
        kind = self.Kind(dev)
        if kind in ('rt909', 'mp60'):
            velocity = source.pattern.get(name, [0] * instruments.STEPS)[index]
            return instruments.is_accent(velocity) if mode == 'accent' else bool(velocity)
        if kind == 'ps1200':
            # (on: playing the slice picked)
            picked = self.GetPicked(dev)
            return bool(source.pattern.get(picked, [0] * instruments.STEPS)[index])
        note = self.GetLine(source)[index]
        if note is None:
            return False
        return note[1] if mode == 'accent' else (note[2] if mode == 'slide' else True)

    def ToggleStep(self, source, dev, name, index, mode):
        kind = self.Kind(dev)
        if kind in ('rt909', 'mp60'):
            velocity = source.pattern.get(name, [0] * instruments.STEPS)[index]
            if mode == 'accent':
                source.SetStep(name, index, instruments.STEP_ON
                               if instruments.is_accent(velocity) else instruments.STEP_ACCENT)
            else:
                source.SetStep(name, index, 0 if velocity else instruments.STEP_ON)
        elif kind == 'ps1200':
            # the slice picked put on the step (the one there before off it), or, there
            # already, taken off
            self.SetSliceStep(source, index, None if self.IsStepOn(
                source, dev, name, index, mode) else self.GetPicked(dev))
        else:
            self.ToggleBassStep(source, dev, index, mode)

    def SetSliceStep(self, source, index, slice_name):
        # a PS1200 step to play that slice (None: none), its others off
        for name in list(source.pattern):
            source.SetStep(name, index, 1.0 if name == slice_name else 0)

    def StepSlice(self, dev, index, up):
        # a PS1200 step's slice the next one up or down (none: the picked one)
        source = self.GetSource(dev)
        if source is None or not source.pads:
            return
        playing = [n for n, steps in source.pattern.items() if steps[index]]
        if playing:
            number = int(playing[0].split()[-1]) + (1 if up else -1)
            number = (number - 1) % instruments.STEPS + 1
            name = 'slice %d' % number
        else:
            name = self.GetPicked(dev)
        self.SetSliceStep(source, index, name)

    def HandleSelect(self, hit, step=None):
        '''a selector's choice: step None its menu, else the next (1) or the one before'''
        value, options = self.selectors.get(hit, (None, []))
        if not options:
            return
        if step is not None:
            keys = [key for key, _ in options]
            at = keys.index(value) if value in keys else 0
            self.SetSelect(hit, keys[(at + step) % len(keys)])
            return
        menu = wx.Menu()
        for key, label in options:
            item = menu.AppendRadioItem(wx.ID_ANY, label)
            item.Check(key == value)
            self.Bind(wx.EVT_MENU, lambda event, key=key: self.SetSelect(hit, key), item)
        self.PopupMenu(menu)
        menu.Destroy()

    def SetSelect(self, hit, key):
        kind, value = hit
        control = self.GetControl()
        if kind == 'voice':
            dev, setting = value
            self.HandleKey(control, 'voice', (dev, setting, key))
        elif kind == 'grab_from':
            self.HandleKey(control, 'grab_from', (value[0], key))
        elif kind == 'synth_sel':
            dev, path = value
            source = self.GetMade(dev)
            if source is not None:
                source.SetParam(path, key)
                self.KeepMachines()
        elif kind == 'synth_bars':
            source = self.GetMade(value[0])
            if source is not None:
                source.SetBars(key)
                self.KeepMachines()
                self.RepaintRoll()
        elif kind == 'mp_beats':
            self.pad_beats[value[0]] = key
        elif kind == 'bass_pitch':
            dev, setting = value
            source = self.GetMade(dev)
            if source is not None:
                source.SetPitch(**{setting: key})
                self.KeepMachines()
        elif kind in ('filter', 'slope'):
            source = self.GetSource(value[0])
            if source is not None and source.pads:
                first = next(iter(source.pads.values()))
                if kind == 'slope':
                    source.SetFilter(slope=key)
                elif key is None:
                    source.SetFilter(filter=None)
                else:
                    # (its cutoff where that kind is first heard when it had none)
                    source.SetFilter(filter=key, cutoff=first.cutoff
                                     if first.cutoff is not None else FILTER_FIRST[key])
                self.KeepMachines()
        self.Repaint()

    def HandleStep(self, value, mode, paint=False):
        dev, name, index = value
        source = self.GetMade(dev) if self.Kind(dev) != 'ps1200' else self.GetSource(dev)
        if source is None:
            return
        self.ToggleStep(source, dev, name, index, mode)
        if paint:
            self.paint = (dev, name, mode, self.IsStepOn(source, dev, name, index, mode),
                          {(name, index)})
        else:
            self.KeepMachines()

    def GetLine(self, source):
        return [instruments.read_note(note) for note in
                (list(source.line) + [None] * instruments.STEPS)[:instruments.STEPS]]

    def ToggleBassStep(self, source, dev, index, mode=None):
        line = self.GetLine(source)
        off = self.steps.setdefault((dev, 'bass'), {})
        note = line[index]
        if mode in ('accent', 'slide'):
            degree, accent, slide = note if note is not None else\
                instruments.read_note(off.pop(index, (0, False, False)))
            if mode == 'accent':
                accent = not accent
            else:
                slide = not slide
            line[index] = (degree, accent, slide)
        elif note is not None:
            off[index] = note
            line[index] = None
        else:
            line[index] = instruments.read_note(off.pop(index, (0, False, False)))
        source.SetLine(line)

    # BT303's roll (Reason's Matrix's way): a click on a note takes it away (a drag on
    # takes those it passes on that row away); elsewhere a click places a note, a drag
    # draws them, each step the row under the mouse (moved as the mouse moves over it)

    def StartRoll(self, dev, index, degree):
        source = self.GetMade(dev)
        if source is None:
            return
        line = self.GetLine(source)
        note = line[index]
        erase = note is not None and min(max(note[0], 0), ROLL_DEGREES - 1) == degree
        self.roll_paint = (dev, 'erase' if erase else 'place', {})
        self.SetRollStep(source, line, dev, index, degree)

    def SetRollStep(self, source, line, dev, index, degree):
        _, mode, passed = self.roll_paint
        note = line[index]
        off = self.steps.setdefault((dev, 'bass'), {})
        if mode == 'erase':
            if note is None or min(max(note[0], 0), ROLL_DEGREES - 1) != degree:
                return
            off[index] = note
            line[index] = None
        else:
            if passed.get(index) == degree:
                return
            kept = note or instruments.read_note(off.pop(index, (degree, False, False)))
            line[index] = (degree, kept[1], kept[2])
        passed[index] = degree
        source.SetLine(line)
        self.Repaint()

    def HandleRollPaint(self, event):
        if not event.LeftIsDown:
            self.roll_paint = None
            self.KeepMachines()
            self.Repaint()
            return True
        dev = self.roll_paint[0]
        hit = self.GetHit(wx.Point(int(event.X), int(event.Y)))
        if hit is None or hit[0] != 'roll' or hit[1][0] != dev:
            return True
        _, index, degree = hit[1]
        source = self.GetMade(dev)
        if source is not None:
            self.SetRollStep(source, self.GetLine(source), dev, index, degree)
        return True

    # slots

    def ShowSlotMenu(self, dev, name):
        source = self.GetMade(dev)
        if source is None or name not in source.pads:
            return
        self.picked[dev] = name
        menu = wx.Menu()

        def bind(item, call):
            self.Bind(wx.EVT_MENU, lambda event: (call(), self.KeepMachines(), self.Relayout()),
                      item)
        bind(menu.Append(wx.ID_ANY, 'Rename'), lambda: self.EditSlotName(dev, name))
        sound = wx.Menu()
        for kit in instruments.KITS:
            for kind in instruments.PAD_TYPES:
                item = sound.Append(wx.ID_ANY, '%s  %s' % (kit, kind.title()))
                bind(item, lambda kit=kit, kind=kind: source.SetSlotSound(name, kit, kind))
            sound.AppendSeparator()
        menu.AppendSubMenu(sound, 'Sound')
        choke = wx.Menu()
        for group in (None,) + instruments.CHOKE_GROUPS:
            item = choke.AppendRadioItem(wx.ID_ANY, 'None' if group is None else
                                         'Group %s' % group)
            item.Check(source.pads[name].choke == group)
            bind(item, lambda group=group: source.SetSlotChoke(name, group))
        menu.AppendSubMenu(choke, 'Choke')
        names = list(source.pads)
        index = names.index(name)
        if index > 0:
            bind(menu.Append(wx.ID_ANY, 'Move up'), lambda: source.MoveSlot(name, index - 1))
        if index < len(names) - 1:
            bind(menu.Append(wx.ID_ANY, 'Move down'), lambda: source.MoveSlot(name, index + 1))
        menu.AppendSeparator()
        if len(names) > 1:
            bind(menu.Append(wx.ID_ANY, 'Remove'), lambda: source.RemoveSlot(name))
        self.PopupMenu(menu)
        menu.Destroy()

    def ShowAddSlotMenu(self, dev):
        source = self.GetMade(dev)
        if source is None:
            return
        picked = source.pads.get(self.GetPicked(dev))
        kit = picked.voice.get('kit', '909') if picked is not None and picked.voice else '909'
        menu = wx.Menu()
        for kind in instruments.PAD_TYPES:
            item = menu.Append(wx.ID_ANY, kind.title())

            def add(event, kind=kind):
                name = source.AddSlot(kind, kit)
                if name is not None:
                    self.picked[dev] = name
                self.KeepMachines()
                self.Relayout()
            self.Bind(wx.EVT_MENU, add, item)
        self.PopupMenu(menu)
        menu.Destroy()

    def EditSlotName(self, dev, name):
        # a field over its name: Enter (or leaving it) sets it, Esc leaves it
        source = self.GetSource(dev)
        if source is None or name not in source.pads or self.editor is not None:
            return
        rect = next((r for r, kind, value in self.hits if kind == 'slot'
                     and value == (dev, name)), None)
        if rect is None:
            return
        st = self.parent.st
        editor = wx.TextCtrl(self, pos=rect.GetPosition(), size=rect.GetSize(),
                             style=wx.TE_PROCESS_ENTER | wx.BORDER_NONE)
        editor.SetBackgroundColour(colour(st.METER_OFF_COLOR))
        editor.SetForegroundColour(colour(st.RACK_TEXT_COLOR))
        editor.SetFont(get_font(uikit.LABEL, bold=True))
        editor.SetValue(source.pads[name].label)
        editor.SelectAll()
        editor.SetFocus()
        self.editor = (editor, dev, name)
        editor.Bind(wx.EVT_TEXT_ENTER, lambda event: self.EndEdit(True))
        editor.Bind(wx.EVT_KILL_FOCUS, lambda event: (event.Skip(), self.EndEdit(True)))
        editor.Bind(wx.EVT_CHAR_HOOK, self.OnEditKey)

    def OnEditKey(self, event):
        # (its keys its own: not the player's shortcuts)
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndEdit(False)
            return
        event.DoAllowNextEvent()

    def EndEdit(self, apply):
        if self.editor is None:
            return
        editor, dev, name = self.editor
        self.editor = None
        text = editor.GetValue()
        wx.CallAfter(editor.Destroy)
        source = self.GetSource(dev)
        if apply and source is not None:
            source.RenameSlot(name, text)
            self.KeepMachines()
        self.Repaint()

    # presets

    def ShowPresetMenu(self, dev, what):
        '''a device's sound or pattern: the built-in ones, the saved ones (loaded on a
        click), Save as, Delete'''
        source = self.GetMade(dev)
        if source is None:
            return
        machine = self.Kind(dev)
        menu = wx.Menu()
        built = self.GetBuiltIn(dev, what)
        # (a library's: a submenu a group, 'Group/Name')
        groups = {}
        for name in built:
            if '/' in name:
                group, label = name.split('/', 1)
                if group not in groups:
                    groups[group] = wx.Menu()
                    menu.AppendSubMenu(groups[group], group)
                parent = groups[group]
            else:
                parent, label = menu, name
            item = parent.Append(wx.ID_ANY, label)
            self.Bind(wx.EVT_MENU, lambda event, name=name: self.LoadPreset(
                dev, what, name, built_in=True), item)
        saved = presets.list_saved(machine, what)
        if built and saved:
            menu.AppendSeparator()
        for name in saved:
            item = menu.Append(wx.ID_ANY, name)
            self.Bind(wx.EVT_MENU, lambda event, name=name: self.LoadPreset(dev, what, name),
                      item)
        menu.AppendSeparator()
        item = menu.Append(wx.ID_ANY, 'Save as...')
        self.Bind(wx.EVT_MENU, lambda event: self.SavePreset(dev, what), item)
        if saved:
            delete = wx.Menu()
            for name in saved:
                item = delete.Append(wx.ID_ANY, name)
                self.Bind(wx.EVT_MENU, lambda event, name=name: (
                    presets.delete_saved(machine, what, name)), item)
            menu.AppendSubMenu(delete, 'Delete')
        self.PopupMenu(menu)
        menu.Destroy()

    def AskRemove(self, dev):
        # (its menu at the mouse: removed on its one item, kept on a click elsewhere)
        control = self.GetControl()
        menu = wx.Menu()
        item = menu.Append(wx.ID_ANY, 'Remove %s' % control.GetDeviceLabel(dev))
        self.Bind(wx.EVT_MENU, lambda event: self.RemoveDevice(dev), item)
        self.PopupMenu(menu)
        menu.Destroy()
        self.Repaint()

    def RemoveDevice(self, dev):
        control = self.GetControl()
        if control is None:
            return
        control.RemoveDevice(dev)
        if self.keyed is not None and self.keyed[0] == dev:
            self.keyed = None
        self.Relayout()

    def OpenRoll(self, dev):
        # the piano roll on a synth's notes (shown, unfolded)
        roll = getattr(self.parent, 'PianoRoll', None)
        if roll is not None:
            roll.Open(dev)

    def RepaintRoll(self):
        roll = getattr(self.parent, 'PianoRoll', None)
        if roll is not None and roll.IsShown():
            roll.Repaint()

    def LoadPadFile(self, dev):
        source = self.GetMade(dev)
        if source is None:
            return
        dialog = wx.FileDialog(self, 'Load a sound into the pad', wildcard=(
            'Sounds|*.wav;*.mp3;*.flac;*.ogg;*.m4a;*.aif;*.aiff|All files|*.*'),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() == wx.ID_OK:
            source.LoadPad(self.GetPicked(dev), dialog.GetPath(), 0.0, PAD_FILE_SECONDS)
            self.KeepMachines()
        dialog.Destroy()
        self.Repaint()

    def RepaintMixer(self):
        mixer = getattr(self.parent, 'Mixer', None)
        if mixer is not None and mixer.IsShown():
            mixer.Repaint()

    def GetBuiltIn(self, dev, what):
        if self.Kind(dev) == 'rt909' and what == 'sound':
            return ['%s kit' % kit for kit in instruments.KITS]
        return presets.list_built_in(self.Kind(dev), what)

    def GetPresets(self, dev, what):
        # (name, built in or not): as its menu lists them
        return [(name, True) for name in self.GetBuiltIn(dev, what)]\
            + [(name, False) for name in presets.list_saved(self.Kind(dev), what)]

    def WalkPreset(self, step, group=False):
        '''the keyed LCD's next preset (step 1) or last (-1) loaded, as its menu lists
        them (round); by group: the next group's first, or this group's (the last's when
        at it)'''
        if self.keyed is None or self.keyed[0] not in self.GetDevices():
            self.keyed = None
            return
        dev, what = self.keyed
        entries = self.GetPresets(dev, what)
        if not entries:
            return
        at = self.FindLoaded(dev, what, entries)
        if group:
            groups = [name.split('/')[0] if built and '/' in name else '' for name, built
                      in entries]
            if at is None:
                at = 0 if step > 0 else len(entries) - 1
            elif step > 0:
                ahead = [k for k in range(at + 1, len(entries)) if groups[k] != groups[at]]
                at = ahead[0] if ahead else 0
            else:
                first = at
                while first > 0 and groups[first - 1] == groups[at]:
                    first -= 1
                if first == at and at > 0:
                    first = at - 1
                    while first > 0 and groups[first - 1] == groups[at - 1]:
                        first -= 1
                at = first
        elif at is None:
            at = 0 if step > 0 else len(entries) - 1
        else:
            at = (at + step) % len(entries)
        name, built = entries[at]
        self.LoadPreset(dev, what, name, built_in=built)

    def FindLoaded(self, dev, what, entries):
        # (the place of the preset loaded last; by its shown name when loaded before)
        walked = self.walked.get((dev, what))
        if walked in entries:
            return entries.index(walked)
        source = self.GetMade(dev)
        shown = getattr(source, what + '_name', None) if source is not None else None
        if not shown:
            return None
        return next((k for k, (name, _) in enumerate(entries)
                     if name.split('/')[-1] == shown), None)

    TAKEN_KEYS = (wx.WXK_UP, wx.WXK_DOWN, wx.WXK_NUMPAD_UP, wx.WXK_NUMPAD_DOWN, wx.WXK_PAGEUP,
                  wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEUP, wx.WXK_NUMPAD_PAGEDOWN)

    def TakesKey(self, event):
        '''the arrow keys walking an LCD's presets (the list's not moved by them then):
        the app's own key event'''
        if self.keyed is None or self.editor is not None or self.IsShown() is False:
            return False
        if event.EventType not in (wx.EVT_KEY_DOWN.evtType[0], wx.EVT_CHAR_HOOK.evtType[0]):
            return False
        return event.GetKeyCode() in self.TAKEN_KEYS

    def CATCH_EVT_KEY_DOWN(self, event):
        if self.keyed is None or self.editor is not None:
            return
        code = event.KeyCode
        if code == wx.WXK_ESCAPE:
            self.keyed = None
            self.Repaint()
        elif code in (wx.WXK_UP, wx.WXK_NUMPAD_UP):
            self.WalkPreset(-1)
        elif code in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN):
            self.WalkPreset(1)
        elif code in (wx.WXK_PAGEUP, wx.WXK_NUMPAD_PAGEUP):
            self.WalkPreset(-1, group=True)
        elif code in (wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEDOWN):
            self.WalkPreset(1, group=True)

    def CATCH_EVT_GLOBAL(self, event):
        # (a click anywhere: what it changed drawn again)
        if event.LeftDown or event.RightDown or event.LeftUp:
            self.version += 1
        # (a click outside the rack: the arrow keys the list's again)
        if self.keyed is not None and self.onClient is False\
                and (event.LeftDown or event.RightDown):
            self.keyed = None
        RackModule.CATCH_EVT_GLOBAL(self, event)

    def LoadPreset(self, dev, what, name, built_in=False):
        source = self.GetMade(dev)
        machine = self.Kind(dev)
        if source is None:
            return
        height = self.GetHeight()
        if built_in and machine == 'rt909' and what == 'sound':
            data = dict(kind='rt909', kit=name.split()[0])
        elif built_in:
            data = presets.load_built_in(machine, what, name)
        else:
            data = presets.load_saved(machine, what, name)
        if not data:
            return
        if what == 'sound':
            source.SetSoundData(data)
            source.sound_name = name.split('/')[-1]
        else:
            source.SetPatternData(data)
            source.pattern_name = name.split('/')[-1]
        self.walked[(dev, what)] = (name, built_in)
        self.keyed = (dev, what)
        self.KeepMachines()
        # (laid out again only when its height moved: a walk's steps drawn at once)
        if self.GetHeight() != height:
            self.Relayout()
        else:
            self.Repaint()

    def SavePreset(self, dev, what):
        source = self.GetMade(dev)
        if source is None:
            return
        current = getattr(source, what + '_name', None) or ''
        dialog = wx.TextEntryDialog(self, 'Name', 'Save %s' % what, current)
        if dialog.ShowModal() == wx.ID_OK:
            data = source.GetSoundData() if what == 'sound' else source.GetPatternData()
            name = presets.save(self.Kind(dev), what, dialog.GetValue(), data)
            if name:
                setattr(source, what + '_name', name)
                self.KeepMachines()
        dialog.Destroy()
        self.Repaint()
