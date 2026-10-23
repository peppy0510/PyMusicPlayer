# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import ctypes
import effects
import math

import pybass
from pybass import pybassmix as mix


# the player's wiring as data (Graph): decks, each a source of sound (a file, a station,
# an instrument, a timeline of clips) through its effect chain and its channel (gain, pan,
# mute, solo) into a bus, buses into buses, the master bus through its own chain to the
# output. Build makes it BASS channels: a bassmix mixer a bus (the master's played, the
# others decoding into their parents), a source's decoding handle a deck, VST DSPs the
# chains. what a screen changes later is the data (Route, the chains' slots, the channels)

MASTER = 'master'
# the mixers' rate and channels (the sources resampled to it by bassmix)
MIX_RATE = 44100
MIX_CHANS = 2
# a deck's handle in its bus: its data kept for its taps (BASS_Mixer_ChannelGetData), no
# ramp in (a deck added mid-play starts as it is), its gain and pan by a matrix (its
# channel's: the handle's own volume left to its owner, the player's volume and fades;
# set as the volume, a channel put the song back to full and cut its fades. bassmix
# 2.4.13 has no BASS_ATTRIB_MIXER_VOL)
DECK_FLAGS = mix.BASS_MIXER_BUFFER | mix.BASS_MIXER_NORAMPIN | mix.BASS_MIXER_MATRIX
BASS_ATTRIB_BUFFER = 13
# the VST DSPs' priorities from this down, a slot a step: the chain's first runs first
FX_PRIORITY = 100


class Source():

    '''a deck's sound: Open gives a decoding handle (BASS_STREAM_DECODE), 0 when it can not;
    what it can do told by its flags. the handle is the source's (Close frees it)'''

    KIND = ''
    SEEKABLE = False
    LIVE = False
    # its sound split to the send buses too (a splitter each, its own one to its bus: not
    # the deck's, whose stream's position and seeks are read off its mixer)
    SPLIT = False

    def __init__(self):
        self.handle = 0

    def Open(self):
        return 0

    def Close(self):
        if self.handle:
            pybass.BASS_StreamFree(self.handle)
        self.handle = 0

    def GetSpec(self):
        # what makes it again (Graph.GetData), None for one that is not kept
        return None


class HandleSource(Source):

    '''a decoding handle made elsewhere (the player's file or station, its reverse and tempo
    FX on it): opened as it is, freed by its maker'''

    KIND = 'handle'

    def __init__(self, handle, seekable=True, live=False):
        Source.__init__(self)
        self.given = handle
        self.SEEKABLE = seekable
        self.LIVE = live

    def Open(self):
        self.handle = self.given
        return self.handle

    def Close(self):
        self.handle = 0


class ToneSource(Source):

    '''a sine (the wiring's own test: a deck known to sound), made by a stream's callback'''

    KIND = 'tone'
    LIVE = True

    def __init__(self, freq=1000.0, level=0.5):
        Source.__init__(self)
        self.freq = freq
        self.level = level
        self.phase = 0.0
        self.proc = None

    def Fill(self, handle, buffer, length, user):
        count = length // 4
        step = 2.0 * math.pi * self.freq / MIX_RATE
        out = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_float))
        phase = self.phase
        for i in range(0, count, MIX_CHANS):
            value = self.level * math.sin(phase)
            for c in range(MIX_CHANS):
                out[i + c] = value
            phase += step
        self.phase = phase % (2.0 * math.pi)
        return length

    def Open(self):
        self.proc = pybass.STREAMPROC(self.Fill)
        self.handle = pybass.BASS_StreamCreate(
            MIX_RATE, MIX_CHANS, pybass.BASS_SAMPLE_FLOAT | pybass.BASS_STREAM_DECODE,
            self.proc, None)
        return self.handle

    def GetSpec(self):
        return dict(kind=self.KIND, freq=self.freq, level=self.level)


class VSTInstrumentSource(Source):

    '''a VST instrument's sound (bass_vst's channel), played by its events
    (BASS_VST_ProcessEvent: a MIDI note, a controller)'''

    KIND = 'vsti'
    LIVE = True

    def __init__(self, path):
        Source.__init__(self)
        self.path = path

    def Open(self):
        self.handle = pybass.BASS_VST_ChannelCreate(
            MIX_RATE, MIX_CHANS, self.path,
            pybass.BASS_UNICODE | pybass.BASS_SAMPLE_FLOAT | pybass.BASS_STREAM_DECODE)
        return self.handle

    def Close(self):
        if self.handle:
            pybass.BASS_VST_ChannelFree(self.handle)
        self.handle = 0

    def GetSpec(self):
        return dict(kind=self.KIND, path=self.path)


class Clip():

    '''a part of a file on a timeline: from begin to end (seconds of the file) at at
    (seconds of the timeline), its gain'''

    def __init__(self, path, begin, end, at, gain=1.0):
        self.path = path
        self.begin = begin
        self.end = end
        self.at = at
        self.gain = gain
        self.handle = 0

    def GetSpec(self):
        return dict(path=self.path, begin=self.begin, end=self.end, at=self.at, gain=self.gain)


class TimelineSource(Source):

    '''clips on a timeline (SHORT's parts, a highlight, an arrangement later): a decoding
    mixer of the deck's own, each clip's file put in at its place for its length
    (BASS_Mixer_StreamAddChannelEx's start and length: to the sample), from where it begins'''

    KIND = 'timeline'
    SEEKABLE = True

    def __init__(self, clips=()):
        Source.__init__(self)
        self.clips = list(clips)

    def Open(self):
        self.handle = mix.BASS_Mixer_StreamCreate(
            MIX_RATE, MIX_CHANS, pybass.BASS_SAMPLE_FLOAT | pybass.BASS_STREAM_DECODE
            | mix.BASS_MIXER_END)
        if not self.handle:
            return 0
        for clip in self.clips:
            self.AddClip(clip)
        return self.handle

    def AddClip(self, clip):
        # (prescanned: a seek in an MP3 to its sample, not its frame's guess)
        clip.handle = pybass.BASS_StreamCreateFile(
            False, clip.path, 0, 0,
            pybass.BASS_UNICODE | pybass.BASS_SAMPLE_FLOAT | pybass.BASS_STREAM_DECODE
            | pybass.BASS_STREAM_PRESCAN)
        if not clip.handle:
            return False
        pybass.BASS_ChannelSetPosition(
            clip.handle, pybass.BASS_ChannelSeconds2Bytes(clip.handle, clip.begin),
            pybass.BASS_POS_BYTE)
        pybass.BASS_ChannelSetAttribute(clip.handle, pybass.BASS_ATTRIB_VOL, clip.gain)
        start = pybass.BASS_ChannelSeconds2Bytes(self.handle, clip.at)
        length = pybass.BASS_ChannelSeconds2Bytes(self.handle, clip.end - clip.begin)
        return bool(mix.BASS_Mixer_StreamAddChannelEx(
            self.handle, clip.handle, pybass.BASS_STREAM_AUTOFREE | DECK_FLAGS,
            start, length))

    def Close(self):
        for clip in self.clips:
            clip.handle = 0
        Source.Close(self)

    def GetSpec(self):
        return dict(kind=self.KIND, clips=[clip.GetSpec() for clip in self.clips])


def edit_to_clips(path, edit):
    '''SHORT's plan (start, end, cuts: mfeats.choose_radio_edit) as clips one after another
    on a timeline from 0: what it plays, end to end (the jumps' sound, as a timeline's: an
    arrangement's first one)'''
    start, end, cuts = edit
    bounds = [start] + [v for cut in sorted(cuts) for v in cut] + [end]
    clips, at = [], 0.0
    for begin, until in zip(bounds[0::2], bounds[1::2]):
        if until > begin:
            clips.append(Clip(path, begin, until, at))
            at += until - begin
    return clips


SOURCES = dict(tone=lambda spec: ToneSource(spec.get('freq', 1000.0), spec.get('level', 0.5)),
               vsti=lambda spec: VSTInstrumentSource(spec['path']),
               timeline=lambda spec: TimelineSource(
                   [Clip(**clip) for clip in spec.get('clips', [])]))


def make_source(spec):
    # a kept source made again (Graph.SetData), None for a kind not kept (a handle's)
    make = SOURCES.get((spec or {}).get('kind'))
    return make(spec) if make else None


class FxSlot():

    '''an effect in a chain: a VST (path) or a built-in one by name (BUILTIN_FX: its DLL's
    path found when applied), its parameters (index: 0 to 1), on or bypassed; or one of
    bass_fx's (path 'bfx:' its name: effects.py, MIXER's inserts), its parameters by key in
    their units'''

    def __init__(self, path, params=None, bypass=False, name=''):
        self.path = path
        self.params = dict(params or {})
        self.bypass = bypass
        self.name = name
        self.handle = 0
        # (bass_fx's: the handle it is on, its priority there: put on again unbypassed)
        self.target = 0
        self.priority = 0

    def GetEffect(self):
        return effects.get_name(self.path)

    def GetPath(self):
        find = BUILTIN_FX.get(self.path)
        return find() if find else self.path

    def SetParam(self, index, value):
        if self.GetEffect():
            self.params[index] = float(value)
            if self.handle:
                effects.set_values(self.handle, self.GetEffect(), self.params)
            return
        self.params[index] = min(max(float(value), 0.0), 1.0)
        if self.handle:
            pybass.BASS_VST_SetParam(self.handle, index, self.params[index])

    def SetBypass(self, bypass):
        self.bypass = bool(bypass)
        if self.GetEffect():
            # (bass_fx's have no bypass: off its handle, on again)
            if self.bypass and self.handle:
                effects.remove(self.target, self.handle)
                self.handle = 0
            elif not self.bypass and not self.handle and self.target:
                self.handle = effects.apply(self.target, self.GetEffect(), self.params,
                                            self.priority)
            return
        if self.handle:
            pybass.BASS_VST_SetBypass(self.handle, self.bypass)

    def GetSpec(self):
        return dict(path=self.path, params=dict(self.params), bypass=self.bypass,
                    name=self.name)


def find_automaster():
    try:
        return pybass.bass.load('PyMusicPlayerAutoMaster.dll')[0]._name
    except (FileNotFoundError, OSError):
        return None


# effects by name (their DLLs where the player's are), as a slot's path
BUILTIN_FX = dict(automaster=find_automaster)


class FxChain():

    '''effects in order on a handle (a deck's before its channel, a bus's mixer): put on
    again when the handle is new (a deck's next song), kept as their specs'''

    def __init__(self, slots=()):
        self.slots = list(slots)
        self.target = 0

    def Apply(self, handle):
        self.Remove()
        self.target = handle
        if not handle:
            return
        for k, slot in enumerate(self.slots):
            if slot.GetEffect():
                slot.target, slot.priority = handle, FX_PRIORITY - k
                slot.handle = 0 if slot.bypass else effects.apply(
                    handle, slot.GetEffect(), slot.params, FX_PRIORITY - k)
                continue
            path = slot.GetPath()
            slot.handle = pybass.BASS_VST_ChannelSetDSP(
                handle, path, pybass.BASS_UNICODE | pybass.BASS_VST_KEEP_CHANS,
                FX_PRIORITY - k) if path else 0
            if not slot.handle:
                continue
            for index, value in slot.params.items():
                pybass.BASS_VST_SetParam(slot.handle, int(index), value)
            pybass.BASS_VST_SetBypass(slot.handle, slot.bypass)

    def Remove(self):
        for slot in self.slots:
            if slot.handle and self.target:
                if slot.GetEffect():
                    effects.remove(self.target, slot.handle)
                else:
                    pybass.BASS_VST_ChannelRemoveDSP(self.target, slot.handle)
            slot.handle = 0
            slot.target = 0
        self.target = 0

    def Insert(self, index, slot):
        # a slot put in (the chain on its handle again: the DSPs' order is their priority)
        self.slots.insert(index, slot)
        self.Apply(self.target)

    def Pop(self, index):
        slot = self.slots[index]
        self.Remove()
        target = self.target
        self.slots.pop(index)
        self.Apply(target)
        return slot

    def Move(self, index, to):
        target = self.target
        self.Remove()
        self.slots.insert(to, self.slots.pop(index))
        self.Apply(target)

    def GetSpec(self):
        return [slot.GetSpec() for slot in self.slots]


def make_chain(specs):
    return FxChain([FxSlot(**spec) for spec in specs or []])


class Channel():

    '''a deck's or a bus's level: gain (1 at 0 dB), pan (-1 left to 1 right), mute, solo'''

    def __init__(self, gain=1.0, pan=0.0, mute=False, solo=False):
        self.gain = gain
        self.pan = pan
        self.mute = mute
        self.solo = solo

    def GetSpec(self):
        return dict(gain=self.gain, pan=self.pan, mute=self.mute, solo=self.solo)


# the send buses (their effects their returns, into the master), each deck's send to them
# a level (after its fader)
SENDS = ('send A', 'send B')


class Deck():

    def __init__(self, deck_id, source, bus=MASTER, chain=None, channel=None):
        self.id = deck_id
        self.source = source
        self.bus = bus
        self.chain = chain or FxChain()
        self.channel = channel or Channel()
        self.handle = 0
        # its sends' levels by bus; (split) the handle in its bus (a splitter, or its
        # source's own) and its splitters to the send buses
        self.sends = {}
        self.out = 0
        self.splits = {}


class Bus():

    def __init__(self, bus_id, parent=None, chain=None, channel=None):
        self.id = bus_id
        self.parent = parent
        self.chain = chain or FxChain()
        self.channel = channel or Channel()
        self.handle = 0


class Graph():

    '''the wiring: decks and buses by their ids, the master bus always there. Build makes the
    channels (Free lets them go); while built, a change (a route, a channel, a deck in or
    out) is put on them at once'''

    def __init__(self):
        self.decks = {}
        self.buses = {MASTER: Bus(MASTER)}
        self.built = False
        self.decode = False
        # the player's volume on the master (SetOutput)
        self.output = 1.0

    # the data

    def AddBus(self, bus_id, parent=MASTER):
        if bus_id in self.buses or parent not in self.buses:
            return None
        bus = Bus(bus_id, parent)
        self.buses[bus_id] = bus
        if self.built:
            self.BuildBus(bus)
        return bus

    def RemoveBus(self, bus_id):
        # its decks and buses to its parent
        bus = self.buses.get(bus_id)
        if bus is None or bus_id == MASTER:
            return
        for deck in self.decks.values():
            if deck.bus == bus_id:
                self.Route(deck.id, bus.parent)
        for other in self.buses.values():
            if other.parent == bus_id:
                self.RouteBus(other.id, bus.parent)
        if self.built:
            self.FreeBus(bus)
        del self.buses[bus_id]

    def AddDeck(self, deck_id, source, bus=MASTER):
        if deck_id in self.decks:
            self.RemoveDeck(deck_id)
        deck = Deck(deck_id, source, bus if bus in self.buses else MASTER)
        self.decks[deck_id] = deck
        if self.built:
            self.BuildDeck(deck)
        return deck

    def RemoveDeck(self, deck_id):
        deck = self.decks.pop(deck_id, None)
        if deck is not None and self.built:
            self.FreeDeck(deck)
            # (a solo gone with it: the others heard again)
            self.ApplyChannels()
        return deck

    def SetSource(self, deck_id, source):
        # a deck's sound changed (the next song): its chain and channel on the new handle,
        # in the same bus
        deck = self.decks[deck_id]
        if self.built:
            self.FreeDeck(deck)
        deck.source = source
        if self.built:
            self.BuildDeck(deck)

    def Route(self, deck_id, bus_id):
        deck = self.decks[deck_id]
        if bus_id not in self.buses or deck.bus == bus_id:
            return
        deck.bus = bus_id
        if self.built and deck.handle:
            mix.BASS_Mixer_ChannelRemove(deck.handle)
            self.Connect(deck.handle, self.buses[bus_id].handle)

    def RouteBus(self, bus_id, parent):
        bus = self.buses[bus_id]
        if bus_id == MASTER or parent not in self.buses or self.IsUnder(parent, bus_id):
            return
        bus.parent = parent
        if self.built and bus.handle:
            mix.BASS_Mixer_ChannelRemove(bus.handle)
            self.Connect(bus.handle, self.buses[parent].handle)

    def IsUnder(self, bus_id, other):
        # bus_id is other or under it (a bus routed into its own child would loop)
        while bus_id is not None:
            if bus_id == other:
                return True
            bus_id = self.buses[bus_id].parent
        return False

    def GetChain(self, deck_id=None, bus_id=None):
        # a deck's effects (its own, before its channel) or a bus's
        if deck_id is not None:
            return self.decks[deck_id].chain
        return self.buses[bus_id or MASTER].chain

    def SetChannel(self, deck_id=None, bus_id=None, **values):
        # a deck's or a bus's gain, pan, mute or solo (a solo mutes the decks not soloed)
        target = self.decks[deck_id] if deck_id is not None else self.buses[bus_id]
        for name, value in values.items():
            setattr(target.channel, name, value)
        if self.built:
            self.ApplyChannels()

    # the channels

    def Build(self, decode=False):
        '''the mixers, the decks' handles in them and the chains; decode: the master too
        decodes (read by BASS_ChannelGetData: tests, a render), else it plays'''
        self.Free()
        self.decode = decode
        self.built = True
        for bus in self.GetBusesTopDown():
            self.BuildBus(bus)
        for deck in self.decks.values():
            self.BuildDeck(deck)
        self.ApplyChannels()
        if decode is False:
            # no playback buffer of the mixer's own over the device's (bassmix's advice):
            # what is mixed heard as soon as a stream on its own was (a seek 40 ms late
            # with it, 10 without, measured)
            pybass.BASS_ChannelSetAttribute(self.buses[MASTER].handle, BASS_ATTRIB_BUFFER, 0)
            pybass.BASS_ChannelPlay(self.buses[MASTER].handle, False)
        return self.buses[MASTER].handle

    def Free(self):
        for deck in self.decks.values():
            self.FreeDeck(deck)
        for bus in reversed(self.GetBusesTopDown()):
            self.FreeBus(bus)
        self.built = False

    def GetBusesTopDown(self):
        done, order = set(), []
        while len(order) < len(self.buses):
            for bus in self.buses.values():
                if bus.id not in done and (bus.parent is None or bus.parent in done):
                    order.append(bus)
                    done.add(bus.id)
        return order

    def BuildBus(self, bus):
        flags = pybass.BASS_SAMPLE_FLOAT | mix.BASS_MIXER_NONSTOP
        if bus.id != MASTER or self.decode:
            flags |= pybass.BASS_STREAM_DECODE
        bus.handle = mix.BASS_Mixer_StreamCreate(MIX_RATE, MIX_CHANS, flags)
        if bus.parent is not None:
            self.Connect(bus.handle, self.buses[bus.parent].handle)
        bus.chain.Apply(bus.handle)

    def FreeBus(self, bus):
        bus.chain.Remove()
        if bus.handle:
            pybass.BASS_StreamFree(bus.handle)
        bus.handle = 0

    def BuildDeck(self, deck):
        deck.handle = deck.source.Open() if deck.source is not None else 0
        deck.out, deck.splits = 0, {}
        if not deck.handle:
            return
        deck.chain.Apply(deck.handle)
        sends = [bus_id for bus_id in SENDS if bus_id in self.buses]
        if getattr(deck.source, 'SPLIT', False) and sends:
            # (split: a mixer and a splitter can not both read a stream, both glitched)
            deck.out = mix.BASS_Split_StreamCreate(deck.handle, pybass.BASS_STREAM_DECODE, 0)
            self.Connect(deck.out, self.buses[deck.bus].handle)
            for bus_id in sends:
                split = mix.BASS_Split_StreamCreate(deck.handle, pybass.BASS_STREAM_DECODE, 0)
                if split and self.buses[bus_id].handle:
                    self.Connect(split, self.buses[bus_id].handle)
                    deck.splits[bus_id] = split
        else:
            deck.out = deck.handle
            self.Connect(deck.handle, self.buses[deck.bus].handle)
        # (the source told where it is heard: its hits' lead read there)
        if deck.source is not None:
            deck.source.out = deck.out
        self.ApplyChannels()

    def FreeDeck(self, deck):
        deck.chain.Remove()
        for split in list(deck.splits.values()) + ([deck.out] if deck.out != deck.handle
                                                   else []):
            if split:
                mix.BASS_Mixer_ChannelRemove(split)
                pybass.BASS_StreamFree(split)
        if deck.handle:
            mix.BASS_Mixer_ChannelRemove(deck.handle)
        if deck.source is not None:
            deck.source.Close()
        deck.handle, deck.out, deck.splits = 0, 0, {}

    def SetSend(self, deck_id, bus_id, level):
        deck = self.decks.get(deck_id)
        if deck is not None:
            deck.sends[bus_id] = min(max(float(level), 0.0), 1.0)
            self.ApplyChannels()

    def Connect(self, handle, mixer):
        return bool(mix.BASS_Mixer_StreamAddChannel(mixer, handle, DECK_FLAGS))

    def ApplyChannels(self):
        # each deck's and bus's gain and pan: in its mixer by a matrix (set_matrix), the
        # master's on its own handle (it plays); the muted (or not soloed, while one is)
        # at 0
        soloed = any(deck.channel.solo for deck in self.decks.values())
        for target in list(self.decks.values()) + list(self.buses.values()):
            if not target.handle:
                continue
            channel = target.channel
            silent = channel.mute or (soloed and isinstance(target, Deck)
                                      and channel.solo is False)
            gain = 0.0 if silent else channel.gain
            if isinstance(target, Bus) and target.id == MASTER:
                pybass.BASS_ChannelSetAttribute(target.handle, pybass.BASS_ATTRIB_VOL,
                                                gain * self.output)
                pybass.BASS_ChannelSetAttribute(target.handle, pybass.BASS_ATTRIB_PAN,
                                                channel.pan)
            elif isinstance(target, Deck):
                set_matrix(target.out or target.handle, gain, channel.pan)
                # its sends after its fader
                for bus_id, split in target.splits.items():
                    set_matrix(split, gain * target.sends.get(bus_id, 0.0), channel.pan)
            else:
                set_matrix(target.handle, gain, channel.pan)

    def SetOutput(self, volume):
        '''the player's volume, the master's last (after its chain: Auto Master's AGC
        before it, not working against it), its fader with it'''
        if abs(volume - self.output) < 1e-6:
            return
        self.output = volume
        master = self.buses[MASTER]
        if self.built and master.handle:
            channel = master.channel
            pybass.BASS_ChannelSetAttribute(master.handle, pybass.BASS_ATTRIB_VOL,
                                            0.0 if channel.mute else channel.gain * volume)

    def GetPeak(self, deck_id=None, bus_id=None):
        '''(left, right) a deck's or a bus's peak as heard (0 to 1): a deck's after its
        own volume and its channel, the master's as it plays'''
        target = self.decks.get(deck_id) if deck_id is not None else self.buses.get(bus_id)
        if target is None or not target.handle:
            return 0.0, 0.0
        if isinstance(target, Bus) and target.id == MASTER:
            level = pybass.BASS_ChannelGetLevel(target.handle)
            if level in (-1, 0xFFFFFFFF):
                return 0.0, 0.0
            return (level & 0xFFFF) / 32768.0, (level >> 16) / 32768.0
        # (bassmix's: before the source's volume and its matrix)
        handle = target.out or target.handle if isinstance(target, Deck) else target.handle
        level = mix.BASS_Mixer_ChannelGetLevel(handle)
        if level in (-1, 0xFFFFFFFF):
            return 0.0, 0.0
        volume = ctypes.c_float(1.0)
        pybass.BASS_ChannelGetAttribute(target.handle, pybass.BASS_ATTRIB_VOL,
                                        ctypes.byref(volume))
        channel = target.channel
        soloed = any(deck.channel.solo for deck in self.decks.values())
        silent = channel.mute or (soloed and isinstance(target, Deck) and not channel.solo)
        left, right = pan_gains(0.0 if silent else channel.gain, channel.pan)
        return ((level & 0xFFFF) / 32768.0 * volume.value * left,
                (level >> 16) / 32768.0 * volume.value * right)

    # the taps, floats: a deck's after its chain, before its channel (bassmix's source data:
    # a meter's pre-fader); the master's all of it, after its chain

    def ReadDeck(self, deck_id, count):
        deck = self.decks[deck_id]
        return read_floats(deck.out or deck.handle, count, mixer_source=True)

    def ReadMaster(self, count):
        return read_floats(self.buses[MASTER].handle, count)

    # kept as data (the settings): the buses, the routes, the chains, the channels and the
    # sources that can be made again

    def GetData(self):
        return dict(
            buses=[dict(id=bus.id, parent=bus.parent, chain=bus.chain.GetSpec(),
                        channel=bus.channel.GetSpec()) for bus in self.GetBusesTopDown()],
            decks=[dict(id=deck.id, bus=deck.bus, chain=deck.chain.GetSpec(),
                        channel=deck.channel.GetSpec(),
                        source=deck.source.GetSpec() if deck.source else None)
                   for deck in self.decks.values()])

    def SetData(self, data, sources=None):
        '''the wiring from GetData's; sources: {deck id: Source} for the decks whose sound
        is made elsewhere (the player's), else made from their kept specs'''
        built, decode = self.built, self.decode
        self.Free()
        self.decks = {}
        self.buses = {MASTER: Bus(MASTER)}
        for spec in data.get('buses', []):
            if spec['id'] != MASTER:
                self.buses[spec['id']] = Bus(spec['id'], spec.get('parent') or MASTER)
            bus = self.buses[spec['id']]
            bus.chain = make_chain(spec.get('chain'))
            bus.channel = Channel(**spec.get('channel', {}))
        for spec in data.get('decks', []):
            source = (sources or {}).get(spec['id']) or make_source(spec.get('source'))
            deck = Deck(spec['id'], source, spec.get('bus', MASTER)
                        if spec.get('bus') in self.buses else MASTER,
                        make_chain(spec.get('chain')), Channel(**spec.get('channel', {})))
            self.decks[deck.id] = deck
        if built:
            self.Build(decode)


def pan_gains(gain, pan):
    # (left, right): a balance (the centre at full on both, a side turned down)
    return gain * min(1.0, 1.0 - pan), gain * min(1.0, 1.0 + pan)


def set_matrix(handle, gain, pan):
    '''a source's gain and pan in its mixer (MIX_CHANS out): a mono one to both sides, a
    stereo one side to side, more channels folded to their sides'''
    info = pybass.BASS_CHANNELINFO()
    pybass.BASS_ChannelGetInfo(handle, ctypes.byref(info))
    chans = max(info.chans, 1)
    sides = pan_gains(gain, pan)
    matrix = (ctypes.c_float * (MIX_CHANS * chans))()
    share = 1.0 / max(chans // 2, 1)
    for out in range(MIX_CHANS):
        for k in range(chans):
            if chans == 1:
                matrix[out * chans + k] = sides[out]
            elif k % 2 == out:
                matrix[out * chans + k] = sides[out] * share
    return bool(mix.BASS_Mixer_ChannelSetMatrix(handle, matrix))


def read_floats(handle, count, mixer_source=False):
    '''count floats (interleaved) read from a handle: a decoding one's next, a playing one's
    or a mixer source's last (its data kept: DECK_FLAGS), [] for none'''
    if not handle:
        return []
    buffer = (ctypes.c_float * count)()
    size = ctypes.sizeof(buffer) | pybass.BASS_DATA_FLOAT
    if mixer_source:
        got = mix.BASS_Mixer_ChannelGetData(handle, buffer, size)
    else:
        got = pybass.BASS_ChannelGetData(handle, buffer, size)
    if got in (-1, 0xFFFFFFFF):
        return []
    return list(buffer[:got // 4])
