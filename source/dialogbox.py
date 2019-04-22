# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import images
import json
import socket
import threading
import urllib
# import urllib2
import webbrowser
import wx

from macroboxlib import Button
from macroboxlib import CheckBox
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
from macroboxlib import FONT_ITEM
from macroboxlib import FancyButton
from macroboxlib import FancyDialogBox
from macroboxlib import FancyDialogBoxGlobalEvent
from macroboxlib import GetPreference
from macroboxlib import MACROBOX_DOWNLOAD_URL
from macroboxlib import MUTEKLAB_WEB_URL
from macroboxlib import PRODUCT_BUILD
from macroboxlib import PRODUCT_EDITION
from macroboxlib import PRODUCT_NAME
from macroboxlib import PRODUCT_PLATFORM
from macroboxlib import PRODUCT_UPDATE_CHECK_URL
from macroboxlib import PRODUCT_VERSION
from macroboxlib import SetPreference
from macroboxlib import StaticText


class AboutPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        bgcolor = self.parent.GetBackgroundColour()
        self.SetBackgroundColour(bgcolor)

        imgsize = 53
        bmpbg = wx.Panel(self, style=wx.NO_BORDER)
        bmpbg.SetBackgroundColour((255, 255, 255))
        bmpbg.SetRect((23, 23, imgsize, imgsize))

        bmp = images.macrobox_icon53.GetBitmap()
        wx.StaticBitmap(bmpbg, -1, bmp, pos=(0, 0))

        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_BOLD)
        font.SetFaceName(FONT_ITEM)
        font.SetPixelSize((10, 18))

        x = imgsize + 23 + 10
        offset = 17
        # label = u'%s %s' % (PRODUCT_NAME, PRODUCT_EDITION)
        label = u'{}'.format(self.parent.parent.__appname__)
        text = StaticText(self, label=label)
        text.SetFont(font)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 28
        label = u'{} Version {} build {}'.format(
            self.parent.parent.__appname__,
            '.'.join(self.parent.parent.__version__.split('.')[:2]),
            self.parent.parent.__version__.split('.')[-1])
        # label = label % (
        #     PRODUCT_NAME, PRODUCT_EDITION, PRODUCT_VERSION, PRODUCT_BUILD)
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        # offset += 18
        # label = u'Copyright (c) 2013 MUTEKLAB Co., Ltd. All rights reserved.'
        # text = StaticText(self, label=label)
        # text.SetForegroundColour((255, 255, 255))
        # text.SetPosition((x, offset))

        offset += 20
        # label = u'Powered by wxPython, scipy, numpy, un4seen BASS, LoudMax VST.'
        label = u'Powered by wxPython, scipy, numpy, un4seen BASS.'
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 20
        label = u'Author: {}'.format(self.parent.parent.__author__)
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 20
        label = u'Contact: {}'.format(self.parent.parent.__email__)
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        # Portions of this product are provided under license by NumPy.
        # Copyright (C) 2005 NumPy.
        # Portions of this product are provided under license by SciPy.
        # Copyright (C) 2003-2013 SciPy.
        # Portions of this product are provided under license by Enthought, Inc.
        # Copyright (C) 2001, 2002 Enthought, Inc.
        # Special thanks to univista, ohrecords, platform advisory group,
        # korean institute of startup enterpreneurship department,
        # venture square, coolidge corner investment. dooho patent,
        # Robin Dunn, Harri Pasanen, Travis Oliphant

        x, y, w, h = text.GetRect()
        width, height = self.parent.GetClientSize()
        self.SetClientSize((width, y + h + 1))

    def OnSize(self, event):
        width, height = self.GetClientSize()

    def OnClose(self, event):
        self.Destroy()


class AboutBox(FancyDialogBox, wx.Timer, FancyDialogBoxGlobalEvent):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        style = wx.FRAME_SHAPED | wx.NO_BORDER
        FancyDialogBox.__init__(self, parent, style=style)
        FancyDialogBoxGlobalEvent.__init__(self)
        self.SetClientSize((420, 185))
        self.parent = parent
        self.SetTitle('About')
        self.SetTransparent(220)
        self.SetBackgroundColour((0, 0, 0))
        self.AboutPanel = AboutPanel(self)
        # self.VisitButton = FancyButton(self, label='MUTEKLAB')
        # self.VisitButton.Bind(wx.EVT_BUTTON, self.OnVisit)
        self.CloseButton = FancyButton(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.OnSize(None)
        # self.OnSize(None)
        self.interval = 50
        # self.Start(self.interval)

    def Notify(self):
        if self.stop_globalevent:
            return
        self.HandleGlobalEvent()

    def OnSize(self, event):
        if 'CloseButton' not in dir(self):
            return
        # if 'VisitButton' not in dir(self):
        #     return
        width, height = self.GetClientSize()
        height -= self.CloseButton.GetSize().height + 20 + 3
        # self.VisitButton.SetSize((75, 26))
        self.CloseButton.SetSize((75, 26))
        # self.VisitButton.SetPosition((width - 95 - 80 - 3, height))
        self.CloseButton.SetPosition((width - 95 - 3, height))

    def OnVisit(self, event):
        webbrowser.open(MUTEKLAB_WEB_URL)

    def OnClose(self, event):
        self.stop_globalevent = True
        self.Destroy()


class CheckItemsConsistencyThread(threading.Thread):

    def __init__(self, ListBox):
        threading.Thread.__init__(self)
        self.ListBox = ListBox
        self.start()

    def run(self):
        self.ListBox.CheckItemsConsistencyAll()

    def __del__(self):
        pass


class CheckFilesConsistencyPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        width, height = self.parent.GetClientSize()
        self.SetRect((0, 0, width, 100))
        width, height = self.GetSize()
        self.text_messages = list()
        label = 'This task will check broken links '
        label += 'between your music files\nand MFEATS database. '
        label += 'Totoal %d tracks are in the playlist. '
        label += 'May take some time to check all files consistency.'
        label += '\nWould you proceed this task?'
        label = label % (self.parent.items_number)
        width, height = self.GetClientSize()
        text = StaticText(self, label=label, style=wx.ALIGN_CENTER)
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((7, 14))
        font.SetFaceName(FONT_ITEM)
        text.SetFont(font)
        text.SetPosition((20, 20))
        text.SetInitialSize((width - 40, height))

    def OnClose(self, event):
        self.Destroy()


class CheckFilesConsistencyProgressPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        width, height = self.parent.GetClientSize()
        self.SetRect((0, 0, width, 65))
        width, height = self.GetClientSize()
        self.TextMessage = StaticText(self, id=-1, label='', pos=(20, 20))
        self.ProgressBar = wx.Gauge(self, range=self.parent.items_number)
        self.ProgressBar.SetRect((20, 50, width - 40, 10))

    def OnClose(self, event):
        self.Destroy()


class CheckItemsConsistencyConfirmBoxTimer(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent

    def Notify(self):
        self.parent.Notify()


class CheckItemsConsistencyConfirmBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(400, 190))
        self.parent = parent
        self.ListBox = self.parent.MainPanel.ListBox
        self.SetTitle('Check Files Consistency')

        self.stop = False
        self.count = 0
        self.interval = 20

        self.items_number = self.ListBox.GetTotalItemsNumber()
        self.ConfirmPanel = CheckFilesConsistencyPanel(self)

        width, height = self.GetClientSize()
        self.ApplyButton = Button(self, label='Start')
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        y = height - self.CloseButton.GetSize().height - 20
        self.ApplyButton.SetPosition((width - 95 - 80, y))
        self.CloseButton.SetPosition((width - 95, y))

    def Notify(self):
        if self.stop:
            return
        if hasattr(self.ListBox, 'consistency_check_counter') is False:
            return
        self.count = self.ListBox.consistency_check_counter
        self.error_counter = self.ListBox.consistency_check_error_counter

        if self.error_counter != 0 and self.ListBox.consistency_check_counter == self.items_number:
            self.RemoveButton = Button(self, label='Remove broken tracks')
            _, y, _, height = self.ApplyButton.GetRect()
            self.RemoveButton.Bind(wx.EVT_BUTTON, self.OnRemove)
            self.RemoveButton.SetRect((20, y, 150, height))

        if self.ListBox.consistency_check_counter >= self.items_number:
            self.ListBox.consistency_check_counter = 0
            self.CloseButton.SetLabelText('Done')
            self.stop = True

        self.ProgressPanel.ProgressBar.SetValue(self.count)
        label = 'Checking %d/%d files. (found %d broken links)'\
                % (self.count, self.items_number, self.error_counter)
        self.ProgressPanel.TextMessage.SetLabelText(label)
        self.ProgressPanel.Refresh()

    def OnRemove(self, event):
        self.ListBox.RemoveItemsByPath(self.ListBox.consistency_check_error_items)
        self.RemoveButton.Disable()
        self.RemoveButton.SetLabelText('Removed broken tracks')

    def OnApply(self, event):
        self.ApplyButton.Disable()
        for v in self.ConfirmPanel.text_messages:
            v.Destroy()
        self.ConfirmPanel.Destroy()
        width, height = self.GetSize()
        self.SetSize((width, 155))
        self.ProgressPanel = CheckFilesConsistencyProgressPanel(self)

        width, height = self.GetClientSize()
        y = height - self.CloseButton.GetSize().height - 20
        self.ApplyButton.SetPosition((width - 95 - 80, y))
        self.CloseButton.SetPosition((width - 95, y))
        self.CloseButton.SetLabelText('Cancel')

        self.Timer = CheckItemsConsistencyConfirmBoxTimer(self)
        self.Timer.Start(self.interval)
        self.Thread = CheckItemsConsistencyThread(self.ListBox)

    def OnClose(self, event):
        self.stop = True
        if hasattr(self.ListBox, 'consistency_check_stop'):
            self.ListBox.consistency_check_stop = True
        self.Destroy()


class UpdateCheckThread(threading.Thread):

    def __init__(self, parent):
        threading.Thread.__init__(self)
        self.parent = parent
        self.result = None
        self.step = 0
        self.max_step = 6

    def run(self):
        socket.setdefaulttimeout(5)
        url = PRODUCT_UPDATE_CHECK_URL
        # url = 'http://invalid.com/'
        values = {
            'platform': PRODUCT_PLATFORM,
            'name': PRODUCT_NAME,
            'edition': PRODUCT_EDITION,
            'version': PRODUCT_VERSION,
            'build': PRODUCT_BUILD}
        try:
            data = urllib.urlencode(values)
            self.step = 1
            req = urllib2.Request(url, data)
            self.step = 2
            response = urllib2.urlopen(req)
            self.step = 3
            result = response.read()
            self.step = 4
            result = json.loads(result)
            self.step = 5
        except Exception:
            result = None
        self.result = result
        self.step = 6
        # result = {url, version, build, md5, result}

    def __del__(self):
        pass


class AutoCheckUpdate(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent
        self.Thread = UpdateCheckThread(None)
        self.stop = False
        self.interval = 50
        self.Start(self.interval)
        self.Thread.start()

    def Notify(self):
        if self.stop:
            return
        if self.Thread.step != self.Thread.max_step:
            return
        result = self.Thread.result
        if result is None:
            self.stop = True
            self.Destroy()
            return
        if result['result'] is False:
            self.stop = True
            self.Destroy()
            return
        if self.parent.DialogBox is not None:
            return
        self.stop = True
        self.parent.DialogBox = AutoUpdateBox(self.parent.MainPanel, result)
        x, y, w, h = self.parent.GetRect()
        width, height = self.parent.DialogBox.GetSize()
        self.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.DialogBox.ShowModal()
        self.parent.DialogBox = None
        self.parent.MainPanel.ListBox.reInitBuffer = True
        self.Destroy()

    def OnClose(self, event):
        self.Destroy()


class UpdateBoxCommon(DialogBox):

    def __init__(self, parent, size=(-1, -1), pos=(-1, -1)):
        DialogBox.__init__(self, parent, size=size, pos=pos)
        self.parent = parent
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.DownloadButton = Button(self, label='Download')
        self.DownloadButton.Bind(wx.EVT_BUTTON, self.OnDownload)
        self.DownloadButton.Disable()

        self.AutoCheckUpdate = CheckBox(self)
        self.AutoCheckUpdate.Bind(wx.EVT_CHECKBOX, self.OnAutoCheckUpdate)
        label = u'Auto check update on startup'
        self.AutoCheckText = StaticText(self, label=label)
        preference = GetPreference('auto_check_update')
        if preference is None or preference:
            self.AutoCheckUpdate.SetValue(1)

    def OnDownload(self, event):
        webbrowser.open(MACROBOX_DOWNLOAD_URL)

    def OnAutoCheckUpdate(self, event):
        if event.IsChecked():
            SetPreference('auto_check_update', True)
        else:
            SetPreference('auto_check_update', False)


class UpdatePanel(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY,
                          style=wx.CLIP_CHILDREN | wx.FRAME_SHAPED |
                          wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL)
        self.parent = parent
        self.SetBackgroundColour((230, 230, 230))
        width, height = self.parent.GetSize()
        self.SetRect((0, 0, width, 58))
        self.TextMessage = StaticText(self, label='', pos=(18, 20))

    def OnClose(self, event):
        self.Destroy()


class AutoUpdateBox(UpdateBoxCommon):

    def __init__(self, parent, result):
        UpdateBoxCommon.__init__(self, parent, size=(400, 130))
        self.parent = parent
        self.result = result
        self.SetTitle('Update Notify')
        width, height = self.GetClientSize()
        self.UpdatePanel = UpdatePanel(self)
        label = u'New update are available. (Version %s Build %s)'\
                % (str(self.result['version']), str(self.result['build']))
        self.UpdatePanel.TextMessage.SetLabelText(label)
        self.DownloadButton.Enable()
        self.OnSize(None)

    def OnSize(self, event):
        width, height = self.GetClientSize()
        height -= self.CloseButton.GetSize().height + 20
        self.AutoCheckUpdate.SetPosition((20, height + 5))
        self.AutoCheckText.SetPosition((20 + 25, height + 5))
        self.DownloadButton.SetPosition((width - 95 - 80, height))
        self.CloseButton.SetPosition((width - 95, height))

    def OnClose(self, event):
        self.Destroy()


class UpdateCheckProgressPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        width, height = self.GetClientSize()
        label = u'Check avaliable update.'
        self.TextMessage = StaticText(self, label=label)
        self.TextMessage.SetPosition((20, 20))
        self.ProgressBar = wx.Gauge(self, range=self.parent.Thread.max_step)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.OnSize(None)

    def OnSize(self, event):
        width, height = self.GetClientSize()
        self.ProgressBar.SetRect((20, 50, width - 40, 10))

    def OnClose(self, event):
        self.Destroy()


class UpdateBoxTimer(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent

    def Notify(self):
        self.parent.Notify()


class UpdateBox(UpdateBoxCommon):

    def __init__(self, parent):
        UpdateBoxCommon.__init__(self, parent, size=(400, 155))
        self.parent = parent
        self.SetTitle('Update Check')
        self.Thread = UpdateCheckThread(self)
        self.ProgressPanel = UpdateCheckProgressPanel(self)
        self.OnSize(None)
        self.stop = False
        self.interval = 20
        self.Timer = UpdateBoxTimer(self)
        self.Timer.Start(self.interval)
        self.Thread.start()

    def Notify(self):
        if self.stop:
            return
        self.UpdateProgress()

    def OnSize(self, event):
        self.ProgressPanel.OnSize(None)
        width, height = self.GetClientSize()
        self.ProgressPanel.SetSize((width, 60))
        height -= self.CloseButton.GetSize().height + 20
        self.AutoCheckUpdate.SetPosition((20, height + 5))
        self.AutoCheckText.SetPosition((20 + 25, height + 5))
        self.DownloadButton.SetPosition((width - 95 - 80, height))
        self.CloseButton.SetPosition((width - 95, height))

    def UpdateProgress(self):
        if hasattr(self, 'Thread') is False:
            return
        if hasattr(self.ProgressPanel, 'ProgressBar') is False:
            width, height = self.GetSize()
        label = u'Check avaliable update. (Step %d/%d)'\
                % (self.Thread.step, self.Thread.max_step)
        self.ProgressPanel.TextMessage.SetLabelText(label)
        self.ProgressPanel.ProgressBar.SetValue(self.Thread.step)
        if self.Thread.step != self.Thread.max_step:
            return
        self.stop = True
        result = self.Thread.result
        if result is None:
            label = u'Please try later. (Server connection error)'
            self.ProgressPanel.TextMessage.SetLabelText(label)
            return
        if result['result'] is False:
            label = u'No update available. (Current version is the latest)'
            self.ProgressPanel.TextMessage.SetLabelText(label)
            return
        self.DownloadButton.Enable()
        self.ProgressPanel.Destroy()
        self.UpdatePanel = UpdatePanel(self)
        width, height = self.GetSize()
        self.SetSize((width, 140))
        width, height = self.GetSize()
        self.CloseButton.SetPosition((width - 95, height - 68))
        self.DownloadButton.SetPosition((width - 95 - 80, height - 68))
        self.AutoCheckUpdate.SetPosition((20, height - 63))
        label = u'New update are available. (Version %s Build %s)'\
                % (str(result['version']), str(result['build']))
        self.UpdatePanel.TextMessage.SetLabelText(label)
        self.Refresh()

    def OnClose(self, event):
        self.stop = True
        if self.Thread.isAlive():
            self.Thread._Thread__stop()
        self.Destroy()
