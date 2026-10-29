# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import argparse
import faulthandler
import json
import logging
import numpy
import os
import socket
import sys
import time
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


def write_launch_log(message):
    # why a start showed nothing (pythonw has no console): the reason, in the
    # user's app folder
    try:
        path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'PyMusicPlayer', 'launch.log')
        with open(path, 'a', encoding='utf-8') as file:
            file.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} pid {os.getpid()}: {message}\n')
    except Exception:
        pass


def launch(filepath=None):
    write_launch_log(f'launching (cwd {os.getcwd()})')
    # a crash in native code (no Python error) and an error in an event handler
    # (wx goes on, pythonw shows nothing) are written there too
    try:
        crash_log = open(os.path.join(
            os.environ.get('LOCALAPPDATA', ''), 'PyMusicPlayer', 'launch.log'), 'a', encoding='utf-8')
        faulthandler.enable(file=crash_log, all_threads=True)
        sys.excepthook = lambda kind, value, trace: write_launch_log(
            'error\n' + ''.join(traceback.format_exception(kind, value, trace)))
    except Exception:
        pass
    try:
        from mainapp import launch_mainapp
        launch_mainapp(filepath)
        write_launch_log('closed')
    except Exception:
        write_launch_log('failed\n' + traceback.format_exc())


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
        sock.send(f'{json.dumps({"filepath": filepath})}\n'.encode('utf-8'))
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
        # if not has_running_instance():
        #     launch()
        running = has_running_instance()
        if running:
            write_launch_log(f'not started: already running as {running}')
        else:
            launch()
    # except Exception:
    #     logging.error(traceback.format_exc())
    #     # logger = logging.getLogger('')


if __name__ == '__main__':
    main()
