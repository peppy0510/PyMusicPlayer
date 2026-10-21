# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import hashlib
import io
import os
import threading
import time
import urllib.request
import zipfile

from utilities import get_user_docapp_path


# files the repository may not carry (their licences), fetched from their makers when the
# player starts and they are missing, into the user's folder. one is used only when it is
# the very file tested here (sha256): a newer one upstream is not taken, but told in
# addons.log
ADDONS = {
    'bass_aac.dll': dict(
        url='https://www.un4seen.com/files/z/2/bass_aac24.zip',
        member='x64/bass_aac.dll',
        sha256='c9d9b511d68ccd927d9b4e702fe47b9a9681a550715d6c353e2acfcbbf5737e2'),
    'fpcalc.exe': dict(
        url='https://github.com/acoustid/chromaprint/releases/download/v1.5.1/'
            'chromaprint-fpcalc-1.5.1-windows-x86_64.zip',
        member='chromaprint-fpcalc-1.5.1-windows-x86_64/fpcalc.exe',
        sha256='659ea2dba1a12d7df4fe2b6f23f60fd9414ae61aca1b014ee8fa37c5e09b930b'),
}
USER_AGENT = 'PyMusicPlayer/1.1.1 +https://github.com/peppy0510/PyMusicPlayer'
TIMEOUT = 30


def get_addons_path():
    path = os.path.join(get_user_docapp_path(), 'addons')
    os.makedirs(path, exist_ok=True)
    return path


def find_addon(name):
    # the file in the user's add-on folder, or None
    path = os.path.join(get_addons_path(), name)
    return path if os.path.isfile(path) else None


def log(text):
    try:
        with open(os.path.join(get_user_docapp_path(), 'addons.log'), 'a',
                  encoding='utf-8') as file:
            file.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), text))
    except OSError:
        pass


def fetch(name):
    # the zip read, its one file checked and written; True when it is in place
    addon = ADDONS[name]
    request = urllib.request.Request(addon['url'])
    request.add_header('User-Agent', USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            body = resp.read()
        data = zipfile.ZipFile(io.BytesIO(body)).read(addon['member'])
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        log('%s: not fetched, %s' % (name, error))
        return False
    digest = hashlib.sha256(data).hexdigest()
    if digest != addon['sha256']:
        log('%s: not used, its sha256 %s is not the tested one (a newer release?)'
            % (name, digest))
        return False
    path = os.path.join(get_addons_path(), name)
    with open(path + '.part', 'wb') as file:
        file.write(data)
    os.replace(path + '.part', path)
    log('%s: fetched' % (name))
    return True


def fetch_missing(done=None):
    '''the missing ones fetched together on a thread; done(names fetched) after, on that
    thread (none missing: nothing done)'''
    missing = [name for name in ADDONS if find_addon(name) is None]
    if not missing:
        return

    def work():
        fetched = [name for name in missing if fetch(name)]
        if done is not None and fetched:
            done(fetched)

    threading.Thread(target=work, daemon=True).start()
