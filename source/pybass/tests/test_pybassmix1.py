#!/usr/bin/python -tt


__version__ = '0.1'
__versionTime__ = '2013-04-10'
__author__ = 'Luigi Brambilla <l.brambilla@abcdef.it>'


import time

from pybass import BASS_ATTRIB_VOL
from pybass import BASS_ChannelBytes2Seconds
from pybass import BASS_ChannelGetLength
from pybass import BASS_ChannelGetPosition
from pybass import BASS_ChannelPlay
from pybass import BASS_ChannelSetAttribute
from pybass import BASS_ErrorGetCode
from pybass import BASS_Init
from pybass import BASS_POS_BYTE
from pybass import BASS_STREAM_DECODE
from pybass import BASS_STREAM_PRESCAN
from pybass import BASS_StreamCreateFile
from pybass import get_error_description
from pybassmix import BASS_MIXER_NONSTOP
from pybassmix import BASS_MIXER_NORAMPIN
from pybassmix import BASS_Mixer_StreamAddChannel
from pybassmix import BASS_Mixer_StreamCreate


if __name__ == '__main__':
    if not BASS_Init(1, 44100, 0, 0, 0):
        print('           - BASS_Init error %s' % get_error_description(BASS_ErrorGetCode()))
    else:
        print('           - BASS_Init %s' % get_error_description(BASS_ErrorGetCode()))

        mixer = BASS_Mixer_StreamCreate(44100, 2, BASS_MIXER_NONSTOP)
        print('%s - BASS_Mixer_StreamCreate - %s' % (repr(mixer), get_error_description(BASS_ErrorGetCode())))
        BASS_ChannelPlay(mixer, False)
        print('           - BASS_Channel play mixer %s' % get_error_description(BASS_ErrorGetCode()))
        BASS_ChannelSetAttribute(mixer, BASS_ATTRIB_VOL, 0.8)
        print('           - BASS_SetAttribute %s' % get_error_description(BASS_ErrorGetCode()))

        stream = BASS_StreamCreateFile(False, 'test.mp3', 0, 0, BASS_STREAM_PRESCAN | BASS_STREAM_DECODE)
        print('%s - BASS_StreamCreateFile %s' % (repr(stream), get_error_description(BASS_ErrorGetCode())))

        BASS_Mixer_StreamAddChannel(mixer, stream, BASS_MIXER_NORAMPIN)  # | BASS_MIXER_BUFFER
        print('           - ADD stream - %s' % get_error_description(BASS_ErrorGetCode()))

        channel_length = BASS_ChannelGetLength(stream, BASS_POS_BYTE)
        channel_position = BASS_ChannelGetPosition(stream, BASS_POS_BYTE)

        # ~ if not BASS_ChannelPlay(stream, False):
        # ~ print('BASS_ChannelPlay error %s' % get_error_description(BASS_ErrorGetCode()))
        # ~ else:
        while channel_position < channel_length:
            channel_position = BASS_ChannelGetPosition(stream, BASS_POS_BYTE)
            print(int(BASS_ChannelBytes2Seconds(stream, channel_position)))
            print(int(BASS_ChannelBytes2Seconds(mixer, BASS_ChannelGetPosition(mixer, BASS_POS_BYTE))))
            time.sleep(2)
