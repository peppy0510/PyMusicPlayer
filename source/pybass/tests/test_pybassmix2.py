#!/usr/bin/python -tt


__version__ = '0.2'
__versionTime__ = '2013-04-11'
__author__ = 'Luigi Brambilla <l.brambilla@abcdef.it>'


import sys
import time

from pybass import BASS_ATTRIB_VOL
from pybass import BASS_ChannelBytes2Seconds
from pybass import BASS_ChannelGetLength
from pybass import BASS_ChannelGetPosition
from pybass import BASS_ChannelPlay
from pybass import BASS_ChannelSeconds2Bytes
from pybass import BASS_ChannelSetAttribute
from pybass import BASS_ChannelSetSync
from pybass import BASS_ErrorGetCode
from pybass import BASS_Init
from pybass import BASS_POS_BYTE
from pybass import BASS_STREAM_DECODE
from pybass import BASS_STREAM_PRESCAN
from pybass import BASS_SYNC_END
from pybass import BASS_SYNC_ONETIME
from pybass import BASS_SYNC_POS
from pybass import BASS_StreamCreateFile
from pybass import BASS_StreamFree
from pybass import SYNCPROC
from pybass import get_error_description
from pybassmix import BASS_MIXER_NONSTOP
from pybassmix import BASS_MIXER_NORAMPIN
from pybassmix import BASS_Mixer_ChannelGetMixer
from pybassmix import BASS_Mixer_StreamAddChannel
from pybassmix import BASS_Mixer_StreamCreate


def CloseStream(handle, channel, data, chan):
    BASS_StreamFree(handle)


def Print10(handle, channel, data, chan):
    print('\n\n ****** Sync after 10 seconds \n')


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

        BASS_Mixer_StreamAddChannel(mixer, stream, BASS_MIXER_NORAMPIN)
        print('           - ADD stream - %s' % get_error_description(BASS_ErrorGetCode()))

        mom = BASS_Mixer_ChannelGetMixer(stream)
        print('%s - GET Mixer - %s' % (repr(mom), get_error_description(BASS_ErrorGetCode())))

        sync = BASS_ChannelSetSync(stream, BASS_SYNC_END | BASS_SYNC_ONETIME, 0, SYNCPROC(CloseStream), 0)
        print('%s - SET Sync close - %s' % (repr(sync), get_error_description(BASS_ErrorGetCode())))

        sec10 = BASS_ChannelSeconds2Bytes(stream, 10)
        print('10 seconds = %d bytes, %s' % (sec10, get_error_description(BASS_ErrorGetCode())))

        tsync = BASS_ChannelSetSync(stream, BASS_SYNC_POS | BASS_SYNC_ONETIME, sec10, SYNCPROC(Print10), 0)
        print('%s - SET Sync 10 sec - %s' % (repr(tsync), get_error_description(BASS_ErrorGetCode())))

        channel_length = BASS_ChannelGetLength(stream, BASS_POS_BYTE)
        channel_position = BASS_ChannelGetPosition(stream, BASS_POS_BYTE)

        while channel_position < channel_length:
            channel_position = BASS_ChannelGetPosition(stream, BASS_POS_BYTE)
            value = 'Play second %s of song' % str(int(BASS_ChannelBytes2Seconds(stream, channel_position)))
            sys.stdout.write('%s\r' % value.ljust(20))
            sys.stdout.flush()
            time.sleep(2)
