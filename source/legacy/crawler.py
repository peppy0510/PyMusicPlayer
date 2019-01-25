# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import discogs_client as discogs
import gc
import multiprocessing
import os
import pygn
import random
import threading
import time
import urllib
import wx

from pyechonest import artist as echonest_artist
from pyechonest import config as echonest_config
from pyechonest import song as echonest_song


class DiscogsThread(threading.Thread):

    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.parent = parent
        self.result = None
        self.step = 0
        self.info = Struct(releases=list())
        self.max_step = 6

    def run(self):
        # socket.setdefaulttimeout(3)
        artist = self.parent.parent.parent.GetSelectedItemsKeyValue('artist')[0]
        discogs.user_agent = 'muteklab/1.0 +http://www.muteklab.com'
        artist = discogs.Artist(artist)
        try:
            keys = artist.data.keys()
        except Exception:
            # queue.put(None)
            return
        if u'id' in keys:
            self.info.id = artist.data[u'id']
        if u'name' in keys:
            self.info.name = artist.data[u'name']
        if u'aliases' in keys:
            self.info.aliases = artist.data[u'aliases']
        if u'namevariations' in keys:
            self.info.namevariations = artist.data[u'namevariations']
        if u'realname' in keys:
            self.info.realname = artist.data[u'realname']
        if u'members' in keys:
            self.info.members = artist.data[u'members']
        collected = gc.collect()
        self.info.images = list()
        self.info.releases = list()
        random.randrange(0, len(artist.releases))
        randomIdx = random.sample(range(len(artist.releases)), len(artist.releases))
        for i in randomIdx:
            try:
                release = artist.releases[i]
                data = '%s %s' % (release.data['year'], release.data['title'])
                self.info.releases.append(data)
                # print(i)
                # if 'images' in release.data.keys():
                #   # uri = release.data['images'][0]['uri']
                #   uri = release.data['images'][0]['uri150']
                #   artwork = urllib.urlopen(uri).read()
                #   info.images.append(artwork)
                # queue.put(info)
            except Exception:
                pass
        gc.collect()

    def __del__(self):
        pass


class DiscogsPanel(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY,
                          style=wx.CLIP_CHILDREN | wx.FRAME_SHAPED |
                          wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL)
        self.parent = parent
        self.SetBackgroundColour((255, 255, 255))
        width, height = self.parent.GetSize()
        self.SetRect((0, 0, width, 58))
        DialogBoxShowdowLine(self)
        self.TextMessage = wx.StaticText(self, label='', pos=(18, 20))

    def OnClose(self, event):
        self.Destroy()


class DiscogsBox(wx.Dialog, wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        wx.Dialog.__init__(self, parent, wx.ID_ANY, size=(450, 163),
                           pos=wx.DefaultPosition, style=wx.CLIP_CHILDREN |
                           wx.CAPTION | wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL | wx.STAY_ON_TOP)
        self.parent = parent
        self.SetTitle('Discogs')
        self.Thread = DiscogsThread(self)
        self.DiscogsPanel = DiscogsPanel(self)
        self.SetBackgroundColour((240, 240, 240))
        width, height = self.GetSize()
        self.CloseButton = wx.Button(self,
                                     label='Close', pos=(width - 95, height - 68), size=(75, -1))
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        # self.DownloadButton = wx.Button(self,\
        #   label='Download', pos=(width-95-80, height-68), size=(75, -1))
        # self.DownloadButton.Bind(wx.EVT_BUTTON, self.OnDownload)
        # self.DownloadButton.Disable()

        # self.AutoCheckUpdate = wx.CheckBox(self,\
        #   label='  Auto check update on startup', pos=(20, height-63))
        # self.AutoCheckUpdate.Bind(wx.EVT_CHECKBOX, self.OnAutoCheckUpdate)
        # preference = GetPreference('auto_check_update')
        # if preference is None or preference: self.AutoCheckUpdate.SetValue(1)
        self.Centre()
        self.Show(True)
        self.stop = False
        self.interval = 20
        self.Start(self.interval)
        self.Thread.start()

    def Notify(self):
        if self.stop:
            return
        self.UpdateProgress()

    def UpdateProgress(self):
        if hasattr(self, 'Thread') is False:
            return
        # if hasattr(self.ProgressPanel, 'ProgressBar') is False:
        #   width, height = self.GetSize()
        # label = 'Check avaliable update. (Step %d/%d)'\
        #   % (self.Thread.step, self.Thread.max_step)
        if len(self.Thread.info.releases) == 0:
            return

        label = self.Thread.info.releases[-1]
        self.DiscogsPanel.TextMessage.SetLabelText(label)
        # self.ProgressPanel.ProgressBar.SetValue(self.Thread.step)
        # if self.Thread.step != self.Thread.max_step: return
        # self.stop = True
        # result = self.Thread.result
        # if result is None:
        #   label = 'Please try later. (Server connection error)'
        #   self.ProgressPanel.TextMessage.SetLabelText(label)
        #   return
        # if result['result'] is False:
        #   label = 'No update available. (Current version is the latest)'
        #   self.ProgressPanel.TextMessage.SetLabelText(label)
        #   return
        # self.DownloadButton.Enable()
        # self.ProgressPanel.Destroy()
        # self.UpdatePanel = UpdatePanel(self)
        # width, height = self.GetSize()
        # self.SetSize((width, 140))
        # width, height = self.GetSize()
        # self.CloseButton.SetPosition((width-95, height-68))
        # self.DownloadButton.SetPosition((width-95-80, height-68))
        # self.AutoCheckUpdate.SetPosition((20, height-63))
        # label = 'New update are available. (Version %s Build %s)'\
        #   % (str(result['version']), str(result['build']))
        # self.UpdatePanel.TextMessage.SetLabelText(label)
        self.Refresh()

    # def OnDownload(self, event):
    #   webbrowser.open(MACROBOX_DOWNLOAD_URL)
    #
    # def OnAutoCheckUpdate(self, event):
    #   if event.IsChecked():
    #       SetPreference('auto_check_update', True)
    #   else: SetPreference('auto_check_update', False)

    def OnClose(self, event):
        self.stop = True
        if self.Thread.isAlive():
            self.Thread._Thread__stop()
        self.EndModal(0)
        self.Destroy()


# https://developer.gracenote.com/web-api

threadCrawlerLock = threading.Lock()


def GracenoteCrawler(path, queue):
    threadCrawlerLock.acquire(0)
    filename = os.path.basename(path)
    filename = os.path.splitext(filename)[0].lower()
    keywords = filename.split(' - ')[0]
    keywords = keywords.split('pres')[0]
    keywords = keywords.split('feat')[0]
    keywords = keywords.split('with')[0]
    keywords = keywords.split('and')[0]
    artist = keywords
    clientID = '104448-DA1673C7F933E828A270DD9EE58C4B8B'
    userID = pygn.register(clientID)
    metadata = pygn.searchArtist(clientID, userID, artist)
    uri = metadata['artist_image_url']
    artwork = urllib.urlopen(uri).read()
    metadata['artist_image'] = artwork
    uri = metadata['album_art_url']
    artwork = urllib.urlopen(uri).read()
    metadata['album_art'] = artwork
    queue.put(metadata)
    # collected = gc.collect()
    gc.collect()


# http://www.discogs.com/developers/index.html

threadCrawlerLock = threading.Lock()


def DiscogsCrawler(path, queue):
    info = Struct()
    threadCrawlerLock.acquire(0)
    filename = os.path.basename(path)
    filename = os.path.splitext(filename)[0].lower()
    keywords = filename.split(' - ')[0]
    keywords = keywords.split('pres')[0]
    keywords = keywords.split('feat')[0]
    keywords = keywords.split('with')[0]
    keywords = keywords.split('and')[0]
    discogs.user_agent = 'muteklab/1.0 +http://www.muteklab.com'
    artist = discogs.Artist(keywords)
    try:
        keys = artist.data.keys()
    except Exception:
        queue.put(None)
        return
    if u'id' in keys:
        info.id = artist.data[u'id']
    if u'name' in keys:
        info.name = artist.data[u'name']
    if u'aliases' in keys:
        info.aliases = artist.data[u'aliases']
    if u'namevariations' in keys:
        info.namevariations = artist.data[u'namevariations']
    if u'realname' in keys:
        info.realname = artist.data[u'realname']
    if u'members' in keys:
        info.members = artist.data[u'members']
    collected = gc.collect()
    info.images = list()
    info.releases = list()
    random.randrange(0, len(artist.releases))
    randomIdx = random.sample(range(len(artist.releases)), len(artist.releases))
    for i in randomIdx:
        try:
            release = artist.releases[i]
            data = '%s %s' % (release.data['year'], release.data['title'])
            info.releases.append(data)
            if 'images' in release.data.keys():
                # uri = release.data['images'][0]['uri']
                uri = release.data['images'][0]['uri150']
                artwork = urllib.urlopen(uri).read()
                info.images.append(artwork)
            queue.put(info)
        except Exception:
            pass
    gc.collect()


# http://developer.echonest.com/docs/v4
# https://github.com/echonest/pyechonest

threadCrawlerLock = threading.Lock()


def EchonestCrawler(path, queue):
    threadCrawlerLock.acquire(0)
    filename = os.path.basename(path)
    filename = os.path.splitext(filename)[0].lower()
    keywords = filename.split(' - ')[0]
    keywords = keywords.split('pres')[0]
    keywords = keywords.split('feat')[0]
    keywords = keywords.split('with')[0]
    keywords = keywords.split('and')[0]
    keywords = u'%s' % (keywords)
    echonest_config.ECHO_NEST_API_KEY = '3NUCRNQMMTWBDJCSL'
    try:
        bk = echonest_artist.Artist(keywords)
    except Exception:
        queue.put(None)
        return
    info = Struct()
    info.artist = bk.name
    info.similar = list()
    for v in bk.similar:
        info.similar.append(v.name)
    queue.put(info)
    collected = gc.collect()


threadCrawlerLock = threading.Lock()


def MetaCrawler(path, queue):
    threadCrawlerLock.acquire(0)
    info = Struct()
    info.google = Struct()
    info.discogs = Struct(idx=None, name=None, aliases=None,
                          namevariations=None, realname=None, members=None, releases=None)
    info.echonest = Struct(artist=None, similar=None)
    info.gracenote = Struct()
    filename = os.path.basename(path)
    filename = os.path.splitext(filename)[0].lower()
    keywords = filename.split(' - ')[0]
    keywords = keywords.split('pres')[0]
    keywords = keywords.split('feat')[0]
    keywords = keywords.split('with')[0]
    keywords = keywords.split('and')[0]
    keywords = u'%s' % (keywords)

    echonest_config.ECHO_NEST_API_KEY = '3NUCRNQMMTWBDJCSL'
    try:
        bk = echonest_artist.Artist(keywords)
        info.echonest.artist = bk.name
        info.echonest.similar = list()
        for v in bk.similar:
            info.echonest.similar.append(v.name)
    except Exception:
        pass
    queue.put(info)

    discogs.user_agent = 'muteklab/1.0 +http://www.muteklab.com'
    artist = discogs.Artist(keywords)
    try:
        keys = artist.data.keys()
        if u'id' in keys:
            info.discogs.idx = artist.data[u'id']
        if u'name' in keys:
            info.discogs.name = artist.data[u'name']
        if u'aliases' in keys:
            info.discogs.aliases = artist.data[u'aliases']
        if u'namevariations' in keys:
            info.discogs.namevariations = artist.data[u'namevariations']
        if u'realname' in keys:
            info.discogs.realname = artist.data[u'realname']
        if u'members' in keys:
            info.discogs.members = artist.data[u'members']
    except Exception:
        pass
    queue.put(info)
    # info.discogs.images = list()
    info.discogs.releases = list()
    try:
        # random.randrange(0, len(artist.releases))
        # randomIdx = random.sample(range(len(artist.releases)), len(artist.releases))
        # for i in randomIdx:
        for i in range(len(artist.releases)):
            release = artist.releases[i]
            data = '%s %s' % (release.data['year'], release.data['title'])
            info.discogs.releases.append(data)
            # if 'images' in release.data.keys():
            #   # uri = release.data['images'][0]['uri']
            #   uri = release.data['images'][0]['uri150']
            #   artwork = urllib.urlopen(uri).read()
            #   info.discogs.images.append(artwork)
            queue.put(info)
    except Exception:
        pass
    queue.put(info)
    gc.collect()


class CRAWLER_Scheduler():

    def __init__(self, parent):
        self.parent = parent
        self.path = None
        self.last_path = None
        self.crawler_timer = time.time()
        self.info = None
        self.queue = None

    def AddCRAWLERTask(self, path):
        self.path = path

    def GetCRAWLERInfo(self):
        if self.queue is None:
            return
        if self.cache.timestamp - self.crawler_timer < 0.5:
            return self.info
        self.crawler_timer = self.cache.timestamp
        try:
            self.info = self.queue.get(False)
        except Exception:
            return self.info
        return self.info

    def RunCRAWLER(self):
        if self.path is None:
            return
        if self.path == self.last_path:
            return
        self.last_path = self.path
        self.info = None
        self.queue = None
        if hasattr(self, 'threadCrawler'):
            if self.threadCrawler.is_alive():
                self.threadCrawler.terminate()
        self.queue = Queue()
        self.threadCrawler = multiprocessing.Process(
            target=MetaCrawler, args=(self.path, self.queue))
        self.threadCrawler.daemon = True
        self.threadCrawler.start()

    def __del__(self):
        if self.threadCrawler.is_alive():
            self.threadCrawler.terminate()
