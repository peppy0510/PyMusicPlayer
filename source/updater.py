# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import hashlib
import http.client
import importlib.util
import json
import os
import psutil
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wx


APP_NAME = 'PyMusicPlayer'
APP_HOME = 'https://github.com/peppy0510/PyMusicPlayer'
RELEASE_URL = APP_HOME.replace('https://github.com/', 'https://api.github.com/repos/') + \
    '/releases/latest'
CHECK_SECONDS = 24 * 60 * 60
RETRY_SECONDS = 60 * 60
# after the start, so the first paint and the playlists do not wait on it
START_DELAY = 10
TIMEOUT = 10
GIT_TIMEOUT = 120
CHUNK = 64 * 1024
INSTALLER_SUFFIX = '-Setup.exe'
# releases are tagged there; a checkout on another branch is someone's work
RELEASE_BRANCH = 'main'
CREATE_NO_WINDOW = 0x08000000
PYTHONS = ('python.exe', 'pythonw.exe')

MARKDOWN_LINK = re.compile(r'!?\[([^\]]*)\]\([^)]*\)')
MARKDOWN_MARKS = re.compile(r'(\*\*|__|`)')
MARKDOWN_BULLET = re.compile(r'^\s*[-*+]\s+')
MARKDOWN_HEADING = re.compile(r'^\s*#+\s*')
HTML_COMMENT = re.compile(r'<!--.*?-->', re.S)


class UpdateError(Exception):
    pass


def parse_version(text):
    found = re.search(r'(\d+)\.(\d+)\.(\d+)', text or '')
    return tuple(int(part) for part in found.groups()) if found else None


def is_newer(version, current):
    new, old = parse_version(version), parse_version(current)
    return new is not None and old is not None and new > old


def clean_notes(body):
    '''a release body in Markdown as plain lines'''
    lines = []
    for line in HTML_COMMENT.sub('', body or '').splitlines():
        line = MARKDOWN_HEADING.sub('', line)
        line = MARKDOWN_BULLET.sub('• ', line)
        line = MARKDOWN_MARKS.sub('', MARKDOWN_LINK.sub(r'\1', line)).rstrip()
        # GitHub's generated notes end in a compare link
        if line.startswith('Full Changelog'):
            continue
        if line or (lines and lines[-1]):
            lines.append(line)
    while lines and not lines[-1]:
        lines.pop()
    return '\n'.join(lines)


def fetch_release():
    '''the latest release, or None while there is none'''
    request = urllib.request.Request(RELEASE_URL, headers={
        'User-Agent': APP_NAME, 'Accept': 'application/vnd.github+json'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    installer = next((asset for asset in data.get('assets', [])
                      if asset.get('name', '').endswith(INSTALLER_SUFFIX)), None)
    return {
        'version': '.'.join(str(part) for part in parse_version(data.get('tag_name')) or ()),
        'notes': clean_notes(data.get('body')),
        'page': data.get('html_url') or f'{APP_HOME}/releases',
        'installer': installer and {
            'name': installer['name'],
            'url': installer['browser_download_url'],
            'size': installer.get('size', 0),
            'digest': installer.get('digest') or '',
        },
    }


def get_source_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_git(root, *arguments, timeout=TIMEOUT):
    return subprocess.run(['git', '-C', root, *arguments], capture_output=True, text=True,
                          timeout=timeout, creationflags=CREATE_NO_WINDOW)


def read_git(root, *arguments):
    try:
        result = run_git(root, *arguments)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def can_pull(root):
    '''a clean checkout of the release branch, following its remote'''
    if not os.path.isdir(os.path.join(root, '.git')) or not shutil.which('git'):
        return False
    if read_git(root, 'symbolic-ref', '--short', 'HEAD') != RELEASE_BRANCH:
        return False
    if read_git(root, 'rev-parse', '--abbrev-ref', f'{RELEASE_BRANCH}@{{upstream}}') != \
            f'origin/{RELEASE_BRANCH}':
        return False
    return read_git(root, 'status', '--porcelain', '--untracked-files=no') == ''


def get_update_kind():
    '''how this copy updates: its installer, a pull of its checkout or by hand from the page'''
    if getattr(sys, 'frozen', False):
        return 'installer'
    return 'git' if can_pull(get_source_root()) else 'page'


def read_file(path):
    try:
        with open(path, 'rb') as file:
            return file.read()
    except OSError:
        return None


def get_console_python():
    # pythonw has no pip output to show and a venv's Scripts holds both
    folder, name = os.path.split(sys.executable)
    console = os.path.join(folder, 'python.exe')
    return console if name.lower() == 'pythonw.exe' and os.path.exists(console) else \
        sys.executable


def install_requirements(root):
    path = os.path.join(root, 'requirements.pip')
    python = get_console_python()
    # a venv made by uv comes without pip
    if importlib.util.find_spec('pip'):
        command = [python, '-m', 'pip', 'install', '-r', path]
    elif shutil.which('uv'):
        command = ['uv', 'pip', 'install', '--python', python, '-r', path]
    else:
        raise UpdateError('Updated, but install requirements.pip by hand')
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=GIT_TIMEOUT * 5,
                                creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        raise UpdateError('Updated, but the packages could not be installed')
    if result.returncode != 0:
        raise UpdateError('Updated, but the packages could not be installed')


def pull_source():
    root = get_source_root()
    if not can_pull(root):
        raise UpdateError(f'Only a clean {RELEASE_BRANCH} checkout updates itself')
    requirements = os.path.join(root, 'requirements.pip')
    before = read_file(requirements)
    try:
        result = run_git(root, 'pull', '--ff-only', timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        raise UpdateError('git pull did not finish')
    if result.returncode != 0:
        lines = (result.stderr or result.stdout).strip().splitlines()
        raise UpdateError(lines[-1] if lines else 'git pull failed')
    if read_file(requirements) != before:
        install_requirements(root)


def get_launcher_pid():
    # a venv's pythonw starts the real interpreter as its child and outlives it briefly
    process = psutil.Process()
    try:
        while process.parent() and process.parent().name().lower() in PYTHONS:
            process = process.parent()
    except psutil.Error:
        pass
    return process.pid


def restart_source():
    root = get_source_root()
    script = os.path.join(root, 'source', 'main.pyw')
    # from the repository's root as pymp.cmd starts it (the icon is found from there); the
    # new copy waits for this one to let go before its instance check
    subprocess.Popen([sys.executable, script, '--after', str(get_launcher_pid())], cwd=root)


def get_download_folder():
    return os.path.join(tempfile.gettempdir(), APP_NAME)


def download_installer(installer, on_progress, cancelled):
    folder = get_download_folder()
    os.makedirs(folder, exist_ok=True)
    for name in os.listdir(folder):
        if INSTALLER_SUFFIX in name:
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
    path = os.path.join(folder, installer['name'])
    partial = f'{path}.part'
    digest = hashlib.sha256()
    received = 0
    request = urllib.request.Request(installer['url'], headers={'User-Agent': APP_NAME})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response, \
                open(partial, 'wb') as file:
            total = installer['size'] or int(response.headers.get('Content-Length') or 0)
            while True:
                if cancelled():
                    raise UpdateError('Download cancelled')
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                file.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                on_progress(received / total if total else 0.0)
    except (OSError, http.client.HTTPException):
        raise UpdateError('The download failed')
    if installer['size'] and received != installer['size']:
        raise UpdateError('The download was cut short')
    algorithm, _, expected = installer['digest'].partition(':')
    if algorithm == 'sha256' and expected.lower() != digest.hexdigest():
        raise UpdateError('The download does not match the release')
    os.replace(partial, path)
    return path


def launch_installer(path):
    # through the shell, which asks for elevation; a refused prompt raises
    try:
        os.startfile(path)
    except OSError:
        raise UpdateError('The installer did not start')


class Updater:
    '''checks once a day for a release newer than version; the frame shows what it finds'''

    def __init__(self, settings, version, on_checked):
        self.version = version
        self.on_checked = on_checked
        self.checked_at = settings.get('update_checked_at') or 0
        self.skipped = settings.get('update_skipped') or ''
        self.started = time.monotonic()
        self.failed_at = None
        self.busy = False
        self.cancelled = False

    def is_due(self):
        now = time.monotonic()
        if now - self.started < START_DELAY:
            return False
        if self.failed_at is not None and now - self.failed_at < RETRY_SECONDS:
            return False
        # a clock set back counts as due
        return not 0 <= time.time() - self.checked_at < CHECK_SECONDS

    def tick(self, enabled):
        if enabled and not self.busy and self.is_due():
            self.check()

    def check(self, forced=False):
        if self.busy:
            return
        self.busy = True
        threading.Thread(target=self.run_check, args=(forced,), daemon=True).start()

    def run_check(self, forced):
        release, failed = None, True
        try:
            release = fetch_release()
            if release is not None:
                release['kind'] = get_update_kind()
            failed = False
        except (OSError, ValueError, KeyError, http.client.HTTPException):
            pass
        finally:
            # whatever else went wrong, the next check is not blocked for good
            wx_call(self.finish_check, release, failed, forced)

    def finish_check(self, release, failed, forced):
        self.busy = False
        if failed:
            self.failed_at = time.monotonic()
            self.on_checked(None, 'error', forced)
            return
        self.failed_at = None
        self.checked_at = time.time()
        if release is None or not is_newer(release['version'], self.version):
            self.on_checked(None, 'current', forced)
        elif release['version'] == self.skipped and not forced:
            self.on_checked(None, 'skipped', forced)
        else:
            self.on_checked(release, 'found', forced)

    def update(self, release, on_progress, on_done):
        '''on_done(error) runs on the main thread, error None when the app should now quit'''
        self.cancelled = False

        def work():
            # the notice waits on an answer either way
            error = 'The update stopped'
            try:
                if release['kind'] == 'installer':
                    if not release['installer']:
                        raise UpdateError('This release has no installer')
                    path = download_installer(release['installer'],
                                              lambda ratio: wx_call(on_progress, ratio),
                                              lambda: self.cancelled)
                    launch_installer(path)
                else:
                    pull_source()
                error = None
            except UpdateError as caught:
                error = str(caught)
            except OSError:
                error = 'The update could not write its files'
            finally:
                wx_call(on_done, error)

        threading.Thread(target=work, daemon=True).start()

    def cancel(self):
        self.cancelled = True


def wx_call(function, *arguments):
    try:
        wx.CallAfter(function, *arguments)
    except (AssertionError, RuntimeError):
        # the app is gone
        pass
