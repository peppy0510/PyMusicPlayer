# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import images
import io
import listimages
import macroboxstyle
import mfeats
import os
import threading
import time
import uikit
import urllib.parse
import webbrowser
import webinfo
import wx

from coverbox import COVER_PRESETS
from coverbox import CoverField
from coverbox import CoverPicture
from coverbox import append_cover_items
from coverbox import edit_cover_by_hand
from coverbox import format_picture_size
from coverbox import get_cover_label
from coverbox import keep_copied_cover
from coverbox import look_up_cover_for
from coverbox import preset_cover
from coverbox import show_notice
from macroboxlib import Button
from macroboxlib import ConfirmDialogBox
from macroboxlib import DialogBox
from macroboxlib import DialogPanel
from macroboxlib import DIALOG_GAP
from macroboxlib import DIALOG_PAD
from macroboxlib import DIALOG_ROW
from macroboxlib import make_check
from macroboxlib import GetPreference
from macroboxlib import GetPreferences
from macroboxlib import ListBoxColumn
from macroboxlib import MakeMusicFileItem
from macroboxlib import SetPreference
from macroboxlib import StaticText
from macroboxlib import TextCtrl


class ItemEditPanel(DialogPanel):

    def __init__(self, parent, pos=(0, 0)):
        DialogPanel.__init__(self, parent)
        self.Show(False)
        self.parent = parent
        x, y = pos
        width, height = self.parent.GetClientSize()
        self.SetRect((x, y, width, self.GetContentHeight()))
        self.labels = ('Path', 'Filename', 'Duration', 'Size', 'Bitrate',
                       'Channel', 'Artist', 'Title', 'Album', 'Genre', 'Key', 'Tempo')
        self.disables = ('Duration', 'Type', 'Size', 'Bitrate', 'Channel', 'Path')
        # keep the file's modified date on save (KEEP), read once
        keep = GetPreference('item_editor_keep_modified')
        self.keep_modified = keep is not False

    # fields and footer in the dialogs' spacing (macroboxlib.DIALOG_PAD)
    PAD = DIALOG_PAD
    ROW = DIALOG_ROW
    ROW_GAP = DIALOG_GAP
    LABEL = 50
    LABEL_GAP = DIALOG_GAP
    # Modified shown, not a list column; KEEP across two columns
    ROWS = (('Path',), ('Filename',), ('Duration', 'Size', 'Bitrate', 'Channel'),
            ('Modified', None, 'KEEP', None),
            ('Artist',), ('Title',), ('Album',), ('Genre', None, 'Key', 'Tempo'))
    RIGHT = ('Duration', 'Size', 'Bitrate', 'Channel', 'Tempo')
    # the fields' width; the cover (CoverField) at their left, as tall as their rows
    GRID = 552

    @classmethod
    def GetCoverSize(cls):
        return len(cls.ROWS) * cls.ROW + (len(cls.ROWS) - 1) * cls.ROW_GAP

    @classmethod
    def GetContentHeight(cls):
        return cls.PAD * 2 + cls.GetCoverSize()

    @classmethod
    def GetContentWidth(cls):
        return cls.PAD * 3 + cls.GetCoverSize() + cls.GRID

    def SetPage(self, item_idx):
        if hasattr(self, 'TextCtrls') is False:
            self.InitTextCtrls()
        self.restore_value = list()
        for i, v in enumerate(self.labels):
            columnKey = v.lower()
            value = self.parent.parent.parent.GetItemValueByColumnKey(item_idx, columnKey)
            # if type(value) == str:
            # if isinstance(value, str):
            #     value = value.decode(sys.getfilesystemencoding())
            # if type(value) in (int, float, long):
            if isinstance(value, int) or isinstance(value, float):
                value = str(value)
            self.TextCtrls[i].SetValue(value)
            self.restore_value.append(value)
            if columnKey == 'path':
                value = os.path.dirname(value)
            if isinstance(value, str):
                # value = value.decode(sys.getfilesystemencoding())
                self.TextCtrls[i].SetValue(value)
            if v in self.disables:
                # read-only
                self.TextCtrls[i].SetReadOnly()
        path = self.parent.parent.parent.GetItemValueByColumnKey(item_idx, 'path')
        self.Cover.SetSong(path)
        self.SetModified(path)
        self.Refresh()

    def InitTextCtrls(self):
        width, height = self.GetClientSize()
        size = self.GetCoverSize()
        self.Cover = CoverField(self, (self.PAD, self.PAD), (size, size))
        start = self.PAD * 2 + size
        right = width - self.PAD
        column = (right - start - self.PAD * 3) / 4.0
        fields = dict()
        y = self.PAD
        for row in self.ROWS:
            for k, label in enumerate(row):
                if label is None:
                    continue
                x = int(round(start + k * (column + self.PAD)))
                left = x + self.LABEL + self.LABEL_GAP
                # the last of a row to the right edge; Genre across two
                last = k == len(row) - 1
                spans = 2 if k + 1 < len(row) and row[k + 1] is None else 1
                end = right if last else int(round(
                    start + (k + spans) * (column + self.PAD) - self.PAD))
                if label == 'KEEP':
                    self.KeepModified, _ = make_check(
                        self, 'Keep the modified date on save', (left, y + 3),
                        self.keep_modified, self.OnKeepModified)
                    continue
                style = wx.ALIGN_RIGHT if label in self.RIGHT else 0
                text = StaticText(self, label=label, pos=(x, y + 3),
                                  size=(self.LABEL, 20), style=wx.ALIGN_RIGHT)
                fields[label] = (text, TextCtrl(self, pos=(left, y),
                                                size=(end - left, self.ROW), style=style))
            y += self.ROW + self.ROW_GAP
        self.StaticTexts = [fields[v][0] for v in self.labels]
        self.TextCtrls = [fields[v][1] for v in self.labels]
        # editable fields mark changes as typed; their own menu
        for i, label in enumerate(self.labels):
            if label in self.disables:
                continue
            text = self.TextCtrls[i]
            text.Bind(wx.EVT_TEXT, lambda e: (self.parent.UpdateMarks(), e.Skip()))
            text.Bind(wx.EVT_CONTEXT_MENU, lambda e, i=i: self.parent.ShowFieldMenu(i))
        self.Modified = fields['Modified'][1]
        self.Modified.SetReadOnly()
        # the names dimmed, the values (and the fields) brighter
        for text, _ in fields.values():
            text.SetForegroundColour(macroboxstyle.current().UI.BAR_TEXT_DIM)
        # the editor's menu on its ground and names too; fields keep their own
        for window in [self] + [c for c in self.GetChildren() if isinstance(c, wx.StaticText)]:
            window.Bind(wx.EVT_RIGHT_UP, lambda e, window=window:
                        self.parent.ShowMenu(window))

    def OnKeepModified(self, value):
        self.keep_modified = value
        SetPreference('item_editor_keep_modified', value)

    def SetModified(self, path):
        try:
            stamp = os.stat(path).st_mtime
        except OSError:
            self.Modified.SetValue('')
            return
        self.Modified.SetValue(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stamp)))

    def OnClose(self, event):
        self.Destroy()


class ItemEditBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(600, 320))
        self.parent = parent
        self.SetTitle('Track Information Editor')
        self.selectedList = self.parent.parent.selectedList
        self.selectedItems = self.parent.parent.GetSelectedItems()
        self.total_items = len(self.selectedItems)
        self.selected_idx = 0
        # changes held till Save, let go by Cancel, close or Esc:
        # {item: dict(fields={name: value}, cover=('chosen'|'remove', ...))}
        self.pending = dict()
        self.lookups = dict()
        # the fields (ItemEditPanel), the footer under them
        self.SetClientSize((ItemEditPanel.GetContentWidth(),
                            ItemEditPanel.GetContentHeight() + self.GetFooterHeight()))
        self.SaveButton = Button(self, label='Save', primary=True)
        self.SaveButton.Bind(wx.EVT_BUTTON, self.OnSave)
        self.CancelButton = Button(self, label='Cancel')
        self.CancelButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.NextButton = Button(self, label='Next')
        self.NextButton.Bind(wx.EVT_BUTTON, self.OnNext)
        self.PrevButton = Button(self, label='Prev')
        self.PrevButton.Bind(wx.EVT_BUTTON, self.OnPrev)
        self.LookUpButton = Button(self, label='Look Up')
        self.LookUpButton.Bind(wx.EVT_BUTTON, self.OnLookUp)
        top = self.PlaceButtons(right=(self.PrevButton, self.NextButton, self.SaveButton,
                                       self.CancelButton),
                                left=(self.LookUpButton,))
        # page number PAD before Prev, on the buttons' middle
        label = f'{int(self.selected_idx + 1)} / {int(self.total_items)}'
        self.PageNumber = StaticText(self, label=label, pos=(
            self.PrevButton.GetPosition().x - DIALOG_PAD - 160, top + 5), size=(160, 20),
            style=wx.ALIGN_RIGHT)
        self.LookUpButton.SetToolTip(wx.ToolTip(
            'Find artist, title, album and genre on Discogs, Last.fm and AcoustID.'
            '\nThe keys are set in Preference > Web Services.'))
        self.ItemEditPanel = ItemEditPanel(self)
        self.SetPage()
        self.ItemEditPanel.Show(True)
        for window in (self, self.PageNumber):
            window.Bind(wx.EVT_RIGHT_UP, lambda e, window=window: self.ShowMenu(window))

    def ShowMenu(self, window):
        # the editor's menu where asked: the cover's items, Look Up
        menu = wx.Menu()
        self.ItemEditPanel.Cover.AppendMenu(menu)
        menu.AppendSeparator()
        look = menu.Append(wx.ID_ANY, 'Look Up...')
        look.Enable(self.LookUpButton.IsEnabled())
        menu.Bind(wx.EVT_MENU, self.OnLookUp, look)
        cover = menu.Append(wx.ID_ANY, 'Look Up Cover...')
        menu.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(self.OnLookUpCover), cover)
        uikit.mark_menu_checks(menu)
        window.PopupMenu(menu)
        menu.Destroy()

    def GetFieldText(self, label):
        return self.ItemEditPanel.TextCtrls[self.ItemEditPanel.labels.index(label)]

    def OnLookUp(self, event):
        keys = dict(zip(webinfo.PREFERENCE_KEYS, GetPreferences(webinfo.PREFERENCE_KEYS)))
        if not any(keys.values()):
            show_notice(self, 'Look Up', 'Set a key in Preference > Web Services first.')
            return
        itemIdx = self.selectedItems[self.selected_idx]
        path = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
        artist = self.GetFieldText('Artist').GetValue().strip()
        title = self.GetFieldText('Title').GetValue().strip()
        self.LookUpButton.Disable()
        self.LookUpButton.SetLabel('Looking...')
        thread = threading.Thread(target=self.LookUpThread,
                                  args=(self.selected_idx, path, artist, title, keys))
        thread.daemon = True
        thread.start()

    def OnLookUpCover(self):
        # the cover chosen there put in the cover field, written with the page
        itemIdx = self.selectedItems[self.selected_idx]
        value = self.parent.parent.GetItemValueByColumnKey
        path = value(itemIdx, 'path')
        track = dict(path=path, mdx=value(itemIdx, 'mdx'),
                     artist=self.GetFieldText('Artist').GetValue().strip(),
                     title=self.GetFieldText('Title').GetValue().strip(),
                     label=os.path.basename(path))
        selected_idx = self.selected_idx

        def use(results):
            if self and selected_idx == self.selected_idx and len(results) > 0:
                self.ItemEditPanel.Cover.SetChosen(results[0][2])
        look_up_cover_for(self.parent.parent, [track], use=use, parent=self)

    def LookUpThread(self, selected_idx, path, artist, title, keys):
        try:
            candidates, errors = webinfo.lookup(path, artist, title, keys, webinfo.Cache())
        except Exception as error:
            candidates, errors = list(), [str(error)]
        wx.CallAfter(self.OnLookedUp, selected_idx, candidates, errors)

    def OnLookedUp(self, selected_idx, candidates, errors):
        if not self:
            return
        self.LookUpButton.SetLabel('Look Up')
        self.LookUpButton.Enable()
        if selected_idx != self.selected_idx:
            return
        itemIdx = self.selectedItems[self.selected_idx]
        length = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'duration')
        # rows kept: each field's values to choose from
        self.lookups[itemIdx] = candidates
        self.UpdateMarks()
        dialog = WebInfoBox(self, candidates, errors, length, use=self.UseLookUpValue)
        answer = dialog.ShowModal()
        SetPreference('lookup_size', tuple(dialog.GetClientSize()))
        if answer == wx.ID_OK and dialog.selected is not None:
            chosen = candidates[dialog.selected]
            # only the ticked fields
            for label in self.LOOKUP_FIELDS:
                if dialog.apply[label.lower()] and chosen[label.lower()]:
                    self.GetFieldText(label).SetValue(chosen[label.lower()])
            if dialog.apply['cover'] and chosen['image']:
                self.UseLookUpValue('Cover', dialog.GetCoverValue(chosen['image']))
        dialog.Destroy()

    # the fields Look Up fills (its rows' keys, in lower case)
    LOOKUP_FIELDS = ('Artist', 'Title', 'Album', 'Genre')

    def UseLookUpValue(self, label, value):
        # one value of a Look Up row in its field, held as a change
        if label != 'Cover':
            self.GetFieldText(label).SetValue(value)
            return
        if isinstance(value, tuple):
            # edited there: the picture, its edit and what it made
            self.ItemEditPanel.Cover.SetEdit(*value)
            return
        self.ItemEditPanel.Cover.SetNote('Loading...')
        thread = threading.Thread(target=self.FetchCoverThread,
                                  args=(self.selected_idx, value))
        thread.daemon = True
        thread.start()

    def FetchCoverThread(self, selected_idx, url):
        try:
            data, note = webinfo.fetch_image(url), ''
        except Exception as error:
            data, note = None, str(error)
        wx.CallAfter(self.OnCoverFetched, selected_idx, data, note)

    def OnCoverFetched(self, selected_idx, data, note):
        if not self or selected_idx != self.selected_idx:
            return
        if data:
            self.ItemEditPanel.Cover.SetChosen(data)
        else:
            self.ItemEditPanel.Cover.SetNote(note or 'No cover')

    def KeepModified(self, itemIdx, before):
        # restore the modified and accessed dates after writing (KEEP)
        if before is None or not self.ItemEditPanel.keep_modified:
            return
        path = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
        try:
            if os.stat(path).st_mtime_ns != before.st_mtime_ns:
                with mfeats.tags_written(path):
                    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        except OSError as error:
            show_notice(self, 'Modified', f'The modified date was not kept.\n{error}')

    def OnAutoSave(self, event):
        if event.IsChecked():
            self.auto_save = True
            self.SaveButton.Disable()
            SetPreference('item_editor_auto_save', True)
        else:
            self.auto_save = False
            self.SaveButton.Enable()
            SetPreference('item_editor_auto_save', False)
        self.parent.parent.parent.parent.item_editor_auto_save = self.auto_save

    def AutoSeButtonState(self):
        if self.selected_idx == 0:
            self.PrevButton.Disable()
        else:
            self.PrevButton.Enable()
        if self.selected_idx == self.total_items - 1:
            self.NextButton.Disable()
        else:
            self.NextButton.Enable()

    def CommitText(self):
        itemIdx = self.selectedItems[self.selected_idx]
        if self.columnIdx == self.parent.parent.GetColumnKeyToIdx('filename'):
            self.RenameFile()
        if self.parent.parent.IsID3TAGColumnByColumnIdx(self.columnIdx):
            self.RenameID3TAG()
        newValue = self.GetValue()
        columnKey = self.parent.parent.GetColumnIdxToKey(self.columnIdx)
        if columnKey == 'tempo':
            try:
                newValue = float(newValue)
                newValue = f'{0.1 * round(newValue * 10):05.1f}'
            except Exception:
                newValue = ''
        self.parent.parent.SetItemValueByColumnIdx(itemIdx, self.columnIdx, newValue)

    def RenameID3TAG(self):
        newValue = self.GetValue()
        resp = self.parent.parent.RenameID3TAGByColumnItemIdx(
            self.columnIdx, self.selectedItems[self.selected_idx], newValue)
        if resp is False:
            self.SetValue(self.restore_value)

    def RenameFile(self):
        itemIdx = self.selectedItems[self.selected_idx]
        newFilename = self.GetValue()
        newFilename = self.parent.parent.LimitFileName(newFilename)
        oldPath = self.parent.parent.GetItemValueByColumnKey(itemIdx, 'path')
        pathBase = os.path.sep.join(oldPath.split(os.path.sep)[:-1])
        fileType = os.path.splitext(oldPath)[-1]
        newPath = os.path.sep.join([pathBase, newFilename])
        newPath = ''.join([newPath, fileType])
        resp = self.parent.parent.RenameFileByItemIdx(itemIdx, newPath)
        if resp is False:
            self.SetValue(self.restore_value)

    # held

    def StashPage(self):
        # the page's changes (its fields and cover against the file's) held for Save
        panel = self.ItemEditPanel
        itemIdx = self.selectedItems[self.selected_idx]
        fields = dict()
        for i, label in enumerate(panel.labels):
            if label in panel.disables:
                continue
            value = panel.TextCtrls[i].GetValue()
            if value != panel.restore_value[i]:
                fields[label] = value
        cover = panel.Cover
        change = ('remove', None) if cover.remove else\
            ('chosen', cover.chosen) if cover.chosen is not None else None
        if fields or change is not None:
            self.pending[itemIdx] = dict(fields=fields, cover=change)
        else:
            self.pending.pop(itemIdx, None)

    def UpdateMarks(self):
        # changed field: accent name and a left bar; a mark when Look Up has values
        panel = getattr(self, 'ItemEditPanel', None)
        # not while a page loads: its fields are set one at a time
        if panel is None or getattr(self, 'loading', False):
            return
        ui = macroboxstyle.current().UI
        for i, label in enumerate(panel.labels):
            if label in panel.disables:
                continue
            text = panel.TextCtrls[i]
            changed = text.GetValue() != panel.restore_value[i]
            text.frame.SetChanged(changed)
            name = panel.StaticTexts[i]
            colour = wx.Colour(ui.ACCENT if changed else ui.BAR_TEXT_DIM)
            if name.GetForegroundColour() != colour:
                name.SetForegroundColour(colour)
                name.Refresh()
            text.frame.SetMark((lambda i=i: self.ShowFieldMenu(i)) if self.GetPicks(label)
                               else None)
        self.StashPage()
        label = f'{int(self.selected_idx + 1)} / {int(self.total_items)}'
        if self.total_items > 1 and self.pending:
            label = f'{len(self.pending)} changed   {label}'
        if self.PageNumber.GetLabelText() != label:
            size = self.PageNumber.GetSize()
            self.PageNumber.SetLabelText(label)
            self.PageNumber.SetInitialSize(size)

    def GetPicks(self, label):
        # [(value, its sources)] Look Up found for this field of the page's track
        if label not in self.LOOKUP_FIELDS:
            return []
        rows = self.lookups.get(self.selectedItems[self.selected_idx]) or []
        picks = dict()
        for row in rows:
            value = (row.get(label.lower()) or '').strip()
            if value:
                sources = picks.setdefault(value, [])
                if row['source'] not in sources:
                    sources.append(row['source'])
        return list(picks.items())

    def ShowFieldMenu(self, i):
        # field menu: Look Up values, Revert, Apply to All, edit items
        panel = self.ItemEditPanel
        label, text = panel.labels[i], panel.TextCtrls[i]
        menu = wx.Menu()

        def add(name, action, enable=True):
            item = menu.Append(wx.ID_ANY, name)
            item.Enable(enable)
            menu.Bind(wx.EVT_MENU, lambda e: action(), item)

        picks = self.GetPicks(label)
        for value, sources in picks:
            shown = value if len(value) <= 60 else value[:57] + '...'
            add(f'{shown.replace("&", "&&")}\t{", ".join(sources)}',
                lambda value=value: text.SetValue(value))
        if picks:
            menu.AppendSeparator()
        original = panel.restore_value[i]
        add('Revert', lambda: text.SetValue(original), text.GetValue() != original)
        if self.total_items > 1 and label != 'Filename':
            add(f'Apply to All {int(self.total_items)} Tracks',
                lambda: self.ApplyToAll(label, text.GetValue()))
        menu.AppendSeparator()
        add('Cut', text.Cut, text.CanCut())
        add('Copy', text.Copy, text.CanCopy())
        add('Paste', text.Paste, text.CanPaste())
        add('Select All', text.SelectAll)
        uikit.mark_menu_checks(menu)
        text.frame.PopupMenu(menu)
        menu.Destroy()

    def ApplyToAll(self, label, value):
        # this value for every track, held as each page's change
        listbox = self.parent.parent
        current = self.selectedItems[self.selected_idx]
        for itemIdx in self.selectedItems:
            if itemIdx == current:
                continue
            change = self.pending.setdefault(itemIdx, dict(fields=dict(), cover=None))
            own = listbox.GetItemValueByColumnKey(itemIdx, label.lower())
            own = str(own) if isinstance(own, (int, float)) else own
            if value == own:
                change['fields'].pop(label, None)
            else:
                change['fields'][label] = value
            if not change['fields'] and change['cover'] is None:
                self.pending.pop(itemIdx, None)
        self.UpdateMarks()

    # saved

    def OnSave(self, event):
        # every track's changes written, then closed
        self.StashPage()
        for itemIdx in [v for v in self.selectedItems if v in self.pending]:
            self.WriteItem(itemIdx, self.pending.pop(itemIdx))
        self.parent.parent.List.DirectDraw()
        self.EndModal(wx.ID_OK)

    def WriteItem(self, itemIdx, change):
        # rename first, then tags and cover; the playing song paused meanwhile
        listbox = self.parent.parent
        playbox = listbox.parent.PlayBox
        path = listbox.GetItemValueByColumnKey(itemIdx, 'path')
        try:
            before = os.stat(path)
        except OSError:
            before = None
        playing = playbox.IsPlaying() and path == playbox.GetPlayingItemInfo('path')
        if playing:
            playbox.OnPause()
        renamed = None
        for label in self.ItemEditPanel.labels:
            if label not in change['fields']:
                continue
            value = change['fields'][label]
            columnIdx = listbox.GetColumnKeyToIdx(label.lower())
            if label == 'Filename':
                name = listbox.LimitFileName(value)
                base = os.path.sep.join(path.split(os.path.sep)[:-1])
                newPath = os.path.sep.join([base, name]) + os.path.splitext(path)[-1]
                if newPath != path and listbox.RenameFileByItemIdx(itemIdx, newPath) is not False:
                    renamed = newPath
            elif listbox.IsID3TAGColumnByColumnIdx(columnIdx):
                if label == 'Tempo':
                    try:
                        value = f'{0.1 * round(float(value) * 10):05.1f}'
                    except Exception:
                        value = ''
                listbox.RenameID3TAGByColumnItemIdx(columnIdx, itemIdx, value)
        if change['cover'] is not None:
            self.WriteCover(itemIdx, *change['cover'])
        self.KeepModified(itemIdx, before)
        if playing:
            if renamed:
                playbox.cue.path = renamed
                playbox.cue.mdx = playbox.GetMDX(renamed)
                playbox.cue.item = MakeMusicFileItem(renamed, 0, ListBoxColumn())
            playbox.OnResume()

    def WriteCover(self, itemIdx, kind, data):
        # write or remove the cover in the tags, then reload list and player
        listbox = self.parent.parent
        path = listbox.GetItemValueByColumnKey(itemIdx, 'path')
        try:
            if kind == 'remove':
                listimages.remove_cover(path)
            else:
                listimages.write_cover(path, data)
        except Exception as error:
            show_notice(self, 'Cover', f'The cover was not saved.\n{error}')
            return
        images = getattr(self.parent, 'images', None)
        if images is not None:
            images.Forget(listbox.GetItemValueByColumnKey(itemIdx, 'mdx'), 'cover')
        playbox = listbox.parent.PlayBox
        if playbox.cue.path == path:
            playbox.Apic.HandleApicChange(forced=True)

    # paged

    def OnPrev(self, event):
        if self.selected_idx > 0:
            self.StashPage()
            self.selected_idx -= 1
            self.SetPage()

    def OnNext(self, event):
        if self.selected_idx < self.total_items - 1:
            self.StashPage()
            self.selected_idx += 1
            self.SetPage()

    def SetPage(self):
        # the track's fields as its file has them, its held changes over them
        self.Freeze()
        self.loading = True
        self.AutoSeButtonState()
        itemIdx = self.selectedItems[self.selected_idx]
        panel = self.ItemEditPanel
        panel.SetPage(itemIdx)
        change = self.pending.get(itemIdx)
        if change is not None:
            for label, value in change['fields'].items():
                panel.TextCtrls[panel.labels.index(label)].SetValue(value)
            if change['cover'] is not None:
                kind, data = change['cover']
                if kind == 'remove':
                    panel.Cover.SetRemove()
                else:
                    panel.Cover.SetChosen(data)
        self.loading = False
        self.UpdateMarks()
        self.Thaw()

    def OnClose(self, event):
        # Cancel, close or Esc: changes let go, asked first if any
        self.StashPage()
        if self.pending and not confirm_discard_edits(self, len(self.pending)):
            return
        self.pending.clear()
        self.EndModal(wx.ID_CANCEL)


class DiscardEditsBox(ConfirmDialogBox):

    # discard the editor's changes, or go back to them
    def __init__(self, parent, count, answer):
        ConfirmDialogBox.__init__(self, parent)
        self.answer = answer
        self.SetTitle('Discard Changes')
        self.ApplyButton.SetLabelText('Discard')
        self.CloseButton.SetLabelText('Keep Editing')
        self.Message.Hide()
        tracks = 'this track' if count == 1 else f'{int(count)} tracks'
        self.Text = wx.StaticText(self, label=f'Discard the changes to {tracks}?\nNothing has been '
                                  'written to the files.',
                                  style=wx.ALIGN_CENTER_HORIZONTAL | wx.ST_NO_AUTORESIZE)
        self.Text.SetForegroundColour(macroboxstyle.current().UI.TEXT)
        self.Text.SetFont(uikit.get_font(uikit.BODY))
        self.SetClientSize((340, DIALOG_PAD * 2 + 40 + self.GetFooterHeight()))
        self.OnSize(None)

    def OnSize(self, event):
        ConfirmDialogBox.OnSize(self, event)
        if getattr(self, 'Text', None) is not None:
            width, height = self.GetClientSize()
            self.Text.SetRect((DIALOG_PAD, DIALOG_PAD, width - DIALOG_PAD * 2, 40))

    def OnApply(self, event):
        self.answer.append(True)
        self.OnClose(event)


def confirm_discard_edits(parent, count):
    # True when the editor's changes are to be let go (asked over it)
    answer = []
    box = DiscardEditsBox(parent, count, answer)
    x, y, w, h = parent.GetRect()
    bw, bh = box.GetSize()
    box.SetPosition((x + (w - bw) // 2, y + (h - bh) // 2))
    box.ShowModal()
    return bool(answer)


class LookUpList(wx.Window):

    '''columns: [(title, width, flexible)]; cells(row); picture(row, column)'''

    HEADER = 26
    ROW = 26
    PAD = 8
    PICTURE_GAP = 6
    BAR = 3
    SCROLL = 6
    # a column's least width when its edge is dragged; the edge's grip each side of it
    LEAST = 40
    GRIP = 4

    def __init__(self, parent, columns, cells, picture=None):
        wx.Window.__init__(self, parent, style=wx.WANTS_CHARS | wx.BORDER_NONE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.columns = columns
        self.cells = cells
        self.picture = picture
        self.count = 0
        self.selected = -1
        self.offset = 0
        self.sort = None
        self.drag = None
        self.widths = []
        self.hidden = set()
        # dragged widths per column or None; the drag: (column, x, widths)
        self.custom = None
        self.resize = None
        # horizontal scroll when wider than the list; bar drag: (x, hoffset)
        self.hoffset = 0
        self.hdrag = None
        # told: on_select(row), on_activate(row), on_menu(row, column), on_sort(column),
        # on_columns(hidden), on_widths(custom)
        self.on_select = self.on_activate = self.on_menu = self.on_sort = None
        self.on_columns = self.on_widths = None
        frame = wx.GetApp().GetTopWindow()
        listbox = getattr(getattr(frame, 'MainPanel', None), 'ListBox', None)
        self.font = getattr(listbox, 'font', None) or self.GetFont()
        self.tips = uikit.CutTips(self)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda e: self.tips.Update())
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnCaptureLost)
        self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    def SetCount(self, count):
        self.count = count
        self.selected = min(self.selected, count - 1)
        self.Scroll(self.offset)

    def GetSelected(self):
        return self.selected

    def Select(self, row, tell=False):
        if not 0 <= row < self.count:
            return
        self.selected = row
        self.EnsureVisible(row)
        self.Refresh(False)
        if tell and self.on_select:
            self.on_select(row)

    def SetSort(self, column, ascending):
        self.sort = (column, ascending)
        self.Refresh(False)

    # the horizontal bar's strip below the rows
    HBAR = 12

    def HasHBar(self):
        return sum(self.widths) > self.GetClientSize().width

    def GetView(self):
        strip = self.HBAR if self.HasHBar() else 0
        return max(self.GetClientSize().height - self.HEADER - strip, 0)

    def Scroll(self, offset):
        most = max(self.count * self.ROW - self.GetView(), 0)
        self.offset = int(min(max(offset, 0), most))
        self.Refresh(False)

    def EnsureVisible(self, row):
        top, bottom = row * self.ROW, (row + 1) * self.ROW
        if top < self.offset:
            self.Scroll(top)
        elif bottom > self.offset + self.GetView():
            self.Scroll(bottom - self.GetView())

    def GetWidths(self, width):
        shown = [k not in self.hidden for k in range(len(self.columns))]
        if self.custom is not None:
            widths = [w if on else 0 for w, on in zip(self.custom, shown)]
            last = max((k for k, on in enumerate(shown) if on), default=None)
            if last is not None:
                widths[last] = max(width - sum(widths) + widths[last], self.LEAST)
            return widths
        fixed = sum(w for (_, w, flexible), on in zip(self.columns, shown) if on and not flexible)
        shares = sum(w for (_, w, flexible), on in zip(self.columns, shown) if on and flexible)
        room = max(width - fixed, 0)
        # flexible columns never under 0.6 of their width nor LEAST
        widths = [0 if not on else max(int(room * w / shares), int(w * 0.6), self.LEAST)
                  if flexible else w for (_, w, flexible), on in zip(self.columns, shown)]
        last = max((k for k, on in enumerate(shown) if on), default=None)
        if last is not None and sum(widths) < width:
            widths[last] += width - sum(widths)
        return widths

    def ScrollH(self, hoffset):
        most = max(sum(self.widths) - self.GetClientSize().width, 0)
        self.hoffset = int(min(max(hoffset, 0), most))
        self.Refresh(False)

    def GetHThumb(self):
        # in its strip, clear of the sides and of the upright bar's corner
        w, h = self.GetClientSize()
        total = sum(self.widths)
        if total <= w or w <= 0:
            return None
        track = w - 4 - (self.SCROLL + 4 if self.count * self.ROW > self.GetView() else 0)
        width = max(int(track * w / total), 24)
        left = 2 + int((track - width) * self.hoffset / (total - w))
        return wx.Rect(left, h - self.HBAR + (self.HBAR - self.SCROLL) // 2, width,
                       self.SCROLL)

    def SetHidden(self, hidden):
        hidden = set(k for k in hidden if 0 <= k < len(self.columns))
        if len(hidden) < len(self.columns):
            self.hidden = hidden
            self.Refresh(False)

    def ShowColumnMenu(self):
        menu = wx.Menu()
        for k, (title, _, _) in enumerate(self.columns):
            item = menu.AppendCheckItem(wx.ID_ANY, title)
            item.Check(k not in self.hidden)
            item.Enable(k in self.hidden or len(self.hidden) < len(self.columns) - 1)
            menu.Bind(wx.EVT_MENU, lambda e, k=k: self.ToggleColumn(k), item)
        menu.AppendSeparator()
        item = menu.Append(wx.ID_ANY, 'Reset column widths')
        item.Enable(self.custom is not None)
        menu.Bind(wx.EVT_MENU, lambda e: self.ResetWidths(), item)
        uikit.mark_menu_checks(menu)
        self.PopupMenu(menu)
        menu.Destroy()

    def ToggleColumn(self, k):
        self.SetHidden(self.hidden ^ {k})
        if self.on_columns:
            self.on_columns(set(self.hidden))

    def SetCustomWidths(self, custom):
        # None, or a width for every column
        if custom is not None and len(custom) != len(self.columns):
            custom = None
        self.custom = custom
        self.Refresh(False)

    def ResetWidths(self):
        self.SetCustomWidths(None)
        if self.on_widths:
            self.on_widths(None)

    def GetEdge(self, x):
        # the column whose right edge is under x (the last shown one has none), or None
        last = max((k for k, w in enumerate(self.widths) if w), default=-1)
        x += self.hoffset
        right = 0
        for k, w in enumerate(self.widths):
            right += w
            if w and k < last and abs(x - right) <= self.GRIP:
                return k
        return None

    def HitTest(self, point):
        # (row or -1, column or -1); -2 for the header row
        x, y = point
        x += self.hoffset
        column, left = -1, 0
        for k, w in enumerate(self.widths):
            if left <= x < left + w:
                column = k
                break
            left += w
        if y < self.HEADER:
            return -2, column
        row = int((y - self.HEADER + self.offset) // self.ROW)
        return (row if 0 <= row < self.count else -1), column

    def GetThumb(self):
        view, total = self.GetView(), self.count * self.ROW
        if total <= view or view <= 0:
            return None
        w, track = self.GetClientSize().width, view - 4
        height = max(int(track * view / total), 24)
        top = self.HEADER + 2 + int((track - height) * self.offset / (total - view))
        return wx.Rect(w - self.SCROLL - 2, top, self.SCROLL, height)

    def OnSize(self, event):
        self.Scroll(self.offset)
        event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        st = macroboxstyle.current().LISTBOX
        w, h = self.GetClientSize()
        self.widths = self.GetWidths(w)
        self.hoffset = int(min(self.hoffset, max(sum(self.widths) - w, 0)))
        dc.SetBackground(wx.Brush(wx.Colour(*st.LIST_BG_COLOR)))
        dc.Clear()
        self.tips.Clear()
        self.DrawRows(dc, st, w, h)
        self.DrawHeader(dc, st, w)
        for thumb in (self.GetThumb(), self.GetHThumb()):
            if thumb is None:
                continue
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(*st.SCROLLBAR_PN_COLOR)))
            dc.DrawRoundedRectangle(thumb, self.SCROLL / 2.0)

    def DrawRows(self, dc, st, w, h):
        ct = st.LIST_BG_CONTRAST
        grounds = [wx.Colour(*[min(max(v + d, 0), 255) for v in st.LIST_BG_COLOR[:3]])
                   for d in (-ct, ct)]
        dc.SetFont(self.font)
        th = dc.GetTextExtent('Ag')[1]
        first = self.offset // self.ROW
        last = min(self.count, (self.offset + self.GetView()) // self.ROW + 1)
        dc.SetClippingRegion(0, self.HEADER, w, self.GetView())
        for row in range(first, last):
            y = self.HEADER + row * self.ROW - self.offset
            selected = row == self.selected
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(wx.Colour(*st.SELECTED_BG_COLOR) if selected
                                 else grounds[row % 2]))
            dc.DrawRectangle(0, y, w, self.ROW)
            if selected:
                dc.SetBrush(wx.Brush(wx.Colour(*st.SELECTED_BAR_COLOR)))
                dc.DrawRectangle(0, y, self.BAR, self.ROW)
            dc.SetTextForeground(wx.Colour(*(st.SELECTED_FG_COLOR if selected
                                             else st.LIST_FG_COLOR)))
            x = -self.hoffset
            for column, (text, width) in enumerate(zip(self.cells(row), self.widths)):
                if not width:
                    continue
                bitmap = self.picture(row, column) if self.picture else None
                left = x + self.PAD
                if bitmap is not None and bitmap.IsOk():
                    dc.DrawBitmap(bitmap, left, y + (self.ROW - bitmap.GetHeight()) // 2)
                    left += bitmap.GetWidth() + self.PICTURE_GAP
                if text:
                    shown = wx.Control.Ellipsize(str(text), dc, wx.ELLIPSIZE_END,
                                                 max(x + width - self.PAD - left, 1))
                    dc.DrawText(shown, left, y + (self.ROW - th) // 2)
                    # the row's part in the view
                    top = max(y, self.HEADER)
                    bottom = min(y + self.ROW, self.HEADER + self.GetView())
                    if bottom > top:
                        self.tips.Add((x, top, width, bottom - top), text, shown)
                x += width
        dc.DestroyClippingRegion()

    def DrawHeader(self, dc, st, w):
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(wx.Colour(*st.HEADER_BG_COLOR)))
        dc.DrawRectangle(0, 0, w, self.HEADER)
        font = uikit.get_font(10)
        dc.SetFont(font)
        top = int(round(uikit.get_caps_top(font, 0, self.HEADER)))
        dim = [int(v * 0.62 + g * 0.38) for v, g in zip(st.HEADER_FG_COLOR, st.HEADER_BG_COLOR)]
        dc.SetTextForeground(wx.Colour(*dim))
        dc.SetPen(wx.Pen(wx.Colour(*st.HEADER_PN_COLOR), 1))
        dc.DrawLine(0, self.HEADER - 1, w, self.HEADER - 1)
        x = -self.hoffset
        last = max((k for k, w in enumerate(self.widths) if w), default=-1)
        for column, ((title, _, _), width) in enumerate(zip(self.columns, self.widths)):
            if not width:
                continue
            sorted_here = self.sort is not None and self.sort[0] == column
            room = width - self.PAD * 2 - (12 if sorted_here else 0)
            shown = wx.Control.Ellipsize(title.upper(), dc, wx.ELLIPSIZE_END, max(room, 1))
            dc.DrawText(shown, x + self.PAD, top)
            self.tips.Add((x, 0, width, self.HEADER), title.upper(), shown)
            if sorted_here:
                cx, cy, size = x + width - self.PAD - 3, self.HEADER // 2, 3
                down = [(cx - size, cy - 1), (cx + size, cy - 1), (cx, cy + 2)]
                up = [(cx - size, cy + 2), (cx + size, cy + 2), (cx, cy - 1)]
                points = up if self.sort[1] else down
                dc.SetBrush(wx.Brush(wx.Colour(*st.HEADER_FG_COLOR)))
                dc.SetPen(wx.Pen(wx.Colour(*st.HEADER_FG_COLOR), 1))
                dc.DrawPolygon(points)
                dc.SetPen(wx.Pen(wx.Colour(*st.HEADER_PN_COLOR), 1))
            x += width
            if column < last:
                dc.DrawLine(x, 5, x, self.HEADER - 5)

    def OnLeftDown(self, event):
        self.SetFocus()
        hthumb = self.GetHThumb()
        if hthumb is not None and event.GetY() >= hthumb.y - 2:
            if hthumb.Contains(event.GetPosition()):
                self.hdrag = (event.GetX(), self.hoffset)
                self.CaptureMouse()
            else:
                w = self.GetClientSize().width
                self.ScrollH(self.hoffset + (w if event.GetX() > hthumb.x else -w))
            return
        thumb = self.GetThumb()
        if thumb is not None and event.GetX() >= thumb.x - 2:
            if thumb.Contains(event.GetPosition()):
                self.drag = (event.GetY(), self.offset)
                self.CaptureMouse()
            else:
                page = self.GetView() if event.GetY() > thumb.y else -self.GetView()
                self.Scroll(self.offset + page)
            return
        row, column = self.HitTest(event.GetPosition())
        edge = self.GetEdge(event.GetX()) if row == -2 else None
        if edge is not None:
            self.resize = (edge, event.GetX(), list(self.widths))
            self.CaptureMouse()
        elif row == -2:
            if column >= 0 and self.on_sort:
                self.on_sort(column)
        elif row >= 0:
            self.Select(row, tell=True)

    def OnLeftUp(self, event):
        if self.hdrag is not None:
            self.hdrag = None
            if self.HasCapture():
                self.ReleaseMouse()
        if self.resize is not None:
            self.resize = None
            if self.HasCapture():
                self.ReleaseMouse()
            if self.on_widths:
                self.on_widths(list(self.custom))
        if self.drag is not None:
            self.drag = None
            if self.HasCapture():
                self.ReleaseMouse()

    def DragEdge(self, x):
        # widen from the next columns (nearest first), narrow into the next
        column, start, widths = self.resize
        widths = list(widths)
        after = [k for k in range(column + 1, len(widths)) if widths[k]]
        spare = sum(widths[k] - self.LEAST for k in after if widths[k] > self.LEAST)
        moved = int(min(max(x - start, self.LEAST - widths[column]), spare))
        widths[column] += moved
        if moved < 0:
            widths[after[0]] -= moved
        for k in after:
            if moved <= 0:
                break
            given = min(max(widths[k] - self.LEAST, 0), moved)
            widths[k] -= given
            moved -= given
        custom = list(self.custom) if self.custom is not None\
            else [w for _, w, _ in self.columns]
        for k, w in enumerate(widths):
            if w:
                custom[k] = w
        self.custom = custom
        self.Refresh(False)

    def OnMotion(self, event):
        if self.hdrag is not None and event.LeftIsDown():
            thumb = self.GetHThumb()
            if thumb is not None:
                x, hoffset = self.hdrag
                w, total = self.GetClientSize().width, sum(self.widths)
                self.ScrollH(hoffset + (event.GetX() - x) * (total - w) / max(w - thumb.width, 1))
            return
        if self.resize is not None and event.LeftIsDown():
            self.DragEdge(event.GetX())
            return
        if self.drag is None:
            over = event.GetY() < self.HEADER and self.GetEdge(event.GetX()) is not None
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZEWE if over else wx.CURSOR_ARROW))
            self.tips.Update(None if over else event.GetPosition())
        if self.drag is None or not event.LeftIsDown():
            return
        thumb = self.GetThumb()
        if thumb is None:
            return
        y, offset = self.drag
        total, view = self.count * self.ROW, self.GetView()
        moved = (event.GetY() - y) * (total - view) / max(view - 4 - thumb.height, 1)
        self.Scroll(offset + moved)

    def OnCaptureLost(self, event):
        self.drag = None
        self.resize = None
        self.hdrag = None

    def OnLeftDClick(self, event):
        row, _ = self.HitTest(event.GetPosition())
        if row >= 0 and self.on_activate:
            self.Select(row)
            self.on_activate(row)

    def OnRightDown(self, event):
        self.SetFocus()
        row, column = self.HitTest(event.GetPosition())
        if row == -2:
            self.ShowColumnMenu()
        elif row >= 0:
            self.Select(row, tell=True)
            if self.on_menu:
                self.on_menu(row, column)

    def OnWheel(self, event):
        # sideways with a tilted wheel or with Shift
        step = event.GetWheelRotation() / 120.0
        if event.GetWheelAxis() == wx.MOUSE_WHEEL_HORIZONTAL:
            self.ScrollH(self.hoffset + step * 60)
        elif event.ShiftDown():
            self.ScrollH(self.hoffset - step * 60)
        else:
            self.Scroll(self.offset - step * 3 * self.ROW)

    TRACK_MOVES = {'previous_track': -1, 'next_track': 1}

    def GetTrackMove(self, event):
        frame = wx.GetApp().GetTopWindow()
        if not hasattr(frame, 'GetNameSpaceByRawKeyFlag'):
            return None
        namespace = frame.GetNameSpaceByRawKeyFlag(
            event.GetRawKeyFlags(), event.CmdDown() or event.ControlDown(), event.ShiftDown())
        return self.TRACK_MOVES.get(namespace)

    def OnKeyDown(self, event):
        key = event.GetKeyCode()
        page = max(self.GetView() // self.ROW - 1, 1)
        moves = {wx.WXK_UP: -1, wx.WXK_DOWN: 1, wx.WXK_PAGEUP: -page, wx.WXK_PAGEDOWN: page}
        track = self.GetTrackMove(event)
        if track is not None:
            self.Select(min(max(self.selected + track, 0), self.count - 1), tell=True)
        elif key in moves:
            self.Select(min(max(self.selected + moves[key], 0), self.count - 1), tell=True)
        elif key == wx.WXK_HOME:
            self.Select(0, tell=True)
        elif key == wx.WXK_END:
            self.Select(self.count - 1, tell=True)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if self.selected >= 0 and self.on_activate:
                self.on_activate(self.selected)
        else:
            event.Skip()


class WebInfoBox(DialogBox):

    COVER = 200

    def __init__(self, parent, candidates, errors, length='', use=None):
        # resizable by its edges, size kept (lookup_size)
        DialogBox.__init__(self, parent, size=(1150, 340), style=wx.RESIZE_BORDER)
        self.built = False
        # use(field, value): one cell's value put in the editor's field (its menu)
        self.use = use
        # not composited (WS_EX_COMPOSITED): Windows' list repaints endlessly
        self.SetDoubleBuffered(False)
        title = f'Look Up: {len(candidates)} found'
        if length:
            title += f', this file {length}'
        self.SetTitle(title)
        self.candidates = candidates
        self.selected = None
        # every row's cover fetched in turn, the chosen row first, by address
        self.covers = dict()
        self.cover_first = 0
        self.closing = False
        # by address: the pictures, the edits made here and what they make
        self.datas = dict()
        self.edits = dict()
        self.edited = dict()
        self.shown_url = None
        # as tall as the cover and its note
        self.SetClientSize((self.GetClientSize().width, DIALOG_PAD + self.COVER + DIALOG_GAP
                            + 18 + DIALOG_PAD + self.GetFooterHeight()))
        # no smaller than made, but for a narrower list
        least = self.GetClientSize()
        self.SetMinClientSize((least.width - 300, least.height))
        kept = GetPreference('lookup_size')
        if isinstance(kept, tuple) and len(kept) == 2:
            self.SetClientSize((max(kept[0], least.width - 300), max(kept[1], least.height)))
        # Cover: none -, fetching ..., failed Failed
        # Cover as wide as a size and ratio text
        columns = (('Source', 72, False), ('Cover', 160, False), ('Artist', 120, True),
                   ('Title', 130, True), ('Album', 110, True), ('Release', 170, True),
                   ('Genre', 90, False), ('Length', 64, False), ('Year', 62, False),
                   ('Score', 64, False))
        self.List = LookUpList(self, columns, self.GetRowCells, self.GetRowPicture)
        self.thumbs = dict()
        # shown order as indexes into candidates; header click sorts, again reverses
        self.order = list(range(len(candidates)))
        self.sort_column = None
        self.sort_ascending = True
        # Cover text by address; picture sizes for sorting
        self.cover_cells = dict()
        self.cover_sizes = dict()
        self.List.SetCount(len(candidates))
        self.List.on_sort = self.OnColumnClick
        self.List.on_activate = lambda row: self.OnApply(None)
        self.List.on_menu = self.OnRowMenu
        self.List.on_select = self.OnSelected
        titles = [title for title, _, _ in columns]
        hidden = GetPreference('lookup_hidden_columns') or []
        self.List.SetHidden([titles.index(v) for v in hidden if v in titles])
        self.List.on_columns = lambda hidden: SetPreference(
            'lookup_hidden_columns', [titles[k] for k in sorted(hidden)])
        # the widths its edges were dragged to, kept by title for the next Look Up
        kept = GetPreference('lookup_column_widths')
        if isinstance(kept, dict):
            self.List.SetCustomWidths([kept.get(title, w) for title, w, _ in columns])
        self.List.on_widths = lambda custom: SetPreference(
            'lookup_column_widths', None if custom is None else dict(zip(titles, custom)))
        # as every cover: click to edit, the cover items on right-click
        self.Cover = CoverPicture(self, (self.COVER, self.COVER))
        self.Cover.Bind(wx.EVT_LEFT_UP, lambda e: wx.CallAfter(self.DoCoverItem, 'Edit Cover...'))
        self.Cover.Bind(wx.EVT_RIGHT_UP, lambda e: self.OnCoverMenu())
        self.CoverText = StaticText(self, label='', style=wx.ALIGN_CENTER)
        self.ApplyButton = Button(self, label='Apply', primary=True)
        self.ApplyButton.Bind(wx.EVT_BUTTON, self.OnApply)
        self.CancelButton = Button(self, label='Cancel')
        self.CancelButton.Bind(wx.EVT_BUTTON, self.OnCancel)
        self.SetCover(None, '')
        self.Errors = None
        if errors:
            self.Errors = StaticText(self, label=' / '.join(errors), size=(-1, 18))
        self.PageButton = Button(self, label='Open Page')
        self.PageButton.Bind(wx.EVT_BUTTON, lambda e: self.OpenPage(self.GetChosen()))
        self.PageButton.SetToolTip(wx.ToolTip('Open the chosen release on its service'))
        self.YouTubeButton = Button(self, label='YouTube')
        self.YouTubeButton.Bind(wx.EVT_BUTTON, lambda e: self.SearchYouTube(self.GetChosen()))
        self.YouTubeButton.SetToolTip(wx.ToolTip('Look for its artist and title on YouTube'))
        top = self.PlaceButtons(right=(self.PageButton, self.YouTubeButton, self.ApplyButton,
                                       self.CancelButton))
        made = set(self.GetChildren())
        # off until a row is chosen (OnSelected): with nothing found, never on
        self.PageButton.Disable()
        self.YouTubeButton.Disable()
        # fields Apply takes from the row, each on its own, and its cover
        tags = GetPreference('lookup_apply_tags') is not False
        self.apply = dict()
        for key in self.APPLY_KEYS:
            kept = GetPreference(f'lookup_apply_{key}')
            self.apply[key] = (tags if key != 'cover' else True) if kept is None else bool(kept)
        x = DIALOG_PAD
        for key in self.APPLY_KEYS:
            _, used = make_check(self, key.capitalize(), (x, top + 5), self.apply[key],
                                 lambda value, key=key: self.SetApply(key, value))
            x += used + DIALOG_PAD
        # the checks and their names, how far under the buttons' top (on the footer's row)
        self.checks = [(v, v.GetPosition().y - top) for v in self.GetChildren()
                       if v not in made]
        self.built = True
        self.PlaceParts()
        self.candidates_found = bool(candidates)
        if candidates:
            self.List.Select(0, tell=True)
            self.List.SetFocus()
        self.SetApply()
        if any(v['image'] for v in candidates):
            threading.Thread(target=self.FetchCovers, daemon=True).start()

    # Apply's checks, in the list's order
    APPLY_KEYS = ('artist', 'title', 'album', 'genre', 'cover')

    def OnSize(self, event):
        # asked while the dialog is made, before its parts
        if getattr(self, 'built', False):
            self.PlaceParts()
            self.Refresh(False)
        if event is not None:
            event.Skip()

    def PlaceParts(self):
        # the dialogs' spacing: list and cover PAD in and apart
        width, height = self.GetClientSize()
        bottom = self.GetContentBottom()
        rows = DIALOG_ROW + DIALOG_GAP if self.Errors is not None else 0
        cx = width - DIALOG_PAD - self.COVER
        self.List.SetRect((DIALOG_PAD, DIALOG_PAD, cx - DIALOG_PAD * 2,
                           bottom - DIALOG_PAD - rows))
        self.Cover.SetRect((cx, DIALOG_PAD, self.COVER, self.COVER))
        self.CoverText.SetRect((cx, DIALOG_PAD + self.COVER + DIALOG_GAP, self.COVER, 18))
        if self.Errors is not None:
            self.Errors.SetRect((DIALOG_PAD, bottom - DIALOG_ROW + 3, cx - DIALOG_PAD * 2, 18))
        top = self.PlaceButtons(right=(self.PageButton, self.YouTubeButton, self.ApplyButton,
                                       self.CancelButton))
        for window, below in self.checks:
            window.SetPosition((window.GetPosition().x, top + below))

    def GetRowValues(self, k):
        v = self.candidates[k]
        score = '' if v['score'] is None else f'{v["score"]:.2f}'
        cover = self.cover_cells.get(v['image'], '...') if v['image'] else '-'
        return (v['source'], cover, v['artist'], v['title'], v['album'], v['release'],
                v['genre'], webinfo.format_duration(v['duration']), v['year'], score)

    def GetRowCells(self, row):
        return self.GetRowValues(self.order[row])

    def GetRowPicture(self, row, column):
        if column != 1:
            return None
        return self.thumbs.get(self.candidates[self.order[row]]['image'])

    def FillRows(self):
        self.List.Refresh(False)

    def GetSortKey(self, k, column):
        # Length, Year, Score numeric, Cover by size, the rest text; None last
        v = self.candidates[k]
        if column == 7:
            return v['duration'] or None
        if column == 8:
            return int(v['year'][:4]) if v['year'][:4].isdigit() else None
        if column == 9:
            return v['score']
        if column == 1:
            size = self.cover_sizes.get(v['image'])
            return size[0] * size[1] if size else None
        text = self.GetRowValues(k)[column]
        return text.casefold() if text else None

    def OnColumnClick(self, column):
        if column < 0:
            return
        ascending = not self.sort_ascending if column == self.sort_column else True
        self.sort_column, self.sort_ascending = column, ascending
        row = self.List.GetSelected()
        chosen = self.order[row] if row >= 0 else None
        keys = dict((k, self.GetSortKey(k, column)) for k in self.order)
        present = sorted([k for k in self.order if keys[k] is not None], key=keys.get,
                         reverse=not ascending)
        self.order = present + [k for k in self.order if keys[k] is None]
        self.List.SetSort(column, ascending)
        # the chosen row stays chosen where it has moved to
        if chosen is not None:
            self.List.Select(self.order.index(chosen))
        self.FillRows()

    def OnRowMenu(self, idx, column):
        # row menu: values into fields, copy the cell, open its page
        row = self.candidates[self.order[idx]]
        menu = wx.Menu()

        def add(name, action, enable=True):
            item = menu.Append(wx.ID_ANY, name.replace('&', '&&'))
            item.Enable(enable)
            menu.Bind(wx.EVT_MENU, lambda e: action(), item)

        for key in self.APPLY_KEYS:
            value = row['image'] if key == 'cover' else row[key]
            if not value:
                continue
            shown = 'its cover' if key == 'cover' else\
                (value if len(value) <= 50 else value[:47] + '...')
            if key == 'cover':
                value = self.GetCoverValue(value)
                shown = 'its cover, edited' if isinstance(value, tuple) else shown
            add(f'Use {key.capitalize()}: {shown}',
                lambda key=key, value=value: self.use(key.capitalize(), value),
                self.use is not None)
        menu.AppendSeparator()
        cell = self.GetRowCells(idx)[column] if column >= 0 else ''
        shown = cell if len(cell) <= 40 else f'{cell[:37]}...'
        add(f'Copy "{shown}"' if cell else 'Copy',
            lambda: self.CopyText(cell), bool(cell))
        add('Open Source Page', lambda: self.OpenPage(row), bool(row['url']))
        add('Search on YouTube', lambda: self.SearchYouTube(row),
            bool(row['artist'] or row['title']))
        uikit.mark_menu_checks(menu)
        self.List.PopupMenu(menu)
        menu.Destroy()

    def CopyText(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()

    def SetApply(self, key=None, value=None):
        if key is not None:
            self.apply[key] = value
            SetPreference(f'lookup_apply_{key}', value)
        self.ApplyButton.Enable(self.candidates_found and any(self.apply.values()))

    def OnApply(self, event):
        idx = self.List.GetSelected()
        if idx < 0 or not any(self.apply.values()):
            return
        self.selected = self.order[idx]
        self.EndModal(wx.ID_OK)

    def MakeCover(self, data):
        # picture fitted in the cover square, or the ground alone
        image = None
        if data:
            try:
                image = wx.Image(io.BytesIO(data))
            except Exception:
                image = None
        if image is not None and image.IsOk():
            w, h = image.GetSize()
            scale = min(self.COVER / w, self.COVER / h)
            image = image.Scale(max(1, int(w * scale)), max(1, int(h * scale)),
                                wx.IMAGE_QUALITY_HIGH)
            image.Resize((self.COVER, self.COVER),
                         ((self.COVER - image.GetWidth()) // 2,
                          (self.COVER - image.GetHeight()) // 2), *macroboxstyle.current().UI.RAISED_BG)
            return wx.Bitmap(image), (w, h)
        bmp = wx.Bitmap(self.COVER, self.COVER)
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(macroboxstyle.current().UI.RAISED_BG))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)
        return bmp, None

    def MakeThumb(self, data):
        side = LookUpList.ROW - 6
        try:
            image = wx.Image(io.BytesIO(data))
        except Exception:
            return None
        if not image.IsOk():
            return None
        w, h = image.GetSize()
        scale = min(side / w, side / h)
        return wx.Bitmap(image.Scale(max(1, int(w * scale)), max(1, int(h * scale)),
                                     wx.IMAGE_QUALITY_HIGH))

    def SetCover(self, data, label, bitmap=None):
        self.Cover.SetBitmap(bitmap or self.MakeCover(data)[0])
        self.CoverText.SetLabel(label)

    def OnSelected(self, row):
        # its cover at once when fetched, else fetched next
        idx = self.order[row]
        self.cover_first = idx
        self.ShowCover(idx)
        chosen = self.candidates[idx]
        if hasattr(self, 'PageButton'):
            self.PageButton.Enable(bool(chosen['url']))
            self.YouTubeButton.Enable(bool(chosen['artist'] or chosen['title']))

    def GetChosen(self):
        row = self.List.GetSelected()
        return self.candidates[self.order[row]] if row >= 0 else None

    def OpenPage(self, chosen):
        if chosen and chosen['url']:
            webbrowser.open(chosen['url'])

    def GetYouTubeURL(self, chosen):
        words = ' '.join(v for v in (chosen['artist'], chosen['title']) if v)
        return 'https://www.youtube.com/results?search_query=' + urllib.parse.quote_plus(words)

    def SearchYouTube(self, chosen):
        if chosen and (chosen['artist'] or chosen['title']):
            webbrowser.open(self.GetYouTubeURL(chosen))

    def ShowCover(self, idx):
        # idx: the candidate's, not its row's
        url = self.candidates[idx]['image']
        self.shown_url = url
        self.Cover.SetActive(url in self.datas)
        if url in self.edited:
            bitmap, size = self.MakeCover(self.edited[url])
            label = '' if size is None else f'Edited to {format_picture_size(size)}'
            self.SetCover(None, label, bitmap)
        elif not url:
            self.SetCover(None, 'No cover')
        elif url in self.covers:
            bitmap, label = self.covers[url]
            self.SetCover(None, label, bitmap)
        else:
            self.SetCover(None, 'Loading...')

    def FetchCovers(self):
        # covers one at a time, the chosen row first; from disk when cached
        done = set()
        while not self.closing:
            order = [self.cover_first] + list(range(len(self.candidates)))
            todo = [k for k in order if self.candidates[k]['image']
                    and self.candidates[k]['image'] not in done]
            if not todo:
                return
            idx = todo[0]
            url = self.candidates[idx]['image']
            done.add(url)
            try:
                data, label = webinfo.fetch_image(url), ''
            except Exception as error:
                data, label = None, str(error)
            if self.closing:
                return
            wx.CallAfter(self.OnCoverLoaded, url, data, label)

    def OnCoverLoaded(self, url, data, label):
        if not self or self.closing:
            return
        bitmap, size = self.MakeCover(data)
        self.covers[url] = (bitmap, label or (format_picture_size(size) if size else 'Not an image'))
        if size:
            self.datas[url] = data
        # one cover may be several releases'
        self.cover_cells[url] = format_picture_size(size) if size else 'Failed'
        if size:
            self.cover_sizes[url] = size
        if size:
            self.thumbs[url] = self.MakeThumb(data)
        self.FillRows()
        idx = self.List.GetSelected()
        if idx >= 0 and self.candidates[self.order[idx]]['image'] == url:
            self.ShowCover(self.order[idx])

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnClose(self, event):
        self.EndModal(wx.ID_CANCEL)

    # the shared cover items, on the shown row's cover

    def OnCoverMenu(self):
        url = self.shown_url
        menu = wx.Menu()
        shown = self.edited[url] if url in self.edited else self.datas.get(url)
        append_cover_items(menu, shown, url in self.edited, self.DoCoverItem)
        uikit.mark_menu_checks(menu)
        self.Cover.PopupMenu(menu)
        menu.Destroy()

    def DoCoverItem(self, name):
        url = self.shown_url
        if not self or url not in self.datas:
            return
        data = self.datas[url]
        idx = [k for k, c in enumerate(self.candidates) if c['image'] == url][0]
        if name == 'Copy Cover':
            keep_copied_cover(self.edited.get(url, data), get_cover_label(self.candidates[idx]))
            return
        made = None
        if name == 'Undo Cover Change':
            self.edits.pop(url, None)
            self.edited.pop(url, None)
        elif name in COVER_PRESETS:
            edit = preset_cover(data, self.edits.get(url), COVER_PRESETS[name])
            made = None if edit is None else (listimages.edit_cover(data, edit), edit)
        elif name == 'Edit Cover...':
            made = edit_cover_by_hand(self, data, self.edits.get(url))
        if made is not None and made[0] is not None:
            self.edited[url], self.edits[url] = made
        self.ShowCover(idx)

    def GetCoverValue(self, url):
        # the address, or (picture, edit, edited) when edited here
        if url in self.edited:
            return (self.datas[url], self.edits[url], self.edited[url])
        return url

    def Destroy(self):
        # cover fetching ends with it
        self.closing = True
        return DialogBox.Destroy(self)
