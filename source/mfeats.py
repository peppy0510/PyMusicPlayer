# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


# from __future__ import division


import os
import sys

from utilities import get_user_docapp_path


MFEATS_DB = os.path.join(get_user_docapp_path(), 'macroboxplayer.mfeats')


MFEATS_VERSION = '1.0.1'
# CLIENT_ADDRESS = ('localhost', 12501)
# SERVER_ADDRESS = ('localhost', 12502)
CLIENT_ADDRESS = ('127.0.0.1', 12702)
SERVER_ADDRESS = ('127.0.0.1', 12703)

WORKING_PATH = os.path.abspath(os.path.dirname(__file__))
try:
    packages = os.path.join(sys._MEIPASS, 'packages')
except Exception:
    packages = os.path.join(WORKING_PATH, 'packages')
sys.path.insert(0, packages)

PACKAGED = False
for v in ('27', '35', '36', '37', '38'):
    if os.path.isfile('python%s.dll' % (v)):
        PACKAGED = True
        break

if sys.platform.startswith('win'):
    if PACKAGED:
        PROCESS_NAME = 'mfeats.exe'
    else:
        PROCESS_NAME = 'python.exe'
elif sys.platform.startswith('darwin'):
    if PACKAGED:
        PROCESS_NAME = 'mfeats'
    else:
        PROCESS_NAME = 'python'


import ctypes
import multiprocessing
import mutagen
import numpy
import modpybass as pybass
# pybass = pybass.load()
import sqlite3
import threading
import time

from audio import fir_filter
from audio import get_channel
from audio import init_bass_decode
from copy import deepcopy
from macroboxlib import PREFERENCE_DB
from utilities import PipeMessenger
from utilities import Struct
from utilities import compress_object
from utilities import decompress_object  # noqa
from utilities import get_master_path
from utilities import get_memory_by_pid
from utilities import is_process_running_by_name
from utilities import is_process_running_by_pid
from utilities import kill_self_process
from utilities import makemdx
from utilities import open_shelves
from utilities import run_hidden_subprocess
from utilities import set_process_priority


# import multiprocessing.forking
# from audio import get_fs

# from audio import get_duration
# from utilities import open_shelve
# from utilities import SocketMessenger
# from utilities import is_packaged
# from utilities import get_most_common_element
# from utilities import decompress_object
# from utilities import file2md5
# from utilities import string2md5
# from utilities import PipeReceiver
# from utilities import send_pipe_message

# import thread
# import struct
# import gc
# import pylab


# tuple of (field_key, field_type)

# MFEATS_DEFINITION = (\
#   ('mdx', 'TEXT PRIMARY KEY'), ('path', 'TEXT'), ('duration', 'REAL'),\
#   ('channel', 'INTEGER'), ('bit', 'INTEGER'), ('samplerate', 'INTEGER'),\
#   ('bitrate', 'INTEGER'), ('key', 'TEXT'), ('tempo', 'REAL'),\
#   ('waveform', 'BLOB'), ('highlight', 'BLOB'), ('user_highlight', 'BLOB'),\
#   ('similar_artists', 'BLOB'), ('fingerprint', 'BLOB'), ('autogain', 'REAL'),\
#   ('md5', 'TEXT'), ('date', 'REAL'), ('version', 'TEXT'), ('error', 'INTEGER'),)
MFEATS_DEFINITION = (
    ('mdx', 'TEXT PRIMARY KEY'), ('path', 'TEXT'), ('duration', 'REAL'),
    ('channel', 'INTEGER'), ('bit', 'INTEGER'), ('samplerate', 'INTEGER'),
    ('bitrate', 'INTEGER'), ('key', 'TEXT'), ('tempo', 'REAL'),
    ('autogain', 'REAL'), ('waveform', 'BLOB'), ('highlight', 'BLOB'),
    ('date', 'REAL'), ('version', 'TEXT'), ('error', 'INTEGER'),)


class MFEATS(Struct):

    def __init__(self, **kwards):
        for field_key, field_type in MFEATS_DEFINITION:
            if field_type.startswith('REAL'):
                initial_value = '0.0'
            elif field_type.startswith('INTEGER'):
                initial_value = '0'
            elif field_type.startswith('TEXT') or field_type.startswith('BLOB'):
                initial_value = '""'
            exec('''self.%s = %s''' % (field_key, initial_value))
        self.__dict__.update(kwards)


# https://gist.github.com/endolith/255291
# http://wiki.hydrogenaudio.org/index.php?title=ReplayGain_1.0_specification
# https://gist.github.com/255291/c97d2b088c53104f1d0d7cf8b20e89fc788037df


def mfeats_single(path, queue=None):
    # uses mono data

    # tic = time.time()
    key, bit, error = ('', 16, 0)
    path = os.path.abspath(path)
    mdx = makemdx(path)
    # key_analysis_fs = 6000
    # waveform_length = 2000
    # waveform_oversampling = 20
    # key_analysis_fs = 6000
    # waveform_length = 2500
    # waveform_oversampling = 20
    waveform_length = 10000
    waveform_oversampling = 20
    best_highlight_duration_beat = 32 * 2
    # best_highlight_duration_beat = 16 * 2
    version = MFEATS_VERSION

    init_bass_decode()
    channel = get_channel(path)
    hstream = pybass.BASS_StreamCreateFile(
        False, path, 0, 0, pybass.BASS_STREAM_DECODE |
        pybass.BASS_STREAM_PRESCAN | pybass.BASS_UNICODE)
    fs = ctypes.c_float()
    pybass.BASS_ChannelGetAttribute(
        hstream, pybass.BASS_ATTRIB_FREQ, ctypes.byref(fs))
    fs = int(fs.value)
    hlength = pybass.BASS_ChannelGetLength(hstream, pybass.BASS_POS_BYTE)
    duration = pybass.BASS_ChannelBytes2Seconds(hstream, hlength)
    total_frame_length = hlength / 2

    if hstream == 0:
        error = 1

    if error == 1:
        mfeats_data = MFEATS(mdx=mdx, path=path, date=time.time(), version=version, error=1)
        if queue is not None:
            queue.put(mfeats_data)
            return
        else:
            return mfeats_data

    if total_frame_length / 2 < waveform_length:
        waveform_length = total_frame_length / 2
    frame_length = int(1.0 * total_frame_length / waveform_length) * 2
    if int(frame_length) % 8 != 0:
        frame_length += (8 - int(frame_length) % 8)
    gap = total_frame_length / frame_length - waveform_length
    waveform = numpy.linspace(0, 0, waveform_length + gap)
    highlight_raw_points = numpy.linspace(0, 0, waveform_length + gap)
    frame_raw = numpy.arange(frame_length, dtype=ctypes.c_short)
    jump = 1.0 * frame_length / waveform_oversampling

    analyze_frame, tempo_frame, tempo_fs = ([], [], 200)

    for cnt, frame_position in enumerate(
            numpy.arange(0, total_frame_length - frame_length, frame_length)):
        pybass.BASS_ChannelGetData(
            hstream, frame_raw.ctypes.data_as(ctypes.POINTER(ctypes.c_short)), int(frame_length * 2))

        mono_frame = deepcopy(frame_raw[::channel])
        analyze_frame += [mono_frame]
        if jump < waveform_oversampling:
            waveform[cnt] = numpy.max(numpy.abs(mono_frame))
        else:
            points = [numpy.max(numpy.abs(mono_frame[int(i):int(i + jump)]))
                      for i in numpy.arange(0, frame_length / channel - jump, jump)]
            waveform[cnt] = numpy.mean(points)
        highlight_raw_points[cnt] = numpy.mean(numpy.abs(mono_frame))

        # collect frames for long term analysis

        alength = len(analyze_frame) * len(analyze_frame[-1])
        if alength >= fs * 30 or alength * channel >= total_frame_length - frame_length:
            analyze_frame = numpy.concatenate(analyze_frame, axis=0)

            num = int(len(analyze_frame) / (1.0 * fs / tempo_fs))
            tempo_frame += [
                numpy.abs(numpy.interp(
                    numpy.linspace(0, len(analyze_frame) - 1, num),
                    numpy.arange(len(analyze_frame)), analyze_frame))]

            # key_frame_length = int(fs*0.25); key_frame_jump = 0.8
            # for i in range(0, len(analyze_frame)-key_frame_length,\
            #   int(key_frame_length*key_frame_jump)):
            #   spectrum = numpy.fft.fft(\
            #       analyze_frame[i:i+key_frame_length],\
            #       int(fs*key_analysis_resolution))
            #   spectrum = numpy.abs(spectrum[1:int(len(spectrum)/2)])
            #   notes = spectrum_to_note_by_max(spectrum, note_freq_div)
            #   chromagram += [note_to_chroma_by_max(notes)]
            analyze_frame = []

    # waveform

    waveform = numpy.int8(waveform / (2**8))

    # tempo analysis with tempo_frame

    # if duration > 60:
    #   tempo_frame = numpy.concatenate(tempo_frame, axis=0)
    #   tempo = get_tempo(tempo_frame, tempo_fs)
    # else: tempo = 0.0
    tempo_frame = numpy.concatenate(tempo_frame, axis=0)
    tempo = get_tempo(tempo_frame, tempo_fs)

    xtempo = tempo
    if xtempo <= 95:
        xtempo = xtempo * 2.0
    if xtempo == 0:
        until_duration = duration
    else:
        until_duration = 60.0 / xtempo * best_highlight_duration_beat

    # highlight analysis with highlight_raw_points

    jump = 1
    duratsum = []
    highlight_length = until_duration * len(highlight_raw_points) / duration
    duratsum = numpy.linspace(0, 0, len(highlight_raw_points))

    # limit_factor = 1-(duration-60.0)/duration
    # if limit_factor > 1.00: limit_factor = 0.00
    # if limit_factor < 0.25: limit_factor = 0.25
    # limithead = limit_factor
    # limittail = limit_factor
    # highlight_raw_points[:int(len(highlight_raw_points)*limithead)] = 0
    # highlight_raw_points[-int(len(highlight_raw_points)*limittail):] = 0

    limit_factor = 1 - (duration - 60.0) / duration
    if limit_factor > 1.00:
        limit_factor = 0.00
    if limit_factor < 0.25:
        limit_factor = 0.25
    htlength = int(len(highlight_raw_points) * limit_factor)
    window = numpy.hamming(htlength * 2)
    highlight_raw_points[:htlength] = highlight_raw_points[:htlength] * window[:htlength]
    highlight_raw_points[-htlength:] = highlight_raw_points[-htlength:] * window[htlength:]

    for cnt in numpy.arange(0, len(highlight_raw_points) - highlight_length, jump):
        thdata = numpy.mean(highlight_raw_points[int(cnt):int(cnt + highlight_length)])
        duratsum[int(cnt)] = thdata
    pntadd = numpy.argmax(duratsum)
    offset_time = 1.0 * jump * pntadd / (len(highlight_raw_points) / duration)
    highlight = (offset_time, until_duration)

    # autogain analysis in highlight period

    autogain = 0.4

    if duration > 60:

        autogain_analysis_length = highlight[1]
        if duration - highlight[0] < autogain_analysis_length:
            autogain_analysis_length = duration - highlight[0]
        frame_length = fs * channel * autogain_analysis_length
        byte_position = pybass.BASS_ChannelSeconds2Bytes(hstream, highlight[0])
        pybass.BASS_ChannelSetPosition(hstream, byte_position, False)
        frame_raw = numpy.arange(frame_length, dtype=ctypes.c_short)

        pybass.BASS_ChannelGetData(
            hstream,
            frame_raw.ctypes.data_as(ctypes.POINTER(ctypes.c_short)),
            int(frame_length * 2))

        mono_frame = frame_raw[::channel] / 32768.0
        mono_frame = fir_filter(mono_frame, lowcut=500, highcut=fs / 2, fs=fs, order=15)
        mono_frame = fir_filter(mono_frame, lowcut=1000, highcut=fs / 2, fs=fs, order=7)
        mono_frame = fir_filter(mono_frame, lowcut=1000, highcut=fs / 2, fs=fs, order=5)
        mono_frame = fir_filter(mono_frame, lowcut=5000, highcut=fs / 2, fs=fs, order=5)
        if fs / 2 > 21000:
            mono_frame = fir_filter(mono_frame, lowcut=0, highcut=20000, fs=fs, order=45)
            mono_frame += fir_filter(mono_frame, lowcut=15000, highcut=fs / 2, fs=fs, order=5) * 0.5
        rms = numpy.mean(mono_frame**2)**0.5 * 3

        # spectrum = numpy.fft.fft(mono_frame, fs)
        # spectrum = numpy.abs(spectrum[1:int(len(spectrum)/2)])
        # pylab.plot(spectrum); pylab.show()

        autogain = 0.14 / rms
    else:
        autogain = 0.4

    # key analysis in highlight period

    chromagram, resolution = ([], 1.0)
    note_freq_div = get_note_freq_div(resolution)
    # note_window = get_note_window(fs, resolution, note_freq_div)
    if xtempo == 0:
        frame_length = int(fs * channel * 0.5)
    else:
        frame_length = int(fs * channel * (60.0 / xtempo))

    offset_position, until_position = (highlight[0], fs * channel * until_duration * 2)

    if frame_length > total_frame_length:
        frame_length = total_frame_length - 1

    if offset_position + until_position > total_frame_length:
        until_position = total_frame_length - offset_position

    frame_raw = numpy.arange(frame_length, dtype=ctypes.c_short)
    byte_position = pybass.BASS_ChannelSeconds2Bytes(hstream, offset_position)
    pybass.BASS_ChannelSetPosition(hstream, byte_position, False)

    for cnt, frame_position in enumerate(
            numpy.arange(0, total_frame_length - frame_length, frame_length)):

        pybass.BASS_ChannelGetData(
            hstream, frame_raw.ctypes.data_as(ctypes.POINTER(ctypes.c_short)), int(frame_length * 2))

        mono_frame = frame_raw[::channel] / 32768.0
        spectrum = numpy.fft.fft(mono_frame, int(fs * resolution))
        spectrum = numpy.abs(spectrum[1:int(len(spectrum) / 2)])
        notes = spectrum_to_note_by_max(spectrum, note_freq_div)
        chromagram += [note_to_chroma_by_max(notes)]
        if (cnt + 1) * frame_length >= until_position:
            break

    scored_keys, key_scores, key_counts = ([], [0] * 24, [0] * 24)
    for chroma in chromagram:
        lag, score = get_chord_binaries_correlation_lag_score(chroma)
        scored_keys += [lag]
        key_counts[lag] += 1
        key_scores[lag] += score
    key_scores = numpy.array(key_scores)
    max_key_scores = max(key_scores)
    if max_key_scores == 0.0:
        key = ''
    else:
        key_scores = key_scores / max_key_scores * 100
        scored_key_idx = []
        for i in range(1):
            value, pnt = find_max(key_scores)
            if value < 50:
                break
            scored_key_idx += [pnt[0]]
            key_scores[pnt[0]] = 0
        string_keys = []
        for i in range(len(scored_key_idx) - 1, -1, -1):
            if scored_key_idx[i] - 12 in scored_key_idx:
                scored_key_idx.pop(i)
                continue
            elif scored_key_idx[i] + 12 in scored_key_idx:
                scored_key_idx.pop(i)
                continue
            string_keys += [chord_idx_to_char(scored_key_idx[i])]
        string_keys = ' or '.join(string_keys)
        key = '%s' % (string_keys)

    # chromagram = numpy.array(chromagram).T
    # chromagram = numpy.flipud(chromagram)
    # pylab.imshow(chromagram, interpolation='nearest')
    # pylab.show() # pylab.grid(True)

    # md5 = file2md5(upath)

    tempo_type, key_type, save_tag = open_shelves(
        ('tempo_restict_type', 'key_format_type', 'auto_save_tag'), PREFERENCE_DB)

    if tempo_type is None or tempo_type == 0:
        pass
    elif tempo_type == 1 and tempo <= 95:
        tempo = tempo * 2.0
    elif tempo_type == 2 and tempo >= 120:
        tempo = tempo * 0.5
    if key_type is None:
        key_type = 1
    key = convert_chord_type(key, key_type)
    if save_tag is None:
        save_tag = False
    if save_tag:
        mutagen_mp3 = mutagen.mp3.MP3(path)
        mutagen_mp3['TKEY'] = mutagen.id3.TKEY(encoding=3, text=[key])
        mutagen_mp3['TBPM'] = mutagen.id3.TBPM(encoding=3, text=[tempo])
        mutagen_mp3.save()

    mfeats_data = MFEATS(mdx=mdx, path=path, key=key, tempo=tempo,
                         duration=duration, highlight=highlight, waveform=waveform,
                         date=time.time(), version=version, channel=channel, bit=bit, error=0,
                         autogain=autogain)

    # pybass.BASS_Free()
    if pybass.BASS_ChannelIsActive(hstream) == 1:
        pybass.BASS_StreamFree(hstream)

    # print 'mfeats_single_finished: elapsed_time: %03.06fsec: %03.06fmsec/onesec'\
    #   % (time.time()-tic, (time.time()-tic)/duration*1000)
    # return mfeats_data

    if queue is not None:
        queue.put(mfeats_data)
        return
    else:
        return mfeats_data


def note_to_chroma_by_sum(notes):
    return [sum(notes[i::12]) for i in range(12)]


def note_to_chroma_by_max(notes):
    return [max(notes[i::12]) for i in range(12)]


def spectrum_to_note_by_max(spectrum, note_freq_div):
    notes = numpy.zeros(len(note_freq_div))
    for i in range(len(note_freq_div) - 1):
        elem = spectrum[note_freq_div[i]:note_freq_div[i + 1]]
        if elem != []:
            notes[i] = max(elem)
    return notes


def freq_to_note_idx(freq):
    return int(round(57 + numpy.log2(freq / 440.0) * 12))


def note_idx_to_freq(note):
    return 440 * 2**((note - 57) / 12.0)


def freq_to_note_cent(freq):
    value = 57 + numpy.log2(freq / 440.0) * 12
    return int(round(value)) - value


def note_idx_to_freq_range(note):
    bin_from = int(round(440 * 2**((note - 0.5 - 57) / 12.0)))
    bin_until = int(round(440 * 2**((note + 0.5 - 57) / 12.0)))
    return range(bin_from, bin_until)


def get_note_freq_div(scale=1.0):
    note_freq_div = numpy.arange(36, 120, 1) - 0.5
    note_freq_div = 440 * 2**((note_freq_div - 57) / 12.0)
    note_freq_div = note_freq_div * scale
    return numpy.int16(note_freq_div)


def get_note_window(fs, resolution, note_freq_div):
    # print fs, note_freq_div
    note_window = numpy.zeros(int(fs * resolution * 0.5 - 1))
    for i in range(len(note_freq_div) - 1):
        a = note_freq_div[i]
        b = note_freq_div[i + 1]
        win = numpy.kaiser(b - a, 5)
        if i == 0:
            note_window[a:b] = win * 0
        else:
            seg = win * numpy.log2(i)
            if len(seg) == len(note_window[a:b]):
                note_window[a:b] = seg
            else:
                note_window[a:b] = seg[:len(note_window[a:b])]
    note_window[:int(140 * resolution)] = 0
    min_freq = 400
    window = numpy.kaiser(int(
        min_freq * resolution * 2), 9)[:int(min_freq * resolution)]
    note_window[:int(min_freq * resolution)]\
        = note_window[:int(min_freq * resolution)] * window
    # pylab.plot(note_window); pylab.show()
    return note_window


def get_chord_binaries():
    return [get_major_chord_binary(i) for i in range(12)]\
        + [get_minor_chord_binary(i) for i in range(12)]


def get_major_chord_binary(root):
    major = (1.00, 0, 0, 0, 0.80, 0, 0, 0.80, 0, 0, 0, 0.20)
    return major[12 - root:] + major[:12 - root]


def get_minor_chord_binary(root):
    minor = (1.00, 0, 0, 0.80, 0, 0, 0, 0.80, 0, 0, 0, 0.20)
    return minor[12 - root:] + minor[:12 - root]


def chord_idx_to_char(idx, chord_type=1):
    return get_chord_type_definition()[chord_type][idx]


def convert_chord_type(chord, type_idx):
    chord_type_definition = get_chord_type_definition()
    for idx, chords in enumerate(chord_type_definition):
        chord_idx = [i for i, v in enumerate(chords) if v == chord]
        if chord_idx != []:
            return chord_type_definition[type_idx][chord_idx[0]]
    return chord


def get_note_type_idx(note):
    note_types = get_note_type_definition()
    return [i for i in range(len(note_types)) if note in note_types[i]]


def note_idx_to_char(idx, note_type=1):
    if idx >= 12:
        idx = idx % 12
    note_types = get_note_type_definition()
    return note_types[note_type][idx]


def note_char_to_idx(note):
    note_types = get_note_type_definition()
    for type_idx in range(len(note_types)):
        for note_idx in range(len(note_types[type_idx])):
            if note_types[type_idx][note_idx] == note:
                return note_idx
    return None


def get_note_type_definition():
    return (
        ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'),
        ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'))


def get_chord_type_definition():
    return (
        ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B',
         'Cm', 'Dbm', 'Dm', 'Ebm', 'Em', 'Fm', 'Gbm', 'Gm', 'Abm', 'Am', 'Bbm', 'Bm'),
        ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B',
         'Cm', 'C#m', 'Dm', 'D#m', 'Em', 'Fm', 'F#m', 'Gm', 'G#m', 'Am', 'A#m', 'Bm'),
        ('8B', '3B', '10B', '5B', '12B', '7B', '2B', '9B', '4B', '11B', '6B', '1B',
         '5A', '12A', '7A', '2A', '9A', '4A', '11A', '6A', '1A', '8A', '3A', '10A'))


def get_chord_binaries_correlation_lag_score(chroma):
    major_binary = get_major_chord_binary(0)
    major_binary = major_binary + major_binary
    con = numpy.convolve(chroma, major_binary[::-1])
    major_value, major_pnt = find_max(con[11:-11])
    major_lag = major_pnt[0]

    minor_binary = get_minor_chord_binary(0)
    minor_binary = minor_binary + minor_binary
    con = numpy.convolve(chroma, minor_binary[::-1])
    minor_value, minor_pnt = find_max(con[11:-11])
    minor_lag = minor_pnt[0]

    if major_value > minor_value:
        return (major_lag, major_value)
    return (minor_lag + 12, minor_value)


# http://www.pyinstaller.org/ticket/182
# http://www.pyinstaller.org/wiki/Recipe/Multiprocessing
# https://github.com/terryh/autotrader/blob/master/quote/quoteworker.py


# class _Popen(multiprocessing.forking.Popen):

#     def __init__(self, *args, **kw):
#         if hasattr(sys, 'frozen'):
#             # We have to set original _MEIPASS2 value from sys._MEIPASS
#             # to get --onefile mode working.
#             # Last character is stripped in C-loader. We have to add
#             # '/' or '\\' at the end.
#             os.putenv('_MEIPASS2', sys._MEIPASS + os.sep)
#         try:
#             super(_Popen, self).__init__(*args, **kw)
#         finally:
#             if hasattr(sys, 'frozen'):
#                 if hasattr(os, 'unsetenv'):
#                     os.unsetenv('_MEIPASS2')
#                 else:
#                     os.putenv('_MEIPASS2', '')


class Process(multiprocessing.Process):
    # _Popen = _Popen

    def __init__(self, path, queue=None):
        self.path = path
        self.result = None
        self.queue = multiprocessing.Queue()
        # multiprocessing.freeze_support()
        multiprocessing.Process.__init__(self)

    def run(self):
        set_process_priority(6)
        mfeats_single(self.path, self.queue)
        self.result = self.queue.get()
        insert_mfeats(self.result)

    def __del__(self):
        pass


class Thread(threading.Thread):

    def __init__(self, path):
        threading.Thread.__init__(self)
        self.path = path
        self.result = None

    def run(self):
        self.result = mfeats_single(self.path)
        insert_mfeats(self.result)

    def __del__(self):
        pass


# Tempo Extractor

# tempo.tempo(filename), tempo.tempo(audict), tempo.tempo(audiodata, audiorate)


def get_tempo(audata, samplerate, tmin=60, tmax=190):
    tempi, magnitude = get_tempi_using_overlap_sum_fft(audata, samplerate)
    tempo = trim_tempo(tempi[0])
    return tempo


def get_tempi_using_overlap_sum_fft(audata, samplerate):
    # tempi extraction using overlap sum fft
    # pre_min_tempo = 60
    # pre_max_tempo = 200
    post_min_tempo = 60
    post_max_tempo = 190
    tempi_candidates = 1
    tempo_resolution = 0.1
    audio_resolution = samplerate  # 200
    peak_min_distance = 5

    # preprocess
    if samplerate != audio_resolution:
        num = int(len(audata) / (samplerate / float(audio_resolution)))
        audata = numpy.abs(numpy.interp(
            numpy.linspace(0, len(audata) - 1, num), numpy.arange(len(audata)), audata))

    # fft and trim fft signal
    mcomplex = 1.0 / (numpy.array([1, 2, 3, 4, 8, 12, 16]) / 4.0)
    min_point = int(post_min_tempo / tempo_resolution)
    max_point = int(post_max_tempo / tempo_resolution)
    fftpoint = int(audio_resolution * 60 / tempo_resolution)
    spectrum = numpy.fft.fft(audata, fftpoint)
    spectrum = numpy.abs(spectrum[1:int(len(spectrum) / 2)])
    overlap_spectrum = [rescale(spectrum[:int(numpy.ceil(max_point / v))], v)[:max_point]
                        for i, v in enumerate(mcomplex)]

    # overlap rescaled fft signals
    overlap_sum_spectrum = numpy.sum(overlap_spectrum, axis=0)
    rmlength = int(numpy.ceil(peak_min_distance / tempo_resolution / 2))
    overlap_sum_spectrum[:min_point] = 0
    overlap_sum_spectrum[max_point + 1:max_point + rmlength] = 0
    tempi, magnitude = ([], [])
    for i in range(tempi_candidates):
        mag, peak_point = find_max(overlap_sum_spectrum)
        tempi += [peak_point[0] * tempo_resolution]
        magnitude += [mag]
        points = range(int(peak_point[0] - rmlength),
                       int(peak_point[0] + rmlength))
        if tempi_candidates == 1:
            break
        if max(points) >= max_point:
            overlap_sum_spectrum[int(peak_point[0] - rmlength):max_point + 1] = 0
        elif min(points) <= min_point:
            overlap_sum_spectrum[min_point:int(peak_point[0] + rmlength) + 1] = 0
        else:
            overlap_sum_spectrum[min(points):max(points) + 1] = 0

    max_magnitude = magnitude[0] / 1.0
    if max_magnitude != 0.0:
        magnitude = [v / max_magnitude for v in magnitude]

    return tempi, magnitude


def find_max(inlist):
    maxvalue = numpy.max(inlist)
    return maxvalue, [i for i, v in enumerate(inlist) if v == maxvalue]


def trim_tempo(tempo, min_tempo=60, max_tempo=190):
    if (tempo < min_tempo) and (tempo < 0.5 * max_tempo):
        return 2.0 * tempo
    elif (tempo > 2.0 * min_tempo) and (tempo > max_tempo):
        return 0.5 * tempo
    return 1.0 * tempo


def gridrescale(insignal, ratio):
    nlength = int(numpy.floor(len(insignal) * ratio))
    pntxb = numpy.arange(0, nlength / ratio, 1.0 / ratio) + (1.0 / ratio) * 0.5
    pntxa = numpy.concatenate(([0], pntxb[:nlength - 1]), axis=0)
    pntxb[-1] = len(insignal)
    pntxa = numpy.int32(numpy.floor(pntxa))
    pntxb = numpy.int32(numpy.ceil(pntxb))
    return [max(insignal[pntxa[i]:pntxb[i]]) for i in range(nlength)]


def rescale(insignal, ratio):
    if ratio <= 1:
        outsignal = gridrescale(insignal, ratio)
    elif ratio > 1:
        for i in range(1, 4096 + 1):
            cond = (ratio * i) % i
            if numpy.floor(cond) == cond:
                mdmult = i
                break
        mdmult = float(mdmult)
        if mdmult == 1:
            outsignal = gridrescale(insignal, ratio)
        elif mdmult > 1:
            outsignal = gridrescale(insignal, ratio * mdmult)
            outsignal = gridrescale(outsignal, 1.0 / mdmult)
    return outsignal


# SQLITE DB Connection


def create_mfeats_table(table_name='mfeats', db_name=None):
    if db_name is None:
        db_name = MFEATS_DB

    if os.path.isfile(db_name):
        return
    fields = ','.join([' '.join(field) for field in MFEATS_DEFINITION])
    query = '''CREATE TABLE %s (%s);''' % (table_name, fields)
    conn = None

    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute(query)
    conn.commit()
    conn.close()
    # try:
    #     conn = sqlite3.connect(db_name)
    #     c = conn.cursor()
    #     c.execute(query)
    #     conn.commit()
    #     conn.close()
    # except:
    #     pass
    # finally:
    #     if conn:
    #         conn.close()


def drop_table(table_name='mfeats', db_name=None):
    if db_name is None:
        db_name = MFEATS_DB
    query = '''DROP TABLE IF EXISTS %s;''' % (table_name)
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute(query)
        conn.commit()
        conn.close()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


def deleteby_key_value(key, value, table_name='mfeats', db_name=None):
    if db_name is None:
        db_name = MFEATS_DB
    query = '''DELETE FROM %s WHERE %s="%s"''' % (table_name, key, value)
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        c = conn.cursor()
        c.execute(query)
        conn.commit()
        conn.close()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


def getby_key_value(key, value, table_name='mfeats', db_name=None):
    if db_name is None:
        db_name = MFEATS_DB
    query = '''SELECT * FROM %s WHERE %s="%s"''' % (table_name, key, value)
    conn = None

    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    resp = c.execute(query)

    if resp is None:
        conn.close()
        return
    fetchs = resp.fetchall()
    if len(fetchs) == 0:
        conn.close()
        return
    field_keys = [field_key for field_key, _ in MFEATS_DEFINITION]

    exec('for %s in fetchs: break' % (','.join(field_keys)))

    blob_field_keys = [field_key for field_key, field_type in MFEATS_DEFINITION if field_type == 'BLOB']
    for field_key in blob_field_keys:
        exec('%s = decompress_object(%s)' % (field_key, field_key))

    conn.close()
    kwrds = ['='.join(v) for v in zip(field_keys, field_keys)]
    mfeats_data = eval('MFEATS(%s)' % (','.join(kwrds)))
    mfeats_data.key = fetchs[0][7]
    return mfeats_data

    # try:
    #     conn = sqlite3.connect(db_name)
    #     c = conn.cursor()
    #     resp = c.execute(query)
    #     if resp is not None:
    #         field_keys = [field_key for field_key, _ in MFEATS_DEFINITION]
    #         exec('for %s in resp.fetchall(): break' % (','.join(field_keys)))
    #         blob_field_keys = [field_key for field_key, field_type in MFEATS_DEFINITION if field_type == 'BLOB']
    #         for field_key in blob_field_keys:
    #             exec('%s = decompress_object(%s)' % (field_key, field_key))
    #     conn.commit()
    #     conn.close()
    #     kwrds = ['='.join(v) for v in zip(field_keys, field_keys)]
    #     mfeats_data = eval('MFEATS(%s)' % (','.join(kwrds)))
    #     print('GET', mfeats_data.mdx, mfeats_data.key, mfeats_data.tempo)
    #     return eval('MFEATS(%s)' % (','.join(kwrds)))
    # except:
    #     pass
    # finally:
    #     if conn:
    #         conn.close()


def update_many_key_values(where, key_values, table_name='mfeats', db_name=None):
    if db_name is None:
        db_name = MFEATS_DB
    key_values = [''.join([key, '="', value, '"']) for key, value in key_values]
    key_values = ','.join(key_values)
    query = '''UPDATE %s SET %s WHERE %s="%s";''' % (table_name, key_values, where[0], where[1])
    conn = None
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute(query)
    conn.commit()
    conn.close()
    # try:
    #     conn = sqlite3.connect(db_name)
    #     c = conn.cursor()
    #     c.execute(query)
    #     conn.commit()
    #     conn.close()
    # except:
    #     pass
    # finally:
    #     if conn:
    #         conn.close()


def insert_mfeats(mfeats_data, table_name='mfeats', db_name=None):
    # tic = time.time()
    if db_name is None:
        db_name = MFEATS_DB
    resp = getby_key_value('mdx', mfeats_data.mdx)
    if resp is not None:
        deleteby_key_value('mdx', mfeats_data.mdx)

    field_keys = [v for v, _ in MFEATS_DEFINITION]
    field_types = [v for _, v in MFEATS_DEFINITION]
    field_values = [getattr(mfeats_data, v) for v in field_keys]
    for i, field_type in enumerate(field_types):
        if field_type == 'BLOB':
            field_values[i] = '"%s"' % (compress_object(field_values[i]))
        else:
            field_values[i] = '"%s"' % (field_values[i])
    values = ','.join(field_values)
    query = '''INSERT INTO %s VALUES (%s);''' % (table_name, values)
    # print('SET', mfeats_data.mdx, mfeats_data.key, mfeats_data.tempo, field_values)
    conn = None
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute(query)
    conn.commit()
    conn.close()

    # try:
    #     conn = sqlite3.connect(db_name)
    #     c = conn.cursor()
    #     c.execute(query)
    #     conn.commit()
    #     conn.close()
    # except:
    #     pass
    # finally:
    #     if conn:
    #         conn.close()
    # print time.time()-tic


class MFEATS_JOB_Scheduler(threading.Thread):

    def __init__(self, parent, master_pid=None, max_memory=0, max_idletime=0):
        threading.Thread.__init__(self)
        self.parent = parent
        self.interval = 0.05
        # termaniting condition
        self.master_pid = master_pid
        self.max_memory = max_memory
        self.max_idletime = max_idletime
        # self.max_idletime = 60.0*10

        self.loop = True
        self.proclist = []
        self.idletime = 0.0
        self.memorytime = 0.0
        self.mastertime = 0.0
        self.nomastertime = 0.0
        # self.Messenger = SocketMessenger(SERVER_ADDRESS)
        self.Messenger = PipeMessenger('macrobox_mfeats')
        self.Messenger.start()
        # print 'MFEATS_JOB_Scheduler Launched'

    def run(self):
        while self.loop:
            if self.master_pid is not None:
                self.check_master()
            self.watch_new_proclist()
            self.watch_dead_proclist()
            if self.max_idletime != 0:
                self.idletime_terminator()
            if self.max_memory != 0:
                self.memorymax_terminator()
            self.resend_failed_messenge()
            self.no_master_terminator()
            time.sleep(self.interval)

    def check_master(self):
        self.mastertime += self.interval
        if self.mastertime < 0.5:
            return
        self.mastertime = 0.0
        self.Messenger.send_message('master_alive', 'macrobox_mfeats')
        # self.Messenger.send_message('master_alive', CLIENT_ADDRESS)
        if self.Messenger.has_failed() is False:
            return
        failed = [v for v in self.Messenger.get_failed() if v == 'master_alive']
        if len(failed) > 3:
            self.terminate()

    def resend_failed_messenge(self):
        if self.Messenger.has_failed():
            self.Messenger.resend_failed()

    def watch_dead_proclist(self):
        if self.proclist == []:
            return
        for i in range(len(self.proclist) - 1, -1, -1):
            if self.proclist[i].proc.is_alive() is False:
                self.proclist[i].proc._Thread__stop()
                this = self.proclist.pop(i)
                self.Messenger.send_message(this.path, 'macrobox_mfeats')
                # self.Messenger.send_message(this.path, CLIENT_ADDRESS)
                # print 'watch_dead_proclist job finished: %s' % (this.path)
                # print 'watch_dead_proclist sending message to client: %s'\
                #   % (this.address)

    def watch_new_proclist(self):
        if self.Messenger.has_message() is False:
            return
        message, address = self.Messenger.pop_message()
        # print message
        if message == 'terminate':
            self.terminate()
        elif message == 'connected':
            self.Messenger.send_message('connected', 'macrobox_mfeats')
            # self.Messenger.send_message('connected', CLIENT_ADDRESS)
        elif message == 'master_alive':
            pass
        elif message not in [v.path for v in self.proclist]:
            self.proclist.append(Struct(
                path=message, proc=Thread(message), address=address))
            self.proclist[-1].daemon = True
            self.proclist[-1].proc.start()
            # print 'watch_new_proclist job started: %s' % (message)

    def idletime_terminator(self):
        if self.proclist == []:
            self.idletime += self.interval
        else:
            self.idletime = 0.0
        if self.idletime < self.max_idletime:
            return
        # print u'[ MAX IDLETIME REACHED : TERMINATING MFEATS ]'
        self.terminate()

    def memorymax_terminator(self):
        self.memorytime += self.interval
        if self.memorytime < 10.0:
            return
        self.memorytime = 0.0
        memory = get_memory_by_pid(os.getpid())
        # limit with max megabyte
        if memory < self.max_memory * 1024 * 1024:
            return
        # print u'[ MAX MEMORY REACHED : TERMINATING MFEATS ]'
        self.terminate()

    def no_master_terminator(self):
        self.nomastertime += self.interval
        if self.nomastertime < 5.0:
            return
        self.nomastertime = 0.0
        if is_process_running_by_pid(self.master_pid):
            return  # no master is alived
        self.terminate()

    def terminate(self):
        self.loop = False
        self.Messenger.send_message('terminating', 'macrobox_mfeats')
        # self.Messenger.send_message('terminating', CLIENT_ADDRESS)
        self.Messenger.terminate()
        self.Messenger._Thread__stop()
        for i in range(len(self.proclist)):
            self.proclist[i].proc.join()
        for i in range(len(self.proclist)):
            self.proclist[i].proc._Thread__stop()
        pybass.BASS_Free()
        kill_self_process()

    def __del__(self):
        self.terminate()


def is_scheduler_running():
    return is_process_running_by_name(PROCESS_NAME)


def boot_scheduler(master_pid, max_memory=0, max_idletime=0):
    cmd = [PROCESS_NAME]
    if PACKAGED is False:
        cmd += [os.path.abspath(os.path.join(get_master_path(), 'mfeats.py'))]
    cmd += ['%d' % (master_pid)]
    cmd += ['%.f' % (max_memory)]
    cmd += ['%.f' % (max_idletime)]
    run_hidden_subprocess(cmd)


def boot(master_pid, max_memory=0, max_idletime=0):
    set_process_priority(6)
    scheduler = MFEATS_JOB_Scheduler(None)
    scheduler.master_pid = master_pid
    scheduler.max_memory = max_memory
    scheduler.max_idletime = max_idletime
    scheduler.start()
    scheduler.join()


if __name__ == '__main__':
    master_pid = None
    max_memory = 0
    max_idletime = 0
    if len(sys.argv) >= 2:
        master_pid = int(sys.argv[1])
    if len(sys.argv) >= 3:
        max_memory = float(sys.argv[2])
    if len(sys.argv) >= 4:
        max_idletime = float(sys.argv[3])
    boot(master_pid, max_memory, max_idletime)
