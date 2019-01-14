# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import os
import sys

# packages = os.path.join(os.path.split(os.path.split(os.path.abspath(__file__))[0])[0], 'venv', 'Lib', 'site-packages')
# sys.path.insert(0, packages)

import mfeats
import multiprocessing
import wx

from dialogbox import AutoCheckUpdate
from listbox import ListBox
from listbox import ListBoxSearch
from listbox import ListBoxTab
from listbox import StatusBox
from macroboxlib import BorderBoxH
from macroboxlib import EVENT_Scheduler
from macroboxlib import EventDistributor
from macroboxlib import MFEATS_Network_Scheduler
from macroboxlib import MFEATS_Scheduler
from macroboxlib import PopupMenuEventCatcher
from macroboxlib import RectRect
from macroboxlib import SUPPORTED_AUDIO_TYPE
from macroboxlib import TITLE
from menubar import KeymapPreset
from menubar import MacroBoxMenuBar
from menubar import MacroBoxPreference
from packages import pybass
from playbox import PlayBox
from utilities import Struct
from utilities import kill_self_process
from utilities import set_master_path
from utilities import set_process_priority
# from utilities import is_ghost_runnung
# from dialogbox import ProductLogRequest
# from macroboxlib import FileExecutionMonitor


LOGGING = False

BOOT_NETWORK_SCHEDULER = False

MULTIPROCESSING_FORK = '--multiprocessing-fork'


class MainPanel(wx.Panel, RectRect, EventDistributor, PopupMenuEventCatcher):

    def __init__(self, parent):
        RectRect.__init__(self)
        wx.Panel.__init__(self, parent=parent,
                          style=wx.CLIP_CHILDREN | wx.TAB_TRAVERSAL | wx.NO_BORDER | wx.FRAME_SHAPED)
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

        self.PlayBox = PlayBox(self)
        self.ListBox = ListBox(self)
        self.ListTab = ListBoxTab(self)
        self.ListSearch = ListBoxSearch(self)
        self.StatusBox = StatusBox(self)
        # self.BorderBoxHT = BorderBoxH(self)
        # bgcolor = parent.st.PLAYBOX.PLAY_BG_COLOR
        # self.BorderBoxHT.SetBackgroundColour(bgcolor)
        self.BorderBoxHB = BorderBoxH(self, grad=True)
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
        self.PlayBox.Info.CatchEvent(event)
        self.PlayBox.ControlButton.CatchEvent(event)
        self.PlayBox.Title.CatchEvent(event)
        self.PlayBox.Spectrum.CatchEvent(event)
        self.PlayBox.VectorScope.CatchEvent(event)
        self.PlayBox.Apic.CatchEvent(event)
        self.PlayBox.VolumeSlider.CatchEvent(event)
        if self.ListBox.IsAnyListLocked() is False:
            self.ListTab.CatchEvent(event)
            # self.ListSearch.CatchEvent(event)
            # self.ListBox.CatchEvent(event) #####
            # self.ListBox.Header.CatchEvent(event)
            self.ListBox.List.CatchEvent(event)
            # self.ListBox.SliderH.CatchEvent(event)
            self.ListBox.SliderV.CatchEvent(event)
        self.StatusBox.CatchEvent(event)

    def OnSize(self, event=None):
        self.Freeze()
        self.cache.eventskip = 5
        if self.parent.IsPlayerTopShowOn():
            pbh = 193  # playbox height
        else:
            pbh = 133
        w, h = self.GetSize()
        sph = 4
        self.PlayBox.SetRect((0, 0, w, pbh + sph))
        # self.BorderBoxHT.SetRect((0, pbh, w, sph))
        self.ListBox.SetRect((0, pbh + sph, w, h - pbh + sph - (24 + 26 + 35 + 5) + 26))
        # self.ListSearch.SetRect((0, h-24-27-5-26, w, 26))
        self.ListSearch.SetRect((0, h - 24 - 27 - 5 - 26, w, 0))
        self.StatusBox.SetRect((0, h - 24 - 27 - 5, w, 27))
        self.ListTab.SetRect((0, h - 24 - 5, w, 24))
        self.BorderBoxHB.SetRect((0, h - 5, w, 5))
        self.PlayBox.OnSize()
        self.ListTab.OnSize()
        # self.ListSearch.OnSize()
        self.ListBox.OnSize()
        self.StatusBox.OnSize()
        # self.BorderBoxHT.OnSize()
        self.BorderBoxHB.OnSize()
        self.Thaw()

    def SetRectPre(self):
        pass  # override this method

    def SetRectDraw(self, dc):
        pass  # override this method

    def __del__(self):
        pass


class MainFrame(wx.Frame, MacroBoxMenuBar, MacroBoxPreference, KeymapPreset):

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
        self.SetTitle(TITLE)
        self.DialogBox = None
        self.SetTransparent(255)
        self.SetMinSize((600, 450))
        self.SetMaxSize((-1, -1))
        # self.SetMaxSize((800, -1))
        # self.toolbar = self.CreateToolBar()

        self.MainPanel = MainPanel(self)
        self.MainPanel.MFEATS.AutoAnalyzer()
        MacroBoxMenuBar.__init__(self)
        self.LoadPreferences()
        self.SetMainFrameIcon()
        self.RestoreMainFrameRect()
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
        self.LoadInitFile()
        # ProductLogRequest()
        # self.FileExecutionMonitor = FileExecutionMonitor(self)

        # self.OnAbout(None)
        # self.OnPreference(None)
        # self.OnTutorial(None)
        # self.OnUpdate(None)
        # self.OnLicense(None)
        # self.OnScriptEditor(self)
        # self.OnTutorial(None)
        # self.OnCheckItemsConsistency(None)

    def LoadInitFile(self):
        initfile = self.initfile
        if initfile is None:
            return
        file_type = os.path.splitext(initfile)[1][1:]
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
        if self.IsPlayerOnlyModeOn():
            if self.IsPlayerTopShowOn():
                height = 242
            else:
                height = 186
            self.MainPanel.SetRect((0, 0, w, height))
        else:
            self.MainPanel.SetRect((0, 0, w, h))
        self.MainPanel.OnSize()
        self.Thaw()

    def OnAutoCheckUpdate(self, event):
        self.AutoCheckUpdate = AutoCheckUpdate(self)

    def OnClose(self, event):
        self.Hide()
        self.SavePreferences()
        self.MainPanel.MFEATS.__del__()
        self.Destroy()
        kill_self_process()

    def __del__(self):
        pass


class MtunesApp(wx.App):

    # def __init__(self, parent=None, initfile=None):
    def __init__(self, parent=None, initfile=None, *argv, **kwargs):
        self.initfile = initfile
        wx.App.__init__(self, parent, *argv, **kwargs)

    def FilterEvent(self, event):
        return -1

    def OnPreInit(self):
        self.MainFrame = MainFrame(initfile=self.initfile)

    def __del__(self):
        pybass.BASS_Free()


def main(initfile=None):

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
        app = MtunesApp(initfile=initfile)
        # app.SetCallFilterEvent(False)
    elif LOGGING is True:
        filename = '%s.log' % (os.path.splitext(os.path.basename(__file__))[0])
        app = MtunesApp(initfile=initfile, filename=filename, redirect=True)
        app.SetCallFilterEvent(True)
    app.MainLoop()


if __name__ == '__main__':

    initfile = None

    # if len(sys.argv) > 1:
    #     argv = win32_unicode_argv()
    #     initfile = argv[1]

    mfeats.create_mfeats_table()

    if len(sys.argv) > 1:
        # argv = win32_unicode_argv()
        initfile = sys.argv[1]

    main(initfile)
    pybass.BASS_Free()
