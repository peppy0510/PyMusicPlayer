# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import collections
import images
import json
import macroboxstyle
import mfeats
import socket
import threading
import urllib
import webbrowser
import wx

from macroboxlib import Button
from macroboxlib import ProgressBar
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
from macroboxlib import DIALOG_GAP
from macroboxlib import DIALOG_PAD
from macroboxlib import make_check
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
# import urllib2


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
        # opaque on the dialogs' ground, its button as theirs (a see-through black before)
        self.SetBackgroundColour(macroboxstyle.current().UI.DIALOG_BG)
        self.AboutPanel = AboutPanel(self)
        # self.VisitButton = FancyButton(self, label='MUTEKLAB')
        # self.VisitButton.Bind(wx.EVT_BUTTON, self.OnVisit)
        self.CloseButton = Button(self, label='Close', primary=True)
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
        # (worded again: a typo, and one long sentence)
        label = 'Checks the playlist\'s %d tracks for broken links:\n'
        label += 'files that were moved or deleted.\n'
        label += 'It may take a while. Start now?'
        label = label % (self.parent.items_number)
        width, height = self.GetClientSize()
        text = StaticText(self, label=label, style=wx.ALIGN_CENTER)
        font = wx.Font(0, wx.SWISS, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((7, 14))
        font.SetFaceName(FONT_ITEM)
        text.SetFont(font)
        # the dialogs' spacing: PAD in
        text.SetPosition((DIALOG_PAD, DIALOG_PAD))
        lines = text.GetBestSize().height
        text.SetInitialSize((width - DIALOG_PAD * 2, lines))
        # its words' height and PAD over and under them
        self.content_height = DIALOG_PAD * 2 + lines
        self.SetSize((width, self.content_height))

    def OnClose(self, event):
        self.Destroy()


# a progress's words, its bar under them and PAD round them
PROGRESS_HEIGHT = DIALOG_PAD * 2 + 18 + DIALOG_GAP + 10


class CheckFilesConsistencyProgressPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        width, height = self.parent.GetClientSize()
        self.SetRect((0, 0, width, PROGRESS_HEIGHT))
        width, height = self.GetClientSize()
        # the dialogs' spacing: the words PAD in, the bar GAP under them
        self.TextMessage = StaticText(self, id=-1, label='', pos=(DIALOG_PAD, DIALOG_PAD))
        self.ProgressBar = ProgressBar(self, range=self.parent.items_number)
        self.ProgressBar.SetRect((DIALOG_PAD, DIALOG_PAD + 18 + DIALOG_GAP,
                                  width - DIALOG_PAD * 2, 10))

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
        # its words (CheckFilesConsistencyPanel), the footer under them
        self.SetClientSize((self.GetClientSize().width,
                            self.ConfirmPanel.content_height + self.GetFooterHeight()))

        self.ApplyButton = Button(self, label='Start', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.PlaceButtons(right=(self.ApplyButton, self.CloseButton))

    def Notify(self):
        if self.stop:
            return
        if hasattr(self.ListBox, 'consistency_check_counter') is False:
            return
        self.count = self.ListBox.consistency_check_counter
        self.error_counter = self.ListBox.consistency_check_error_counter

        if self.error_counter != 0 and self.ListBox.consistency_check_counter == self.items_number:
            self.RemoveButton = Button(self, label='Remove broken tracks', size=(150, 26))
            self.RemoveButton.Bind(wx.EVT_BUTTON, self.OnRemove)
            self.PlaceButtons(right=(self.ApplyButton, self.CloseButton),
                              left=(self.RemoveButton,))

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
        self.SetClientSize((self.GetClientSize().width, PROGRESS_HEIGHT + self.GetFooterHeight()))
        self.ProgressPanel = CheckFilesConsistencyProgressPanel(self)
        self.PlaceButtons(right=(self.ApplyButton, self.CloseButton))
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
            req = urllib.request(url, data)
            # req = urllib2.Request(url, data)
            self.step = 2
            response = urllib.urlopen(req)
            # response = urllib2.urlopen(req)
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


class AnalyzerVersionBox(DialogBox):

    '''the playlists' songs analyzed by an older analyzer (or their grid by an older one,
    or not made, or not analyzed at all) counted, and analyzed again when asked (the auto
    analyzer did it unasked, when it was on; off, they stayed as they were)'''

    WIDTH = 440

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(self.WIDTH, 200))
        self.parent = parent
        self.ListBox = self.parent.MainPanel.ListBox
        self.SetTitle('Check Analyzer Versions')
        self.queued = 0
        label, self.outdated = self.Count()
        width = self.GetClientSize().width
        self.Message = StaticText(self, label=label, pos=(DIALOG_PAD, DIALOG_PAD))
        self.Message.SetInitialSize((width - DIALOG_PAD * 2, self.Message.GetBestSize().height))
        self.SetClientSize((width, DIALOG_PAD * 2 + self.Message.GetSize().height
                            + self.GetFooterHeight()))
        self.ApplyButton = Button(self, label='Analyze Again', primary=True, size=(110, 26))
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.ApplyButton.Enable(self.outdated > 0)
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.PlaceButtons(right=(self.ApplyButton, self.CloseButton))

    def Count(self):
        # (the words told, the songs to analyze again): each song once, the stations left out
        state = mfeats.get_analysis_versions()
        paths = dict()
        for listIdx in range(len(self.ListBox.innerList)):
            pathIdx = self.ListBox.GetColumnKeyToIdx('path', listIdx)
            mdxIdx = self.ListBox.GetColumnKeyToIdx('mdx', listIdx)
            for item in self.ListBox.innerList[listIdx].items:
                if not audio.is_stream_path(item[pathIdx]):
                    paths[item[pathIdx]] = item[mdxIdx]
        older, grids, none, failed = collections.Counter(), 0, 0, 0
        for mdx in paths.values():
            row = state.get(mdx)
            if row is None:
                none += 1
            elif row[0] != mfeats.MFEATS_VERSION:
                older[row[0] or '?'] += 1
            elif row[1]:
                failed += 1
            elif row[2] != mfeats.GRID_VERSION:
                grids += 1
        outdated = sum(older.values()) + grids + none
        lines = ['The playlists\' %d tracks against the analyzer %s (its grid %s):'
                 % (len(paths), mfeats.MFEATS_VERSION, mfeats.GRID_VERSION)]
        versions = ', '.join('%s: %d' % (v, n) for v, n in sorted(older.items(), reverse=True))
        lines.append('Analyzed by an older analyzer: %d%s'
                     % (sum(older.values()), ' (%s)' % (versions) if versions else ''))
        lines.append('Grid older or not made: %d' % (grids))
        lines.append('Not analyzed yet: %d' % (none))
        if failed:
            lines.append('Not analyzable (left as they are): %d' % (failed))
        lines.append('')
        lines.append('Analyze the %d tracks again? It may take a while.' % (outdated)
                     if outdated else 'All of them are analyzed by this version.')
        return '\n'.join(lines), outdated

    def OnApply(self, event):
        # marked to be analyzed and queued (as the auto analyzer does: its progress in the
        # list's status)
        self.parent.MainPanel.MFEATS.QueueOutdated(mfeats.get_done_mdx(), asked=True)
        self.ApplyButton.Disable()
        self.ApplyButton.SetLabel('Queued')
        self.ListBox.reInitBuffer = True

    def OnClose(self, event):
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class UpdateBoxCommon(DialogBox):

    def __init__(self, parent, size=(-1, -1), pos=(-1, -1), content=None):
        # content: its words' (and bar's) height, PAD round them (a progress's at most)
        DialogBox.__init__(self, parent, size=size, pos=pos)
        self.parent = parent
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.DownloadButton = Button(self, label='Download', primary=True)
        self.DownloadButton.Bind(wx.EVT_BUTTON, self.OnDownload)
        self.DownloadButton.Disable()

        # the words (and a progress's bar) PAD in, the footer under them: the check box at
        # its left, the buttons at its right (the dialogs' spacing)
        self.SetClientSize((self.GetClientSize().width,
                            (content or PROGRESS_HEIGHT) + self.GetFooterHeight()))
        top = self.PlaceButtons(right=(self.DownloadButton, self.CloseButton))
        preference = GetPreference('auto_check_update')
        self.AutoCheckUpdate, _ = make_check(self, u'Auto check update on startup',
                                             (DIALOG_PAD, top + 5), preference is not False,
                                             self.OnAutoCheckUpdate)

    def OnDownload(self, event):
        webbrowser.open(MACROBOX_DOWNLOAD_URL)

    def OnAutoCheckUpdate(self, value):
        SetPreference('auto_check_update', bool(value))


class UpdatePanel(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, wx.ID_ANY,
                          style=wx.CLIP_CHILDREN | wx.FRAME_SHAPED |
                          wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL)
        self.parent = parent
        self.SetBackgroundColour(macroboxstyle.current().UI.DIALOG_BG)
        width, height = self.parent.GetSize()
        self.SetRect((0, 0, width, 58))
        self.TextMessage = StaticText(self, label='', pos=(DIALOG_PAD, DIALOG_PAD))

    def OnClose(self, event):
        self.Destroy()


class AutoUpdateBox(UpdateBoxCommon):

    def __init__(self, parent, result):
        UpdateBoxCommon.__init__(self, parent, size=(400, 130), content=DIALOG_PAD * 2 + 18)
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
        self.PlaceButtons(right=(self.DownloadButton, self.CloseButton))

    def OnClose(self, event):
        self.Destroy()


class UpdateCheckProgressPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        width, height = self.GetClientSize()
        label = u'Check avaliable update.'
        self.TextMessage = StaticText(self, label=label)
        self.TextMessage.SetPosition((DIALOG_PAD, DIALOG_PAD))
        self.ProgressBar = ProgressBar(self, range=self.parent.Thread.max_step)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.OnSize(None)

    def OnSize(self, event):
        width, height = self.GetClientSize()
        self.ProgressBar.SetRect((DIALOG_PAD, DIALOG_PAD + 18 + DIALOG_GAP,
                                  width - DIALOG_PAD * 2, 10))

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
        self.ProgressPanel.SetSize((width, PROGRESS_HEIGHT))
        self.PlaceButtons(right=(self.DownloadButton, self.CloseButton))

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
        if self.Thread.is_alive():
            # self.Thread._Thread__stop()
            self.Thread._stop()
        self.Destroy()
