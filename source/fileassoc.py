# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import ctypes
import os
import sys
import winreg

from ctypes import wintypes


APP_NAME = 'PyMusicPlayer'
APP_DESCRIPTION = 'Music player with waveform, tempo and key analysis'
CLASSES = 'Software\\Classes'
CAPABILITIES_ROOT = f'Software\\{APP_NAME}'
CAPABILITIES = f'{CAPABILITIES_ROOT}\\Capabilities'
REGISTERED_APPLICATIONS = 'Software\\RegisteredApplications'
# Windows lets only the user change a default; a new registration may land on the page
# before it, which still has Set a default for a file type
SETTINGS_PAGE = f'ms-settings:defaultapps?registeredAppUser={APP_NAME}'

# what the player decodes and is music: not mp4, webm (video), ape (no decoder)
FILE_TYPES = (
    ('mp3', 'MP3 Audio'),
    ('flac', 'FLAC Audio'),
    ('wav', 'WAV Audio'),
    ('m4a', 'MPEG-4 Audio'),
    ('aac', 'AAC Audio'),
    ('ogg', 'Ogg Vorbis Audio'),
    ('wma', 'Windows Media Audio'),
    ('aiff', 'AIFF Audio'),
    ('ac3', 'Dolby Digital Audio'),
    ('mp2', 'MPEG Layer II Audio'),
    ('m3u', 'M3U Playlist'),
)
# (folder in assets/icon/filetypes, name)
ICON_STYLES = (('', 'Color'), ('light', 'Light'))

ASSOCSTR_FRIENDLYAPPNAME = 4
ASSOCSTR_PROGID = 20
SHCNE_ASSOCCHANGED = 0x08000000
SHCNF_IDLIST = 0


def get_prog_id(ext):
    return f'{APP_NAME}.{ext}'


def get_root_path():
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_icon():
    return os.path.join(get_root_path(), 'assets', 'icon', 'icon.ico')


def get_file_icon(ext, style=''):
    return os.path.join(get_root_path(), 'assets', 'icon', 'filetypes', style, f'{ext}.ico')


def get_open_command():
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}" "%1"'
    python = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    if os.path.exists(python) is False:
        python = sys.executable
    script = os.path.join(get_root_path(), 'source', 'main.pyw')
    return f'"{python}" "{script}" "%1"'


def set_value(path, name, value):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)


def delete_value(path, name):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass


def delete_tree(path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            names = []
            while True:
                try:
                    names.append(winreg.EnumKey(key, len(names)))
                except OSError:
                    break
    except FileNotFoundError:
        return
    for name in names:
        delete_tree(f'{path}\\{name}')
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


def notify_shell():
    ctypes.windll.shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, SHCNF_IDLIST, None, None)


def get_icon_value(ext, icons, style=''):
    path = (icons or {}).get(ext)
    if path is None or os.path.exists(path) is False:
        path = get_file_icon(ext, style)
    return f'{path},0'


def register(icons=None, style=''):
    '''this user's keys only: needs no elevation, wins over the machine's'''
    command = get_open_command()
    set_value(CAPABILITIES, 'ApplicationName', APP_NAME)
    set_value(CAPABILITIES, 'ApplicationDescription', APP_DESCRIPTION)
    set_value(CAPABILITIES, 'ApplicationIcon', f'{get_app_icon()},0')
    for ext, name in FILE_TYPES:
        prog_id = get_prog_id(ext)
        path = f'{CLASSES}\\{prog_id}'
        set_value(path, '', name)
        set_value(f'{path}\\DefaultIcon', '', get_icon_value(ext, icons, style))
        # Settings would call a source run Python
        set_value(f'{path}\\Application', 'ApplicationName', APP_NAME)
        set_value(f'{path}\\Application', 'ApplicationIcon', f'{get_app_icon()},0')
        set_value(f'{path}\\shell', '', 'open')
        set_value(f'{path}\\shell\\open', '', 'Play')
        set_value(f'{path}\\shell\\open', 'Icon', f'{get_app_icon()},0')
        set_value(f'{path}\\shell\\open', 'FriendlyAppName', APP_NAME)
        set_value(f'{path}\\shell\\open\\command', '', command)
        set_value(f'{CLASSES}\\.{ext}\\OpenWithProgids', prog_id, '')
        set_value(f'{CAPABILITIES}\\FileAssociations', f'.{ext}', prog_id)
    set_value(REGISTERED_APPLICATIONS, APP_NAME, CAPABILITIES)
    notify_shell()


def unregister():
    delete_value(REGISTERED_APPLICATIONS, APP_NAME)
    delete_tree(CAPABILITIES_ROOT)
    for ext, name in FILE_TYPES:
        delete_tree(f'{CLASSES}\\{get_prog_id(ext)}')
        delete_value(f'{CLASSES}\\.{ext}\\OpenWithProgids', get_prog_id(ext))
    notify_shell()


def is_registered():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTERED_APPLICATIONS) as key:
            winreg.QueryValueEx(key, APP_NAME)
    except FileNotFoundError:
        return False
    return True


def query_association(kind, ext):
    # the shell's own answer: UserChoice moved to UserChoiceLatest on newer builds
    query = ctypes.windll.shlwapi.AssocQueryStringW
    query.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                      wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    query.restype = ctypes.c_long
    size = wintypes.DWORD(512)
    value = ctypes.create_unicode_buffer(size.value)
    if query(0, kind, f'.{ext}', None, value, ctypes.byref(size)) != 0:
        return None
    return value.value


def is_default(ext):
    return query_association(ASSOCSTR_PROGID, ext) == get_prog_id(ext)


def get_default_name(ext):
    return query_association(ASSOCSTR_FRIENDLYAPPNAME, ext)


def open_default_apps():
    os.startfile(SETTINGS_PAGE)
