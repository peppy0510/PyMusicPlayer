# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
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

from macroboxlib import Button
from macroboxlib import ComboBox
from macroboxlib import DialogBox
from macroboxlib import GetPreference
from macroboxlib import SetPreference
from macroboxlib import StaticText
from macroboxlib import TextCtrl
from utilities import get_user_docapp_path


# internet radio: a stream played by BASS beside the player (the player paused while it
# plays, the radio stopped when the player plays). stations kept in the settings; the
# directory (radio-browser.info) read when the window opens (its genres and countries, kept
# a day) and when a genre, a country or a name is asked for
LVM_SETEXTENDEDLISTVIEWSTYLE = 0x1036
LVS_EX_INFOTIP = 0x400
LVS_EX_LABELTIP = 0x4000
USER_AGENT = 'PyMusicPlayer/1.1.1 +https://github.com/peppy0510/PyMusicPlayer'
DIRECTORY = 'https://all.api.radio-browser.info/json'
TIMEOUT = 15
LISTS_SECONDS = 60 * 60 * 24
STATIONS_LIMIT = 200
# the waveform of what the radio played, for the player's waveform boxes (GetTrace)
TRACE_SECONDS = 30
# a station's picture no larger than this (a favicon, a logo)
PICTURE_BYTES = 2 * 1024 * 1024
# what a failed connection says (BASS_ErrorGetCode); 10 is BASS_ERROR_SSL, not in pybass
ERRORS = {2: 'the station did not answer the address', 10: 'HTTPS is not available',
          32: 'no network', 40: 'the station took too long to answer',
          41: 'a stream format BASS does not play (AAC or HLS needs a plugin)',
          44: 'a codec BASS does not have', -1: 'an unknown error'}


class RadioPlayer():

    def __init__(self):
        self.handle = 0
        self.station = None
        self.job = 0
        self.volume = 1.0
        # LOUD (Auto Master) as the player has it, set by the player (SetLoud)
        self.loud = True
        self.vst = 0
        # the station's picture (its favicon's bytes) for the player's cover, or None
        self.picture = None
        self.ResetTrace()

    def SetLoud(self, on):
        self.loud = on
        if self.vst:
            pybass.BASS_VST_SetBypass(self.vst, on is False)

    def ResetTrace(self):
        self.trace = numpy.zeros((0, 5), dtype=numpy.uint8)
        self.trace_lap = None
        self.trace_due = 0.0

    def GetTrace(self):
        '''the last TRACE_SECONDS of what is heard, as waveform columns (mfeats'), the newest
        last; the columns since the last call read from the stream (what the sound card
        plays now), as many as the time gone by'''
        if self.IsPlaying() is False:
            return None
        now = time.time()
        elapsed = 0.05 if self.trace_lap is None else now - self.trace_lap
        self.trace_lap = now
        # after a stall, no more than the stream keeps
        self.trace_due += min(max(elapsed, 0.0), 0.25)
        step = mfeats.WAVEFORM_COLUMN_SECONDS
        count = int(self.trace_due / step)
        if count == 0:
            return self.trace
        self.trace_due -= count * step
        info = pybass.BASS_CHANNELINFO()
        pybass.BASS_ChannelGetInfo(self.handle, ctypes.byref(info))
        fs, chans = info.freq, max(info.chans, 1)
        if fs <= 0:
            return self.trace
        frames = count * max(int(fs * step), 1)
        data = numpy.zeros(frames * chans, dtype=numpy.float32)
        got = pybass.BASS_ChannelGetData(
            self.handle, data.ctypes.data_as(ctypes.c_void_p),
            (frames * chans * 4) | pybass.BASS_DATA_FLOAT)
        if got in (-1, 0xFFFFFFFF) or got <= 0:
            return self.trace
        mono = data[:got // 4 // chans * chans].reshape(-1, chans).mean(axis=1)
        columns = mfeats.get_live_waveform_columns(mono, fs)
        most = int(TRACE_SECONDS / step)
        self.trace = numpy.vstack([self.trace, columns])[-most:]
        return self.trace

    def Play(self, station, done):
        # opened on a thread (the connection takes seconds); done(error or None) on the
        # GUI thread. a later Play or Stop drops what an earlier one opens
        self.Stop()
        self.job += 1
        job = self.job
        self.station = station
        self.picture = None
        self.ResetTrace()

        def work():
            # an address that is a playlist (.pls, .m3u) followed to its stream; an https one
            # that fails tried once more over http (many stations serve both)
            pybass.BASS_SetConfig(pybass.BASS_CONFIG_NET_PLAYLIST, 1)
            urls = [station['url']]
            if station['url'].lower().startswith('https://'):
                urls.append('http://' + station['url'][len('https://'):])
            # no download callback: a null one of pybass' type (None was refused by ctypes,
            # an ArgumentError on the thread, and no station ever opened)
            handle, error = 0, None
            for url in urls:
                try:
                    handle = pybass.BASS_StreamCreateURL(url.encode('utf-8'), 0, 0,
                                                         pybass.DOWNLOADPROC(), None)
                except Exception as e:
                    handle, error = 0, -1
                    log_failure(station, url, '%s %s' % (type(e).__name__, e))
                    continue
                if handle:
                    break
                error = pybass.BASS_ErrorGetCode()
                log_failure(station, url, error)
            wx.CallAfter(opened, handle, None if handle else error)
            favicon = station.get('favicon')
            if favicon is None:
                # kept before stations had their picture: looked up once by its address
                favicon = find_favicon(station['url'])
                wx.CallAfter(keep_favicon, station, favicon)
            picture = read_picture(favicon)
            if picture is not None:
                wx.CallAfter(pictured, picture)

        def pictured(picture):
            if job == self.job:
                self.picture = picture

        def opened(handle, error):
            if job != self.job:
                if handle:
                    pybass.BASS_StreamFree(handle)
                return
            if handle:
                self.handle = handle
                # through Auto Master as the player's tracks are
                self.vst = audio.set_automaster(handle, self.loud)
                self.SetVolume(self.volume)
                pybass.BASS_ChannelPlay(handle, False)
            done(error)

        threading.Thread(target=work, daemon=True).start()

    def Stop(self):
        self.job += 1
        if self.handle:
            pybass.BASS_StreamFree(self.handle)
        self.handle = 0
        self.vst = 0
        self.station = None

    def IsPlaying(self):
        return bool(self.handle) and \
            pybass.BASS_ChannelIsActive(self.handle) != pybass.BASS_ACTIVE_STOPPED

    def SetVolume(self, volume):
        self.volume = volume
        if self.handle:
            pybass.BASS_ChannelSetAttribute(self.handle, pybass.BASS_ATTRIB_VOL, volume)

    def GetTitle(self):
        # the song the station is playing now, from its stream's metadata
        if not self.handle:
            return ''
        pointer = pybass.BASS_ChannelGetTags(self.handle, pybass.BASS_TAG_META)
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


PLAYER = RadioPlayer()


def find_favicon(url):
    # the directory's picture for a stream address ('' when none or not found)
    try:
        found = read_directory('stations/byurl', dict(url=url))
    except Exception:
        return ''
    return next((v.get('favicon') for v in found if v.get('favicon')), '')


def keep_favicon(station, favicon):
    # the station (in an open window's list too) and the saved ones with its address keep
    # it (looked up once)
    station['favicon'] = favicon
    stations = GetPreference('radio_stations') or []
    for v in stations:
        if v.get('url') == station['url']:
            v['favicon'] = favicon
    SetPreference('radio_stations', stations)


def read_picture(url):
    '''the bytes of a station's picture (its favicon), kept in the covers folder; None when
    it has none or it cannot be read'''
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


def log_failure(station, url, error):
    # what did not play, for a look later (radio.log in the user's folder)
    try:
        with open(os.path.join(get_user_docapp_path(), 'radio.log'), 'a',
                  encoding='utf-8') as file:
            file.write('%s error %s codec %s | %s | %s\n' % (
                time.strftime('%Y-%m-%d %H:%M:%S'), error, station.get('codec', ''),
                station.get('name', ''), url))
    except OSError:
        pass


def stop():
    # from the player when it plays
    PLAYER.Stop()


def read_directory(path, query=None):
    url = '%s/%s' % (DIRECTORY, path)
    if query:
        url += '?' + urllib.parse.urlencode(query)
    request = urllib.request.Request(url)
    request.add_header('User-Agent', USER_AGENT)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))


def get_lists():
    '''(genres, countries) of the directory, [(name, stations)] the most stations first; read
    once a day, kept in the user's folder'''
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
    '''[station] of the directory for a genre (tag), a country (countrycode) or a name, the
    most voted first'''
    query.update(limit=STATIONS_LIMIT, hidebroken='true', order='votes', reverse='true')
    body = read_directory('stations/search', query)
    return [dict(name=v.get('name', '').strip(), url=v.get('url_resolved') or v.get('url', ''),
                 tags=v.get('tags', ''), bitrate=v.get('bitrate', 0),
                 country=v.get('countrycode', ''), favicon=v.get('favicon', '') or '',
                 codec=('HLS' if v.get('hls') else v.get('codec', '')))
            for v in body if v.get('url_resolved') or v.get('url')]


class RadioBox(DialogBox):

    def __init__(self, parent, mainpanel):
        DialogBox.__init__(self, parent, size=(620, 620))
        self.mainpanel = mainpanel
        self.SetTitle('Internet Radio')
        self.stations = GetPreference('radio_stations') or []
        self.found = []
        self.status = ''
        self.hovered = (None, -1)
        self.genres = []
        self.countries = []
        width, height = self.GetClientSize()
        StaticText(self, label='My stations', pos=(10, 8), size=(200, -1))
        self.Stations = self.MakeList((10, 26, width - 20, 130))
        self.Stations.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnPlayStation)
        y = 162
        buttons = (('Play', self.OnPlayStation), ('Stop', self.OnStop),
                   ('Remove', self.OnRemove), ('Add URL...', self.OnAddURL))
        for i, (label, handler) in enumerate(buttons):
            button = Button(self, label=label)
            button.SetRect((10 + i * 90, y, 84, 26))
            button.Bind(wx.EVT_BUTTON, handler)
        y += 42
        StaticText(self, label='Browse the directory', pos=(10, y), size=(200, -1))
        y += 20
        StaticText(self, label='Genre', pos=(10, y + 3), size=(50, -1))
        self.Genre = ComboBox(self, choices=[], style=wx.CB_READONLY)
        self.Genre.SetRect((60, y, 200, 24))
        self.Genre.Bind(wx.EVT_COMBOBOX, self.OnGenre)
        StaticText(self, label='Country', pos=(276, y + 3), size=(55, -1))
        self.Country = ComboBox(self, choices=[], style=wx.CB_READONLY)
        self.Country.SetRect((332, y, 180, 24))
        self.Country.Bind(wx.EVT_COMBOBOX, self.OnCountry)
        button = Button(self, label='Top voted')
        button.SetRect((width - 100, y - 1, 90, 26))
        button.Bind(wx.EVT_BUTTON, self.OnTop)
        y += 32
        StaticText(self, label='Name', pos=(10, y + 3), size=(50, -1))
        self.Query = TextCtrl(self, pos=(60, y), size=(260, 22), style=wx.TE_PROCESS_ENTER)
        self.Query.Bind(wx.EVT_TEXT_ENTER, self.OnSearch)
        button = Button(self, label='Search')
        button.SetRect((328, y - 2, 84, 26))
        button.Bind(wx.EVT_BUTTON, self.OnSearch)
        button = Button(self, label='Keep')
        button.SetRect((width - 100, y - 2, 90, 26))
        button.Bind(wx.EVT_BUTTON, self.OnKeep)
        self.Found = self.MakeList((10, y + 30, width - 20, height - y - 30 - 64))
        self.Found.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnPlayFound)
        self.Status = StaticText(self, label='', pos=(10, height - 52), size=(width - 140, 18))
        StaticText(self, label='Volume', pos=(width - 230, height - 30), size=(50, -1))
        self.Volume = wx.Slider(self, value=int(PLAYER.volume * 100), minValue=0,
                                maxValue=100, pos=(width - 175, height - 34), size=(160, 24))
        self.Volume.Bind(wx.EVT_SLIDER, self.OnVolume)
        self.NowPlaying = StaticText(self, label='', pos=(10, height - 30),
                                     size=(width - 250, 18))
        self.FillList(self.Stations, self.stations)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.timer.Start(2000)
        self.ShowPlaying()
        self.LoadLists()

    def MakeList(self, rect):
        control = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        control.SetRect(rect)
        for i, (title, width) in enumerate((('Name', 240), ('Tags', 190), ('Country', 55),
                                            ('Codec', 55), ('kbps', 45))):
            control.InsertColumn(i, title, width=width)
        # no pop-up of a cut cell's whole text (it was cut off by the windows beside the
        # dialog): the station under the pointer is told in the status line instead
        ctypes.windll.user32.SendMessageW(control.GetHandle(), LVM_SETEXTENDEDLISTVIEWSTYLE,
                                          LVS_EX_LABELTIP | LVS_EX_INFOTIP, 0)
        control.Bind(wx.EVT_MOTION, self.OnListMotion)
        control.Bind(wx.EVT_LEAVE_WINDOW, self.OnListLeave)
        return control

    def OnListMotion(self, event):
        event.Skip()
        control = event.GetEventObject()
        index, _ = control.HitTest(event.GetPosition())
        stations = self.stations if control is self.Stations else self.found
        if index == self.hovered[1] and control is self.hovered[0]:
            return
        self.hovered = (control, index)
        if 0 <= index < len(stations):
            v = stations[index]
            self.Status.SetLabel('%s | %s' % (v['name'] or v['url'], v.get('tags', '') or ''))
        else:
            self.Status.SetLabel(self.status)

    def OnListLeave(self, event):
        event.Skip()
        self.hovered = (None, -1)
        self.Status.SetLabel(self.status)

    def SetStatus(self, label):
        # the status line's own message, shown again when the pointer leaves a list
        self.status = label
        if self.hovered[1] < 0:
            self.Status.SetLabel(label)

    def FillList(self, control, stations):
        control.DeleteAllItems()
        for i, v in enumerate(stations):
            control.InsertItem(i, v['name'] or v['url'])
            control.SetItem(i, 1, v.get('tags', '') or '')
            control.SetItem(i, 2, v.get('country', '') or '')
            control.SetItem(i, 3, v.get('codec', '') or '')
            control.SetItem(i, 4, str(v.get('bitrate', '') or ''))

    def Ask(self, label, work, done):
        # the directory on a thread, its answer (or error) back on the GUI thread
        self.SetStatus(label)

        def run():
            try:
                answer, error = work(), None
            except Exception as e:
                answer, error = None, str(e)
            wx.CallAfter(finish, answer, error)

        def finish(answer, error):
            if not self:
                return
            if error is not None:
                self.SetStatus('The directory did not answer: %s' % (error))
                return
            done(answer)

        threading.Thread(target=run, daemon=True).start()

    def LoadLists(self):
        def done(answer):
            self.genres, self.countries = answer
            self.Genre.Set(['%s (%d)' % (name, count) for name, count in self.genres])
            self.Country.Set(['%s (%d)' % (name, count) for name, count, _ in self.countries])
            self.SetStatus('%d genres, %d countries' % (len(self.genres),
                                                              len(self.countries)))
        self.Ask('Reading the directory ...', get_lists, done)

    def ShowFound(self, label):
        def done(found):
            self.found = found
            self.FillList(self.Found, found)
            self.SetStatus('%s: %d stations' % (label, len(found)))
        return done

    def OnGenre(self, event):
        index = self.Genre.GetSelection()
        if index < 0 or index >= len(self.genres):
            return
        name = self.genres[index][0]
        self.Ask('Reading %s ...' % (name), lambda: get_stations(tag=name, tagExact='true'),
                 self.ShowFound(name))

    def OnCountry(self, event):
        index = self.Country.GetSelection()
        if index < 0 or index >= len(self.countries):
            return
        name, _, code = self.countries[index]
        if code:
            query = dict(countrycode=code)
        else:
            query = dict(country=name, countryExact='true')
        self.Ask('Reading %s ...' % (name), lambda: get_stations(**query),
                 self.ShowFound(name))

    def OnTop(self, event):
        self.Ask('Reading the most voted ...', lambda: get_stations(),
                 self.ShowFound('Top voted'))

    def OnSearch(self, event):
        name = self.Query.GetValue().strip()
        if not name:
            return
        self.Ask('Searching ...', lambda: get_stations(name=name), self.ShowFound(name))

    def Play(self, station):
        # the player paused only when it plays: paused again, its place went to the track's
        # end and the playlist's next track began
        if self.mainpanel.PlayBox.IsPlaying():
            self.mainpanel.PlayBox.OnPause()
        PLAYER.SetLoud(self.mainpanel.PlayBox.IsLoudOn())
        PLAYER.SetVolume(self.Volume.GetValue() / 100.0)
        self.SetStatus('Connecting to %s ...' % (station['name'] or station['url']))
        PLAYER.Play(station, self.OnOpened)

    def OnOpened(self, error):
        if not self:
            return
        if error is not None:
            self.SetStatus('Not played: %s (BASS error %d)' % (ERRORS.get(error, 'error'),
                                                               error))
            return
        self.ShowPlaying()

    def ShowPlaying(self):
        if PLAYER.station is not None and PLAYER.IsPlaying():
            self.SetStatus('Playing %s' % (PLAYER.station['name'] or PLAYER.station['url']))
        self.NowPlaying.SetLabel(PLAYER.GetTitle())

    def OnTimer(self, event):
        if not self:
            return
        self.ShowPlaying()

    def OnPlayStation(self, event):
        index = self.Stations.GetFirstSelected()
        if index >= 0:
            self.Play(self.stations[index])

    def OnPlayFound(self, event):
        index = self.Found.GetFirstSelected()
        if index >= 0:
            self.Play(self.found[index])

    def OnStop(self, event):
        PLAYER.Stop()
        self.SetStatus('Stopped')
        self.NowPlaying.SetLabel('')

    def OnRemove(self, event):
        index = self.Stations.GetFirstSelected()
        if index < 0:
            return
        self.stations.pop(index)
        self.SaveStations()

    def OnAddURL(self, event):
        url = wx.GetTextFromUser('Stream URL (http or https)', 'Add Station', '', self)
        if not url.strip().lower().startswith(('http://', 'https://')):
            return
        name = wx.GetTextFromUser('Name', 'Add Station', '', self)
        self.stations.append(dict(name=name.strip(), url=url.strip(), tags='', bitrate=0))
        self.SaveStations()

    def OnKeep(self, event):
        index = self.Found.GetFirstSelected()
        if index < 0:
            return
        station = self.found[index]
        if station['url'] not in [v['url'] for v in self.stations]:
            self.stations.append(station)
            self.SaveStations()

    def SaveStations(self):
        SetPreference('radio_stations', self.stations)
        self.FillList(self.Stations, self.stations)

    def OnVolume(self, event):
        PLAYER.SetVolume(self.Volume.GetValue() / 100.0)

    def OnClose(self, event):
        # the radio plays on with its window closed (Stop, or the player, ends it)
        self.timer.Stop()
        self.Destroy()
