# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import bisect
import collections
import ctypes
import ctypes.wintypes
import hashlib
import macroboxstyle
import uikit
import mfeats
import multiprocessing
import mutagen
import mutagen.id3
import mutagen.mp3
import os
import stat
import sys
import threading
import time
import win32file
import win32pipe
import weakref
import wx
import wx.lib.newevent

from utilities import PipeMessenger
from utilities import Struct
from utilities import compress_object
from utilities import decompress_object
from utilities import get_user_appdata_path
from utilities import get_user_docapp_path
from utilities import open_shelve
from utilities import open_shelves
from utilities import save_shelve
from utilities import save_shelves


PRODUCT_PLATFORM = 'Windows'
# PRODUCT_NAME = 'QTRAKCS'
PRODUCT_NAME = 'MACROBOX'
PRODUCT_EDITION = 'Player'
PRODUCT_VERSION = '1.0'
PRODUCT_BUILD = '51'
# PRODUCT_BUILD = '40'
# MUTEKLAB_WEB_URL = 'http://muteklab.com:33699/'
# MUTEKLAB_WEB_URL = 'http://192.168.0.100/'
# MUTEKLAB_WEB_URL = 'http://127.0.0.1:8000/'
MUTEKLAB_WEB_URL = 'http://muteklab.com/'
MACROBOX_BUY_URL = MUTEKLAB_WEB_URL + 'macrobox/download/'
MACROBOX_DOWNLOAD_URL = MUTEKLAB_WEB_URL + 'macrobox/download/'
PRODUCT_ONLINE_HELP_URL = MUTEKLAB_WEB_URL + 'macrobox/help/'
PRODUCT_LOG_REQUEST_URL = MUTEKLAB_WEB_URL + 'product/log/req/'
PRODUCT_UPDATE_CHECK_URL = MUTEKLAB_WEB_URL + 'product/update/check/req/'
PRODUCT_LICENSE_CHECK_URL = MUTEKLAB_WEB_URL + 'product/license/check/req/'

TITLE = '%s %s' % (PRODUCT_NAME, PRODUCT_EDITION)

# DEBUG(hang): how often costly things run (mainapp's watchdog writes them); removed
# once found
COUNTS = collections.Counter()
# PREFERENCE_DB = os.path.sep.join([get_user_docapp_path(), 'macroboxplayer.db'])
# PREFERENCE_DB = os.path.sep.join([get_user_docapp_path(), 'macroboxplayer'])
PREFERENCE_DB = os.path.sep.join([get_user_docapp_path(), 'settings'])
# PREFERENCE_DB = os.path.sep.join([os.path.expanduser(r'~'), 'AppData', 'Local', 'PyMusicPlayer'])
# PREFERENCE_DB = os.path.join(os.path.expanduser(r'~'), 'AppData', 'Local', 'PyMusicPlayer', 'settings')

SUPPORTED_PLAYLIST_TYPE = ('m3u',)
SUPPORTED_AUDIO_TYPE = (
    'mp2', 'mp3', 'mp4', 'wav', 'm4a',
    'ape', 'flac', 'aac', 'ac3', 'aiff', 'wma', 'ogg', 'webm',)
MUTAGEN_SUPPORTED_TYPE = ('mp2', 'mp3', 'mpg', 'mpeg', 'webm',)
# mutagen only works with mp2, mp3, mpg, mpeg ?


if sys.platform.startswith('win'):

    FONT_BUTTON = u'Arial'
    FONT_BUTTON_SIZE = 6
    FONT_PLAYINFO = u'Lucida Console'
    FONT_PLAYINFO_SIZE = 9

    if sys.getwindowsversion().major == 5:  # if windows xp
        FONT_ITEM = u'Tahoma'
        FONT_ITEM_SIZE = (6, 12)
        FONT_PLAYINFO = u'Lucida Console'
    else:
        FONT_ITEM = u'Segoe UI'
        FONT_ITEM_SIZE = (6, 12)
        FONT_PLAYINFO = u'Consolas'

elif sys.platform.startswith('darwin'):

    FONT_ITEM = u'Tahoma'
    FONT_ITEM_SIZE = (6, 12)
    FONT_BUTTON = u'ArialMT'
    FONT_BUTTON_SIZE = 8
    FONT_PLAYINFO = u'Monaco'
    FONT_PLAYINFO_SIZE = 10


try:
    packages = os.path.join(sys._MEIPASS, 'packages')
except Exception:
    packages = os.path.join('packages')

sys.path.insert(0, packages)


COLOR_STATUS_BG = (240, 240, 240, 255)
COLOR_TOOLBAR_BG = (240, 240, 240, 255)


class ColumnDefinition(list):

    def SetColumns(self):
        pass  # Override This Method

    def AddColumn(self, key, title='', title_align=0, right_align=False,
                  width=80, min_width=28, max_width=1024, id3=None, show=True,
                  sortable=True, editable=False, removeable=True, searchable=False,
                  private=False):

        local = vars()
        local.pop('self')
        struct = []
        # for k in local.iterkeys():
        for k in local.keys():
            struct.append('%s=%s' % (k, k))
        exec('self.append(Struct(%s))' % (','.join(struct)))


class ListBoxColumn(ColumnDefinition):

    def __init__(self):
        ColumnDefinition.__init__(self)
        self.AddColumn(key='status', title=u'≡', show=False, private=True)
        self.AddColumn(key='order', title=u'#', width=58, max_width=58, right_align=True)
        self.AddColumn(key='filename', title='filename', width=300)
        self.AddColumn(key='duration', title='duration', right_align=True, width=65, max_width=65)
        self.AddColumn(key='tempo', title='tempo', right_align=True,
                       id3=u'TBPM', width=55, max_width=55)
        self.AddColumn(key='key', title='key', id3=u'TKEY', width=55, max_width=55)
        self.AddColumn(key='type', title='type', show=False, private=True)
        # the file's size (MB), shown from the header's menu (private, never shown, before)
        self.AddColumn(key='size', title='size', right_align=True, width=80, max_width=90,
                       show=False)
        # the tags, shown from the header's menu (private, never shown, before); the comment
        # read from its frame (COMM, audio.get_id3)
        self.AddColumn(key='artist', title='artist', id3=u'TPE1', width=160, show=False)
        self.AddColumn(key='title', title='title', id3=u'TIT2', width=200, show=False)
        self.AddColumn(key='album', title='album', id3=u'TALB', width=160, show=False)
        self.AddColumn(key='genre', title='genre', id3=u'TCON', width=100, show=False)
        self.AddColumn(key='comment', title='comment', id3=u'COMM', width=200, show=False)
        self.AddColumn(key='bitrate', title='bitrate', show=False, private=True)
        self.AddColumn(key='samplerate', title='samplerate', show=False, private=True)
        self.AddColumn(key='channel', title='channel', show=False, private=True)
        # the file's path (a station's address), shown from the header's menu (private before)
        self.AddColumn(key='path', title='path', width=300, show=False)
        self.AddColumn(key='mdx', title='mdx', show=False, private=True)
        # pictures, not text (listimages): shown from the header's menu
        self.AddColumn(key='cover', title='cover', width=24, min_width=24, max_width=200,
                       show=False, sortable=False)
        self.AddColumn(key='wave', title='wave', width=160, min_width=40, show=False,
                       sortable=False)


# columns made public since a list was saved private: their definition's look taken
RENEWED_COLUMNS = ('size', 'path', 'artist', 'title', 'album', 'genre')


def AddMissingColumns(innerList):
    # columns added since the list was saved: put at its end, an empty value in each row
    keys = [v.key for v in innerList.columns]
    defaults = dict((v.key, v) for v in ListBoxColumn())
    for column in innerList.columns:
        if column.key in RENEWED_COLUMNS and getattr(column, 'private', False):
            new = defaults[column.key]
            for name in ('private', 'right_align', 'width', 'max_width', 'min_width'):
                setattr(column, name, getattr(new, name))
    for column in ListBoxColumn():
        if column.key in keys:
            continue
        innerList.columns.append(column)
        # rows are tuples, replaced whole (SetItemValueByColumnIdxLocal)
        for rows in (getattr(innerList, 'items', None), getattr(innerList, 'filterCache', None)):
            for i in range(len(rows or [])):
                rows[i] = tuple(rows[i]) + ('',)


class InnerList():

    def __init__(self, value=None):
        if value is not None:
            self.append(value)
        self.rects = Struct(row=wx.Size(-1, 22), offset=wx.Point(0, 0))
        self.title = ''
        columns = GetPreference('columns')
        if columns is None:
            self.columns = ListBoxColumn()
        else:
            self.columns = columns
            AddMissingColumns(self)
        self.selectedItems = []
        self.filterCache = None
        self.filterQuery = None
        self.items = []
        self.lastSortedColumn = [None, None]
        self.focus = Struct(item=-1, shift=-1)
        self.Id = time.process_time()
        if self.lastSortedColumn == [None, None]:
            idx = [i for i, v in enumerate(self.columns) if v.key == 'order'][0]
            self.lastSortedColumn = [idx, 1]


def SetPreference(key, value):
    save_shelve(key, value, PREFERENCE_DB)


def GetPreference(key):
    return open_shelve(key, PREFERENCE_DB)


def SetPreferences(keyvalues):
    save_shelves(keyvalues, PREFERENCE_DB)


def GetPreferences(keys):
    return open_shelves(keys, PREFERENCE_DB)


class FileExecutionMonitor(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent
        self.interval = 1000
        self.Start(self.interval)

    def Notify(self):
        path = None
        try:
            pipe = r'\\.\pipe\pass_to_another_instance'
            self.fileHandle = win32file.CreateFile(pipe,
                                                   win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                                                   0, None, win32file.OPEN_EXISTING,
                                                   win32file.FILE_ATTRIBUTE_NORMAL, None)
            data = win32file.ReadFile(self.fileHandle, 1024, None)
            if data[0] == 0:
                path = decompress_object(data[1])
            win32file.CloseHandle(self.fileHandle)
        except Exception:
            return
        if path is None:
            return
        file_type = os.path.splitext(path)[1][1:]
        if file_type not in SUPPORTED_AUDIO_TYPE:
            return
        self.parent.MainPanel.PlayBox.cue.path = path
        self.parent.MainPanel.PlayBox.OnPlay()


def pass_to_another_instance(initfile):
    pipe = r'\\.\pipe\pass_to_another_instance'
    p = win32pipe.CreateNamedPipe(pipe,
                                  win32pipe.PIPE_ACCESS_DUPLEX,
                                  win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                                  1, 65536, 65536, 300, None)
    win32pipe.ConnectNamedPipe(p, None)
    data = compress_object(initfile)
    win32file.WriteFile(p, data)


def MakeStreamItem(path, order, columns):
    # an internet radio station's row: its name, tags, country, codec and bitrate as kept
    # (radio_stations, else radio_seen: found in the directory), no length, no analysis
    # (status 'stream', never queued)
    # (radio.get_station: both read once and kept; read here a row at a time, a radio tab
    # made at the start read them 400 times, 2 s)
    import radio
    station = radio.get_station(path) or {}
    values = dict(status='stream', order=order, filename=station.get('name') or path,
                  duration='LIVE', type=station.get('codec') or 'radio', path=path,
                  genre=station.get('tags', ''), album=station.get('country', ''),
                  bitrate=str(station.get('bitrate') or ''),
                  mdx='stream-' + hashlib.sha1(path.encode('utf-8')).hexdigest()[:16])
    return [values.get(v.key, '') for v in columns]


def MakeMusicFileItem(path, order, columns):
    if audio.is_stream_path(path):
        return MakeStreamItem(path, order, columns)
    ext = os.path.splitext(path)[1][1:].lower()
    if ext not in SUPPORTED_AUDIO_TYPE:
        return None
    try:
        stats = os.stat(path)  # noqa
    except Exception:
        return None
    size = "%.2f MB" % (stats[stat.ST_SIZE] / 1024.0**2)  # noqa
    file = os.path.basename(path)  # noqa
    filename = os.path.splitext(os.path.basename(path))[0]  # noqa

    id3tagFiledKeys = [v.id3 for v in columns if v.id3 is not None]
    audio_id3 = audio.get_id3(path, id3tagFiledKeys)
    if ext in MUTAGEN_SUPPORTED_TYPE:
        try:
            mutagen_mp3 = mutagen.mp3.MP3(path)
        except Exception:
            return None
        duration = mutagen_mp3.info.length
        bitrate = mutagen_mp3.info.bitrate  # noqa
        samplerate = mutagen_mp3.info.sample_rate
        channel_flag = mutagen_mp3.info.mode
        if channel_flag == 3:
            channel = 1
        else:
            channel = 2
    else:
        duration = audio.get_duration(path)
        channel = audio.get_channel(path)  # noqa
        samplerate = audio.get_fs(path)  # noqa
    if audio_id3 is not None:
        for v in columns:
            if v.id3 is None:
                continue
            exec(u'''%s = audio_id3[u"%s"]''' % (v.key, v.id3))
        try:
            tempo = '%03.5f' % (tempo)  # noqa
        except Exception:
            tempo = ''
    mdx = audio.makemdx(path)
    resp = mfeats.getby_key_value('mdx', mdx, waveform=False)
    if resp is not None:
        if resp.highlight != '':
            highlight = resp.highlight[0]
            highlight = audio.second2time(highlight)
        tempo = resp.tempo
        duration = resp.duration
        try:
            tempo = '%05.1f' % (0.1 * round(tempo * 10))
        except Exception:
            tempo = ''
        key = resp.key  # noqa
        # analyzed by an older version: its values shown, waiting for the analysis
        # again (marked red, queued by the auto analyzer)
        if resp.version == mfeats.MFEATS_VERSION:
            status = 'analyzed'  # noqa
    duration = '%02d:%02d' % (duration / 60, duration % 60)

    item = [None] * len(columns)
    for i, v in enumerate(columns):
        try:
            item[i] = eval(v.key)
        except Exception:
            item[i] = ''
    return item


class CursorEventCatcher():

    def __init__(self, parent):
        self.parent = parent
        self.cursor_stock = Struct(
            ARROW=wx.Cursor(wx.CURSOR_ARROW),
            WAIT=wx.Cursor(wx.CURSOR_WAIT),
            HAND=wx.Cursor(wx.CURSOR_HAND),
            SIZEWE=wx.Cursor(wx.CURSOR_SIZEWE),
            NO_ENTRY=wx.Cursor(wx.CURSOR_NO_ENTRY),
            ARROWWAIT=wx.Cursor(wx.CURSOR_ARROWWAIT))
        self.SetCursorStatus('ARROW')
        self.global_cursor_event_off = False

    def CatchCurserEvent(self, event):
        isInFrameReSize = self.IsInFrameReSize(event)
        if self.IsInListBox(event)\
                and self.parent.ListBox.IsAnyListLocked():
            self.SetCursorWAIT()
        # elif self.parent.ListBox.Header.IsSplitterOnSize():
        #   self.SetCursorSIZEWE()
        # elif self.IsInTextEdit(event):
        #     pass
        elif isInFrameReSize is False and self.parent.pending_item_drag is None:
            self.SetCursorARROW()

    def IsInFrameHeader(self, event):
        xy = (event.x, event.y)
        rect = self.parent.parent.GetScreenRect()
        if self.parent.IsInRect(rect, xy):
            x, y, w, h = rect
            rect = (x + 10, y + 10, w - 20, 40)
            if self.parent.IsInRect(rect, xy):
                return True
        return False

    def IsInFrameReSize(self, event):
        xy = (event.x, event.y)
        rect = self.parent.parent.GetScreenRect()
        if self.parent.IsInRect(rect, xy):
            x, y, w, h = rect
            rect = (x + 10, y + 10, w - 20, h - 20)
            if self.parent.IsInRect(rect, xy) is False:
                return True
        return False

    def IsInTextEdit(self, event):
        if self.parent.ListSearch.SearchText.onClient:
            return True
        if self.parent.ListBox.List.TextEdit is not None:
            return True
        if self.parent.ListTab.TextEdit is not None:
            return True
        return False

    def IsInListBox(self, event):
        return False
        xy = (event.x, event.y)
        rect = self.parent.ListBox.GetScreenRect()
        if self.parent.IsInRect(rect, xy):
            return True
        rect = self.parent.ListTab.GetScreenRect()
        if self.parent.IsInRect(rect, xy):
            return True
        # rect = self.parent.ListSearch.GetScreenRect()
        # if self.parent.IsInRect(rect, xy):
        #     return True
        return False

    def SetCursorARROW(self):
        # once, as the others: set at every event (25 ms) it was put on the screen at once
        # under the mouse, and a child's own (the header's resize cursor over a column's
        # edge) came back after it, the two flickering
        if self.cursor_status == 'ARROW':
            return
        self.parent.SetCursor(self.cursor_stock.ARROW)
        self.SetCursorStatus('ARROW')

    def SetCursorWAIT(self):
        if self.cursor_status == 'WAIT':
            return
        self.parent.SetCursor(self.cursor_stock.WAIT)
        self.SetCursorStatus('WAIT')

    def SetCursorARROWWAIT(self):
        if self.cursor_status == 'ARROWWAIT':
            return
        self.parent.SetCursor(self.cursor_stock.ARROWWAIT)
        self.SetCursorStatus('ARROWWAIT')

    def SetCursorSIZEWE(self):
        if self.cursor_status == 'SIZEWE':
            return
        self.parent.SetCursor(self.cursor_stock.SIZEWE)
        self.SetCursorStatus('SIZEWE')

    def SetCursorStatus(self, status):
        self.cursor_status = status


class ThreadTimer():
    # wx.Timer's Start/Stop/IsRunning/Notify with its beat from two places, Notify once a
    # beat on the GUI thread: a thread's CallAfter, and a wx.Timer. a wx.Timer alone comes
    # as WM_TIMER, which Windows sends only when no other message waits: with the mouse
    # moving over the window it waited, and the events, the list and the analysis with
    # it. a CallAfter alone waits in the loops Windows runs on its own (a drag and drop,
    # a window moved or resized), where WM_TIMER still comes: drag and drop stopped.
    # the analysis' only (MFEATS_Scheduler). the mouse events (EVENT_Scheduler) keep
    # their wx.Timer: on this beat, on its own or with the drag's start and the list
    # tab's sash, a drag in the list failed and the sash hardly followed the mouse

    def __init__(self):
        self.timer_interval = 0
        self.timer_running = False
        self.timer_posted = False
        self.timer_generation = 0
        self.timer_last = 0
        self.timer_notifying = False
        self.timer_wx = wx.Timer()
        self.timer_wx.Bind(wx.EVT_TIMER, lambda event: self.OnTimerBeat())

    def Start(self, milliseconds=-1, oneShot=False):
        if milliseconds > 0:
            self.timer_interval = milliseconds
        self.timer_running = True
        self.timer_wx.Start(max(self.timer_interval, 1))
        # a thread a start: the one before ends at its next beat
        self.timer_generation += 1
        threading.Thread(target=self.KeepTimerBeat, args=(self.timer_generation,),
                         daemon=True).start()
        return True

    def Stop(self):
        self.timer_running = False
        self.timer_wx.Stop()

    def IsRunning(self):
        return self.timer_running

    def GetInterval(self):
        return self.timer_interval

    def KeepTimerBeat(self, generation):
        due = time.perf_counter()
        while self.timer_running and generation == self.timer_generation:
            due += max(self.timer_interval, 1) / 1000.0
            delay = due - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                # behind (the computer was busy): from now on, no catching up
                due = time.perf_counter()
            if self.timer_posted:
                continue
            self.timer_posted = True
            try:
                wx.CallAfter(self.OnTimerPosted)
            except Exception:
                # no app any more (it is closing)
                return

    def OnTimerPosted(self):
        self.timer_posted = False
        self.OnTimerBeat()

    def OnTimerBeat(self):
        # the two beats of one: whichever comes first. and not in its own Notify (a
        # loop Windows runs from it lets the wx.Timer's beat in)
        now = time.perf_counter()
        if self.timer_running is False or now - self.timer_last < self.timer_interval * 0.0006:
            return
        if self.timer_notifying:
            return
        self.timer_last = now
        self.timer_notifying = True
        try:
            self.Notify()
        finally:
            self.timer_notifying = False

    def Notify(self):
        pass


class PopupMenuEventCatcherTimer(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent
        self.interval = 100
        self.Start(self.interval)

    def Notify(self):
        self.parent.CatchPopupMenuEvent()
        self.parent.CatchItemDragEvent()


class PopupMenuEventCatcher():

    def __init__(self, parent):
        self.parent = parent
        self.pending_popup_event = None
        self.pending_item_drag = None
        self.Timer = PopupMenuEventCatcherTimer(self)

    def SetPopupMenu(self, obj, xy, closed=None):
        # closed: called when the menu is gone (its opener's arrow turned back)
        if self.pending_popup_event is not None:
            self.pending_popup_event.object.Destroy()
            # (one not shown yet, put aside: its opener told too)
            if getattr(self.pending_popup_event, 'closed', None) is not None:
                self.pending_popup_event.closed()
        self.pending_popup_event = Struct(object=obj, x=xy[0], y=xy[1], pending=False,
                                          closed=closed)

    def CatchPopupMenuEvent(self):
        if self.pending_popup_event is None:
            return
        if self.pending_popup_event.pending is True:
            return
        self.pending_popup_event.pending = True

        x, y = self.GetScreenPosition()
        x = self.pending_popup_event.x - x
        y = self.pending_popup_event.y - y
        self.PopupMenu(self.pending_popup_event.object, (x, y))
        self.pending_popup_event.object.Destroy()
        closed = getattr(self.pending_popup_event, 'closed', None)
        self.pending_popup_event = None
        if closed is not None:
            closed()

    def SetItemDrag(self, paths, del_source=False):
        if self.pending_item_drag is not None:
            return
        self.pending_item_drag = Struct(paths=paths, del_source=del_source, pending=False)

    def CatchItemDragEvent(self):
        if self.pending_item_drag is None:
            return
        if self.pending_item_drag.pending is True:
            return

        self.pending_item_drag.pending = True

        data = wx.FileDataObject()
        for item in self.pending_item_drag.paths:
            data.AddFile(item)

        dropSource = wx.DropSource(None)
        dropSource.SetData(data)
        dropSource.DoDragDrop(False)

        if self.pending_item_drag.del_source:
            for item in self.pending_item_drag.paths:
                try:
                    os.remove(item)
                except Exception:
                    pass

        self.pending_item_drag = None

    def OnDragItem(self, event):
        data = wx.FileDataObject()
        if event is None:
            obj = None
        else:
            obj = event.GetEventObject()
        selected = self.parent.GetSelectedItemsKey('path')
        if selected is None:
            return
        for item in selected:
            data.AddFile(item)
        dropSource = wx.DropSource(obj)
        dropSource.SetData(data)
        dropSource.DoDragDrop(False)


# a worker idle this long is told to end
MFEATS_WORKER_IDLETIME = 10.0
# the DeepRhythm model process's torch threads at most (StartModel)
MODEL_THREADS_MOST = 4


class MFEATS_Scheduler(ThreadTimer):

    def __init__(self, parent):
        ThreadTimer.__init__(self)
        self.parent = parent
        self.interval = 50
        self.max_cores = multiprocessing.cpu_count()
        self.SetOptimalProcsLimit()
        # self.procs_limit = self.max_cores
        self.auto_analyzer_on = False
        self.procpath = []
        self.taskpath = []
        self.proclist = []
        # asked for again though analyzed (Analyze): all of it, not the grid alone
        self.forcedpath = set()
        self.stop = False
        self.redraw_pending = False
        # DeepRhythm's process for the workers (StartModel): started with the first,
        # ended once they are all gone
        self.model = None
        self.model_lock = threading.Lock()
        self.model_address = mfeats.get_deeprhythm_address(os.getpid())
        self.Start(self.interval)

    def SetOptimalProcsLimit(self):
        max_cores = multiprocessing.cpu_count()
        if max_cores >= 4:
            procs_limit = int(max_cores * 0.75)
        else:
            procs_limit = int(max_cores * 0.5)
        if procs_limit < 1:
            procs_limit = 1
        self.procs_limit = procs_limit
        return

    def Notify(self):
        if self.stop:
            return
        self.HandleFinishedJob()
        self.SendJobToProcessor()

    # def watch_dead_proclist(self):
    #   if self.proclist == []: return
    #   for i in range(len(self.proclist)-1, -1, -1):
    #       if self.proclist[i].proc.is_alive() is False:
    #           self.proclist[i].proc._Thread__stop()
    #           this = self.proclist.pop(i)
    #           this.path
    #           # self.Messenger.send_message(this.path, CLIENT_ADDRESS)

    def StopNotify(self):
        self.stop = True

    def StartNotify(self):
        self.stop = False

    def IsAutoAnalyzerOn(self):
        return self.auto_analyzer_on

    def SetAutoAnalyzerOn(self):
        self.auto_analyzer_on = True
        SetPreference('auto_analyzer_on', True)

    def SetAutoAnalyzerOff(self):
        self.auto_analyzer_on = False
        self.taskpath = []
        SetPreference('auto_analyzer_on', False)

    def AutoAnalyzer(self):
        if self.IsAutoAnalyzerOn() is False:
            return
        # a list's status is saved with it: songs since outdated (a newer analysis, or a
        # grid not made yet) marked to be analyzed again, ahead of being played
        threading.Thread(target=self.FindOutdated, daemon=True).start()

    def FindOutdated(self):
        try:
            done = mfeats.get_done_mdx()
        except Exception:
            done = None
        wx.CallAfter(self.QueueOutdated, done)

    def QueueOutdated(self, done, asked=False):
        # asked: by Check Analyzer Versions, the auto analyzer on or not
        if not self.parent or (self.IsAutoAnalyzerOn() is False and asked is False):
            return
        lists = self.parent.ListBox.innerList
        if done is not None:
            for listIdx in range(len(lists)):
                statusIdx = self.parent.ListBox.GetColumnKeyToIdx('status', listIdx)
                mdxIdx = self.parent.ListBox.GetColumnKeyToIdx('mdx', listIdx)
                items = lists[listIdx].items
                for i in range(len(items)):
                    if items[i][statusIdx] == 'analyzed' and items[i][mdxIdx] not in done:
                        # rows are tuples, replaced whole
                        item = list(items[i])
                        item[statusIdx] = ''
                        items[i] = tuple(item)
        for listIdx in range(len(lists)):
            itemsIdx = self.parent.ListBox\
                .GetItemsIdxByColumnKeyValue('status', '', listIdx)
            if itemsIdx == []:
                continue
            pathIdx = self.parent.ListBox.GetColumnKeyToIdx('path', listIdx)
            # one thread for them all: a thread an item was thousands of threads
            # on a big list, each looking its row up
            paths = [self.parent.ListBox.innerList[listIdx].items[itemIdx][pathIdx]
                     for itemIdx in itemsIdx]
            t = threading.Thread(target=self.AddMFEATSTasks, args=(paths,), daemon=True)
            t.start()
            # for itemIdx in itemsIdx:
            #     path = self.parent.ListBox.innerList[listIdx].items[itemIdx][pathIdx]
            #     # self.AddMFEATSTask(path, urgent=False)
            #     t = threading.Thread(
            #         target=self.AddMFEATSTask,
            #         args=(path,), kwargs={'urgent': False},
            #         daemon=True
            #     )
            #     t.start()

    def AddMFEATSTasks(self, paths):
        for path in paths:
            self.AddMFEATSTask(path, urgent=False, redraw=False)
        wx.CallAfter(self.RequestListRedraw)

    def SetProcsLimit(self, value):
        self.procs_limit = value

    def RequestListRedraw(self):
        # the list drawn again for the analysis at most four times a second, on
        # the GUI thread (songs are queued from threads too): drawn at once for
        # every song queued, sent and done it was 20 ms a time, at times 100,
        # and the visualizers stuttered with it
        if self.redraw_pending:
            return
        self.redraw_pending = True
        wx.CallLater(250, self.RedrawList)

    def RedrawList(self):
        self.redraw_pending = False
        if not self.parent:
            return
        self.parent.ListBox.List.DirectDraw()

    def AddMFEATSTask(self, path, urgent=False, forced=False, redraw=True):
        # a station's stream has nothing to analyze
        if audio.is_stream_path(path):
            return
        if redraw:
            wx.CallAfter(self.RequestListRedraw)
        resp = mfeats.getby_key_value('path', path, waveform=False)
        # analyzed by an older version: analyzed again; analyzed, its grid not: the grid
        if resp is not None and resp.version == mfeats.MFEATS_VERSION and forced is False:
            if resp.error != 0 or mfeats.is_grid_current(resp.mdx):
                return
        if forced:
            self.forcedpath.add(path)
        pnt = [i for i, v in enumerate(self.taskpath) if v == path]
        if urgent is False:
            if len(pnt) > 0:
                return
            if self.IsPathTasking(path):
                return
            self.taskpath.append(path)
        else:
            if self.IsPathProcessing(path):
                return
            for i in range(len(pnt) - 1, -1, -1):
                self.taskpath.pop(pnt[i])
            self.taskpath.insert(0, path)

    def IsPathProcessing(self, path):
        if path in self.GetProcPath():
            return True
        return False

    def IsPathTasking(self, path):
        if path in self.GetProcPath():
            return True
        if path in self.GetTaskPath():
            return True
        return False

    def HandleFinishedJob(self):
        if self.proclist == []:
            return
        now = time.time()
        for i in range(len(self.proclist) - 1, -1, -1):
            this = self.proclist[i]
            # still being started (StartWorker)
            if this.proc is None:
                continue
            alive = this.proc.is_alive()
            done = False
            try:
                done = alive and this.conn.poll()
                if done:
                    this.conn.recv()
            except (EOFError, OSError):
                alive = False
            # its song done, or the worker died with it (the song is left, as a process's was)
            if this.path is not None and (done or alive is False):
                path, this.path, this.idle = (this.path, None, now)
                idx = [i for i, v in enumerate(self.procpath) if v == path]
                if idx != []:
                    path = self.procpath.pop(idx[0])
                    self.UpdateItemsValue(path)
            if alive is False:
                # self.proclist[i].proc._Thread__stop()
                this.conn.close()
                self.proclist.pop(i)
            elif this.retired is False and this.path is None\
                    and now - this.idle >= MFEATS_WORKER_IDLETIME:
                # told to end, not ended by itself: no song is sent to one ending
                this.retired = True
                try:
                    this.conn.send(None)
                except (EOFError, OSError):
                    this.proc.terminate()
        # every worker gone (a new one is in the list before it starts): the model too
        if self.proclist == [] and self.model is not None:
            self.StopModel()
        # died with workers left: started again (on a thread, a start is 17 ms)
        elif self.model is not None and self.model.proc.is_alive() is False:
            threading.Thread(target=self.StartModel, daemon=True).start()

    def SendJobToProcessor(self):
        if self.IsProcsFull():
            return
        if self.HasTask() is False:
            return
        path = self.taskpath.pop(0)
        if path in self.procpath:
            return
        # self.proclist.append(Struct(path=path, proc=mfeats.Process(path)))
        # self.proclist.append(Struct(path=path, proc=mfeats.Thread(path)))
        # self.proclist[-1].daemon = True
        # the process's own flag (the Struct's was set): ended with the app
        # self.proclist[-1].proc.daemon = True
        # self.proclist[-1].proc.start()
        idle = [v for v in self.proclist if v.path is None and v.retired is False]
        if idle == []:
            # started on a thread with its song: a start held the window about
            # 17 ms, a frame of the visualizers
            conn, worker_conn = multiprocessing.Pipe()
            this = Struct(proc=None, conn=conn, path=path, idle=0, retired=False)
            self.proclist.append(this)
            threading.Thread(target=self.StartWorker, args=(this, worker_conn), daemon=True).start()
            self.procpath.append(path)
            self.UpdateItemsValue(path)
            return
        try:
            idle[0].conn.send(self.GetJobMessage(path))
        except (EOFError, OSError):
            # died idle: the song waits for the next worker
            idle[0].retired = True
            self.taskpath.insert(0, path)
            return
        idle[0].path = path
        self.procpath.append(path)
        self.UpdateItemsValue(path)

    def StartModel(self):
        # from the workers' starting threads, more than one at a time
        with self.model_lock:
            if self.model is not None and self.model.proc.is_alive():
                return
            # its process gone (it died): started again at the same address
            if self.model is not None:
                self.model.control.close()
            control, model_control = multiprocessing.Pipe()
            # torch on the cores the workers leave (it takes them all by default), 4 at
            # most: on 32 cores it took 30 and the whole computer to 100% at times
            threads = max(1, min(MODEL_THREADS_MOST, self.max_cores - self.procs_limit - 1))
            proc = multiprocessing.Process(
                target=mfeats.deeprhythm_server,
                args=(model_control, self.model_address, threads), daemon=True)
            proc.start()
            model_control.close()
            self.model = Struct(proc=proc, control=control)

    def StopModel(self):
        with self.model_lock:
            if self.model is None:
                return
            try:
                self.model.control.send(None)
            except (EOFError, OSError):
                self.model.proc.terminate()
            self.model.control.close()
            self.model = None

    def StartWorker(self, this, worker_conn):
        self.StartModel()
        proc = multiprocessing.Process(
            target=mfeats.mfeats_worker, args=(worker_conn, self.model_address), daemon=True)
        proc.start()
        worker_conn.close()
        try:
            # its song as it is now (renamed meanwhile: ResetItemValue)
            this.conn.send(self.GetJobMessage(this.path))
        except (EOFError, OSError):
            # died at once: seen as dead (HandleFinishedJob), its song left
            pass
        this.proc = proc

    def GetJobMessage(self, path):
        # the song's path for its whole analysis, ('grid', path) when only its grid is due
        if path in self.forcedpath:
            self.forcedpath.discard(path)
            return path
        resp = mfeats.getby_key_value('path', path, waveform=False)
        if resp is not None and resp.version == mfeats.MFEATS_VERSION and resp.error == 0:
            return ('grid', path)
        return path

    def ResetItemValue(self, old_path, new_path):
        idx = [i for i in range(len(self.taskpath))
               if self.taskpath[i] == old_path]
        for i in idx:
            self.taskpath[i] = new_path
        idx = [i for i in range(len(self.procpath))
               if self.procpath[i] == old_path]
        for i in idx:
            self.procpath[i] = new_path
        # the running job too, or its slot was never given back
        for proc in self.proclist:
            if proc.path == old_path:
                proc.path = new_path

    def UpdateItemsValue(self, path):
        mdx = audio.makemdx(path)
        resp = mfeats.getby_key_value('mdx', mdx, waveform=False)
        # the list's waveform cell made again from the new analysis
        images = getattr(self.parent.ListBox.List, 'images', None)
        if images is not None:
            images.Forget(mdx)
        if resp is None:
            # analyzing status uses GetProcPath
            self.parent.ListBox.SetListItemsValueWhereColumnKey(
                ('mdx', mdx), ('status', ''))
            self.RequestListRedraw()
            return

        key = resp.key
        tempo = resp.tempo
        duration = resp.duration
        duration = '%02d:%02d' % (duration / 60, duration % 60)
        try:
            tempo = '%05.1f' % (0.1 * round(tempo * 10))
        except Exception:
            tempo = ''
        # an older version's row: not analyzed yet (MakeMusicFileItem)
        status = 'analyzed' if resp.version == mfeats.MFEATS_VERSION else ''
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('status', status))
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('tempo', tempo))
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('key', key))
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('duration', duration))
        self.RequestListRedraw()

    def HasTask(self):
        return self.taskpath != []

    def HasProc(self):
        return self.procpath != []

    def IsProcsFull(self):
        return len(self.procpath) >= self.procs_limit

    def GetProcPath(self):
        return self.procpath

    def GetTaskPath(self):
        return self.taskpath

    def GetWorkingCount(self):
        return len(self.procpath), len(self.taskpath), self.procs_limit

    def GetMaxCores(self):
        return self.max_cores

    def GetProcsLimit(self):
        return self.procs_limit

    def get_procs_path(self):
        return self.procpath

    def terminate(self):
        self.stop = True
        self.StopModel()
        # for i in range(len(self.proclist)):
        #     self.proclist[i].proc.join()
        # an analysis still running is left (its row is written again later)
        # every worker ends with the window, the idle ones too
        for i in range(len(self.proclist)):
            if self.proclist[i].proc is not None:
                self.proclist[i].proc.terminate()
        for i in range(len(self.proclist)):
            if self.proclist[i].proc is not None:
                self.proclist[i].proc.join(1.0)
            self.proclist[i].conn.close()
        self.proclist = []
        # for i in range(len(self.proclist)):
        #   self.proclist[i].proc._Thread__stop()

    def __del__(self):
        self.terminate()


class MFEATS_Network_Scheduler(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        # mfeats.boot_scheduler()
        self.parent = parent
        self.interval = 50
        self.procs_watch_interval = 1000
        self.procs_watch_timer = 0
        self.max_cores = multiprocessing.cpu_count()
        # self.procs_limit = self.max_cores
        self.SetOptimalProcsLimit()
        self.auto_analyzer_on = False
        self.procpath = []
        self.taskpath = []
        self.stop = False
        self.lock = False
        self.wakeup = False
        self.Start(self.interval)
        self.Messenger = PipeMessenger('macrobox_mfeats')
        # self.Messenger = SocketMessenger(mfeats.CLIENT_ADDRESS)
        self.Messenger.start()

    def SetOptimalProcsLimit(self):
        max_cores = multiprocessing.cpu_count()
        if max_cores >= 4:
            procs_limit = int(max_cores * 0.75)
        else:
            procs_limit = int(max_cores * 0.5)
        if procs_limit < 1:
            procs_limit = 1
        self.procs_limit = procs_limit

    def Notify(self):
        if self.stop:
            return
        self.WatchServer()
        self.HandleFailedJob()
        self.HandleFinishedJob()
        if self.wakeup:
            return
        self.SendJobToServer()

    def StopNotify(self):
        self.stop = True

    def StartNotify(self):
        self.stop = False

    def IsAutoAnalyzerOn(self):
        return self.auto_analyzer_on

    def SetAutoAnalyzerOn(self):
        self.auto_analyzer_on = True
        SetPreference('auto_analyzer_on', True)

    def SetAutoAnalyzerOff(self):
        self.auto_analyzer_on = False
        self.taskpath = []
        SetPreference('auto_analyzer_on', False)

    def AutoAnalyzer(self):
        if self.IsAutoAnalyzerOn() is False:
            return
        for listIdx in range(len(self.parent.ListBox.innerList)):
            itemsIdx = self.parent.ListBox\
                .GetItemsIdxByColumnKeyValue('status', '', listIdx)
            if itemsIdx == []:
                continue
            pathIdx = self.parent.ListBox.GetColumnKeyToIdx('path', listIdx)
            for itemIdx in itemsIdx:
                path = self.parent.ListBox.innerList[listIdx].items[itemIdx][pathIdx]
                # self.AddMFEATSTask(path, urgent=False)
                t = threading.Thread(
                    target=self.AddMFEATSTask,
                    args=(path,), kwargs={'urgent': False},
                    daemon=True
                )
                t.start()

    def SetProcsLimit(self, value):
        self.procs_limit = int(value)

    def AddMFEATSTask(self, path, urgent=False, forced=False):
        if audio.is_stream_path(path):
            return
        resp = mfeats.getby_key_value('path', path, waveform=False)
        if resp is not None and forced is False:
            return
        pnt = [i for i, v in enumerate(self.taskpath) if v == path]
        if urgent is False:
            if len(pnt) > 0:
                return
            if self.IsPathTasking(path):
                return
            self.taskpath.append(path)
        else:
            if self.IsPathProcessing(path):
                return
            for i in range(len(pnt) - 1, -1, -1):
                self.taskpath.pop(pnt[i])
            self.taskpath.insert(0, path)

    def IsPathProcessing(self, path):
        if path in self.GetProcPath():
            return True
        return False

    def IsPathTasking(self, path):
        if path in self.GetProcPath():
            return True
        if path in self.GetTaskPath():
            return True
        return False

    def HandleFailedJob(self):
        if self.wakeup:
            return
        if self.Messenger.has_failed() is False:
            return
        self.Messenger.resend_failed()
        self.wakeup = True

    def HandleFinishedJob(self):
        if self.Messenger.has_message() is False:
            return
        message, address = self.Messenger.pop_message()
        if message == 'terminating':
            return
        elif message == 'connected':
            return
        elif message == 'master_alive':
            return
        else:
            path = message
        idx = [i for i, v in enumerate(self.procpath) if v == path]
        if idx == []:
            return
        path = self.procpath.pop(idx[0])
        # print len(self.taskpath), len(self.procpath)
        # print 'HandleFinishedJob job finished message received: %s' % (message)
        self.UpdateItemsValue(path)

    def SendJobToServer(self):
        if self.IsProcsFull():
            return
        if self.HasTask() is False:
            return
        path = self.taskpath.pop(0)
        if path in self.procpath:
            return
        self.Messenger.send_message(path, 'macrobox_mfeats')
        # self.Messenger.send_message(path, mfeats.SERVER_ADDRESS)
        self.procpath.append(path)
        self.UpdateItemsValue(path)

    def WatchServer(self):
        self.procs_watch_timer += self.interval
        if self.procs_watch_timer > self.procs_watch_interval:
            self.procs_watch_timer = 0
            if self.wakeup is False and self.HasProc():
                self.Messenger.send_message('connected', 'macrobox_mfeats')
                # self.Messenger.send_message('connected', mfeats.SERVER_ADDRESS)
                # if 'connected' not in self.Messenger.get_message():
                #   self.wakeup = True
        if self.wakeup is False:
            return
        # if mfeats.is_scheduler_running(): return
        # self.wakeup = False
        # mfeats.boot_scheduler()
        # for path in self.GetProcPath():
        #   self.Messenger.send_socket_message(path, mfeats.SERVER_ADDRESS)

    def ResetItemValue(self, old_path, new_path):
        idx = [i for i in range(len(self.taskpath))
               if self.taskpath[i] == old_path]
        for i in idx:
            self.taskpath[i] = new_path
        idx = [i for i in range(len(self.procpath))
               if self.procpath[i] == old_path]
        for i in idx:
            self.procpath[i] = new_path

    def UpdateItemsValue(self, path):
        mdx = audio.makemdx(path)
        resp = mfeats.getby_key_value('mdx', mdx, waveform=False)
        if resp is None:
            # analyzing status uses GetProcPath
            self.parent.ListBox.SetListItemsValueWhereColumnKey(
                ('mdx', mdx), ('status', ''))
            self.parent.ListBox.List.DirectDraw()
            # self.parent.ListBox.List.reInitBuffer = True
            return

        key = resp.key
        tempo = resp.tempo
        duration = resp.duration
        duration = '%02d:%02d' % (duration / 60, duration % 60)
        try:
            tempo = '%05.1f' % (0.1 * round(tempo * 10))
        except Exception:
            tempo = ''
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('status', 'analyzed'))
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('tempo', tempo))
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('key', key))
        self.parent.ListBox.SetListItemsValueWhereColumnKey(
            ('mdx', mdx), ('duration', duration))
        self.parent.ListBox.List.DirectDraw()
        # self.parent.ListBox.List.reInitBuffer = True

    def HasTask(self):
        return self.taskpath != []

    def HasProc(self):
        return self.procpath != []

    def IsProcsFull(self):
        return len(self.procpath) >= self.procs_limit

    def GetProcPath(self):
        return self.procpath

    def GetTaskPath(self):
        return self.taskpath

    def GetWorkingCount(self):
        return len(self.procpath), len(self.taskpath), self.procs_limit

    def GetMaxCores(self):
        return self.max_cores

    def GetProcsLimit(self):
        return self.procs_limit

    def get_procs_path(self):
        return self.procpath

    def __del__(self):
        self.Messenger.send_message('terminate', 'macrobox_mfeats', urgent=True)
        # self.Messenger.send_message('terminate',\
        #   mfeats.SERVER_ADDRESS, urgent=True)
        time.sleep(0.1)
        self.Messenger.terminate()
        self.Messenger._Thread__stop()


evt_global, EVT_GLOBAL = wx.lib.newevent.NewEvent()

# wx assigns event type ids at runtime, so they shift between wxWidgets builds
KEY_EVENT_TYPES = (wx.EVT_KEY_DOWN.evtType[0], wx.EVT_KEY_UP.evtType[0],
                   wx.EVT_CHAR.evtType[0], wx.EVT_CHAR_HOOK.evtType[0])
MOUSE_EVENT_TYPES = tuple(wx.EVT_MOUSE_EVENTS.evtType)


# the mouse is read off the whole screen (wx.GetMouseState), not from the player's own
# events: a press over another window lying on the player (the radio's, a menu) was taken
# by the box under it too
user32 = ctypes.windll.user32 if hasattr(ctypes, 'windll') else None
if user32 is not None:
    user32.WindowFromPoint.argtypes = [ctypes.wintypes.POINT]
    user32.WindowFromPoint.restype = ctypes.wintypes.HWND
    user32.GetAncestor.argtypes = [ctypes.wintypes.HWND, ctypes.c_uint]
    user32.GetAncestor.restype = ctypes.wintypes.HWND


def is_pointer_covered(x, y, window):
    # another top-level window under the pointer than the player's own
    if user32 is None or not window:
        return False
    try:
        root = user32.GetAncestor(user32.WindowFromPoint(ctypes.wintypes.POINT(x, y)), 2)
        main = wx.GetTopLevelParent(window).GetHandle()
    except Exception:
        return False
    return bool(root) and root != main


class PressFilter(wx.EventFilter):

    '''the player's own presses (wx's events, any window of it): told to the mouse's poll
    (EVENT_Scheduler), which reads the button's state only every interval. its timer comes
    last (a timer's message waits for every other): with the player busy drawing, a click
    let go before the next read was never seen, a button not pressed at the first click'''

    TYPES = {wx.wxEVT_LEFT_DOWN: 'left', wx.wxEVT_LEFT_DCLICK: 'left',
             wx.wxEVT_RIGHT_DOWN: 'right', wx.wxEVT_RIGHT_DCLICK: 'right'}

    def __init__(self, scheduler):
        wx.EventFilter.__init__(self)
        self.scheduler = scheduler

    def FilterEvent(self, event):
        button = self.TYPES.get(event.GetEventType())
        if button is not None:
            self.scheduler.NotePress(button)
        return self.Event_Skip


class EVENT_Scheduler(wx.Timer, CursorEventCatcher):

    # a press told by PressFilter: taken as down at the next read when the read finds it
    # let go already, if it is this new (seconds; older: the read saw it itself)
    PRESS_FRESH = 0.4

    def __init__(self, parent):
        wx.Timer.__init__(self)
        CursorEventCatcher.__init__(self, parent)
        self.parent = parent
        self.interval = 25
        self.cache = self.InitEvent()
        self.last_screen_rect = None
        # presses wx told of, not yet read: {button: when}
        self.presses = {}
        self.press_filter = PressFilter(self)
        wx.EvtHandler.AddFilter(self.press_filter)
        self.Start(self.interval)
        self.onsize = False
        # self.path = None
        self.stop = False
        self.LeftUpDelayedCounter = None  # MAC

    def StopNotify(self):
        self.stop = True
        # (off wx before the app goes: a filter left in its list crashed it at the end)
        if self.press_filter is not None:
            wx.EvtHandler.RemoveFilter(self.press_filter)
            self.press_filter = None

    def NotePress(self, button):
        # (read at once after wx's press is handled: not at the timer's turn)
        if not self.presses:
            wx.CallAfter(self.Notify)
        self.presses[button] = time.time()

    def StartNotify(self):
        self.stop = False

    def Notify(self):
        if self.stop:
            return
        event = self.MakeEvent()
        event.covered = is_pointer_covered(event.x, event.y, self.parent)
        self.CatchCurserEvent(event)
        if not hasattr(self.parent, 'StatusBox'):
            return
        self.parent.DistributeEvent(event)

    def InitEvent(self):
        event = evt_global(EventType=[0], timestamp=time.time(), dragging=False,
                           LeftDrag=False, LeftIsDrag=False, LeftDClick=False, RightDrag=False,
                           RightIsDrag=False, RightDClick=False, MiddleDrag=False,
                           MiddleIsDrag=False, MiddleDClick=False,
                           x=-1, y=-1, X=None, Y=None, rectIdx=None,
                           click=Struct(x=None, y=None, timestamp=None, button=None),
                           drag=Struct(x=None, y=None, X=None, Y=None, rectIdx=None),
                           down=Struct(x=None, y=None, X=None, Y=None, rectIdx=None),
                           LeftDown=False, RightDown=False, MiddleDown=False,
                           LeftIsDown=False, RightIsDown=False, MiddleIsDown=False,
                           LeftUp=False, RightUp=False, MiddleUp=False, CmdDown=False,
                           AltDown=False, ShiftDown=False, ControlDown=False, KeyCode=None,
                           LeftUpDelayed=False)
        return event

    def MakeEvent(self):
        event = self.InitEvent()
        state = wx.GetMouseState()

        event.CmdDown = state.cmdDown
        event.AltDown = state.altDown
        event.ShiftDown = state.shiftDown
        event.ControlDown = state.controlDown
        event.LeftIsDown = state.LeftIsDown()
        event.RightIsDown = state.RightIsDown()
        event.MiddleIsDown = state.MiddleIsDown()
        event.x, event.y = (state.x, state.y)
        # a press wx told of, let go before this read: down for this read (up at the next)
        presses, self.presses = self.presses, {}
        now = time.time()
        for button, when in presses.items():
            if now - when > self.PRESS_FRESH:
                continue
            if button == 'left' and not self.cache.LeftIsDown:
                event.LeftIsDown = True
            elif button == 'right' and not self.cache.RightIsDown:
                event.RightIsDown = True

        if self.cache.LeftIsDown is False and event.LeftIsDown:
            event.LeftDown = True
        elif self.cache.LeftIsDown and event.LeftIsDown is False:
            event.LeftUp = True
        if self.cache.RightIsDown is False and event.RightIsDown:
            event.RightDown = True
        elif self.cache.RightIsDown and event.RightIsDown is False:
            event.RightUp = True
        if self.cache.MiddleIsDown is False and event.MiddleIsDown:
            event.MiddleDown = True
        elif self.cache.MiddleIsDown and event.MiddleIsDown is False:
            event.MiddleUp = True

        if event.LeftUp:
            self.LeftUpDelayedCounter = 0
        if self.LeftUpDelayedCounter is not None:
            self.LeftUpDelayedCounter += 1
            if self.LeftUpDelayedCounter >= 6:
                self.LeftUpDelayedCounter = None
                event.LeftUpDelayed = True

        if event.LeftDown or event.RightDown or event.MiddleDown:
            event.down.x, event.down.y = (event.x, event.y)
        elif (event.LeftIsDown or event.RightIsDown or event.MiddleIsDown) is False:
            event.down.x, event.down.y = (None, None)
        else:
            event.down.x, event.down.y = (self.cache.down.x, self.cache.down.y)

        isClickedSameButton = self.IsClickedSameButton(event)
        isMoved = (event.x != self.cache.x) or (event.y != self.cache.y)

        if isMoved:
            pass
        elif isClickedSameButton is False\
                and (event.LeftDown or event.RightDown or event.MiddleDown):
            self.SetClickEvent(event)
        elif self.cache.click.button is None\
                and (event.LeftDown or event.RightDown or event.MiddleDown):
            self.SetClickEvent(event)
        else:
            self.KeepClickEvent(event)
        if self.cache.click.timestamp is None:
            isInTime = False
        else:
            isInTime = (event.timestamp - self.cache.click.timestamp < 0.5)
        if isInTime is False and self.cache.click.timestamp is not None:
            self.InitClickEvent(event)
        if isClickedSameButton and isInTime and event.LeftDown:
            event.LeftDClick = True
            self.InitClickEvent(event)
        elif isClickedSameButton and isInTime and event.RightDown:
            event.RightDClick = True
            self.InitClickEvent(event)
        elif isClickedSameButton and isInTime and event.MiddleDown:
            event.MiddleDClick = True
            self.InitClickEvent(event)
        elif isClickedSameButton:
            self.SetClickEvent(event)

        if (event.LeftIsDown and self.cache.LeftIsDown) and isMoved:
            event.LeftIsDrag = True
        elif event.LeftIsDown:
            event.LeftIsDrag = self.cache.LeftIsDrag
        if (event.RightIsDown and self.cache.RightIsDown) and isMoved:
            event.RightIsDrag = True
        elif event.RightIsDown:
            event.RightIsDrag = self.cache.RightIsDrag
        if (event.MiddleIsDown and self.cache.MiddleIsDown) and isMoved:
            event.MiddleIsDrag = True
        elif event.MiddleIsDown:
            event.MiddleIsDrag = self.cache.MiddleIsDrag
        if event.LeftIsDrag and self.cache.LeftIsDrag is False:
            event.LeftDrag = True
        if event.RightIsDrag and self.cache.RightIsDrag is False:
            event.RightDrag = True
        if event.MiddleIsDrag and self.cache.MiddleIsDrag is False:
            event.MiddleDrag = True
        if event.LeftDrag or event.RightDrag or event.MiddleDrag:
            event.drag.x, event.drag.y = (event.down.x, event.down.y)
        elif event.LeftIsDrag or event.RightIsDrag or event.MiddleIsDrag:
            event.drag.x, event.drag.y = (self.cache.drag.x, self.cache.drag.y)
        if event.LeftUp or event.RightUp or event.MiddleUp:
            event.down.x, event.down.y = (self.cache.down.x, self.cache.down.y)
            event.drag.x, event.drag.y = (self.cache.drag.x, self.cache.drag.y)

        self.cache = event
        return event

    def InitClickEvent(self, event):
        event.click.x, event.click.y = (None, None)
        event.click.timestamp, event.click.button = (None, None)
        return event

    def SetClickEvent(self, event):
        if event.LeftDown:
            event.click.button = 'Left'
        if event.RightDown:
            event.click.button = 'Right'
        if event.MiddleDown:
            event.click.button = 'Middle'
        event.click.timestamp = event.timestamp
        event.click.x, event.click.y = (event.x, event.y)
        return event

    def KeepClickEvent(self, event):
        event.click.button = self.cache.click.button
        event.click.timestamp = self.cache.click.timestamp
        event.click.x, event.click.y = (self.cache.click.x, self.cache.click.y)
        return event

    def IsClickedSameButton(self, event):
        if self.cache.click.button is None:
            return False
        if event.LeftDown and self.cache.click.button == 'Left':
            return True
        if event.RightDown and self.cache.click.button == 'Right':
            return True
        if event.MiddleDown and self.cache.click.button == 'Middle':
            return True
        return False

    def CatchOnSizeEvent(self, event):
        if event.LeftUp:
            self.onsize = False
        if self.parent.IsOnSize():
            self.onsize = True

    def IsOnSize(self):
        return self.onsize

    def __del__(self):
        pass


class EventRaiser():

    def __init__(self):
        self.onClient = False

        self.Bind(wx.EVT_SET_FOCUS, self.RaiseSetFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.RaiseKillFocus)
        self.Bind(wx.EVT_ENTER_WINDOW, self.RaiseEnterWindow)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.RaiseLeaveWindow)

        self.Bind(wx.EVT_KEY_UP, self.RaiseKeyUpEvent)
        self.Bind(wx.EVT_KEY_DOWN, self.RaiseKeyDownEvent)
        self.Bind(wx.EVT_CHAR_HOOK, self.RaiseKeyHookEvent)
        self.Bind(wx.EVT_MOUSEWHEEL, self.RaiseMouseWheelEvent)

    def RaiseEvent(self, event):
        event.ResumePropagation(4)
        event.Skip()

    def RaiseSetFocus(self, event):
        self.RaiseEvent(event)

    def RaiseKillFocus(self, event):
        self.RaiseEvent(event)

    def RaiseEnterWindow(self, event):
        self.RaiseEvent(event)
        self.onClient = True

    def RaiseLeaveWindow(self, event):
        self.RaiseEvent(event)
        self.onClient = False

    def RaiseKeyUpEvent(self, event):
        self.RaiseEvent(event)

    def RaiseKeyDownEvent(self, event):
        self.RaiseEvent(event)

    def RaiseKeyHookEvent(self, event):
        self.RaiseEvent(event)

    def RaiseMouseWheelEvent(self, event):
        self.RaiseEvent(event)


class EventDistributor():

    def __init__(self, parent):
        self.parent = parent
        self.overBoxIdx = None
        self.selectedBoxIdx = None

        self.Bind(wx.EVT_SET_FOCUS, self.DistributeSetFocusEvent)
        self.Bind(wx.EVT_KILL_FOCUS, self.DistributeKillFocusEvent)
        self.Bind(wx.EVT_ENTER_WINDOW, self.DistributeEnterWindowEvent)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.DistributeLeaveWindowEvent)

        self.Bind(wx.EVT_KEY_UP, self.DistributeKeyUpEvent)
        self.Bind(wx.EVT_KEY_DOWN, self.DistributeKeyDownEvent)
        self.Bind(wx.EVT_CHAR_HOOK, self.DistributeKeyHookEvent)
        self.Bind(wx.EVT_MOUSEWHEEL, self.DistributeMouseWheelEvent)

    # Distribute Meathods

    def DistributeEvent(self, event):
        pass  # Override This Method

    def DistributeSetFocusEvent(self, event):
        self.DistributeEvent(event)

    def DistributeKillFocusEvent(self, event):
        self.DistributeEvent(event)

    def DistributeEnterWindowEvent(self, event):
        # self.overBoxIdx = event.Id
        self.DistributeEvent(event)

    def DistributeLeaveWindowEvent(self, event):
        # if self.overBoxIdx == event.Id: self.overBoxIdx = None
        self.DistributeEvent(event)

    def DistributeKeyUpEvent(self, event):
        self.DistributeEvent(event)

    def DistributeKeyDownEvent(self, event):
        self.DistributeEvent(event)
        event.Skip()

    def DistributeKeyHookEvent(self, event):
        arrowkeyflags = (21692417, 1095434241, 21823489, 1095565313,
                         21495809, 1095237633, 22020097, 1095761921, 3735553, 1077477377)
        if event.GetRawKeyFlags() in arrowkeyflags:
            self.DistributeEvent(event)
        event.Skip()

    def DistributeMouseWheelEvent(self, event):
        self.DistributeEvent(event)


class EventCatcher():

    def __init__(self):
        self.cache = Struct(
            down=Struct(X=None, Y=None, rectIdx=None),
            drag=Struct(X=None, Y=None, rectIdx=None))

    def CatchEvent(self, event):
        evtType = event.EventType
        if evtType == EVT_GLOBAL.evtType[0]:
            self.CATCH_EVT_GLOBAL(self.MakeupGlobalEvent(event))
        elif evtType == wx.EVT_KEY_UP.evtType[0]:
            self.CATCH_EVT_KEY_UP(self.MakeupLocalEvent(event))
        elif evtType == wx.EVT_KEY_DOWN.evtType[0]:
            self.CATCH_EVT_KEY_DOWN(self.MakeupLocalEvent(event))
        elif evtType == wx.EVT_CHAR_HOOK.evtType[0]:
            self.CATCH_EVT_KEY_DOWN(self.MakeupLocalEvent(event))
        elif evtType == wx.EVT_MOUSEWHEEL.evtType[0]:
            self.CATCH_EVT_MOUSEWHEEL(self.MakeupLocalEvent(event))

    # if self.parent.parent.HasToSkipEvent(): return

    def MakeupGlobalEvent(self, event):
        event.X, event.Y = self.ScreenToClient((event.x, event.y))
        event.rectIdx = self.GetRectIdx((event.X, event.Y))
        # another window over the player there (a dialog, a menu): not this box's
        if getattr(event, 'covered', False):
            event.rectIdx = None

        if event.LeftDown or event.RightDown or event.MiddleDown:
            event.down.X, event.down.Y = self.ScreenToClient((event.down.x, event.down.y))
            event.down.rectIdx = self.GetRectIdx((event.down.X, event.down.Y))
            if getattr(event, 'covered', False):
                event.down.rectIdx = None
            self.cache.down.X, self.cache.down.Y, self.cache.down.rectIdx\
                = (event.down.X, event.down.Y, event.down.rectIdx)
        elif (event.down.x, event.down.y) != (None, None):
            event.down.X, event.down.Y, event.down.rectIdx\
                = (self.cache.down.X, self.cache.down.Y, self.cache.down.rectIdx)

        if event.LeftDrag or event.RightDrag or event.MiddleDrag:
            event.drag.X, event.drag.Y = self.ScreenToClient((event.drag.x, event.drag.y))
            event.drag.rectIdx = self.GetRectIdx((event.drag.X, event.drag.Y))
            self.cache.drag.X, self.cache.drag.Y, self.cache.drag.rectIdx\
                = (event.drag.X, event.drag.Y, event.drag.rectIdx)
        elif (event.drag.x, event.drag.y) != (None, None):
            event.drag.X, event.drag.Y, event.drag.rectIdx\
                = (self.cache.drag.X, self.cache.drag.Y, self.cache.drag.rectIdx)

        if event.LeftDown or event.RightDown or event.MiddleDown:
            self.selected = self.onClient

        return self.ExtendGlobalEvent(event)

    def MakeupLocalEvent(self, event):
        new_event = Struct()
        sp_x, sp_y = event.GetEventObject().GetScreenPosition()
        new_event.x, new_event.y = (sp_x + event.GetX(), sp_y + event.GetY())
        new_event.X, new_event.Y = self.ScreenToClient((new_event.x, new_event.y))
        new_event.Id = event.Id
        new_event.EventType = event.EventType
        new_event.Timestamp = event.Timestamp
        new_event.AltDown = event.AltDown()
        new_event.CmdDown = event.CmdDown()
        new_event.ShiftDown = event.ShiftDown()
        new_event.ControlDown = event.ControlDown()

        if event.EventType in KEY_EVENT_TYPES:
            new_event.KeyCode = event.KeyCode
            new_event.RawKeyFlags = event.GetRawKeyFlags()

        if event.EventType in MOUSE_EVENT_TYPES:
            new_event.LeftUp = event.LeftUp()
            new_event.LeftDown = event.LeftDown()
            new_event.LeftIsDown = event.LeftIsDown()
            new_event.LeftDClick = event.LeftDClick()
            new_event.MiddleUp = event.MiddleUp()
            new_event.MiddleDown = event.MiddleDown()
            new_event.MiddleIsDown = event.MiddleIsDown()
            new_event.MiddleDClick = event.MiddleDClick()
            new_event.RightUp = event.RightUp()
            new_event.RightDown = event.RightDown()
            new_event.RightIsDown = event.RightIsDown()
            new_event.RightDClick = event.RightDClick()
            new_event.LeftIsDrag = event.Dragging()
            new_event.WheelRotation = event.GetWheelRotation()

        new_event.rectIdx = self.GetRectIdx((new_event.X, new_event.Y))
        return self.ExtendLocalEvent(new_event)

    # Event Extention Methods

    def ExtendGlobalEvent(self, event):
        return event  # Override This Method

    def ExtendLocalEvent(self, event):
        return event  # Override This Method

    # Event Catching Methods

    def CATCH_EVT_GLOBAL(self, event):
        pass  # Override This Method

    def CATCH_EVT_KEY_UP(self, event):
        pass  # Override This Method

    def CATCH_EVT_KEY_DOWN(self, event):
        pass  # Override This Method

    def CATCH_EVT_MOUSEWHEEL(self, event):
        pass  # Override This Method


# LimitTextLength's text widths by (font, text)
TEXT_EXTENTS = {}

# drawn and not yet on the screen (DirectDraw), put there by PaintUnpainted. Windows
# paints only when no other message waits: with the mouse moving over the window
# the list and the buttons waited. each painted at once instead, a sash dragged
# painted every box at every step and hardly followed the mouse
UNPAINTED = set()
# every box, for DrawPending
BOXES = weakref.WeakSet()


# a tick's time for them at most (DrawPending), and a box drawn by them this often at most:
# the rest at the next tick (when idle comes, OnIdle draws them at once as before)
PENDING_BUDGET = 0.008
PENDING_INTERVAL = 0.05


def DrawPending():
    '''the boxes asked to be drawn again (reInitBuffer), drawn and painted now: they were
    drawn when idle, and idle never came while the visualizers' ticks kept the queue busy
    (a song clicked was heard at once and shown long after, a scroll followed late). the
    longest waiting first, PENDING_BUDGET a tick, PENDING_INTERVAL a box: a song skipped 30
    times a second drew the whole list every tick, and the waveform fell to 8 frames a
    second'''
    start = time.perf_counter()
    boxes = [box for box in list(BOXES) if box and box.reInitBuffer
             and start - getattr(box, 'pending_lap', 0.0) >= PENDING_INTERVAL]
    # (those the eye follows first: PENDING_FIRST, the list's rows and the song's title)
    for box in sorted(boxes, key=lambda box: (getattr(box, 'PENDING_FIRST', False) is False,
                                              getattr(box, 'pending_lap', 0.0))):
        if time.perf_counter() - start > PENDING_BUDGET:
            break
        if box.IsShownOnScreen() is False:
            continue
        lap = box.buffer.lap
        box.OnIdle(None)
        if box.buffer.lap != lap:
            box.Update()
            box.pending_lap = time.perf_counter()


def PaintUnpainted():
    '''the boxes drawn since, painted now, once each (from a beat the mouse does
    not hold back: the visualizers' clock, PlayBoxVisualClock)'''
    boxes = list(UNPAINTED)
    UNPAINTED.clear()
    for box in boxes:
        # gone meanwhile (a dialog's)
        if box:
            box.Update()


class RectRect():

    def __init__(self):
        self.reInitBuffer = False
        self.buffer = Struct(fps=120, lap=time.time(), bmp=None)
        BOXES.add(self)

    def GetRectIdx(self, xy):
        # outside box
        if self.onClient is False:
            return None
        # inside box
        pass
        # inside box but empty area
        return 1

    def GetScreenRect(self):
        x, y = self.GetScreenPosition()
        w, h = self.GetSize()
        return wx.Rect(x, y, w, h)

    def IsInRect(self, rect, xy):
        x, y, w, h = rect
        if xy[0] < x or xy[0] >= x + w:
            return False
        if xy[1] < y or xy[1] >= y + h:
            return False
        return True

    def IsInClient(self, xy):
        rect = self.GetScreenRect()
        return self.IsInRect(rect, xy)

    def LimitTextLength(self, dc, string, width, margin=12):
        string = '%s' % (string)
        # each text's widths measured once a font: measured at every draw, a sash
        # dragged drew the list at every step and this was a sixth of all the time
        key = (dc.GetFont().GetNativeFontInfoDesc(), string)
        extents = TEXT_EXTENTS.get(key)
        if extents is None:
            if len(TEXT_EXTENTS) > 50000:
                TEXT_EXTENTS.clear()
            extents = TEXT_EXTENTS[key] = dc.GetPartialTextExtents(string)
        limit = bisect.bisect_right(extents, width - margin)
        if limit == len(string):
            return string
        return string[:limit] + '...'

    def SetRectPre(self):
        pass  # override this method

    def SetRectDraw(self, dc):
        pass  # override this method

    def InitBuffer(self):
        # self.buffer.lap = 0
        self.SetRectPre()
        width, height = self.GetSize()
        if width > 0 and height > 0:
            # (the last frame's picture drawn over when it is the size: one made a frame
            # was half of a frame's setting up)
            bmp = self.buffer.bmp
            if bmp is None or bmp.GetSize() != (width, height):
                self.buffer.bmp = wx.Bitmap(width, height)
            dc = wx.BufferedDC(None, self.buffer.bmp)
            dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
            dc.SetBackgroundMode(wx.TRANSPARENT)
            dc.Clear()
            self.SetRectDraw(dc)
        # drawn again at the next frame when the drawing asked it (redraw_next: a fading
        # mark), else not till something changes
        self.reInitBuffer = getattr(self, 'redraw_next', False)
        self.redraw_next = False

    def OnSize(self, event):
        self.DirectDraw()

    def OnIdle(self, event):
        if self.reInitBuffer is False:
            return
        if self.IsDrawable() is False:
            return
        elapsed_time = time.time() - self.buffer.lap
        if elapsed_time < 1.0 / self.buffer.fps:
            return
        self.buffer.lap = time.time()
        self.InitBuffer()
        self.Refresh(False)

    def OnPaint(self, event):
        UNPAINTED.discard(self)
        if self.buffer.bmp is None:
            return
        wx.BufferedPaintDC(self, self.buffer.bmp)

    def IsDrawable(self):
        # nothing is drawn while the window is minimized; drawn again when it is back
        return wx.GetTopLevelParent(self).IsIconized() is False

    def DirectDraw(self):
        if self.IsDrawable() is False:
            self.reInitBuffer = True
            return
        # elapsed_time = time.time() - self.buffer.lap
        # if elapsed_time < 1.0 / self.buffer.fps:
        #     return
        # self.buffer.lap = time.time()
        # on the beat: a tick a little early still draws, and the next frame is due
        # a frame after this one was due (not after now), so the fps is kept
        now = time.time()
        interval = 1.0 / self.buffer.fps
        elapsed_time = now - self.buffer.lap
        if elapsed_time < interval * 0.8:
            return
        if elapsed_time > interval * 2:
            self.buffer.lap = now
        else:
            self.buffer.lap += interval
        self.InitBuffer()
        self.Refresh(False)
        UNPAINTED.add(self)

    def OnErase(self, event):
        pass


class RectBox(RectRect, wx.Window, EventRaiser, EventCatcher):

    def __init__(self, parent, Id=None):
        RectRect.__init__(self)
        wx.Window.__init__(self, parent,
                           style=wx.CLIP_CHILDREN | wx.TAB_TRAVERSAL | wx.NO_BORDER)
        # wx.NO_FULL_REPAINT_ON_RESIZE|wx.FULL_REPAINT_ON_RESIZE
        EventRaiser.__init__(self)
        EventCatcher.__init__(self)
        self.parent = parent
        if Id is not None:
            self.Id = Id
        else:
            self.Id = wx.ID_ANY
        # self.InitBuffer()
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_IDLE, self.OnIdle)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)


class BorderBoxV(RectBox):

    def __init__(self, parent):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.OnSize()
        self.InitBuffer()

    def GetRectIdx(self, xy):
        return None

    # Draw BorderBox Empty Area

    # def SetRectDraw(self, dc):
    #     dc.SetBrush(wx.Brush(COLOR_TAB_BG))
    #     dc.SetPen(wx.Pen(COLOR_TAB_BG, 0))
    #     x, y, w, h = self.rect
    #     dc.DrawRectangle(x, y, w, h)

    # Buffered DC

    def OnSize(self, event=None):
        w, h = self.GetSize()
        self.rect = (0, 0, w, 24)
        self.DirectDraw()


class BorderBoxH(RectBox):

    def __init__(self, parent, grad=False):
        RectBox.__init__(self, parent)
        self.parent = parent
        self.grad = grad
        self.OnSize()
        self.InitBuffer()

    def GetRectIdx(self, xy):
        return None

    # Buffered DC

    def SetRectDraw(self, dc):
        if self.grad is False:
            return
        w, h = self.GetSize()
        lines, pens = ([], [])
        inc = 40
        init_color = 50
        for i in range(5):
            lines += [(0, i, w, i)]
            rgb = init_color + i * inc
            pens += [wx.Pen((rgb, rgb, rgb), 1)]
        for i in range(5, 10):
            lines += [(0, i, w, i)]
            pens += [pens[-1]]
        dc.DrawLineList(lines, pens=pens)

    def OnSize(self, event=None):
        self.DirectDraw()


class ItemTextEdit(wx.TextCtrl):

    def __init__(self, parent):
        wx.TextCtrl.__init__(self, parent, pos=(0, 0), size=(0, 0),
                             style=wx.BORDER_NONE | wx.TE_NOHIDESEL | wx.TE_RICH)
        self.parent = parent
        self.destroy = False
        self.onClient = False
        self.itemIdx = None
        self.columnIdx = None
        self.restore_value = None
        self.SetBackgroundColour(macroboxstyle.current().UI.EDIT_BG)
        self.SetForegroundColour(macroboxstyle.current().UI.EDIT_FG)
        self.SetFont(wx.Font(
            9, wx.MODERN, wx.NORMAL, wx.NORMAL, False, FONT_ITEM))
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)

    def OnMouseWheel(self, event):
        self.CommitText()
        event.Skip()

    def OnFocus(self, event):
        self.onClient = True
        event.Skip()

    def OnKillFocus(self, event):
        self.onClient = False
        self.CommitText()
        event.Skip()

    def OnKeyDown(self, event):
        # http://wxpython.org/docs/api/wx.KeyEvent-class.html
        internal_use_keys = (wx.WXK_NUMPAD_SPACE,
                             wx.WXK_HOME, wx.WXK_END, wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE)
        commit_keys = (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_UP,
                       wx.WXK_DOWN, wx.WXK_NUMPAD_UP, wx.WXK_NUMPAD_DOWN, wx.WXK_PAGEUP,
                       wx.WXK_PAGEDOWN, wx.WXK_NUMPAD_PAGEUP, wx.WXK_NUMPAD_PAGEDOWN)
        if event.KeyCode in commit_keys:
            self.CommitText()
        elif event.KeyCode in internal_use_keys:
            event.ResumePropagation(0)
            event.Skip()
        elif event.KeyCode == wx.WXK_TAB:
            self.SetTextNextItem()
        elif event.KeyCode == wx.WXK_ESCAPE:
            self.RollbackText()
        else:
            event.ResumePropagation(0)
            event.Skip()

    def SetText(self, itemIdx, columnIdx):
        self.itemIdx = itemIdx
        self.columnIdx = self.parent.parent.GetShownColumnsIdx()[columnIdx]
        value = '%s' % (
                self.parent.parent.GetItemValueByColumnIdx(itemIdx, self.columnIdx))
        self.restore_value = value
        self.SetValue(value)
        self.SetFocus()
        self.parent.reInitBuffer = True

    def RollbackText(self):
        self.destroy = True

    def CommitText(self):
        if self.columnIdx == self.parent.parent.GetColumnKeyToIdx('filename'):
            self.RenameFile()
        if self.parent.parent.IsID3TAGColumnByColumnIdx(self.columnIdx):
            self.RenameID3TAG()
        newValue = self.GetValue()
        columnKey = self.parent.parent.GetColumnIdxToKey(self.columnIdx)
        if columnKey == 'tempo':
            try:
                newValue = float(newValue)
                newValue = u'%05.1f' % (0.1 * round(newValue * 10))
            except Exception:
                newValue = ''
        self.parent.parent.SetItemValueByColumnIdx(
            self.itemIdx, self.columnIdx, newValue)
        self.destroy = True

    def RenameID3TAG(self):
        newValue = self.GetValue()
        resp = self.parent.parent.RenameID3TAGByColumnItemIdx(
            self.columnIdx, self.itemIdx, newValue)
        if resp is False:
            self.SetValue(self.restore_value)

    def SetTextNextItem(self):
        if self.itemIdx >= self.parent.parent.GetItemsLength() - 1:
            self.CommitText()
            return

        item = list(self.parent.parent.innerList[
            self.parent.parent.selectedList].items[self.itemIdx])
        item[self.columnIdx] = self.GetValue()
        self.parent.parent.innerList[self.parent
                                     .parent.selectedList].items[self.itemIdx] = tuple(item)

        self.itemIdx += 1
        self.parent.parent.SelectAndFocusItem(self.itemIdx)
        self.SetText(self.itemIdx, self.columnIdx)

    def RenameFile(self):
        newFilename = self.GetValue()
        newFilename = self.parent.parent.LimitFileName(newFilename)
        oldPath = self.parent.parent.GetItemValueByColumnKey(self.itemIdx, 'path')
        pathBase = os.path.sep.join(oldPath.split(os.path.sep)[:-1])
        fileType = os.path.splitext(oldPath)[-1]
        newPath = os.path.sep.join([pathBase, newFilename])
        newPath = ''.join([newPath, fileType])
        resp = self.parent.parent.RenameFileByItemIdx(self.itemIdx, newPath)
        if resp is False:
            self.SetValue(self.restore_value)


class TabTextEdit(wx.TextCtrl):

    def __init__(self, parent):
        wx.TextCtrl.__init__(self, parent, pos=(0, 0), size=(0, 0),
                             style=wx.BORDER_NONE | wx.TE_NOHIDESEL | wx.TE_RICH)
        self.parent = parent
        self.SetBackgroundColour(macroboxstyle.current().UI.EDIT_BG)
        self.SetForegroundColour(macroboxstyle.current().UI.EDIT_FG)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.onClient = False
        self.destroy = False
        self.rect = wx.Rect(0, 0, 0, 0)
        self.tabIdx = self.parent.text_edit_tabIdx
        self.parent.text_edit_tabIdx = None
        self.SetFont(wx.Font(8, wx.MODERN, wx.NORMAL, wx.NORMAL, False, FONT_ITEM))
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.SetFocus()

    def OnMouseWheel(self, event):
        self.CommitText()
        event.Skip()

    def OnFocus(self, event):
        self.onClient = True
        event.Skip()

    def OnKillFocus(self, event):
        self.onClient = False
        self.CommitText()
        event.Skip()

    def OnKeyDown(self, event):
        commit_keys = (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
        if event.KeyCode in commit_keys:
            self.CommitText()
        elif event.KeyCode == wx.WXK_ESCAPE:
            self.RollbackText()
        else:
            event.ResumePropagation(0)
            event.Skip()

    def RollbackText(self):
        self.destroy = True

    def CommitText(self):
        string = self.GetValue()
        self.parent.SetTabTitle(string, self.tabIdx)
        self.destroy = True


# the dialogs' spacing, one ladder for all of them (the tag editor's, Look Up's and the
# rest each had their own: the user): PAD round a dialog, between its groups (columns,
# sections) and round its footer's line and buttons; GAP between rows, a name and its
# field, and buttons side by side; CHECK_GAP from a check box to its name; ROW a field's
# height, BUTTON_HEIGHT a button's
DIALOG_PAD = 16
DIALOG_GAP = 8
DIALOG_CHECK_GAP = 6
DIALOG_ROW = 22
DIALOG_BUTTON_HEIGHT = 26


class DialogBox(wx.Dialog):

    # the footer: its line PAD over the buttons, the buttons PAD from the bottom and the
    # sides (OnDialogPaint, PlaceButtons)
    footer_gap = DIALOG_PAD + 1

    @staticmethod
    def GetFooterHeight():
        return 1 + DIALOG_PAD * 2 + DIALOG_BUTTON_HEIGHT

    def GetContentBottom(self):
        # where a dialog's content ends: PAD over its footer's line
        return self.GetClientSize().height - self.GetFooterHeight() - DIALOG_PAD

    def PlaceButtons(self, right=(), left=()):
        '''the footer's buttons: right, their order kept, at its right end; left at its
        left; GAP between them, PAD from the sides and the bottom; their row's top'''
        width, height = self.GetClientSize()
        top = height - DIALOG_PAD - DIALOG_BUTTON_HEIGHT
        x = width - DIALOG_PAD
        for button in reversed(right):
            x -= button.GetSize().width
            button.SetPosition((x, top))
            x -= DIALOG_GAP
        x = DIALOG_PAD
        for button in left:
            button.SetPosition((x, top))
            x += button.GetSize().width + DIALOG_GAP
        return top

    def __init__(self, parent, id=-1, size=(-1, -1), pos=(-1, -1), style=0):
        style = style | wx.CLIP_CHILDREN | wx.CAPTION | wx.TAB_TRAVERSAL |\
            wx.NO_FULL_REPAINT_ON_RESIZE | wx.STAY_ON_TOP | wx.CLOSE_BOX | wx.NO_BORDER
        wx.Dialog.__init__(self, parent, id=id, size=size, pos=pos, style=style)
        self.parent = parent
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour(macroboxstyle.current().UI.DIALOG_BG)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_PAINT, self.OnDialogPaint)

    def OnSize(self, event):
        pass

    def OnDialogPaint(self, event):
        # the footer: a line over the buttons along the dialog's bottom (its actions
        # apart from what they act on); a window of its own, over the panels (a line
        # painted on the dialog was under them)
        wx.PaintDC(self)
        w, h = self.GetClientSize()
        tops = [child.GetRect().y for child in self.GetChildren()
                if isinstance(child, Button) and child.IsShown()
                and child.GetRect().GetBottom() > h - 60]
        line = getattr(self, 'footer_line', None)
        if not tops:
            if line is not None:
                line.Hide()
            return
        if line is None:
            line = self.footer_line = wx.Window(self, style=wx.BORDER_NONE)
            line.SetBackgroundColour(macroboxstyle.current().UI.BAR_LINE)
        rect = wx.Rect(0, min(tops) - self.footer_gap, w, 1)
        if line.GetRect() != rect:
            line.SetRect(rect)
        line.Show()
        line.Raise()

    def OnClose(self, event):
        self.Destroy()


class DialogPanel(wx.Panel):

    def __init__(self, parent, id=-1, size=(-1, -1), pos=(-1, -1), style=0):
        style = style | wx.CLIP_CHILDREN | wx.FRAME_SHAPED |\
            wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL | wx.NO_BORDER
        wx.Panel.__init__(self, parent, id=id, size=size, pos=pos, style=style)
        self.parent = parent
        self.SetDoubleBuffered(True)
        bgcolor = self.parent.GetBackgroundColour()
        self.SetBackgroundColour(bgcolor)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def OnSize(self, event):
        pass


class FancyDialogBoxGlobalEvent(RectRect):

    def __init__(self):
        self.onClient = False
        self.draginit_xy = None
        self.draginit_rect = None
        self.last_leftisdown = False
        self.stop_globalevent = False
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)

    def OnEnterWindow(self, event):
        self.onClient = True

    def OnLeaveWindow(self, event):
        self.onClient = False

    def HandleGlobalEvent(self):
        if self.stop_globalevent:
            return
        state = wx.GetMouseState()
        self.OnMouseEvent(state)

    def OnMouseEvent(self, event):
        if self.stop_globalevent:
            return
        if event.LeftIsDown() is False:
            self.draginit_xy = None
            self.draginit_rect = None
            self.last_leftisdown = False
            return
        xy = (event.x, event.y)
        px, py = self.GetScreenPosition()
        pw, ph = self.GetSize()
        rect = (px, py, pw, ph)
        is_movable = self.IsInRect(rect, xy)
        objects = ('BuyNowButton', 'LicenseButton', 'CloseButton', 'VisitButton')
        for v in objects:
            if hasattr(self, v) is False:
                continue
            exec('rect = self.%s.GetScreenRect()' % (v))
            if self.IsInRect(rect, xy):
                is_movable = False
        if is_movable and self.draginit_xy is None\
                and event.LeftIsDown() and self.last_leftisdown is False:
            self.draginit_xy = (event.x, event.y)
            self.draginit_rect = self.GetScreenRect()
        if self.draginit_xy is not None and event.LeftIsDown():
            dx = self.draginit_xy[0] - event.x
            dy = self.draginit_xy[1] - event.y
            x, y, w, h = self.draginit_rect
            self.SetRect((x - dx, y - dy, w, h))
        self.last_leftisdown = event.LeftIsDown()

    def OnClose(self, event):
        self.Destroy()


class FancyDialogBox(wx.Dialog):

    def __init__(self, parent, id=-1, size=(-1, -1), pos=(-1, -1), style=0):
        style = style | wx.CLIP_CHILDREN | wx.TAB_TRAVERSAL |\
            wx.NO_FULL_REPAINT_ON_RESIZE | wx.STAY_ON_TOP | wx.NO_BORDER
        wx.Dialog.__init__(self, parent, id=id, size=size, pos=pos, style=style)
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour(macroboxstyle.current().UI.DIALOG_BG)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnSize(self, event):
        pass

    def OnClose(self, event):
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class UserInputDialogPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        self.UserInput = TextCtrl(self)
        self.OnSize(None)

    def OnSize(self, event):
        width, height = self.parent.GetClientSize()
        self.UserInput.SetRect((DIALOG_PAD, DIALOG_PAD, width - DIALOG_PAD * 2, DIALOG_ROW))

    def GetValue(self):
        return self.UserInput.GetValue()

    def SetValue(self, value):
        self.UserInput.SetValue(value)

    def OnClose(self, event):
        self.Destroy()


# the small dialogs' width: their two buttons and the footer's sides
SMALL_DIALOG_WIDTH = DIALOG_PAD * 2 + 75 * 2 + DIALOG_GAP


class UserInputDialogBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(190, 115))
        self.parent = parent
        # a field, the footer under it
        self.SetClientSize((max(SMALL_DIALOG_WIDTH, 190), DIALOG_PAD * 2 + DIALOG_ROW
                            + self.GetFooterHeight()))
        self.UserInput = UserInputDialogPanel(self)
        self.ApplyButton = Button(self, label='', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CloseButton = Button(self, label='Cancel')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)

    def ShowModal(self):
        self.OnSize(None)
        return DialogBox.ShowModal(self)

    def OnSize(self, event):
        # (a size set before its children are made: none to place yet)
        if getattr(self, 'CloseButton', None) is None:
            return
        width, height = self.GetClientSize()
        self.UserInput.SetRect((0, 0, width, DIALOG_PAD * 2 + DIALOG_ROW))
        self.UserInput.OnSize(None)
        self.PlaceButtons(right=(self.ApplyButton, self.CloseButton))

    def OnApply(self, event):
        self.OnClose(event)

    def OnClose(self, event):
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class ConfirmDialogPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        self.Message = StaticText(self, style=wx.ALIGN_CENTER)
        self.OnSize(None)

    def OnSize(self, event):
        width, height = self.GetClientSize()
        self.Message.SetPosition((DIALOG_PAD, DIALOG_PAD))
        self.Message.SetInitialSize((width - DIALOG_PAD * 2, DIALOG_ROW))

    def SetLabelText(self, value):
        self.Message.SetLabelText(value)
        self.OnSize(None)

    def OnClose(self, event):
        self.Destroy()


class ConfirmDialogBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(180, 105))
        self.parent = parent
        # a line of words, the footer under it
        self.SetClientSize((SMALL_DIALOG_WIDTH, DIALOG_PAD * 2 + DIALOG_ROW
                            + self.GetFooterHeight()))
        self.Message = ConfirmDialogPanel(self)
        self.ApplyButton = Button(self, label='', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CloseButton = Button(self, label='Cancel')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.OnSize(None)

    def OnSize(self, event):
        if getattr(self, 'CloseButton', None) is None:
            return
        width, height = self.GetClientSize()
        self.Message.SetRect((0, 0, width, DIALOG_PAD * 2 + DIALOG_ROW))
        self.Message.OnSize(None)
        self.PlaceButtons(right=(self.ApplyButton, self.CloseButton))

    def OnApply(self, event):
        self.OnClose(event)

    def OnClose(self, event):
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


def fit_name_column(parent, x, width):
    '''names right-aligned in a column width wide at x, their fields past it: the column
    made as wide as its widest name (that one PAD from the edge, not 30 and more: a fixed
    column wider than its names, the user), everything past it moved as much; the px saved'''
    children = list(parent.GetChildren())
    names = [c for c in children if isinstance(c, wx.StaticText)
             and c.GetPosition().x == x and c.GetSize().width == width]
    if not names:
        return 0
    widest = max(c.GetBestSize().width for c in names)
    shift = width - widest
    if shift <= 0:
        return 0
    for c in children:
        cx, cy = c.GetPosition()
        if c in names:
            c.SetSize((widest, c.GetSize().height))
        elif cx >= x + width:
            c.SetPosition((cx - shift, cy))
    return shift


def make_check(parent, label, pos, value, handler):
    '''a check box and its name, a text of its own CHECK_GAP past the box (the box's own
    name sat against it: the user), a click on the name checking it too; (box, width).
    pos: the name's top left as a row's names (the box a pixel lower, on its middle)'''
    box = CheckBox(parent, label='', pos=(pos[0], pos[1] + 1))
    box.SetSize(box.GetBestSize())
    box.SetValue(value)
    box.Bind(wx.EVT_CHECKBOX, lambda e: handler(box.GetValue()))
    x = pos[0] + box.GetSize().width + DIALOG_CHECK_GAP
    name = StaticText(parent, label=label, pos=(x, pos[1]))
    name.SetSize(name.GetBestSize())

    def flip(event):
        box.SetValue(not box.GetValue())
        handler(box.GetValue())
    name.Bind(wx.EVT_LEFT_DOWN, flip)
    return box, x + name.GetSize().width - pos[0]


def draw_field(gc, w, h, focused):
    # a field's ground (as FieldFrame's): rounded, its edge in the accent with the focus
    ui = macroboxstyle.current().UI
    edge = ui.FIELD_FOCUS if focused else ui.FIELD_EDGE
    gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(edge)).Width(1)))
    gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.FIELD_BG))))
    gc.DrawRoundedRectangle(0, 0, w - 1, h - 1, uikit.RADIUS)


class SpinCtrl(wx.Control):

    '''a number in a field with its steps at the right (up and down), as the dialogs'
    fields: typed, or stepped by them, the arrow keys or the wheel; wx.EVT_SPINCTRL when it
    changes (GetInt, as a wx.SpinCtrl's)'''

    STEP = 16

    def __init__(self, parent, id=-1, value='', pos=(-1, -1), size=(60, 24), style=0):
        wx.Control.__init__(self, parent, id=id, pos=pos, size=size, style=wx.BORDER_NONE)
        self.parent = parent
        self.low, self.high = 0, 100
        self.value = int(value) if str(value).lstrip('-').isdigit() else 0
        self.pressed = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.text = wx.TextCtrl(self, value=str(self.value),
                                style=wx.BORDER_NONE | wx.TE_RIGHT | wx.TE_PROCESS_ENTER)
        font = wx.Font(wx.Size(0, 13), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL, faceName='Consolas')
        self.text.SetFont(font)
        ui = macroboxstyle.current().UI
        self.text.SetBackgroundColour(ui.FIELD_BG)
        self.text.SetForegroundColour(ui.EDIT_FG)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, lambda e: self.Layout())
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, lambda e: self.SetPressed(None))
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.text.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.text.Bind(wx.EVT_KEY_DOWN, self.OnKey)
        self.text.Bind(wx.EVT_KILL_FOCUS, self.OnCommit)
        self.text.Bind(wx.EVT_TEXT_ENTER, self.OnCommit)
        self.text.Bind(wx.EVT_SET_FOCUS, lambda e: (self.Refresh(), e.Skip()))
        self.Layout()

    def Layout(self):
        w, h = self.GetClientSize()
        th = min(self.text.GetCharHeight() + 2, h)
        self.text.SetSize(4, min((h - th) // 2 + 1, h - th), max(w - self.STEP - 8, 1), th)
        self.Refresh()

    def SetRange(self, low, high):
        self.low, self.high = int(low), int(high)
        self.SetValue(self.value)

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = min(max(int(value), self.low), self.high)
        self.text.ChangeValue(str(self.value))

    def SetFontPixelSize(self, size):
        pass

    def Change(self, value):
        value = min(max(int(value), self.low), self.high)
        if value == self.value:
            self.text.ChangeValue(str(self.value))
            return
        self.SetValue(value)
        event = wx.SpinEvent(wx.wxEVT_SPINCTRL, self.GetId())
        event.SetEventObject(self)
        event.SetInt(self.value)
        event.SetPosition(self.value)
        self.GetEventHandler().ProcessEvent(event)

    def OnCommit(self, event):
        text = self.text.GetValue().strip()
        self.Change(int(text) if text.lstrip('-').isdigit() else self.value)
        self.Refresh()
        event.Skip()

    def OnKey(self, event):
        code = event.GetKeyCode()
        if code == wx.WXK_UP:
            self.Change(self.value + 1)
        elif code == wx.WXK_DOWN:
            self.Change(self.value - 1)
        else:
            event.Skip()

    def OnWheel(self, event):
        self.Change(self.value + (1 if event.GetWheelRotation() > 0 else -1))

    def GetStepRects(self):
        w, h = self.GetClientSize()
        x = w - self.STEP - 1
        return wx.Rect(x, 1, self.STEP, h // 2 - 1), wx.Rect(x, h // 2, self.STEP, h - h // 2 - 1)

    def SetPressed(self, which):
        self.pressed = which
        self.Refresh()

    def OnLeftDown(self, event):
        up, down = self.GetStepRects()
        if up.Contains(event.GetPosition()):
            self.SetPressed('up')
            self.Change(self.value + 1)
        elif down.Contains(event.GetPosition()):
            self.SetPressed('down')
            self.Change(self.value - 1)
        else:
            self.text.SetFocus()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        gc = wx.GraphicsContext.Create(dc)
        draw_field(gc, w, h, self.text.HasFocus())
        ui = macroboxstyle.current().UI
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(ui.FIELD_EDGE)).Width(1)))
        x = w - self.STEP - 1.5
        gc.StrokeLine(x, 3, x, h - 3)
        for rect, icon in zip(self.GetStepRects(), ('up', 'down')):
            ink = uikit.colour(ui.TEXT if self.pressed == icon else ui.CONTROL_FG)
            uikit.draw_icon(gc, icon, (rect.x, rect.y, rect.width, rect.height + 2), ink)


class ProgressBar(wx.Control):

    '''a thin bar of what is done, in the accent on an unlit ground (the status line's,
    a wx.Gauge's place)'''

    def __init__(self, parent, range=100):
        wx.Control.__init__(self, parent, style=wx.BORDER_NONE)
        self.range = max(int(range), 1)
        self.value = 0
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def SetRange(self, range):
        self.range = max(int(range), 1)
        self.Refresh()

    def SetValue(self, value):
        self.value = min(max(value, 0), self.range)
        self.Refresh()

    def GetValue(self):
        return self.value

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        ui = macroboxstyle.current().UI
        bar = 4
        y = (h - bar) // 2
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(ui.CONTROL_BG))
        dc.DrawRectangle(0, y, w, bar)
        dc.SetBrush(wx.Brush(ui.ACCENT))
        dc.DrawRectangle(0, y, int(w * self.value / float(self.range)), bar)


class Dropdown(wx.Control):

    '''a choice in a field (its arrow at the right), as the dialogs' fields: a click
    opens its choices as a menu under it; wx.EVT_COMBOBOX when another is chosen
    (GetString, GetSelection), as a read only wx.ComboBox'''

    def __init__(self, parent, id=-1, value='', choices=[''], pos=(-1, -1), size=(75, 24),
                 style=0):
        wx.Control.__init__(self, parent, id=id, pos=pos, size=size,
                            style=wx.BORDER_NONE | wx.WANTS_CHARS)
        self.parent = parent
        self.choices = list(choices)
        self.value = value
        self.hover = False
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self.SetHover(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.SetHover(False))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnOpen)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKey)
        self.Bind(wx.EVT_SET_FOCUS, lambda e: self.Refresh())
        self.Bind(wx.EVT_KILL_FOCUS, lambda e: self.Refresh())

    def AcceptsFocus(self):
        return True

    def SetHover(self, on):
        self.hover = on
        self.Refresh()

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value
        self.Refresh()

    def GetStringSelection(self):
        return self.value

    def GetSelection(self):
        return self.choices.index(self.value) if self.value in self.choices else -1

    def SetSelection(self, index):
        self.SetValue(self.choices[index])

    def GetItems(self):
        return list(self.choices)

    def SetItems(self, choices):
        self.choices = list(choices)
        self.Refresh()

    def SetFontPixelSize(self, size):
        pass

    def Choose(self, index):
        if self.choices[index] == self.value:
            return
        self.SetValue(self.choices[index])
        event = wx.CommandEvent(wx.wxEVT_COMBOBOX, self.GetId())
        event.SetEventObject(self)
        event.SetString(self.value)
        event.SetInt(index)
        self.GetEventHandler().ProcessEvent(event)

    def OnOpen(self, event=None):
        self.SetFocus()
        menu = wx.Menu()
        for k, choice in enumerate(self.choices):
            item = menu.AppendCheckItem(wx.ID_ANY, choice)
            item.Check(choice == self.value)
            self.Bind(wx.EVT_MENU, lambda e, k=k: self.Choose(k), item)
        self.PopupMenu(menu, (0, self.GetClientSize().height))
        menu.Destroy()

    def OnKey(self, event):
        code = event.GetKeyCode()
        index = self.GetSelection()
        if code in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_F4):
            self.OnOpen()
        elif code == wx.WXK_UP and index > 0:
            self.Choose(index - 1)
        elif code == wx.WXK_DOWN and index < len(self.choices) - 1:
            self.Choose(index + 1)
        else:
            event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        gc = wx.GraphicsContext.Create(dc)
        draw_field(gc, w, h, self.HasFocus())
        ui = macroboxstyle.current().UI
        font = wx.Font(wx.Size(0, 12), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL,
                       wx.FONTWEIGHT_NORMAL, faceName=FONT_ITEM)
        uikit.set_font(gc, font, uikit.colour(ui.EDIT_FG))
        tw, th = gc.GetTextExtent(self.value)[:2]
        gc.Clip(1, 1, w - 22, h - 2)
        gc.DrawText(self.value, 8, (h - th) / 2.0)
        gc.ResetClip()
        ink = uikit.colour(ui.TEXT if self.hover else ui.CONTROL_FG)
        uikit.draw_icon(gc, 'down', (w - 20, 0, 16, h), ink)


class NativeComboBox(wx.ComboBox):

    # an editable one (its text typed): the native control
    def __init__(self, parent, id=-1, value='', choices=[''], pos=(-1, -1), size=(75, 24), style=0):
        wx.ComboBox.__init__(self, parent, id=id, value=value,
                             choices=choices, pos=pos, size=size, style=style)
        self.value = value
        self.parent = parent
        self.SetDoubleBuffered(True)
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetFaceName(FONT_ITEM)
        font.SetPixelSize((6, 12))
        self.SetFont(font)

    def SetFontPixelSize(self, size):
        font = self.GetFont()
        font.SetPixelSize(size)
        self.SetFont(font)


def ComboBox(parent, id=-1, value='', choices=[''], pos=(-1, -1), size=(75, 24), style=0):
    # a read only one as the dialogs' field (Dropdown), an editable one native
    kind = Dropdown if style & wx.CB_READONLY else NativeComboBox
    return kind(parent, id=id, value=value, choices=choices, pos=pos, size=size, style=style)


class FieldFrame(wx.Window):

    '''a TextCtrl's frame (the field the dialog places): a rounded ground of its own,
    the edge in the accent while it is typed in, the text control borderless inside it with
    its text on the field's middle (a borderless control alone kept its text at the top);
    read only, its edge alone, the dialog's ground in it (no field at all, the value as text
    on the dialog's, before: numbers floating in the air, the user)'''

    # the text control at PAD in from the field's edge: its own margin (4 px) adds to it, the
    # text's ink 8 px in (it was 11 at 7); one row under the middle, so the capitals sit on
    # the field's middle and Hangul's taller glyphs too (measured: Latin 6 to 14 of 22,
    # Hangul 5 to 17)
    PAD = 4
    # its menu's mark at its right (SetMark: a ▾ when it has values to choose from), the
    # text short of it
    MARK = 16

    def __init__(self, parent, pos, size):
        wx.Window.__init__(self, parent, pos=pos, size=size, style=wx.BORDER_NONE)
        self.text = None
        # changed (SetChanged: a bar in the accent at its left, not saved yet), its mark's
        # action (SetMark)
        self.changed = False
        self.mark = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, lambda e: self.Layout())
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)

    def OnLeftDown(self, event):
        if self.mark is not None and event.GetX() >= self.GetClientSize().width - self.MARK - 2:
            self.mark()
            return
        if self.text:
            self.text.SetFocus()

    def SetChanged(self, changed):
        if changed != self.changed:
            self.changed = changed
            self.Refresh()

    def SetMark(self, action):
        if (action is None) != (self.mark is None):
            self.mark = action
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND if action else wx.CURSOR_DEFAULT))
            self.Layout()
        self.mark = action

    def Layout(self):
        if self.text is None:
            return
        w, h = self.GetClientSize()
        th = min(self.text.GetCharHeight() + 2, h)
        y = min((h - th) // 2 + 1, h - th)
        room = w - self.PAD * 2 - (self.MARK if self.mark is not None else 0)
        wx.TextCtrl.SetSize(self.text, self.PAD, y, max(room, 1), th)
        self.Refresh()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        ui = macroboxstyle.current().UI
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        if self.text is None:
            return
        w, h = self.GetClientSize()
        gc = wx.GraphicsContext.Create(dc)
        read_only = self.text.read_only
        edge = ui.FIELD_FOCUS if self.text.HasFocus() and not read_only else ui.FIELD_EDGE
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(edge)).Width(1)))
        gc.SetBrush(wx.NullGraphicsBrush if read_only else
                    gc.CreateBrush(wx.Brush(uikit.colour(ui.FIELD_BG))))
        # (from (0, 0), w - 1: the renderer puts the edge on the outer rows, uikit.draw_face)
        gc.DrawRoundedRectangle(0, 0, w - 1, h - 1, uikit.RADIUS)
        if self.changed:
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.colour(ui.ACCENT))))
            gc.DrawRectangle(1, 3, 2, h - 6)
        if self.mark is not None:
            # a small chevron, as the dropdowns'
            cx, cy = w - self.PAD - self.MARK / 2.0, h / 2.0
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.colour(ui.BAR_TEXT_DIM)).Width(1.4)))
            gc.StrokeLines([(cx - 3.5, cy - 1.5), (cx, cy + 2), (cx + 3.5, cy - 1.5)])


class TextCtrl(wx.TextCtrl):

    '''a dialog's text field: a borderless text control in a FieldFrame (placed, sized,
    shown and destroyed with it); SetReadOnly: a value shown in a field of its edge alone'''

    def __init__(self, parent, id=-1, value='',
                 pos=(-1, -1), size=(75, 24), style=0):
        self.frame = FieldFrame(parent, pos, size)
        wx.TextCtrl.__init__(self, self.frame, id=id,
                             value=value, style=style | wx.BORDER_NONE)
        self.parent = parent
        self.read_only = False
        self.SetDoubleBuffered(True)
        font = wx.Font(8, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetFaceName(FONT_ITEM)
        font.SetPixelSize((6, 12))
        self.SetFont(font)
        self.frame.text = self
        self.ApplyLook()
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnFocus)

    def OnFocus(self, event):
        self.frame.Refresh()
        event.Skip()

    def ApplyLook(self):
        ui = macroboxstyle.current().UI
        if self.read_only:
            # brighter than the names beside it (those dimmed)
            self.SetBackgroundColour(self.frame.GetParent().GetBackgroundColour())
            self.SetForegroundColour(ui.BAR_TEXT)
        else:
            self.SetBackgroundColour(ui.FIELD_BG)
            self.SetForegroundColour(ui.EDIT_FG)
        self.frame.Layout()

    def SetReadOnly(self, read_only=True):
        self.SetEditable(not read_only)
        self.read_only = read_only
        self.ApplyLook()

    # placed as its frame
    def SetRect(self, rect):
        self.frame.SetRect(rect)

    def SetPosition(self, pos):
        self.frame.SetPosition(pos)

    def SetSize(self, *args):
        self.frame.SetSize(*args)

    def GetRect(self):
        return self.frame.GetRect()

    def GetPosition(self):
        return self.frame.GetPosition()

    def GetSize(self):
        return self.frame.GetSize()

    def Show(self, show=True):
        return self.frame.Show(show)

    def Hide(self):
        return self.frame.Hide()

    def Destroy(self):
        return self.frame.Destroy()


class CheckBox(wx.CheckBox):

    def __init__(self, parent, id=-1, label='', pos=(-1, -1), size=(-1, 15), style=0):
        wx.CheckBox.__init__(self, parent, id=id,
                             label=label, pos=pos, size=size, style=style)
        self.label = label
        self.SetDoubleBuffered(True)
        self.SetForegroundColour(macroboxstyle.current().UI.TEXT)
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((6, 12))
        font.SetFaceName(FONT_ITEM)
        self.SetFont(font)


class RadioButton(wx.RadioButton):

    def __init__(self, parent, id=-1, label='', pos=(-1, -1), size=(-1, 15), style=0):
        wx.RadioButton.__init__(self, parent, id=id,
                                label=label, pos=pos, size=size, style=style)
        self.label = label
        self.SetDoubleBuffered(True)
        self.SetForegroundColour(macroboxstyle.current().UI.TEXT)
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((6, 12))
        font.SetFaceName(FONT_ITEM)
        self.SetFont(font)


class StaticText(wx.StaticText):

    def __init__(self, parent, id=-1, label='', pos=(-1, -1), size=(-1, -1), style=0):
        wx.StaticText.__init__(self, parent, id=id,
                               label=label, pos=pos, size=size, style=style)
        self.label = label
        self.parent = parent
        self.onClient = False
        self.SetDoubleBuffered(True)
        self.bgcolor = (40, 40, 40)
        self.fgcolor = macroboxstyle.current().UI.TEXT
        self.SetForegroundColour(self.fgcolor)
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((6, 12))
        font.SetFaceName(FONT_ITEM)
        self.SetFont(font)
        self.SetInitialSize(size)
        self.SetWindowStyle(style)
        self.SetWindowStyleFlag(style)
        # self.SetWindowStyle()
        # self.SetWindowStyleFlag()


class Button(wx.Control):

    '''a dialog's button drawn as the player's keys (uikit.draw_button: matte, a darker
    edge); primary, the dialog's own action in the accent. clicked by the mouse, or by the
    space or enter key while it has the focus (its edge in the accent): wx.EVT_BUTTON, as a
    wx.Button's'''

    def __init__(self, parent, id=-1, label='', pos=(-1, -1), size=(75, 26), style=0,
                 primary=False):
        wx.Control.__init__(self, parent, id=id, pos=pos, size=size,
                            style=style | wx.BORDER_NONE | wx.WANTS_CHARS)
        self.label = label
        self.parent = parent
        self.primary = primary
        self.hover = False
        self.down = False
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ENTER_WINDOW, lambda e: self.SetHover(True))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.SetHover(False))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, lambda e: self.SetDown(False))
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_SET_FOCUS, lambda e: self.Refresh())
        self.Bind(wx.EVT_KILL_FOCUS, lambda e: self.Refresh())

    def AcceptsFocus(self):
        return self.IsEnabled()

    def DoGetBestSize(self):
        return wx.Size(75, 26)

    def SetLabel(self, label):
        self.label = label
        self.Refresh()

    def GetLabel(self):
        return self.label

    def SetLabelText(self, label):
        self.SetLabel(label)

    def GetLabelText(self):
        return self.label

    def SetHover(self, on):
        self.hover = on
        self.Refresh()

    def SetDown(self, on):
        self.down = on
        self.Refresh()

    def Enable(self, enable=True):
        result = wx.Control.Enable(self, enable)
        self.Refresh()
        return result

    def Disable(self):
        return self.Enable(False)

    def SetDisable(self):
        self.Disable()

    def SetEnable(self):
        self.Enable()

    def SetFontPixelSize(self, size):
        pass

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        w, h = self.GetClientSize()
        enabled = self.IsEnabled()
        uikit.draw_button(dc, (0, 0, w, h), label=self.label, on=self.primary and enabled,
                          down=self.down and self.hover, hover=self.hover and enabled,
                          disabled=not enabled, font=uikit.get_font(12))
        if self.HasFocus() and enabled:
            gc = wx.GraphicsContext.Create(dc)
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(
                uikit.colour(uikit.ui().ACCENT_FG if self.primary else uikit.ui().ACCENT))
                .Width(1)))
            gc.SetBrush(wx.NullGraphicsBrush)
            gc.DrawRoundedRectangle(1, 1, w - 3, h - 3, uikit.RADIUS - 1)

    def OnLeftDown(self, event):
        if self.IsEnabled() is False:
            return
        self.SetFocus()
        self.CaptureMouse()
        self.SetDown(True)

    def OnLeftUp(self, event):
        if self.HasCapture():
            self.ReleaseMouse()
        clicked = self.down and self.GetClientRect().Contains(event.GetPosition())
        self.SetDown(False)
        if clicked:
            self.Click()

    def OnKeyDown(self, event):
        if event.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.Click()
            return
        event.Skip()

    def Click(self):
        if self.IsEnabled() is False:
            return
        event = wx.CommandEvent(wx.wxEVT_BUTTON, self.GetId())
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)


class SegmentBar(wx.Control):

    '''keys side by side, one of them chosen (a dialog's pages, in a notebook's tabs'
    place): on_change(index) when another is chosen'''

    GAP = 2

    def __init__(self, parent, labels, on_change, selection=0):
        wx.Control.__init__(self, parent, style=wx.BORDER_NONE)
        self.labels = list(labels)
        self.on_change = on_change
        self.selection = selection
        self.hovered = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.SetHovered(None))
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)

    def GetKeyWidths(self):
        dc = wx.ClientDC(self)
        dc.SetFont(uikit.get_font(12))
        return [dc.GetTextExtent(label)[0] + 28 for label in self.labels]

    def GetBestWidth(self):
        widths = self.GetKeyWidths()
        return sum(widths) + self.GAP * (len(widths) - 1)

    def GetRects(self):
        h = self.GetClientSize().height
        x, rects = 0, []
        for width in self.GetKeyWidths():
            rects.append(wx.Rect(x, 0, width, h))
            x += width + self.GAP
        return rects

    def SetHovered(self, index):
        if index != self.hovered:
            self.hovered = index
            self.Refresh()

    def OnMotion(self, event):
        hit = [k for k, rect in enumerate(self.GetRects()) if rect.Contains(event.GetPosition())]
        self.SetHovered(hit[0] if hit else None)

    def OnLeftDown(self, event):
        hit = [k for k, rect in enumerate(self.GetRects()) if rect.Contains(event.GetPosition())]
        if hit and hit[0] != self.selection:
            self.selection = hit[0]
            self.Refresh()
            self.on_change(self.selection)

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        for k, rect in enumerate(self.GetRects()):
            uikit.draw_button(dc, tuple(rect), label=self.labels[k], on=k == self.selection,
                              hover=k == self.hovered, font=uikit.get_font(12))


class FancyButton(wx.Button):

    def __init__(self, parent, label='', style=0):
        style = style | wx.NO_BORDER
        wx.Button.__init__(self, parent, label='', style=style)
        self.label = label
        self.parent = parent
        self.SetDoubleBuffered(True)
        font = wx.Font(8, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((6, 11))
        font.SetFaceName(FONT_ITEM)
        self.SetFont(font)
        self.buffer = Struct(bmp=None)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnMouseEnter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouseLeave)
        self.Bind(wx.EVT_LEFT_UP, self.OnMouseLeftUp)
        # self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvents)
        enabled = Struct(bg=(40, 40, 40), fg=(255, 255, 255), pen=(80, 80, 80))
        disabled = Struct(bg=(40, 40, 40), fg=(80, 80, 80), pen=(80, 80, 80))
        mouseover = Struct(bg=(50, 50, 50), fg=(255, 255, 255), pen=(80, 80, 80))
        colormap = Struct(enabled=enabled, disabled=disabled, mouseover=mouseover)
        self.SetColorMap(colormap)
        self.fontpixelsize = (6, 11)

    def SetColorMap(self, colormap):
        self.colormap = colormap
        self.bgcolor = self.colormap.enabled.bg
        self.fgcolor = self.colormap.enabled.fg
        self.pencolor = self.colormap.enabled.pen
        self.SetBackgroundColour(self.bgcolor)
        self.SetForegroundColour(self.fgcolor)

    def SetDisable(self):
        self.bgcolor = self.colormap.disabled.bg
        self.fgcolor = self.colormap.disabled.fg
        self.pencolor = self.colormap.disabled.pen
        self.Disable()
        self.DirectDraw()

    def SetEnable(self):
        self.bgcolor = self.colormap.enabled.bg
        self.fgcolor = self.colormap.enabled.fg
        self.pencolor = self.colormap.enabled.pen
        self.Enable()
        self.DirectDraw()

    def OnMouseEnter(self, event):
        self.bgcolor = self.colormap.mouseover.bg
        self.fgcolor = self.colormap.mouseover.fg
        self.pencolor = self.colormap.mouseover.pen
        self.DirectDraw()

    def OnMouseLeave(self, event):
        self.bgcolor = self.colormap.enabled.bg
        self.fgcolor = self.colormap.enabled.fg
        self.pencolor = self.colormap.enabled.pen
        self.DirectDraw()

    def OnMouseLeftUp(self, event):
        self.OnMouseLeave(None)
        event.Skip()

    def OnSize(self, event):
        self.DirectDraw()

    def InitBuffer(self):
        width, height = self.GetSize()
        # self.buffer.bmp = wx.EmptyBitmap(width, height)
        self.buffer.bmp = wx.Bitmap(width, height)
        dc = wx.BufferedDC(None, self.buffer.bmp)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.SetBackgroundMode(wx.TRANSPARENT)
        dc.Clear()
        self.SetRectDraw(dc)
        # self.reInitBuffer = False

    def SetFontPixelSize(self, size):
        self.fontpixelsize = size

    def SetRectDraw(self, dc):
        w, h = self.GetClientSize()
        dc.SetPen(wx.Pen(self.pencolor, 1))
        dc.SetBrush(wx.Brush(self.bgcolor, wx.SOLID))
        dc.DrawRectangle(0, 0, w, h)
        font = wx.Font(8, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetFaceName('Segoe UI')
        font.SetPixelSize(self.fontpixelsize)
        dc.SetFont(font)
        dc.SetTextForeground(self.fgcolor)
        tw, th, _, _ = dc.GetFullTextExtent(self.label, font)
        dc.DrawText(self.label, int((w - tw) * 0.5), int((h - th) * 0.5))

    def OnPaint(self, event):
        if self.buffer.bmp is None:
            return
        wx.BufferedPaintDC(self, self.buffer.bmp)

    def DirectDraw(self):
        self.InitBuffer()
        self.Refresh()

    def OnErase(self, event):
        pass
