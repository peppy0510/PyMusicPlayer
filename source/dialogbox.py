# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import wx
import gc
import json
import time
import images
import socket
import urllib
import threading
import webbrowser
from macroboxlib import Button
from macroboxlib import CheckBox
from macroboxlib import DialogBox
from macroboxlib import TextCtrl
from macroboxlib import StaticText
from macroboxlib import DialogPanel
from macroboxlib import FancyButton
from macroboxlib import FancyDialogBox
from macroboxlib import FancyDialogBoxGlobalEvent
from macroboxlib import GetPreference
from macroboxlib import SetPreference
from macroboxlib import FONT_ITEM
from macroboxlib import PRODUCT_NAME
from macroboxlib import PRODUCT_BUILD
from macroboxlib import PRODUCT_EDITION
from macroboxlib import PRODUCT_VERSION
from macroboxlib import MUTEKLAB_WEB_URL
from macroboxlib import PRODUCT_UPDATE_CHECK_URL
from macroboxlib import PRODUCT_PLATFORM
from macroboxlib import MACROBOX_DOWNLOAD_URL
from macroboxlib import PRODUCT_LOG_REQUEST_URL
from macroboxlib import PRODUCT_LICENSE_CHECK_URL
from macroboxlib import MACROBOX_BUY_URL
from utilities import Struct
from utilities import struct_to_dict
from utilities import get_hostname
from utilities import get_macaddress
from utilities import compress_object
from utilities import decompress_object
from license import generate_code
# from macroboxlib import *
# from scripteditor import *
# from listbox import FileOpenDialog
# from listbox import FileSaveDialog


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
        label = u'%s %s' % (PRODUCT_NAME, PRODUCT_EDITION)
        text = StaticText(self, label=label)
        text.SetFont(font)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 28
        label = u'%s %s Version %s build %s'
        label = label % (
            PRODUCT_NAME, PRODUCT_EDITION, PRODUCT_VERSION, PRODUCT_BUILD)
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        # offset += 18
        # label = u'Copyright (c) 2013 MUTEKLAB Co., Ltd. All rights reserved.'
        # text = StaticText(self, label=label)
        # text.SetForegroundColour((255, 255, 255))
        # text.SetPosition((x, offset))

        offset += 20
        label = u'Powered by wxpython, scipy, numpy, un4seen bass.'
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 20
        label = u'Author:  Taehong Kim'
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 20
        label = u'Contact:  peppy0510@hotmail.com'
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
        self.VisitButton = FancyButton(self, label='MUTEKLAB')
        self.VisitButton.Bind(wx.EVT_BUTTON, self.OnVisit)
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
        if 'VisitButton' not in dir(self):
            return
        width, height = self.GetClientSize()
        height -= self.CloseButton.GetSize().height + 20 + 3
        self.VisitButton.SetSize((75, 26))
        self.CloseButton.SetSize((75, 26))
        self.VisitButton.SetPosition((width - 95 - 80 - 3, height))
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
        self.SetRect((0, 0, width, 80))
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
        height -= self.CloseButton.GetSize().height + 20
        self.ApplyButton.SetPosition((width - 95 - 80, height))
        self.CloseButton.SetPosition((width - 95, height))

    def Notify(self):
        # print('*' * 100)
        if self.stop:
            return
        if hasattr(self.ListBox, 'consistency_check_counter') is False:
            return
        self.count = self.ListBox.consistency_check_counter
        self.error_counter = self.ListBox.consistency_check_error_counter

        if self.error_counter != 0 and self.ListBox.consistency_check_counter == self.items_number:
            self.RemoveButton = Button(self, label='Remove broken tracks')
            w, h = self.RemoveButton.GetSize()
            self.RemoveButton.SetSize((150, h))
            width, height = self.GetClientSize()
            height -= self.CloseButton.GetSize().height + 20
            self.RemoveButton.SetPosition((20, height))
            self.RemoveButton.Bind(wx.EVT_BUTTON, self.OnRemove)

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
        height -= self.CloseButton.GetSize().height + 20
        self.ApplyButton.SetPosition((width - 95 - 80, height))
        self.CloseButton.SetPosition((width - 95, height))
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
        except:
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


class ProductLogRequest(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)
        self.start()

    def run(self):
        socket.setdefaulttimeout(5)
        url = PRODUCT_LOG_REQUEST_URL
        try:
            values = {
                'macaddress': get_macaddress(),
                'hostname': get_hostname(),
                'platform': PRODUCT_PLATFORM,
                'product_name': PRODUCT_NAME,
                'product_edition': PRODUCT_EDITION,
                'product_version': PRODUCT_VERSION,
                'product_build': PRODUCT_BUILD
            }
            data = urllib.urlencode(values)
            req = urllib2.Request(url, data)
            response = urllib2.urlopen(req)
            result = response.read()
            result = json.loads(result)
        except:
            result = None

    def __del__(self):
        pass


class ClientEnvironment(Struct):

    def __init__(self):
        self.hostname = get_hostname()
        self.macaddress = get_macaddress()
        # self.ipaddress = get_external_ip()
        # self.hddserial = get_hddserial()[0]


class ProductLicenseQueryForm(ClientEnvironment):

    def __init__(self, email='', publickey=''):
        ClientEnvironment.__init__(self)
        self.name = PRODUCT_NAME
        self.edition = PRODUCT_EDITION
        self.version = PRODUCT_VERSION
        self.platform = PRODUCT_PLATFORM
        self.email = email
        self.publickey = publickey
        seed = self.email + self.publickey + self.name + self.edition + self.macaddress
        self.querykey = generate_code(seed, length=64)

    def set_querykey(self):
        seed = self.email + self.publickey + self.name + self.edition + self.macaddress
        self.querykey = generate_code(seed, length=64)

    def get_querykey(self):
        return self.querykey

    def get_responsekey(self):
        seed = self.email + self.publickey + self.name\
            + self.edition + self.macaddress + self.querykey
        return generate_code(seed, length=64)


class ProductLicenseQuery():

    def __init__(self, query_form):
        self.url = PRODUCT_LICENSE_CHECK_URL
        self.query_form = query_form
        self.step = 0
        self.max_step = 5
        self.result = None

    def get_license_query_data(self, email='', publickey=''):
        self.query_form.email = email
        self.query_form.publickey = publickey
        if hasattr(self.parent.parent, 'LicensePanel'):
            self.query_form.email = self.parent.parent\
                .LicensePanel.LicenseEmail.GetValue()
            self.query_form.publickey = self.parent.parent\
                .LicensePanel.LicenseCode.GetValue()
        self.query_form.set_querykey()
        query_data = struct_to_dict(self.query_form)
        return compress_object(query_data)

    def save_license(self):
        license = Struct(email=self.query_form.email,
                         publickey=self.query_form.publickey)
        SetPreference('license', compress_object(license))

    def load_license(self):
        license = GetPreference('license')
        if license is None:
            return None
        return decompress_object(license)

    def query_license(self, email='', publickey=''):
        license = self.get_license_query_data(
            email=email, publickey=publickey)
        data = {'license': license.encode('utf-8')}
        socket.setdefaulttimeout(5)
        try:
            data = urllib.urlencode(data)
            self.step = 1
            req = urllib2.Request(self.url, data)
            self.step = 2
            response = urllib2.urlopen(req)
            self.step = 3
            response = response.read()
            self.step = 4
            response = decompress_object(response)
            self.step = 5
        except:
            self.step = 5
            return
        # print response
        if response is None:
            self.result = 'CONNECTION_ERROR'
            return
        if 'responsekey' not in response:
            self.result = response['result']
            return
        responsekey = self.query_form.get_responsekey()
        if response['responsekey'] != responsekey:
            self.result = 'INVALID_RESPONSEKEY'
            return
        self.result = 'SUCCESS'


class LicenseOnlineCheckThread(threading.Thread, ProductLicenseQuery):

    def __init__(self, parent, query_form, license=None):
        self.parent = parent
        self.license = license
        self.query_form = query_form
        threading.Thread.__init__(self)
        ProductLicenseQuery.__init__(self, query_form)
        # ProductLicenseQueryForm()

    def run(self):
        if self.license is None:
            self.query_license()
            return
        if isinstance(self.license, str):
            self.license = decompress_object(self.license)
        self.query_license(self.license.email, self.license.publickey)

    def __del__(self):
        pass
        # self.Thread.isAlive():
        # self.Thread._Thread__stop()


class LicenseOnlineCheckPanel(DialogPanel, wx.Timer):

    def __init__(self, parent, pos=(0, 0)):
        wx.Timer.__init__(self)
        DialogPanel.__init__(self, parent, wx.ID_ANY,
                             style=wx.CLIP_CHILDREN | wx.FRAME_SHAPED |
                             wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL)
        self.parent = parent
        self.stop = None
        self.interval = 100
        x, y = pos
        width, height = self.parent.GetClientSize()
        self.SetRect((x, y, width, 60))
        self.query_form = ProductLicenseQueryForm()
        self.Thread = LicenseOnlineCheckThread(self, self.query_form)
        label = 'Check for your license.'
        self.TextMessage = StaticText(self, label=label)
        self.ProgressBar = wx.Gauge(self, range=self.Thread.max_step)
        self.OnSize(None)
        self.Start(self.interval)
        self.parent.LicenseButton.Bind(wx.EVT_BUTTON, self.OnConfirm)
        self.Thread.start()

    def OnSize(self, event):
        width, height = self.parent.GetClientSize()
        self.TextMessage.SetPosition((20, 15))
        self.ProgressBar.SetRect((20, 45, width - 40, 10))

    def Notify(self):
        if self.stop:
            return
        self.UpdateProgress()

    def OnConfirm(self, event):
        if hasattr(self, 'Thread') and self.Thread.isAlive():
            self.Thread._Thread__stop()
            self.Thread = None
        self.parent.LicenseButton.Disable()
        self.Thread = LicenseOnlineCheckThread(self, self.query_form)
        self.ProgressBar.SetValue(0)
        self.stop = False
        self.Thread.start()

    def UpdateProgress(self):
        label = 'Check for your license. (Step %d/%d)'\
                % (self.Thread.step, self.Thread.max_step)
        self.TextMessage.SetLabelText(label)
        self.ProgressBar.SetValue(self.Thread.step)
        if self.Thread.step != self.Thread.max_step:
            return
        self.stop = True
        result = self.Thread.result
        if result == 'CONNECTION_ERROR':
            label = 'Please try again. (Server connection error)'
            self.TextMessage.SetLabelText(label)
            self.parent.LicenseButton.Enable()
            return
        if result in ('INVALID_PUBLICKEY', 'INVALID_QUERYKEY'):
            label = 'Invalid license.'
            self.TextMessage.SetLabelText(label)
            self.parent.LicenseButton.Enable()
            return
        if result == 'MAX_DEVICE_REACHED':
            label = 'This license code has reached max device allowance.'
            label += ' You need to reissue the license code.'
            self.TextMessage.SetLabelText(label)
            self.parent.LicenseButton.Enable()
            return
        if result == 'SUCCESS':
            label = 'Thank you for license.'
            self.TextMessage.SetLabelText(label)
            self.Thread.save_license()
            license = self.Thread.load_license()
            self.parent.LicensePanel.SetLicensed(license)
            self.parent.CloseButton.Enable()
            return
        label = 'Please try again. (Server connection error)'
        self.TextMessage.SetLabelText(label)
        self.parent.LicenseButton.Enable()

    def OnClose(self, event):
        self.stop = True
        if hasattr(self, 'Thread') and self.Thread.isAlive():
            self.Thread._Thread__stop()
        self.Destroy()


class LicensePanel(DialogPanel):

    def __init__(self, parent, pos=(-1, -1), size=(-1, -1)):
        DialogPanel.__init__(self, parent, pos=pos, size=size)
        self.parent = parent
        width, height = self.parent.GetSize()
        width, height = self.GetSize()
        offset = 20
        text = StaticText(self, label='User email', style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 4, 70, 20))
        offset += 30
        text = StaticText(self, label='License code', style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 4, 70, 20))
        self.LicenseEmail = TextCtrl(self)
        self.LicenseCode = TextCtrl(self)

    def SetLicensed(self, license):
        if isinstance(license, str):
            license = decompress_object(license)
        self.LicenseEmail.Disable()
        self.LicenseEmail.SetValue(license.email)
        self.LicenseCode.Disable()
        self.LicenseCode.SetValue(license.publickey)
        self.parent.BuyNowButton.Disable()
        self.parent.LicenseButton.Disable()
        if hasattr(self.parent.parent, 'LicenseCheckTimer'):
            self.parent.parent.LicenseCheckTimer.license = license
        if hasattr(self.parent.parent, 'parent')\
                and hasattr(self.parent.parent.parent, 'LicenseCheckTimer'):
            self.parent.parent.parent.LicenseCheckTimer.license = license

    def OnConfirm(self, event):
        self.parent.LicenseButton.Disable()
        if hasattr(self.parent, 'LicenseOnlineCheckPanel') is False:
            width, height = self.parent.GetSize()
            w, h = self.GetSize()
            x, y = self.GetPosition()
            self.parent.LicenseOnlineCheckPanel\
                = LicenseOnlineCheckPanel(self.parent, pos=(x, y + h + 1))
            x, y = self.parent.LicenseOnlineCheckPanel.GetPosition()
            w, h = self.parent.LicenseOnlineCheckPanel.GetSize()
            self.parent.SetSize((width, height + h + 1))
            width, height = self.parent.GetClientSize()
            height -= self.parent.CloseButton.GetSize().height + 20
            self.parent.CloseButton.SetPosition((width - 95, height))
            self.parent.LicenseButton.SetPosition((width - 95 - 80, height))
            self.parent.BuyNowButton.SetPosition((width - 95 - 80 - 80, height))

    def OnSize(self, event):
        width, height = self.GetClientSize()
        offset = 20
        self.LicenseEmail.SetRect((105, offset, width - 105 - 20, 24))
        self.LicenseCode.SetRect((105, offset + 30, width - 105 - 20, 24))

    def OnClose(self, event):
        self.Destroy()


class LicenseBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(450, 168))
        self.parent = parent
        self.interval = 100
        self.SetTitle('License')
        self.LicensePanel = LicensePanel(self)
        width, height = self.GetSize()
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.LicenseButton = Button(self, label='Confirm')
        self.LicenseButton.Bind(wx.EVT_BUTTON, self.LicensePanel.OnConfirm)
        self.BuyNowButton = Button(self, label='Buy Now')
        self.BuyNowButton.Bind(wx.EVT_BUTTON, self.OnBuyNow)
        self.OnSize(None)
        license = GetPreference('license')
        if license is not None:
            self.LicensePanel.SetLicensed(license)
        self.Show(True)

    def OnSize(self, event):
        width, height = self.GetClientSize()
        self.LicensePanel.OnSize(None)
        self.LicensePanel.SetRect((0, 0, width, 80))
        height -= self.CloseButton.GetSize().height + 20
        self.BuyNowButton.SetPosition((width - 95 - 80 - 80, height))
        self.LicenseButton.SetPosition((width - 95 - 80, height))
        self.CloseButton.SetPosition((width - 95, height))

    def OnBuyNow(self, event):
        webbrowser.open(MACROBOX_BUY_URL)

    def OnClose(self, event):
        if hasattr(self, 'LicenseOnlineCheckPanel'):
            self.LicenseOnlineCheckPanel.OnClose(event)
        self.EndModal(0)
        self.Destroy()


class LicenseNotifyPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        bgcolor = self.parent.GetBackgroundColour()
        self.SetBackgroundColour(bgcolor)
        self.SetTransparent(220)
        width, height = self.parent.GetClientSize()
        self.SetRect((0, 0, width, 80))

        label = 'Unless license, you will see this message every %d minutes.'\
                % int(self.parent.check_interval / 60)
        self.Message = StaticText(self, label=label)
        self.Message.SetForegroundColour((255, 255, 255))
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_NORMAL)
        font.SetPixelSize((6, 12))
        font.SetFaceName(FONT_ITEM)
        self.Message.SetFont(font)
        self.Message.SetInitialSize((width - 40, height))
        self.Message.SetDoubleBuffered(True)

        max_range = int(1.0 * self.parent.notify_time / self.parent.interval)
        self.ProgressBar = wx.Gauge(self, range=max_range)
        self.ProgressBar.SetDoubleBuffered(True)
        self.OnSize(None)

    def OnSize(self, event):
        pad = 5
        width, height = self.GetClientSize()
        if hasattr(self, 'Message'):
            self.Message.SetPosition((20 + pad, 20))
        if hasattr(self, 'ProgressBar'):
            self.ProgressBar.SetRect((20 + pad, 50, width - 40 - pad * 2, 10))

    def OnClose(self, event):
        self.Destroy()


class LicenseNotifyBox(FancyDialogBox, wx.Timer, FancyDialogBoxGlobalEvent):

    def __init__(self, parent, notify_time=10, check_interval=600):
        wx.Timer.__init__(self)
        style = wx.CLIP_CHILDREN | wx.FRAME_SHAPED | wx.NO_BORDER |\
            wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL | wx.STAY_ON_TOP
        FancyDialogBox.__init__(self, parent, size=(460, 210), style=style)
        FancyDialogBoxGlobalEvent.__init__(self)
        self.bgcolor = (0, 0, 0)
        self.bgcolor_inverse = False
        self.SetBackgroundColour(self.bgcolor)
        self.SetTransparent(220)
        self.parent = parent
        self.SetTitle('License')
        self.count = 0
        self.stop = False
        self.interval = 50
        self.DialogBox = None
        self.notify_time = notify_time * 1000
        self.check_interval = check_interval
        self.CloseButton = FancyButton(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.CloseButton.SetDisable()
        self.LicenseButton = FancyButton(self, label='License')
        self.LicenseButton.Bind(wx.EVT_BUTTON, self.OnLicense)
        self.BuyNowButton = FancyButton(self, label='Buy Now')
        self.BuyNowButton.Bind(wx.EVT_BUTTON, self.OnBuyNow)
        self.AboutPanel = AboutPanel(self)
        self.LicenseNotifyPanel = LicenseNotifyPanel(self)
        self.OnSize(None)
        self.Start(self.interval)

    def OnSize(self, event):
        self.AboutPanel.SetPosition((0, 3))
        height = self.AboutPanel.GetSize().height + 3
        self.LicenseNotifyPanel.SetPosition((0, height))
        pad = 5
        width, height = self.GetClientSize()
        height -= self.CloseButton.GetSize().height + 20 + pad
        self.BuyNowButton.SetRect((width - 95 - 80 - 80 - pad, height, 75, 26))
        self.LicenseButton.SetRect((width - 95 - 80 - pad, height, 75, 26))
        self.CloseButton.SetRect((width - 95 - pad, height, 75, 26))

    def Notify(self):
        if self.stop_globalevent:
            return
        if self.DialogBox is None:
            self.HandleGlobalEvent()
        # if self.BGColorInverseRule():
        # 	r, g, b = self.DecColor(self.bgcolor)
        # else: r, g, b = self.IncColor(self.bgcolor)
        # self.bgcolor = (r, g, b)
        # self.SetBackgroundColour((r, g, b))
        # self.AboutPanel.SetBackgroundColour((r, g, b))
        # self.LicenseNotifyPanel.SetBackgroundColour((r, g, b))
        # self.Refresh()
        if self.stop:
            return
        self.UpdateProgress()

    def BGColorInverseRule(self):
        r, g, b = self.bgcolor
        if r > 50:
            self.bgcolor_inverse = True
        if r < 1:
            self.bgcolor_inverse = False
        return self.bgcolor_inverse

    def IncColor(self, rgb, speed=5):
        r, g, b = rgb
        return r + speed, g, b

    def DecColor(self, rgb, speed=5):
        r, g, b = rgb
        return r - speed, g, b

    def UpdateProgress(self):
        # print self.LicenseNotifyPanel.Message.GetRect(), self.LicenseNotifyPanel.ProgressBar.GetRect()
        # self.LicenseNotifyPanel.Message.SetSize((420, 150))
        # self.LicenseNotifyPanel.ProgressBar.SetValue(self.count)
        left_time = 1.0 * (self.notify_time - self.count * self.interval) / 1000
        self.count += 1
        label = 'Unless license, you will see this message every %d minutes. (Wait %0.1f seconds)'\
                % (int(self.check_interval / 60), left_time)
        self.LicenseNotifyPanel.Message.SetLabelText(label)
        if self.count * self.interval <= self.notify_time:
            return
        self.stop = True
        label = 'Unless license, you will see this message every %d minutes.'\
                % int(self.check_interval / 60)
        self.LicenseNotifyPanel.Message.SetLabelText(label)
        self.CloseButton.SetEnable()

    def OnBuyNow(self, event):
        webbrowser.open(MACROBOX_BUY_URL)

    def OnLicense(self, event):
        self.DialogBox = LicenseBox(self)
        x, y, w, h = self.GetRect()
        width, height = self.DialogBox.GetSize()
        self.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.DialogBox.ShowModal()
        self.DialogBox.Destroy()
        self.DialogBox = None

    def OnClose(self, event):
        self.stop = True
        self.stop_globalevent = True
        if hasattr(self, 'LicenseOnlineCheckPanel'):
            self.LicenseOnlineCheckPanel.OnClose(event)
        self.EndModal(0)
        self.Destroy()


class LicenseCheckTimer(wx.Timer):

    def __init__(self, parent, notify_time=10, check_interval=600):
        # def __init__(self, parent, notify_time=1, check_interval=2):
        wx.Timer.__init__(self)
        self.parent = parent
        self.notify_time = notify_time
        self.check_interval = check_interval
        self.last_check = time.time()
        self.count = 0
        self.stop = False
        self.online_checked = False
        self.init_license_noty = False
        license = GetPreference('license')
        if license is not None:
            license = decompress_object(license)
        self.license = license
        self.query_from = ProductLicenseQueryForm()
        self.interval = 1000
        self.Start(self.interval)

    def Notify(self):
        if self.stop:
            return
        self.LicenseNotyCheck()
        self.OnlineCheck()

    def OnlineCheck(self):
        if self.online_checked:
            return
        if hasattr(self, 'Thread') is False:
            self.Thread = LicenseOnlineCheckThread(
                self, self.query_from, license=self.license)
            self.Thread.start()
        if hasattr(self, 'Thread') is False:
            return
        if self.Thread.result is not None:
            self.online_checked = True
        if self.Thread.result in (None, 'CONNECTION_ERROR', 'SUCCESS'):
            return
        self.RemoveLicense()

    def RemoveLicense(self):
        SetPreference('license', None)

    def LicenseNotyCheck(self):
        if self.init_license_noty is False:
            self.init_license_noty = True
            if self.parent.DialogBox is not None:
                return
            self.last_check = time.time()
            if self.license is None:
                self.OnLicenseNotify(None)
        if time.time() <= self.last_check + self.check_interval:
            return
        if self.parent.DialogBox is not None:
            return
        self.last_check = time.time()
        if self.license is None:
            self.OnLicenseNotify(None)

    def OnLicenseNotify(self, event):
        if self.parent.DialogBox is not None:
            return
        if self.parent.MainPanel.pending_popup_event is not None:
            return
        self.parent.DialogBox = LicenseNotifyBox(
            self.parent, notify_time=self.notify_time, check_interval=self.check_interval)
        x, y, w, h = self.parent.GetRect()
        width, height = self.parent.DialogBox.GetSize()
        self.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.DialogBox.ShowModal()
        self.parent.DialogBox.Destroy()
        self.parent.DialogBox = None
        self.last_check = time.time()
        self.parent.MainPanel.ListBox.reInitBuffer = True


# import wmi, pygn, urllib
# import discogs_client as discogs
# from pyechonest import song as echonest_song
# from pyechonest import artist as echonest_artist
# from pyechonest import config as echonest_config

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
        except:
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
                # 	# uri = release.data['images'][0]['uri']
                # 	uri = release.data['images'][0]['uri150']
                # 	artwork = urllib.urlopen(uri).read()
                # 	info.images.append(artwork)
                # queue.put(info)
            except:
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
        # 	label='Download', pos=(width-95-80, height-68), size=(75, -1))
        # self.DownloadButton.Bind(wx.EVT_BUTTON, self.OnDownload)
        # self.DownloadButton.Disable()

        # self.AutoCheckUpdate = wx.CheckBox(self,\
        # 	label='  Auto check update on startup', pos=(20, height-63))
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
        # 	width, height = self.GetSize()
        # label = 'Check avaliable update. (Step %d/%d)'\
        # 	% (self.Thread.step, self.Thread.max_step)
        if len(self.Thread.info.releases) == 0:
            return

        label = self.Thread.info.releases[-1]
        self.DiscogsPanel.TextMessage.SetLabelText(label)
        # self.ProgressPanel.ProgressBar.SetValue(self.Thread.step)
        # if self.Thread.step != self.Thread.max_step: return
        # self.stop = True
        # result = self.Thread.result
        # if result is None:
        # 	label = 'Please try later. (Server connection error)'
        # 	self.ProgressPanel.TextMessage.SetLabelText(label)
        # 	return
        # if result['result'] is False:
        # 	label = 'No update available. (Current version is the latest)'
        # 	self.ProgressPanel.TextMessage.SetLabelText(label)
        # 	return
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
        # 	% (str(result['version']), str(result['build']))
        # self.UpdatePanel.TextMessage.SetLabelText(label)
        self.Refresh()

    # def OnDownload(self, event):
    # 	webbrowser.open(MACROBOX_DOWNLOAD_URL)
    #
    # def OnAutoCheckUpdate(self, event):
    # 	if event.IsChecked():
    # 		SetPreference('auto_check_update', True)
    # 	else: SetPreference('auto_check_update', False)

    def OnClose(self, event):
        self.stop = True
        if self.Thread.isAlive():
            self.Thread._Thread__stop()
        self.EndModal(0)
        self.Destroy()
