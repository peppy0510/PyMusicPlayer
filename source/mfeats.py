# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import ctypes
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
# 3band waveform: a column's seconds (about), where the lows end, the highs begin and end (Hz)
WAVEFORM_COLUMN_SECONDS = 0.01
# the bands are read over blocks of about this long (a column is too short to tell
# 200 Hz from 1,500); a frame shorter than two of them is read whole
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
            exec('''self.%s = %s''' % (field_key, initial_value))
        self.__dict__.update(kwards)


# https://gist.github.com/endolith/255291
# http://wiki.hydrogenaudio.org/index.php?title=ReplayGain_1.0_specification
# https://gist.github.com/255291/c97d2b088c53104f1d0d7cf8b20e89fc788037df


def mfeats_single(path, queue=None, on_wave=None):
    # on_wave: given the song's waveform (and highlight) as soon as they are there,
    # before the tempo's octave and the key
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
    # an empty file, or one with no length to read
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
    # whole samples of every channel (8 for stereo, as before)
    frame_unit = int(numpy.lcm(8, channel))
    if int(frame_length) % frame_unit != 0:
        frame_length += (frame_unit - int(frame_length) % frame_unit)
    gap = total_frame_length / frame_length - waveform_length
    highlight_raw_points = numpy.linspace(0, 0, int(round(waveform_length + gap)))
    frame_raw = numpy.arange(frame_length, dtype=ctypes.c_short)
    # jump = 1.0 * frame_length / waveform_oversampling
    mix_length = int(frame_length / channel)
    # the waveform's columns: a frame split into some of about WAVEFORM_COLUMN_SECONDS
    sub_count = max(int(round(1.0 * mix_length / fs / WAVEFORM_COLUMN_SECONDS)), 1)
    sub_length = int(mix_length / sub_count)
    # waveform = numpy.linspace(0, 0, int(round(waveform_length + gap)))
    waveform = numpy.zeros((int(round(waveform_length + gap)) * sub_count, 5))
    # mix_window = numpy.hanning(mix_length)
    # mix_freqs = numpy.fft.rfftfreq(mix_length, 1.0 / fs)
    # the bands block by block, each column the block its middle falls in: a frame
    # is a 5000th of the file, and a three-hour mix had one colour every 2 seconds
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
    # the key on a thread of its own: this pass hands it the frames it reads for the
    # waveform (mix), thirty seconds at a time, where it handed them to the key
    # itself before, and goes on (its FFTs let go of the GIL). in this pass the key
    # held the waveform back (4.5 s of 22 for an hour's mix); read again after it,
    # the song took a third longer; read again alongside, the two fought for the
    # GIL. the same frames in the same bunches, in order: the same sums to the bit
    key_frames, key_bunches, key_found = ([], Queue(), [])

    def read_key():
        # the first frame centred at 0, as Essentia's FrameCutter
        key_length = get_key_frame_length(fs)
        key_hpcp, rest = (numpy.zeros(12), numpy.zeros(int((key_length + 1) / 2)))
        while True:
            # given up on if this pass is gone (an error in it): no thread left behind
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
    # peak and level square-rooted, then each band's share of the sound
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

    # the waveform shown while the rest goes on: DeepRhythm (its model loaded in a
    # new worker, seconds) and the key's pass are still to come
    if on_wave is not None:
        # the tempo before its octave (for the highlight's length in beats only)
        on_wave(MFEATS(
            mdx=mdx, path=path, duration=duration, highlight=highlight, waveform=waveform,
            tempo=tempo, date=time.time(), version=version, channel=channel, bit=bit,
            error=0, autogain=0.4))

    # the octave from DeepRhythm over the highlight, the value from the spectrum
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


# Essentia's KeyExtractor with its defaults (bgate profile) in numpy: whitened spectral
# peaks of 25 to 3500 Hz into a 12-bin HPCP over the whole song. Same keys as Essentia on
# 1,413 songs; on 1,526 tagged songs 66% against 36% for the highlight's most frequent chord.

KEY_FS = 44100
KEY_FRAME = 4096
KEY_MIN_FREQUENCY = 25.0
KEY_MAX_FREQUENCY = 3500.0
KEY_MAX_PEAKS = 60
KEY_PEAK_THRESHOLD = 0.0001
KEY_PCP_THRESHOLD = 0.2
# added to the minor correlations: the library is mostly minor (84% of tags, 94% of 10,916
# labelled loops); exact 63 to 68% on songs, 44 to 49% on loops, majors 83 to 79% and 43 to 38%
KEY_MINOR_BIAS = 0.05
# major and minor from A (Faraldo, Jorda and Herrera, AES Semantic Audio 2017)
KEY_PROFILES = (
    (1.00, 0.00, 0.42, 0.00, 0.53, 0.37, 0.00, 0.77, 0.00, 0.38, 0.21, 0.30),
    (1.00, 0.00, 0.36, 0.39, 0.00, 0.38, 0.00, 0.74, 0.27, 0.00, 0.42, 0.23))


def get_key_frame_length(fs):
    return int(round(1.0 * KEY_FRAME * fs / KEY_FS))


def get_key_harmonics():
    '''(semitone, weight) of a peak as the 1st to 5th harmonic of a lower note'''
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
    '''the frames' HPCP summed, from A'''
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

    # whitening: a peak's level against the spectrum's envelope, every 100 Hz
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
    '''the whole frames of mix added to hpcp, the rest returned (padded and added if last)'''
    if last and len(mix) % length != 0:
        mix = numpy.concatenate((mix, numpy.zeros(length - len(mix) % length)))
    count = int(len(mix) / length)
    if count > 0:
        hpcp += get_key_hpcp(mix[:count * length].reshape(count, length), fs)
    return mix[count * length:]


def get_key_from_hpcp(hpcp):
    '''the chord index (C to B major, then minor) of the best correlated profile, or None'''
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
        # a failed analysis is kept as an error, or it was tried again on every start
        try:
            self.result = mfeats_single(self.path)
        except Exception:
            self.result = MFEATS(mdx=makemdx(self.path), path=self.path,
                                 date=time.time(), version=MFEATS_VERSION, error=1)
        insert_mfeats(self.result)

    def __del__(self):
        pass


# how long the key's thread waits for the next frames before it gives up
KEY_BUNCH_WAIT = 120


def mfeats_worker(conn, model_address=None):
    # model_address: deeprhythm_server's, for the tempo's octave (none: the model here)
    # one process for the songs in a row: torch and its models load once, not a song each.
    # here, not in macroboxlib: a worker spawned for one there imported macroboxlib first,
    # met this module importing it back half done (circular import) and died before a song
    set_process_priority(6)
    DEEPRHYTHM.address = model_address
    # DeepRhythm's model is loaded with the first song, after its waveform is out
    # (mfeats_single's on_wave): loaded on a thread alongside, its imports held the
    # GIL and the first waveform came at 5.3 s, not 2.2 (done at 5.4 s either way)
    while True:
        try:
            path = conn.recv()
        except (EOFError, OSError):
            # the app is gone (its end of the pipe closed)
            return
        if path is None:
            return
        # ('grid', path): the song is analyzed, only its grid is not
        if isinstance(path, tuple):
            path = path[1]
            resp = getby_key_value('mdx', makemdx(path), waveform=False)
            if resp is not None and resp.error == 0:
                analyze_grid_into_db(path, resp.tempo, resp.highlight)
            try:
                conn.send(path)
            except (EOFError, OSError):
                return
            continue
        # a failed analysis is kept as an error, or it was tried again on every start
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


# The spectrum below picks the double of a slow song (its harmonic sum favours 2T),
# DeepRhythm picks the octave but only whole BPMs, a class low. Measured on 1,530
# tagged songs: spectrum 79%, DeepRhythm 93%, both 93% and 95% within 0.5 BPM.

DEEPRHYTHM_FS = 22050
DEEPRHYTHM_CLIP = 8
DEEPRHYTHM = Struct(predictor=None, failed=False, lock=threading.Lock(),
                    address=None, client=None, unreachable=0)
# DeepRhythm in a process of its own for all the workers (deeprhythm_server): in each
# worker torch and the model were 313 MB of its 437 (24 workers, 10 GB), and a new
# worker waited seconds for them. a worker given its address sends a clip and gets
# the BPM; a server starting is waited for, a server gone leaves the spectrum tempo
DEEPRHYTHM_CONNECT_WAIT = 20
# the most songs' clips through the model at once (a song is 4 to 8 clips of 8 s)
DEEPRHYTHM_BATCH = 16
DEEPRHYTHM_ANSWER_WAIT = 30
# not reached: tried again after this long (the scheduler starts it again)
DEEPRHYTHM_RETRY = 60


def get_deeprhythm_address(pid):
    return r'\\.\pipe\PyMusicPlayer-deeprhythm-%d' % (pid)


def deeprhythm_server(control, address, threads=None):
    '''DeepRhythm's BPMs for the workers connected at address, until control ends.
    threads: torch's own (the cores the workers leave; torch takes them all by default)'''
    set_process_priority(6)
    if threads is not None:
        import torch
        torch.set_num_threads(threads)
    listener = Listener(address)
    requests = Queue()
    # loaded at once: the first clip comes after a song's first pass
    threading.Thread(target=get_deeprhythm, daemon=True).start()

    def serve(client):
        while True:
            try:
                request = client.recv()
            except (EOFError, OSError):
                break
            # Beat This! for the grid: answered here, a clip at a time
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
        # the clips asked for meanwhile in one batch: one at a time, a clip for each of
        # 24 workers, one process answered 6.7 a second
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
    # told to end (None), or the app gone (its end closed)
    try:
        control.recv()
    except (EOFError, OSError):
        pass


def predict_deeprhythm_batch(batch):
    '''each asked's bpm (None if none): its 8 s clips with all the others' through the
    model at once, then each song's mean as predict_from_audio takes it'''
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
        # the batch failed (one song's clip): each on its own, as before
        for asked in batch:
            try:
                asked.bpm = float(predictor.predict_from_audio(asked.audio, asked.fs))
            except Exception:
                asked.bpm = None


def predict_deeprhythm(audio):
    '''DeepRhythm's BPM for the clip, from the server when the worker has one; or None'''
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
                        # not waited for again at every song of this worker
                        DEEPRHYTHM.unreachable = time.time() + DEEPRHYTHM_RETRY
                        return None
                    time.sleep(0.2)
        DEEPRHYTHM.client.send(request)
        if DEEPRHYTHM.client.poll(DEEPRHYTHM_ANSWER_WAIT) is False:
            raise TimeoutError
        return DEEPRHYTHM.client.recv()
    except Exception:
        # gone or stuck: this song keeps the spectrum tempo, the next one connects again
        try:
            DEEPRHYTHM.client.close()
        except Exception:
            pass
        DEEPRHYTHM.client = None
        return None


def get_deeprhythm():
    '''once a process; None without the package, and the spectrum tempo stays'''
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
    '''the spectrum tempo halved or doubled to DeepRhythm's, when one is within 3%'''
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


# Beat Grid: the tempo to 0.0005 BPM and the beats' phase from the high band's attacks
# folded on the beat; the quarter of a beat they fall on and the bar's first beat from
# Beat This! over the highlight. scored on 268 hand-gridded EDM edits (2026-10-20): all
# within 0.005 BPM, 98-99% of beats within 15 ms, downbeats 87%

GRID_VERSION = '1.1.0'
GRID_TABLE = 'mfeats_grid'
GRID_FS = 11025
GRID_HOP = 11
GRID_SEARCH = ((0.3, 0.01), (0.012, 0.0005))
GRID_BINS = 240
BEATTHIS_FS = 22050
BEATTHIS_SECONDS = 60
# a quarter-beat move of the grid is taken only when Beat This!'s beats sit this
# close to it and this far from where it was
BEATTHIS_NEAR = 0.030
BEATTHIS_FAR = 0.060
BEATTHIS = Struct(predictor=None, failed=False, lock=threading.Lock())
# the phrase (4 bars): the bar after which the sound changes most, beat by beat 4 beats
# against the 4 before, summed over the song. 77% on the edits cut at random (85% on
# the right bar), chance 25%
PHRASE_WINDOW = 4
PHRASE_BANDS = numpy.geomspace(40, 5000, 13)


def read_mono_all(path, fs_out):
    # the whole song as mono at fs_out, read in pieces (a long mix whole at once
    # was hundreds of MB of shorts)
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
    '''(bpm, seconds of a beat from the start): the tempo near seed where the high band's
    attacks line up sharpest on the beat, and where; the half beat told by the kick'''
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
    # off-beat hats are the sharpest in some songs: the kick is on the beat
    low = fold_grid_onset(get_grid_onset(mono, 'low'), bpm)

    def kick(at):
        k = int(round(at / period * GRID_BINS))
        return sum(low[(k + i) % GRID_BINS] for i in range(25))

    if kick((phase + period / 2) % period) > kick(phase):
        phase = (phase + period / 2) % period
    return float(bpm), float(phase)


def get_beatthis():
    '''once a process; None without the package (the grid's own phase and no bar)'''
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
    '''(beats, downbeats) in seconds of the clip, from the model's process when the worker
    has one (the same connection as DeepRhythm's); or None'''
    if DEEPRHYTHM.address is None:
        return predict_beatthis_here(audio, BEATTHIS_FS)
    answer = ask_model(('beats', audio, BEATTHIS_FS))
    if not isinstance(answer, tuple):
        return None
    return answer


def resolve_grid_phase(phase, period, beats):
    # the quarter-beat move of the grid that Beat This!'s beats sit on, if clearly
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
    # which of four beats the bar starts on, by the most downbeats
    if len(downbeats) == 0:
        return None
    beats = numpy.round((numpy.asarray(downbeats) - phase) / period).astype(int) % 4
    return int(numpy.bincount(beats, minlength=4).argmax())


def analyze_grid(path, tempo, highlight):
    '''Struct(bpm, downbeat, source): downbeat, the first bar's start in seconds (0 to
    four beats); source, 'beatthis' when the bar was found, 'fold' when not. None when the
    song gives no grid'''
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
    downbeat = (phase + bar * period) % (period * 4)
    try:
        phrase = get_grid_phrase(mono, GRID_FS * 4, downbeat, period)
    except Exception:
        phrase = 0
    return Struct(bpm=bpm, downbeat=downbeat, source=source, phrase=phrase)


def get_grid_phrase(mono, fs, downbeat, period):
    '''bars (0 to 3) from downbeat to the first phrase's start'''
    feats = []
    start = downbeat % period
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
    if len(feats) < w * 2 + 16:
        return 0
    change = numpy.zeros(len(feats))
    for k in range(w, len(feats) - w):
        change[k] = numpy.linalg.norm(feats[k:k + w].mean(0) - feats[k - w:k].mean(0))
    # beat numbers from the grid's first beat; the downbeat's among them
    bar0 = int(round((downbeat - start) / period)) % 4
    scores = [change[(bar0 + 4 * q) % 16::16].sum() for q in range(4)]
    return int(numpy.argmax(scores))


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
    # except Exception:
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
    # rows are looked up by path too (the scheduler's check)
    if db_name is None:
        db_name = MFEATS_DB
    conn = sqlite3.connect(db_name)
    conn.execute('CREATE INDEX IF NOT EXISTS %s_path ON %s (path)' % (table_name, table_name))
    conn.commit()
    conn.close()


def getby_key_value(key, value, table_name='mfeats', db_name=None, waveform=True):
    # waveform=False: the row without its waveform (the biggest blob), for the
    # list's and the scheduler's checks
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
    # values as parameters: a quote in a key or a tempo broke the query
    names = ','.join(['%s=?' % (key) for key, _ in key_values])
    query = '''UPDATE %s SET %s WHERE %s=?;''' % (table_name, names, where[0])
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


# the waveform of a song still being analyzed (mfeats_single's on_wave), shown
# before its tempo and key: a table of its own, never taken for an analyzed song
MFEATS_WAVE_TABLE = 'mfeats_wave'


def insert_mfeats_wave(mfeats_data):
    fields = ','.join([' '.join(field) for field in MFEATS_DEFINITION])
    conn = sqlite3.connect(MFEATS_DB)
    conn.execute('CREATE TABLE IF NOT EXISTS %s (%s)' % (MFEATS_WAVE_TABLE, fields))
    conn.commit()
    conn.close()
    insert_mfeats(mfeats_data, table_name=MFEATS_WAVE_TABLE)


def getby_mdx_wave(mdx):
    # none yet: no table before the first one
    try:
        return getby_key_value('mdx', mdx, table_name=MFEATS_WAVE_TABLE)
    except sqlite3.Error:
        return None


def delete_mfeats_wave(mdx):
    deleteby_key_value('mdx', mdx, table_name=MFEATS_WAVE_TABLE)


# the beat grid: a table and a version of its own, so a new grid analyzes no song's
# waveform, tempo or key again. shift: the user's move of the bar, in beats, kept
# through a new analysis
# phrase: bars from the downbeat to the first phrase (4 bars); phrase_shift, the user's
# move of it, kept as shift is
GRID_DEFINITION = (('mdx', 'TEXT PRIMARY KEY'), ('bpm', 'REAL'), ('downbeat', 'REAL'),
                   ('shift', 'INTEGER'), ('source', 'TEXT'), ('version', 'TEXT'),
                   ('date', 'REAL'), ('phrase', 'INTEGER'), ('phrase_shift', 'INTEGER'))


def connect_grid():
    conn = sqlite3.connect(MFEATS_DB)
    conn.execute('CREATE TABLE IF NOT EXISTS %s (%s)' % (
        GRID_TABLE, ','.join([' '.join(field) for field in GRID_DEFINITION])))
    # a table made before the phrase: its columns added (at the end, as listed)
    columns = [v[1] for v in conn.execute('PRAGMA table_info(%s)' % (GRID_TABLE))]
    for key, kind in GRID_DEFINITION:
        if key not in columns:
            conn.execute('ALTER TABLE %s ADD COLUMN %s %s DEFAULT 0' % (GRID_TABLE, key, kind))
            conn.commit()
    return conn


def get_grid(mdx):
    '''Struct of the song's grid row (bpm 0: none found), or None when not analyzed'''
    conn = connect_grid()
    try:
        row = conn.execute('SELECT * FROM %s WHERE mdx=?' % (GRID_TABLE), (mdx,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return Struct(**dict(zip([key for key, _ in GRID_DEFINITION], row)))


def is_grid_current(mdx):
    grid = get_grid(mdx)
    return grid is not None and grid.version == GRID_VERSION


def insert_grid(mdx, grid):
    old = get_grid(mdx)
    shift = old.shift if old is not None and old.shift else 0
    phrase_shift = old.phrase_shift if old is not None and old.phrase_shift else 0
    if grid is None:
        grid = Struct(bpm=0.0, downbeat=0.0, source='', phrase=0)
    conn = connect_grid()
    try:
        conn.execute('INSERT OR REPLACE INTO %s VALUES (?,?,?,?,?,?,?,?,?)' % (GRID_TABLE),
                     (mdx, grid.bpm, grid.downbeat, shift, grid.source, GRID_VERSION,
                      time.time(), grid.phrase, phrase_shift))
        conn.commit()
    finally:
        conn.close()


def set_grid_shift(mdx, shift, key='shift'):
    # key: 'shift' (the bar, in beats) or 'phrase_shift' (the phrase, in bars)
    conn = connect_grid()
    try:
        conn.execute('UPDATE %s SET %s=? WHERE mdx=?' % (GRID_TABLE, key), (int(shift) % 4, mdx))
        conn.commit()
    finally:
        conn.close()


def analyze_grid_into_db(path, tempo, highlight):
    # a failed grid is kept as none (bpm 0), or it was tried again every time it played
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
    # replaced in one statement: deleted then inserted, a reader in between found
    # no row and queued the file again

    field_keys = [v for v, _ in MFEATS_DEFINITION]
    field_types = [v for _, v in MFEATS_DEFINITION]
    field_values = [getattr(mfeats_data, v) for v in field_keys]
    for i, field_type in enumerate(field_types):
        if field_type == 'BLOB':
            field_values[i] = compress_object(field_values[i])
        else:
            field_values[i] = '%s' % (field_values[i])
    marks = ','.join(['?'] * len(field_values))
    query = '''INSERT OR REPLACE INTO %s VALUES (%s);''' % (table_name, marks)
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
