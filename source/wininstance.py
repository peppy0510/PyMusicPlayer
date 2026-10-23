# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import json
import os
import psutil
import sys
from pathlib import Path


def has_process_authority(p):
    try:
        p.cwd()
        p.name()
    except Exception:
        return False
    return True


def get_current_process():
    pid = int(os.getpid())
    for p in psutil.process_iter():
        if p.pid == pid and has_process_authority(p):
            return p


def get_real_cwd(p):
    # return str(Path('.').resolve().parent.joinpath('source'))
    return str(Path(__file__).resolve().parent.parent.joinpath('source'))

    cmdline = p.cmdline()
    split = len(cmdline)
    for i in range(len(cmdline)):
        if cmdline[i].startswith('-'):
            split = i
            break
    cmdline = cmdline[:split]
    relcwd = os.path.dirname(cmdline[-1])
    return os.path.join(p.cwd(), relcwd).rstrip(' ' + os.path.sep)


def get_current_real_cwd():
    cp = get_current_process()
    return get_real_cwd(cp)


def has_running_instance():
    pid = int(os.getpid())
    cp = get_current_process()
    cpname = cp.name()
    cpcwd = get_real_cwd(cp)
    # a venv launches through Scripts\python.exe, which shares our name and cwd
    ancestors = {p.pid for p in cp.parents()}

    for p in psutil.process_iter():
        if p.pid == pid or p.pid in ancestors or not has_process_authority(p):
            continue

        if hasattr(sys, '_MEIPASS'):
            if cpname == p.name():
                return True
        else:
            if p.name().lower() not in ('python.exe', 'pythonw.exe',):
                continue
            print(p.cmdline())
            # if cpcwd == get_real_cwd(p):
            if [True for v in p.cmdline() if v.startswith(cpcwd)]:
                print(cpcwd)
                # which process it was (main.pyw logs it): truthy as before
                return 'pid %d %s' % (p.pid, ' '.join(p.cmdline()))

    return False


def kill_existing_instances():
    pid = int(os.getpid())
    cp = get_current_process()
    cpname = cp.name()
    cpcwd = get_real_cwd(cp)

    for p in psutil.process_iter():
        if p.pid == pid or not has_process_authority(p):
            continue

        if hasattr(sys, '_MEIPASS'):
            if cpname == p.name():
                p.terminate()
        else:
            if p.name().lower() not in ('python.exe', 'pythonw.exe',):
                continue
            if cpcwd == get_real_cwd(p):
                p.terminate()
            # only SIGTERM, CTRL_C_EVENT, CTRL_BREAK_EVENT signals on Windows Platform.
            # p.send_signal(signal.SIGTERM)


def get_instance_file_path():
    from utilities import get_user_docapp_path
    return os.path.join(get_user_docapp_path(), 'instance.json')


def read_instance_port():
    try:
        with open(get_instance_file_path(), 'r') as file:
            data = json.loads(file.read())
        if psutil.pid_exists(int(data['pid'])) is False:
            return None
        return int(data['port'])
    except Exception:
        return None


def write_instance_port(port):
    data = {'pid': os.getpid(), 'port': int(port)}
    try:
        with open(get_instance_file_path(), 'w') as file:
            file.write(json.dumps(data))
    except Exception:
        pass


def clear_instance_port():
    try:
        os.remove(get_instance_file_path())
    except Exception:
        pass


# a test's launch (TEST_PLACE set in its environment: the agent's restarts): its window on
# the second virtual desktop, in the leftmost monitor's lower half, out of the user's way

TEST_PLACE = 'PYMP_TEST_PLACE'
TEST_DESKTOP = 2
VIRTUAL_DESKTOPS = r'Software\Microsoft\Windows\CurrentVersion\Explorer\VirtualDesktops'
# IVirtualDesktopManager (shobjidl): a window of its own process moved to a desktop
DESKTOP_MANAGER = '{aa509086-5ca9-4c25-8f95-589d3c07b48a}'
DESKTOP_MANAGER_IID = '{a5cd92ff-29be-454c-8d04-d82879fb3f1b}'


# a launch put on a virtual desktop (its number) where it would be anyway (the user's
# place): the agent's last restart, its tests done, back on the user's desktop
HOME_DESKTOP = 'PYMP_DESKTOP'


def is_test_launch():
    return bool(os.environ.get(TEST_PLACE))


def get_launch_desktop():
    try:
        return int(os.environ.get(HOME_DESKTOP, '0')) or None
    except ValueError:
        return None


def move_to_virtual_desktop(hwnd, number):
    '''a window of this process onto a virtual desktop (1 the first, as the task view
    numbers them); False when there is no such desktop or it could not'''
    import ctypes
    import winreg
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                    ('Data3', wintypes.WORD), ('Data4', ctypes.c_ubyte * 8)]

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, VIRTUAL_DESKTOPS) as key:
            ids = winreg.QueryValueEx(key, 'VirtualDesktopIDs')[0]
    except OSError:
        return False
    if len(ids) < number * 16:
        return False
    desktop = GUID.from_buffer_copy(ids[(number - 1) * 16:number * 16])
    ole32 = ctypes.OleDLL('ole32')
    clsid, iid = GUID(), GUID()
    ole32.CLSIDFromString(DESKTOP_MANAGER, ctypes.byref(clsid))
    ole32.CLSIDFromString(DESKTOP_MANAGER_IID, ctypes.byref(iid))
    manager = ctypes.c_void_p()
    try:
        ole32.CoCreateInstance(ctypes.byref(clsid), None, 0x17, ctypes.byref(iid),
                               ctypes.byref(manager))
    except OSError:
        return False
    table = ctypes.cast(manager, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    # (IUnknown's three, IsWindowOnCurrentVirtualDesktop, GetWindowDesktopId, then it)
    move = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, wintypes.HWND,
                              ctypes.POINTER(GUID))(table[5])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[2])
    result = move(manager, hwnd, ctypes.byref(desktop))
    release(manager)
    return result == 0
