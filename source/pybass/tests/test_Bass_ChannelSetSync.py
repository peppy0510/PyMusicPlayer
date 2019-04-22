#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# Copyright(c) Wasylews 2013 (sabov.97@mail.ru)


from pybass import BASS_ChannelSetSync
from pybass import BASS_Free
from pybass import BASS_Init
from pybass import BASS_SYNC_END
from pybass import BASS_StreamCreateFile
from pybass import SYNCPROC
from pybass import play_handle


@SYNCPROC
def onEndPlay(handle, buffer, length, user):
    print("playing finished.")


if __name__ == '__main__':
    BASS_Init(-1, 44100, 0, 0, 0)
    handle = BASS_StreamCreateFile(False, b'test.mp3', 0, 0, 0)
    BASS_ChannelSetSync(handle, BASS_SYNC_END, 0, onEndPlay, 0)
    play_handle(handle, False)
    BASS_Free()
