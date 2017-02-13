# Copyright(c) Max Kolosov 2009 maxkolosov@inbox.ru
# http://vosolok2008.narod.ru
# BSD license

__version__ = '0.2'
__versionTime__ = '2013-01-22'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'
__doc__ = '''
pytags.py - is ctypes python module for
TAGS (Another Tags Reading Library written by Wraith).

BASS audio library has limited support for reading tags, associated with a
stream. This library extends that functionality, allowing developer/user to
extract specific song information from the stream handle used with BASS. The
extracted tag values are formatted into text ouput according to given format
string (including conditional processing).

Supported tags:
---------------
  MP3 ID3v1 and ID3v2.2/3/4
  OGG/FLAC comments
  WMA
  APE, OFR, MPC, AAC - all use APE tags
  MP4
  MOD/etc titles
'''

import sys, ctypes, platform

if platform.system().lower() == 'windows':
	tags_module = ctypes.WinDLL('tags')
	func_type = ctypes.WINFUNCTYPE
else:
	tags_module = ctypes.CDLL('tags')
	func_type = ctypes.CFUNCTYPE

# Current version. Just increments each release.
TAGS_VERSION = 15

# returns description of the last error.
#const char*  _stdcall TAGS_GetLastErrorDesc();
TAGS_GetLastErrorDesc = func_type(ctypes.c_char_p)(('TAGS_GetLastErrorDesc', tags_module))

# main purpose of this library
#const char*  _stdcall TAGS_Read( DWORD dwHandle, const char* fmt );
TAGS_Read = func_type(ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)(('TAGS_Read', tags_module))

# retrieves the current version
#DWORD _stdcall TAGS_GetVersion();
TAGS_GetVersion = func_type(ctypes.c_ulong)(('TAGS_GetVersion', tags_module))


if __name__ == "__main__":
	print('TAGS implemented Version %d' % TAGS_VERSION)
	print('TAGS real Version %X' % TAGS_GetVersion())
	import pybass
	if not pybass.BASS_Init(-1, 44100, 0, 0, 0):
		print('BASS_Init error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
	else:
		handle = pybass.BASS_StreamCreateFile(False, b'test.ogg', 0, 0, 0)
		if handle == 0:
			print('BASS_StreamCreateFile error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
		else:
			fmt = '%IFV1(%ITRM(%TRCK),%ITRM(%TRCK). )%IFV2(%ITRM(%ARTI),%ICAP(%ITRM(%ARTI)),no artist) - %IFV2(%ITRM(%TITL),%ICAP(%ITRM(%TITL)),no title)%IFV1(%ITRM(%ALBM), - %IUPC(%ITRM(%ALBM)))%IFV1(%YEAR, %(%YEAR%))%IFV1(%ITRM(%GNRE), {%ITRM(%GNRE)})%IFV1(%ITRM(%CMNT), [%ITRM(%CMNT)])'
			tags = TAGS_Read(handle, fmt)
			print(tags)
			if not pybass.BASS_StreamFree(handle):
				print('BASS_StreamFree error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
		if not pybass.BASS_Free():
			print('BASS_Free error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
