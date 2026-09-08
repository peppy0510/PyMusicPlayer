# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import argparse
import json
import logging
import numpy
import os
import socket
import sys
import traceback

from pathlib import Path
from wininstance import has_running_instance
from wininstance import read_instance_port


class stderr:
    def write(self, *args, **kwargs):
        pass


if not sys.stderr:
    sys.stderr = stderr()


numpy.finfo(numpy.dtype('float32'))
numpy.finfo(numpy.dtype('float64'))


# MAIN_SOCKET_PORT = 55557
MAIN_SOCKET_PORT = 55755


def launch(filepath=None):
    from mainapp import launch_mainapp
    try:
        launch_mainapp(filepath)
    except Exception:
        pass


def get_mainapp_port():
    port = read_instance_port()
    if port is None:
        return MAIN_SOCKET_PORT
    return port


def check_mainapp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect(('127.0.0.1', get_mainapp_port()))
    except OSError:
        return False
    return True


def send_filepath_to_mainapp(filepath):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        sock.connect(('127.0.0.1', get_mainapp_port()))
    except OSError:
        sock.close()
        launch(filepath)
        return

    try:
        sock.send(('%s\n' % (json.dumps({'filepath': filepath}))).encode('utf-8'))
    except OSError:
        pass
    sock.close()


def main(initfile=None):
    # root = Path(__file__).resolve().parent.parent
    # debug = root.joinpath('log/debug.log')
    # if not debug.parent.exists():
    #     os.makedirs(debug.parent)
    # logging.basicConfig(filename=debug, level=logging.DEBUG)

    # try:
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
    # except Exception:
    #     logging.error(traceback.format_exc())
    #     # logger = logging.getLogger('')


if __name__ == '__main__':
    main()
