# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


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


import os
import sys
from utilities import get_user_docapp_path


TITLE = '%s %s' % (PRODUCT_NAME, PRODUCT_EDITION)
# PREFERENCE_DB = os.path.sep.join([get_user_docapp_path(), 'macroboxplayer.db'])
PREFERENCE_DB = os.path.sep.join([get_user_docapp_path(), 'macroboxplayer'])

SUPPORTED_PLAYLIST_TYPE = ('m3u',)
SUPPORTED_AUDIO_TYPE = (
    'mp2', 'mp3', 'mp4', 'wav', 'm4a',
    'ape', 'flac', 'aac', 'ac3', 'aiff', 'wma', 'ogg')  # wma, ogg
MUTAGEN_SUPPORTED_TYPE = ('mp2', 'mp3', 'mpg', 'mpeg')
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
except:
    packages = os.path.join('packages')

sys.path.insert(0, packages)


# from ctypes import WinDLL
# gdi32 = WinDLL('gdi32.dll')
# fonts = [font for font in os.listdir(packages)\
# 	if font.endswith('otf') or font.endswith('ttf')]
# for font in fonts: gdi32.AddFontResourceA(os.path.join(packages, font))


import wx
import wx.lib.newevent
import gc
import random
import mutagen
import mutagen.mp3
import mutagen.id3
import time
import stat
import glob
import audio
import mfeats
import threading
import multiprocessing
import urllib
import win32file
import win32pipe
from utilities import Struct
from utilities import save_shelve
from utilities import open_shelve
from utilities import save_shelves
from utilities import open_shelves
from utilities import PipeMessenger
from utilities import compress_object
from utilities import decompress_object
# from utilities import get_hostname
# from utilities import get_external_ip
# from utilities import get_macaddress
# import images
# import subprocess
# import numpy
# import win32con
# import webbrowser
# import _winreg as winreg
# import StringIO
# import cStringIO
# import re
# import math
# import json
# import socket
# import urllib2
# import httplib
# import platform
# import win32event
# import pywintypes
# import pybass
# import pickle
# import zlib
# import base64
# from copy import deepcopy
# from PIL import Image
# from PIL import ImageDraw
# import wx.lib.agw.shortcuteditor as ShortcutEditor
# from operator import attrgetter
# from operator import itemgetter
# from license import is_valid_license
# from license import generate_secretkey
# from license import generate_code
# from utilities import is_packaged
# from utilities import kill_self_process
# from utilities import run_hidden_subprocess
# from utilities import win32_unicode_argv
# from utilities import PipeReceiver
# from utilities import kill_ghost_process
# from utilities import is_process_running_by_name
# from utilities import set_process_priority
# from utilities import struct_to_dict
# from utilities import dict_to_struct
# from utilities import rgb_hex2dec
# from utilities import rgb_dec2hex
# from utilities import get_hddserial
# from utilities import get_macaddress
# from utilities import get_hostname
# from utilities import get_external_ip
# from utilities import send_pipe_message
# from utilities import SocketReceiver
# from utilities import SocketMessenger
# from utilities import send_socket_message
# from utilities import set_master_path
# from utilities import get_master_path
# from utilities import is_ghost_runnung


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
        self.AddColumn(key='tempo', title='tempo', right_align=True, id3=u'TBPM', width=55, max_width=55)
        self.AddColumn(key='key', title='key', id3=u'TKEY', width=55, max_width=55)

        self.AddColumn(key='type', title='type', show=False, private=True)
        self.AddColumn(key='size', title='size', show=False, private=True)
        self.AddColumn(key='artist', title='artist', id3=u'TPE1', show=False, private=True)
        self.AddColumn(key='title', title='title', id3=u'TIT2', show=False, private=True)
        self.AddColumn(key='album', title='album', id3=u'TALB', show=False, private=True)
        self.AddColumn(key='genre', title='genre', id3=u'TCON', show=False, private=True)
        self.AddColumn(key='bitrate', title='bitrate', show=False, private=True)
        self.AddColumn(key='samplerate', title='samplerate', show=False, private=True)
        self.AddColumn(key='channel', title='channel', show=False, private=True)
        self.AddColumn(key='path', title='path', show=False, private=True)
        self.AddColumn(key='mdx', title='mdx', show=False, private=True)


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
        self.selectedItems = []
        self.filterCache = None
        self.filterQuery = None
        self.items = []
        self.lastSortedColumn = [None, None]
        self.focus = Struct(item=-1, shift=-1)
        self.Id = time.clock()
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
        except:
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


def MakeMusicFileItem(path, order, columns):
    ext = os.path.splitext(path)[1][1:].lower()
    if ext not in SUPPORTED_AUDIO_TYPE:
        return None
    try:
        stats = os.stat(path)  # noqa
    except:
        return None
    size = "%.2f MB" % (stats[stat.ST_SIZE] / 1024.0**2)  # noqa
    file = os.path.basename(path)  # noqa
    filename = os.path.splitext(os.path.basename(path))[0]  # noqa

    id3tagFiledKeys = [v.id3 for v in columns if v.id3 is not None]
    audio_id3 = audio.get_id3(path, id3tagFiledKeys)
    if ext in MUTAGEN_SUPPORTED_TYPE:
        try:
            mutagen_mp3 = mutagen.mp3.MP3(path)
        except:
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
        except:
            tempo = ''
    mdx = audio.makemdx(path)
    resp = mfeats.getby_key_value('mdx', mdx)
    if resp is not None:
        if resp.highlight != '':
            highlight = resp.highlight[0]
            highlight = audio.second2time(highlight)
        tempo = resp.tempo
        duration = resp.duration
        try:
            tempo = '%05.1f' % (0.1 * round(tempo * 10))
        except:
            tempo = ''
        key = resp.key  # noqa
        status = 'analyzed'  # noqa
    duration = '%02d:%02d' % (duration / 60, duration % 60)

    item = [None] * len(columns)
    for i, v in enumerate(columns):
        try:
            item[i] = eval(v.key)
        except:
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
        # 	self.SetCursorSIZEWE()
        elif self.IsInTextEdit(event):
            pass
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
        xy = (event.x, event.y)
        rect = self.parent.ListBox.GetScreenRect()
        if self.parent.IsInRect(rect, xy):
            return True
        rect = self.parent.ListTab.GetScreenRect()
        if self.parent.IsInRect(rect, xy):
            return True
        rect = self.parent.ListSearch.GetScreenRect()
        if self.parent.IsInRect(rect, xy):
            return True
        return False

    def SetCursorARROW(self):
        self.parent.parent.MainPanel.SetCursor(self.cursor_stock.ARROW)
        self.SetCursorStatus('ARROW')

    def SetCursorWAIT(self):
        if self.cursor_status == 'WAIT':
            return
        self.parent.parent.MainPanel.SetCursor(self.cursor_stock.WAIT)
        self.SetCursorStatus('WAIT')

    def SetCursorARROWWAIT(self):
        if self.cursor_status == 'ARROWWAIT':
            return
        self.parent.parent.MainPanel.SetCursor(self.cursor_stock.ARROWWAIT)
        self.SetCursorStatus('ARROWWAIT')

    def SetCursorSIZEWE(self):
        if self.cursor_status == 'SIZEWE':
            return
        self.parent.parent.MainPanel.SetCursor(self.cursor_stock.SIZEWE)
        self.SetCursorStatus('SIZEWE')

    def SetCursorStatus(self, status):
        self.cursor_status = status


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

    def SetPopupMenu(self, obj, xy):
        if self.pending_popup_event is not None:
            self.pending_popup_event.object.Destroy()
        self.pending_popup_event = Struct(object=obj, x=xy[0], y=xy[1], pending=False)

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
        self.pending_popup_event = None

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
                except:
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


class MFEATS_Scheduler(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent
        self.interval = 50
        self.max_cores = multiprocessing.cpu_count()
        self.SetOptimalProcsLimit()
        # self.procs_limit = self.max_cores
        self.auto_analyzer_on = False
        self.procpath = []
        self.taskpath = []
        self.proclist = []
        self.stop = False
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
    # 	if self.proclist == []: return
    # 	for i in range(len(self.proclist)-1, -1, -1):
    # 		if self.proclist[i].proc.is_alive() is False:
    # 			self.proclist[i].proc._Thread__stop()
    # 			this = self.proclist.pop(i)
    # 			this.path
    # 			# self.Messenger.send_message(this.path, CLIENT_ADDRESS)

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
                self.AddMFEATSTask(path, urgent=False)

    def SetProcsLimit(self, value):
        self.procs_limit = value

    def AddMFEATSTask(self, path, urgent=False, forced=False):
        resp = mfeats.getby_key_value('path', path)
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

    def HandleFinishedJob(self):
        if self.proclist == []:
            return
        for i in range(len(self.proclist) - 1, -1, -1):
            if self.proclist[i].proc.is_alive() is False:
                # self.proclist[i].proc._Thread__stop()
                this = self.proclist.pop(i)
                path = this.path
                idx = [i for i, v in enumerate(self.procpath) if v == path]
                if idx == []:
                    return
                path = self.procpath.pop(idx[0])
                self.UpdateItemsValue(path)

    def SendJobToProcessor(self):
        if self.IsProcsFull():
            return
        if self.HasTask() is False:
            return
        path = self.taskpath.pop(0)
        if path in self.procpath:
            return
        self.proclist.append(Struct(path=path, proc=mfeats.Process(path)))
        # self.proclist.append(Struct(path=path, proc=mfeats.Thread(path)))
        self.proclist[-1].daemon = True
        self.proclist[-1].proc.start()
        self.procpath.append(path)
        self.UpdateItemsValue(path)

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
        resp = mfeats.getby_key_value('mdx', mdx)
        if resp is None:
            # analyzing status uses GetProcPath
            self.parent.ListBox.SetListItemsValueWhereColumnKey(
                ('mdx', mdx), ('status', ''))
            self.parent.ListBox.List.DirectDraw()
            return

        key = resp.key
        tempo = resp.tempo
        duration = resp.duration
        duration = '%02d:%02d' % (duration / 60, duration % 60)
        try:
            tempo = '%05.1f' % (0.1 * round(tempo * 10))
        except:
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
        for i in range(len(self.proclist)):
            self.proclist[i].proc.join()
        # for i in range(len(self.proclist)):
        # 	self.proclist[i].proc._Thread__stop()

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
                self.AddMFEATSTask(path, urgent=False)

    def SetProcsLimit(self, value):
        self.procs_limit = int(value)

    def AddMFEATSTask(self, path, urgent=False, forced=False):
        resp = mfeats.getby_key_value('path', path)
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
                # 	self.wakeup = True
        if self.wakeup is False:
            return
        # if mfeats.is_scheduler_running(): return
        # self.wakeup = False
        # mfeats.boot_scheduler()
        # for path in self.GetProcPath():
        # 	self.Messenger.send_socket_message(path, mfeats.SERVER_ADDRESS)

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
        resp = mfeats.getby_key_value('mdx', mdx)
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
        except:
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
        # 	mfeats.SERVER_ADDRESS, urgent=True)
        time.sleep(0.1)
        self.Messenger.terminate()
        self.Messenger._Thread__stop()


evt_global, EVT_GLOBAL = wx.lib.newevent.NewEvent()


class EVENT_Scheduler(wx.Timer, CursorEventCatcher):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        CursorEventCatcher.__init__(self, parent)
        self.parent = parent
        self.interval = 25
        self.cache = self.InitEvent()
        self.last_screen_rect = None
        self.Start(self.interval)
        self.onsize = False
        # self.path = None
        self.stop = False
        self.LeftUpDelayedCounter = None  # MAC

    def StopNotify(self):
        self.stop = True

    def StartNotify(self):
        self.stop = False

    def Notify(self):
        if self.stop:
            return
        event = self.MakeEvent()
        self.CatchCurserEvent(event)
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

        if event.LeftDown or event.RightDown or event.MiddleDown:
            event.down.X, event.down.Y = self.ScreenToClient((event.down.x, event.down.y))
            event.down.rectIdx = self.GetRectIdx((event.down.X, event.down.Y))
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

        # keyboard up down # darwin 10051, 10054
        # print event.EventType
        if event.EventType in (10051, 10054, 10055, 10056, 10057, 10058, 10059):
            new_event.KeyCode = event.KeyCode
            new_event.RawKeyFlags = event.GetRawKeyFlags()

        # wheelrotation # darwin 10042
        if event.EventType in (10042, 10045, 10046, 10047):
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


class RectRect():

    def __init__(self):
        self.buffer = Struct(fps=120, lap=time.time(), bmp=None)

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
        limit = len([i for i in dc.GetPartialTextExtents(string) if i <= width - margin])
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
        # self.buffer.bmp = wx.EmptyBitmap(width, height)
        self.buffer.bmp = wx.Bitmap(width, height)
        dc = wx.BufferedDC(None, self.buffer.bmp)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.SetBackgroundMode(wx.TRANSPARENT)
        dc.Clear()
        self.SetRectDraw(dc)
        self.reInitBuffer = False

    def OnSize(self, event):
        self.DirectDraw()

    def OnIdle(self, event):
        if self.reInitBuffer is False:
            return
        elapsed_time = time.time() - self.buffer.lap
        if elapsed_time < 1.0 / self.buffer.fps:
            return
        self.buffer.lap = time.time()
        self.InitBuffer()
        self.Refresh(False)

    def OnPaint(self, event):
        if self.buffer.bmp is None:
            return
        wx.BufferedPaintDC(self, self.buffer.bmp)

    def DirectDraw(self):
        elapsed_time = time.time() - self.buffer.lap
        if elapsed_time < 1.0 / self.buffer.fps:
            return
        self.buffer.lap = time.time()
        self.InitBuffer()
        self.Refresh(False)

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
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
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
            except:
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
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
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
    except:
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
        except:
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
    except:
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
    except:
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
    except:
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
            # 	# uri = release.data['images'][0]['uri']
            # 	uri = release.data['images'][0]['uri150']
            # 	artwork = urllib.urlopen(uri).read()
            # 	info.discogs.images.append(artwork)
            queue.put(info)
    except:
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
        except:
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


class DialogBox(wx.Dialog):

    def __init__(self, parent, id=-1, size=(-1, -1), pos=(-1, -1), style=0):
        style = style | wx.CLIP_CHILDREN | wx.CAPTION | wx.TAB_TRAVERSAL |\
            wx.NO_FULL_REPAINT_ON_RESIZE | wx.STAY_ON_TOP | wx.CLOSE_BOX | wx.NO_BORDER
        wx.Dialog.__init__(self, parent, id=id, size=size, pos=pos, style=style)
        self.parent = parent
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour((230, 230, 230))
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def OnSize(self, event):
        pass

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
        self.SetBackgroundColour((230, 230, 230))
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
        margin = 10
        width, height = self.parent.GetClientSize()
        self.UserInput.SetRect((margin, margin, width - margin * 2, 22))

    def GetValue(self):
        return self.UserInput.GetValue()

    def SetValue(self, value):
        self.UserInput.SetValue(value)

    def OnClose(self, event):
        self.Destroy()


class UserInputDialogBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(190, 115))
        self.parent = parent
        self.UserInput = UserInputDialogPanel(self)
        self.ApplyButton = Button(self, label='')
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CloseButton = Button(self, label='Cancel')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.OnSize(None)

    def OnSize(self, event):
        margin = 10
        width, height = self.GetClientSize()
        self.UserInput.SetRect((0, 0, width, 40))
        self.UserInput.OnSize(None)
        self.ApplyButton.SetRect((width / 2 - 75 - 3, height - margin - 24, 75, 24))
        self.CloseButton.SetRect((width / 2 + 3, height - margin - 24, 75, 24))

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
        margin = 10
        width, height = self.GetClientSize()
        self.Message.SetPosition((margin, margin + 3))
        self.Message.SetInitialSize((width - margin * 2, 22))

    def SetLabelText(self, value):
        self.Message.SetLabelText(value)
        self.OnSize(None)

    def OnClose(self, event):
        self.Destroy()


class ConfirmDialogBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(180, 105))
        self.parent = parent
        self.Message = ConfirmDialogPanel(self)
        self.ApplyButton = Button(self, label='')
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CloseButton = Button(self, label='Cancel')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.OnSize(None)

    def OnSize(self, event):
        margin = 10
        width, height = self.GetClientSize()
        self.Message.SetRect((0, 0, width, 40))
        self.Message.OnSize(None)
        self.ApplyButton.SetRect((width / 2 - 75 - 2, height - margin - 24, 75, 24))
        self.CloseButton.SetRect((width / 2 + 3, height - margin - 24, 75, 24))
        # self.ApplyButton.SetRect((margin, height-margin-24, 75, 24))
        # self.CloseButton.SetRect((width-75-margin, height-margin-24, 75, 24))

    def OnApply(self, event):
        self.OnClose(event)

    def OnClose(self, event):
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class SpinCtrl(wx.SpinCtrl):

    def __init__(self, parent, id=-1, value='', pos=(-1, -1), size=(60, 24), style=0):
        wx.SpinCtrl.__init__(self, parent, id=id, value=value,
                             pos=pos, size=size, style=style | wx.ALIGN_RIGHT)
        self.value = value
        self.parent = parent
        self.SetDoubleBuffered(True)
        font = wx.Font(8, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetFaceName('Consolas')
        font.SetPixelSize((7, 14))
        self.SetFont(font)


class ComboBox(wx.ComboBox):

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
        # self.fontpixelsize = size


class TextCtrl(wx.TextCtrl):

    def __init__(self, parent, id=-1, value='',
                 pos=(-1, -1), size=(75, 24), style=0):
        wx.TextCtrl.__init__(self, parent, id=id,
                             value=value, pos=pos, size=size, style=style)
        self.parent = parent
        self.SetDoubleBuffered(True)
        font = wx.Font(8, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetFaceName(FONT_ITEM)
        font.SetPixelSize((6, 12))
        self.SetFont(font)


class CheckBox(wx.CheckBox):

    def __init__(self, parent, id=-1, label='', pos=(-1, -1), size=(-1, 15), style=0):
        wx.CheckBox.__init__(self, parent, id=id,
                             label=label, pos=pos, size=size, style=style)
        self.label = label
        self.SetDoubleBuffered(True)
        self.SetForegroundColour((30, 30, 30))
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
        self.SetForegroundColour((30, 30, 30))
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
        self.fgcolor = (0, 0, 0)
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


class Button(wx.Button):

    def __init__(self, parent, id=-1, label='', pos=(-1, -1), size=(75, 26), style=0):
        wx.Button.__init__(self, parent, id=id,
                           label=label, pos=pos, size=size, style=style)
        self.label = label
        self.parent = parent
        self.SetDoubleBuffered(True)
        self.bgcolor = (40, 40, 40)
        self.fgcolor = (0, 0, 0)
        self.SetForegroundColour(self.fgcolor)
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((6, 12))
        font.SetFaceName(FONT_ITEM)
        self.SetFont(font)

    def SetFontPixelSize(self, size):
        font = self.GetFont()
        font.SetPixelSize(size)
        self.SetFont(font)

    def SetDisable(self):
        self.Disable()

    def SetEnable(self):
        self.Enable()


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


class ScriptControl():

    def __init__(self):
        self.InitScriptVars()
        self.InitScriptPath()
        self.CONTEXT_MENU = '# CONTEXT MENU'

    def SetPlayBox(self, PlayBox):
        self.PlayBox = PlayBox

    def SetListBox(self, ListBox):
        self.ListBox = ListBox

    def InitScriptVars(self):
        self.scriptvars = (('path', 'FILEPATH', False),
                           ('filename', 'FILENAME', True), ('type', 'FILETYPE', True),
                           ('album', 'ALBUM', True), ('artist', 'ARTIST', True),
                           ('title', 'TITLE', True), ('genre', 'GENRE', True),
                           ('key', 'KEY', True), ('tempo', 'TEMPO', True),
                           ('bitrate', 'BITRATE', False), ('channel', 'CHANNEL', False),
                           ('size', 'SIZE', False), ('duration', 'DURATION', False))

    def GetScriptChoices(self):
        if os.path.isdir(self.scriptpath) is False:
            os.mkdir(self.scriptpath)
        paths = glob.glob(os.path.join(self.scriptpath, u'*.py'))
        choices = [os.path.basename(path)[:-3] for path in paths]
        if len(choices) == 0:
            choices.append('')
        return sorted(choices)

    def GetScriptShortCuts(self):
        if os.path.isdir(self.scriptpath) is False:
            os.mkdir(self.scriptpath)
        paths = glob.glob(os.path.join(self.scriptpath, u'*.py'))
        shortcutpaths = list()
        for i in range(len(paths)):
            f = open(paths[i], 'rb')
            if self.CONTEXT_MENU in f.read():
                shortcutpaths.append(paths[i])
            f.close()
        choices = [os.path.basename(path)[:-3] for path in shortcutpaths]
        if len(choices) == 0:
            choices.append('')
        return sorted(choices)

    def InitScriptPath(self):
        self.scriptpath = os.path.join(get_user_docapp_path(), 'script')

    def GetScriptPath(self):
        return self.scriptpath

    def GetScriptResult(self, script=None):
        if script is None:
            script = self.EditorPanel.TextCtrl.GetValue()
        # scriptpath = self.GetScriptPath()
        scriptvars = self.GetScriptVars()
        # listIdx = self.ListBox.GetSelectedListIdx()
        command = "thisItem.%s = self.ListBox.GetItemValueByColumnKey(itemIdx, '%s', listIdx)"
        self.preview_result = list()
        for count, itemIdx in enumerate(self.ListBox.GetSelectedItems()):
            thisItem = Struct()
            for v in scriptvars:
                exec(command % (v[1], v[0]))
            thisItem.COUNT = count + 1
            syspath = sys.path
            import rename
            self.preview_result += [rename.rename(
                thisItem, script, [self.GetScriptPath()])]
            # syspath = sys.path
        return self.preview_result

    def GetSelectedScriptPath(self, selected=None):
        if os.path.isdir(self.GetScriptPath()) is False:
            os.mkdir(self.GetScriptPath())
        if selected is None:
            selected = self.ScriptSelector.GetValue()
        selected = '.'.join((selected, 'py'))
        return os.path.join(self.scriptpath, selected)

    def GetScriptVars(self):
        return self.scriptvars

    def ProcessScript(self, results, preview=None):
        if results is None:
            return
        if len(results) == 0:
            return
        if preview == 'ERROR':
            return
        scriptvars = [v for v in self.GetScriptVars() if v[2] is True]
        for i in range(len(results)):
            oldPath = results[i].FILEPATH
            listItemsIdx = self.ListBox\
                .GetListItemsIdxByColumnKeyValue('path', oldPath)
            itemIdx = listItemsIdx[0][1]
            selectedList = listItemsIdx[0][0]

            is_playing_item = False
            path_resp = False
            if self.PlayBox.IsPlaying():
                if oldPath == self.PlayBox.GetPlayingItemInfo('path'):
                    is_playing_item = True
                    self.PlayBox.OnPause()
                    # resume = self.PlayBox.cue.resume

            for v in scriptvars:
                exec('new = results[i].%s' % (v[1]))
                exec('old = self.originals[i].%s' % (v[1]))
                if type(old) != unicode:
                    old = old.decode(sys.getfilesystemencoding())
                if new == old:
                    continue

                if v[0] == 'filename':
                    # new = new.encode(sys.getfilesystemencoding())
                    newFilename = self.ListBox.LimitFileName(new)
                    pathBase = os.path.sep.join(oldPath.split(os.path.sep)[:-1])
                    fileType = os.path.splitext(oldPath)[-1]
                    newPath = ''.join((os.path.join(pathBase, newFilename), fileType))
                    if oldPath != newPath:
                        path_resp = self.ListBox\
                            .RenameFileByItemIdx(itemIdx, newPath, selectedList)

                columnIdx = self.ListBox\
                    .GetColumnKeyToIdx(v[0], selectedList)
                if self.ListBox\
                        .IsID3TAGColumnByColumnIdx(columnIdx, selectedList):
                    if v[0] == 'tempo':
                        try:
                            new = float(new)
                            new = u'%05.1f' % (0.1 * round(new * 10))
                        except:
                            new = ''
                    tag_resp = self.parent.MainPanel\
                        .ListBox.RenameID3TAGByColumnItemIdx(
                            columnIdx, itemIdx, new, selectedList)

            if is_playing_item:
                if path_resp:
                    self.PlayBox.cue.path = newPath
                    self.PlayBox.cue.mdx\
                        = self.PlayBox.GetMDX(newPath)
                    self.PlayBox.cue.item\
                        = MakeMusicFileItem(newPath, 0, ListBoxColumn())
                self.PlayBox.OnResume()

    def GetScriptVarsChoices(self):
        choices = [v[1] for v in self.GetScriptVars() if v[2] is True]
        return choices + ['CUSTOMFIELD']


class ScriptProcessProgressTimer(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent
        self.stop = False

    def Notify(self):
        if self.stop:
            return
        self.parent.UpdateProgress()

    def Stop(self, event=None):
        self.stop = True


class ScriptProcessProgressBox(DialogBox, ScriptControl):

    def __init__(self, parent):
        ScriptControl.__init__(self)
        DialogBox.__init__(self, parent, size=(250, 105 + 25))
        self.parent = parent
        self.Message = StaticText(self, style=wx.ALIGN_CENTER)
        self.ProgressBar = wx.Gauge(self)
        self.CloseButton = Button(self, label='Cancel')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.interval = 1
        self.item_count = 0
        self.item_total = 0
        self.check_somemore = 5
        self.cache = list()
        self.OnSize(None)
        choices = self.GetScriptVarsChoices()
        self.selected_field = choices[self.parent.PreviewField.GetSelection()]

    def UpdateProgress(self):
        result = self.cache
        self.cache = list()
        self.parent.process_result += [result]
        self.parent.PreviewPanel.TextCtrl.SetReadOnly(False)
        for v in result:
            exec('preview = unicode(v[1][1].%s)' % (self.selected_field))
            self.parent.PreviewPanel.TextCtrl.AppendText(preview)
            self.parent.PreviewPanel.TextCtrl.DocumentEnd()
            self.parent.PreviewPanel.TextCtrl.NewLine()
            self.parent.PreviewPanel.TextCtrl.EmptyUndoBuffer()
        self.parent.PreviewPanel.TextCtrl.SetReadOnly(True)
        self.parent.PreviewPanel.SliderV.DirectDraw()
        self.parent.PreviewPanel.SliderH.DirectDraw()

        margin = 10
        width, height = self.GetClientSize()
        label = 'Processing script. (%d/%d tracks)'\
                % (self.item_count, self.item_total)
        self.Message.SetLabelText(label)
        self.Message.SetInitialSize((width - margin * 2, 22))
        self.ProgressBar.SetValue(self.item_count)

        if self.item_count != self.item_total:
            return
        if self.check_somemore > 0:
            self.check_somemore -= 1
            return
        self.parent.PreviewField.Disable()
        self.Timer.Stop()
        # self.parent.ProcessButton.SetEnable()
        self.OnClose(None)

    def StartRendering(self):
        self.item_count = 0
        self.parent.process_result = list()
        self.Timer = ScriptProcessProgressTimer(self)
        self.Timer.Start(self.interval)
        self.Thread = threading.Thread(
            target=self.RenderProcess, name='script_process', args=())
        self.Thread.start()

    def RenderProcess(self):
        # print self.parent.preview_result
        # if results is None: return
        # if len(results) == 0: return
        # if preview == 'ERROR': return
        # print dir(self.parent.preview_result[0][0][0])

        allpaths = list()
        uresults = list()
        for v in self.parent.preview_result:
            if v[0].FILEPATH in allpaths:
                continue
            allpaths.append(v[0].FILEPATH)
            uresults.append(v)

        self.item_total = len(allpaths)
        self.item_duplicated = len(self.parent.preview_result) - self.item_total
        self.ProgressBar.SetRange(self.item_total)
        self.parent.PreviewPanel.TextCtrl.SetValue(u'')
        for result in uresults:
            if len(result) == 0:
                continue
            self.item_count += 1
            listItemsIdx = self.parent.ListBox\
                .GetListItemsIdxByColumnKeyValue('path', result[0].FILEPATH)
            listIdx = listItemsIdx[0][0]
            itemIdx = listItemsIdx[0][1]
            time.sleep(0.001)
            resp = self.ProcessScriptByListItemIdx(listIdx, itemIdx, result)
            self.cache += [(resp, result)]

    def ProcessScriptByListItemIdx(self, listIdx, itemIdx, result):
        scriptvars = [v for v in self.GetScriptVars() if v[2] is True]
        result_old, result_new = result
        path_resp = False
        is_playing_item = False
        oldPath = result_old.FILEPATH
        if self.parent.PlayBox.IsPlaying():
            if oldPath == self.parent.PlayBox.GetPlayingItemInfo('path'):
                is_playing_item = True
                self.parent.PlayBox.OnPause()
                resume = self.parent.PlayBox.cue.resume

        for v in scriptvars:
            exec('old = result_old.%s' % (v[1]))
            exec('new = result_new.%s' % (v[1]))
            if type(old) != unicode:
                old = old.decode(sys.getfilesystemencoding())
            if new == old:
                continue

            if v[0] == 'filename':
                # new = new.encode(sys.getfilesystemencoding())
                newFilename = self.parent.ListBox.LimitFileName(new)
                pathBase = os.path.sep.join(oldPath.split(os.path.sep)[:-1])
                fileType = os.path.splitext(oldPath)[-1]
                newPath = ''.join((os.path.join(pathBase, newFilename), fileType))
                if oldPath != newPath:
                    path_resp = self.parent.ListBox\
                        .RenameFileByItemIdx(itemIdx, newPath, listIdx)

            columnIdx = self.parent.ListBox.GetColumnKeyToIdx(v[0], listIdx)
            if self.parent.ListBox.IsID3TAGColumnByColumnIdx(columnIdx, listIdx):
                if v[0] == 'tempo':
                    try:
                        new = float(new)
                        new = u'%05.1f' % (0.1 * round(new * 10))
                    except:
                        new = ''
                tag_resp = self.parent.parent.MainPanel\
                    .ListBox.RenameID3TAGByColumnItemIdx(
                        columnIdx, itemIdx, new, listIdx)

        if is_playing_item:
            if path_resp:
                self.parent.PlayBox.cue.path = newPath
                self.parent.PlayBox.cue.mdx = self.parent.PlayBox.GetMDX(newPath)
                self.parent.PlayBox.cue.item = MakeMusicFileItem(newPath, 0, ListBoxColumn())
            self.parent.PlayBox.OnResume()

    def OnSize(self, event):
        margin = 10
        width, height = self.GetClientSize()
        self.Message.SetPosition((margin, 15))
        self.Message.SetInitialSize((width - margin * 2, 22))
        self.ProgressBar.SetRect((margin * 2, 45, width - margin * 4, 10))
        self.CloseButton.SetRect(((width - 75) / 2 + 1, height - 24 - margin, 75, 24))

    def OnApply(self, event):
        self.OnClose(event)

    def OnClose(self, event):
        self.Timer.Stop()
        if self.Thread.is_alive():
            self.Thread._Thread__stop()
            # self.Thread.Destroy()
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class ScriptPreviewProgressTimer(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent
        self.stop = False

    def Notify(self):
        if self.stop:
            return
        self.parent.UpdateProgress()

    def Stop(self, event=None):
        self.stop = True


class ScriptPreviewProgressBox(DialogBox, ScriptControl):

    def __init__(self, parent):
        ScriptControl.__init__(self)
        DialogBox.__init__(self, parent, size=(250, 105 + 25))
        self.parent = parent
        self.Message = StaticText(self, style=wx.ALIGN_CENTER)
        self.ProgressBar = wx.Gauge(self)
        self.CloseButton = Button(self, label='Cancel')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.interval = 1
        self.item_count = 0
        self.item_total = 0
        self.check_somemore = 5
        self.cache = list()
        self.OnSize(None)
        choices = self.GetScriptVarsChoices()
        self.selected_field = choices[self.parent.PreviewField.GetSelection()]

    def UpdateProgress(self):
        result = self.cache
        self.cache = list()
        if len(result) > 0:
            self.parent.preview_result += result
        self.parent.PreviewPanel.TextCtrl.SetReadOnly(False)
        for v in result:
            # preview = unicode(v[1].PREVIEW)
            try:
                exec('preview = unicode(v[1].%s)' % (self.selected_field))
            except:
                preview = 'ERROR'
            self.parent.PreviewPanel.TextCtrl.AppendText(preview)
            self.parent.PreviewPanel.TextCtrl.DocumentEnd()
            self.parent.PreviewPanel.TextCtrl.NewLine()
            self.parent.PreviewPanel.TextCtrl.EmptyUndoBuffer()
        self.parent.PreviewPanel.TextCtrl.SetReadOnly(True)
        self.parent.PreviewPanel.SliderV.DirectDraw()
        self.parent.PreviewPanel.SliderH.DirectDraw()

        margin = 10
        width, height = self.GetClientSize()
        label = 'Rendering preview. (%d/%d tracks)'\
                % (self.item_count, self.item_total)
        self.Message.SetLabelText(label)
        self.Message.SetInitialSize((width - margin * 2, 22))
        self.ProgressBar.SetValue(self.item_count)

        if self.item_count != self.item_total:
            return
        if self.check_somemore > 0:
            self.check_somemore -= 1
            return
        self.Timer.Stop()
        self.parent.ProcessButton.SetEnable()
        self.OnClose(None)

    def StartRendering(self):
        self.parent.preview_result = list()
        self.Timer = ScriptPreviewProgressTimer(self)
        self.Timer.Start(self.interval)
        self.Thread = threading.Thread(
            target=self.RenderPreview, name='script_preview', args=())
        self.Thread.start()

    def RenderPreview(self):
        self.parent.PreviewPanel.TextCtrl.SetValue(u'')
        selectedIdx = self.parent.ScopeSelector.GetCurrentSelection()
        update_time = 0.001

        if selectedIdx == 0:
            listsIdx = range(len(self.parent.ListBox.innerList))
            self.item_total = sum([self.parent.ListBox
                                   .GetItemsLength(listIdx) for listIdx in listsIdx])
            self.ProgressBar.SetRange(self.item_total)
            self.item_count = 0
            for listIdx in listsIdx:
                itemsIdx = range(self.parent.ListBox.GetItemsLength(listIdx))
                for itemIdx in itemsIdx:
                    self.item_count += 1
                    if self.Timer.stop:
                        return
                    old, new = self.GetScriptResultByListItemIdx(
                        listIdx, itemIdx, self.item_count)
                    self.cache.append((old, new))
                    if update_time != 0:
                        time.sleep(update_time)

        if selectedIdx == 1:
            listIdx = self.parent.ListBox.GetSelectedListIdx()
            itemsIdx = range(self.parent.ListBox.GetItemsLength())
            self.item_total = len(itemsIdx)
            self.ProgressBar.SetRange(self.item_total)
            for count, itemIdx in enumerate(itemsIdx):
                self.item_count = count + 1
                if self.Timer.stop:
                    return
                old, new = self.GetScriptResultByListItemIdx(listIdx, itemIdx, count)
                self.cache.append((old, new))
                if update_time != 0:
                    time.sleep(update_time)

        if selectedIdx == 2:
            listIdx = self.parent.ListBox.GetSelectedListIdx()
            itemsIdx = self.parent.ListBox.GetSelectedItems()
            self.item_total = len(itemsIdx)
            self.ProgressBar.SetRange(self.item_total)
            for count, itemIdx in enumerate(itemsIdx):
                self.item_count = count + 1
                if self.Timer.stop:
                    return
                old, new = self.GetScriptResultByListItemIdx(listIdx, itemIdx, count)
                self.cache.append((old, new))
                if update_time != 0:
                    time.sleep(update_time)

    def GetScriptResultByListItemIdx(self, listIdx, itemIdx, count=0, script=None):
        if script is None:
            script = self.parent.EditorPanel.TextCtrl.GetValue()
        command = "thisItem.%s = self.parent.ListBox.GetItemValueByColumnKey(itemIdx, '%s', listIdx)"
        thisItem = Struct()
        for v in self.GetScriptVars():
            exec(command % (v[1], v[0]))
        oldpath = thisItem.FILEPATH
        thisItem.COUNT = count + 1
        syspath = sys.path
        import rename
        result = rename.rename(thisItem, script, [self.GetScriptPath()])
        syspath = sys.path
        return thisItem, result

    def OnSize(self, event):
        margin = 10
        width, height = self.GetClientSize()
        self.Message.SetPosition((margin, 15))
        self.Message.SetInitialSize((width - margin * 2, 22))
        self.ProgressBar.SetRect((margin * 2, 45, width - margin * 4, 10))
        self.CloseButton.SetRect(((width - 75) / 2 + 1, height - 24 - margin, 75, 24))

    def OnApply(self, event):
        self.OnClose(event)

    def OnClose(self, event):
        self.Timer.Stop()
        if self.Thread.is_alive():
            self.Thread._Thread__stop()
            # self.Thread.Destroy()
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()
