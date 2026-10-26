# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


__appname__ = 'PyMusicPlayer'
__version__ = '1.1.1'
__author__ = 'Taehong Kim'
__email__ = 'peppy0510@hotmail.com'
__license__ = ''
__doc__ = '''
'''


import json
import macroboxstyle
import math
import mfeats
import multiprocessing
import os
import socketserver
import sys
import threading
import time
import radio
import wx

from dialogbox import AutoCheckUpdate
from listbox import ListBox
from listbox import ListBoxSash
from listbox import ListBoxSearch
from listbox import ListBoxTab
from listbox import StatusBox
from macroboxlib import BorderBoxH
from macroboxlib import EVENT_Scheduler
from macroboxlib import EventDistributor
from macroboxlib import GetPreference
from macroboxlib import MFEATS_Network_Scheduler
from macroboxlib import MFEATS_Scheduler
from macroboxlib import PopupMenuEventCatcher
from macroboxlib import RectRect
from macroboxlib import SUPPORTED_AUDIO_TYPE
from menubar import KeymapPreset
from menubar import MacroBoxMenuBar
from menubar import MacroBoxPreference
from playbox import PlayBox
from pybass import pybass
from utilities import Struct
from utilities import kill_existing_instances
from utilities import kill_self_process
from utilities import set_master_path
from utilities import set_process_priority
from wininstance import clear_instance_port
from wininstance import get_launch_desktop
from wininstance import is_test_launch
from wininstance import move_to_virtual_desktop
from wininstance import write_instance_port
# import setproctitle
# from packages import pybass
# from utilities import is_ghost_runnung
# from dialogbox import ProductLogRequest
# from macroboxlib import FileExecutionMonitor
# import modpybass as pybass


LOGGING = False

BOOT_NETWORK_SCHEDULER = False

MULTIPROCESSING_FORK = '--multiprocessing-fork'

# MAIN_SOCKET_PORT = 55557
MAIN_SOCKET_PORT = 55755
# a test's launch placed this long after it shows (wininstance.is_test_launch)
TEST_PLACE_MS = 600

# GRAB over 2 eats the tab scrollbar
LIST_SASH_WIDTH = 8
LIST_SASH_GRAB = 2
LIST_TAB_WIDTH = 180
LIST_TAB_WIDTH_MIN = 120
LIST_TAB_WIDTH_RATIO_MAX = 0.5
LIST_BOX_WIDTH_MIN = 240
LIST_TAB_ANIMATION_INTERVAL = 10
# wx.Timer will not notify finer than about 15ms
LIST_TAB_ANIMATION_DURATION = 80


# the search row's height over the list (ListBoxSearch)
SEARCH_ROW_HEIGHT = 32


class ListTabAnimationTimer(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent
        self.interval = LIST_TAB_ANIMATION_INTERVAL

    def Notify(self):
        self.parent.OnListTabAnimation()


class MainPanel(wx.Panel, RectRect, EventDistributor, PopupMenuEventCatcher):

    def __init__(self, parent):
        RectRect.__init__(self)
        wx.Panel.__init__(
            self, parent=parent, style=wx.CLIP_CHILDREN |
            wx.TAB_TRAVERSAL | wx.NO_BORDER | wx.FRAME_SHAPED)
        EventDistributor.__init__(self, parent=parent)
        PopupMenuEventCatcher.__init__(self, parent=parent)

        self.parent = parent
        self.DialogBox = None
        self.cache = Struct(eventskip=0)
        self.buffer = Struct(fps=30, lap=0, bmp=None)
        self.Event = EVENT_Scheduler(self)
        if BOOT_NETWORK_SCHEDULER:
            self.MFEATS = MFEATS_Network_Scheduler(self)
        else:
            self.MFEATS = MFEATS_Scheduler(self)

        self.showListTab = True
        self.list_tab_width = LIST_TAB_WIDTH
        self.list_tab_ratio = 1.0
        self.list_tab_ratio_start = 1.0
        self.list_tab_ratio_target = 1.0
        self.list_tab_lap = 0.0
        self.ListTabAnimation = ListTabAnimationTimer(self)
        self.PlayBox = PlayBox(self)
        self.ListBox = ListBox(self)
        self.ListTab = ListBoxTab(self)
        self.ListSash = ListBoxSash(self)
        self.ListSearch = ListBoxSearch(self)
        self.StatusBox = StatusBox(self)
        # self.BorderBoxHT = BorderBoxH(self)
        # bgcolor = parent.st.PLAYBOX.PLAY_BG_COLOR
        # self.BorderBoxHT.SetBackgroundColour(bgcolor)
        # (the window's bottom 5 px a bevel's gradient to a light grey before, the old
        # look's: none now, the status line at the bottom)
        self.BorderBoxHB = BorderBoxH(self)
        self.BorderBoxHB.SetBackgroundColour(self.StatusBox.GetBackgroundColour())
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_IDLE, self.OnIdle)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.InitBuffer()

    def EventSkipTimer(self):
        # prevent event from dialogbox with timer
        if self.cache.eventskip > 0:
            self.cache.eventskip -= 1
        elif self.DialogBox is not None:
            self.cache.eventskip = 5
        elif self.parent.DialogBox is not None:
            self.cache.eventskip = 5

    def HasToSkipEvent(self):
        if self.cache.eventskip > 0:
            return True
        return False

    def DistributeEvent(self, event):
        self.EventSkipTimer()
        self.PlayBox.CatchEvent(event)
        self.PlayBox.Wave.CatchEvent(event)
        self.PlayBox.WaveDetail.CatchEvent(event)
        self.PlayBox.Info.CatchEvent(event)
        self.PlayBox.ControlButton.CatchEvent(event)
        self.PlayBox.Title.CatchEvent(event)
        self.PlayBox.Spectrum.CatchEvent(event)
        self.PlayBox.VectorScope.CatchEvent(event)
        self.PlayBox.Apic.CatchEvent(event)
        self.PlayBox.VolumeSlider.CatchEvent(event)
        self.PlayBox.TempoButton.CatchEvent(event)
        self.PlayBox.KeyButton.CatchEvent(event)
        self.PlayBox.TempoStrip.CatchEvent(event)
        self.PlayBox.SnapButton.CatchEvent(event)
        self.PlayBox.RackBar.CatchEvent(event)
        self.PlayBox.Rack.CatchEvent(event)
        self.ListSash.CatchEvent(event)
        if self.ListBox.IsAnyListLocked() is False\
                and self.ListSash.IsOnSize() is False:
            self.ListTab.TabList.CatchEvent(event)
            self.ListTab.SliderV.CatchEvent(event)
            self.ListTab.TabHeader.CatchEvent(event)
            # the search row over the list (it had no row: off while it was hidden)
            self.ListSearch.CatchEvent(event)
            # self.ListBox.CatchEvent(event) #####
            # the list's header: sorting, and the columns' widths dragged at their edges
            self.ListBox.Header.CatchEvent(event)
            self.ListBox.List.CatchEvent(event)
            # shown when the columns are wider than the list (the radio's Browse tab)
            self.ListBox.SliderH.CatchEvent(event)
            self.ListBox.SliderV.CatchEvent(event)
        self.StatusBox.CatchEvent(event)

    def SetCursor(self, cursor):
        ListSash = getattr(self, 'ListSash', None)
        if ListSash is not None and ListSash.IsHot():
            return False
        return wx.Panel.SetCursor(self, cursor)

    def GetPlayBoxHeight(self):
        # the rack adds its height (over the header)
        master = self.PlayBox.GetRackHeight() + self.PlayBox.GetHeaderExtra()\
            + self.PlayBox.GetControlExtra()\
            if hasattr(self, 'PlayBox') else 0
        # (the waveforms' frame 8 px from the header over it and from the control row under
        # it: 4 px less than before, 12 over and 8 under)
        if self.parent.IsPlayerTopShowOn():
            # (the header 13 px lower than it was: PlayBox.HEADER_HEIGHT)
            return 154 + self.parent.GetWaveformDetailHeight() + master
        return 130 + self.parent.GetWaveformDetailHeight() + master

    def SetListRects(self):
        w, h = self.GetSize()
        pbh = self.GetPlayBoxHeight()
        sph = 4

        # if w < 740:
        if self.parent.IsListTabShowOn() or self.list_tab_ratio > 0.0:
            left_panel_min_activate_width = 718
            left_panel_min_activate_width = 0
        else:
            left_panel_min_activate_width = 999999

        if w < left_panel_min_activate_width:
            left_panel_width = 0
            right_panel_width = 0
            sash_width = 0
        else:
            left_panel_width = math.ceil(160 + (w - left_panel_min_activate_width) * 0.333)
            left_panel_width = self.LimitListTabWidth(self.list_tab_width)
            right_panel_width = 0
            sash_width = LIST_SASH_WIDTH

        list_tab_width = left_panel_width
        left_panel_width = int(round(left_panel_width * self.GetListTabRatio()))
        if left_panel_width <= 0:
            left_panel_width = 0
            sash_width = 0

        list_top = pbh + sph
        # down to the status line (its 27 rows at the window's bottom; the 5 under it gone)
        list_height = h - pbh + sph - (26 + 35) + 26
        # the search row across the window (its sidebar key at the left, over the sidebar;
        # a field of its own width whether the sidebar is open or not), the sidebar and the
        # list under it
        search = (0, list_top, w - right_panel_width, SEARCH_ROW_HEIGHT)
        below = list_top + SEARCH_ROW_HEIGHT
        height = list_height - SEARCH_ROW_HEIGHT
        list_box = (left_panel_width, below,
                    w - (left_panel_width + right_panel_width), height)
        list_tab = (left_panel_width - list_tab_width, below, list_tab_width, height)
        list_sash = (left_panel_width - LIST_SASH_GRAB, below, sash_width, height)

        self.ListSearch.SetRect(search)
        self.ListBox.SetRect(list_box)
        self.ListTab.SetRect(list_tab)
        self.ListSash.SetRect(list_sash)

    def OnSize(self, event=None):
        self.Freeze()
        self.cache.eventskip = 5
        pbh = self.GetPlayBoxHeight()
        w, h = self.GetSize()
        sph = 4
        size = self.PlayBox.GetSize()
        self.PlayBox.SetRect((0, 0, w, pbh + sph))
        # self.BorderBoxHT.SetRect((0, pbh, w, sph))

        self.SetListRects()
        # at the window's bottom (5 px over a bevel strip before, BorderBoxHB, now none)
        self.StatusBox.SetRect((0, h - 27, w, 27))

        # self.ListBox.SetRect((0, pbh + sph, w, h - pbh + sph - (24 + 26 + 35 + 5) + 26))
        # self.ListSearch.SetRect((0, h-24-27-5-26, w, 26))
        # self.ListSearch.SetRect((0, h - 24 - 27 - 5 - 26, w, 0))
        # self.StatusBox.SetRect((0, h - 24 - 27 - 5, w, 27))
        # self.ListTab.SetRect((0, h - 24 - 5, w, 24))

        self.BorderBoxHB.SetRect((0, h, w, 0))
        # a new size has laid the play box out already (its EVT_SIZE, in SetRect):
        # laid out again here it was done twice a step
        if self.PlayBox.GetSize() == size:
            self.PlayBox.OnSize()
        self.ListTab.OnSize()
        self.ListSearch.OnSize()
        self.ListBox.OnSize()
        self.StatusBox.OnSize()
        # self.BorderBoxHT.OnSize()
        self.BorderBoxHB.OnSize()
        self.Thaw()

    def OnListTabSize(self):
        self.Freeze()
        size = self.ListBox.GetSize()
        self.SetListRects()
        self.ListTab.OnSize()
        # a new size has laid the list out already (its EVT_SIZE, in SetRect): laid
        # out again here, a step of a sash dragged drew the list three times (80 ms)
        if self.ListBox.GetSize() == size:
            self.ListBox.OnSize()
        self.Thaw()

    def GetListTabRatio(self):
        r = self.list_tab_ratio
        return r * (2.0 - r)

    def AnimateListTabShow(self, show):
        if show:
            self.list_tab_ratio_target = 1.0
        else:
            self.list_tab_ratio_target = 0.0
        if self.list_tab_ratio == self.list_tab_ratio_target:
            self.OnSize()
            return
        if self.parent.IsShown() is False:
            self.list_tab_ratio = self.list_tab_ratio_target
            self.OnSize()
            return
        self.list_tab_ratio_start = self.list_tab_ratio
        self.list_tab_lap = time.time()
        if self.ListTabAnimation.IsRunning() is False:
            self.ListTabAnimation.Start(LIST_TAB_ANIMATION_INTERVAL)

    def OnListTabAnimation(self):
        span = self.list_tab_ratio_target - self.list_tab_ratio_start
        duration = LIST_TAB_ANIMATION_DURATION * abs(span)
        elapsed = (time.time() - self.list_tab_lap) * 1000.0
        if duration <= 0.0 or elapsed >= duration:
            self.list_tab_ratio = self.list_tab_ratio_target
            self.ListTabAnimation.Stop()
        else:
            self.list_tab_ratio = self.list_tab_ratio_start + span * (elapsed / duration)
        self.OnListTabSize()

    def GetListTabWidth(self):
        return self.list_tab_width

    def SetListTabWidth(self, width):
        width = self.LimitListTabWidth(width)
        if width == self.list_tab_width:
            return
        self.list_tab_width = width
        # the list tab, the sash and the list only (SetListRects): laid out whole
        # (OnSize), the player above was laid out and drawn at every step of a sash
        # dragged, and it hardly followed the mouse
        self.OnListTabSize()

    def ResetListTabWidth(self):
        self.SetListTabWidth(LIST_TAB_WIDTH)

    def LimitListTabWidth(self, width):
        w, h = self.GetSize()
        limit = math.floor(w * LIST_TAB_WIDTH_RATIO_MAX)
        if limit > w - LIST_BOX_WIDTH_MIN:
            limit = w - LIST_BOX_WIDTH_MIN
        if limit > LIST_TAB_WIDTH_MIN and width > limit:
            width = limit
        if width < LIST_TAB_WIDTH_MIN:
            width = LIST_TAB_WIDTH_MIN
        return width

    def SetRectPre(self):
        pass  # override this method

    def SetRectDraw(self, dc):
        pass  # override this method

    def __del__(self):
        pass


class MainSocketHandler(socketserver.StreamRequestHandler):

    def handle(self):
        data = self.rfile.readline().strip()
        if len(data) == 0:
            return
        data = json.loads(data)
        filepath = data.get('filepath')
        if filepath is None:
            return
        # wx is not thread safe
        wx.CallAfter(self.server.parent.parent.LoadMainSocketFile, filepath)
        # self.wfile.write(self.data.upper())


class MainSocket(threading.Thread):
    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.daemon = True
        self.port = MAIN_SOCKET_PORT
        self.parent = parent
        self.server = None
        self._quit = False
        self.start()

    def OpenServer(self):
        # the fixed port is not always available, fall back to any free one
        for port in (self.port, 0,):
            try:
                return socketserver.TCPServer(('127.0.0.1', port), MainSocketHandler)
            except OSError:
                continue
        return None

    def run(self):
        server = self.OpenServer()
        if server is None:
            return
        self.server = server
        self.port = server.server_address[1]
        write_instance_port(self.port)
        with server:
            server.parent = self
            server.serve_forever()

    def Quit(self):
        self._quit = True
        if self.server is not None:
            self.server.shutdown()


class MainFrame(wx.Frame, MacroBoxMenuBar, MacroBoxPreference, KeymapPreset):

    __appname__ = __appname__
    __version__ = __version__
    __author__ = __author__
    __email__ = __email__
    __license__ = __license__
    __doc__ = __doc__

    def __init__(self, parent=None, initfile=None):
        KeymapPreset.__init__(self)
        MacroBoxPreference.__init__(self)
        wx.Frame.__init__(self, parent, id=wx.ID_ANY,
                          pos=wx.DefaultPosition, size=wx.Size(800, 600),
                          style=wx.CLIP_CHILDREN | wx.FRAME_SHAPED | wx.MINIMIZE_BOX |
                          wx.MAXIMIZE_BOX | wx.SYSTEM_MENU | wx.CLOSE_BOX | wx.CAPTION |
                          wx.RESIZE_BORDER | wx.TAB_TRAVERSAL | wx.BORDER_DEFAULT)
        # style=wx.CLIP_CHILDREN|wx.FRAME_SHAPED|wx.TAB_TRAVERSAL|wx.BORDER_DEFAULT)
        self.initfile = initfile
        self.SetTitle(self.__appname__)
        self.DialogBox = None
        self.SetTransparent(255)
        self.SetMinSize((480, 450))
        self.SetMaxSize((-1, -1))
        # self.SetMaxSize((800, -1))
        # self.toolbar = self.CreateToolBar()
        self.MainPanel = MainPanel(self)
        self.MainPanel.MFEATS.AutoAnalyzer()
        MacroBoxMenuBar.__init__(self)
        self.LoadPreferences()
        self.SetMainFrameIcon()
        self.RestoreMainFrameRect()
        # the radio's tabs as a station's (made before with a playlist's columns; once the
        # lists are read, LoadPreferences)
        radio.repair_playlist_columns(self.MainPanel.ListBox)
        radio.ensure_station_columns(self.MainPanel.ListBox, rebuild=True)
        # the rack's modules shown when it closed: room for them with the list
        wx.CallAfter(self.FitRackRoom)
        fgsizer = wx.FlexGridSizer(1, 0, 0, 0)
        fgsizer.AddGrowableCol(0)
        fgsizer.AddGrowableRow(0)
        fgsizer.SetFlexibleDirection(wx.BOTH)
        fgsizer.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_SPECIFIED)
        fgsizer.Add(self.MainPanel, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL, 5)
        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        self.SetSizer(fgsizer)
        # self.LicenseCheckTimer = LicenseCheckTimer(self)
        self.Show()
        if is_test_launch():
            # (after the rack's room is made: its height set)
            wx.CallLater(TEST_PLACE_MS, self.PlaceForTest)
        elif get_launch_desktop():
            wx.CallLater(TEST_PLACE_MS, lambda: move_to_virtual_desktop(
                self.GetHandle(), get_launch_desktop()))
        self.LoadInitFile()
        self.GauranteeAlwaysOnTop()
        self.InitMainSocket()

        # ProductLogRequest()
        # self.FileExecutionMonitor = FileExecutionMonitor(self)
        # self.OnAbout(None)
        # self.OnPreference(None)
        # self.OnUpdate(None)
        # self.OnLicense(None)
        # self.OnCheckItemsConsistency(None)
        # print(setproctitle.getproctitle())
        # print(setproctitle.getthreadtitle())
        # setproctitle.setproctitle('pymp.exe')
        # setproctitle.setthreadtitle('pymp.exe')
        # print(setproctitle.getproctitle())
        # print(setproctitle.getthreadtitle())
        # os.environ["PYTHON_HOME"] = "C:\\Users\\tkmix\\WORK\\PyMusicPlayer"
        # os.environ["PYTHON_NAME"] = "pymp.exe"

    def InitMainSocket(self):
        MainSocket(self)

    def LoadMainSocketFile(self, filepath):
        self.LoadInitFile(filepath)
        if self.IsIconized():
            self.Iconize(False)
        self.Raise()

    def LoadInitFile(self, initfile=None):
        if initfile is None:
            initfile = self.initfile
        if initfile is None:
            return
        file_type = os.path.splitext(initfile)[1][1:].lower()
        if file_type not in SUPPORTED_AUDIO_TYPE:
            return
        self.MainPanel.PlayBox.cue.path = initfile
        self.MainPanel.PlayBox.OnPlay()
        # self.MainPanel.PlayBox.Info.reInitBuffer = True
        self.MainPanel.PlayBox.Title.reInitBuffer = True
        # self.MainPanel.PlayBox.Info.HandleInfoChange()

    def OnSize(self, event=None):
        self.Freeze()
        w, h = self.GetClientSize()
        size = self.MainPanel.GetSize()
        if self.IsPlayerOnlyModeOn():
            height = self.GetPlayerOnlyHeight()
            self.MainPanel.SetRect((0, 0, w, height))
        else:
            self.MainPanel.SetRect((0, 0, w, h))
        # a new size has laid the panel out already (its EVT_SIZE, in SetRect):
        # laid out again here it was done twice a step, the list drawn twice
        if self.MainPanel.GetSize() == size:
            self.MainPanel.OnSize()
        self.Thaw()

    def OnAutoCheckUpdate(self, event):
        self.AutoCheckUpdate = AutoCheckUpdate(self)

    def OnClose(self, event):
        self.Hide()
        clear_instance_port()
        self.SavePreferences()
        self.MainPanel.MFEATS.__del__()
        self.Destroy()
        kill_self_process()

    def __del__(self):
        pass


class MacroBoxApp(wx.App):

    # def __init__(self, parent=None, initfile=None):
    def __init__(self, parent=None, initfile=None, *argv, **kwargs):
        self.initfile = initfile
        wx.App.__init__(self, parent, *argv, **kwargs)

    def FilterEvent(self, event):
        return -1

    def OnPreInit(self):
        # a dark style: Windows' dark mode for the title bar, the menus and the standard
        # controls (wx 3.3), set before any window; a style chosen later takes it at the next
        # start. wx.App's own first: it makes the stock pens and brushes (without it
        # wx.TRANSPARENT_PEN and _BRUSH stayed invalid, drawn as a black pen and a white fill)
        wx.App.OnPreInit(self)
        if macroboxstyle.load(GetPreference('color_scheme')).UI.DARK:
            self.MSWEnableDarkMode(wx.App.DarkMode_Always)
        self.MainFrame = MainFrame(initfile=self.initfile)
        # DEBUG(hang): every thread's stack written when the GUI stops for 3 s; removed
        # once found
        import faulthandler
        beat = [time.time()]
        self.hang_timer = wx.Timer()
        self.hang_timer.Bind(wx.EVT_TIMER, lambda event: beat.__setitem__(0, time.time()))
        self.hang_timer.Start(250)
        import ctypes
        from macroboxlib import COUNTS

        def memory():
            class Counters(ctypes.Structure):
                _fields_ = [('cb', ctypes.c_ulong), ('faults', ctypes.c_ulong)] + [
                    (name, ctypes.c_size_t) for name in (
                        'peak', 'ws', 'qpp', 'qp', 'qnpp', 'qnp', 'page', 'ppage')]
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            ctypes.windll.psapi.GetProcessMemoryInfo(
                ctypes.c_void_p(-1), ctypes.byref(counters), counters.cb)
            return counters.ws // (1 << 20)

        def note(file):
            # (the boxes' drawing: ms a second since the last note)
            try:
                counts = dict(list(COUNTS.items()))
                file.write('memory %d MB, counts %s\n' % (memory(), counts))
                for key in [k for k in counts if k.startswith('ms ')]:
                    COUNTS.pop(key, None)
            except Exception as error:
                file.write('note failed: %r\n' % error)

        def watch():
            path = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'PyMusicPlayer', 'hang.log')
            lap = time.time()
            while True:
                time.sleep(1.0)
                if time.time() - lap > 15.0:
                    lap = time.time()
                    with open(path, 'a', encoding='utf-8') as file:
                        file.write('=== %s\n' % time.strftime('%H:%M:%S'))
                        note(file)
                if time.time() - beat[0] > 3.0:
                    with open(path, 'a', encoding='utf-8') as file:
                        file.write('--- %s\n' % time.strftime('%H:%M:%S'))
                        note(file)
                        file.flush()
                        faulthandler.dump_traceback(file=file, all_threads=True)
                    time.sleep(5.0)
        threading.Thread(target=watch, daemon=True).start()

    def __del__(self):
        pybass.BASS_Free()


def mainapp(initfile=None):
    if sys.platform.startswith('win'):
        multiprocessing.freeze_support()

    set_master_path()
    # ghost_name = 'macrobox.exe'
    # if is_ghost_runnung(ghost_name):
    #     if initfile is not None:
    #         pass_to_another_instance(initfile)
    #         return

    if initfile != MULTIPROCESSING_FORK:
        set_process_priority(2)
    else:
        set_process_priority(6)

    if BOOT_NETWORK_SCHEDULER:
        mfeats.boot_scheduler(os.getpid(), max_memory=0, max_idletime=0)
    if LOGGING is False:
        app = MacroBoxApp(initfile=initfile)
        # app.SetCallFilterEvent(False)
    elif LOGGING is True:
        filename = '%s.log' % (os.path.splitext(os.path.basename(__file__))[0])
        app = MacroBoxApp(initfile=initfile, filename=filename, redirect=True)
        app.SetCallFilterEvent(True)
    app.MainLoop()


def launch_mainapp(initfile=None):
    kill_existing_instances()
    mfeats.create_mfeats_table()
    mainapp(initfile)
    pybass.BASS_Free()


def main():
    try:
        launch_mainapp()
    except Exception:
        pass


if __name__ == '__main__':
    main()
