# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import copy
import ctypes
import hashlib
import json
import mfeats
import numpy
import os
import pybass
import re
import threading
import time
import urllib.parse
import urllib.request
import wx

from macroboxlib import GetPreference
from macroboxlib import ListBoxColumn
from macroboxlib import MakeMusicFileItem
from macroboxlib import SetPreference
from utilities import get_user_docapp_path


# internet radio as playlist rows: a station's path is its stream address
USER_AGENT = 'PyMusicPlayer/1.5.0 +https://github.com/peppy0510/PyMusicPlayer'
DIRECTORY = 'https://all.api.radio-browser.info/json'
TIMEOUT = 15
LISTS_SECONDS = 60 * 60 * 24
STATIONS_LIMIT = 200
# the radio tabs: favorites and browse
RADIO_TITLE = 'Radio'
BROWSE_TITLE = 'Radio Browse'
# recently played stations, latest first
RECENT_TITLE = 'Radio Recent'
RECENT_LIMIT = 50
RADIO_TABS = {RADIO_TITLE: 'Favorite stations', RECENT_TITLE: 'Recent stations',
              BROWSE_TITLE: 'Browse stations'}
# browsed stations kept for their rows after a restart
SEEN_LIMIT = 3000
# browse tab columns: (key, title) shown, the rest hidden
BROWSE_COLUMNS = (('order', '#', 58), ('filename', 'station', 300), ('genre', 'tags', 220),
                  ('album', 'country', 60), ('type', 'codec', 60), ('bitrate', 'kbps', 50))
# stream waveform for the player's waveform boxes
TRACE_SECONDS = 30
# station picture size cap
PICTURE_BYTES = 2 * 1024 * 1024
# 10 is BASS_ERROR_SSL, not in pybass
ERRORS = {2: 'the station did not answer the address', 10: 'HTTPS is not available',
          32: 'no network', 40: 'the station took too long to answer',
          41: 'a stream format BASS does not play (AAC or HLS needs a plugin)',
          44: 'a codec BASS does not have', -1: 'an unknown error'}


def open_stream(url, decode=False):
    '''(handle, error) of a station's stream; blocks, called on the audio thread'''
    pybass.BASS_SetConfig(pybass.BASS_CONFIG_NET_PLAYLIST, 1)
    urls = [url]
    if url.lower().startswith('https://'):
        urls.append('http://' + url[len('https://'):])
    # null DOWNLOADPROC: ctypes refuses None
    handle, error = 0, None
    # through bass_fx tempo for key changes only: tempo drains the buffer
    tempo_create = audio.load_bass_fx_tempo()[0]
    for address in urls:
        try:
            handle = pybass.BASS_StreamCreateURL(
                address.encode('utf-8'), 0, pybass.BASS_STREAM_DECODE if tempo_create else 0,
                pybass.DOWNLOADPROC(), None)
        except Exception as e:
            handle, error = 0, -1
            log_failure(url, address, f'{type(e).__name__} {e}')
            continue
        if handle and tempo_create:
            # decode: for the mixer deck
            tempo = tempo_create(handle, audio.BASS_FX_FREESOURCE
                                 | (pybass.BASS_STREAM_DECODE if decode else 0))
            if tempo:
                return tempo, None
            pybass.BASS_StreamFree(handle)
            tempo_create = None
            handle = pybass.BASS_StreamCreateURL(
                address.encode('utf-8'), 0, pybass.BASS_STREAM_DECODE if decode else 0,
                pybass.DOWNLOADPROC(), None)
        if handle:
            return handle, None
        error = pybass.BASS_ErrorGetCode()
        log_failure(url, address, error)
    return 0, error


def get_stream_title(handle):
    # now playing from the stream metadata ('' without)
    if not handle:
        return ''
    # the station's own stream under the tempo one
    handle = audio.get_tempo_source(handle) or handle
    pointer = pybass.BASS_ChannelGetTags(handle, pybass.BASS_TAG_META)
    if not pointer:
        return ''
    text = ctypes.string_at(pointer)
    for encoding in ('utf-8', 'cp1252'):
        try:
            text = text.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return ''
    found = re.search(r"StreamTitle='(.*?)';", text)
    return found.group(1) if found else ''


class LiveTrace():

    '''last TRACE_SECONDS of the stream as waveform columns, newest last'''

    def __init__(self):
        self.Reset()

    def Reset(self, handle=0):
        self.handle = handle
        self.trace = numpy.zeros((0, 5), dtype=numpy.uint8)
        self.lap = None
        self.due = 0.0

    def Get(self, handle, playing):
        if not handle:
            return None
        if handle != self.handle:
            self.Reset(handle)
        if playing is False:
            self.lap = None
            return self.trace
        now = time.time()
        elapsed = 0.05 if self.lap is None else now - self.lap
        self.lap = now
        # after a stall, no more than the stream keeps
        self.due += min(max(elapsed, 0.0), 0.25)
        step = mfeats.WAVEFORM_COLUMN_SECONDS
        count = int(self.due / step)
        if count == 0:
            return self.trace
        self.due -= count * step
        info = pybass.BASS_CHANNELINFO()
        pybass.BASS_ChannelGetInfo(handle, ctypes.byref(info))
        fs, chans = info.freq, max(info.chans, 1)
        if fs <= 0:
            return self.trace
        frames = count * max(int(fs * step), 1)
        data = numpy.zeros(frames * chans, dtype=numpy.float32)
        got = audio.get_channel_data(
            handle, data.ctypes.data_as(ctypes.c_void_p),
            (frames * chans * 4) | pybass.BASS_DATA_FLOAT)
        if got in (-1, 0xFFFFFFFF) or got <= 0:
            return self.trace
        mono = data[:got // 4 // chans * chans].reshape(-1, chans).mean(axis=1)
        columns = mfeats.get_live_waveform_columns(mono, fs)
        most = int(TRACE_SECONDS / step)
        self.trace = numpy.vstack([self.trace, columns])[-most:]
        return self.trace


def get_saved_stations():
    return GetPreference('radio_stations') or []


# stations cached from the settings, reread after a save
STATIONS = None


def get_station(url):
    # a saved station, else a browsed one
    global STATIONS
    if STATIONS is None:
        STATIONS = dict(GetPreference('radio_seen') or {})
        STATIONS.update((v.get('url'), v) for v in get_saved_stations())
    return STATIONS.get(url)


def forget_stations():
    global STATIONS
    STATIONS = None


def remember_stations(stations):
    # browsed stations by address, the latest SEEN_LIMIT
    seen = GetPreference('radio_seen') or {}
    for station in stations:
        seen.pop(station['url'], None)
        seen[station['url']] = dict(station)
    while len(seen) > SEEN_LIMIT:
        seen.pop(next(iter(seen)))
    SetPreference('radio_seen', seen)
    forget_stations()


def keep_station(station):
    # keep a played station once
    stations = get_saved_stations()
    if any(v.get('url') == station['url'] for v in stations):
        return
    stations.append(dict(station))
    SetPreference('radio_stations', stations)
    forget_stations()


def keep_favicon(url, favicon):
    # saved stations keep their picture address
    stations = get_saved_stations()
    for v in stations:
        if v.get('url') == url:
            v['favicon'] = favicon
    SetPreference('radio_stations', stations)
    forget_stations()


def find_favicon(url):
    # directory picture for a stream address ('' when none)
    try:
        found = read_directory('stations/byurl', dict(url=url))
    except Exception:
        return ''
    return next((v.get('favicon') for v in found if v.get('favicon')), '')


def fetch_picture(url):
    '''station favicon bytes or None; blocks, called on threads'''
    station = get_station(url) or {}
    favicon = station.get('favicon')
    if favicon is None:
        favicon = find_favicon(url)
        wx.CallAfter(keep_favicon, url, favicon)
    return read_picture(favicon)


PICTURES = {}


def get_picture(url):
    # station cover read once on a thread, None till then
    if url not in PICTURES:
        PICTURES[url] = None

        def work():
            PICTURES[url] = fetch_picture(url)
        threading.Thread(target=work, daemon=True).start()
    return PICTURES[url]


def read_picture(url):
    '''picture bytes by address, cached in the covers folder'''
    if not url or not url.lower().startswith(('http://', 'https://')):
        return None
    folder = os.path.join(get_user_docapp_path(), 'covers', 'radio')
    path = os.path.join(folder, hashlib.sha1(url.encode('utf-8')).hexdigest())
    try:
        with open(path, 'rb') as file:
            return file.read() or None
    except OSError:
        pass
    request = urllib.request.Request(url)
    request.add_header('User-Agent', USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            data = resp.read(PICTURE_BYTES + 1)
    except (OSError, ValueError):
        return None
    if not data or len(data) > PICTURE_BYTES:
        return None
    os.makedirs(folder, exist_ok=True)
    with open(path, 'wb') as file:
        file.write(data)
    return data


def log_failure(url, address, error):
    # log what failed to play (radio.log)
    station = get_station(url) or {}
    try:
        with open(os.path.join(get_user_docapp_path(), 'radio.log'), 'a',
                  encoding='utf-8') as file:
            file.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} error {error} codec '
                       f'{station.get("codec", "")} | {station.get("name", "")} | {address}\n')
    except OSError:
        pass


def open_tab(listbox, title):
    # tab index, made when missing
    index = [i for i, v in enumerate(listbox.innerList) if v.title == title]
    if not index:
        selected = listbox.selectedList
        listbox.AddInnerList(title)
        listbox.SetSelectedList(selected)
        index = [len(listbox.innerList) - 1]
    ensure_station_columns(listbox)
    return index[0]


def ensure_station_columns(listbox, rebuild=False):
    '''radio tabs with station columns only'''
    wanted = [key for key, _, _ in BROWSE_COLUMNS]
    for inner in listbox.innerList:
        if inner.title not in RADIO_TABS:
            continue
        if [v.key for v in inner.columns if v.show] != wanted:
            set_browse_columns(inner)
        elif rebuild is False:
            continue
        # rows rebuilt from their http address
        paths = [next((v for v in item if isinstance(v, str)
                       and v.startswith(('http://', 'https://'))), None) for item in inner.items]
        inner.items = [tuple(MakeMusicFileItem(path, order, inner.columns))
                       for order, path in enumerate([v for v in paths if v], 1)]
        inner.filterCache = None
    listbox.reInitBuffer = True


def get_favorite_urls(listbox):
    # addresses in the Favorites tab
    for inner in listbox.innerList:
        if inner.title == RADIO_TITLE:
            pathIdx = [v.key for v in inner.columns].index('path')
            return set(item[pathIdx] for item in inner.items)
    return set()


def get_station_rows(inner, stations):
    # station rows for a tab
    return [tuple(MakeMusicFileItem(v['url'], order, inner.columns))
            for order, v in enumerate(stations, 1)]


def set_browse_columns(inner):
    # station, tags, country, codec, bitrate; set before the rows are made
    # copies: tabs can share column objects
    shown = dict((key, (title, width)) for key, title, width in BROWSE_COLUMNS)
    order = [key for key, _, _ in BROWSE_COLUMNS]
    columns = [copy.deepcopy(v) for v in sorted(
        inner.columns, key=lambda v: order.index(v.key) if v.key in shown else len(order))]
    for column in columns:
        column.show = column.key in shown
        if column.key in shown:
            column.title, column.width = shown[column.key]
    inner.columns = columns


def repair_playlist_columns(listbox):
    '''restore a playlist's columns sorted as a station's'''
    station = [key for key, _, _ in BROWSE_COLUMNS]
    default = GetPreference('columns') or ListBoxColumn()
    by_key = dict((v.key, v) for v in default)
    for inner in listbox.innerList:
        if inner.title in RADIO_TABS:
            continue
        keys = [v.key for v in inner.columns]
        if keys[:len(station)] != station or set(keys) != set(by_key):
            continue
        inner.columns = [copy.deepcopy(by_key[v.key]) for v in default]
        inner.filterCache = None
    listbox.reInitBuffer = True


def show_found(mainpanel, stations, label):
    '''browsed stations in the Browse tab, selected'''
    remember_stations(stations)
    listbox = mainpanel.ListBox
    index = open_tab(listbox, BROWSE_TITLE)
    inner = listbox.innerList[index]
    set_browse_columns(inner)
    inner.items = get_station_rows(inner, stations)
    inner.filterCache = None
    inner.filterQuery = None
    inner.selectedItems = []
    listbox.SetSelectedList(index)
    listbox.reInitBuffer = True
    mainpanel.ListTab.TabList.reInitBuffer = True
    tell(mainpanel, f'{label}: {len(stations)} stations')


def browse(mainpanel, label, work):
    # query on a thread, show in the Browse tab
    tell(mainpanel, f'Reading {label} ...')

    def run():
        try:
            stations, error = work(), None
        except Exception as e:
            stations, error = None, str(e)
        if error is not None:
            wx.CallAfter(tell, mainpanel, f'The directory did not answer: {error}', True)
        else:
            wx.CallAfter(show_found, mainpanel, stations, label)

    threading.Thread(target=run, daemon=True).start()


def tell(mainpanel, text, warn=False):
    # in the status line
    status = getattr(mainpanel, 'StatusBox', None)
    if status:
        status.alarm = text
        status.alarm_color = 'red' if warn else 'blue'


def add_favorites(mainpanel, stations):
    # keep stations and add them to Favorites, once each
    listbox = mainpanel.ListBox
    index = open_tab(listbox, RADIO_TITLE)
    inner = listbox.innerList[index]
    pathIdx = [v.key for v in inner.columns].index('path')
    there = set(item[pathIdx] for item in inner.items)
    added = [v for v in stations if v['url'] not in there]
    for station in added:
        keep_station(station)
    rows = [tuple(MakeMusicFileItem(v['url'], len(inner.items) + order, inner.columns))
            for order, v in enumerate(added, 1)]
    inner.items = list(inner.items) + rows
    inner.filterCache = None
    listbox.reInitBuffer = True
    mainpanel.ListTab.TabList.reInitBuffer = True
    tell(mainpanel, f'{len(added)} added to {RADIO_TABS[RADIO_TITLE]}')


def remove_favorites(mainpanel, urls):
    # remove from Favorites and renumber
    listbox = mainpanel.ListBox
    index = [i for i, v in enumerate(listbox.innerList) if v.title == RADIO_TITLE]
    if not index:
        return
    inner = listbox.innerList[index[0]]
    keys = [v.key for v in inner.columns]
    pathIdx, orderIdx = keys.index('path'), keys.index('order') if 'order' in keys else None
    kept = [item for item in inner.items if item[pathIdx] not in set(urls)]
    removed = len(inner.items) - len(kept)
    if orderIdx is not None:
        kept = [item[:orderIdx] + (order,) + item[orderIdx + 1:]
                for order, item in enumerate(kept, 1)]
    inner.items = kept
    inner.filterCache = None
    inner.selectedItems = []
    listbox.reInitBuffer = True
    mainpanel.ListTab.TabList.reInitBuffer = True
    tell(mainpanel, f'{removed} removed from {RADIO_TABS[RADIO_TITLE]}')


def note_recent(url):
    # played station first in recent, the latest RECENT_LIMIT
    urls = [v for v in (GetPreference('recent_stations') or []) if v != url]
    SetPreference('recent_stations', [url] + urls[:RECENT_LIMIT - 1])


def show_recent(mainpanel):
    '''recent stations, latest first, selected'''
    listbox = mainpanel.ListBox
    index = open_tab(listbox, RECENT_TITLE)
    inner = listbox.innerList[index]
    stations = [get_station(v) or dict(url=v, name=v)
                for v in (GetPreference('recent_stations') or [])]
    inner.items = get_station_rows(inner, stations)
    inner.filterCache = None
    inner.selectedItems = []
    listbox.SetSelectedList(index)
    listbox.reInitBuffer = True


def toggle_favorite(mainpanel, url):
    # browse row star: toggle favorite
    if url in get_favorite_urls(mainpanel.ListBox):
        remove_favorites(mainpanel, [url])
    else:
        add_favorites(mainpanel, [get_station(url) or dict(url=url, name=url)])


def add_url(mainpanel):
    # add a station by its address to favorites
    url = wx.GetTextFromUser('Stream URL (http or https)', 'Add Station', '', mainpanel)
    url = url.strip()
    if not url.lower().startswith(('http://', 'https://')):
        return
    name = wx.GetTextFromUser('Name', 'Add Station', '', mainpanel).strip()
    add_favorites(mainpanel, [dict(name=name or url, url=url, tags='', bitrate=0)])


def get_browse_choices():
    '''[(label, query)] to browse by'''
    genres, countries = get_lists()
    choices = [('Top voted', dict())]
    choices += [(f'Genre: {name}', dict(tag=name, tagExact='true'))
                for name, _ in genres[:100]]
    choices += [(f'Country: {name}',
                 dict(countrycode=code) if code else dict(country=name, countryExact='true'))
                for name, _, code in countries[:100]]
    return choices


def read_directory(path, query=None):
    url = f'{DIRECTORY}/{path}'
    if query:
        url += '?' + urllib.parse.urlencode(query)
    request = urllib.request.Request(url)
    request.add_header('User-Agent', USER_AGENT)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_lists():
    '''(genres, countries) of the directory, cached a day'''
    path = os.path.join(get_user_docapp_path(), 'radio_lists.json')
    try:
        if time.time() - os.path.getmtime(path) < LISTS_SECONDS:
            with open(path, encoding='utf-8') as file:
                kept = json.load(file)
            return kept['genres'], kept['countries']
    except (OSError, ValueError, KeyError):
        pass
    tags = read_directory('tags', dict(order='stationcount', reverse='true', limit=300,
                                       hidebroken='true'))
    countries = read_directory('countries', dict(order='stationcount', reverse='true',
                                                 hidebroken='true'))
    genres = [(v['name'], v['stationcount']) for v in tags if v.get('name')]
    countries = [(v['name'], v['stationcount'], v.get('iso_3166_1', ''))
                 for v in countries if v.get('name')]
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(dict(genres=genres, countries=countries), file)
    return genres, countries


def get_stations(**query):
    '''[station] for a genre, country or name, most voted first'''
    query.update(limit=STATIONS_LIMIT, hidebroken='true', order='votes', reverse='true')
    body = read_directory('stations/search', query)
    return [dict(name=v.get('name', '').strip(), url=v.get('url_resolved') or v.get('url', ''),
                 tags=v.get('tags', ''), bitrate=v.get('bitrate', 0),
                 country=v.get('countrycode', ''), favicon=v.get('favicon', '') or '',
                 codec=('HLS' if v.get('hls') else v.get('codec', '')))
            for v in body if v.get('url_resolved') or v.get('url')]
