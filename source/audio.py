# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import os
import sys


# try:
#     packages = os.path.join(sys._MEIPASS, 'packages')
# except Exception:
#     packages = os.path.join('packages')

# sys.path.insert(0, packages)


import codecs
import ctypes
import math
import mutagen
import mutagen.id3
import mutagen.mp3
import numpy
# import packctrl
import modpybass as pybass
import struct

from PIL import Image
from copy import deepcopy
from scipy import signal
from scipy import where
from utilities import makemdx  # noqa


# def platform_sign():
#     if platform.architecture()[0] == '':
#         return ''
#     return ''


def find_max_point(inlist):
    maxvalue = max(inlist)
    pntadd = []
    for cnt, this in enumerate(inlist):
        if this == maxvalue:
            pntadd.append(cnt)
    return pntadd


def find_min_point(inlist):
    minvalue = min(inlist)
    pntadd = []
    for cnt, this in enumerate(inlist):
        if this == minvalue:
            pntadd.append(cnt)
    return pntadd


def find_zcrs(data):
    data = numpy.array(data)
    zcrs = where(data[1:] * data[:-1] <= 0)[0]
    delete_points = where(zcrs[1:] - zcrs[:-1] == 1)[0]
    zcrs = numpy.delete(zcrs, delete_points)
    return zcrs


def find_peaks(data, threshold=0):
    data = numpy.array(data) / (1.0 * max(data))
    peaks = where(data[1:] - data[:-1] <= 0)[0]
    delete_points = where(peaks[1:] - peaks[:-1] == 1)[0]
    peaks = numpy.delete(peaks, numpy.array(delete_points) + 1)
    delete_points = []
    for cnt in range(0, len(peaks)):
        if numpy.abs(data[peaks[cnt]]) < threshold:
            delete_points.append(cnt)
    peaks = numpy.delete(peaks, delete_points)
    return peaks


def fade_inout(indata, fadein=20, fadeout=20):
    if fadein != 0:
        winfadein = numpy.hamming(fadein * 2)[:fadein]
        indata[:fadein] = indata[:fadein] * winfadein
    if fadeout != 0:
        winfadeout = numpy.hamming(fadeout * 2)[fadeout:]
        indata[-fadeout:] = indata[-fadeout:] * winfadeout
    return indata


def encode_wave(audiodata):
    raw_data = []
    try:
        nchannels = len(audiodata[0])
    except Exception:
        nchannels = 1
    if nchannels == 1:
        for i in range(0, len(audiodata)):
            raw_data.append(struct.pack('h', audiodata[i]))
    if nchannels == 2:
        for i in range(0, len(audiodata)):
            raw_data.append(struct.pack('h', audiodata[i][0]))
            raw_data.append(struct.pack('h', audiodata[i][1]))
    return ''.join(raw_data)


def decode_wave(raw_data):
    nframes = len(raw_data) / 2
    # 8bit:"%iB":unsigned chars # 16bit:"%ih":signed 2 byte shorts
    for fmt in ('%ih' % nframes, '%iB' % nframes):
        try:
            return struct.unpack(fmt, raw_data)
        except Exception:
            pass


# def mplot(data, zoom=None, title=''):
#     a = 0
#     b = len(data[0])
#     if zoom is not None:
#         a = zoom[0]
#         b = zoom[1]
#     for cnt in range(0, len(data)):
#         pos = '%d%d%d' % (len(data), 1, cnt + 1)
#         pylab.subplot(int(pos))
#         pylab.title(str(title))
#         pylab.plot(data[cnt][a:b])
#     pylab.show()


def interpolation(data, input_fs, output_fs):
    num = int(len(data) / (1.0 * input_fs / output_fs))
    return numpy.interp(numpy.linspace(0, len(data) - 1, num), numpy.arange(len(data)), data)


def fixed_length_interp(data, output_length):
    return numpy.interp(numpy.linspace(0, len(data) - 1, output_length), numpy.arange(len(data)), data)


def easy_fft(indata, fftpnt):
    outdata = numpy.fft.fft(indata, fftpnt)
    outdata = numpy.abs(outdata[1:int(len(outdata) / 2)])
    return outdata


def max_wide_fill(input_data, output_length):
    jump = 2.0 * len(input_data) / output_length
    output_data = numpy.linspace(0, 0, output_length)
    for cnt, pnt in enumerate(numpy.arange(0, len(input_data) - jump, jump)):
        output_data[cnt * 2] = max(input_data[int(pnt):int(numpy.ceil(pnt + jump))])
        output_data[cnt * 2 + 1] = min(input_data[int(pnt):int(numpy.ceil(pnt + jump))])
    return output_data


def max_wide_fill_sym(input_data, output_length):
    jump = 1.0 * len(input_data) / output_length
    output_data = numpy.linspace(0, 0, output_length)
    for cnt, pnt in enumerate(numpy.arange(0, len(input_data) - jump - 1, jump)):
        output_data[cnt] = max(abs(input_data[int(pnt):int(numpy.ceil(pnt + jump)) + 1]))
    return output_data


def wav2img(data, dstpath=None,
            width=1500, height=75, oversampling=1, antialias='ANTIALIAS'):

    bgcolor = 'white'
    wavcolor = (25, 50, 50)
    data = max_wide_fill(data, width * 2 * oversampling)
    center = int(height / 2)
    data = 1.0 * data / max(numpy.abs(data)) * center
    data = numpy.int16(numpy.round(data))
    im = Image.new("RGB", (len(data) / 2, height), bgcolor)
    for x, cnt in enumerate(range(0, len(data), 2)):
        im.putpixel((x, center), wavcolor)
        for y in range(data[cnt]):
            im.putpixel((x, -y - 1 - center + height), wavcolor)
        for y in range(0, data[cnt + 1], -1):
            im.putpixel((x, -y + center), wavcolor)

    # NEAREST BILINEAR BICUBIC ANTIALIAS
    im = im.resize((width, height), eval('Image.' + antialias))
    if dstpath is not None:
        format = os.path.splitext(dstpath)[-1][1:]
        im.save(dstpath, format)
    return im


def smooth(data, windowsize=50):
    window = numpy.hamming(windowsize)
    output = numpy.convolve(data, window)
    output = numpy.convolve(window, output)
    trim = int((len(output) - len(data)) / 2)
    output = output[trim + 1:-trim]
    return output


def normalize_offset_level(data):
    offsets = [numpy.mean(data[i:i + 10]) for i in range(len(data) - 10)]
    offsets = offsets + [offsets[-1]] * 15
    for i in range(len(data)):
        v = data[i] - offsets[i]
        if v < 0:
            v = 0
        data[i] = v
    return data


def fir_filter(data, lowcut, highcut, fs, order=29):
    # order: Length of the filter
    # (number of coefficients, i.e. the filter order + 1)
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if low == 0 and high == 1:
        return data
    elif low == 0 and high != 1:
        coeff = signal.firwin(order, highcut / nyq)
    elif low != 0 and high == 1:
        coeff = signal.firwin(order, lowcut / nyq, pass_zero=False)
    elif low != 0 and high != 1:
        coeff = signal.firwin(order, [low, high], pass_zero=False)
    output = signal.lfilter(coeff, 1.0, data)
    return output


def butter_filter(data, lowcut, highcut, fs, order=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if low == 0 and high == 1:
        return data
    elif low == 0 and high != 1:
        b, a = signal.butter(order, highcut / nyq, btype='low')
    elif low != 0 and high == 1:
        b, a = signal.butter(order, lowcut / nyq, btype='high')
    elif low != 0 and high != 1:
        b, a = signal.butter(order, [low, high], btype='band')
    output = signal.filtfilt(b, a, data)  # lfilter(b, a, data)
    return output


def cheby1_filter(data, lowcut, highcut, fs, order=5, riple=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if low == 0 and high == 1:
        return data
    elif low == 0 and high != 1:
        b, a = signal.cheby1(order, riple, highcut / nyq, btype='low')
    elif low != 0 and high == 1:
        b, a = signal.cheby1(order, riple, lowcut / nyq, btype='high')
    elif low != 0 and high != 1:
        b, a = signal.cheby1(order, riple, [low, high], btype='band')
    output = signal.filtfilt(b, a, data)  # lfilter(b, a, data)
    return output


def cheby2_filter(data, lowcut, highcut, fs, order=5, riple=5):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    if low == 0 and high == 1:
        return data
    elif low == 0 and high != 1:
        b, a = signal.cheby2(order, riple, highcut / nyq, btype='low')
    elif low != 0 and high == 1:
        b, a = signal.cheby2(order, riple, lowcut / nyq, btype='high')
    elif low != 0 and high != 1:
        b, a = signal.cheby2(order, riple, [low, high], btype='band')
    output = signal.filtfilt(b, a, data)  # lfilter(b, a, data)
    return output


# pybass.BASS_Init(-1,...)
# -1 is default device / 0 is no sound / 1 is first real output device

def init_bass_play():
    plugins = ['bass_vst.dll', 'bassaac.dll', 'bassac3.dll', 'bassape.dll',
               'bassflac.dll', 'bass_mpc.dll', 'bassopus.dll', 'basswma.dll']
    # 'bass_spx.dll', 'bass_tta.dll', 'bass_aix.dll'
    for plugin in plugins:
        try:
            bass_module, func_type = pybass.bass.load(plugin)
            pybass.BASS_PluginLoad(bass_module, func_type)
        except Exception:
            pass
        # pybass.BASS_PluginLoad(packctrl.findPath(plugin, ['', 'packages']), 0)
    pybass.BASS_Init(-1, 44100, 0, 0, 0)


def init_bass_decode():
    plugins = ['bass_vst.dll', 'bassaac.dll', 'bassac3.dll', 'bassape.dll',
               'bassflac.dll', 'bassmpc.dll', 'bassopus.dll', 'basswma.dll']
    # 'bass_spx.dll', 'bass_tta.dll', 'bass_aix.dll'
    for plugin in plugins:
        try:
            bass_module, func_type = pybass.bass.load(plugin)
            pybass.BASS_PluginLoad(bass_module, func_type)
        except Exception:
            pass
        # pybass.BASS_PluginLoad(packctrl.findPath(plugin, ['', 'packages']), 0)
    # pybass.BASS_Init(0, 0, 0, 0, 0)
    pybass.BASS_Init(-1, 44100, 0, 0, 0)


def get_channel(path):
    # input is filename
    hstream = pybass.BASS_StreamCreateFile(
        False, path, 0, 0, pybass.BASS_STREAM_DECODE | pybass.BASS_SAMPLE_MONO | pybass.BASS_UNICODE)
    fs = get_fs(hstream)
    duration = get_duration(hstream)
    # length_m = pybass.BASS_ChannelGetLength(hstream, pybass.BASS_POS_BYTE)
    pybass.BASS_StreamFree(hstream)
    hstream = pybass.BASS_StreamCreateFile(
        False, path, 0, 0, pybass.BASS_STREAM_DECODE | pybass.BASS_UNICODE)
    length_s = pybass.BASS_ChannelGetLength(hstream, pybass.BASS_POS_BYTE)
    pybass.BASS_StreamFree(hstream)
    if duration * fs == 0:
        return 0
    return int(round(1.0 * length_s / (duration * fs * 2)))


def get_fs(input_data):
    fs = ctypes.c_float()
    # if input is hstream
    # if type(input_data) in (int, long,):
    if isinstance(input_data, int):
        pybass.BASS_ChannelGetAttribute(
            input_data, pybass.BASS_ATTRIB_FREQ, ctypes.byref(fs))
        return int(fs.value)

    # if input is filename
    hstream = pybass.BASS_StreamCreateFile(
        False, input_data, 0, 0, pybass.BASS_STREAM_DECODE | pybass.BASS_UNICODE)
    pybass.BASS_ChannelGetAttribute(
        hstream, pybass.BASS_ATTRIB_FREQ, ctypes.byref(fs))
    return deepcopy(int(fs.value))


def get_duration(input_data):
    # if input is hstream
    # if type(input_data) in (int, long,):
    if isinstance(input_data, int):
        hlength = pybass.BASS_ChannelGetLength(input_data, pybass.BASS_POS_BYTE)
        return pybass.BASS_ChannelBytes2Seconds(input_data, hlength)

    # if input is filename
    hstream = pybass.BASS_StreamCreateFile(
        False, input_data, 0, 0, pybass.BASS_STREAM_DECODE | pybass.BASS_UNICODE)
    hlength = pybass.BASS_ChannelGetLength(hstream, pybass.BASS_POS_BYTE)
    duration = pybass.BASS_ChannelBytes2Seconds(hstream, hlength)
    return deepcopy(duration)


# def play(filename, hstream=0, cue_second=None):
#     if pybass.BASS_ChannelIsActive(hstream) == 1:
#         pybass.BASS_StreamFree(hstream)
#     filename = os.path.abspath(filename)
#     ufilename = filename.encode(sys.getfilesystemencoding())
#     hstream = pybass.BASS_StreamCreateFile(False, ufilename, 0, 0, 0)
#     if cue_second is not None:
#         set_position(hstream, cue_second)
#     PlayThread(hstream)
#     return hstream


def is_playing(hstream):
    if pybass.BASS_ChannelIsActive(hstream) == 1:
        return True
    return False


def stop(hstream):
    return_second = get_position(hstream)
    if pybass.BASS_ChannelIsActive(hstream) == 1:
        pybass.BASS_StreamFree(hstream)
    return return_second


def fforward(hstream, skip_second):
    new_second = get_position(hstream) + skip_second
    if new_second >= get_duration(hstream):
        stop(hstream)
    else:
        set_position(hstream, new_second)


def fbackward(hstream, skip_second):
    new_second = get_position(hstream) - skip_second
    if new_second <= 0:
        set_position(hstream, 0)
    else:
        set_position(hstream, new_second)


def get_position(hstream):
    byte_position = pybass.BASS_ChannelGetPosition(hstream, False)
    return pybass.BASS_ChannelBytes2Seconds(hstream, byte_position)


def set_position(hstream, second):
    byte_position = pybass.BASS_ChannelSeconds2Bytes(hstream, second)
    pybass.BASS_ChannelSetPosition(hstream, byte_position, False)


def set_volume(hstream, volume):
    pybass.BASS_ChannelSetAttribute(hstream, pybass.BASS_ATTRIB_VOL, volume)


def get_stream_level(hstream):
    if hstream == 0:
        return 0
    frame_length = 44100 / 30  # 1024*16
    frame_raw = numpy.arange(frame_length, dtype=ctypes.c_short)
    pybass.BASS_ChannelGetData(hstream, frame_raw.ctypes.
                               data_as(ctypes.POINTER(ctypes.c_short)), frame_length * 2)
    frame_raw = numpy.int32(frame_raw)
    level = numpy.mean(numpy.power(frame_raw, 2))
    level = numpy.power(level, 0.5) / 32768 * 2
    level = numpy.power(level, 0.5)
    return level


def get_stream_vectorscope(hstream, size):
    if hstream == 0:
        return None
    frame_length = int(44100 / 10)
    data = numpy.arange(frame_length, dtype=ctypes.c_short)
    pybass.BASS_ChannelGetData(hstream, data.ctypes.
                               data_as(ctypes.POINTER(ctypes.c_short)), frame_length * 2)
    if max(data) == 0:
        return
    dataL = numpy.array(data[0::2]) * 0.00001 * size
    dataR = numpy.array(data[1::2]) * 0.00001 * size
    sdt = numpy.sin(0.75 * numpy.pi)
    cdt = numpy.cos(0.75 * numpy.pi)
    xdts = dataR * cdt + dataL * sdt
    ydts = -dataL * sdt + dataR * cdt
    return zip(xdts + 0.5 * size + 1, ydts + 0.5 * size + 1)


def get_stream_spectrum_vectorscope_repl(hstream, vs_size=90, channel=2, autogain=1):
    if hstream == 0:
        return 0
    amplify = 1.25
    # amplify = 0.99
    fftrex = 1
    fs = get_fs(hstream)
    if fs == 0:
        return None, None
    freqmax = int(round(fs / fftrex))
    frame_length = int(round(freqmax * fftrex * 0.075 * (2 / channel)))
    fftpnt = int(round(freqmax * fftrex * 0.1))
    data = numpy.arange(frame_length, dtype=ctypes.c_short)
    pybass.BASS_ChannelGetData(hstream, data.ctypes.
                               data_as(ctypes.POINTER(ctypes.c_short)), frame_length)
    if channel == 1:
        dataL, dataR = (data, data)
    elif channel == 2:
        dataL = numpy.array(data[0::2])
        dataR = numpy.array(data[1::2])

    amplify = autogain * (1.0 / 0.4) * 2 * (1.0 * fs / 44100) * amplify
    spectrum = numpy.fft.fft(dataL * amplify, fftpnt)
    spectrum = spectrum[1:int(len(spectrum) / 2)]
    spectrum = abs(spectrum) / fftpnt / 8192
    low_pad = [2, 3, 4, 5, 6, 7]
    freqbin = [freq for freq in get_note_freq_range()
               if freq > 8 and freq < len(spectrum) + len(low_pad) + 1]
    freqbin = low_pad + freqbin + [len(spectrum)]
    log_spcetrum = numpy.zeros(len(freqbin) - 1)
    for i, v in enumerate(freqbin[:-1]):
        x = numpy.max(spectrum[freqbin[i]:freqbin[i + 1] + 1])
        log_spcetrum[i] = x * math.log(1 + v, 2) * (v**0.25)
        log_spcetrum[i] = (log_spcetrum[i]**(1.4 * ((2 + i) / (1 + i)))) * 1.5
    # print numpy.mean(log_spcetrum)

    # dataL = dataL*amplify*1.20
    # dataR = dataR*amplify*1.20
    dataL = dataL * amplify * 1.00
    dataR = dataR * amplify * 1.00
    dataL_max = numpy.max(numpy.abs(dataL))
    dataR_max = numpy.max(numpy.abs(dataR))
    data_max = max((dataL_max, dataR_max))
    if data_max > 32768:
        dataL = dataL / data_max * 32768
        dataR = dataR / data_max * 32768
    dataL = dataL[:1024] * 0.00001 * vs_size
    dataR = dataR[:1024] * 0.00001 * vs_size
    sdt = numpy.sin(0.75 * numpy.pi)
    cdt = numpy.cos(0.75 * numpy.pi)
    xdts = dataR * cdt + dataL * sdt
    ydts = -dataL * sdt + dataR * cdt

    xys = zip(numpy.int16(-xdts + 0.5 * vs_size), numpy.int16(ydts + 0.5 * vs_size))
    # xys = zip(numpy.int16(-xdts+0.5*vs_size), numpy.int16(ydts+0.5*vs_size+1.5))
    # if data_max < 9921:
    #   xys = ()
    #   log_spcetrum = log_spcetrum/2
    # print data_max
    return log_spcetrum, list(set(xys))


def get_stream_spectrum_vectorscope(hstream, vs_size=90, channel=2, autogain=1, spectrum_scale=1):
    if hstream == 0:
        return 0
    amplify = 1.25
    amplify = 1.25 * pow(spectrum_scale, 0.5)
    # amplify = 0.99
    fftrex = 1
    fs = get_fs(hstream)
    if fs == 0:
        return None, None
    freqmax = int(round(fs / fftrex))
    frame_length = int(round(freqmax * fftrex * 0.075 * (2 / channel)))
    # frame_length = int(round(freqmax * fftrex * 0.075 * (2 / channel) * pow(spectrum_scale, 0.75)))
    fftpnt = int(round(freqmax * fftrex * 0.1))
    data = numpy.arange(frame_length, dtype=ctypes.c_short)
    pybass.BASS_ChannelGetData(hstream, data.ctypes.
                               data_as(ctypes.POINTER(ctypes.c_short)), frame_length)
    if channel == 1:
        dataL, dataR = (data, data)
    elif channel == 2:
        dataL = numpy.array(data[0::2])
        dataR = numpy.array(data[1::2])

    amplify = autogain * (1.0 / 0.4) * 2 * (1.0 * fs / 44100) * amplify
    spectrum = numpy.fft.fft(dataL * amplify, fftpnt)
    spectrum = spectrum[1:int(len(spectrum) / 2)]
    spectrum = abs(spectrum) / fftpnt / 8192
    low_pad = [2, 3, 4, 5, 6, 7]
    # low_pad = []
    # for i in range(len(note_freq_range) - 1, 0, -1):
    #     x = (note_freq_range[i] - note_freq_range[i - 1]) / spectrum_scale
    #     for ii in range(spectrum_scale - 1, 0, -1):
    #         note_freq_range.insert(i, note_freq_range[i - 1] + x * ii)

    note_freq_range = list(get_note_freq_range())

    freqbin = [freq for freq in note_freq_range
               if freq > 8 and freq < len(spectrum) + len(low_pad) + 1]
    # freqbin = low_pad + freqbin + [len(spectrum)]
    freqbin = low_pad + freqbin + [len(spectrum)]

    for i in range(len(freqbin) - 1, 0, -1):
        x = (freqbin[i] - freqbin[i - 1]) / spectrum_scale
        for ii in range(spectrum_scale - 1, 0, -1):
            freqbin.insert(i, freqbin[i - 1] + x * ii)

    # print(freqbin)
    log_spcetrum = numpy.zeros(len(freqbin) - 1)
    for i, v in enumerate(freqbin[:-1]):
        x = numpy.max(spectrum[int(freqbin[i]):int(freqbin[i + 1]) + 1])
        log_spcetrum[i] = x * math.log(1 + v, 2) * (v**0.25)
        log_spcetrum[i] = (log_spcetrum[i]**(1.4 * ((2 + i) / (1 + i)))) * 1.5
    # print numpy.mean(log_spcetrum)

    dataL = dataL * amplify * 1.20
    dataR = dataR * amplify * 1.20
    dataL_max = numpy.max(numpy.abs(dataL))
    dataR_max = numpy.max(numpy.abs(dataR))
    data_max = max((dataL_max, dataR_max))
    if data_max > 32768:
        dataL = dataL / data_max * 32768
        dataR = dataR / data_max * 32768
    dataL = dataL[:768] * 0.00001 * vs_size
    dataR = dataR[:768] * 0.00001 * vs_size
    sdt = numpy.sin(0.75 * numpy.pi)
    cdt = numpy.cos(0.75 * numpy.pi)
    xdts = dataR * cdt + dataL * sdt
    ydts = -dataL * sdt + dataR * cdt
    xys = zip(numpy.int16(-xdts + 0.5 * vs_size), numpy.int16(ydts + 0.5 * vs_size + 1))
    return log_spcetrum, list(set(xys))


def get_id3(filename, field_keys):
    # filename = filename.encode(sys.getfilesystemencoding())
    try:
        mutagen_id3 = mutagen.id3.ID3(filename)
    except Exception:
        return None
    audio_id3 = dict()
    for field_key in field_keys:
        # field_key = field_key.encode(sys.getfilesystemencoding())
        try:
            value = mutagen_id3.get(field_key)
        except Exception:
            value = None
        if value is None or len(value.text) == 0:
            audio_id3[field_key] = u''
        else:
            value = value.text[0]
            # try:
            #     value = unicode(value).encode("iso-8859-1")\
            #         .decode(sys.getfilesystemencoding())
            # except:
            #     pass
            audio_id3[field_key] = value
    del mutagen_id3, field_key, value
    return audio_id3


def read_m3u(filename):
    f = codecs.open(filename, 'rb', encoding=sys.getfilesystemencoding())
    paths = list()
    for line in f.readlines():
        if line.startswith('#EXTM3U'):
            continue
        if line.startswith('#EXTINF:'):
            continue
        paths.append(line.splitlines()[0])
    f.close()
    return paths


def generate_m3u(filename, paths):
    # filename = filename.encode(sys.getfilesystemencoding())
    f = codecs.open(filename, 'wb', encoding=sys.getfilesystemencoding())
    f.write(u'#EXTM3U\n')
    for path in paths:
        string = ''.join(('#EXTINF:\n', path, '\n'))
        f.write(string)
    f.close()


def second2time(duration, format=0):
    if format == 0:
        return '%02d:%02d' % (duration / 60, duration % 60)
    return '%02d:%02d.%02d' % (duration / 60, duration % 60, duration % 1 * 100)


# exec compile('get_id3 = get_id3', '<string>', 'exec')


# maxnote = 128
# noteC0 = 8.1757989156
# noteratio = 1.05946309435929
# notefreq = numpy.arange(1, maxnote, 1)
# noterang = numpy.arange(1, maxnote+1, 1)
# for cnt in range(1, maxnote):
#   notefreq[cnt-1] = noteC0*numpy.power(noteratio, cnt)
# for cnt in range(1, maxnote+1):
#   noterang[cnt-1] = noteC0*numpy.power(noteratio, cnt-0.5)


def get_note_freq():
    return (
        8.17579891560000, 8.66195721798090, 9.17702399736983, 9.72271824126291,
        10.3008611534719, 10.9133822322228, 11.5623257096764, 12.2498573743638,
        12.9782717993034, 13.7499999999259, 14.5676175473617, 15.4338531641705,
        16.3515978311990, 17.3239144359608, 18.3540479947386, 19.4454364825246,
        20.6017223069426, 21.8267644644442, 23.1246514193515, 24.4997147487260,
        25.9565435986052, 27.4999999998501, 29.1352350947217, 30.8677063283392,
        32.7031956623961, 34.6478288719195, 36.7080959894749, 38.8908729650470,
        41.2034446138827, 43.6535289288858, 46.2493028387001, 48.9994294974491,
        51.9130871972073, 54.9999999996969, 58.2704701894399, 61.7354126566747,
        65.4063913247883, 69.2956577438348, 73.4161919789455, 77.7817459300893,
        82.4068892277605, 87.3070578577664, 92.4986056773947, 97.9988589948924,
        103.826174394408, 109.999999999387, 116.540940378873, 123.470825313342,
        130.812782649569, 138.591315487661, 146.832383957882, 155.563491860169,
        164.813778455511, 174.614115715522, 184.997211354778, 195.997717989773,
        207.652348788804, 219.999999998761, 233.081880757731, 246.941650626669,
        261.625565299122, 277.182630975306, 293.664767915747, 311.126983720320,
        329.627556911003, 349.228231431024, 369.994422709535, 391.995435979523,
        415.304697577584, 439.999999997496, 466.163761515435, 493.883301253309,
        523.251130598212, 554.365261950579, 587.329535831459, 622.253967440603,
        659.255113821966, 698.456462862006, 739.988845419025, 783.990871958999,
        830.609395155119, 879.999999994940, 932.327523030814, 987.766602506559,
        1046.50226119636, 1108.73052390109, 1174.65907166285, 1244.50793488113,
        1318.51022764385, 1396.91292572393, 1479.97769083796, 1567.98174391790,
        1661.21879031014, 1759.99999998977, 1864.65504606152, 1975.53320501300,
        2093.00452239260, 2217.46104780205, 2349.31814332555, 2489.01586976211,
        2637.02045528755, 2793.82585144769, 2959.95538167575, 3135.96348783562,
        3322.43758062008, 3519.99999997934, 3729.31009212281, 3951.06641002576,
        4186.00904478495, 4434.92209560383, 4698.63628665083, 4978.03173952393,
        5274.04091057478, 5587.65170289504, 5919.91076335114, 6271.92697567086,
        6644.87516123976, 7039.99999995826, 7458.62018424518, 7902.13282005105,
        8372.01808956939, 8869.84419120714, 9397.27257330109, 9956.06347904726,
        10548.0818211489, 11175.3034057894, 11839.8215267016, 12543.8539513410)


def get_note_freq_range():
    return (
        8, 8.41536811017449, 8.91577193817796, 9.44593132622375, 10.0076156319864,
        10.6026994246227, 11.2331687409722, 11.9011277137705, 12.6088055939964,
        13.3585641907901, 14.1529057537717, 14.9944813240663, 15.8860995819079,
        16.8307362203480, 17.8315438763549, 18.8918626524464, 20.0152312639715,
        21.2053988492441, 22.4663374819431, 23.8022554275395, 25.2176111879912,
        26.7171283815786, 28.3058115075417, 29.9889626481309, 31.7721991638139,
        33.6614724406940, 35.6630877527076, 37.7837253048905, 40.0304625279407,
        42.4107976984856, 44.9326749638834, 47.6045108550761, 50.4352223759794,
        53.4342567631540, 56.6116230150800, 59.9779252962582, 63.5443983276241,
        67.3229448813839, 71.3261755054109, 75.5674506097764, 80.0609250558765,
        84.8215953969662, 89.8653499277615, 95.2090217101466, 100.870444751953,
        106.868513526302, 113.223246030153, 119.955850592509, 127.088796655241,
        134.645889762760, 142.652351010813, 151.134901219544, 160.121850111743,
        169.643190793922, 179.730699855512, 190.418043420282, 201.740889503893,
        213.737027052590, 226.446492060293, 239.911701185004, 254.177593310466,
        269.291779525503, 285.304702021609, 302.269802439069, 320.243700223468,
        339.286381587824, 359.461399711003, 380.836086840541, 403.481779007763,
        427.474054105155, 452.892984120558, 479.823402369980, 508.355186620901,
        538.583559050974, 570.609404043185, 604.539604878103, 640.487400446897,
        678.572763175607, 718.922799421963, 761.672173681036, 806.963558015477,
        854.948108210259, 905.785968241063, 959.646804739902, 1016.71037324174,
        1077.16711810188, 1141.21880808630, 1209.07920975613, 1280.97480089372,
        1357.14552635113, 1437.84559884384, 1523.34434736198, 1613.92711603086,
        1709.89621642042, 1811.57193648202, 1919.29360947969, 2033.42074648336,
        2154.33423620364, 2282.43761617247, 2418.15841951212, 2561.94960178728,
        2714.29105270211, 2875.69119768751, 3046.68869472378, 3227.85423206152,
        3419.79243284063, 3623.14387296382, 3838.58721895915, 4066.84149296648,
        4308.66847240702, 4564.87523234466, 4836.31683902395, 5123.89920357426,
        5428.58210540388, 5751.38239537467, 6093.37738944719, 6455.70846412265,
        6839.58486568085, 7246.28774592720, 7677.17443791784, 8133.68298593247,
        8617.33694481353, 9129.75046468877, 9672.63367804733, 10247.7984071479,
        10857.1642108071, 11502.7647907487, 12186.7547788937, 12911.4169282445)


if __name__ == '__main__':
    init_bass_play()
