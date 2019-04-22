# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license


__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pybassasio.py - is ctypes python module for BASSASIO (http://www.un4seen.com).

BASSASIO is basically a wrapper for ASIO drivers, with the addition of channel
joining, format conversion and resampling.

Requirements
============
BASSASIO requires a soundcard with ASIO drivers installed. It also makes use
of SSE and 3DNow optimizations, but is fully functional without them.

The BASS library is not required by BASSASIO, but BASS can of course be used
for decoding purposes, to apply DSP/FX, etc...
'''


import ctypes


try:
    import bass
except ImportError:
    from .import bass


bassasio_module, func_type = bass.load(__file__)


BASSASIOVERSION = 0x100


# error codes returned by BASS_ASIO_ErrorGetCode
error_descriptions = {}
BASS_OK = 0
error_descriptions[BASS_OK] = 'all is OK'
BASS_ERROR_DRIVER = 3
error_descriptions[BASS_ERROR_DRIVER] = "can't find a free/valid driver"
BASS_ERROR_FORMAT = 6
error_descriptions[BASS_ERROR_FORMAT] = 'unsupported sample format'
BASS_ERROR_INIT = 8
error_descriptions[BASS_ERROR_INIT] = 'BASS_ASIO_Init has not been successfully called'
BASS_ERROR_START = 9
error_descriptions[BASS_ERROR_START] = "BASS_ASIO_Start has/hasn't been called"
BASS_ERROR_ALREADY = 14
error_descriptions[BASS_ERROR_ALREADY] = 'already initialized/started'
BASS_ERROR_NOCHAN = 18
error_descriptions[BASS_ERROR_NOCHAN] = 'no channels are enabled'
BASS_ERROR_ILLPARAM = 20
error_descriptions[BASS_ERROR_ILLPARAM] = 'an illegal parameter was specified'
BASS_ERROR_DEVICE = 23
error_descriptions[BASS_ERROR_DEVICE] = 'illegal device number'
BASS_ERROR_NOTAVAIL = 37
error_descriptions[BASS_ERROR_NOTAVAIL] = 'not available'
BASS_ERROR_UNKNOWN = -1
error_descriptions[BASS_ERROR_UNKNOWN] = 'some other mystery problem'


def get_error_description(error_code=-1):
    return error_descriptions.get(error_code, 'unknown BASS error code ' + str(error_code))


# device info structure
class BASS_ASIO_DEVICEINFO(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char_p),  # const char *name;//  description
                ('driver', ctypes.c_char_p)  # const char *driver;// driver
                ]


class BASS_ASIO_INFO(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char * 32),  # char name[32];// driver name
        ('version', ctypes.c_ulong),  # DWORD version;// driver version
        ('inputs', ctypes.c_ulong),  # DWORD inputs;// number of inputs
        ('outputs', ctypes.c_ulong),  # DWORD outputs;// number of outputs
        ('bufmin', ctypes.c_ulong),  # DWORD bufmin;// minimum buffer length
        ('bufmax', ctypes.c_ulong),  # DWORD bufmax;// maximum buffer length
        ('bufpref', ctypes.c_ulong),  # DWORD bufpref;// preferred/default buffer length
        ('bufgran', ctypes.c_int)  # int bufgran;// buffer length granularity
    ]


class BASS_ASIO_CHANNELINFO(ctypes.Structure):
    _fields_ = [
        ('group', ctypes.c_ulong),  # DWORD group;
        ('format', ctypes.c_ulong),  # DWORD format;// sample format (BASS_ASIO_FORMAT_xxx)
        ('name', ctypes.c_char * 32)  # char name[32];// channel name
    ]


# sample formats
BASS_ASIO_FORMAT_16BIT = 16  # 16-bit integer
BASS_ASIO_FORMAT_24BIT = 17  # 24-bit integer
BASS_ASIO_FORMAT_32BIT = 18  # 32-bit integer
BASS_ASIO_FORMAT_FLOAT = 19  # 32-bit floating-point


# BASS_ASIO_ChannelReset flags
BASS_ASIO_RESET_ENABLE = 1  # disable channel
BASS_ASIO_RESET_JOIN = 2  # unjoin channel
BASS_ASIO_RESET_PAUSE = 4  # unpause channel
BASS_ASIO_RESET_FORMAT = 8  # reset sample format to native format
BASS_ASIO_RESET_RATE = 16  # reset sample rate to device rate
BASS_ASIO_RESET_VOLUME = 32  # reset volume to 1.0


# BASS_ASIO_ChannelIsActive return values
BASS_ASIO_ACTIVE_DISABLED = 0
BASS_ASIO_ACTIVE_ENABLED = 1
BASS_ASIO_ACTIVE_PAUSED = 2


# typedef DWORD (CALLBACK ASIOPROC)(
# BOOL input, DWORD channel, void *buffer, DWORD length, void *user);
ASIOPROC = func_type(
    ctypes.c_ulong, ctypes.c_byte, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p
)
# ASIO channel callback function.
# input  : Input? else output
# channel: Channel number
# buffer : Buffer containing the sample data
# length : Number of bytes
# user   : The 'user' parameter given when calling BASS_ASIO_ChannelEnable
# RETURN : The number of bytes written (ignored with input channels)


# typedef void (CALLBACK ASIONOTIFYPROC)(
# DWORD notify, void *user);
ASIONOTIFYPROC = func_type(
    None, ctypes.c_ulong, ctypes.c_void_p
)
# Driver notification callback function.
# notify : The notification (BASS_ASIO_NOTIFY_xxx)
# user   : The 'user' parameter given when calling BASS_ASIO_SetNotify


# driver notifications
BASS_ASIO_NOTIFY_RATE = 1  # sample rate change
BASS_ASIO_NOTIFY_RESET = 2  # reset (reinitialization) request

# DWORD BASSASIODEF(BASS_ASIO_GetVersion)();
BASS_ASIO_GetVersion = func_type(
    ctypes.c_ulong
)(('BASS_ASIO_GetVersion', bassasio_module))


# DWORD BASSASIODEF(BASS_ASIO_ErrorGetCode)();
BASS_ASIO_ErrorGetCode = func_type(
    ctypes.c_ulong
)(('BASS_ASIO_ErrorGetCode', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_GetDeviceInfo)(
# DWORD device, BASS_ASIO_DEVICEINFO *info);
BASS_ASIO_GetDeviceInfo = func_type(
    ctypes.c_byte, ctypes.c_ulong, ctypes.POINTER(BASS_ASIO_DEVICEINFO)
)(('BASS_ASIO_GetDeviceInfo', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_SetDevice)(
# DWORD device);
BASS_ASIO_SetDevice = func_type(
    ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_SetDevice', bassasio_module))


# DWORD BASSASIODEF(BASS_ASIO_GetDevice)();
BASS_ASIO_GetDevice = func_type(
    ctypes.c_ulong
)(('BASS_ASIO_GetDevice', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_Init)(
# DWORD device);
BASS_ASIO_Init = func_type(
    ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_Init', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_Free)();
BASS_ASIO_Free = func_type(
    ctypes.c_byte
)(('BASS_ASIO_Free', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_SetNotify)(
# ASIONOTIFYPROC *proc, void *user);
BASS_ASIO_SetNotify = func_type(
    ctypes.c_byte, ASIONOTIFYPROC, ctypes.c_void_p
)(('BASS_ASIO_SetNotify', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ControlPanel)();
BASS_ASIO_ControlPanel = func_type(
    ctypes.c_byte
)(('BASS_ASIO_ControlPanel', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_GetInfo)(
# BASS_ASIO_INFO *info);
BASS_ASIO_GetInfo = func_type(
    ctypes.c_byte, ctypes.POINTER(BASS_ASIO_INFO)
)(('BASS_ASIO_GetInfo', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_SetRate)(
# double rate);
BASS_ASIO_SetRate = func_type(
    ctypes.c_byte, ctypes.c_double
)(('BASS_ASIO_SetRate', bassasio_module))


# double BASSASIODEF(BASS_ASIO_GetRate)();
BASS_ASIO_GetRate = func_type(
    ctypes.c_double
)(('BASS_ASIO_GetRate', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_Start)(
# DWORD buflen);
BASS_ASIO_Start = func_type(
    ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_Start', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_Stop)();
BASS_ASIO_Stop = func_type(
    ctypes.c_byte
)(('BASS_ASIO_Stop', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_IsStarted)();
BASS_ASIO_IsStarted = func_type(
    ctypes.c_byte
)(('BASS_ASIO_IsStarted', bassasio_module))


# DWORD BASSASIODEF(BASS_ASIO_GetLatency)(
# BOOL input);
BASS_ASIO_GetLatency = func_type(
    ctypes.c_ulong, ctypes.c_byte
)(('BASS_ASIO_GetLatency', bassasio_module))


# float BASSASIODEF(BASS_ASIO_GetCPU)();
BASS_ASIO_GetCPU = func_type(
    ctypes.c_float
)(('BASS_ASIO_GetCPU', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_Monitor)(
# int input, DWORD output, DWORD gain, DWORD state, DWORD pan);
BASS_ASIO_Monitor = func_type(
    ctypes.c_byte, ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_ASIO_Monitor', bassasio_module))

# BOOL BASSASIODEF(BASS_ASIO_ChannelGetInfo)(
# BOOL input, DWORD channel, BASS_ASIO_CHANNELINFO *info);
BASS_ASIO_ChannelGetInfo = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.POINTER(BASS_ASIO_CHANNELINFO)
)(('BASS_ASIO_ChannelGetInfo', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelReset)(
# BOOL input, int channel, DWORD flags);
BASS_ASIO_ChannelReset = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_int, ctypes.c_ulong
)(('BASS_ASIO_ChannelReset', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelEnable)(
# BOOL input, DWORD channel, ASIOPROC *proc, void *user);
BASS_ASIO_ChannelEnable = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ASIOPROC, ctypes.c_void_p
)(('BASS_ASIO_ChannelEnable', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelEnableMirror)(
# DWORD channel, BOOL input2, DWORD channel2);
BASS_ASIO_ChannelEnableMirror = func_type(
    ctypes.c_byte, ctypes.c_ulong, ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_ChannelEnableMirror', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelJoin)(
# BOOL input, DWORD channel, int channel2);
BASS_ASIO_ChannelJoin = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.c_int
)(('BASS_ASIO_ChannelJoin', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelPause)(
# BOOL input, DWORD channel);
BASS_ASIO_ChannelPause = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_ChannelPause', bassasio_module))


# DWORD BASSASIODEF(BASS_ASIO_ChannelIsActive)(
# BOOL input, DWORD channel);
BASS_ASIO_ChannelIsActive = func_type(
    ctypes.c_ulong, ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_ChannelIsActive', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelSetFormat)(
# BOOL input, DWORD channel, DWORD format);
BASS_ASIO_ChannelSetFormat = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.c_ulong
)(('BASS_ASIO_ChannelSetFormat', bassasio_module))


# DWORD BASSASIODEF(BASS_ASIO_ChannelGetFormat)(
# BOOL input, DWORD channel);
BASS_ASIO_ChannelGetFormat = func_type(
    ctypes.c_ulong, ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_ChannelGetFormat', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelSetRate)(
# BOOL input, DWORD channel, double rate);
BASS_ASIO_ChannelSetRate = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.c_double
)(('BASS_ASIO_ChannelSetRate', bassasio_module))


# double BASSASIODEF(BASS_ASIO_ChannelGetRate)(
# BOOL input, DWORD channel);
BASS_ASIO_ChannelGetRate = func_type(
    ctypes.c_double, ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_ChannelGetRate', bassasio_module))


# BOOL BASSASIODEF(BASS_ASIO_ChannelSetVolume)(
# BOOL input, int channel, float volume);
BASS_ASIO_ChannelSetVolume = func_type(
    ctypes.c_byte, ctypes.c_byte, ctypes.c_int, ctypes.c_float
)(('BASS_ASIO_ChannelSetVolume', bassasio_module))


# float BASSASIODEF(BASS_ASIO_ChannelGetVolume)(
# BOOL input, int channel);
BASS_ASIO_ChannelGetVolume = func_type(
    ctypes.c_float, ctypes.c_byte, ctypes.c_int
)(('BASS_ASIO_ChannelGetVolume', bassasio_module))


# float BASSASIODEF(BASS_ASIO_ChannelGetLevel)(
# BOOL input, DWORD channel);
BASS_ASIO_ChannelGetLevel = func_type(
    ctypes.c_float, ctypes.c_byte, ctypes.c_ulong
)(('BASS_ASIO_ChannelGetLevel', bassasio_module))


if __name__ == '__main__':
    print('BASSASIO implemented Version %X' % BASSASIOVERSION)
    print('BASSASIO real Version %X' % BASS_ASIO_GetVersion())
    if not BASS_ASIO_Init(0):
        print('BASS_ASIO_Init error %s' % get_error_description(BASS_ASIO_ErrorGetCode()))
    else:
        if not BASS_ASIO_Free():
            print('BASS_ASIO_Free error %s' % get_error_description(BASS_ASIO_ErrorGetCode()))
