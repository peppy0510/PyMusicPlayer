import glob
import os
import sys

from utilities import get_user_docapp_path


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
            # syspath = sys.path
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
                        except Exception:
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
                    except Exception:
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
            except Exception:
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
