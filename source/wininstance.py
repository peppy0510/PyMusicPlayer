# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import os
import psutil
import sys


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
    relcwd = os.path.dirname(p.cmdline()[-1])
    return os.path.join(p.cwd(), relcwd).rstrip(' ' + os.path.sep)


def get_current_real_cwq():
    cp = get_current_process()
    return get_real_cwd(cp)


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
