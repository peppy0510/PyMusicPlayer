# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


from macroboxlib import *
from listbox import FileOpenDialog
from listbox import FileSaveDialog
import wx.stc
import keyword
import images


class AddNewScriptBox(UserInputDialogBox):

    def __init__(self, parent, script=None):
        UserInputDialogBox.__init__(self, parent)
        self.parent = parent
        self.script = script
        self.SetTitle('New Script')
        self.SetSize((200, 105))
        width, height = self.GetClientSize()
        x, y, w, h = self.CloseButton.GetRect()
        self.Message = StaticText(self,
                                  label='Already exist.', style=wx.ALIGN_CENTER)
        self.Message.SetRect((0, 15, width, 20))
        self.Message.Hide()
        self.OkButton = Button(self, label='OK')
        self.OkButton.Hide()
        self.OkButton.SetRect(((width - w) / 2, y, w, h))
        self.OkButton.Bind(wx.EVT_BUTTON, self.OnOkButton)
        self.ApplyButton.SetLabelText('Create')

    def OnOkButton(self, event):
        self.UserInput.Show()
        self.ApplyButton.Show()
        self.CloseButton.Show()
        self.Message.Hide()
        self.OkButton.Hide()

    def OnApply(self, event):
        selected = self.UserInput.GetValue()
        if len(selected) == 0:
            return
        scripts = glob.glob(os.path.join(self.parent.scriptpath, u'*.py'))
        scripts = [v.lower() for v in scripts]
        path = self.parent.GetSelectedScriptPath(selected)
        if path.lower() in scripts:
            self.UserInput.Hide()
            self.ApplyButton.Hide()
            self.CloseButton.Hide()
            self.Message.Show()
            self.OkButton.Show()
            return
        if self.script == None:
            self.script = self.GetTemplateCode()
        self.parent.SaveScriptFile(path, self.script)
        self.parent.SetScriptSelector(selected)
        self.OnClose(None)

    def GetTemplateCode(self):
        template = u"""
			        # MACROBOX Script
					# CUSTOMFIELD, COUNT
					# FILENAME, FILETYPE
					# ALBUM, ARTIST, TITLE, GENRE, KEY, TEMPO
					"""
        return template


class SetDefaultScript():

    def __init__(self, parent):
        self.parent = parent
        scripts = glob.glob(os.path.join(self.parent.scriptpath, u'*.py'))
        scripts = [v.lower() for v in scripts]
        # path = self.parent.GetSelectedScriptPath(selected)
        defaults = ['id3tag_to_filename']
        for name in defaults:
            if name in scripts:
                continue
            path = self.parent.GetSelectedScriptPath(name)
            exec('script = self.%s()' % (name))
            self.parent.SaveScriptFile(path, script)

    def id3tag_to_filename(self):
        template = u"""# MACROBOX Script
					ARTIST = ARTIST.strip(' ')
					TITLE = TITLE.strip(' ')
					FILENAME = ' - '.join([ARTIST, TITLE])
					FILETYPE = FILETYPE.lower()
					"""
        return template


class DeleteScriptConfirmBox(ConfirmDialogBox):

    def __init__(self, parent, script=None):
        ConfirmDialogBox.__init__(self, parent)
        self.parent = parent
        self.script = script
        self.SetTitle('Delete Confirm')
        self.SetSize((200, 105))
        label = 'Do you really want to delete ?'
        self.Message.SetLabelText(label)
        self.ApplyButton.SetLabelText('Delete')

    def OnApply(self, event):
        self.OnClose(None)
        self.parent.trigger_script_delete = True

    def OnClose(self, event):
        self.parent.trigger_script_delete = False
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class SaveScriptConfirmBox(ConfirmDialogBox):

    def __init__(self, parent, script=None):
        ConfirmDialogBox.__init__(self, parent)
        self.parent = parent
        self.script = script
        self.SetTitle('Save Confirm')
        self.SetSize((200, 105))
        label = 'Script has been modified.'
        self.Message.SetLabelText(label)
        self.ApplyButton.SetLabelText('Save')
        self.CloseButton.SetLabelText("Don't Save")

    def OnApply(self, event):
        self.OnClose(None)
        self.parent.trigger_script_save = True

    def OnClose(self, event):
        self.parent.trigger_script_save = False
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


# class ScriptButton(FancyButton):
#
# 	def __init__(self, parent, label=''):
# 		FancyButton.__init__(self, parent, label=label)
# 		self.parent = parent
#
# 		enabled = Struct(bg=(220,220,220), fg=(30,30,30), pen=(160,160,160))
# 		disabled = Struct(bg=(240,240,240), fg=(160,160,160), pen=(215,215,215))
# 		mouseover = Struct(bg=(230,230,255), fg=(30,30,30), pen=(160,160,160))
# 		colormap = Struct(enabled=enabled, disabled=disabled, mouseover=mouseover)
# 		self.SetColorMap(colormap)
# 		self.SetFontPixelSize((5,10))

class ScriptButton(Button):

    def __init__(self, parent, label=''):
        Button.__init__(self, parent, label=label)
        self.parent = parent
        self.SetFontPixelSize((5, 10))


class ScriptPreviewButton(ScriptButton):

    def __init__(self, parent):
        ScriptButton.__init__(self, parent)
        self.parent = parent

    def SetDisable(self):
        # self.bgcolor = self.colormap.disabled.bg
        # self.fgcolor = self.colormap.disabled.fg
        # self.pencolor = self.colormap.disabled.pen
        self.parent.parent.EditorPanel.Hide()
        self.parent.parent.PreviewPanel.Show()
        self.parent.parent.PreviewToolPanel.Show()
        self.parent.parent.PreviewPanel.TextCtrl.SetFocus()
        self.label = 'Editor'
        self.SetLabelText(self.label)
        # self.DirectDraw()

    def SetEnable(self):
        # self.bgcolor = self.colormap.enabled.bg
        # self.fgcolor = self.colormap.enabled.fg
        # self.pencolor = self.colormap.enabled.pen
        self.parent.parent.PreviewPanel.Hide()
        self.parent.parent.PreviewToolPanel.Hide()
        self.parent.parent.EditorPanel.Show()
        self.parent.parent.EditorPanel.TextCtrl.SetFocus()
        self.label = 'Preview'
        self.SetLabelText(self.label)
        # self.DirectDraw()


class ScriptComboBox(ComboBox):

    def __init__(self, parent, value='', choices=[], style=wx.CB_READONLY):
        ComboBox.__init__(self, parent, value=value, choices=choices, style=style)
        self.parent = parent
        self.SetFontPixelSize((5, 10))


class ScriptEditorBox(DialogBox, ScriptControl):

    def __init__(self, parent):
        self.SetPlayBox(parent.MainPanel.PlayBox)
        self.SetListBox(parent.MainPanel.ListBox)
        ScriptControl.__init__(self)
        style = wx.CLIP_CHILDREN | wx.RESIZE_BORDER | wx.BORDER_DEFAULT |\
            wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL | wx.STAY_ON_TOP |\
            wx.CAPTION | wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.SYSTEM_MENU | wx.CLOSE_BOX
        DialogBox.__init__(self, parent, style=style)
        self.parent = parent
        self.onPreview = False
        self.SetTitle('Script Editor')
        self.SetMinSize((600, 300))

        self.EditorPanel = ScriptEditorPanel(self)
        self.PreviewPanel = ScriptPreviewPanel(self)
        self.ButtonPanel = DialogPanel(self)
        self.PreviewToolPanel = DialogPanel(self)
        st = self.parent.st.EDITBOX
        self.ButtonPanel.SetBackgroundColour(st.TOOLBAR_BG_COLOR)
        self.ButtonPanel.SetDoubleBuffered(True)
        self.PreviewToolPanel.SetBackgroundColour(st.TOOLBAR_BG_COLOR)
        self.PreviewToolPanel.SetDoubleBuffered(True)
        self.PreviewToolPanel.Hide()
        SetDefaultScript(self)

        self.ScriptSelector = ScriptComboBox(
            self.ButtonPanel, value='', choices=[''])
        self.ScriptSelector.Bind(wx.EVT_COMBOBOX, self.OnScriptSelected)

        choices = ['All Tracks', 'Current Tracklist', 'Selected Tracks']
        value = GetPreference('script_process_scope')
        if value == None:
            value = choices[1]
        self.script_process_scope = value
        self.ScopeSelector = ScriptComboBox(
            self.ButtonPanel, value=value, choices=choices)
        self.ScopeSelector.Bind(wx.EVT_COMBOBOX, self.OnScopeSelected)

        self.DeleteButton = ScriptButton(self.ButtonPanel, label='Delete')
        self.NewButton = ScriptButton(self.ButtonPanel, label='New')
        self.SaveButton = ScriptButton(self.ButtonPanel, label='Save')
        self.SaveButton.SetEnable()
        self.PreviewButton = ScriptPreviewButton(self.ButtonPanel)
        self.ProcessButton = ScriptButton(self.ButtonPanel, label='Process')
        self.CloseButton = ScriptButton(self.ButtonPanel, label='Close')

        self.DeleteButton.Bind(wx.EVT_BUTTON, self.OnDelete)
        self.NewButton.Bind(wx.EVT_BUTTON, self.OnNew)
        self.SaveButton.Bind(wx.EVT_BUTTON, self.OnSave)
        self.PreviewButton.Bind(wx.EVT_BUTTON, self.OnPreviewToggle)
        self.ProcessButton.Bind(wx.EVT_BUTTON, self.OnProcess)
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)

        choices = self.GetScriptVarsChoices()
        value = GetPreference('script_preview_field')
        if value == None:
            value = 'FILENAME'
        self.PreviewField = ScriptComboBox(
            self.PreviewToolPanel, value=value, choices=choices)
        self.PreviewField.Bind(wx.EVT_COMBOBOX, self.OnPreviewFieldSelected)
        self.EditorPanel.TextCtrl.SetSaveButton(self.SaveButton)

        selected = GetPreference('script_editor_selected_script')
        self.SetScriptSelector(selected)
        self.script_selector_cache = selected
        self.SaveButton.SetDisable()
        self.PreviewButton.SetEnable()
        self.ProcessButton.SetDisable()

        self.Bind(wx.EVT_CLOSE, self.OnClose)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        size = GetPreference('script_editor_size')
        if size == None:
            size = (650, 380)
        self.SetSize(size)
        self.OnSize(None)

    def OnPreviewFieldSelected(self, event):
        choices = self.GetScriptVarsChoices()
        field = choices[self.PreviewField.GetSelection()]
        self.PreviewPanel.TextCtrl.SetReadOnly(False)
        self.PreviewPanel.TextCtrl.ClearAll()
        for v in self.preview_result:
            self.PreviewPanel.TextCtrl.SetReadOnly(False)
            exec('preview = v[1].%s' % (field))
            self.PreviewPanel.TextCtrl.AppendText(preview)
            self.PreviewPanel.TextCtrl.DocumentEnd()
            self.PreviewPanel.TextCtrl.NewLine()
            self.PreviewPanel.TextCtrl.EmptyUndoBuffer()
            self.PreviewPanel.TextCtrl.SetReadOnly(True)

    def LoadScriptFile(self, path):
        if os.path.split(path)[-1].lower() == '.py':
            return
        self.EditorPanel.TextCtrl.ClearAll()
        self.EditorPanel.TextCtrl.LoadFile(path, fileType=wx.TEXT_TYPE_ANY)
        self.EditorPanel.TextCtrl.InitMaxLineWidthCache()
        self.EditorPanel.TextCtrl.SetSelection(0, 0)
        self.EditorPanel.TextCtrl.SetSavePoint()

    def SaveScriptFile(self, path, script=None):
        if script == None:
            script = self.EditorPanel.TextCtrl.GetValue()
        if os.path.split(path)[-1].lower() == '.py':
            self.OnNew(None, script=script)
            return
        import codecs
        self.EditorPanel.TextCtrl.SaveFile(path, fileType=wx.TEXT_TYPE_ANY)
        file = codecs.open(path, 'w', 'utf-8')
        file.write(script)
        file.close()

    def SetScriptSelected(self, selected):
        if selected == None:
            return
        path = self.GetSelectedScriptPath(selected)
        self.LoadScriptFile(path)
        self.EditorPanel.OnSize(None)
        self.script_selector_cache = selected

    def SetScriptSelector(self, selected=None):
        choices = self.GetScriptChoices()
        self.ScriptSelector.Clear()
        self.EditorPanel.TextCtrl.ClearAll()
        for v in choices:
            self.ScriptSelector.Append(v)
        if selected == None:
            self.ScriptSelector.SetValue('')
        else:
            self.ScriptSelector.SetValue(selected)
        if selected == None:
            return
        path = self.GetSelectedScriptPath(selected)
        self.LoadScriptFile(path)
        self.EditorPanel.OnSize(None)
        self.script_selector_cache = selected
        self.EditorPanel.TextCtrl.SetSavePoint()

    def OnScriptSelected(self, event):
        if self.EditorPanel.TextCtrl.IsModified():
            selected = self.ScriptSelector.GetStringSelection()
            self.ScriptSelector.SetValue(self.script_selector_cache)
            self.OnSaveConfirm(None)
            if self.trigger_script_save:
                self.OnSave(None)
            self.ScriptSelector.SetValue(selected)
        selected = event.GetString()
        if len(selected) != 0:
            self.SetScriptSelected(event.GetString())
        self.OnPreviewExit(None)
        self.SaveButton.SetDisable()
        self.PreviewButton.SetEnable()
        self.ProcessButton.SetDisable()
        self.PreviewPanel.TextCtrl.SetValue(u'')
        self.EditorPanel.TextCtrl.SetSavePoint()

    def OnSaveConfirm(self, event):
        self.parent.DialogBox = SaveScriptConfirmBox(self)
        x, y, w, h = self.GetRect()
        width, height = self.parent.DialogBox.GetSize()
        self.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.DialogBox.ShowModal()
        self.parent.DialogBox.Destroy()
        self.parent.DialogBox = None

    def OnNew(self, event, script=None):
        self.parent.DialogBox = AddNewScriptBox(self, script=script)
        x, y, w, h = self.GetRect()
        width, height = self.parent.DialogBox.GetSize()
        self.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.DialogBox.ShowModal()
        self.parent.DialogBox.Destroy()
        self.parent.DialogBox = None

    def OnSave(self, event):
        if os.path.isdir(self.GetScriptPath()) == False:
            os.mkdir(self.GetScriptPath())
        path = self.GetSelectedScriptPath()
        self.SaveScriptFile(path)
        self.SaveButton.SetDisable()
        self.PreviewButton.SetEnable()
        # self.ProcessButton.SetDisable()

    def OnDelete(self, event):
        items = self.ScriptSelector.GetItems()
        if len(items) == 0:
            return
        if len(items) == 1 and items[0] == u'':
            return
        self.parent.DialogBox = DeleteScriptConfirmBox(self)
        x, y, w, h = self.GetRect()
        width, height = self.parent.DialogBox.GetSize()
        self.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.DialogBox.ShowModal()
        self.parent.DialogBox.Destroy()
        self.parent.DialogBox = None

        if self.trigger_script_delete == False:
            return
        path_py = self.GetSelectedScriptPath()
        path_pyc = u'.'.join((os.path.splitext(path_py)[0], u'pyc'))
        path_pyo = u'.'.join((os.path.splitext(path_py)[0], u'pyo'))
        try:
            if os.path.isfile(path_pyo):
                os.remove(path_pyo)
            if os.path.isfile(path_pyc):
                os.remove(path_pyc)
            if os.path.isfile(path_py):
                os.remove(path_py)
            self.SetScriptSelector()
            items = self.ScriptSelector.GetItems()
            if len(items) > 0:
                self.SetScriptSelector(items[0])
            else:
                self.SetScriptSelector()
        except:
            pass

    def UpdatePreview(self):
        self.parent.DialogBox = ScriptPreviewProgressBox(self)
        x, y, w, h = self.GetRect()
        width, height = self.parent.DialogBox.GetSize()
        self.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.DialogBox.StartRendering()
        self.parent.DialogBox.ShowModal()
        self.parent.DialogBox.Destroy()
        self.parent.DialogBox = None

    def OnProcess(self, event):
        self.ProcessButton.SetDisable()
        self.parent.DialogBox = ScriptProcessProgressBox(self)
        x, y, w, h = self.GetRect()
        width, height = self.parent.DialogBox.GetSize()
        self.parent.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.parent.DialogBox.StartRendering()
        self.parent.DialogBox.ShowModal()
        self.parent.DialogBox.Destroy()
        self.parent.DialogBox = None

    def OnPreviewToggle(self, event):
        trigger = True
        # if event != None:
        # 	event.Skip()
        # 	if hasattr(event, 'CmdDown'):
        # 		trigger = event.CmdDown() and event.GetRawKeyFlags() == 3145729 # B
        if trigger == False:
            return
        if self.PreviewPanel.IsShown():
            self.OnPreviewExit(None)
        else:
            self.OnPreviewEnter(None)

    def OnPreviewEnter(self, event):
        if event != None:
            event.Skip()
        if self.PreviewPanel.IsShown():
            return
        self.PreviewButton.SetDisable()
        self.DeleteButton.SetDisable()
        self.NewButton.SetDisable()
        self.ScriptSelector.Disable()
        self.ScopeSelector.Disable()
        self.PreviewToolPanel.Show()
        self.UpdatePreview()
        self.MakeModal(True)
        self.OnSize(None)

    def OnPreviewExit(self, event):
        if event != None:
            event.Skip()
        if self.PreviewPanel.IsShown() == False:
            return
        self.PreviewButton.SetEnable()
        self.ProcessButton.SetDisable()
        self.DeleteButton.SetEnable()
        self.NewButton.SetEnable()
        self.ScriptSelector.Enable()
        self.ScopeSelector.Enable()
        self.PreviewToolPanel.Hide()
        self.PreviewField.Enable()
        self.MakeModal(False)
        self.OnSize(None)

    def OnScopeSelected(self, event):
        pass

    def OnSize(self, event):
        self.Freeze()
        margin = 2
        bsp = 25 * 2
        sp = 2
        width, height = self.GetClientSize()

        x, y, w, h = self.ButtonPanel.GetRect()
        tp = 5
        top = 3
        bottom = 2
        self.EditorPanel.SetRect((0, 0, width, height - h))
        self.PreviewPanel.SetRect((0, 0, width, height - h * 2 + tp))
        self.PreviewToolPanel.SetRect((0, height - h * 2 + tp, width, h - tp))
        w, h = (60, 22)
        self.ButtonPanel.SetRect((0, height - h - margin * 2 - top - bottom, width, h + margin * 2 + top + bottom))

        self.DeleteButton.SetRect((margin, margin + top, 60, h))
        self.NewButton.SetRect((margin + (w + sp), margin + top, 60, h))
        ssw = width - 650 + 140 + 19
        if ssw > 200:
            ssw = 200
        self.ScriptSelector.SetRect((margin + (w + sp) * 2 + 1, margin + 1 + top, ssw - 2, h - 2))
        self.SaveButton.SetRect((margin + (w + sp) * 2 + ssw + sp, margin + top, 60, h))
        self.ScopeSelector.SetRect((width - (w + sp) * 3 + sp - margin - 115 + 1, margin + 1 + top, 115 - 2 - 2, h - 2))
        self.PreviewButton.SetRect((width - (w + sp) * 3 + sp - margin, margin + top, 60, h))
        self.ProcessButton.SetRect((width - (w + sp) * 2 + sp - margin, margin + top, 60, h))
        self.CloseButton.SetRect((width - (w + sp) * 1 + sp - margin, margin + top, 60, h))

        offset = -115 * 1 + 2
        self.PreviewField.SetRect((width - (w + sp) * 3 - 3 + margin + offset, margin + 1 + top, 115 - 2 - 2, h - 2))

        if self.EditorPanel.IsShown():
            self.EditorPanel.TextCtrl.SetUpEditor()
        elif self.PreviewPanel.IsShown():
            self.PreviewPanel.TextCtrl.SetUpPreview()
        self.Thaw()

    def OnClose(self, event):
        selected = self.ScriptSelector.GetValue()
        if selected == '':
            selected = None
        SetPreference('script_editor_selected_script', selected)
        size = self.GetSize()
        SetPreference('script_editor_size', size)
        selected = self.ScopeSelector.GetValue()
        SetPreference('script_process_scope', selected)
        choices = self.GetScriptVarsChoices()
        field = choices[self.PreviewField.GetSelection()]
        SetPreference('script_preview_field', field)
        self.EditorPanel.TextCtrl.OnClose(None)
        self.PreviewPanel.TextCtrl.OnClose(None)
        self.MakeModal(False)
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class ScriptCommonPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        self.SetDoubleBuffered(True)

        self.TextCtrl = StyledTextCtrl(self)
        self.SliderV = TextCtrlSliderV(self, self.TextCtrl)
        self.SliderH = TextCtrlSliderH(self, self.TextCtrl)
        self.TextCtrl.SetSliderV(self.SliderV)
        self.TextCtrl.SetSliderH(self.SliderH)
        self.HorizonLeft = DialogPanel(self)
        self.HorizonRight = DialogPanel(self)

        self.OnColor(None)

        self.TextCtrl.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.TextCtrl.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.TextCtrl.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.OnSize(None)
        self.OnColor(None)

    def OnMouseWheel(self, event):
        if event.CmdDown():
            return
        event.Skip()

    def OnSetFocus(self, event):
        self.onFocus = True
        event.Skip()

    def OnKillFocus(self, event):
        self.onFocus = False
        event.Skip()

    def OnSize(self, event):
        margin_top, margin_bottom = (0, 0)
        margin_left, margin_right = (0, 0)
        ss = self.parent.parent.MainPanel.ListBox.scrollbar_size
        padV, padH = (ss, ss)
        self.SliderH.LimitXOffset()
        width, height = self.GetClientSize()
        x_max = self.SliderH.GetXOffsetLimit()
        if x_max > 0:
            sp = 1
        else:
            sp, padH = (1, 0)
        always_show_slider = self.parent.parent.MainPanel.ListBox.always_show_slider
        if always_show_slider:
            sp, padH = (1, ss)

        self.TextCtrl.SetRect((margin_left, margin_top + sp,
                               width - padV - margin_left - margin_right - 1 * 2,
                               height - margin_top - margin_bottom - padH - 1 - sp * 2))
        line = self.TextCtrl.GetFirstVisibleLine()
        self.TextCtrl.ScrollToLine(line)

        self.SliderV.SetRect((width - padV - margin_right - 1, margin_top + 1,
                              padV, height - margin_top - margin_bottom - padH - 1 * 2 - sp))
        self.SliderH.SetRect((40 + margin_left + sp, height - margin_bottom - padH - sp,
                              width - 40 - padV - margin_left - margin_right - sp * 2 - 1, padH))
        self.HorizonLeft.SetRect((0, height - margin_bottom - padH - 2, 40, padH + 2))
        self.HorizonRight.SetRect((width - padV - margin_right - sp,
                                   margin_top + height - margin_top - margin_bottom - padH - sp, padV + 1, padH + 2))
        self.OnColor(None)

    def OnColor(self, event):
        pass

    def OnClose(self, event):
        self.Destroy()


class ScriptEditorPanel(ScriptCommonPanel):

    def __init__(self, parent):
        ScriptCommonPanel.__init__(self, parent)
        self.parent = parent
        st = self.parent.parent.st.EDITBOX
        self.TextCtrl.SetUpEditor()
        self.TextCtrl.TimerEvent = TextEditorEventTimer(self.TextCtrl)
        self.TextCtrl.SetLexer(wx.stc.STC_LEX_PYTHON)
        self.TextCtrl.SetKeyWords(0, ' '.join(keyword.kwlist))
        scriptvars = [v[1] for v in self.parent.GetScriptVars()]
        scriptvars += ['CUSTOMFIELD', 'COUNT']
        self.TextCtrl.SetUserKeyWords(scriptvars)
        self.OnColor(None)

    def OnColor(self, event):
        st = self.parent.parent.st.EDITBOX
        self.SetBackgroundColour(st.EDITOR_BG_COLOR)
        self.TextCtrl.SetBackgroundColour(st.EDITOR_BG_COLOR)
        self.HorizonLeft.SetBackgroundColour(st.LINENUM_BG_COLOR)
        self.HorizonRight.SetBackgroundColour(st.SCROLLBAR_BG_COLOR)


class ScriptPreviewPanel(ScriptCommonPanel):

    def __init__(self, parent):
        ScriptCommonPanel.__init__(self, parent)
        self.parent = parent
        st = self.parent.parent.st.EDITBOX
        self.TextCtrl.SetUpPreview()
        self.OnColor(None)

    def OnColor(self, event):
        st = self.parent.parent.st.EDITBOX
        self.SetBackgroundColour(st.PREVIEW_BG_COLOR)
        self.TextCtrl.SetBackgroundColour(st.PREVIEW_BG_COLOR)
        self.HorizonLeft.SetBackgroundColour(st.LINENUM_BG_COLOR)
        self.HorizonRight.SetBackgroundColour(st.SCROLLBAR_BG_COLOR)


class TextEditorEventTimer(wx.Timer):

    def __init__(self, parent):
        wx.Timer.__init__(self)
        self.parent = parent

        self.stop = False
        self.interval = 100
        self.Start(self.interval)

    def Notify(self):
        if self.stop:
            return
        if self.parent.IsEditable() == False:
            return
        if self.parent.IsModified() and self.parent.parent.IsShown():
            self.parent.savebutton.SetEnable()
        else:
            self.parent.savebutton.SetDisable()


class TextCtrlMaxLineWidthCache():

    def __init__(self):
        self.maxlinewidth_cache = None
        self.maxlinewidth_cache_on = False
        self.maxlinewidth_method = 0
        self.maxlinewidth_rawcache = list()

    def GetCurrentFontWidth(self):
        return self.TextWidth(self.GetStyleAt(0), u'A') - 1
        # return self.TextWidth(wx.stc.STC_STYLE_DEFAULT, u'A')-1

    def GetMaxLineWidth(self):
        if self.maxlinewidth_cache_on:
            if self.maxlinewidth_cache == None:
                self.InitMaxLineWidthCache()
            if self.IsModified():
                self.UpdateMaxLineWidthCache()
            return self.GetMaxLineWidthCache()
        method = self.maxlinewidth_method
        # print self.GetMaxLineWidthBySelectedMethod(method)
        return self.GetMaxLineWidthBySelectedMethod(method)

    def GetMaxLineWidthBySelectedMethod(self, method):
        if method == 0:
            return self.GetMaxLineWidthFixedWidth()
        elif method == 1:
            return self.GetMaxLineWidthFixedWidthLineSep()
        elif method == 2:
            return self.GetMaxLineWidthPrecise()
        elif method == 3:
            return self.GetMaxLineWidthPreciseMore()
        elif method == 4:
            return self.GetMaxLineWidthPreciseSamrt()

    def InitMaxLineWidthCache(self):
        method = self.maxlinewidth_method
        cache = self.GetMaxLineWidthBySelectedMethod(method)
        self.maxlinewidth_cache = cache

    def UpdateMaxLineWidthCache(self):
        string = self.GetLine(self.GetCurrentLine())
        tw = self.GetCurrentFontWidth()
        cache = self.TextWidth(wx.stc.STC_STYLE_DEFAULT, string) + tw
        # self.TextWidth(wx.stc.STC_STYLE_DEFAULT,\
        # 	self.GetLine(i)) for i in range(self.GetLineCount())
        # GetStyleAt()
        # GetLinesAdded
        if cache > self.maxlinewidth_cache:
            self.maxlinewidth_cache = cache

    def GetMaxLineWidthCache(self):
        return self.maxlinewidth_cache

    def GetMaxLineWidthFixedWidth(self):
        tw = self.GetCurrentFontWidth()
        maxlinewidth = max([len(self.GetLine(i).replace('\t', 'AAAA'))
                            for i in range(self.GetLineCount())])
        return maxlinewidth * tw
    #
    # def GetMaxLineWidthFixedWidthLineSep(self):
    #  	tw = self.GetCurrentFontWidth()
    # 	# text = self.GetValue()
    # 	text = self.GetTextRaw()
    # 	maxlinewidth = max([len(v) for v in text.split('\n')])
    # 	return maxlinewidth*tw

    def GetMaxLineWidthFixedWidthLineSep(self):
        print(self.GetEdgeColumn())
        tw = self.GetCurrentFontWidth()
        mlw = [self.GetLineEndPosition(i) for i in range(self.GetLineCount())]
        maxlinewidth = max(numpy.array(mlw + [mlw[-1]]) - numpy.array([0] + mlw))
        return maxlinewidth * tw

    def GetMaxLineWidthPrecise(self):
        cache = list()
        tw = self.GetCurrentFontWidth()
        maxlinewidth = max([self.TextWidth(wx.stc.STC_STYLE_DEFAULT,
                                           self.GetLine(i)) for i in range(self.GetLineCount())])
        return maxlinewidth

    def GetMaxLineWidthPreciseMore(self):
        style = self.GetStyleAt(0)
        lines = list()
        for i in range(self.GetLineCount()):
            string = self.GetLine(i)
            string = string.replace('\t', 'AAAA').replace(' ', 'A')
            lines += [self.TextWidth(style, string)]
        maxlinewidth = max(lines)
        return maxlinewidth

    def GetMaxLineWidthPreciseSamrt(self):
        threshold = 0
        lines = list()
        tw = self.GetCurrentFontWidth()
        for i in range(self.GetLineCount()):
            string = self.GetLine(i)
            if len(string) < threshold:
                continue
            threshold = len(string) / 2
            lines += [self.TextWidth(wx.stc.STC_STYLE_DEFAULT, string)]
        maxlinewidth = max(lines)
        return maxlinewidth


# wx.stc.StyledTextCtrl
# http://www.wxpython.org/docs/api/wx.stc.StyledTextCtrl-class.html

class StyledTextCtrl(wx.stc.StyledTextCtrl, TextCtrlMaxLineWidthCache):
    fold_symbols = 2

    def __init__(self, parent):
        wx.stc.StyledTextCtrl.__init__(self, parent, style=wx.BORDER_NONE)
        self.parent = parent
        self.SetUpCommonStyle()
        TextCtrlMaxLineWidthCache.__init__(self)
        self.SetUseHorizontalScrollBar(False)
        self.SetUseVerticalScrollBar(False)

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.Bind(wx.stc.EVT_STC_UPDATEUI, self.OnUpdateUI)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyPressed)
        self.Bind(wx.stc.EVT_STC_AUTOCOMP_SELECTION,
                  self.AutoCompleteMouseEventHandler)
        self.autocomplete_trigger_word = None
        self.autocomplete_shownkeyword = None

        # self.CmdKeyAssign(ord('B'), wx.stc.STC_SCMOD_CTRL, wx.stc.STC_CMD_ZOOMIN)
        # self.CmdKeyAssign(ord('N'), wx.stc.STC_SCMOD_CTRL, wx.stc.STC_CMD_ZOOMOUT)

    def SetSaveButton(self, savebutton):
        self.savebutton = savebutton

    def SetSliderV(self, SliderV):
        self.SliderV = SliderV

    def SetSliderH(self, SliderH):
        self.SliderH = SliderH

    def OnMouseWheel(self, event):
        if hasattr(self, 'SliderV'):
            self.SliderV.DirectDraw()
        if hasattr(self, 'SliderH') and event.cmdDown:
            self.SliderH.DirectDraw()
        event.Skip()

    def AutoCompleteMouseEventHandler(self, event):
        self.AutoCompleteCustomEventHandler()
        event.Skip()

    def OnKeyPressed(self, event):
        if self.IsEditable():
            self.HandleEditorEvent(event)
        else:
            event.Skip()

    def AutoCompleteCustomEventHandler(self):
        if self.AutoCompActive() == False:
            return False
        if self.autocomplete_trigger_word == None:
            return False
        if self.autocomplete_shownkeyword == None:
            return False
        idx = self.AutoCompGetCurrent()
        self.AutoCompCancel()
        pos = self.GetCurrentPos()
        self.SetSelection(pos - len(self.autocomplete_trigger_word), pos)
        word = self.autocomplete_shownkeyword[idx].split('?')[0]
        self.ReplaceSelection(word)
        self.autocomplete_trigger_word = None
        self.autocomplete_shownkeyword = None
        return True

    def HandleEditorEvent(self, event):
        keycode = event.GetKeyCode()

        if self.CallTipActive():
            self.CallTipCancel()

        if (event.CmdDown() or event.ControlDown()) and keycode == 83:  # Ctrl + S
            self.parent.parent.OnSave(None)
            self.savebutton.SetDisable()

        if keycode == wx.WXK_TAB\
                or keycode == wx.WXK_RETURN\
                or keycode == wx.WXK_NUMPAD_ENTER:
            if self.AutoCompleteCustomEventHandler():
                return

        if keycode == wx.WXK_TAB:
            pos = self.GetCurrentPos()
            string, pos = self.GetCurLine()
            word = string[:pos].split(' ')[-1]
            for v in """.|,|=|+|-|*|/|%|^|&|@|(|[|{|\t""".split('|'):
                word = word.split(v)[-1]
            if len(word) != 0:
                kw = keyword.kwlist[:]
                kw = [v for v in kw if v.lower().startswith(word.lower())]
                if len(kw) != 0:
                    kw.sort()
                    for i in range(len(kw)):
                        kw[i] = kw[i] + '?1'
                    self.autocomplete_trigger_word = word
                    self.autocomplete_shownkeyword = kw
                    self.AutoCompSetIgnoreCase(False)  # so this needs to match
                    self.AutoCompShow(0, ' '.join(kw))
                else:
                    event.Skip()
            else:
                event.Skip()
        else:
            event.Skip()

    def OnUpdateUI(self, event):
        # check for matching braces
        braceAtCaret = -1
        braceOpposite = -1
        charBefore = None
        caretPos = self.GetCurrentPos()
        if caretPos > 0:
            charBefore = self.GetCharAt(caretPos - 1)
            styleBefore = self.GetStyleAt(caretPos - 1)

        # check before
        if charBefore and chr(charBefore) in '[]{}()'\
                and styleBefore == wx.stc.STC_P_OPERATOR:
            braceAtCaret = caretPos - 1

        # check after
        if braceAtCaret < 0:
            charAfter = self.GetCharAt(caretPos)
            styleAfter = self.GetStyleAt(caretPos)
            if charAfter and chr(charAfter) in '[]{}()'\
                    and styleAfter == wx.stc.STC_P_OPERATOR:
                braceAtCaret = caretPos

        if braceAtCaret >= 0:
            braceOpposite = self.BraceMatch(braceAtCaret)
        if braceAtCaret != -1 and braceOpposite == -1:
            self.BraceBadLight(braceAtCaret)
        else:
            self.BraceHighlight(braceAtCaret, braceOpposite)
            #pt = self.PointFromPosition(braceOpposite)
            #self.Refresh(True, wxRect(pt.x, pt.y, 5,5))
            # print pt
            # self.Refresh(False)

        self.parent.OnSize(None)
        if hasattr(self, 'SliderV'):
            self.SliderV.DirectDraw()
        if hasattr(self, 'SliderH'):
            self.SliderH.DirectDraw()

    def SetValue(self, value):
        if wx.USE_UNICODE:
            value = value.decode('iso8859_1')
        val = self.GetReadOnly()
        self.SetReadOnly(False)
        self.SetText(value)
        self.EmptyUndoBuffer()
        self.SetSavePoint()
        self.SetReadOnly(val)

    def SetEditable(self, val):
        self.SetReadOnly(not val)

    def IsModified(self):
        return self.GetModify()

    def Clear(self):
        self.ClearAll()

    def SetInsertionPoint(self, pos):
        self.SetCurrentPos(pos)
        self.SetAnchor(pos)

    def ShowPosition(self, pos):
        line = self.LineFromPosition(pos)
        # self.EnsureVisible(line)
        self.GotoLine(line)

    def GetLastPosition(self):
        return self.GetLength()

    def GetPositionFromLine(self, line):
        return self.PositionFromLine(line)

    def GetRange(self, start, end):
        return self.GetTextRange(start, end)

    def GetSelection(self):
        return self.GetAnchor(), self.GetCurrentPos()

    def SetSelection(self, start, end):
        self.SetSelectionStart(start)
        self.SetSelectionEnd(end)

    def SelectLine(self, line):
        start = self.PositionFromLine(line)
        end = self.GetLineEndPosition(line)
        self.SetSelection(start, end)

    def SetUserKeyWords(self, keywords):
        keyword.kwlist = keyword.kwlist + keywords
        self.SetKeyWords(0, ' '.join(keyword.kwlist))

    def GetDefaultFont(self):
        font = wx.Font(0, wx.FONTFAMILY_MODERN,
                       wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        font.SetPixelSize((8, 13))
        font.SetFaceName('Consolas')
        return font

    def SetUpCommonStyle(self):

        st = self.parent.parent.parent.st.EDITBOX
        # if wx.Platform == '__WXMSW__':
        # 11, 8, Times New Roman, Courier New, Arial, Comic Sans MS
        # elif wx.Platform == '__WXMAC__':
        # 12, 10, Times New Roman, Monaco, Arial, Comic Sans MS
        # else: # 12, 10, Times, Courier, Helvetica, new century schoolbook

        self.SetMargins(6, 6)  # Left and Right margins
        self.SetViewWhiteSpace(False)
        self.SetEdgeMode(wx.stc.STC_EDGE_NONE)
        self.SetMarginType(1, wx.stc.STC_MARGIN_NUMBER)
        self.SetMarginWidth(1, 40)
        self.SetMarginWidth(2, 0)
        self.SetMarginMask(2, 0)

        st = self.parent.parent.parent.st.EDITBOX
        font = self.GetDefaultFont()
        fontname = font.GetFaceName()
        fontsize = font.GetPointSize()
        bgcolor = rgb_dec2hex(st.EDITOR_BG_COLOR)
        fgcolor = rgb_dec2hex(st.EDITOR_FG_COLOR)
        self.StyleSetSpec(wx.stc.STC_STYLE_DEFAULT,
                          'fore:#%s,back:#%s,face:%s,size:%d' % (fgcolor, bgcolor, fontname, fontsize))
        self.StyleSetSpec(wx.stc.STC_STYLE_CONTROLCHAR, 'face:%s' % fontname)

        self.RegisterImage(1, images.checkmark_icon14.GetBitmap())

        self.SetEOLMode(wx.stc.STC_EOL_LF)  # strings will always have '\n'
        self.SetViewEOL(False)

        self.SetTwoPhaseDraw(True)
        self.SetCaretPeriod(400)
        # Caret color
        self.SetCaretForeground(st.CARET_BG_COLOR)
        self.SetCaretWidth(1)
        # Selection background
        self.SetSelBackground(2, st.CARET_BG_COLOR)
        self.SetSelBackground(True, st.CARET_BG_COLOR)
        self.SetSelForeground(True, st.CARET_FG_COLOR)

    def SetUpEditor(self):

        self.SetUpCommonStyle()
        self.StyleClearAll()

        self.SetIndent(4)
        self.SetIndentationGuides(True)
        self.SetBackSpaceUnIndents(True)
        self.SetTabIndents(True)
        self.SetTabWidth(4)
        self.SetUseTabs(True)

        st = self.parent.parent.parent.st.EDITBOX
        # Clear styles and revert to default.
        # Line numbers in margin
        self.StyleSetSpec(wx.stc.STC_STYLE_LINENUMBER, 'fore:#%s,back:#%s'
                          % (rgb_dec2hex(st.LINENUM_FG_COLOR), rgb_dec2hex(st.LINENUM_BG_COLOR)))

        bg = rgb_dec2hex(st.BRACE_BG_COLOR)
        fg = rgb_dec2hex(st.BRACE_FG_COLOR)
        # Highlighted brace
        self.StyleSetSpec(wx.stc.STC_STYLE_BRACELIGHT, 'fore:#%s,back:#%s' % (fg, bg))
        # Unmatched brace
        self.StyleSetSpec(wx.stc.STC_STYLE_BRACEBAD, 'fore:#%s,back:#%s' % (fg, bg))
        # Indentation guide
        self.StyleSetSpec(wx.stc.STC_STYLE_INDENTGUIDE, 'fore:#404040')

        self.StyleSetSpec(wx.stc.STC_MARGIN_BACK, 'fore:#404040,back:#99A9C2')

        # Python styles
        bg = rgb_dec2hex(st.EDITOR_BG_COLOR)
        fg = rgb_dec2hex(st.EDITOR_FG_COLOR)
        self.StyleSetSpec(wx.stc.STC_P_DEFAULT, 'fore:#%s' % (fg))
        # Comments
        self.StyleSetSpec(wx.stc.STC_P_COMMENTLINE,  'fore:#404040')
        self.StyleSetSpec(wx.stc.STC_P_COMMENTBLOCK, 'fore:#404040')
        # Numbers
        self.StyleSetSpec(wx.stc.STC_P_NUMBER, 'fore:#%s,back:#%s' % (fg, bg))
        # Strings and characters
        self.StyleSetSpec(wx.stc.STC_P_STRING, 'fore:#22AA22')
        self.StyleSetSpec(wx.stc.STC_P_CHARACTER, 'fore:#22AA22')
        # Keywords
        self.StyleSetSpec(wx.stc.STC_P_WORD, 'fore:#6060FF,bold')
        # Triple quotes
        self.StyleSetSpec(wx.stc.STC_P_TRIPLE, 'fore:#22AA22')
        self.StyleSetSpec(wx.stc.STC_P_TRIPLEDOUBLE, 'fore:#22AA22')
        # Class names
        self.StyleSetSpec(wx.stc.STC_P_CLASSNAME, 'fore:#22EE22,bold')
        # Function names
        self.StyleSetSpec(wx.stc.STC_P_DEFNAME, 'fore:#22EE22,bold')
        # Operators
        self.StyleSetSpec(wx.stc.STC_P_OPERATOR, 'fore:#882222,bold')
        # Identifiers. I leave this as not bold because everything seems
        # to be an identifier if it doesn't match the above criterae
        self.StyleSetSpec(wx.stc.STC_P_IDENTIFIER, 'fore:#%s' % (fg))

    def SetUpPreview(self):
        self.SetUpCommonStyle()
        self.StyleClearAll()
        self.SetLexer(wx.stc.STC_LEX_NULL)
        self.SetEditable(False)

        st = self.parent.parent.parent.st.EDITBOX
        font = self.GetDefaultFont()
        fontname = font.GetFaceName()
        fontsize = font.GetPointSize()
        bgcolor = rgb_dec2hex(st.PREVIEW_BG_COLOR)
        fgcolor = rgb_dec2hex(st.PREVIEW_FG_COLOR)
        self.StyleSetSpec(wx.stc.STC_STYLE_DEFAULT,
                          'fore:#%s,back:#%s,face:%s,size:%d' % (fgcolor, bgcolor, fontname, fontsize))
        self.StyleSetSpec(wx.stc.STC_STYLE_CONTROLCHAR, 'face:%s' % fontname)
        self.StyleClearAll()

        # Line numbers in margin
        fg = rgb_dec2hex(st.LINENUM_FG_COLOR)
        bg = rgb_dec2hex(st.LINENUM_BG_COLOR)
        self.StyleSetSpec(wx.stc.STC_STYLE_LINENUMBER, 'fore:#%s,back:#%s' % (fg, bg))
        # Python styles
        fg = rgb_dec2hex(st.EDITOR_FG_COLOR)
        self.StyleSetSpec(wx.stc.STC_P_DEFAULT, 'fore:#%s' % (fg))

    def RegisterModifiedEvent(self, eventHandler):
        self.Bind(wx.stc.EVT_STC_CHANGE, eventHandler)

    def OnSize(self, event):
        pass

    def OnClose(self, event):
        pass


class TextCtrlSliderEvent(wx.Timer):

    def __init__(self, slider):
        wx.Timer.__init__(self)
        self.slider = slider
        self.stop = True
        self.interval = 50
        self.rectIdx = None
        self.Start(self.interval)

    def Notify(self):
        if self.stop:
            return
        state = wx.GetMouseState()
        state.x, state.y = self.slider.ScreenToClient((state.x, state.y))
        if state.LeftIsDown() == False:
            self.Trace(None)
            self.slider.knobdrag = False
        self.slider.OnMouseEvent(state)

    def Trace(self, rectIdx):
        self.rectIdx = rectIdx
        if self.rectIdx:
            self.stop = False
        else:
            self.stop = True


class TextCtrlSliderRect(RectRect, wx.Window):

    def __init__(self, parent, textctrl):
        RectRect.__init__(self)
        wx.Window.__init__(self, parent,
                           style=wx.CLIP_CHILDREN | wx.TAB_TRAVERSAL | wx.NO_BORDER)
        self.parent = parent
        self.textctrl = textctrl
        st = self.parent.parent.parent.st.LISTBOX
        self.SetBackgroundColour(st.SCROLLBAR_BG_COLOR)
        self.knobdrag = False
        self.Bind(wx.EVT_SIZE, self.OnSize)
        # self.Bind(wx.EVT_IDLE, self.OnIdle)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.event = TextCtrlSliderEvent(self)


class TextCtrlSliderV(TextCtrlSliderRect):

    def __init__(self, parent, textctrl):
        TextCtrlSliderRect.__init__(self, parent, textctrl)
        self.InitBuffer()

    def OnEnterWindow(self, event):
        self.onClient = True

    def OnLeaveWindow(self, event):
        self.onClient = False

    def GetVisibleLineCount(self):
        return len([i for i in range(linelength) if self.textctrl.GetLineVisible(i)])

    def GetVirtualPositionYLimit(self):
        th = self.textctrl.TextHeight(0)
        try:
            shownheight = self.textctrl.GetVirtualSize().height
        except:
            shownheight = 0
        linelength = self.textctrl.GetLineCount()
        totalheight = linelength * th
        if totalheight < shownheight:
            return 0
        return -totalheight + shownheight

    def OnMouseEvent(self, event):
        xy = (event.x, event.y)
        rectIdx = self.GetRectIdx(xy)

        if (rectIdx == 5 and hasattr(event, 'EventType') and event.LeftDown())\
                or (rectIdx == 5 and event.LeftIsDown() and self.event.rectIdx == rectIdx):
            self.textctrl.ScrollLines(-1)
            # self.reInitBuffer = True
            self.DirectDraw()
            self.event.Trace(rectIdx)

        if (rectIdx == 4 and hasattr(event, 'EventType') and event.LeftDown())\
                or (rectIdx == 4 and event.LeftIsDown() and self.event.rectIdx == rectIdx):
            self.textctrl.ScrollLines(1)
            # self.reInitBuffer = True
            self.DirectDraw()
            self.event.Trace(rectIdx)

        elif rectIdx == 3 and hasattr(event, 'EventType')\
                and event.LeftDown() and self.event.rectIdx == None:
            if self.knobdrag == False:
                th = self.textctrl.TextHeight(0)
                self.knobdrag_startline = self.textctrl.GetFirstVisibleLine()
                self.knobdrag_startpos = self.textctrl.GetFirstVisibleLine() * th
                self.knobdrag_start_y = event.y
            self.knobdrag = True
            # self.reInitBuffer = True
            self.DirectDraw()
            self.event.Trace(rectIdx)

        elif self.knobdrag and self.event.rectIdx == 3:
            rect = self.rects
            initPosY = self.knobdrag_start_y - rect.slidable.y
            th = self.textctrl.TextHeight(0)
            linelength = self.textctrl.GetLineCount()
            totalheight = linelength * th
            shownheight = self.textctrl.GetVirtualSize().height
            if totalheight != 0:
                shownRatio = 1.0 * shownheight / totalheight
            else:
                shownRatio = 1.0
            if shownRatio > 1.0:
                shownRatio = 1.0
            slidable = rect.slidable.height - rect.knob.height
            if slidable == 0:
                return
            diff = event.y - initPosY - rect.slidable.y
            diffRatio = 1.0 * diff * (totalheight - shownheight) / slidable
            vpy = self.knobdrag_startpos - diffRatio
            line = self.knobdrag_startline * 2 - 1.0 * vpy / th
            self.textctrl.ScrollToLine(line)
            # self.reInitBuffer = True
            self.DirectDraw()

        elif rectIdx == 2 and hasattr(event, 'EventType') and event.LeftDown():
            rect = self.rects
            slidable = rect.slidable.height - rect.knob.height
            if slidable != 0:
                posCYRatio = 1.0 * (event.Y - rect.slidable.y - rect.knob.height * 0.5) / slidable
            else:
                posCYRatio = 1.0
            vpy_limit = self.GetVirtualPositionYLimit()
            vpy = int(posCYRatio * vpy_limit)
            th = self.textctrl.TextHeight(0)
            line = -1.0 * vpy / th
            self.event.Trace(rectIdx)
            self.textctrl.ScrollToLine(line)
            # self.reInitBuffer = True
            self.DirectDraw()

    def SetRectDraw(self, dc):
        self.DrawSliderV(dc)

    def DrawSliderV(self, dc):
        width, height = self.GetSize()
        slider = wx.Rect(0, 0, width, height)
        btnup = wx.Rect(0, 0, width, width)
        btndown = wx.Rect(0, height - width, width, width)
        slidable = wx.Rect(0, width, width, height - width * 2)
        th = self.textctrl.TextHeight(0)
        linelength = self.textctrl.GetLineCount()
        totalheight = linelength * th
        current = self.textctrl.GetFirstVisibleLine() * th
        if totalheight != 0:
            shownRatio = 1.0 * self.textctrl.GetVirtualSize().height / totalheight
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        h = slidable.height * shownRatio
        if h < width:
            h = 1.0 * width
        div = totalheight - self.textctrl.GetVirtualSize().height
        if div != 0:
            posCYRatio = 1.0 * (current) / div
        else:
            posCYRatio = 1.0
        if posCYRatio > 1.0:
            posCYRatio = 1.0
        x = slidable.x
        y = slidable.y + math.ceil((slidable.height - h) * posCYRatio)
        knob = wx.Rect(x, y, width, h)
        self.rects = Struct(slider=slider, slidable=slidable,
                            knob=knob, btnup=btnup, btndown=btndown)

        st = self.parent.parent.parent.st.EDITBOX
        bgcolor = st.SCROLLBAR_BG_COLOR
        fgcolor = st.SCROLLBAR_FG_COLOR
        pncolor = st.SCROLLBAR_PN_COLOR

        dc.DrawRectangleList((slidable,),
                             pens=wx.Pen(bgcolor, 1), brushes=wx.Brush(bgcolor))
        lines = ((slidable.x + 1, slidable.y, slidable.x + width - 1, slidable.y),
                 (slidable.x + 1, slidable.height + width - 1, slidable.x + width - 1, slidable.height + width - 1))
        dc.DrawLineList(lines, pens=wx.Pen(bgcolor, 1))
        dc.DrawRectangleList((knob, btnup, btndown),
                             pens=wx.Pen(pncolor, 1), brushes=wx.Brush(fgcolor))

    def GetRectIdx(self, xy):
        if self.onClient == False:
            return None
        if self.IsInRect(self.rects.btnup, xy):
            return 5
        elif self.IsInRect(self.rects.btndown, xy):
            return 4
        elif self.IsInRect(self.rects.knob, xy):
            return 3
        elif self.IsInRect(self.rects.slidable, xy):
            return 2
        return 1

    def OnSize(self, event=None):
        self.DirectDraw()


class TextCtrlSliderH(TextCtrlSliderRect):

    def __init__(self, parent, textctrl):
        TextCtrlSliderRect.__init__(self, parent, textctrl)
        self.InitBuffer()

    def OnEnterWindow(self, event):
        self.onClient = True

    def OnLeaveWindow(self, event):
        self.onClient = False

    def OnMouseEvent(self, event):
        xy = (event.x, event.y)
        self.reInitBuffer = True

    def SetRectDraw(self, dc):
        self.LimitXOffset()
        self.DrawSliderH(dc)

    def DrawSliderH(self, dc):
        tw = self.GetCurrentFontWidth()
        width, height = self.GetClientSize()
        slider = wx.Rect(0, 0, width, height)
        btnleft = wx.Rect(0, 0, height, height)
        btnright = wx.Rect(width - height, 0, height, height)
        slidable = wx.Rect(height, 0, width - height * 2, height)
        length = self.GetMaxLineWidth()  # +tw
        if length != 0:
            shownRatio = 1.0 * self.GetShownAreaWidth() / length
        else:
            shownRatio = 1.0
        if shownRatio > 1.0:
            shownRatio = 1.0
        w = slidable.width * shownRatio
        if w < height:
            w = 1.0 * height

        div = length - self.GetShownAreaWidth()
        if div != 0:
            posCXRatio = 1.0 * (self.textctrl.GetXOffset()) / div
        else:
            posCXRatio = 1.0
        if posCXRatio > 1.0:
            posCXRatio = 1.0
        x = slidable.x + math.ceil((slidable.width - w) * posCXRatio)
        y = slidable.y
        knob = wx.Rect(x, y, w, height)
        self.rects = Struct(slider=slider, slidable=slidable, knob=knob,
                            btnleft=btnleft, btnright=btnright)

        st = self.parent.parent.parent.st.EDITBOX
        bgcolor = st.SCROLLBAR_BG_COLOR
        fgcolor = st.SCROLLBAR_FG_COLOR
        pncolor = st.SCROLLBAR_PN_COLOR

        dc.DrawRectangleList((slidable,),
                             pens=wx.Pen(bgcolor, 1), brushes=wx.Brush(bgcolor))
        lines = ((slidable.x, slidable.y + 1, slidable.x, slidable.y + height - 1),
                 (slidable.width + height - 1, slidable.y + 1, slidable.width + height - 1, slidable.y + height - 1))
        dc.DrawLineList(lines, pens=wx.Pen(bgcolor, 1))
        dc.DrawRectangleList((knob, btnleft, btnright),
                             pens=wx.Pen(pncolor, 1), brushes=wx.Brush(fgcolor))

    def GetMaxLineWidth(self):
        return self.textctrl.GetMaxLineWidth()

    def GetCurrentFontWidth(self):
        return self.textctrl.GetCurrentFontWidth()

    def GetShownAreaWidth(self):
        return self.GetClientSize().width

    def LimitXOffset(self):
        tw = self.GetCurrentFontWidth()
        x = self.textctrl.GetXOffset()
        x = self.GetLimitedXOffset(x)
        self.textctrl.SetXOffset(x)

    def GetLimitedXOffset(self, x):
        x_max = self.GetXOffsetLimit()
        if x > x_max:
            x = x_max
        if x < 0:
            x = 0
        return x

    def GetXOffsetLimit(self):
        tw = self.GetCurrentFontWidth()
        margin = self.textctrl.GetMarginLeft() + self.textctrl.GetMarginRight() + 40
        return self.GetMaxLineWidth() - self.textctrl.GetVirtualSize().width + margin

    def OnMouseEvent(self, event):
        xy = (event.x, event.y)
        rectIdx = self.GetRectIdx(xy)
        tw = self.GetCurrentFontWidth()

        if (rectIdx == 5 and hasattr(event, 'EventType') and event.LeftDown())\
                or (rectIdx == 5 and event.LeftIsDown() and self.event.rectIdx == rectIdx):
            x = self.textctrl.GetXOffset()
            x = self.GetLimitedXOffset(x - tw * 4)
            self.textctrl.SetXOffset(x)
            # self.reInitBuffer = True
            self.DirectDraw()
            self.event.Trace(rectIdx)

        elif (rectIdx == 4 and hasattr(event, 'EventType') and event.LeftDown())\
                or (rectIdx == 4 and event.LeftIsDown() and self.event.rectIdx == rectIdx):
            x = self.textctrl.GetXOffset()
            x = self.GetLimitedXOffset(x + tw * 4)
            self.textctrl.SetXOffset(x)
            # self.reInitBuffer = True
            self.DirectDraw()
            self.event.Trace(rectIdx)

        elif rectIdx == 3 and hasattr(event, 'EventType')\
                and event.LeftDown() and self.event.rectIdx == None:
            if self.knobdrag == False:
                self.knobdrag_startpos = self.textctrl.GetXOffset()
                self.knobdrag_start_x = event.x
            self.knobdrag = True
            # self.reInitBuffer = True
            self.DirectDraw()
            self.event.Trace(rectIdx)

        elif self.knobdrag and self.event.rectIdx == 3:
            rect = self.rects
            initPosX = self.knobdrag_start_x - rect.slidable.x
            length = self.GetMaxLineWidth() + tw
            list_width = self.textctrl.GetVirtualSize().width - 40
            slidable = rect.slidable.width - rect.knob.width
            if slidable == 0:
                return
            diff = event.x - initPosX - rect.slidable.x
            diffRatio = 1.0 * diff * (length - list_width) / slidable
            vpx = diffRatio + self.knobdrag_startpos
            vpx = self.GetLimitedXOffset(vpx)
            self.textctrl.SetXOffset(vpx)
            # self.reInitBuffer = True
            self.DirectDraw()

        elif rectIdx == 2 and hasattr(event, 'EventType') and event.LeftDown():
            rect = self.rects
            slidable = rect.slidable.height - rect.knob.height
            rect = self.rects
            slidable = rect.slidable.width - rect.knob.width
            if slidable != 0:
                posCXRatio = 1.0 * (event.x - rect.slidable.x - rect.knob.width * 0.5) / slidable
            else:
                posCXRatio = 1.0
            vpx = int(posCXRatio * self.GetXOffsetLimit())
            self.event.Trace(rectIdx)
            vpx = self.GetLimitedXOffset(vpx)
            self.textctrl.SetXOffset(vpx)
            # self.reInitBuffer = True
            self.DirectDraw()

    def GetRectIdx(self, xy):
        if self.onClient == False:
            return None
        if self.IsInRect(self.rects.btnleft, xy):
            return 5
        elif self.IsInRect(self.rects.btnright, xy):
            return 4
        elif self.IsInRect(self.rects.knob, xy):
            return 3
        elif self.IsInRect(self.rects.slidable, xy):
            return 2
        return 1

    def OnSize(self, event=None):
        self.DirectDraw()
