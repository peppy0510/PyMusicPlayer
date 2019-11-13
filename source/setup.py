# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import os

from shortcut import create_desktop_ini
from shortcut import create_shortcut


def main():
    # C:\Users\username\AppData\Roaming\Microsoft\Windows\Start Menu
    # C:\Users\username\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup

    python_path = 'pythonw.exe'
    shortcut_name = 'PyMusicPlayer'
    cwd = os.path.abspath(os.path.dirname(__file__))
    target_path = os.path.join(cwd, 'main.pyw')
    rootpath = os.path.dirname(cwd)
    home = os.path.expanduser('~')
    icon = os.path.join(rootpath, 'assets', 'icon', 'icon.ico')
    startmenu = os.path.join(home, 'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu')

    create_shortcut(
        os.path.join(startmenu, shortcut_name),
        python_path, target_path, cwd, icon)

    create_desktop_ini(os.path.dirname(cwd), icon)


if __name__ == '__main__':
    main()
