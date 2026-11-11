# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import ctypes
import hashlib
import multiprocessing
import mutagen
import numpy
import os
import pybass
import sqlite3
import sys
import threading
import time

from audio import fir_filter
from audio import get_channel
from audio import init_bass_decode
from copy import deepcopy
from multiprocessing.connection import Client
from multiprocessing.connection import Listener
from queue import Empty
from queue import Queue
from macroboxlib import PREFERENCE_DB
from utilities import PipeMessenger
from utilities import Struct
from utilities import compress_object
from utilities import decompress_object  # noqa
from utilities import get_master_path
from utilities import get_memory_by_pid
from utilities import get_user_docapp_path
from utilities import is_process_running_by_name
from utilities import is_process_running_by_pid
from utilities import kill_self_process
from utilities import makemdx
from utilities import open_shelves
from utilities import run_hidden_subprocess
from utilities import set_process_priority


MFEATS_DB = os.path.join(get_user_docapp_path(), 'database.db')


MFEATS_VERSION = '1.5.1'
# 3band waveform: column seconds, band edges (Hz)
WAVEFORM_COLUMN_SECONDS = 0.01
# bands read over blocks this long (a column is too short)
WAVEFORM_BAND_SECONDS = 0.023
WAVEFORM_LOW_TOP = 200
WAVEFORM_HIGH_BOTTOM = 1500
WAVEFORM_HIGH_TOP = 5512.5
# CLIENT_ADDRESS = ('localhost', 12501)
# SERVER_ADDRESS = ('localhost', 12502)
CLIENT_ADDRESS = ('127.0.0.1', 12702)
SERVER_ADDRESS = ('127.0.0.1', 12703)

# WORKING_PATH = os.path.abspath(os.path.dirname(__file__))
# try:
#     packages = os.path.join(sys._MEIPASS, 'packages')
# except Exception:
#     packages = os.path.join(WORKING_PATH, 'packages')
# sys.path.insert(0, packages)

PACKAGED = hasattr(sys, '_MEIPASS')
# PACKAGED = False
# for v in ('27', '35', '36', '37', '38'):
#     if os.path.isfile('python%s.dll' % (v)):
#         PACKAGED = True
#         break

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
            exec(f'''self.{field_key} = {initial_value}''')
        self.__dict__.update(kwards)


# https://gist.github.com/endolith/255291
# http://wiki.hydrogenaudio.org/index.php?title=ReplayGain_1.0_specification
# https://gist.github.com/255291/c97d2b088c53104f1d0d7cf8b20e89fc788037df


def mfeats_single(path, queue=None, on_wave=None):
    # on_wave: called with the waveform early, before tempo octave and key
    # uses mono data

    # tic = time.time()
    find_key = True
    find_gain = False
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
    # empty file or unreadable length
    if hlength <= 0 or hlength == 0xFFFFFFFFFFFFFFFF or duration <= 0:
        error = 1

    if error == 1:
        if hstream != 0:
            pybass.BASS_StreamFree(hstream)
        mfeats_data = MFEATS(mdx=mdx, path=path, date=time.time(), version=version, error=1)
        if queue is not None:
            queue.put(mfeats_data)
            return
        else:
            return mfeats_data

    if total_frame_length / 2 < waveform_length:
        waveform_length = total_frame_length / 2
    frame_length = int(1.0 * total_frame_length / waveform_length) * 2
    # if int(frame_length) % 8 != 0:
    #     frame_length += (8 - int(frame_length) % 8)
    # whole samples of every channel
    frame_unit = int(numpy.lcm(8, channel))
    if int(frame_length) % frame_unit != 0:
        frame_length += (frame_unit - int(frame_length) % frame_unit)
    gap = total_frame_length / frame_length - waveform_length
    highlight_raw_points = numpy.linspace(0, 0, int(round(waveform_length + gap)))
    frame_raw = numpy.arange(frame_length, dtype=ctypes.c_short)
    # jump = 1.0 * frame_length / waveform_oversampling
    mix_length = int(frame_length / channel)
    # waveform columns of about WAVEFORM_COLUMN_SECONDS each
    sub_count = max(int(round(1.0 * mix_length / fs / WAVEFORM_COLUMN_SECONDS)), 1)
    sub_length = int(mix_length / sub_count)
    # waveform = numpy.linspace(0, 0, int(round(waveform_length + gap)))
    waveform = numpy.zeros((int(round(waveform_length + gap)) * sub_count, 5))
    # mix_window = numpy.hanning(mix_length)
    # mix_freqs = numpy.fft.rfftfreq(mix_length, 1.0 / fs)
    # bands block by block, each column from the block its middle falls in
    band_length = int(fs * WAVEFORM_BAND_SECONDS)
    if mix_length < band_length * 2:
        band_length = mix_length
    band_count = max(int(mix_length / band_length), 1)
    band_of_sub = numpy.minimum(
        ((numpy.arange(sub_count) + 0.5) * sub_length / band_length).astype(int), band_count - 1)
    mix_window = numpy.hanning(band_length)
    mix_freqs = numpy.fft.rfftfreq(band_length, 1.0 / fs)
    mix_bands = (mix_freqs < WAVEFORM_LOW_TOP,
                 (mix_freqs >= WAVEFORM_LOW_TOP) & (mix_freqs < WAVEFORM_HIGH_BOTTOM),
                 (mix_freqs >= WAVEFORM_HIGH_BOTTOM) & (mix_freqs < WAVEFORM_HIGH_TOP))

    analyze_frame, tempo_frame, tempo_fs = ([], [], 200)
    # key on its own thread, fed this pass's frames in bunches
    # (its FFTs release the GIL)
    key_frames, key_bunches, key_found = ([], Queue(), [])

    def read_key():
        # first frame centred at 0, as Essentia's FrameCutter
        key_length = get_key_frame_length(fs)
        key_hpcp, rest = (numpy.zeros(12), numpy.zeros(int((key_length + 1) / 2)))
        while True:
            # give up if this pass is gone
            try:
                last, frames = key_bunches.get(timeout=KEY_BUNCH_WAIT)
            except Empty:
                return
            rest = add_key_frames(
                key_hpcp, numpy.concatenate([rest] + frames), key_length, fs, last=last)
            if last:
                break
        key_found.append(get_key_from_hpcp(key_hpcp))

    key_thread = threading.Thread(target=read_key, daemon=True)
    if find_key:
        key_thread.start()

    for cnt, frame_position in enumerate(
            numpy.arange(0, total_frame_length - frame_length, frame_length)):
        pybass.BASS_ChannelGetData(
            hstream, frame_raw.ctypes.data_as(
                ctypes.POINTER(ctypes.c_short)), int(frame_length * 2))

        mono_frame = deepcopy(frame_raw[::channel])
        analyze_frame += [mono_frame]
        # if jump < waveform_oversampling:
        #     waveform[cnt] = numpy.max(numpy.abs(mono_frame))
        # else:
        #     points = [numpy.max(numpy.abs(mono_frame[int(i):int(i + jump)]))
        #               for i in numpy.arange(0, frame_length / channel - jump, jump)]
        #     waveform[cnt] = numpy.mean(points)
        mix = frame_raw[:mix_length * channel].reshape(-1, channel).mean(axis=1) / 32768.0
        # power = numpy.abs(numpy.fft.rfft(mix * mix_window))**2
        blocks = mix[:band_length * band_count].reshape(band_count, band_length)
        power = numpy.abs(numpy.fft.rfft(blocks * mix_window, axis=1))**2
        bands = numpy.column_stack([power[:, v].sum(axis=1) for v in mix_bands])
        subs = numpy.abs(mix[:sub_length * sub_count]).reshape(sub_count, sub_length)
        row = cnt * sub_count
        waveform[row:row + sub_count, 0] = subs.max(axis=1)
        waveform[row:row + sub_count, 1] = subs.mean(axis=1)
        # waveform[row:row + sub_count, 2:] = [power[v].sum() for v in mix_bands]
        waveform[row:row + sub_count, 2:] = bands[band_of_sub]
        highlight_raw_points[cnt] = numpy.mean(numpy.abs(mono_frame))
        if find_key:
            key_frames += [mix]

        # collect frames for long term analysis

        alength = len(analyze_frame) * len(analyze_frame[-1])
        if alength >= fs * 30 or alength * channel >= total_frame_length - frame_length:
            analyze_frame = numpy.concatenate(analyze_frame, axis=0)

            num = int(len(analyze_frame) / (1.0 * fs / tempo_fs))
            tempo_frame += [
                numpy.abs(numpy.interp(
                    numpy.linspace(0, len(analyze_frame) - 1, num),
                    numpy.arange(len(analyze_frame)), analyze_frame))]

            if find_key:
                key_bunches.put((False, key_frames))
                key_frames = []

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

    if find_key:
        key_bunches.put((True, key_frames))

    # waveform

    # waveform = numpy.int8(waveform / (2**8))
    # peak and level square-rooted, then each band's share
    shares = numpy.sqrt(waveform[:, 2:])
    shares = shares / numpy.maximum(shares.sum(axis=1, keepdims=True), 1e-12)
    waveform = numpy.uint8(numpy.round(255 * numpy.column_stack([
        numpy.sqrt(numpy.clip(waveform[:, :2], 0, 1)), shares])))

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

    # waveform out early, before DeepRhythm and the key
    if on_wave is not None:
        # tempo before its octave (highlight length only)
        on_wave(MFEATS(
            mdx=mdx, path=path, duration=duration, highlight=highlight, waveform=waveform,
            tempo=tempo, date=time.time(), version=version, channel=channel, bit=bit,
            error=0, autogain=0.4))

    # octave from DeepRhythm over the highlight, value from the spectrum
    seconds = max(until_duration, DEEPRHYTHM_CLIP)
    offset = max(min(highlight[0], duration - seconds), 0)
    tempo = fix_tempo_octave(tempo, read_mono(hstream, fs, channel, offset, seconds), fs)

    # autogain analysis in highlight period

    autogain = 0.4
    if find_gain:
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
                mono_frame += fir_filter(mono_frame, lowcut=15000,
                                         highcut=fs / 2, fs=fs, order=5) * 0.5
            rms = numpy.mean(mono_frame**2)**0.5 * 3

            # spectrum = numpy.fft.fft(mono_frame, fs)
            # spectrum = numpy.abs(spectrum[1:int(len(spectrum)/2)])
            # pylab.plot(spectrum); pylab.show()

            autogain = 0.14 / rms

    # key analysis over the whole song with the HPCP of the first pass

    key = ''
    if find_key:
        key_thread.join()
        if key_found and key_found[0] is not None:
            key = chord_idx_to_char(key_found[0])

    # key analysis in highlight period: the most frequent chord

    # key = ''
    # if find_key:
    #     chromagram, resolution = ([], 1.0)
    #     note_freq_div = get_note_freq_div(resolution)
    #     # note_window = get_note_window(fs, resolution, note_freq_div)
    #     if xtempo == 0:
    #         frame_length = int(fs * channel * 0.5)
    #     else:
    #         frame_length = int(fs * channel * (60.0 / xtempo))
    #     frame_length -= frame_length % channel

    #     offset_position, until_position = (highlight[0], fs * channel * until_duration * 2)

    #     if frame_length > total_frame_length:
    #         frame_length = total_frame_length - 1

    #     if offset_position + until_position > total_frame_length:
    #         until_position = total_frame_length - offset_position

    #     frame_raw = numpy.arange(frame_length, dtype=ctypes.c_short)
    #     byte_position = pybass.BASS_ChannelSeconds2Bytes(hstream, offset_position)
    #     pybass.BASS_ChannelSetPosition(hstream, byte_position, False)

    #     for cnt, frame_position in enumerate(
    #             numpy.arange(0, total_frame_length - frame_length, frame_length)):

    #         got = pybass.BASS_ChannelGetData(
    #             hstream, frame_raw.ctypes.data_as(
    #                 ctypes.POINTER(ctypes.c_short)), int(frame_length * 2))
    #         # past the file's end (-1): the last frame read was counted already
    #         if got <= 0 or got == 0xFFFFFFFF:
    #             break

    #         mono_frame = frame_raw[::channel] / 32768.0
    #         spectrum = numpy.fft.fft(mono_frame, int(fs * resolution))
    #         spectrum = numpy.abs(spectrum[1:int(len(spectrum) / 2)])

    #         if find_key:

    #             notes = spectrum_to_note_by_max(spectrum, note_freq_div)
    #             chromagram += [note_to_chroma_by_max(notes)]

    #         if (cnt + 1) * frame_length >= until_position:
    #             break

    #     scored_keys, key_scores, key_counts = ([], [0] * 24, [0] * 24)
    #     for chroma in chromagram:
    #         lag, score = get_chord_binaries_correlation_lag_score(chroma)
    #         scored_keys += [lag]
    #         key_counts[lag] += 1
    #         key_scores[lag] += score
    #     key_scores = numpy.array(key_scores)
    #     max_key_scores = max(key_scores)
    #     if max_key_scores == 0.0:
    #         key = ''
    #     else:
    #         key_scores = key_scores / max_key_scores * 100
    #         scored_key_idx = []
    #         for i in range(1):
    #             value, pnt = find_max(key_scores)
    #             if value < 50:
    #                 break
    #             scored_key_idx += [pnt[0]]
    #             key_scores[pnt[0]] = 0
    #         string_keys = []
    #         for i in range(len(scored_key_idx) - 1, -1, -1):
    #             if scored_key_idx[i] - 12 in scored_key_idx:
    #                 scored_key_idx.pop(i)
    #                 continue
    #             elif scored_key_idx[i] + 12 in scored_key_idx:
    #                 scored_key_idx.pop(i)
    #                 continue
    #             string_keys += [chord_idx_to_char(scored_key_idx[i])]
    #         string_keys = ' or '.join(string_keys)
    #         key = '%s' % (string_keys)

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
        try:
            mutagen_mp3 = mutagen.mp3.MP3(path)
            mutagen_mp3['TKEY'] = mutagen.id3.TKEY(encoding=3, text=[key])
            mutagen_mp3['TBPM'] = mutagen.id3.TBPM(encoding=3, text=[tempo])
            mutagen_mp3.save()
        except Exception:
            pass

    mfeats_data = MFEATS(
        mdx=mdx, path=path, key=key, tempo=tempo,
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


def get_live_waveform_columns(mono, fs):
    '''live waveform columns as mfeats_single makes them'''
    size = max(int(fs * WAVEFORM_COLUMN_SECONDS), 1)
    count = len(mono) // size
    if count == 0:
        return numpy.zeros((0, 5), dtype=numpy.uint8)
    subs = numpy.abs(mono[:count * size]).reshape(count, size)
    band_length = max(int(fs * WAVEFORM_BAND_SECONDS), 2)
    block = numpy.zeros(band_length)
    tail = mono[-band_length:]
    block[band_length - len(tail):] = tail
    power = numpy.abs(numpy.fft.rfft(block * numpy.hanning(band_length))) ** 2
    freqs = numpy.fft.rfftfreq(band_length, 1.0 / fs)
    bands = numpy.array([power[v].sum() for v in (
        freqs < WAVEFORM_LOW_TOP,
        (freqs >= WAVEFORM_LOW_TOP) & (freqs < WAVEFORM_HIGH_BOTTOM),
        (freqs >= WAVEFORM_HIGH_BOTTOM) & (freqs < WAVEFORM_HIGH_TOP))])
    shares = numpy.sqrt(bands)
    shares = shares / max(shares.sum(), 1e-12)
    columns = numpy.column_stack([
        numpy.sqrt(numpy.clip(subs.max(axis=1), 0, 1)),
        numpy.sqrt(numpy.clip(subs.mean(axis=1), 0, 1)), numpy.tile(shares, (count, 1))])
    return numpy.uint8(numpy.round(255 * columns))


def note_to_chroma_by_sum(notes):
    return [sum(notes[i::12]) for i in range(12)]


def note_to_chroma_by_max(notes):
    return [max(notes[i::12]) for i in range(12)]


def spectrum_to_note_by_max(spectrum, note_freq_div):
    notes = numpy.zeros(len(note_freq_div))
    for i in range(len(note_freq_div) - 1):
        elem = spectrum[note_freq_div[i]:note_freq_div[i + 1]]
        # if elem != []:
        if len(elem):
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


def transpose_chord(chord, semitones):
    # key moved by semitones, in the same notation
    for names in get_chord_type_definition():
        if chord in names:
            idx = names.index(chord)
            return names[(idx % 12 + semitones) % 12 + idx // 12 * 12]
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


# Essentia's KeyExtractor (bgate profile) in numpy: whitened spectral
# peaks of 25 to 3500 Hz into a 12-bin HPCP over the whole song

KEY_FS = 44100
KEY_FRAME = 4096
KEY_MIN_FREQUENCY = 25.0
KEY_MAX_FREQUENCY = 3500.0
KEY_MAX_PEAKS = 60
KEY_PEAK_THRESHOLD = 0.0001
KEY_PCP_THRESHOLD = 0.2
# added to the minor correlations: the library is mostly minor
KEY_MINOR_BIAS = 0.05
# major and minor from A (Faraldo, Jorda and Herrera, AES 2017)
KEY_PROFILES = (
    (1.00, 0.00, 0.42, 0.00, 0.53, 0.37, 0.00, 0.77, 0.00, 0.38, 0.21, 0.30),
    (1.00, 0.00, 0.36, 0.39, 0.00, 0.38, 0.00, 0.74, 0.27, 0.00, 0.42, 0.23))


def get_key_frame_length(fs):
    return int(round(1.0 * KEY_FRAME * fs / KEY_FS))


def get_key_harmonics():
    '''(semitone, weight) of a peak as the 1st to 5th harmonic'''
    harmonics = []
    for i in range(5):
        semitone = 12.0 * numpy.log2(i + 1.0)
        weight = 1.0 / max(1.0, semitone / 12.0 * 0.5)
        while semitone >= 12.0 - 0.00001:
            semitone -= 12.0
        for v in harmonics:
            if abs(v[0] - semitone) < 0.00001:
                v[1] += weight
                break
        else:
            harmonics += [[semitone, weight]]
    return harmonics


def get_key_hpcp(frames, fs):
    '''summed HPCP of the frames, from A'''
    size = frames.shape[1]
    window = numpy.hanning(size)
    window = window * 2.0 / window.sum()
    spectrum = numpy.abs(numpy.fft.rfft(frames * window, axis=1))
    bins = spectrum.shape[1]
    scale = fs / 2.0 / (bins - 1)

    first = max(0, int(numpy.ceil(KEY_MIN_FREQUENCY / scale)))
    last = int(KEY_MAX_FREQUENCY / scale) + 2
    left = spectrum[:, first:last - 1]
    middle = spectrum[:, first + 1:last]
    right = spectrum[:, first + 2:last + 1]
    peak = (left < middle) & (middle > right) & (middle > KEY_PEAK_THRESHOLD)
    with numpy.errstate(divide='ignore', invalid='ignore'):
        delta = 0.5 * (left - right) / (left - 2 * middle + right)
    delta = numpy.where(peak, delta, 0.0)
    magnitude = middle - 0.25 * (left - right) * delta
    frequency = (numpy.arange(first + 1, last) + delta) * scale
    edge = spectrum[:, first]
    peak = numpy.column_stack((
        (edge > spectrum[:, first + 1]) & (edge > KEY_PEAK_THRESHOLD), peak))
    magnitude = numpy.column_stack((edge, magnitude))
    frequency = numpy.column_stack((numpy.full(len(frames), first * scale), frequency))
    peak &= frequency <= KEY_MAX_FREQUENCY
    order = numpy.argsort(numpy.where(peak, -magnitude, numpy.inf), axis=1, kind='stable')
    order = order[:, :KEY_MAX_PEAKS]
    peak = numpy.take_along_axis(peak, order, axis=1)
    magnitude = numpy.take_along_axis(magnitude, order, axis=1)
    frequency = numpy.take_along_axis(frequency, order, axis=1)

    # whitening: peak level against the spectral envelope
    points = numpy.arange(0.0, KEY_MAX_FREQUENCY * 1.2 + 1, 100.0)
    points = points[points <= fs / 2.0]
    shape = numpy.zeros((len(points), bins))
    for i, v in enumerate(points):
        b = int((v - max(50.0, v * 0.34)) / (fs / 2.0) * (bins - 1.0) + 0.5)
        e = int((v + max(50.0, v * 0.58)) / (fs / 2.0) * (bins - 1.0) + 0.5)
        b = min(max(b, 0), bins - 1)
        e = min(max(e, b + 1), bins)
        c = b / 2.0 + e / 2.0
        shape[i, b:e] = (1.0 - numpy.abs(numpy.arange(b, e) - c) / (e - c))**4
    energy = spectrum**2
    total = energy.dot(shape.T)
    with numpy.errstate(divide='ignore', invalid='ignore'):
        envelope = numpy.where(total > 0, (energy**2).dot(shape.T) / total, 0.0)
    envelope[:, -1] = envelope[:, -2]
    envelope = numpy.sqrt(envelope)
    envelope = numpy.where(
        envelope < 1e-10, -200.0, 20 * numpy.log10(numpy.maximum(envelope, 1e-300)))
    level = numpy.where(
        magnitude < 1e-10, -200.0, 20 * numpy.log10(numpy.maximum(magnitude, 1e-300)))
    step = numpy.clip(numpy.floor(frequency / 100.0).astype(int), 0, len(points) - 2)
    floor = numpy.take_along_axis(envelope, step, axis=1)
    floor += (frequency / 100.0 - step) * (
        numpy.take_along_axis(envelope, step + 1, axis=1) - floor)
    white = numpy.where(level > floor, 0.0,
                        numpy.where(level > floor - 30.0, level - floor, -200.0))
    white = 10**((white - 20.0 * frequency / 4000.0) / 20.0)

    hpcp = numpy.zeros(12)
    for semitone, weight in get_key_harmonics():
        note = 12 * numpy.log2(frequency * 2**(-semitone / 12.0) / 440.0)
        nearest = numpy.floor(note + 0.5)
        hpcp += numpy.bincount(
            (nearest[peak] % 12).astype(int), minlength=12,
            weights=(numpy.cos(numpy.pi * (note - nearest)) * white**2 * weight**2)[peak])
    return hpcp


def add_key_frames(hpcp, mix, length, fs, last=False):
    '''add whole frames of mix to hpcp, return the rest'''
    if last and len(mix) % length != 0:
        mix = numpy.concatenate((mix, numpy.zeros(length - len(mix) % length)))
    count = int(len(mix) / length)
    if count > 0:
        hpcp += get_key_hpcp(mix[:count * length].reshape(count, length), fs)
    return mix[count * length:]


def get_key_from_hpcp(hpcp):
    '''chord index of the best correlated profile, or None'''
    if numpy.max(hpcp) <= 0:
        return None
    pcp = numpy.array(hpcp) / numpy.max(hpcp)
    pcp[pcp < KEY_PCP_THRESHOLD] = 0
    pcp = pcp - pcp.mean()
    pcp = pcp / (numpy.sqrt(numpy.sum(pcp**2)) or 1.0)
    best = []
    for bias, profile in zip((0.0, KEY_MINOR_BIAS), KEY_PROFILES):
        profile = numpy.array(profile) - numpy.mean(profile)
        profile = profile / numpy.sqrt(numpy.sum(profile**2))
        scores = [numpy.sum(pcp * numpy.roll(profile, v)) + bias for v in range(12)]
        best += [(max(scores), int(numpy.argmax(scores)))]
    if best[0][0] > best[1][0]:
        return (best[0][1] + 9) % 12
    return (best[1][1] + 9) % 12 + 12


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
        # mfeats_single(self.path, self.queue)
        # self.result = self.queue.get()
        # keep a failed analysis as an error, or it retries on every start
        try:
            self.result = mfeats_single(self.path)
        except Exception:
            self.result = MFEATS(mdx=makemdx(self.path), path=self.path,
                                 date=time.time(), version=MFEATS_VERSION, error=1)
        insert_mfeats(self.result)

    def __del__(self):
        pass


# key thread's wait for the next frames
KEY_BUNCH_WAIT = 120


def mfeats_worker(conn, model_address=None):
    # model_address: deeprhythm_server's (none: the model here)
    # here, not in macroboxlib: a circular import killed spawned workers
    set_process_priority(6)
    DEEPRHYTHM.address = model_address
    # DeepRhythm loads with the first song, after its waveform
    while True:
        try:
            path = conn.recv()
        except (EOFError, OSError):
            # app gone (pipe closed)
            return
        if path is None:
            return
        # ('grid', path): only the grid is missing; ('again', path): analyzed again as asked
        kind = 'whole'
        if isinstance(path, tuple):
            kind, path = path
        if kind == 'grid':
            resp = getby_key_value('mdx', makemdx(path), waveform=False)
            if resp is not None and resp.error == 0:
                analyze_grid_into_db(path, resp.tempo, resp.highlight)
            try:
                conn.send(path)
            except (EOFError, OSError):
                return
            continue
        # unreadable here: mfeats_single keeps it as an error
        try:
            sound = keep_sound(path)
        except (OSError, sqlite3.Error):
            sound = None
        if kind == 'whole' and sound is not None and copy_analysis(path, *sound):
            try:
                conn.send(('copied', path))
            except (EOFError, OSError):
                return
            continue
        # keep a failed analysis as an error, or it retries on every start
        try:
            result = mfeats_single(path, on_wave=insert_mfeats_wave)
        except Exception:
            result = MFEATS(mdx=makemdx(path), path=path, date=time.time(),
                            version=MFEATS_VERSION, error=1)
        insert_mfeats(result)
        delete_mfeats_wave(result.mdx)
        if result.error == 0:
            analyze_grid_into_db(path, result.tempo, result.highlight)
        try:
            conn.send(path)
        except (EOFError, OSError):
            return


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


# the spectrum tends to pick a slow song's double; DeepRhythm gets the
# octave but only whole BPMs

DEEPRHYTHM_FS = 22050
DEEPRHYTHM_CLIP = 8
DEEPRHYTHM = Struct(predictor=None, failed=False, lock=threading.Lock(),
                    address=None, client=None, unreachable=0)
# DeepRhythm in one process for all workers (deeprhythm_server);
# without a server the spectrum tempo is kept
DEEPRHYTHM_CONNECT_WAIT = 20
# most clips through the model at once
DEEPRHYTHM_BATCH = 16
DEEPRHYTHM_ANSWER_WAIT = 30
# retry after this long when not reached
DEEPRHYTHM_RETRY = 60


def get_deeprhythm_address(pid):
    return rf'\\.\pipe\PyMusicPlayer-deeprhythm-{int(pid)}'


def deeprhythm_server(control, address, threads=None):
    '''DeepRhythm BPMs for the workers at address, until control ends'''
    set_process_priority(6)
    if threads is not None:
        import torch
        torch.set_num_threads(threads)
    listener = Listener(address)
    requests = Queue()
    # load at once
    threading.Thread(target=get_deeprhythm, daemon=True).start()

    def serve(client):
        while True:
            try:
                request = client.recv()
            except (EOFError, OSError):
                break
            # Beat This! for the grid, a clip at a time
            if len(request) == 3 and request[0] == 'beats':
                try:
                    answer = predict_beatthis_here(request[1], request[2])
                except Exception:
                    answer = None
                try:
                    client.send(answer)
                except (EOFError, OSError):
                    break
                continue
            audio, fs = request
            asked = Struct(audio=audio, fs=fs, bpm=None, done=threading.Event())
            requests.put(asked)
            asked.done.wait()
            try:
                client.send(asked.bpm)
            except (EOFError, OSError):
                break
        client.close()

    def predict():
        # batch the clips asked for meanwhile
        while True:
            batch = [requests.get()]
            while len(batch) < DEEPRHYTHM_BATCH:
                try:
                    batch.append(requests.get_nowait())
                except Empty:
                    break
            predict_deeprhythm_batch(batch)
            for asked in batch:
                asked.done.set()

    def accept():
        while True:
            try:
                client = listener.accept()
            except multiprocessing.AuthenticationError:
                continue
            except (EOFError, OSError):
                return
            threading.Thread(target=serve, args=(client,), daemon=True).start()

    threading.Thread(target=predict, daemon=True).start()
    threading.Thread(target=accept, daemon=True).start()
    # told to end (None), or the app gone
    try:
        control.recv()
    except (EOFError, OSError):
        pass


def predict_deeprhythm_batch(batch):
    '''each request's bpm (None if none), all clips in one batch'''
    predictor = get_deeprhythm()
    if predictor is None:
        return
    import torch
    from deeprhythm.audio_proc.hcqm import compute_hcqm
    from deeprhythm.utils import class_to_bpm
    from deeprhythm.utils import split_audio
    try:
        clips = [split_audio(asked.audio, asked.fs) for asked in batch]
        counts = [len(v) for v in clips]
        with torch.no_grad():
            inputs = compute_hcqm(torch.cat(clips).to(device=predictor.device),
                                  *predictor.specs).permute(0, 3, 1, 2)
            probabilities = torch.softmax(predictor.model(inputs), dim=1)
        for asked, part in zip(batch, torch.split(probabilities, counts)):
            asked.bpm = float(class_to_bpm(torch.max(part.mean(dim=0), 0)[1].item()))
    except Exception:
        # batch failed: each on its own
        for asked in batch:
            try:
                asked.bpm = float(predictor.predict_from_audio(asked.audio, asked.fs))
            except Exception:
                asked.bpm = None


def predict_deeprhythm(audio):
    '''DeepRhythm BPM of the clip, from the server if any; or None'''
    if DEEPRHYTHM.address is None:
        predictor = get_deeprhythm()
        if predictor is None:
            return None
        with DEEPRHYTHM.lock:
            return float(predictor.predict_from_audio(audio, DEEPRHYTHM_FS))
    return ask_model((audio, DEEPRHYTHM_FS))


def ask_model(request):
    '''deeprhythm_server's answer to request, or None'''
    if time.time() < DEEPRHYTHM.unreachable:
        return None
    try:
        if DEEPRHYTHM.client is None:
            # a server just started is not listening yet
            until = time.time() + DEEPRHYTHM_CONNECT_WAIT
            while DEEPRHYTHM.client is None:
                try:
                    DEEPRHYTHM.client = Client(DEEPRHYTHM.address)
                except (FileNotFoundError, ConnectionError, OSError):
                    if time.time() > until:
                        # not waited for again by this worker
                        DEEPRHYTHM.unreachable = time.time() + DEEPRHYTHM_RETRY
                        return None
                    time.sleep(0.2)
        DEEPRHYTHM.client.send(request)
        if DEEPRHYTHM.client.poll(DEEPRHYTHM_ANSWER_WAIT) is False:
            raise TimeoutError
        return DEEPRHYTHM.client.recv()
    except Exception:
        # gone or stuck: keep the spectrum tempo, reconnect next song
        try:
            DEEPRHYTHM.client.close()
        except Exception:
            pass
        DEEPRHYTHM.client = None
        return None


def get_deeprhythm():
    '''once a process; None without the package'''
    with DEEPRHYTHM.lock:
        if DEEPRHYTHM.predictor is None and DEEPRHYTHM.failed is False:
            try:
                from deeprhythm.model.predictor import DeepRhythmPredictor
                DEEPRHYTHM.predictor = DeepRhythmPredictor(quiet=True)
            except Exception:
                DEEPRHYTHM.failed = True
        return DEEPRHYTHM.predictor


def read_mono(hstream, fs, channel, offset, seconds):
    length = int(fs * seconds) * channel
    frame_raw = numpy.zeros(length, dtype=ctypes.c_short)
    byte_position = pybass.BASS_ChannelSeconds2Bytes(hstream, offset)
    pybass.BASS_ChannelSetPosition(hstream, byte_position, False)
    got = pybass.BASS_ChannelGetData(
        hstream, frame_raw.ctypes.data_as(ctypes.POINTER(ctypes.c_short)), length * 2)
    if got <= 0 or got == 0xFFFFFFFF:
        return numpy.zeros(0)
    frame_raw = frame_raw[:got // 2 // channel * channel]
    return frame_raw.reshape(-1, channel).mean(axis=1) / 32768.0


def fix_tempo_octave(tempo, mono, fs):
    '''spectrum tempo halved or doubled to DeepRhythm's within 3%'''
    if tempo == 0 or len(mono) < fs * DEEPRHYTHM_CLIP:
        return tempo
    from scipy.signal import resample_poly
    gcd = int(numpy.gcd(DEEPRHYTHM_FS, fs))
    audio = resample_poly(mono, DEEPRHYTHM_FS // gcd, fs // gcd).astype(numpy.float32)
    try:
        bpm = predict_deeprhythm(audio)
    except Exception:
        return tempo
    if bpm is None:
        return tempo
    for ratio in (0.5, 1.0, 2.0):
        if abs(tempo * ratio / bpm - 1) <= 0.03:
            return tempo * ratio
    return bpm


# Beat Grid: tempo and phase from the high band's attacks folded on the
# beat; quarter beat and bar from Beat This! over the highlight

GRID_VERSION = '1.2.0'
GRID_TABLE = 'mfeats_grid'
GRID_FS = 11025
GRID_HOP = 11
GRID_SEARCH = ((0.3, 0.01), (0.012, 0.0005))
GRID_BINS = 240
BEATTHIS_FS = 22050
BEATTHIS_SECONDS = 60
# quarter-beat move taken only when Beat This!'s beats are this close
BEATTHIS_NEAR = 0.030
BEATTHIS_FAR = 0.060
BEATTHIS = Struct(predictor=None, failed=False, lock=threading.Lock())
# phrase (4 bars): the bar after which the sound changes most
PHRASE_WINDOW = 4
PHRASE_BANDS = numpy.geomspace(40, 5000, 13)
# Beat This!'s bar given up for the one the changes fall on
BAR_OVERRIDE = 3.0
# draw a phrase only when its score leads the next by this share
PHRASE_SURE = 0.2
# drop start (refine_highlight_start) and calm bar (choose_long_highlight)
HIGHLIGHT_LOW_RISE = 1.0
HIGHLIGHT_CALM = 0.5
# radio edit (choose_radio_edit): main part level, fullness and
# breakdown thresholds
EDIT_MAIN = 0.85
EDIT_FULL = 0.75
# mids alone too, or a DJ intro's guide beat reads as the main part
EDIT_MIDS = 0.6
EDIT_BREAK_HEAD = 1
EDIT_BREAK_TAIL = 2


def read_mono_all(path, fs_out):
    # whole song as mono at fs_out, read in pieces
    from scipy.signal import resample_poly
    init_bass_decode()
    channel = get_channel(path)
    hstream = pybass.BASS_StreamCreateFile(
        False, path, 0, 0, pybass.BASS_STREAM_DECODE |
        pybass.BASS_STREAM_PRESCAN | pybass.BASS_UNICODE)
    if hstream == 0:
        return None
    fs = ctypes.c_float()
    pybass.BASS_ChannelGetAttribute(hstream, pybass.BASS_ATTRIB_FREQ, ctypes.byref(fs))
    fs = int(fs.value)
    gcd = int(numpy.gcd(fs_out, fs))
    pieces = []
    piece = numpy.zeros(fs * 30 * channel, dtype=ctypes.c_short)
    while True:
        got = pybass.BASS_ChannelGetData(
            hstream, piece.ctypes.data_as(ctypes.POINTER(ctypes.c_short)), len(piece) * 2)
        if got <= 0 or got == 0xFFFFFFFF:
            break
        frames = piece[:got // 2 // channel * channel].reshape(-1, channel)
        pieces.append(frames.mean(axis=1).astype(numpy.float32) / 32768.0)
    pybass.BASS_StreamFree(hstream)
    if pieces == []:
        return None
    return resample_poly(numpy.concatenate(pieces), fs_out // gcd, fs // gcd).astype(numpy.float32)


def get_grid_onset(mono, band):
    from scipy.signal import butter
    from scipy.signal import sosfilt
    if band == 'high':
        sos = butter(4, 4000, 'highpass', fs=GRID_FS, output='sos')
    else:
        sos = butter(4, 150, 'lowpass', fs=GRID_FS, output='sos')
    y = sosfilt(sos, mono)
    n = len(y) // GRID_HOP
    energy = numpy.sqrt(numpy.mean(y[:n * GRID_HOP].reshape(n, GRID_HOP) ** 2, axis=1))
    energy = numpy.log1p(1000 * energy)
    return numpy.maximum(numpy.diff(energy, prepend=energy[0]), 0)


def fold_grid_onset(onset, bpm):
    period = 60.0 / bpm * GRID_FS / GRID_HOP
    phase = (numpy.arange(len(onset)) % period) / period
    folded = numpy.bincount((phase * GRID_BINS).astype(int) % GRID_BINS,
                            weights=onset, minlength=GRID_BINS)
    return numpy.convolve(numpy.r_[folded[-2:], folded, folded[:2]], numpy.ones(5) / 5,
                          mode='valid')


def get_fold_grid(mono, seed):
    '''(bpm, phase): tempo near seed where high band attacks line up best'''
    high = get_grid_onset(mono, 'high')
    best = None
    for span, step in GRID_SEARCH:
        centre = seed if best is None else best[1]
        for bpm in numpy.arange(centre - span, centre + span + step / 2, step):
            folded = fold_grid_onset(high, bpm)
            sharpness = folded.max() / (folded.mean() + 1e-9)
            if best is None or sharpness > best[0]:
                best = (sharpness, bpm, folded)
    _, bpm, folded = best
    period = 60.0 / bpm
    phase = (numpy.argmax(folded) + 0.5) / GRID_BINS * period
    # off-beat hats can be sharpest: the kick is on the beat
    low = fold_grid_onset(get_grid_onset(mono, 'low'), bpm)

    def kick(at):
        k = int(round(at / period * GRID_BINS))
        return sum(low[(k + i) % GRID_BINS] for i in range(25))

    if kick((phase + period / 2) % period) > kick(phase):
        phase = (phase + period / 2) % period
    return float(bpm), float(phase)


def get_beatthis():
    '''once a process; None without the package'''
    with BEATTHIS.lock:
        if BEATTHIS.predictor is None and BEATTHIS.failed is False:
            try:
                from beat_this.inference import Audio2Beats
                BEATTHIS.predictor = Audio2Beats(checkpoint_path='final0', device='cpu',
                                                 dbn=False)
            except Exception:
                BEATTHIS.failed = True
        return BEATTHIS.predictor


def predict_beatthis_here(audio, fs):
    predictor = get_beatthis()
    if predictor is None:
        return None
    with BEATTHIS.lock:
        beats, downbeats = predictor(audio, fs)
    return [float(v) for v in beats], [float(v) for v in downbeats]


def predict_beatthis(audio):
    '''(beats, downbeats) of the clip from the model's process; or None'''
    if DEEPRHYTHM.address is None:
        return predict_beatthis_here(audio, BEATTHIS_FS)
    answer = ask_model(('beats', audio, BEATTHIS_FS))
    if not isinstance(answer, tuple):
        return None
    return answer


def resolve_grid_phase(phase, period, beats):
    # quarter-beat move that Beat This!'s beats sit on, if clear
    beats = numpy.asarray(beats)
    if len(beats) < 8:
        return phase
    costs = [numpy.median(numpy.abs(((beats - phase - k * period / 4) / period + 0.5) % 1 - 0.5))
             * period for k in range(4)]
    k = int(numpy.argmin(costs))
    if k != 0 and costs[k] < BEATTHIS_NEAR and costs[0] > BEATTHIS_FAR:
        return phase + k * period / 4
    return phase


def get_grid_bar(downbeats, phase, period):
    # bar start by the most downbeats
    if len(downbeats) == 0:
        return None
    beats = numpy.round((numpy.asarray(downbeats) - phase) / period).astype(int) % 4
    return int(numpy.bincount(beats, minlength=4).argmax())


def analyze_grid(path, tempo, highlight):
    '''Struct(bpm, downbeat, source), or None when the song gives no grid'''
    if not tempo or tempo <= 0:
        return None
    mono = read_mono_all(path, GRID_FS * 4)
    if mono is None or len(mono) < GRID_FS * 4 * 20:
        return None
    from scipy.signal import resample_poly
    bpm, phase = get_fold_grid(resample_poly(mono, 1, 4).astype(numpy.float32), tempo)
    period = 60.0 / bpm
    bar, source = 0, 'fold'
    start = max(0.0, min(highlight[0] if highlight else 0.0,
                         len(mono) / (GRID_FS * 4) - BEATTHIS_SECONDS))
    clip = mono[int(start * GRID_FS * 4):int((start + BEATTHIS_SECONDS) * GRID_FS * 4)]
    try:
        answer = predict_beatthis(resample_poly(clip, 1, 2).astype(numpy.float32))
    except Exception:
        answer = None
    if answer is not None:
        beats, downbeats = (numpy.asarray(v) + start for v in answer)
        phase = resolve_grid_phase(phase, period, beats)
        found = get_grid_bar(downbeats, phase, period)
        if found is not None:
            bar, source = found, 'beatthis'
    phrase, margin = 0, 0.0
    try:
        change = get_beat_changes(mono, GRID_FS * 4, phase % period, period)
        # beat numbers from the grid's first beat
        bar = (bar + int(round((phase - phase % period) / period))) % 4
        checked = check_grid_bar(change, bar)
        if checked != bar:
            bar, source = checked, source + '+changes'
        phrase, margin = get_grid_phrase(change, bar)
    except Exception:
        pass
    downbeat = (phase % period + bar * period) % (period * 4)
    return Struct(bpm=bpm, downbeat=downbeat, source=source, phrase=phrase,
                  phrase_margin=margin)


def get_highlight_taper(count, duration):
    '''author's weight along the song: head and tail eased (mfeats_single)'''
    limit_factor = 1 - (duration - 60.0) / duration
    if limit_factor > 1.00:
        limit_factor = 0.00
    if limit_factor < 0.25:
        limit_factor = 0.25
    taper = numpy.ones(count)
    htlength = int(count * limit_factor)
    if htlength > 0:
        window = numpy.hamming(htlength * 2)
        taper[:htlength] = window[:htlength]
        taper[-htlength:] = window[htlength:]
    return taper


def segment_means(values, a, b):
    '''values[a[i]:b[i]].mean() for each i, vectorized'''
    size = len(values)
    a = numpy.asarray(a, dtype=numpy.int64)
    b = numpy.asarray(b, dtype=numpy.int64)
    lo, hi = numpy.minimum(a, size), numpy.minimum(b, size)
    n = hi - lo
    out = numpy.zeros(len(a))
    ok = n > 0
    if ok.any():
        padded = numpy.append(numpy.asarray(values, dtype=float), 0.0)
        index = numpy.empty(2 * int(ok.sum()), dtype=numpy.int64)
        index[0::2], index[1::2] = lo[ok], hi[ok]
        out[ok] = numpy.add.reduceat(padded, index)[0::2] / n[ok]
    out[(b > a) & ~ok] = numpy.nan
    return out


def segment_mins(values, a, b):
    # values[a[i]:b[i]].min() for each i
    index = numpy.empty(2 * len(a), dtype=numpy.int64)
    index[0::2], index[1::2] = a, numpy.minimum(b, len(values))
    padded = numpy.append(numpy.asarray(values, dtype=float), numpy.inf)
    return numpy.minimum.reduceat(padded, index)[0::2]


def choose_phrase_highlight(waveform, duration, bpm, phrase_start, length, step=None,
                            earliest=None, latest=None):
    '''(start, scores) of the highlight on phrase starts of the grid'''
    period = 60.0 / bpm
    bar = period * 4
    phrase = step or period * 16
    columns = len(waveform) / duration
    # the waveform keeps the level square-rooted
    amplitude = (waveform[:, 1].astype(float) / 255.0) ** 2
    weighted = amplitude * get_highlight_taper(len(amplitude), duration)
    low = waveform[:, 2].astype(float)

    first = phrase_start % bar
    count = int((duration - first) / bar)
    if count < 8:
        return None, []
    # mean bounds, every bar at once
    i = numpy.arange(count)
    a = (numpy.maximum(first + i * bar, 0) * columns).astype(numpy.int64)
    b = (numpy.minimum(first + (i + 1) * bar, duration) * columns).astype(numpy.int64)
    bars, lows = segment_means(amplitude, a, b), segment_means(low, a, b)
    spread = bars.std() + 1e-9
    low_spread = lows.std() + 1e-9
    size = max(1, int(round(length / bar)))
    # weigh the starts, then their measures all at once
    starts, bar_index, allowed = [], [], []
    found = False
    start = phrase_start % phrase
    while start + bar * size <= duration + 1e-6 or not found:
        i = int(round((start - first) / bar))
        if i < 0 or i >= count:
            # no bars left
            break
        starts.append(start)
        bar_index.append(i)
        allowed.append((earliest is None or start >= earliest - 1e-6)
                       and (latest is None or start <= latest + 1e-6))
        found = found or allowed[-1]
        start += phrase
        if not found and start > duration:
            break
    if not found:
        return None, []
    s = numpy.array(starts)
    i = numpy.array(bar_index, dtype=numpy.int64)
    inside = segment_means(bars, i, i + size)
    before = numpy.maximum(i - 4, 0)
    rise = numpy.where(i > before, (segment_means(bars, i, i + min(2, size))
                                    - segment_means(bars, before, i)) / spread, 0.0)
    dip = (inside - segment_mins(bars, i, i + size)) / spread
    held = segment_means(weighted, (numpy.maximum(s, 0) * columns).astype(numpy.int64),
                         (numpy.minimum(s + length, duration) * columns).astype(numpy.int64))
    # the author's measure first; the rest corrects it
    scores = (held - bars.mean()) / spread\
        + 0.25 * (segment_means(lows, i, i + size) - lows.mean()) / low_spread\
        + 0.2 * numpy.clip(rise, 0.0, 2.0) - 0.4 * dip
    scored = [(score, start) for score, start, ok in zip(scores, starts, allowed) if ok]
    return max(scored)[1], scored


def get_bar_levels(waveform, duration, bar, first):
    """(level, low) per bar from first"""
    columns = len(waveform) / duration
    amplitude = (waveform[:, 1].astype(float) / 255.0) ** 2
    low = amplitude * waveform[:, 2].astype(float) / 255.0
    i = numpy.arange(max(0, int((duration - first) / bar)))
    a = ((first + i * bar) * columns).astype(numpy.int64)
    b = ((first + (i + 1) * bar) * columns).astype(numpy.int64)
    return segment_means(amplitude, a, b), segment_means(low, a, b)


def refine_highlight_start(waveform, duration, bpm, start):
    """start moved a bar to where the kick and bass come back"""
    bar = 4 * 60.0 / bpm
    first = start % bar
    _, lows = get_bar_levels(waveform, duration, bar, first)
    if len(lows) < 8:
        return start
    rises = numpy.diff(lows)
    spread = rises.std() + 1e-12
    i = int(round((start - first) / bar))

    def rise(k):
        return lows[k] - lows[k - 1] if 1 <= k < len(lows) else -numpy.inf

    best = max((-1, 0, 1), key=lambda k: (rise(i + k), -abs(k)))
    if best != 0 and rise(i + best) > 0 and \
            rise(i + best) - rise(i) > HIGHLIGHT_LOW_RISE * spread:
        return start + best * bar
    return start


def choose_long_highlight(waveform, duration, bpm, phrase_start, length, step, earliest,
                          latest):
    """start of a longer highlight with the fewest calm bars, or None"""
    _, scored = choose_phrase_highlight(waveform, duration, bpm, phrase_start, length, step,
                                        earliest, latest)
    if not scored:
        return None
    bar = 4 * 60.0 / bpm
    first = phrase_start % bar
    levels, lows = get_bar_levels(waveform, duration, bar, first)
    calm = (levels < HIGHLIGHT_CALM * numpy.quantile(levels, 0.75)) | \
        (lows < HIGHLIGHT_CALM * numpy.quantile(lows, 0.75))
    size = max(1, int(round(length / bar)))

    def count(start):
        i = int(round((start - first) / bar))
        return int(calm[max(i, 0):i + size].sum())

    return min(scored, key=lambda v: (count(v[1]), -v[0]))[1]


def get_phrase_start(grid):
    # first phrase start (seconds) with shift and phrase_shift
    period = 60.0 / grid.bpm
    downbeat = (grid.downbeat + (grid.shift or 0) * period) % (period * 4)
    return downbeat + (((grid.phrase or 0) + (grid.phrase_shift or 0)) % 4) * period * 4


def choose_radio_edit(waveform, duration, bpm, phrase_start, target=None, keep=None):
    """(start, end, cuts) of a DJ track played as a radio edit, or None"""
    bar = 4 * 60.0 / bpm
    block = bar * 4
    first = phrase_start % block
    levels, lows = get_bar_levels(waveform, duration, bar, first)
    count = len(levels) // 4
    if count < 8:
        return None
    body, body_low = numpy.quantile(levels, 0.75), numpy.quantile(lows, 0.75)
    if body <= 0 or body_low <= 0:
        return None
    level = levels[:count * 4].reshape(count, 4).mean(axis=1) / body
    low = lows[:count * 4].reshape(count, 4).mean(axis=1) / body_low
    # mids and highs block by block, against the body's
    columns = len(waveform) / duration
    amplitude = (waveform[:, 1].astype(float) / 255.0) ** 2
    full = level.copy()
    i = numpy.arange(count)
    a = ((first + i * block) * columns).astype(numpy.int64)
    b = ((first + (i + 1) * block) * columns).astype(numpy.int64)
    shares = []
    for band in (3, 4):
        share = amplitude * waveform[:, band].astype(float) / 255.0
        # an empty slice's mean is nan
        values = segment_means(share, a, b)
        values[b <= a] = numpy.nan
        shares.append(values / (numpy.quantile(values, 0.75) + 1e-12))
        full += shares[-1]
    main = (level >= EDIT_MAIN) & (full / 3.0 >= EDIT_FULL) & (shares[0] >= EDIT_MIDS)
    # two blocks running: a lone loud one is not the main part
    starts = [i for i in range(count - 1) if main[i] and main[i + 1]]
    if not starts:
        return None
    head = starts[0]
    tail = max(i for i in range(count) if main[i]) + 1
    if tail - head < 8:
        return None
    cuts = []
    i = head
    while i < tail:
        if low[i] >= HIGHLIGHT_CALM:
            i += 1
            continue
        j = i
        while j < tail and low[j] < HIGHLIGHT_CALM:
            j += 1
        pairs = (j - EDIT_BREAK_TAIL - (i + EDIT_BREAK_HEAD)) // 2
        if pairs >= 1:
            cut_from = first + (i + EDIT_BREAK_HEAD) * block
            cuts.append((cut_from, cut_from + pairs * 2 * block))
        i = j
    kept = None
    if keep is not None and keep[1] > keep[0]:
        kept = (max(int((keep[0] - first) // block), 0),
                min(int(numpy.ceil((keep[1] - first) / block - 1e-6)), count))
        head, tail = min(head, kept[0]), max(tail, kept[1])
        cuts = [(a, b) for a, b in cuts if b <= keep[0] + 1e-6 or a >= keep[1] - 1e-6]
    if target:
        head, tail, cuts = window_edit(first, block, head, tail, cuts, target, low, kept)
    return (first + head * block, min(first + tail * block, duration), cuts)


# timed edit (window_edit): least blocks and off-part weights
EDIT_END_LEAST = 8
EDIT_OFF_PART = 2
EDIT_LATE_START = 1


def window_edit(first, block, head, tail, cuts, target, low, kept=None):
    '''(head, tail, cuts) of the edit played about target seconds'''
    cut = set()
    for a, b in cuts:
        cut.update(range(int(round((a - first) / block)), int(round((b - first) / block))))
    # blocks played before each block (prefix sums)
    played = [0]
    for i in range(tail + 1):
        played.append(played[-1] + (head <= i < tail and i not in cut))
    if played[tail] * block <= target + block:
        return head, tail, cuts

    def is_start(i):
        return i == head or (head < i < tail and low[i - 1] < HIGHLIGHT_CALM <= low[i])

    def is_end(i):
        return i == tail or (head < i < tail and low[i] < HIGHLIGHT_CALM <= low[i - 1])

    steps = set(range(head, tail + 1, 2))
    starts = [i for i in range(head, tail) if (is_start(i) or i in steps) and i not in cut]
    ends = [i for i in range(head + 1, tail + 1) if (is_end(i) or i in steps)
            and i - 1 not in cut]
    best = None
    for s in starts:
        if kept is not None and s > kept[0]:
            break
        for e in ends:
            if e - s < EDIT_END_LEAST or (kept is not None and e < kept[1]):
                continue
            off = abs((played[e] - played[s]) * block - target) / block
            off += (0 if is_start(s) else EDIT_OFF_PART) + (0 if is_end(e) else EDIT_OFF_PART)
            off += EDIT_LATE_START if s > head else 0
            if best is None or off < best[0]:
                best = (off, s, e)
    if best is None:
        return head, tail, cuts
    _, s, e = best
    start_at, end_at = first + s * block, first + e * block
    return s, e, [(max(a, start_at), min(b, end_at)) for a, b in cuts
                  if a < end_at - 1e-6 and b > start_at + 1e-6]


def get_beat_changes(mono, fs, start, period):
    '''sound change at each beat: 4 beats after against the 4 before'''
    feats = []
    for k in range(int((len(mono) / fs - start) / period)):
        segment = mono[int((start + k * period) * fs):int((start + (k + 1) * period) * fs)]
        power = numpy.abs(numpy.fft.rfft(segment * numpy.hanning(len(segment)))) ** 2
        freqs = numpy.fft.rfftfreq(len(segment), 1.0 / fs)
        bands = [power[(freqs >= low) & (freqs < high)].sum()
                 for low, high in zip(PHRASE_BANDS[:-1], PHRASE_BANDS[1:])]
        feats.append(numpy.r_[numpy.log1p(bands),
                              numpy.log1p(numpy.sqrt(numpy.mean(segment ** 2)) * 100)])
    feats = numpy.array(feats)
    w = PHRASE_WINDOW
    change = numpy.zeros(len(feats))
    for k in range(w, len(feats) - w):
        change[k] = numpy.linalg.norm(feats[k:k + w].mean(0) - feats[k - w:k].mean(0))
    return change


def check_grid_bar(change, bar):
    '''the bar's first beat (0 to 3) the biggest changes clearly point to'''
    peaks = [k for k in range(1, len(change) - 1)
             if change[k] > 0 and change[k] == change[max(0, k - 3):k + 4].max()]
    if len(peaks) < 8:
        return bar
    values = numpy.array([change[k] for k in peaks])
    top = [k for k in peaks if change[k] >= numpy.quantile(values, 0.7)]
    weights = numpy.bincount([k % 4 for k in top], weights=[change[k] for k in top], minlength=4)
    best = int(weights.argmax())
    if best != bar and weights[best] >= BAR_OVERRIDE * max(weights[bar], 1e-9):
        return best
    return bar


def get_grid_phrase(change, bar):
    '''(bars to the first phrase start, its score lead as a share)'''
    if len(change) < PHRASE_WINDOW * 2 + 16:
        return 0, 0.0
    scores = numpy.array([change[(bar + 4 * q) % 16::16].sum() for q in range(4)])
    ranked = numpy.sort(scores)[::-1]
    return int(numpy.argmax(scores)), float((ranked[0] - ranked[1]) / (ranked[0] + 1e-9))


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
        create_mfeats_index(table_name, db_name)
        return
    fields = ','.join([' '.join(field) for field in MFEATS_DEFINITION])
    query = f'''CREATE TABLE {table_name} ({fields});'''
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
    # except Exception:
    #     pass
    # finally:
    #     if conn:
    #         conn.close()


def drop_table(table_name='mfeats', db_name=None):
    if db_name is None:
        db_name = MFEATS_DB
    query = f'''DROP TABLE IF EXISTS {table_name};'''
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
    query = f'''DELETE FROM {table_name} WHERE {key}="{value}"'''
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


# class SQLiteThread(threading.Thread):

#     def __init__(self):
#         threading.Thread.__init__(self)
#         self.interval = 0.05
#         self.quit = False
#         self.argvs = []
#         self.kwargs = {}
#         self.run()

#     def getby_key_value(self, *argvs, **kwargs):
#         self.argvs = argvs
#         self.kwargs = kwargs

#     def run(self):
#         while not self.quit:

#             resp = getby_key_value_with_thread(self.result)

#     def __del__(self):
#         pass


# def getby_key_value_with_thread(key, value, table_name='mfeats', db_name=None):
#     thread = SQLiteThread()
#     thread.getby_key_value(key, value, table_name, db_name)


def create_mfeats_index(table_name='mfeats', db_name=None):
    # rows are looked up by path too
    if db_name is None:
        db_name = MFEATS_DB
    conn = sqlite3.connect(db_name)
    conn.execute(f'CREATE INDEX IF NOT EXISTS {table_name}_path ON {table_name} (path)')
    # and by length, for the same sound analyzed before its sound was kept
    conn.execute(f'CREATE INDEX IF NOT EXISTS {table_name}_duration ON {table_name} (duration)')
    conn.commit()
    conn.close()


def getby_key_value(key, value, table_name='mfeats', db_name=None, waveform=True):
    # waveform=False: the row without its waveform blob
    if db_name is None:
        db_name = MFEATS_DB
    # query = f'''SELECT * FROM {table_name} WHERE {key}="{value}"'''
    fields = [field_key for field_key, _ in MFEATS_DEFINITION]
    if waveform is False:
        fields = ["'' AS waveform" if v == 'waveform' else v for v in fields]
    query = f'''SELECT {','.join(fields)} FROM {table_name} WHERE {key}=?'''
    conn = None
    # sqlite.connect(':memory:', check_same_thread = False)
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    resp = c.execute(query, (value,))

    if resp is None:
        conn.close()
        return
    fetchs = resp.fetchall()
    if len(fetchs) == 0:
        conn.close()
        return
    field_keys = [field_key for field_key, _ in MFEATS_DEFINITION]
    data = {k: v for k, v in zip(field_keys, fetchs[0])}
    # exec(f'for {",".join(field_keys)} in fetchs: break')

    blob_field_keys = [field_key for field_key,
                       field_type in MFEATS_DEFINITION if field_type == 'BLOB']
    # data = {}
    for field_key in blob_field_keys:
        if field_key == 'waveform' and waveform is False:
            continue
        data.update(**{field_key: decompress_object(data[field_key])})
        # exec(f'{field_key} = decompress_object({field_key})')

    conn.close()
    mfeats_data = MFEATS(**data)
    # kwrds = ['='.join(v) for v in zip(field_keys, field_keys)]
    # mfeats_data = eval('MFEATS(%s)' % (','.join(kwrds)))
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
    # except Exception:
    #     pass
    # finally:
    #     if conn:
    #         conn.close()


def update_many_key_values(where, key_values, table_name='mfeats', db_name=None):
    if db_name is None:
        db_name = MFEATS_DB
    # key_values = [''.join([key, '="', value, '"']) for key, value in key_values]
    # key_values = ','.join(key_values)
    # query = '''UPDATE %s SET %s WHERE %s="%s";''' % (table_name, key_values, where[0], where[1])
    # values as parameters: quotes broke the query
    names = ','.join([f'{key}=?' for key, _ in key_values])
    query = f'''UPDATE {table_name} SET {names} WHERE {where[0]}=?;'''
    conn = None
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute(query, [value for _, value in key_values] + [where[1]])
    conn.commit()
    conn.close()
    # try:
    #     conn = sqlite3.connect(db_name)
    #     c = conn.cursor()
    #     c.execute(query)
    #     conn.commit()
    #     conn.close()
    # except Exception:
    #     pass
    # finally:
    #     if conn:
    #         conn.close()


# waveform of a song still being analyzed, in its own table
MFEATS_WAVE_TABLE = 'mfeats_wave'


def insert_mfeats_wave(mfeats_data):
    fields = ','.join([' '.join(field) for field in MFEATS_DEFINITION])
    conn = sqlite3.connect(MFEATS_DB)
    conn.execute(f'CREATE TABLE IF NOT EXISTS {MFEATS_WAVE_TABLE} ({fields})')
    conn.commit()
    conn.close()
    insert_mfeats(mfeats_data, table_name=MFEATS_WAVE_TABLE)


def getby_mdx_wave(mdx):
    # no table before the first one
    try:
        return getby_key_value('mdx', mdx, table_name=MFEATS_WAVE_TABLE)
    except sqlite3.Error:
        return None


def delete_mfeats_wave(mdx):
    deleteby_key_value('mdx', mdx, table_name=MFEATS_WAVE_TABLE)


# beat grid: its own table and version; shift and phrase_shift are
# manual moves kept through a new analysis
GRID_DEFINITION = (('mdx', 'TEXT PRIMARY KEY'), ('bpm', 'REAL'), ('downbeat', 'REAL'),
                   ('shift', 'INTEGER'), ('source', 'TEXT'), ('version', 'TEXT'),
                   ('date', 'REAL'), ('phrase', 'INTEGER'), ('phrase_shift', 'INTEGER'),
                   ('phrase_margin', 'REAL'), ('phrase_set', 'INTEGER'),
                   ('bpm_scale', 'REAL'))


def connect_grid():
    conn = sqlite3.connect(MFEATS_DB)
    conn.execute(f'CREATE TABLE IF NOT EXISTS {GRID_TABLE} '
                 f'({",".join([" ".join(field) for field in GRID_DEFINITION])})')
    # older table: add the phrase columns
    columns = [v[1] for v in conn.execute(f'PRAGMA table_info({GRID_TABLE})')]
    for key, kind in GRID_DEFINITION:
        if key not in columns:
            conn.execute(f'ALTER TABLE {GRID_TABLE} ADD COLUMN {key} {kind} DEFAULT 0')
            conn.commit()
    return conn


def get_grid(mdx):
    '''the song's grid row (bpm 0: none found), or None'''
    conn = connect_grid()
    try:
        row = conn.execute(f'SELECT * FROM {GRID_TABLE} WHERE mdx=?', (mdx,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return Struct(**dict(zip([key for key, _ in GRID_DEFINITION], row)))


def get_done_mdx():
    '''songs with nothing left to analyze'''
    conn = connect_grid()
    try:
        rows = conn.execute(
            f'SELECT m.mdx FROM mfeats m LEFT JOIN {GRID_TABLE} g ON g.mdx = m.mdx '
            'WHERE m.version = ? AND (m.error != 0 OR g.version = ?)',
            (MFEATS_VERSION, GRID_VERSION)).fetchall()
    finally:
        conn.close()
    return set(row[0] for row in rows)


def get_analysis_versions():
    '''{mdx: (version, error, grid version or None)} of every song'''
    conn = connect_grid()
    try:
        rows = conn.execute(
            'SELECT m.mdx, m.version, m.error, g.version FROM mfeats m '
            f'LEFT JOIN {GRID_TABLE} g ON g.mdx = m.mdx').fetchall()
    finally:
        conn.close()
    return dict((row[0], tuple(row[1:])) for row in rows)


def is_grid_current(mdx):
    grid = get_grid(mdx)
    return grid is not None and grid.version == GRID_VERSION


def insert_grid(mdx, grid):
    old = get_grid(mdx)
    if grid is None:
        grid = Struct(bpm=0.0, downbeat=0.0, source='', phrase=0, phrase_margin=0.0)
    # manual tempo scale kept through a new analysis
    scale = old.bpm_scale if old is not None and old.bpm_scale else 1.0
    shift, phrase_shift = get_kept_moves(old, grid, scale)
    # a manually set phrase stays set
    phrase_set = 1 if old is not None and old.phrase_set else 0
    conn = connect_grid()
    try:
        conn.execute(f'INSERT OR REPLACE INTO {GRID_TABLE} VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                     (mdx, grid.bpm, grid.downbeat, shift, grid.source, GRID_VERSION,
                      time.time(), grid.phrase, phrase_shift, grid.phrase_margin, phrase_set,
                      scale))
        conn.commit()
    finally:
        conn.close()


def get_kept_moves(old, grid, scale=1.0):
    '''(shift, phrase_shift) keeping manual moves at the same place in the song'''
    if old is None or not (old.shift or old.phrase_shift) or not old.bpm or not grid.bpm:
        return 0, 0
    period = 60.0 / (grid.bpm * scale)
    old_period = 60.0 / (old.bpm * (old.bpm_scale or 1.0))
    bar = (old.downbeat + (old.shift or 0) * old_period) % (old_period * 4)
    phrase = bar + ((old.phrase or 0) + (old.phrase_shift or 0)) % 4 * old_period * 4
    shift = int(round((bar - grid.downbeat) / period)) % 4 if old.shift else 0
    downbeat = grid.downbeat + shift * period
    phrase_shift = (int(round((phrase - downbeat) / (period * 4))) - (grid.phrase or 0)) % 4\
        if old.phrase_shift or old.shift else 0
    return shift, phrase_shift


def apply_grid_scale(grid):
    '''the grid as played: tempo times the scale'''
    scale = grid.bpm_scale or 1.0
    if scale == 1.0:
        return grid
    played = Struct(**vars(grid))
    played.bpm = grid.bpm * scale
    played.downbeat = grid.downbeat % (60.0 / played.bpm * 4)
    if not grid.phrase_set:
        played.phrase_margin = 0.0
    return played


def set_grid_scale(mdx, scale):
    # new scale: the moves start again
    conn = connect_grid()
    try:
        conn.execute(f'UPDATE {GRID_TABLE} SET bpm_scale=?, shift=0, phrase_shift=0, phrase_set=0 '
                     'WHERE mdx=?', (scale, mdx))
        conn.commit()
    finally:
        conn.close()


def set_grid_shift(mdx, shift, key='shift', phrase_set=None):
    # key: 'shift' (beats) or 'phrase_shift' (bars); phrase_set: manual (1)
    conn = connect_grid()
    try:
        conn.execute(f'UPDATE {GRID_TABLE} SET {key}=? WHERE mdx=?', (int(shift) % 4, mdx))
        if phrase_set is not None:
            conn.execute(f'UPDATE {GRID_TABLE} SET phrase_set=? WHERE mdx=?',
                         (phrase_set, mdx))
        conn.commit()
    finally:
        conn.close()


# the same sound under another path (a copy, a moved file): its analysis
# copied, not done again; read from the decoded sound, so tag edits keep it
SOUND_TABLE = 'mfeats_sound'
SOUND_VERSION = '1.0.0'
SOUND_DEFINITION = (('mdx', 'TEXT PRIMARY KEY'), ('sound', 'TEXT'), ('duration', 'REAL'),
                    ('version', 'TEXT'))
# a second read at each of these shares of the song
SOUND_SPOTS = (0.1, 0.35, 0.6, 0.85)
SOUND_SECONDS = 1.0
# songs analyzed before the table: told by their length, their file read then
SOUND_DURATION_GAP = 0.001
SOUND_UNKEPT_MOST = 8


def connect_sound():
    conn = connect_grid()
    conn.execute(f'CREATE TABLE IF NOT EXISTS {SOUND_TABLE} '
                 f'({",".join([" ".join(field) for field in SOUND_DEFINITION])})')
    conn.execute(f'CREATE INDEX IF NOT EXISTS {SOUND_TABLE}_sound ON {SOUND_TABLE} (sound)')
    return conn


def read_sound(path):
    '''(md5 of the decoded sound, duration), or None'''
    init_bass_decode()
    hstream = pybass.BASS_StreamCreateFile(
        False, path, 0, 0, pybass.BASS_STREAM_DECODE |
        pybass.BASS_STREAM_PRESCAN | pybass.BASS_UNICODE)
    if hstream == 0:
        return None
    try:
        length = pybass.BASS_ChannelGetLength(hstream, pybass.BASS_POS_BYTE)
        info = pybass.BASS_CHANNELINFO()
        if length <= 0 or length == 0xFFFFFFFFFFFFFFFF\
                or pybass.BASS_ChannelGetInfo(hstream, ctypes.byref(info)) is False:
            return None
        duration = pybass.BASS_ChannelBytes2Seconds(hstream, length)
        frame = 2 * info.chans
        size = int(info.freq * SOUND_SECONDS) * frame
        buffer = ctypes.create_string_buffer(size)
        md5 = hashlib.md5(f'{length} {info.freq} {info.chans}'.encode('utf-8'))
        for spot in SOUND_SPOTS:
            pybass.BASS_ChannelSetPosition(hstream, int(length * spot) // frame * frame, False)
            got = pybass.BASS_ChannelGetData(hstream, buffer, size)
            if got == 0xFFFFFFFF:
                return None
            md5.update(buffer.raw[:got])
        return md5.hexdigest(), duration
    finally:
        pybass.BASS_StreamFree(hstream)


def keep_sound(path):
    '''the song's sound read and kept: (sound, duration), or None'''
    found = read_sound(path)
    if found is None:
        return None
    conn = connect_sound()
    try:
        conn.execute(f'INSERT OR REPLACE INTO {SOUND_TABLE} VALUES (?,?,?,?)',
                     (makemdx(path), found[0], found[1], SOUND_VERSION))
        conn.commit()
    finally:
        conn.close()
    return found


def find_unkept_sound(conn, mdx, sound, duration):
    '''songs analyzed before their sound was kept: those of this length read now'''
    rows = conn.execute(
        f'SELECT mdx, path FROM mfeats WHERE duration BETWEEN ? AND ? AND version = ? '
        f'AND error = 0 AND mdx != ? AND mdx NOT IN (SELECT mdx FROM {SOUND_TABLE}) LIMIT ?',
        (duration - SOUND_DURATION_GAP, duration + SOUND_DURATION_GAP, MFEATS_VERSION, mdx,
         SOUND_UNKEPT_MOST)).fetchall()
    found = []
    for other, path in rows:
        # its file gone or changed since: its sound not known
        if os.path.isfile(path) is False or makemdx(path) != other:
            continue
        kept = keep_sound(path)
        if kept is not None and kept[0] == sound:
            found.append(other)
    return found


def copy_analysis(path, sound, duration):
    '''the analysis of the same sound under another path copied to this one; False if none'''
    mdx = makemdx(path)
    conn = connect_sound()
    try:
        others = [row[0] for row in conn.execute(
            f'SELECT s.mdx FROM {SOUND_TABLE} s JOIN mfeats m ON m.mdx = s.mdx '
            'WHERE s.sound = ? AND s.version = ? AND s.mdx != ? AND m.version = ? '
            'AND m.error = 0', (sound, SOUND_VERSION, mdx, MFEATS_VERSION))]
        if len(others) == 0:
            others = find_unkept_sound(conn, mdx, sound, duration)
        if len(others) == 0:
            return False
        # one with its grid first: the manual moves come along
        grids = [row[0] for row in conn.execute(
            f'SELECT mdx FROM {GRID_TABLE} WHERE version = ? AND mdx IN '
            f'({",".join(["?"] * len(others))})', [GRID_VERSION] + others)]
        other = grids[0] if len(grids) > 0 else others[0]
        fields = [key for key, _ in MFEATS_DEFINITION if key not in ('mdx', 'path')]
        conn.execute(f'INSERT OR REPLACE INTO mfeats (mdx,path,{",".join(fields)}) '
                     f'SELECT ?,?,{",".join(fields)} FROM mfeats WHERE mdx = ?',
                     (mdx, path, other))
        fields = [key for key, _ in GRID_DEFINITION if key != 'mdx']
        conn.execute(f'DELETE FROM {GRID_TABLE} WHERE mdx = ?', (mdx,))
        conn.execute(f'INSERT INTO {GRID_TABLE} (mdx,{",".join(fields)}) '
                     f'SELECT ?,{",".join(fields)} FROM {GRID_TABLE} WHERE mdx = ?',
                     (mdx, other))
        conn.commit()
    finally:
        conn.close()
    return True


def move_analysis(old_mdx, mdx, path):
    '''a renamed song's analysis, grid and sound under its new name'''
    update_many_key_values(('mdx', old_mdx), [('path', path), ('mdx', mdx)])
    conn = connect_sound()
    try:
        for table in (GRID_TABLE, SOUND_TABLE):
            conn.execute(f'UPDATE OR REPLACE {table} SET mdx = ? WHERE mdx = ?', (mdx, old_mdx))
        conn.commit()
    finally:
        conn.close()


def analyze_grid_into_db(path, tempo, highlight):
    # keep a failed grid as none (bpm 0), or it retries on every play
    try:
        grid = analyze_grid(path, tempo, highlight)
    except Exception:
        grid = None
    insert_grid(makemdx(path), grid)


def insert_mfeats(mfeats_data, table_name='mfeats', db_name=None):
    # tic = time.time()
    if db_name is None:
        db_name = MFEATS_DB
    # resp = getby_key_value('mdx', mfeats_data.mdx)
    # if resp is not None:
    #     deleteby_key_value('mdx', mfeats_data.mdx)
    # replace in one statement: a reader between delete and insert requeued it

    field_keys = [v for v, _ in MFEATS_DEFINITION]
    field_types = [v for _, v in MFEATS_DEFINITION]
    field_values = [getattr(mfeats_data, v) for v in field_keys]
    for i, field_type in enumerate(field_types):
        if field_type == 'BLOB':
            field_values[i] = compress_object(field_values[i])
        else:
            field_values[i] = f'{field_values[i]}'
    marks = ','.join(['?'] * len(field_values))
    query = f'''INSERT OR REPLACE INTO {table_name} VALUES ({marks});'''
    # print('SET', mfeats_data.mdx, mfeats_data.key, mfeats_data.tempo, field_values)
    conn = None
    conn = sqlite3.connect(db_name)
    c = conn.cursor()
    c.execute(query, field_values)
    conn.commit()
    conn.close()

    # try:
    #     conn = sqlite3.connect(db_name)
    #     c = conn.cursor()
    #     c.execute(query)
    #     conn.commit()
    #     conn.close()
    # except Exception:
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
                # self.proclist[i].proc._Thread__stop()
                self.proclist[i].proc._stop()
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
        # self.Messenger._Thread__stop()
        self.Messenger._stop()
        for i in range(len(self.proclist)):
            self.proclist[i].proc.join()
        for i in range(len(self.proclist)):
            # self.proclist[i].proc._Thread__stop()
            self.proclist[i].proc._stop()
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
    cmd += [f'{int(master_pid)}']
    cmd += [f'{max_memory:.f}']
    cmd += [f'{max_idletime:.f}']
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
