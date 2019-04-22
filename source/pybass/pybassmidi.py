# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybassmidi.py - is ctypes python module for
BASSMIDI - extension to the BASS audio library,
enabling the playing of MIDI files and real-time events,
using SF2 soundfonts to provide the sounds.
'''


import ctypes


try:
    import bass
    import pybass
except ImportError:
    from .import bass
    from .import pybass


bassmidi_module, func_type = bass.load(__file__)


HSOUNDFONT = ctypes.c_ulong


QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
DOWNLOADPROC = pybass.DOWNLOADPROC
BASS_FILEPROCS = pybass.BASS_FILEPROCS


# Additional BASS_SetConfig options
BASS_CONFIG_MIDI_COMPACT = 0x10400
BASS_CONFIG_MIDI_VOICES = 0x10401
BASS_CONFIG_MIDI_AUTOFONT = 0x10402


# Additional BASS_SetConfigPtr options
BASS_CONFIG_MIDI_DEFFONT = 0x10403


# Additional sync types
BASS_SYNC_MIDI_MARKER = 0x10000
BASS_SYNC_MIDI_CUE = 0x10001
BASS_SYNC_MIDI_LYRIC = 0x10002
BASS_SYNC_MIDI_TEXT = 0x10003
BASS_SYNC_MIDI_EVENT = 0x10004
BASS_SYNC_MIDI_TICK = 0x10005
BASS_SYNC_MIDI_TIMESIG = 0x10006


# Additional BASS_MIDI_StreamCreateFile/etc flags
BASS_MIDI_DECAYEND = 0x1000
BASS_MIDI_NOFX = 0x2000
BASS_MIDI_DECAYSEEK = 0x4000


class BASS_MIDI_FONT(ctypes.Structure):
    _fields_ = [
        ('font', HSOUNDFONT),  # HSOUNDFONT font; // soundfont
        ('preset', ctypes.c_int),  # int preset; // preset number (-1=all)
        ('bank', ctypes.c_int)  # int bank;
    ]


class BASS_MIDI_FONTINFO(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char_p),  # const char *name;
        ('copyright', ctypes.c_char_p),  # const char *copyright;
        ('comment', ctypes.c_char_p),  # const char *comment;
        ('presets', ctypes.c_ulong),  # DWORD presets; // number of presets/instruments
        ('samsize', ctypes.c_ulong),  # DWORD samsize; // total size (in bytes) of the sample data
        ('samload', ctypes.c_ulong),  # DWORD samload; // amount of sample data currently loaded
        ('samtype', ctypes.c_ulong)  # DWORD samtype; // sample format (CTYPE) if packed
    ]


class BASS_MIDI_MARK(ctypes.Structure):
    _fields_ = [('track', ctypes.c_ulong),  # DWORD track; // track containing marker
                ('pos', ctypes.c_ulong),  # DWORD pos; // marker position (bytes)
                ('text', ctypes.c_char_p)  # const char *text; // marker text
                ]


# Marker types
BASS_MIDI_MARK_MARKER = 0  # marker events
BASS_MIDI_MARK_CUE = 1  # cue events
BASS_MIDI_MARK_LYRIC = 2  # lyric events
BASS_MIDI_MARK_TEXT = 3  # text events
BASS_MIDI_MARK_TIMESIG = 4  # time signature


# MIDI events
MIDI_EVENT_NOTE = 1
MIDI_EVENT_PROGRAM = 2
MIDI_EVENT_CHANPRES = 3
MIDI_EVENT_PITCH = 4
MIDI_EVENT_PITCHRANGE = 5
MIDI_EVENT_DRUMS = 6
MIDI_EVENT_FINETUNE = 7
MIDI_EVENT_COARSETUNE = 8
MIDI_EVENT_MASTERVOL = 9
MIDI_EVENT_BANK = 10
MIDI_EVENT_MODULATION = 11
MIDI_EVENT_VOLUME = 12
MIDI_EVENT_PAN = 13
MIDI_EVENT_EXPRESSION = 14
MIDI_EVENT_SUSTAIN = 15
MIDI_EVENT_SOUNDOFF = 16
MIDI_EVENT_RESET = 17
MIDI_EVENT_NOTESOFF = 18
MIDI_EVENT_PORTAMENTO = 19
MIDI_EVENT_PORTATIME = 20
MIDI_EVENT_PORTANOTE = 21
MIDI_EVENT_MODE = 22
MIDI_EVENT_REVERB = 23
MIDI_EVENT_CHORUS = 24
MIDI_EVENT_CUTOFF = 25
MIDI_EVENT_RESONANCE = 26
MIDI_EVENT_RELEASE = 27
MIDI_EVENT_ATTACK = 28
MIDI_EVENT_REVERB_MACRO = 30
MIDI_EVENT_CHORUS_MACRO = 31
MIDI_EVENT_REVERB_TIME = 32
MIDI_EVENT_REVERB_DELAY = 33
MIDI_EVENT_REVERB_LOCUTOFF = 34
MIDI_EVENT_REVERB_HICUTOFF = 35
MIDI_EVENT_REVERB_LEVEL = 36
MIDI_EVENT_CHORUS_DELAY = 37
MIDI_EVENT_CHORUS_DEPTH = 38
MIDI_EVENT_CHORUS_RATE = 39
MIDI_EVENT_CHORUS_FEEDBACK = 40
MIDI_EVENT_CHORUS_LEVEL = 41
MIDI_EVENT_CHORUS_REVERB = 42
MIDI_EVENT_DRUM_FINETUNE = 50
MIDI_EVENT_DRUM_COARSETUNE = 51
MIDI_EVENT_DRUM_PAN = 52
MIDI_EVENT_DRUM_REVERB = 53
MIDI_EVENT_DRUM_CHORUS = 54
MIDI_EVENT_DRUM_CUTOFF = 55
MIDI_EVENT_DRUM_RESONANCE = 56
MIDI_EVENT_DRUM_LEVEL = 57
MIDI_EVENT_TEMPO = 62
MIDI_EVENT_MIXLEVEL = 0x10000
MIDI_EVENT_TRANSPOSE = 0x10001


class BASS_MIDI_EVENT(ctypes.Structure):
    _fields_ = [
        ('event', ctypes.c_ulong),  # DWORD event; // MIDI_EVENT_xxx
        ('param', ctypes.c_ulong),  # DWORD param;
        ('chan', ctypes.c_ulong),  # DWORD chan;
        ('tick', ctypes.c_ulong),  # DWORD tick; // event position (ticks)
        ('pos', ctypes.c_ulong)  # DWORD pos; // event position (bytes)
    ]


# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_MIDI = 0x10d00


# Additional attributes
BASS_ATTRIB_MIDI_PPQN = 0x12000
BASS_ATTRIB_MIDI_TRACK_VOL = 0x12100  # + track #


# Additional tag type
BASS_TAG_MIDI_TRACK = 0x11000  # + track #, track text : array of null-terminated ANSI strings


# BASS_ChannelGetLength/GetPosition/SetPosition mode
BASS_POS_MIDI_TICK = 2  # tick position


# HSTREAM BASSMIDIDEF(BASS_MIDI_StreamCreate)(DWORD channels, DWORD flags, DWORD freq);
BASS_MIDI_StreamCreate = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_MIDI_StreamCreate', bassmidi_module))


# HSTREAM BASSMIDIDEF(BASS_MIDI_StreamCreateFile)(
# BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags, DWORD freq);
BASS_MIDI_StreamCreateFile = func_type(
    HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_MIDI_StreamCreateFile', bassmidi_module))


# HSTREAM BASSMIDIDEF(BASS_MIDI_StreamCreateURL)(
# const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user, DWORD freq);
BASS_MIDI_StreamCreateURL = func_type(
    HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p, ctypes.c_ulong
)(('BASS_MIDI_StreamCreateURL', bassmidi_module))


# HSTREAM BASSMIDIDEF(BASS_MIDI_StreamCreateFileUser)(
# DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user, DWORD freq);
BASS_MIDI_StreamCreateFileUser = func_type(
    HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p, ctypes.c_ulong
)(('BASS_MIDI_StreamCreateFileUser', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_StreamGetMark)(
# HSTREAM handle, DWORD type, DWORD index, BASS_MIDI_MARK *mark);
BASS_MIDI_StreamGetMark = func_type(
    ctypes.c_byte, HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_MIDI_MARK)
)(('BASS_MIDI_StreamGetMark', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_StreamSetFonts)(
# HSTREAM handle, const BASS_MIDI_FONT *fonts, DWORD count);
BASS_MIDI_StreamSetFonts = func_type(
    ctypes.c_byte, HSTREAM, ctypes.POINTER(BASS_MIDI_FONT), ctypes.c_ulong
)(('BASS_MIDI_StreamSetFonts', bassmidi_module))


# DWORD BASSMIDIDEF(BASS_MIDI_StreamGetFonts)(
# HSTREAM handle, BASS_MIDI_FONT *fonts, DWORD count);
BASS_MIDI_StreamGetFonts = func_type(
    ctypes.c_ulong, HSTREAM, ctypes.POINTER(BASS_MIDI_FONT), ctypes.c_ulong
)(('BASS_MIDI_StreamGetFonts', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_StreamLoadSamples)(HSTREAM handle);
BASS_MIDI_StreamLoadSamples = func_type(
    ctypes.c_byte, HSTREAM
)(('BASS_MIDI_StreamLoadSamples', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_StreamEvent)(
# HSTREAM handle, DWORD chan, DWORD event, DWORD param);
BASS_MIDI_StreamEvent = func_type(
    ctypes.c_byte, HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_MIDI_StreamEvent', bassmidi_module))


# DWORD BASSMIDIDEF(BASS_MIDI_StreamGetEvent)(
# HSTREAM handle, DWORD chan, DWORD event);
BASS_MIDI_StreamGetEvent = func_type(
    ctypes.c_ulong, HSTREAM, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_MIDI_StreamGetEvent', bassmidi_module))


# DWORD BASSMIDIDEF(BASS_MIDI_StreamGetEvents)(
# HSTREAM handle, DWORD track, DWORD filter, BASS_MIDI_EVENT *events);
BASS_MIDI_StreamGetEvents = func_type(
    ctypes.c_ulong, HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_MIDI_EVENT)
)(('BASS_MIDI_StreamGetEvents', bassmidi_module))


# HSTREAM BASSMIDIDEF(BASS_MIDI_StreamGetChannel)(
# HSTREAM handle, DWORD chan);
BASS_MIDI_StreamGetChannel = func_type(
    HSTREAM, HSTREAM, ctypes.c_ulong
)(('BASS_MIDI_StreamGetChannel', bassmidi_module))


# HSOUNDFONT BASSMIDIDEF(BASS_MIDI_FontInit)(
# const void *file, DWORD flags);
BASS_MIDI_FontInit = func_type(
    HSOUNDFONT, ctypes.c_void_p, ctypes.c_ulong
)(('BASS_MIDI_FontInit', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_FontFree)(
# HSOUNDFONT handle);
BASS_MIDI_FontFree = func_type(
    ctypes.c_byte, HSOUNDFONT
)(('BASS_MIDI_FontFree', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_FontGetInfo)(
# HSOUNDFONT handle, BASS_MIDI_FONTINFO *info);
BASS_MIDI_FontGetInfo = func_type(
    ctypes.c_byte, HSOUNDFONT, ctypes.POINTER(BASS_MIDI_FONTINFO)
)(('BASS_MIDI_FontGetInfo', bassmidi_module))


# const char *BASSMIDIDEF(BASS_MIDI_FontGetPreset)(
# HSOUNDFONT handle, int preset, int bank);
BASS_MIDI_FontGetPreset = func_type(
    ctypes.c_char_p, HSOUNDFONT, ctypes.c_int, ctypes.c_int
)(('BASS_MIDI_FontGetPreset', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_FontLoad)(
# HSOUNDFONT handle, int preset, int bank);
BASS_MIDI_FontLoad = func_type(
    ctypes.c_byte, HSOUNDFONT, ctypes.c_int, ctypes.c_int
)(('BASS_MIDI_FontLoad', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_FontCompact)(
# HSOUNDFONT handle);
BASS_MIDI_FontCompact = func_type(
    ctypes.c_byte, HSOUNDFONT
)(('BASS_MIDI_FontCompact', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_FontPack)(
# HSOUNDFONT handle, const void *outfile, const void *encoder, DWORD flags);
BASS_MIDI_FontPack = func_type(
    ctypes.c_byte, HSOUNDFONT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong
)(('BASS_MIDI_FontPack', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_FontUnpack)(
# HSOUNDFONT handle, const void *outfile, DWORD flags);
BASS_MIDI_FontUnpack = func_type(
    ctypes.c_byte, HSOUNDFONT, ctypes.c_void_p, ctypes.c_ulong
)(('BASS_MIDI_FontUnpack', bassmidi_module))


# BOOL BASSMIDIDEF(BASS_MIDI_FontSetVolume)(
# HSOUNDFONT handle, float volume);
BASS_MIDI_FontSetVolume = func_type(
    ctypes.c_byte, HSOUNDFONT, ctypes.c_float
)(('BASS_MIDI_FontSetVolume', bassmidi_module))


# float BASSMIDIDEF(BASS_MIDI_FontGetVolume)(
# HSOUNDFONT handle);
BASS_MIDI_FontGetVolume = func_type(
    ctypes.c_float, HSOUNDFONT
)(('BASS_MIDI_FontGetVolume', bassmidi_module))


if __name__ == '__main__':
    if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
        print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
    else:
        font = BASS_MIDI_FontInit(b'CT4MGM.SF2', 0)
        if font == 0:
            print('BASS_MIDI_FontInit error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
        else:
            font_info = BASS_MIDI_FONTINFO()
            if BASS_MIDI_FontGetInfo(font, font_info):
                print('============== SOUNDFONT Information ==============')
                print("name: %s\nloaded: %d / %d" % (font_info.name, font_info.samload, font_info.samsize))
            handle = BASS_MIDI_StreamCreateFile(False, b'test.mid', 0, 0, 0, 44100)
            pybass.play_handle(handle, False)
            if BASS_MIDI_FontFree(font):
                print('BASS_MIDI_FontFree error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
        if not pybass.BASS_Free():
            print('BASS_Free error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
