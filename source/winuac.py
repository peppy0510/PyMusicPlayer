# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import ctypes
import sys
import winreg


CMD = 'C:\\Windows\\System32\\cmd.exe'
FOD_HELPER = 'C:\\Windows\\System32\\fodhelper.exe'
PYTHON_CMD = 'python'
REG_PATH = 'Software\\Classes\\ms-settings\\shell\\open\\command'
DELEGATE_EXEC_REG_KEY = 'DelegateExecute'


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def create_reg_key(key, value):
    '''
    Creates a reg key
    '''
    try:
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(registry_key, key, 0, winreg.REG_SZ, value)
        winreg.CloseKey(registry_key)
    except WindowsError:
        raise


def bypass_uac(cmd):
    '''
    Tries to bypass the UAC
    '''
    try:
        create_reg_key(DELEGATE_EXEC_REG_KEY, '')
        create_reg_key(None, cmd)
    except WindowsError:
        raise


def run_as_admin(callback, file, try_run_as_admin=True):
    if try_run_as_admin is False or is_admin():
        callback()
    else:
        print(sys.executable)
        create_reg_key(DELEGATE_EXEC_REG_KEY, '')

        # cwd = os.path.dirname(os.path.realpath(file))
        # command = '{} /k {} {}'.format(sys.executable, file, cwd)
        # command = '{} /k {}'.format(sys.executable, file)
        # create_reg_key(None, command)
        # create_reg_key(None, cmd)
        # Rerun with admin rights
        # try:
        #     current_dir = os.path.dirname(os.path.realpath(__file__)) + '\\' + __file__
        #     cmd = '{} /k {} {}'.format(CMD, PYTHON_CMD, current_dir)
        #     bypass_uac(cmd)
        #     os.system(FOD_HELPER)
        #     sys.exit(0)
        # except WindowsError:
        #     sys.exit(1)

        ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, file, None, 1)
