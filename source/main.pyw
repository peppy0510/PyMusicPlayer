# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import argparse
import json
import socket

from pathlib import Path
from wininstance import has_running_instance


MAIN_SOCKET_PORT = 55557


def launch(filepath=None):
    from mainapp import launch_mainapp
    try:
        launch_mainapp(filepath)
    except Exception:
        pass


def check_mainapp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(('127.0.0.1', MAIN_SOCKET_PORT))
    except ConnectionRefusedError:
        return False
    return True


def send_filepath_to_mainapp(filepath):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect(('127.0.0.1', MAIN_SOCKET_PORT))
    except ConnectionRefusedError:
        launch(filepath)
        return

    sock.settimeout(0.1)
    sock.send(json.dumps({'filepath': filepath}).encode('utf-8'))
    sock.close()


def main(initfile=None):
    parser = argparse.ArgumentParser(prog='PyMusicPlayer', add_help=True)
    parser.add_argument(
        'filepath',
        type=str,
        default='',
        nargs='?',
        help='filepath',
    )
    args = parser.parse_args()
    if args.filepath:
        filepath = args.filepath.strip('\'" ')
        if filepath and Path(filepath).exists():
            send_filepath_to_mainapp(filepath)
    else:
        # if not check_mainapp:
        if not has_running_instance():
            launch()


if __name__ == '__main__':
    main()
