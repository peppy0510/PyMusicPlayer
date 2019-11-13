# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import os
import pywintypes  # noqa # pre-load dll for win32com

from win32com.client import Dispatch


class ShortCut():

    @classmethod
    def get_user_path(self):
        return os.path.expanduser('~')

    @classmethod
    def get_user_startmenu_path(self, name=None):
        path = os.path.join(self.get_user_path(), 'AppData',
                            'Roaming', 'Microsoft', 'Windows', 'Start Menu')
        if not name:
            return path
        if not name.lower().endswith('.lnk'):
            name = '{}.lnk'.format(name)
        return os.path.join(path, name)

    @classmethod
    def get_user_startup_path(self, name=None):
        path = os.path.join(self.get_user_startmenu_path(), 'Programs', 'Startup')
        if not name:
            return path
        if not name.lower().endswith('.lnk'):
            name = '{}.lnk'.format(name)
        return os.path.join(path, name)

    @classmethod
    def has_user_startup(self, name):
        path = self.get_user_startup_path(name)
        return os.path.exists(path)

    @classmethod
    def remove_user_startup(self, name):
        path = self.get_user_startup_path(name)
        if os.path.exists(path):
            os.remove(path)

    @classmethod
    def create(self, path, target_path='', arguments='', working_directory='', icon=''):
        ext = os.path.splitext(path)[-1][1:].lower()
        if ext == 'url':
            with open(path, 'w') as file:
                file.write('[InternetShortcut]\nURL=%s' % target_path)
        else:
            shell = Dispatch('WScript.Shell')

            shortcut = shell.CreateShortCut(
                path if path.endswith('.lnk') else '.'.join([path, 'lnk']))
            # shortcut.WindowStyle = 1
            shortcut.Arguments = arguments
            shortcut.Targetpath = target_path
            shortcut.WorkingDirectory = working_directory
            if icon:
                shortcut.IconLocation = icon
            shortcut.save()
        # print('[ SHORTCUT CREATED ] [ {} ]'.format(path))


def create_shortcut(*args, **kwargs):
    ShortCut.create(*args, **kwargs)


def create_desktop_ini(directory, icon_resource, folder_type='Generic'):
    with open(os.path.join(directory, 'desktop.ini'), 'w') as file:
        file.write('\n'.join([
            '[.ShellClassInfo]', 'IconResource=%s,0' % icon_resource,
            '[ViewState]', 'Mode=', 'Vid=', 'FolderType=%s' % folder_type]))
