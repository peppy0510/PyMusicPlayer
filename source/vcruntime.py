# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


# Imported first by main.pyw for its side effect. wxPython wheels load MSVCP140.dll without
# shipping it, so a source run on a PC without the Visual C++ Redistributable dies on
# `import wx`. A frozen build carries its own copy and skips this.

import ctypes
import os
import sys
import sysconfig
import tempfile
import urllib.error
import urllib.request

from ctypes import wintypes


# MSVCP140 before 14.40 crashes code built with Visual Studio 2022 17.10 or later
MINIMUM_VERSION = (14, 40)
REDIST_URL = 'https://aka.ms/vc14/vc_redist.{}.exe'
REDIST_PAGE = 'https://learn.microsoft.com/cpp/windows/latest-supported-vc-redist'

MB_YESNO = 0x04
MB_ICONERROR = 0x10
MB_ICONWARNING = 0x30
IDYES = 6
SEE_MASK_NOCLOSEPROCESS = 0x40
INFINITE = 0xFFFFFFFF

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
version = ctypes.WinDLL('version')
version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, wintypes.LPDWORD]
version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                        ctypes.c_void_p]
version.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                   ctypes.POINTER(ctypes.c_void_p),
                                   ctypes.POINTER(wintypes.UINT)]


class VS_FIXEDFILEINFO(ctypes.Structure):
    _fields_ = [
        ('dwSignature', wintypes.DWORD),
        ('dwStrucVersion', wintypes.DWORD),
        ('dwFileVersionMS', wintypes.DWORD),
        ('dwFileVersionLS', wintypes.DWORD),
    ]


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('fMask', wintypes.ULONG),
        ('hwnd', wintypes.HWND),
        ('lpVerb', wintypes.LPCWSTR),
        ('lpFile', wintypes.LPCWSTR),
        ('lpParameters', wintypes.LPCWSTR),
        ('lpDirectory', wintypes.LPCWSTR),
        ('nShow', ctypes.c_int),
        ('hInstApp', wintypes.HINSTANCE),
        ('lpIDList', ctypes.c_void_p),
        ('lpClass', wintypes.LPCWSTR),
        ('hkeyClass', wintypes.HKEY),
        ('dwHotKey', wintypes.DWORD),
        ('hIconOrMonitor', wintypes.HANDLE),
        ('hProcess', wintypes.HANDLE),
    ]


def get_app_name():
    # main.pyw sits in <repository>\source
    return os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0]))))


def get_file_version(path):
    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        return ()
    data = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, data):
        return ()
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(data, '\\', ctypes.byref(pointer), ctypes.byref(length)):
        return ()
    info = ctypes.cast(pointer, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    return (info.dwFileVersionMS >> 16, info.dwFileVersionMS & 0xFFFF)


def get_runtime_version():
    # read the file rather than load it, so a newer copy installed below is seen in this process
    path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'msvcp140.dll')
    if not os.path.isfile(path):
        return ()
    return get_file_version(path)


def run_elevated(path, parameters):
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = 'runas'
    info.lpFile = path
    info.lpParameters = parameters
    info.nShow = 1
    # fails with ERROR_CANCELLED when the UAC prompt is declined
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        return False
    kernel32.WaitForSingleObject(info.hProcess, INFINITE)
    kernel32.CloseHandle(info.hProcess)
    return True


def install_runtime():
    architecture = 'arm64' if sysconfig.get_platform().endswith('arm64') else 'x64'
    path = os.path.join(tempfile.gettempdir(), f'vc_redist.{architecture}.exe')
    urllib.request.urlretrieve(REDIST_URL.format(architecture), path)
    try:
        return run_elevated(path, '/install /passive /norestart')
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def ensure_runtime():
    if getattr(sys, 'frozen', False) or get_runtime_version() >= MINIMUM_VERSION:
        return
    name = get_app_name()
    message_box = ctypes.windll.user32.MessageBoxW
    text = (f'{name} needs the Microsoft Visual C++ Redistributable, which is missing or too old '
            f'on this PC.\n\nDownload it from Microsoft (about 20 MB) and install it now?')
    if message_box(None, text, name, MB_YESNO | MB_ICONWARNING) != IDYES:
        # let it try anyway; a runtime somewhere other than System32 may still serve wx
        return
    try:
        install_runtime()
    except (OSError, urllib.error.URLError):
        pass
    if get_runtime_version() < MINIMUM_VERSION:
        message_box(None, f'The Microsoft Visual C++ Redistributable was not installed.\n\n'
                    f'Install it from {REDIST_PAGE} and start {name} again.', name, MB_ICONERROR)
        sys.exit(1)


ensure_runtime()
