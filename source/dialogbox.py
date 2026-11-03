# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import collections
import images
import library
import macroboxstyle
import mfeats
import threading
import webbrowser
import wx

from macroboxlib import Button
from macroboxlib import ProgressBar
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
from macroboxlib import DIALOG_GAP
from macroboxlib import DIALOG_PAD
from macroboxlib import FONT_ITEM
from macroboxlib import FancyButton
from macroboxlib import FancyDialogBox
from macroboxlib import FancyDialogBoxGlobalEvent
from macroboxlib import MUTEKLAB_WEB_URL
from macroboxlib import make_check
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
        label = f'{self.parent.parent.__appname__}'
        text = StaticText(self, label=label)
        text.SetFont(font)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 28
        label = f'{self.parent.parent.__appname__} Version {self.parent.parent.__version__}'
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
        label = f'Author: {self.parent.parent.__author__}'
        text = StaticText(self, label=label)
        text.SetForegroundColour((255, 255, 255))
        text.SetPosition((x, offset))

        offset += 20
        label = f'Contact: {self.parent.parent.__email__}'
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
        label = (f'Checking {int(self.count)}/{int(self.items_number)} files. (found '
                 f'{int(self.error_counter)} broken links)')
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
            # (a folder's songs looked through: not the playlists')
            if self.ListBox.innerList[listIdx].title == library.FOLDER_TITLE:
                continue
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
        lines = [f'The playlists\' {len(paths)} tracks against the analyzer '
                 f'{mfeats.MFEATS_VERSION} (its grid {mfeats.GRID_VERSION}):']
        versions = ', '.join(f'{v}: {n}' for v, n in sorted(older.items(), reverse=True))
        versions = f' ({versions})' if versions else ''
        lines.append(f'Analyzed by an older analyzer: {sum(older.values())}{versions}')
        lines.append(f'Grid older or not made: {grids}')
        lines.append(f'Not analyzed yet: {none}')
        if failed:
            lines.append(f'Not analyzable (left as they are): {failed}')
        lines.append('')
        lines.append(f'Analyze the {int(outdated)} tracks again? It may take a while.'
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


class UpdateCheckBox(DialogBox):

    '''Help > Check for Updates: the Update Check dialog as it was (its words and the bar
    under them, its button and Close, the automatic check's box), asking GitHub's latest
    release (updater, MainFrame.OnCheckUpdates) where it asked muteklab's server. taken
    away with that server on 11-02 for the status line's one line, unasked: brought back
    (the user); its words a line of what came of it and one of the versions under it, the
    version run told in every state (the user)'''

    WIDTH = 460
    LINE = 18
    # between the line of what came of it and the versions' line under it
    LINE_GAP = 4

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(self.WIDTH, 170))
        self.parent = parent
        self.release = None
        self.current = f'{parent.__appname__} {parent.__version__}'
        self.SetTitle('Check for Updates')
        content = DIALOG_PAD * 2 + self.LINE * 2 + self.LINE_GAP + DIALOG_GAP + 10
        self.SetClientSize((self.GetClientSize().width, content + self.GetFooterHeight()))
        width = self.GetClientSize().width
        self.Headline = StaticText(self, label='', pos=(DIALOG_PAD, DIALOG_PAD))
        self.Headline.SetInitialSize((width - DIALOG_PAD * 2, self.LINE))
        top = DIALOG_PAD + self.LINE + self.LINE_GAP
        self.Detail = StaticText(self, label='', pos=(DIALOG_PAD, top))
        self.Detail.SetInitialSize((width - DIALOG_PAD * 2, self.LINE))
        self.Detail.SetForegroundColour(macroboxstyle.current().UI.BAR_TEXT_DIM)
        self.ProgressBar = ProgressBar(self, range=100)
        self.ProgressBar.SetRect((DIALOG_PAD, top + self.LINE + DIALOG_GAP,
                                  width - DIALOG_PAD * 2, 10))
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.DownloadButton = Button(self, label='Update Now', primary=True, size=(100, 26))
        self.DownloadButton.Bind(wx.EVT_BUTTON, self.OnDownload)
        self.DownloadButton.Disable()
        top = self.PlaceButtons(right=(self.DownloadButton, self.CloseButton))
        self.AutoCheckUpdate, _ = make_check(self, 'Check for updates automatically',
                                             (DIALOG_PAD, top + 5), self.parent.UpdateCheck,
                                             self.parent.SetUpdateCheck)
        self.Tell('Checking for updates\u2026', f'Current version: {self.current}')
        # the bar going on while the answer is awaited (one request: no steps to count),
        # slower as it nears the end
        self.Timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.Timer)
        self.Timer.Start(20)

    def Tell(self, headline, detail):
        self.Headline.SetLabelText(headline)
        self.Detail.SetLabelText(detail)

    def OnTimer(self, event):
        value = self.ProgressBar.GetValue()
        self.ProgressBar.SetValue(value + max((90 - value) * 0.04, 0))

    def ShowResult(self, release, result):
        # the answer: none to be had, the latest already, or a newer one (its button)
        self.Timer.Stop()
        self.ProgressBar.SetValue(100)
        if result == 'error':
            self.Tell('Couldn\'t check for updates',
                      f'GitHub couldn\'t be reached. Current version: {self.current}')
        elif release is None:
            self.Tell('You\'re up to date', f'{self.current} is the latest version.')
        else:
            self.release = release
            self.Tell(f'Version {release["version"]} is available',
                      f'Current version: {self.current}')
            # a copy that can neither download nor pull opens the release's page (updater)
            if release['kind'] == 'page':
                self.DownloadButton.SetLabel('View Release')
            self.DownloadButton.Enable()
            self.DownloadButton.SetFocus()

    def OnDownload(self, event):
        # the update as the notice's Update now does it (its progress on the notice)
        release = self.release
        self.OnClose(None)
        self.parent.ShowUpdate(release)
        self.parent.OnUpdateAction('update')

    def OnClose(self, event):
        self.Timer.Stop()
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()
