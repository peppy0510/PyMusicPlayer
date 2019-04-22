# Copyright(c) Maxim Kolosov 2011 pyirrlicht@gmail.com
# http://pybass.sf.net
# BSD license


import ctypes

from pybass import BASS_ChannelSetFX
from pybass import BASS_DX8_REVERB
from pybass import BASS_ErrorGetCode
from pybass import BASS_FXGetParameters
from pybass import BASS_FXSetParameters
from pybass import BASS_FX_DX8_REVERB
from pybass import BASS_Free
from pybass import BASS_Init
from pybass import BASS_StreamCreateFile
from pybass import get_error_description


def print_params(params):
    print('fInGain %f' % params.fInGain)
    print('fReverbMix %f' % params.fReverbMix)
    print('fReverbTime %f' % params.fReverbTime)
    print('fHighFreqRTRatio %f' % params.fHighFreqRTRatio)


if not BASS_Init(-1, 44100, 0, 0, 0):
    print('BASS_Init error %s' % get_error_description(BASS_ErrorGetCode()))
else:
    channelHandle = BASS_StreamCreateFile(False, 'test.ogg', 0, 0, 0)
    DX8_effect_handle = BASS_ChannelSetFX(channelHandle, BASS_FX_DX8_REVERB, 0)
    print('DX8 effect handle %d' % DX8_effect_handle)
    params = BASS_DX8_REVERB()
    print_params(params)
    params.fInGain = -95
    params.fReverbMix = -95
    params.fReverbTime = 2999
    params.fHighFreqRTRatio = 0.998
    result_BASS_FXSetParameters = BASS_FXSetParameters(DX8_effect_handle, ctypes.pointer(params))
    print('result BASS_FXSetParameters %d' % result_BASS_FXSetParameters)
    result_BASS_FXGetParameters = BASS_FXGetParameters(DX8_effect_handle, ctypes.pointer(params))
    print('result BASS_FXGetParameters %d' % result_BASS_FXGetParameters)
    print_params(params)
    if not BASS_Free():
        print('BASS_Free error %s' % get_error_description(BASS_ErrorGetCode()))
