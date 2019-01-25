# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import audio
import images
import macroboxstyle
import os
import webbrowser
import wx

from dialogbox import AboutBox
from dialogbox import CheckItemsConsistencyConfirmBox
from dialogbox import DialogBox
from dialogbox import DialogPanel
# from dialogbox import LicenseBox
from dialogbox import UpdateBox
from listbox import FileOpenDialog
from listbox import FileSaveDialog
from macroboxlib import Button
from macroboxlib import CheckBox
from macroboxlib import ComboBox
from macroboxlib import FONT_ITEM
from macroboxlib import GetPreference
from macroboxlib import GetPreferences
from macroboxlib import PRODUCT_ONLINE_HELP_URL
from macroboxlib import SetPreference
from macroboxlib import SetPreferences
from macroboxlib import SpinCtrl
from macroboxlib import StaticText
from macroboxlib import TextCtrl
from operator import itemgetter
from utilities import Struct
# from macroboxlib import *
# from scripteditor import *
# from dialogbox import *
# from menubar import AppearanceBox


# class wxHTML(wx.html.HtmlWindow):
#    def OnLinkClicked(self, link):
#        webbrowser.open(link.GetHref())


# WebLinkEditorPanel

class WebLinkPreset():

    def __init__(self):
        self.default_preset = [
            ('7Digital', 'http://www.7digital.com/search?q=', 'Artist', 'Title'),
            ('Beatport', 'http://www.beatport.com/search?query=', 'Artist', 'Title'),
            ('Bing', 'http://www.bing.com/search?q=', 'Artist', 'Title'),
            ('Discogs', 'http://www.discogs.com/search/?q=', 'Artist', 'Title'),
            ('Google', 'https://www.google.com/?q=#q=', 'Artist', 'Title'),
            ('LastFM', 'http://www.last.fm/search?q=', 'Artist', 'Title'),
            ('MixCloud', 'http://www.mixcloud.com/search/?mixcloud_query=', 'Artist', 'Title'),
            ('SoundCloud', 'https://soundcloud.com/search?q=', 'Artist', 'Title'),
            ('TraxSource', 'http://www.traxsource.com/search?term=', 'Artist', 'Title'),
            ('YouTube', 'http://www.youtube.com/results?search_query=', 'Artist', 'Title')]
        self.default_preset = sorted(self.default_preset, key=itemgetter(0))
        self.default_choices = [v[0] for v in self.default_preset]
        self.preset = GetPreference('weblink_preset')
        if self.preset is None:
            self.preset = self.default_preset
        self.field_choices = ['', 'Filename', 'Album', 'Artist', 'Title']

    def SetPreset(self, preset):
        self.preset = preset
        SetPreference('weblink_preset', preset)

    def GetPreset(self):
        return self.preset


class WebLinkEditorPanel(DialogPanel):

    def __init__(self, parent, pos=(0, 0)):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour((255, 255, 255))
        self.preset = self.parent.parent.parent.WebLinkPreset.preset
        self.field_choices = self.parent.parent.parent.WebLinkPreset.field_choices
        self.default_preset = self.parent.parent.parent.WebLinkPreset.default_preset
        self.default_choices = self.parent.parent.parent.WebLinkPreset.default_choices
        self.WebName = list()
        self.WebLink = list()
        self.StaticTexts = list()
        self.StaticTexts += [StaticText(self, label=u'Name')]
        self.StaticTexts += [StaticText(self, label=u'URL')]
        self.StaticTexts += [StaticText(self, label=u'Query 1')]
        self.StaticTexts += [StaticText(self, label=u'Query 2')]
        self.QueryFields = list()

        idx = 1
        for preset in self.preset:
            self.WebName += [ComboBox(self, id=idx, value=preset[0],
                                      choices=self.default_choices, style=0)]
            self.WebName[-1].SetMark(0, 0)
            self.WebLink += [TextCtrl(self, id=idx, value=preset[1])]
            self.WebName[-1].Bind(wx.EVT_COMBOBOX, self.OnWebName)
            self.WebName[-1].Bind(wx.EVT_TEXT, self.OnEnableApply)
            self.WebLink[-1].Bind(wx.EVT_TEXT, self.OnEnableApply)
            QueryFields = list()
            for i in range(2):
                QueryFields += [ComboBox(self, id=idx, value=preset[i + 2],
                                         choices=self.field_choices, style=wx.CB_READONLY)]
                QueryFields[-1].Bind(wx.EVT_COMBOBOX, self.OnEnableApply)
            self.QueryFields += [QueryFields]
            idx += 1

        for _ in range(10 - len(self.preset)):
            self.WebName += [ComboBox(self, id=idx,
                                      value='', choices=self.default_choices, style=0)]
            self.WebLink += [TextCtrl(self, id=idx, value='')]
            self.WebName[-1].Bind(wx.EVT_COMBOBOX, self.OnWebName)
            self.WebName[-1].Bind(wx.EVT_TEXT, self.OnEnableApply)
            self.WebLink[-1].Bind(wx.EVT_TEXT, self.OnEnableApply)
            QueryFields = list()
            for i in range(2):
                QueryFields += [ComboBox(self, id=idx, value='',
                                         choices=self.field_choices, style=wx.CB_READONLY)]
                QueryFields[-1].Bind(wx.EVT_COMBOBOX, self.OnEnableApply)
            self.QueryFields += [QueryFields]
            idx += 1

        self.Bind(wx.EVT_SIZE, self.OnSize)

    def OnSize(self, event):
        width, height = self.GetClientSize()
        posX = 10
        posY = 20
        self.StaticTexts[0].SetRect((posX + 3, posY, -1, -1))
        self.StaticTexts[1].SetRect((posX + 105 + 3, posY, -1, -1))
        self.StaticTexts[2].SetRect((width - posX - 170 + 5 + 8, posY, -1, -1))
        self.StaticTexts[3].SetRect((width - posX - 85 + 5 + 8, posY, -1, -1))
        for idx in range(len(self.preset)):
            posX = 10
            posY += 30
            self.WebName[idx].SetRect((posX, posY - 5, 100, 22))
            self.WebLink[idx].SetRect((posX + 100 + 5, posY - 5, width - posX * 2 - 100 + 3 - 180 + 10, 22))
            posX = self.WebLink[idx].GetPosition().x + self.WebLink[idx].GetSize().width
            for i in range(2):
                self.QueryFields[idx][i].SetRect((posX + 5, posY - 5, 80, 22))
                posX += 80 + 5

    def OnEnableApply(self, event):
        pass
        # self.parent.ApplyButton.Enable()

    def OnWebName(self, event):
        name = event.String
        weblink = [v for v in self.default_preset if name == v[0]][0]
        idx = event.GetId() - 1
        self.WebLink[idx].SetValue(weblink[1])
        self.QueryFields[idx][0].SetValue(weblink[2])
        self.QueryFields[idx][1].SetValue(weblink[3])
        # self.parent.ApplyButton.Enable()

    def SaveAllPreference(self):
        names = [v.GetValue() for v in self.WebName]
        links = [v.GetValue() for v in self.WebLink]
        fields1 = [v[0].GetValue() for v in self.QueryFields]
        fields2 = [v[1].GetValue() for v in self.QueryFields]
        preset = zip(names, links, fields1, fields2)
        self.parent.parent.parent.WebLinkPreset.SetPreset(preset)

    def OnClose(self, event):
        self.SaveAllPreference()
        self.Destroy()


class KeymapPreset():

    def __init__(self):
        preset = GetPreference('keymap_preset')
        if preset is None:
            self.keymap_preset = self.GetDefaultKeymap()
        else:
            self.keymap_preset = preset

    def GetNameSpaceByRawKeyFlag(self, keyflag, ctrl=False, shift=False):
        vv = [v for v in self.keymap_preset if v[2] is not None and (v[2][0] == keyflag or v[2][1] == keyflag)]
        if len(vv) == 0:
            return None
        vv = [v for v in vv if v[3] == ctrl and v[4] == shift]
        if len(vv) == 0:
            return None
        return vv[0][0]

    def IsDelayedEventRawKeyFlag(self, keyflag):
        pass

    def SetKeymapPreset(self, keymap_preset):
        self.keymap_preset = keymap_preset

    def GetKeymapPreset(self):
        return self.keymap_preset

    def GetDefaultKeymap(self):
        default_keymap = (('play_toggle', 'Spacebar'),
                          ('previous_track', 'W'), ('next_track', 'E'),
                          ('loop_toggle', 'R'), ('highlight_toggle', 'Q'),
                          ('highlight_decrease', '1'), ('highlight_increase', '2'),
                          ('open_id3tageditor', '`'))

        keymap_preset = list()
        for i in range(len(default_keymap)):
            namespace = default_keymap[i][0]
            string = default_keymap[i][1]
            baseflag = self.String2BaseRawKeyFlag(string)
            if u'Ctrl + ' in string:
                ctrl = True
            else:
                ctrl = False
            if u'Shift + ' in string:
                shift = True
            else:
                shift = False
            keymap_preset += [(namespace, string, baseflag, ctrl, shift)]
        return keymap_preset

    def GetKeymapLabels(self):
        keymap_labels = (u'Play and Pause', u'Play previous track',
                         u'Play next track', u'Loop toggle',
                         u'Highlight toggle',
                         u'Highlight duration -', u'Highlight duration +',
                         u'Open ID3Tag Editor')
        return keymap_labels

    def String2BaseRawKeyFlag(self, string):
        key = string.split(' + ')[-1]
        keymap = self.GetKeymap()
        v = [v for v in keymap if v[1] == key]
        if len(v) == 0:
            return None
        return v[0][0]

    def RawKeyFlag2String(self, keyflag):
        keymap = self.GetKeymap()
        v = [v[1] for v in keymap if v[0][0] == keyflag or v[0][1] == keyflag]
        if len(v) == 0:
            return None
        if len(v[0]) == 1:
            v[0] = v[0].upper()
        # return unicode(v[0])
        return v[0]

    def GetKeymap(self, special=False):
        chars = [v for v in """`1234567890-=\\""".upper()]
        rawkeyflags = [(2686977, 1076428801), (131073, 1073872897),
                       (196609, 1073938433), (262145, 1074003969), (327681, 1074069505),
                       (393217, 1074135041), (458753, 1074200577), (524289, 1074266113),
                       (589825, 1074331649), (655361, 1074397185), (720897, 1074462721),
                       (786433, 1074528257), (851969, 1074593793), (2818049, 1076559873)]

        chars += [v for v in """qwertyuiop[]""".upper()]
        rawkeyflags += [(1048577, 1074790401), (1114113, 1074855937),
                        (1179649, 1074921473), (1245185, 1074987009), (1310721, 1075052545),
                        (1376257, 1075118081), (1441793, 1075183617), (1507329, 1075249153),
                        (1572865, 1075314689), (1638401, 1075380225), (1703937, 1075445761),
                        (1769473, 1075511297)]

        chars += [v for v in """asdfghjkl;'""".upper()]
        rawkeyflags += [(1966081, 1075707905), (2031617, 1075773441),
                        (2097153, 1075838977), (2162689, 1075904513), (2228225, 1075970049),
                        (2293761, 1076035585), (2359297, 1076101121), (2424833, 1076166657),
                        (2490369, 1076232193), (2555905, 1076297729), (2621441, 1076363265)]

        chars += [v for v in """zxcvbnm,./""".upper()]
        rawkeyflags += [(2883585, 1076625409), (2949121, 1076690945),
                        (3014657, 1076756481), (3080193, 1076822017), (3145729, 1076887553),
                        (3211265, 1076953089), (3276801, 1077018625), (3342337, 1077084161),
                        (3407873, 1077149697), (3473409, 1077215233)]

        chars += ['Esc', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8',
                  'F9', 'F10', 'F11', 'F12', 'BackSpace', 'Spacebar']
        # 2686977? 65537,1073807361
        rawkeyflags += [(65537, 1073807361), (3866625, 1077608449),
                        (3932161, 1077673985), (3997697, 1077739521), (4063233, 1077805057),
                        (4128769, 1077870593), (4194305, 1077936129), (4259841, 1078001665),
                        (4325377, 1078067201), (4390913, 1078132737), (4456449, 1078198273),
                        (5701633, 1079443457), (5767169, 1079508993), (917505, 1074659329),
                        (3735553, 1077477377)]

        chars += ['NumPad 1', 'NumPad 2', 'NumPad 3', 'NumPad 4', 'NumPad 5',
                  'NumPad 6', 'NumPad 7', 'NumPad 8', 'NumPad 9', 'NumPad 0']
        rawkeyflags += [(5177345, 1078919169), (5242881, 1078984705),
                        (5308417, 1079050241), (4915201, 1078657025), (4980737, 1078722561),
                        (5046273, 1078788097), (4653057, 1078394881), (4718593, 1078460417),
                        (4784129, 1078525953), (5373953, 1079115777)]

        chars += ['NumPad /', 'NumPad *', 'NumPad -', 'NumPad +', 'NumPad .']
        rawkeyflags += [(20250625, 1093992449), (3604481, 1077346305),
                        (4849665, 1078591489), (5111809, 1078853633), (5439489, 1079181313)]

        if special:

            chars += ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown']

            rawkeyflags += [(21692417, 1095434241), (21823489, 1095565313),
                            (21495809, 1095237633), (22020097, 1095761921), (3735553, 1077477377)]

            chars += ['Insert', 'Delete', 'Home', 'End', 'PageUp', 'PageDown']
            rawkeyflags += [(22151169, 1095892993), (22216705, 1095958529),
                            (21430273, 1095172097), (21954561, 1095696385),
                            (21561345, 1095303169), (22085633, 1095827457)]

            chars += ['NumLock', 'Shift(Left)', 'Shift(Right)',
                      'Ctrl', 'CapsLock', 'ScrollLock', 'Break']
            rawkeyflags += [(21299201, 1095041025), (2752513, 1076494337),
                            (3538945, 1077280769), (1900545, 1075642369),
                            (3801089, 1077542913), (4587521, 1078329345), (4521985, 1078263809)]

            chars += ['Alt(Left)', 'Alt(Right)', 'Win(Left)',
                      'Win(Right)', 'ContextMenu', 'Language']
            rawkeyflags += [(540540929, 1614282753), (20447233, 1094189057),
                            (22740993, 1096482817), (22806529, 1096548353),
                            (22872065, 1096613889), (32636929, 1106378753)]

        return [(flag, key) for flag, key in zip(rawkeyflags, chars)]


class ShortcutKeyPanel(DialogPanel, KeymapPreset):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        KeymapPreset.__init__(self)
        self.parent = parent
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour((255, 255, 255))

        labels = self.GetKeymapLabels()
        self.Labels = list()
        self.UserInput = list()
        offset = 20
        pad = -30
        idx = 1

        for i, label in enumerate(labels[:4]):
            self.Labels += [StaticText(self, id=idx, label=label, style=wx.ALIGN_RIGHT)]
            self.Labels[-1].SetRect((pad + 20, offset + 3, 150, -1))
            self.Labels[-1].Bind(wx.EVT_LEFT_DOWN, self.OnRemoveValue)
            self.UserInput += [TextCtrl(self, id=idx)]
            self.UserInput[-1].SetValue(self.keymap_preset[idx - 1][1])
            self.UserInput[-1].SetRect((pad + 165 + 15, offset, 100, 22))
            self.UserInput[-1].Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
            offset += 30
            idx += 1

        offset = 20
        pad = 220
        for i, label in enumerate(labels[4:]):
            self.Labels += [StaticText(self, id=idx, label=label, style=wx.ALIGN_RIGHT)]
            self.Labels[-1].SetRect((pad + 20, offset + 3, 150, -1))
            self.Labels[-1].Bind(wx.EVT_LEFT_DOWN, self.OnRemoveValue)
            self.UserInput += [TextCtrl(self, id=idx)]
            self.UserInput[-1].SetValue(self.keymap_preset[idx - 1][1])
            self.UserInput[-1].SetRect((pad + 165 + 15, offset, 100, 22))
            self.UserInput[-1].Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
            offset += 30
            idx += 1

        offset += 10
        width, height = self.parent.GetClientSize()
        self.DefaultButton = Button(self, label=u'Default')
        self.DefaultButton.SetRect((15, height - 24 - 15, 75, 24))
        self.DefaultButton.Bind(wx.EVT_BUTTON, self.OnDefaultButton)

    def OnSize(self, event):
        pass

    def OnClose(self, event):
        keymap_preset = list()
        default_keymap = self.GetDefaultKeymap()
        for i in range(len(self.UserInput)):
            namespace = default_keymap[i][0]
            string = self.UserInput[i].GetValue()
            baseflag = self.String2BaseRawKeyFlag(self.UserInput[i].GetValue())
            if u'Ctrl + ' in string:
                ctrl = True
            else:
                ctrl = False
            if u'Shift + ' in string:
                shift = True
            else:
                shift = False
            keymap_preset += [(namespace, string, baseflag, ctrl, shift)]
        SetPreference('keymap_preset', keymap_preset)
        self.parent.parent.parent.SetKeymapPreset(keymap_preset)
        self.Destroy()

    def OnRemoveValue(self, event):
        event.Skip()
        idx = event.GetId() - 1
        self.UserInput[idx].SetValue('')

    def OnDefaultButton(self, event):
        default_keymap = self.GetDefaultKeymap()
        for i in range(len(self.UserInput)):
            value = default_keymap[i][1]
            self.UserInput[i].SetValue(value)

    def OnKeyDown(self, event):
        idx = event.GetId() - 1
        # keymap = self.GetKeymap()
        keyflag = event.GetRawKeyFlags()
        value = self.RawKeyFlag2String(keyflag)
        if value is None:
            return
        shift = event.ShiftDown()
        ctrl = event.CmdDown() or event.ControlDown()
        if ctrl:
            value = ' + '.join(('Ctrl', value))
        if shift:
            value = ' + '.join(('Shift', value))
        value = value.replace('  ', ' ')
        if value in ('Ctrl + A'):
            return
        self.UserInput[idx].SetValue(value)
        for i in range(len(self.UserInput)):
            if i == idx:
                continue
            if value == self.UserInput[i].GetValue():
                self.UserInput[i].SetValue('')


class MacroBoxPreference():

    def __init__(self):
        self.playbox_only = False
        self.playbox_top_show = False
        self.playbox_side_show = False
        self.playbox_title_format = None
        self.playbox_title_format = None
        color_scheme = GetPreference('color_scheme')
        if color_scheme is None:
            color_scheme = 'Dark Red'
        self.st = macroboxstyle.load(color_scheme, rgbstyle='dec')

    def SetAlwaysOnTopOn(self):
        style = self.GetWindowStyle()
        self.SetWindowStyle(style ^ wx.STAY_ON_TOP)
        self.SetWindowStyle(style | wx.STAY_ON_TOP)
        SetPreference('always_on_top', True)

    def SetPlayerSideShowOn(self):
        self.playbox_side_show = True
        self.MainPanel.PlayBox.OnSize()

    def SetPlayerSideShowOff(self):
        self.playbox_side_show = False
        self.MainPanel.PlayBox.OnSize()

    def IsPlayerSideShowOn(self):
        return self.playbox_side_show

    def SetPlayerTopShowOn(self):
        self.playbox_top_show = True
        if self.IsPlayerOnlyModeOn():
            height = 242
            w, _ = self.GetSize()
            self.SetMaxSize((-1, height))
            self.SetMinSize((550, height))
            self.SetSize((w, height))
        self.OnSize()

    def SetPlayerTopShowOff(self):
        self.playbox_top_show = False
        if self.IsPlayerOnlyModeOn():
            height = 186
            w, _ = self.GetSize()
            self.SetMinSize((550, height))
            self.SetMaxSize((-1, height)) + 10
            self.SetSize((w, height))
        self.OnSize()

    def SetAlwaysOnTopOff(self):
        style = self.GetWindowStyle()
        self.SetWindowStyle(style ^ wx.STAY_ON_TOP)
        SetPreference('always_on_top', False)

    def IsPlayerTopShowOn(self):
        return self.playbox_top_show

    def SetPlayerOnlyModeOn(self):
        self.playbox_only = True
        style = self.GetWindowStyle()
        self.SetWindowStyle(style ^ wx.SYSTEM_MENU ^
                            wx.MINIMIZE_BOX ^ wx.MAXIMIZE_BOX ^ wx.CLOSE_BOX ^ wx.CAPTION)
        w, h = self.GetSize()
        self.last_height = h
        if self.IsPlayerTopShowOn():
            height = 242
        else:
            height = 186
        self.SetMinSize((550, height))
        self.SetMaxSize((-1, height))
        self.SetSize((w, height))
        self.OnSize()

    def SetPlayerOnlyModeOff(self):
        self.playbox_only = False
        style = self.GetWindowStyle()
        self.SetWindowStyle(style ^ wx.SYSTEM_MENU ^ wx.MINIMIZE_BOX ^ wx.MAXIMIZE_BOX ^ wx.CLOSE_BOX ^ wx.CAPTION)
        self.SetWindowStyle(style | wx.SYSTEM_MENU | wx.MINIMIZE_BOX | wx.MAXIMIZE_BOX | wx.CLOSE_BOX | wx.CAPTION)
        self.MenuBar.Show()
        self.SetMaxSize((-1, -1))
        self.SetMinSize((550, 450))
        w, _ = self.GetSize()
        self.SetSize((w, self.last_height))
        self.OnSize()

    def IsPlayerOnlyModeOn(self):
        return self.playbox_only

    def SetMainFrameIcon(self):
        # path = os.path.join('packages', 'icon-macrobox.ico')
        # icon = wx.Icon(path, wx.BITMAP_TYPE_ICO)
        icon = images.macrobox_icon64.GetIcon()
        self.SetIcon(icon)

    def RestoreMainFrameRect(self):
        rect = GetPreference('rect')
        if rect is None:
            SetPreference('rect', wx.Rect(0, 0, 800, 600))
        else:
            self.SetRect(rect)

    def SavePreferences(self):
        procpath = self.MainPanel.MFEATS.GetProcPath()
        taskpath = self.MainPanel.MFEATS.GetTaskPath()
        self.MainPanel.Event.StopNotify()
        self.MainPanel.MFEATS.StopNotify()
        playcue = self.MainPanel.PlayBox.cue
        self.MainPanel.PlayBox.OnStop()
        self.MainPanel.PlayBox.AudioControl.Quit()
        mfeats_scheduler = Struct(
            taskpath=taskpath, procpath=procpath,
            procs_limit=self.MainPanel.MFEATS.procs_limit,
            auto_analyzer_on=self.MainPanel.MFEATS.auto_analyzer_on)
        self.MainPanel.ListBox.SetFilterOffAll()
        playbox_show = Struct(top=self.IsPlayerTopShowOn(), side=self.IsPlayerSideShowOn())

        SetPreferences(((('rect', self.GetRect()), ('playcue', playcue),
                         ('highlight_duration_type', self.MainPanel.PlayBox.GetHighlightDurationTypeId()),
                         ('playbox_information', self.MainPanel.PlayBox.Info.information),
                         ('query_columnKey', self.MainPanel.ListSearch.query_columnKey),
                         ('listbox_fontinfo', self.MainPanel.ListBox.GetFontInfo()),
                         ('selectedlist', self.MainPanel.ListBox.selectedList),
                         ('innerlist', self.MainPanel.ListBox.innerList),
                         ('mfeats_scheduler', mfeats_scheduler),
                         ('playbox_show', playbox_show))))

    def LoadPreferences(self):
        query_columnKey = GetPreference('query_columnKey')
        if query_columnKey is not None:
            self.MainPanel.ListSearch.query_columnKey = query_columnKey
        playbox_show = GetPreference('playbox_show')
        if playbox_show is None:
            self.SetPlayerTopShowOn()
            self.MenuBar.itemPlayerTopShow.Check()
        else:
            if playbox_show.top:
                self.SetPlayerTopShowOn()
                self.MenuBar.itemPlayerTopShow.Check()
            else:
                self.SetPlayerTopShowOff()
            if playbox_show.side:
                self.SetPlayerSideShowOn()
                self.MenuBar.itemPlayerSideShow.Check()
            else:
                self.SetPlayerSideShowOff()
        if GetPreference('always_on_top'):
            self.MenuBar.itemAlwaysOnTop.Check()
            self.SetAlwaysOnTopOn()
        innerList = GetPreference('innerlist')
        if innerList is not None:
            self.MainPanel.ListBox.innerList = innerList
        selectedList = GetPreference('selectedlist')
        if selectedList is not None:
            self.MainPanel.ListBox.selectedList = selectedList
        # self.MainPanel.ListBox.CheckItemsConsistencyAll()
        mfeats = GetPreference('mfeats_scheduler')
        if mfeats is not None:
            # print mfeats.procs_limit
            self.MainPanel.MFEATS.procs_limit = mfeats.procs_limit
            self.MainPanel.MFEATS.auto_analyzer_on = mfeats.auto_analyzer_on
            # self.MainPanel.MFEATS.taskpath = mfeats.taskpath
            self.LimitCoreNumber(mfeats.procs_limit)
            if mfeats.auto_analyzer_on:
                self.MainPanel.MFEATS.AutoAnalyzer()
                self.MenuBar.itemAutoAnalyze.Check()
            for path in mfeats.procpath:
                self.MainPanel.ListBox.CheckItemConsistencyByPathAll(path)
        else:
            self.MainPanel.MFEATS.auto_analyzer_on = True
            self.MenuBar.itemAutoAnalyze.Check()

        highlight_duration_type = GetPreference('highlight_duration_type')
        if highlight_duration_type is None:
            highlight_duration_type = 2
        for i in range(len(self.MenuBar.highlightDurationItems)):
            if i == highlight_duration_type:
                self.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check()
            else:
                self.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check(False)

        tutotial_show = GetPreference('tutotial_show')
        if tutotial_show is None:
            SetPreference('tutotial_show', True)
        self.MainPanel.OnSize()
        self.MainPanel.ListBox.SetListUnLockAll()
        auto_check_update = GetPreference('auto_check_update')
        if auto_check_update is None or auto_check_update:
            self.OnAutoCheckUpdate(None)
        # if GetPreference('tutotial_show'):
        #   self.OnTutorial(None)
        self.PlayBoxTitleFormat = PlayBoxTitleFormat(self)
        self.WebLinkPreset = WebLinkPreset()


class PlayBoxTitleFormat():

    def __init__(self, parent):
        self.parent = parent
        self.choices = ['', 'Filename', 'Album', 'Artist', 'Title']
        self.preset = GetPreference('playbox_title_format')
        if self.preset is None:
            self.preset = [u'Filename', u'Artist', u'Title']

    def SetPreset(self, preset):
        self.preset = preset
        SetPreference('playbox_title_format', preset)
        self.parent.MainPanel.PlayBox.Title.reInitBuffer = True

    def SetPresetByIdx(self, idx, value):
        self.preset[idx] = value
        SetPreference('playbox_title_format', self.preset)
        self.parent.MainPanel.PlayBox.Title.reInitBuffer = True

    def GetChoices(self):
        return self.choices

    def GetPreset(self):
        return self.preset


class AppearancePanel(wx.Panel):

    def __init__(self, parent, pos=(0, 0)):
        wx.Panel.__init__(self, parent, wx.ID_ANY,
                          style=wx.CLIP_CHILDREN | wx.NO_FULL_REPAINT_ON_RESIZE | wx.TAB_TRAVERSAL)
        self.parent = parent
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour((255, 255, 255))
        # st = self.parent.parent.parent.MainPanel.ListBox.st

        font = wx.Font(0, wx.MODERN, wx.NORMAL, wx.FONTWEIGHT_LIGHT)
        font.SetPixelSize((6, 50))
        font.SetFaceName(FONT_ITEM)
        offset = 20
        pad = 0

        label = u'Player Title Format'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 3, 180, -1))
        preset = self.parent.parent.parent.PlayBoxTitleFormat.GetPreset()
        choices = self.parent.parent.parent.PlayBoxTitleFormat.GetChoices()
        self.PlayerTitleFormat = list()
        self.PlayerTitleFormat += [ComboBox(
            self, id=1, choices=choices, style=wx.CB_READONLY)]
        self.PlayerTitleFormat[-1].SetValue(preset[0])
        self.PlayerTitleFormat[-1].SetRect((200 + 15 + 1 + 85 * 0, offset, 80, 24))

        self.PlayerTitleFormat[-1].Bind(wx.EVT_COMBOBOX, self.OnPlayerTitleFormat)
        self.PlayerTitleFormat += [ComboBox(
            self, id=2, choices=choices, style=wx.CB_READONLY)]
        self.PlayerTitleFormat[-1].SetValue(preset[1])
        self.PlayerTitleFormat[-1].SetRect((200 + 15 + 1 + 85 * 1, offset, 80, 24))
        self.PlayerTitleFormat[-1].Bind(wx.EVT_COMBOBOX, self.OnPlayerTitleFormat)

        self.PlayerTitleFormat += [ComboBox(
            self, id=3, choices=choices, style=wx.CB_READONLY)]
        self.PlayerTitleFormat[-1].SetRect((200 + 15 + 1 + 85 * 2, offset, 80, 24))
        self.PlayerTitleFormat[-1].SetValue(preset[2])
        self.PlayerTitleFormat[-1].Bind(wx.EVT_COMBOBOX, self.OnPlayerTitleFormat)
        offset += 10

        offset += 30
        label = u'Color Scheme'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((pad + 20, offset + 3, 180, -1))

        macroboxstyle.STYLE_NAMES
        choices = macroboxstyle.STYLE_NAMES
        self.ColorScheme = ComboBox(self, choices=choices, style=wx.CB_READONLY)
        self.ColorScheme.SetRect((pad + 200 + 15 + 1, offset, 165, 24))
        self.ColorScheme.Bind(wx.EVT_COMBOBOX, self.OnColorScheme)
        color_scheme = GetPreference('color_scheme')
        if color_scheme is None:
            color_scheme = 'Dark Red'
        self.ColorScheme.SetValue(color_scheme)

        offset += 30
        label = u'Contrast'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((pad + 20, offset + 3, 180, -1))
        self.TracklistLineContrast = SpinCtrl(self, value='0')
        self.TracklistLineContrast.SetRect((pad + 200 + 15 + 1, offset + 1, 60, 22))
        self.TracklistLineContrast.SetRange(-10, 10)
        self.TracklistLineContrast.Bind(wx.EVT_SPINCTRL, self.OnTracklistLineContrast)
        value = self.parent.parent.parent.MainPanel.ListBox.line_contrast
        self.TracklistLineContrast.SetValue(value)

        offset += 30
        label = u'Font'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((pad + 20, offset + 3, 180, -1))
        self.TracklistFont = wx.FontPickerCtrl(self, style=wx.FNTP_FONTDESC_AS_LABEL | wx.ALIGN_LEFT)
        self.TracklistFont.SetRect((pad + 200 + 15, offset, 165 + 2, 24))
        self.Bind(wx.EVT_FONTPICKER_CHANGED, self.OnTracklistFont, self.TracklistFont)

        offset += 30
        label = u'Line Space'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((pad + 20, offset + 3, 180, -1))
        self.TracklistLineSpace = SpinCtrl(self)
        self.TracklistLineSpace.SetRect((pad + 200 + 15 + 1, offset + 1, 60, 22))
        self.TracklistLineSpace.SetRange(20, 30)
        self.TracklistLineSpace.Bind(wx.EVT_SPINCTRL, self.OnTracklistLineSpace)
        value = self.parent.parent.parent.MainPanel.ListBox.line_space
        self.TracklistLineSpace.SetValue(value)

        offset += 30
        label = u'Scrollbar Size'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((pad + 20, offset + 3, 180, -1))
        self.ScrollbarSize = SpinCtrl(self)
        self.ScrollbarSize.SetRect((pad + 200 + 15 + 1, offset + 1, 60, 22))
        self.ScrollbarSize.SetRange(2, 10)
        self.ScrollbarSize.Bind(wx.EVT_SPINCTRL, self.OnScrollbarSize)
        value = self.parent.parent.parent.MainPanel.ListBox.scrollbar_size
        self.ScrollbarSize.SetValue(value)

        # offset += 30
        # label = u'Always show scrollbar'
        # text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        # text.SetRect((pad+20, offset+3, 180, -1))
        # self.AlwaysShowScrollbar = CheckBox(self)
        # self.AlwaysShowScrollbar.SetPosition((pad+200+15, offset+4))
        # self.AlwaysShowScrollbar.Bind(wx.EVT_CHECKBOX, self.OnAlwaysShowScrollbar)
        # value = self.parent.parent.parent.MainPanel.ListBox.always_show_slider
        # # value = self.parent.parent.parent.MainPanel.ListBox.st.SCROLLBAR_ALWAYS
        # self.AlwaysShowScrollbar.SetValue(value)

        self.SetCurrentValues()
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.OnSize(None)

    def OnScrollbarSize(self, event):
        value = event.GetInt()
        self.parent.parent.parent.MainPanel.ListBox.scrollbar_size = value
        self.parent.parent.parent.MainPanel.ListBox.reInitBuffer = True
        self.ApplyToScriptEditorBox()

    def OnAlwaysShowScrollbar(self, event):
        self.parent.parent.parent.MainPanel\
            .ListBox.always_show_slider = event.IsChecked()
        self.ApplyToScriptEditorBox()

    def SetCurrentValues(self):
        font = self.parent.parent.parent.MainPanel.ListBox.font
        self.TracklistFont.SetSelectedFont(font)

    def OnColorScheme(self, event):
        name = event.GetString()
        import macroboxstyle
        style = macroboxstyle.load(name, rgbstyle='dec')
        self.parent.parent.parent.st = style
        self.ApplyToMainFrame()
        self.ApplyToScriptEditorBox()
        self.SetCurrentValues()

    def ApplyToScriptEditorBox(self):
        parent = self.parent.parent.parent
        if hasattr(parent, 'ScriptEditorBox') is False:
            return
        if hasattr(parent.ScriptEditorBox, 'EditorPanel') is False:
            return
        parent.ScriptEditorBox.OnSize(None)
        parent.ScriptEditorBox.EditorPanel.OnSize(None)
        parent.ScriptEditorBox.PreviewPanel.OnSize(None)
        parent.ScriptEditorBox.EditorPanel.OnColor(None)
        parent.ScriptEditorBox.EditorPanel.TextCtrl.SetUpEditor()
        parent.ScriptEditorBox.EditorPanel.TextCtrl.OnUpdateUI(None)
        parent.ScriptEditorBox.PreviewPanel.OnColor(None)
        parent.ScriptEditorBox.PreviewPanel.TextCtrl.SetUpPreview()
        parent.ScriptEditorBox.PreviewPanel.TextCtrl.OnUpdateUI(None)

    def ApplyToMainFrame(self):
        st = self.parent.parent.parent.st
        MainPanel = self.parent.parent.parent.MainPanel
        MainPanel.ListBox.st = st.LISTBOX
        MainPanel.PlayBox.st = st.PLAYBOX
        MainPanel.SetBackgroundColour((0, 0, 0))
        MainPanel.ListBox.SetBackgroundColour(st.LISTBOX.LIST_BG_COLOR)
        MainPanel.ListBox.List.SetBackgroundColour(st.LISTBOX.LIST_BG_COLOR)
        MainPanel.PlayBox.SetBackgroundColour(st.PLAYBOX.PLAY_BG_COLOR)
        MainPanel.OnSize(None)

    def OnTracklistLineContrast(self, event):
        value = event.GetInt()
        self.parent.parent.parent.MainPanel.ListBox.line_contrast = value
        self.parent.parent.parent.MainPanel.ListBox.reInitBuffer = True

    def OnTracklistLineSpace(self, event):
        value = event.GetInt()
        self.parent.parent.parent.MainPanel.ListBox.line_space = value
        self.parent.parent.parent.MainPanel.ListBox.SetRowsHeightAll(value)
        self.parent.parent.parent.MainPanel.ListBox.st.HEADER_HEIGHT = value
        self.parent.parent.parent.MainPanel.ListBox.reInitBuffer = True

    def OnFrameTransparency(self, event):
        value = event.GetInt()
        self.parent.parent.parent.SetTransparent(value)
        self.parent.parent.parent.st.FRAME.TRANSPARENT = value

    def OnPlayerTitleFormat(self, event):
        idx = event.GetId() - 1
        value = event.GetString()
        self.parent.parent.parent.PlayBoxTitleFormat.SetPresetByIdx(idx, value)
        self.parent.parent.parent.MainPanel.PlayBox.Title.reInitBuffer = True

    def OnSize(self, event):
        pass

    def OnTracklistFontColor(self, event):
        rgb = event.GetColour()[:3]
        self.parent.parent.parent.MainPanel.ListBox.st.FONT_COLOR = rgb
        self.parent.parent.parent.MainPanel.ListBox.reInitBuffer = True

    def OnTracklistBGColor(self, event):
        rgb = event.GetColour()[:3]
        self.parent.parent.parent.MainPanel.ListBox.st.BG_COLOR = rgb
        self.parent.parent.parent.MainPanel.ListBox.reInitBuffer = True

    def OnTracklistFont(self, event):
        font = event.GetFont()
        size = font.GetPixelSize()
        tw, th = size
        if th > 30:
            self.SetCurrentValues()
            return
        self.parent.parent.parent.MainPanel.ListBox.SetFont(font)
        th = font.GetPixelSize().height
        height = int(th * 1.5)
        if height > self.parent.parent.parent.MainPanel.ListBox.GetRowsHeight():
            self.parent.parent.parent.MainPanel.ListBox.SetRowsHeightAll(height)
        self.parent.parent.parent.MainPanel.ListBox.reInitBuffer = True

    def OnHighlightDuration(self, event):
        dutaionTypeId = event.Id - 201
        value = [v for i, v in enumerate(
            self.MenuBar.highlightDurationItems) if dutaionTypeId == i][0]
        self.MainPanel.PlayBox.SetBestHighlightVariablePeriodTime(static=value)
        if self.MainPanel.PlayBox.IsPlaying() and self.MainPanel.PlayBox.IsHighlightOn():
            self.MainPanel.PlayBox.GotoTrackOffsetTime()
            self.MainPanel.PlayBox.reInitWave = True
            self.MainPanel.PlayBox.OnSize()
        elif self.MainPanel.PlayBox.IsHighlightOn():
            self.MainPanel.PlayBox.GotoTrackOffsetTime()
            self.MainPanel.PlayBox.reInitWave = True
            self.MainPanel.PlayBox.OnSize()
        for i in range(len(self.MenuBar.highlightDurationItems)):
            if i == dutaionTypeId:
                self.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check()
            else:
                self.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check(False)
        SetPreference('highlight_duration_type', dutaionTypeId)

    def OnClose(self, event):
        color_scheme = self.ColorScheme.GetValue()
        scrollbar_size = self.ScrollbarSize.GetValue()
        # always_show_slider = self.AlwaysShowScrollbar.GetValue()
        listbox_line_space = self.TracklistLineSpace.GetValue()
        listbox_line_contrast = self.TracklistLineContrast.GetValue()
        SetPreferences(((('color_scheme', color_scheme),
                         ('scrollbar_size', scrollbar_size),\
                         # ('always_show_slider', always_show_slider),\
                         ('listbox_line_space', listbox_line_space),\
                         ('listbox_line_contrast', listbox_line_contrast))))
        self.Destroy()


# end of AppearancePanel


#
# # FileAssociation
#
# class FileAssociation(wx.Frame):
#
#   def __init__(self):
#       command = ['assoc']
#       proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
#       resp = proc.communicate()[0]
#       proc.terminate()
#       resp = resp.split(os.linesep)
#       sfes = [v.lower() for v in SUPPORTED_AUDIO_TYPE]
#       sfes = [v for v in resp if v.split('=')[0][1:].lower() in sfes]
#       # for v in sfes: print v
#       #-----------------------------------------------------------------------
#       # command = ['assoc']
#       command = ['ftype']
#       proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
#       resp = proc.communicate()[0]
#       proc.terminate()
#       resp = resp.split(os.linesep)
#       # for v in resp: print v
#       sfts = [v.split('=')[-1] for v in sfes]
#       # print '-'*100
#       # for v in sfts: print v
#       sfts = [v for v in resp if v.split('=')[0].lower() in sfts]
#       # print '-'*100
#       # for v in sfts: print v
#
#   def SetAssociate(self, associate=True):
#       #-----------------------------------------------------------------------
#       if associate:
#           # commands = [('assoc', '.mp3=KMPlayer.mp3')]
#           commands = [('assoc', '.mp3=macrobox')]
#           # commands = [('assoc', '.mp3=macrobox.mp3')]
#           # commands += [('assoc', '.bmp=macrobox')]
#           # commands += [('assoc', '.png=macrobox')]
#           # commands += [('assoc', '.jpg=macrobox')]
#           # commands += [('assoc', '.jpeg=macrobox')]
#       else:
#           commands = [('assoc', '.mp3=giffile')]
#           # commands += [('assoc', '.bmp=pngfile')]
#           # commands += [('assoc', '.png=pngfile')]
#           # commands += [('assoc', '.jpg=jpegfile')]
#           # commands += [('assoc', '.jpeg=jpegfile')]
#       for command in commands:
#           proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
#           resp = proc.communicate()[0]
#       #-----------------------------------------------------------------------
#       # print selfname
#       # command = ['ftype', 'uniview=python.exe', 'D:\XRESEARCHX\uniview\uniview.py', '%1']
#       if is_packaged():
#           selfname = r'D:\XRESEARCHX\macroboxpro\dist\macrobox\macrobox.exe'
#           command = ['ftype', 'macrobox=%s' % (selfname), '%1']
#       else:
#           command = ['ftype', 'macrobox=python.exe', __file__, '%1']

#       selfname = r'D:\XRESEARCHX\macroboxpro\dist\macrobox\macrobox.exe'
#       selfname = r'C:\Program Files (x86)\MACROBOX Professional\macrobox.exe'
#       command = ['ftype', 'macrobox=%s' % (selfname), '%1']

#       proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
#       resp = proc.communicate()[0]
#       return
#
#


class PreferenceMFEATSPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        self.SetDoubleBuffered(True)
        self.SetBackgroundColour((255, 255, 255))

        offset = 20
        label = u'Concurrent processing analyzers'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 3, 200, -1))
        self.ThreadNumber = SpinCtrl(self, value='0')
        # self.ThreadNumber.SetPosition((220+15, offset-1))
        self.ThreadNumber.SetRect((220 + 15, offset - 1, 60, 22))
        max_cores = self.parent.parent.parent.MainPanel.MFEATS.GetMaxCores()
        procs_limit = self.parent.parent.parent.MainPanel.MFEATS.GetProcsLimit()
        self.ThreadNumber.SetRange(1, max_cores)
        self.ThreadNumber.SetValue(procs_limit)
        self.ThreadNumber.Bind(wx.EVT_SPINCTRL, self.OnThreadNumber)
        tooltip = u'Number of concurrent processing analyzers.'
        tooltip += u'\nTotal number of avaliable analyzers are up to'
        tooltip += u'\nyour cpu thread number.'
        self.ThreadNumber.SetToolTip(wx.ToolTip(tooltip))

        values = GetPreferences(('auto_save_tag',
                                 'key_format_type', 'tempo_restict_type'))
        auto_save_tag, key_format_type, tempo_restict_type = values

        offset += 30
        label = u'Auto Save Tempo and Key to ID3Tag'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 3, 200, -1))
        self.AutoSaveID3Tag = CheckBox(self)
        self.AutoSaveID3Tag.SetPosition((220 + 15, offset + 4))
        if auto_save_tag:
            self.AutoSaveID3Tag.SetValue(1)
        self.AutoSaveID3Tag.Bind(wx.EVT_CHECKBOX, self.OnAutoSaveID3Tag)

        offset += 30
        label = u'Restrict Tempo Range on Analysis'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 3, 200, -1))
        self.tempo_choices = ['Full Range', 'Up Tempo (95bpm~)', 'Down Tempo (~120bpm)']
        self.TempoRange = ComboBox(self, choices=self.tempo_choices, style=wx.CB_READONLY)
        self.TempoRange.SetRect((220 + 15, offset, 170, 24))
        if tempo_restict_type is None:
            self.TempoRange.SetValue(self.tempo_choices[0])
        else:
            self.TempoRange.SetValue(self.tempo_choices[tempo_restict_type])
        self.TempoRange.Bind(wx.EVT_COMBOBOX, self.OnTempoRange)

        offset += 30
        StaticText(self, label='Default Key Format on Analysis',
                   pos=(20, offset + 3), size=(200, -1), style=wx.ALIGN_RIGHT)
        self.key_choices = ['Flat (Dbm)', 'Sharp (C#m)', 'Camelot (12A)']
        self.KeyFormat = ComboBox(self, choices=self.key_choices, style=wx.CB_READONLY)
        self.KeyFormat.SetRect((220 + 15, offset, 170, 24))
        if key_format_type is None:
            self.KeyFormat.SetValue(self.key_choices[1])
        else:
            self.KeyFormat.SetValue(self.key_choices[key_format_type])
        self.KeyFormat.Bind(wx.EVT_COMBOBOX, self.OnKeyFormat)

        # offset += 30 + 10
        # label = u'AGC(Auto Gain Control) Headroom (%)'
        # text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        # text.SetRect((20, offset + 3, 200, -1))
        # self.AgcHeadroomSpin = SpinCtrl(self, value='0')
        # # self.AgcHeadroomSpin.SetPosition((220+15, offset-1))
        # self.AgcHeadroomSpin.SetRect((220 + 15, offset, 60, 22))
        # self.AgcHeadroomSpin.SetRange(75, 200)
        # value = self.parent.parent.parent.MainPanel.PlayBox.cue.agc_headroom * 100
        # self.AgcHeadroomSpin.SetValue(value)
        # self.AgcHeadroomSpin.Bind(wx.EVT_SPINCTRL, self.OnAgcHeadroomSpin)
        # tooltip = u'Note that MacroBox does not compress sound for AGC control.'
        # tooltip += u'\nDefault headrooom is set to -12db covers wide range of dynamics.'
        # self.AgcHeadroomSpin.SetToolTip(wx.ToolTip(tooltip))
        # self.AgcSpinDefaultButton = Button(self, label=u'Default')
        # self.AgcSpinDefaultButton.SetRect((220 + 20 + 60 - 5, offset - 1, 52, 24))
        # self.AgcSpinDefaultButton.Bind(wx.EVT_BUTTON, self.OnAgcSpinDefaultButton)
        # self.AgcSpinDefaultButton.SetToolTip(wx.ToolTip(tooltip))

        offset += 30 + 10
        label = u'Spectrum FPS'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 3, 200, -1))
        self.SpectrumFPS = SpinCtrl(self, value='0')
        # self.SpectrumFPS.SetPosition((220+15, offset))
        self.SpectrumFPS.SetRect((220 + 15, offset, 60, 22))
        self.SpectrumFPS.SetRange(1, 240)
        value = self.parent.parent.parent.MainPanel.PlayBox.Spectrum.buffer.fps
        self.SpectrumFPS.SetValue(value)
        self.SpectrumFPS.Bind(wx.EVT_SPINCTRL, self.OnSpectrumFPS)
        tooltip = u'Spectrum FPS(frame/second).'
        self.SpectrumFPS.SetToolTip(wx.ToolTip(tooltip))

        offset += 30
        label = u'Vectorscope FPS'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 3, 200, -1))
        self.VectorscopeFPS = SpinCtrl(self, value='0')
        # self.VectorscopeFPS.SetPosition((220+15, offset))
        self.VectorscopeFPS.SetRect((220 + 15, offset, 60, 22))
        self.VectorscopeFPS.SetRange(1, 240)
        value = self.parent.parent.parent.MainPanel.PlayBox.VectorScope.buffer.fps
        self.VectorscopeFPS.SetValue(value)
        self.VectorscopeFPS.Bind(wx.EVT_SPINCTRL, self.OnVectorscopeFPS)
        tooltip = u'Vectorscope FPS(frame/second).'
        self.VectorscopeFPS.SetToolTip(wx.ToolTip(tooltip))

        offset += 40
        # pad = 0
        label = u'Player Title Format'
        text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        text.SetRect((20, offset + 3, 200, -1))
        preset = self.parent.parent.parent.PlayBoxTitleFormat.GetPreset()
        choices = self.parent.parent.parent.PlayBoxTitleFormat.GetChoices()
        self.PlayerTitleFormat = list()
        self.PlayerTitleFormat += [ComboBox(
            self, id=1, choices=choices, style=wx.CB_READONLY)]
        self.PlayerTitleFormat[-1].SetValue(preset[0])
        self.PlayerTitleFormat[-1].SetRect((220 + 15 + 85 * 0, offset, 80, 24))

        self.PlayerTitleFormat[-1].Bind(wx.EVT_COMBOBOX, self.OnPlayerTitleFormat)
        self.PlayerTitleFormat += [ComboBox(
            self, id=2, choices=choices, style=wx.CB_READONLY)]
        self.PlayerTitleFormat[-1].SetValue(preset[1])
        self.PlayerTitleFormat[-1].SetRect((220 + 15 + 85 * 1, offset, 80, 24))
        self.PlayerTitleFormat[-1].Bind(wx.EVT_COMBOBOX, self.OnPlayerTitleFormat)

        self.PlayerTitleFormat += [ComboBox(
            self, id=3, choices=choices, style=wx.CB_READONLY)]
        self.PlayerTitleFormat[-1].SetRect((220 + 15 + 85 * 2, offset, 80, 24))
        self.PlayerTitleFormat[-1].SetValue(preset[2])
        self.PlayerTitleFormat[-1].Bind(wx.EVT_COMBOBOX, self.OnPlayerTitleFormat)

        # offset += 10
        # offset += 25
        # label = u'Default Audio Player'
        # text = StaticText(self, label=label, style=wx.ALIGN_RIGHT)
        # text.SetRect((20, offset+3, 200, -1))
        # self.DefaultPlayer = CheckBox(self)
        # self.DefaultPlayer.SetPosition((220+15, offset+4))
        # if self.IsDefaultPlayer(): self.DefaultPlayer.SetValue(1)
        # self.DefaultPlayer.Bind(wx.EVT_CHECKBOX, self.OnDefaultPlayer)

        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.OnSize(None)

    def IsDefaultPlayer(self):
        # https://docs.python.org/2/library/_winreg.html
        supported_type = list(SUPPORTED_AUDIO_TYPE) + list(SUPPORTED_PLAYLIST_TYPE)
        address = 'Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\FileExts\\.%s\\UserChoice'
        for extention in supported_type:
            try:
                aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                aKey = winreg.OpenKey(aReg, address % (extention))
                value = winreg.QueryValueEx(aKey, 'ProgId')[0]
                winreg.CloseKey(aKey)
            except Exception:
                return False
            if 'macrobox.exe' not in value:
                return False
        return True

    def OnDefaultPlayer(self, event):
        architecture = ''
        if 'PROGRAMFILES(X86)' in os.environ:
            architecture = ' (x86)'
        app_path = 'C:\\Program Files%s\\%s %s\\macrobox.exe'\
            % (architecture, PRODUCT_NAME, PRODUCT_EDITION)
        supported_type = list(SUPPORTED_AUDIO_TYPE) + list(SUPPORTED_PLAYLIST_TYPE)

        if event.IsChecked() is False:
            for extention in supported_type:
                # extention = 'mp3'
                aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                address = 'Software\\Microsoft\\Windows\\'
                address += 'CurrentVersion\\Explorer\\FileExts\\.%s' % (extention)
                aKey = winreg.OpenKey(aReg, address, 0, winreg.KEY_ALL_ACCESS)
                winreg.DeleteKey(aKey, r'UserChoice')
                winreg.CloseKey(aKey)
            return

        try:
            mst_address = 'Applications'
            sub_address = 'macrobox.exe\\shell\\open\\command'
            aReg = winreg.ConnectRegistry(None, winreg.HKEY_CLASSES_ROOT)
            aKey = winreg.OpenKey(aReg, mst_address, 0, winreg.KEY_ALL_ACCESS)
            winreg.CreateKey(aKey, sub_address)
            winreg.CloseKey(aKey)

            address = '\\'.join([mst_address, sub_address])
            aKey = winreg.OpenKey(aReg, address, 0, winreg.KEY_ALL_ACCESS)
            value = '"%s" "%%1"' % (app_path)
            winreg.SetValueEx(aKey, r'', 0, winreg.REG_SZ, value)
            winreg.SetValueEx(aKey, r'@', 0, winreg.REG_SZ, value)
            winreg.CloseKey(aKey)
        except Exception:
            pass

        mst_address = 'Software\\Classes'
        sub_address = 'Applications\\macrobox.exe\\shell\\open\\command'
        aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        aKey = winreg.OpenKey(aReg, mst_address, 0, winreg.KEY_ALL_ACCESS)
        winreg.CreateKey(aKey, sub_address)
        winreg.CloseKey(aKey)

        address = '\\'.join([mst_address, sub_address])
        aKey = winreg.OpenKey(aReg, address, 0, winreg.KEY_ALL_ACCESS)
        value = '"%s" "%%1"' % (app_path)
        winreg.SetValueEx(aKey, r'', 0, winreg.REG_SZ, value)
        winreg.SetValueEx(aKey, r'@', 0, winreg.REG_SZ, value)
        winreg.CloseKey(aKey)

        for extention in supported_type:
            # extention = 'mp3'
            address = 'Software\\Microsoft\\Windows\\'
            address += 'CurrentVersion\\Explorer\\FileExts\\.%s' % (extention)
            try:
                aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                aKey = winreg.OpenKey(aReg, address, 0, winreg.KEY_ALL_ACCESS)
                winreg.DeleteKey(aKey, r'UserChoice')
                winreg.CloseKey(aKey)
            except Exception:
                pass

            aReg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            aKey = winreg.OpenKey(aReg, address, 0, winreg.KEY_ALL_ACCESS)
            winreg.CreateKey(aKey, r'UserChoice')
            winreg.CloseKey(aKey)

            address = 'Software\\Microsoft\\Windows\\'
            address += 'CurrentVersion\\Explorer\\FileExts\\.%s\\UserChoice' % (extention)
            aKey = winreg.OpenKey(aReg, address, 0, winreg.KEY_ALL_ACCESS)
            value = 'Applications\\macrobox.exe'
            winreg.SetValueEx(aKey, r'ProgId', 0, winreg.REG_SZ, value)
            winreg.CloseKey(aKey)

        # selfname = r'C:\Program Files (x86)\MACROBOX Professional\macrobox.exe'
        # # command = 'ftype macrobox="%s" %%1' % (selfname)
        # command = ['ftype', 'macrobox="%s"' % (selfname), '%1']
        # proc = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        # resp = proc.communicate()[0]
        # proc.terminate()
        # run_hidden_subprocess(command, resp=True)
        # selfname = r'C:\Program Files (x86)\MACROBOX Professional\macrobox.exe'
        # command = ['ftype', 'macrobox=%s' % (selfname), '%1']

    def OnPlayerTitleFormat(self, event):
        idx = event.GetId() - 1
        value = event.GetString()
        self.parent.parent.parent.PlayBoxTitleFormat.SetPresetByIdx(idx, value)
        self.parent.parent.parent.MainPanel.PlayBox.Title.reInitBuffer = True

    def OnSize(self, event):
        width, height = self.parent.parent.GetClientSize()
        # x, y, w, h = self.VectorscopeFPS.GetRect()
        x, y, w, h = self.PlayerTitleFormat[-1].GetRect()
        # x, y, w, h = self.DefaultPlayer.GetRect()
        self.SetSize((width - 20, y + h))

    def OnThreadNumber(self, event):
        value = event.GetInt()
        self.parent.parent.parent.MainPanel.MFEATS.SetProcsLimit(value)

    def OnAutoSaveID3Tag(self, event):
        SetPreference('auto_save_tag', event.IsChecked())

    def OnKeyFormat(self, event):
        idx = [i for i, v in enumerate(
            self.key_choices) if v == event.GetString()][0]
        self.key_format_type = idx
        SetPreference('key_format_type', self.key_format_type)

    def OnTempoRange(self, event):
        idx = [i for i, v in enumerate(
            self.tempo_choices) if v == event.GetString()][0]
        self.tempo_restict_type = idx
        SetPreference('tempo_restict_type', self.tempo_restict_type)

    def OnSpectrumFPS(self, event):
        spectrum_fps = self.SpectrumFPS.GetValue()
        self.parent.parent.parent.MainPanel\
            .PlayBox.Spectrum.buffer.fps = spectrum_fps
        vectorscope_fps = self.VectorscopeFPS.GetValue()
        if vectorscope_fps > spectrum_fps:
            vectorscope_fps = spectrum_fps
        self.VectorscopeFPS.SetValue(vectorscope_fps)
        self.parent.parent.parent.MainPanel\
            .PlayBox.VectorScope.buffer.fps = vectorscope_fps

    def OnVectorscopeFPS(self, event):
        vectorscope_fps = self.VectorscopeFPS.GetValue()
        self.parent.parent.parent.MainPanel\
            .PlayBox.VectorScope.buffer.fps = vectorscope_fps
        spectrum_fps = self.SpectrumFPS.GetValue()
        if vectorscope_fps > spectrum_fps:
            spectrum_fps = vectorscope_fps
        self.SpectrumFPS.SetValue(spectrum_fps)
        self.parent.parent.parent.MainPanel\
            .PlayBox.Spectrum.buffer.fps = spectrum_fps

    def OnAgcSpinDefaultButton(self, event):
        self.AgcHeadroomSpin.SetValue(100)
        self.SetAGCHeadroom(100)

    def OnAgcHeadroomSpin(self, event):
        self.SetAGCHeadroom(event.GetInt())

    def SetAGCHeadroom(self, value):
        self.parent.parent.parent.MainPanel\
            .PlayBox.cue.agc_headroom = value * 0.01
        self.parent.parent.parent.MainPanel.PlayBox.SetVolume()

    def OnClose(self, event):
        # agc_headroom = self.AgcHeadroomSpin.GetValue()
        spectrum_fps = self.SpectrumFPS.GetValue()
        vectorscope_fps = self.VectorscopeFPS.GetValue()
        SetPreferences(((('spectrum_fps', spectrum_fps),
                         ('vectorscope_fps', vectorscope_fps))))
        # SetPreferences(((('agc_headroom', agc_headroom),\
        #   ('spectrum_fps', spectrum_fps),
        #   ('vectorscope_fps', vectorscope_fps))))
        self.Destroy()


class PreferenceNotebook(wx.Notebook):

    def __init__(self, parent):
        wx.Notebook.__init__(self, parent, size=(600, 500), style=wx.BK_DEFAULT)
        self.parent = parent

        self.MFEATSPanel = PreferenceMFEATSPanel(self)
        self.AddPage(self.MFEATSPanel, 'General')

        # self.AppearancePanel = AppearancePanel(self)
        # self.AddPage(self.AppearancePanel, 'Appearance')

        self.ShortcutKeyPanel = ShortcutKeyPanel(self)
        self.AddPage(self.ShortcutKeyPanel, 'Shortcut Key')

        # self.WebLinkPanel = WebLinkEditorPanel(self)
        # self.AddPage(self.WebLinkPanel, 'Web Search')

        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChanged)
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGING, self.OnPageChanging)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.OnSize(None)
        self.Show()

    def OnSize(self, event):
        width, height = self.GetClientSize()
        self.MFEATSPanel.SetSize((width - 20, height - 40))
        # self.AppearancePanel.SetSize((width-20, height-40))
        self.ShortcutKeyPanel.SetSize((width - 20, height - 40))
        # self.WebLinkPanel.SetSize((width-20, height-40))
        self.Refresh()

    def OnPageChanged(self, event):
        # old = event.GetOldSelection()
        # new = event.GetSelection()
        # selected = self.GetSelection()
        event.Skip()

    def OnPageChanging(self, event):
        # old = event.GetOldSelection()
        # new = event.GetSelection()
        # selected = self.GetSelection()
        event.Skip()

    def OnClose(self, event):
        self.MFEATSPanel.OnClose(None)
        self.ShortcutKeyPanel.OnClose(None)
        # self.AppearancePanel.OnClose(None)
        # self.WebLinkPanel.OnClose(None)
        self.Destroy()


class PreferenceBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, wx.ID_ANY, size=(550, 450))
        self.parent = parent
        self.SetTitle('Preference')
        self.SetBackgroundColour((240, 240, 240))
        self.Notebook = PreferenceNotebook(self)

        width, height = self.GetClientSize()
        self.CloseButton = Button(self, label='Close')
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.OnSize(None)

    def OnSize(self, event):
        width, height = self.GetClientSize()
        # x, y, w, h = self.Notebook.WebLinkPanel.WebLink[-1].GetRect()
        # self.SetClientSize((width, y+h+110))
        self.SetClientSize((width, 350))
        self.Notebook.SetRect((5, 5, width - 8, height - 51))
        self.Notebook.OnSize(None)
        w, h = self.CloseButton.GetSize()
        self.CloseButton.SetPosition((width - 85, height - h - 10))

    def OnClose(self, event):
        self.Hide()
        self.Notebook.OnClose(None)
        if self.IsModal():
            self.EndModal(0)
        self.Destroy()


class TutorialPanel(DialogPanel):

    def __init__(self, parent):
        DialogPanel.__init__(self, parent)
        self.parent = parent
        width, height = self.parent.GetSize()
        self.SetRect((0, 0, width, 297))
        self.tutorials = [filename for filename in os.listdir(packages)
                          if filename.startswith("tutorial") and filename.endswith("png")]
        self.maxpage = len(self.tutorials)
        self.current_page = 0
        self.image = None
        self.DiaplayImage(0)

    def DiaplayImage(self, page):
        if self.image is not None:
            self.image.Destroy()
        path = os.path.join(packages, self.tutorials[page])
        data = open(path, "rb").read()
        stream = StringIO.StringIO(data)
        bmp = wx.BitmapFromImage(wx.ImageFromStream(stream))
        width, height = self.GetSize()
        self.image = wx.StaticBitmap(self, -1, bmp, pos=(-3, -3), size=(width, height))
        label = '%d / %s' % (self.current_page + 1, self.maxpage)
        width, height = self.parent.GetSize()
        if hasattr(self, 'text') is False:
            self.text = StaticText(self.parent, pos=(width - 310, height - 63))
            self.text.SetDoubleBuffered(True)
        self.text.SetLabelText(label)

    def OnPrev(self, event):
        self.current_page -= 1
        if self.current_page < 0:
            self.current_page = self.maxpage - 1
        self.DiaplayImage(self.current_page)

    def OnNext(self, event):
        self.current_page += 1
        if self.current_page > self.maxpage - 1:
            self.current_page = 0
        self.DiaplayImage(self.current_page)

    def OnClose(self, event):
        self.Destroy()


class TutorialBox(DialogBox):

    def __init__(self, parent):
        DialogBox.__init__(self, parent, size=(536, 380))
        self.parent = parent
        self.SetTitle('Tutorial')
        self.TutorialPanel = TutorialPanel(self)
        self.InitButtons()
        self.Centre()
        self.Show(True)

    def InitButtons(self):
        width, height = self.GetSize()
        self.StartUpShowCheck = CheckBox(self,
                                         label=' Show me on start up', pos=(20, height - 64))
        if GetPreference('tutotial_show'):
            self.StartUpShowCheck.SetValue(1)
        self.StartUpShowCheck.Bind(wx.EVT_CHECKBOX, self.OnStartUpShowCheck)
        # if self.preference.auto_save_tag: self.StartUpShowCheck.SetValue(1)
        self.PrevButton = Button(self,
                                 label='Prev', pos=(width - 95 - 80 - 80, height - 68))
        self.PrevButton.Bind(wx.EVT_BUTTON, self.OnPrev)
        self.NextButton = Button(self,
                                 label='Next', pos=(width - 95 - 80, height - 68))
        self.NextButton.Bind(wx.EVT_BUTTON, self.OnNext)
        self.CloseButton = Button(self,
                                  label='Close', pos=(width - 95, height - 68))
        self.CloseButton.Bind(wx.EVT_BUTTON, self.OnClose)

    def OnStartUpShowCheck(self, event):
        SetPreference('tutotial_show', event.IsChecked())

    def OnPrev(self, event):
        self.TutorialPanel.OnPrev(event)

    def OnNext(self, event):
        self.TutorialPanel.OnNext(event)

    def OnClose(self, event):
        self.Destroy()


class MacroBoxMenuBar():

    def __init__(self):
        self.MenuBar = MenuBar(self)
        # self.SetMenuBar(self.MenuBar)
        self.default_style = self.GetWindowStyle()
        self.Bind(wx.EVT_MENU, self.OnExportTracklist, self.MenuBar.itemExportTracklist)
        self.Bind(wx.EVT_MENU, self.OnImportTracks, self.MenuBar.itemImportTracks)
        self.Bind(wx.EVT_MENU, self.OnExit, self.MenuBar.itemExit)
        self.Bind(wx.EVT_MENU, self.OnAlwaysOnTop, self.MenuBar.itemAlwaysOnTop)
        self.Bind(wx.EVT_MENU, self.OnAutoAnalyze, self.MenuBar.itemAutoAnalyze)
        self.Bind(wx.EVT_MENU, self.OnCheckItemsConsistency, self.MenuBar.itemCheckItemsConsistency)
        self.Bind(wx.EVT_MENU, self.OnPlayerTopShow, self.MenuBar.itemPlayerTopShow)
        self.Bind(wx.EVT_MENU, self.OnPlayerSideShow, self.MenuBar.itemPlayerSideShow)
        self.Bind(wx.EVT_MENU, self.OnPreference, self.MenuBar.itemPreference)
        # self.Bind(wx.EVT_MENU, self.OnScriptEditor, self.MenuBar.itemScriptEditor)
        # self.Bind(wx.EVT_MENU, self.OnHelp, self.MenuBar.itemHelp)
        self.Bind(wx.EVT_MENU, self.OnUpdate, self.MenuBar.itemUpdate)
        # self.Bind(wx.EVT_MENU, self.OnLicense, self.MenuBar.itemLicense)
        self.Bind(wx.EVT_MENU, self.OnAbout, self.MenuBar.itemAbout)
        self.Bind(wx.EVT_MENU, self.OnMenuBar, self.MenuBar)

    # def OnScriptEditor(self, event):
    #     if hasattr(self, 'ScriptEditorBox'):
    #         if hasattr(self.ScriptEditorBox, 'EditorPanel'):
    #             return
    #     self.ScriptEditorBox = ScriptEditorBox(self)
    #     x, y, w, h = self.GetRect()
    #     width, height = self.ScriptEditorBox.GetSize()
    #     self.ScriptEditorBox.SetRect(
    #         (x + (w - width) / 2, y + (h - height) / 2, width, height))
    #     self.ScriptEditorBox.Show()
    #     self.MainPanel.ListBox.reInitBuffer = True

    def OnMenuBar(self, event):
        pass
        # if self.MainPanel.ListBox.List.TextEdit is not None:
        #     self.MainPanel.ListBox.List.TextEdit.destroy = True
        # if self.MainPanel.ListTab.TextEdit is not None:
        #     self.MainPanel.ListTab.TextEdit.destroy = True
        event.Skip()

    def OnImportTracks(self, event):
        # if self.IsTextEditTurnedOn(): return
        cwd = os.getcwd()
        self.DialogBox = FileOpenDialog(self.MainPanel.ListTab)
        self.DialogBox.ShowModal()
        os.chdir(cwd)  # only works with windows, linux
        paths = self.DialogBox.GetPaths()
        self.MainPanel.ListBox.List.FileDrop.DropFromOutside(paths)
        self.DialogBox.Destroy()
        self.DialogBox = None
        self.MainPanel.ListBox.reInitBuffer = True

    def OnExportTracklist(self, event):
        # if self.IsTextEditTurnedOn(): return
        cwd = os.getcwd()
        self.DialogBox = FileSaveDialog(self.MainPanel.ListTab)
        self.DialogBox.ShowModal()
        os.chdir(cwd)  # only works with windows, linux
        savepath = self.DialogBox.GetPath()
        self.DialogBox.Destroy()
        self.DialogBox = None
        selectedList = self.MainPanel.ListBox.selectedList
        pathIdx = self.MainPanel.ListBox.GetColumnKeyToIdx('path', selectedList)
        paths = map(itemgetter(pathIdx), self.MainPanel.ListBox.innerList[selectedList].items)
        try:
            audio.generate_m3u(savepath, paths)
        except Exception:
            pass
        self.MainPanel.ListBox.reInitBuffer = True

    def OnPlayerSideShow(self, event):
        if event.IsChecked():
            self.SetPlayerSideShowOn()
        else:
            self.SetPlayerSideShowOff()

    def ColorThemeMap(self):
        color_themes = list()
        for v in (5, 20, 40, 60, 80, 100, 150, 170, 190, 210, 230, 250):
            color_themes.append((v, v, v, 255))
        return color_themes

    def ColorThemeId2RGB(self, idx):
        return self.ColorThemeMap()[idx]

    def ColorThemeRGB2Id(self, rgb):
        return [i for i, v in enumerate(self.ColorThemeMap()) if v == rgb][0]

    def SetColorThemeById(self, idx):
        rgb = self.ColorThemeId2RGB(idx)
        self.SetColorThemeByRGB(rgb)

    def SetColorThemeByRGB(self, rgb):
        self.MainPanel.ListBox.SetBackgroundColour(rgb)
        self.MainPanel.ListBox.List.SetBackgroundColour(rgb)
        self.MainPanel.ListBox.SliderV.SetBackgroundColour(rgb)
        self.MainPanel.ListBox.SliderH.SetBackgroundColour(rgb)
        color_theme_id = self.ColorThemeRGB2Id(rgb)
        SetPreference('color_theme', color_theme_id)
        for i in range(len(self.MenuBar.itemColorThemeMenu.MenuItems)):
            if i == color_theme_id:
                self.MenuBar.itemColorThemeMenu.MenuItems[i].Check()
            else:
                self.MenuBar.itemColorThemeMenu.MenuItems[i].Check(False)

    def OnPlayerTopShow(self, event):
        if event.IsChecked():
            self.SetPlayerTopShowOn()
        else:
            self.SetPlayerTopShowOff()

    def OnPlayerOnly(self, event):
        if event.IsChecked():
            self.SetPlayerOnlyModeOn()
        else:
            self.SetPlayerOnlyModeOff()

    # def OnAppearance(self, event):
    #     self.DialogBox = AppearanceBox(self)
    #     x, y, w, h = self.GetRect()
    #     width, height = self.DialogBox.GetSize()
    #     self.DialogBox.SetRect(
    #         (x + (w - width) / 2, y + (h - height) / 2, width, height))
    #     self.DialogBox.ShowModal()
    #     self.DialogBox = None
    #     self.MainPanel.ListBox.reInitBuffer = True

    def OnAbout(self, event):
        self.DialogBox = AboutBox(None)
        x, y, w, h = self.GetRect()
        width, height = self.DialogBox.GetSize()
        self.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.DialogBox.ShowModal()
        self.DialogBox = None
        self.MainPanel.ListBox.reInitBuffer = True

    def OnPreference(self, event):
        self.DialogBox = PreferenceBox(self)
        x, y, w, h = self.GetRect()
        width, height = self.DialogBox.GetSize()
        self.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.DialogBox.ShowModal()
        self.DialogBox = None
        self.MainPanel.ListBox.reInitBuffer = True

    # def OnLicense(self, event):
    #     self.DialogBox = LicenseBox(self)
    #     x, y, w, h = self.GetRect()
    #     width, height = self.DialogBox.GetSize()
    #     self.DialogBox.SetRect(
    #         (x + (w - width) / 2, y + (h - height) / 2, width, height))
    #     self.DialogBox.ShowModal()
    #     self.DialogBox = None
    #     self.MainPanel.ListBox.reInitBuffer = True

    def OnUpdate(self, event):
        self.DialogBox = UpdateBox(None)
        x, y, w, h = self.GetRect()
        width, height = self.DialogBox.GetSize()
        self.DialogBox.SetRect(
            (x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.DialogBox.ShowModal()
        self.DialogBox = None
        self.MainPanel.ListBox.reInitBuffer = True

    def OnHelp(self, event):
        self.RedirecUrl(PRODUCT_ONLINE_HELP_URL)

    def RedirecUrl(self, url):
        webbrowser.open(url)

    def OnShowSpectrum(self, event):
        pass

    def OnExit(self, event):
        self.Close()

    def OnAlwaysOnTop(self, event):
        if event.IsChecked():
            self.SetAlwaysOnTopOn()
        else:
            self.SetAlwaysOnTopOff()

    def OnAutoAnalyze(self, event):
        if event.IsChecked():
            self.MainPanel.MFEATS.SetAutoAnalyzerOn()
            self.MainPanel.MFEATS.AutoAnalyzer()
        else:
            self.MainPanel.MFEATS.SetAutoAnalyzerOff()

    def OnCoreNumber(self, event):
        procs_limit = event.Id - 100
        self.LimitCoreNumber(procs_limit)

    def LimitCoreNumber(self, procs_limit):
        self.MainPanel.MFEATS.SetProcsLimit(procs_limit)

    def OnHighlightDuration(self, event):
        dutaionTypeId = event.Id - 201
        value = [v for i, v in enumerate(
            self.MenuBar.highlightDurationItems) if dutaionTypeId == i][0]
        self.MainPanel.PlayBox.SetBestHighlightVariablePeriodTime(static=value)
        if self.MainPanel.PlayBox.IsPlaying()\
                and self.MainPanel.PlayBox.IsHighlightOn():
            self.MainPanel.PlayBox.GotoTrackOffsetTime()
            self.MainPanel.PlayBox.reInitWave = True
            self.MainPanel.PlayBox.OnSize()
        elif self.MainPanel.PlayBox.IsHighlightOn():
            self.MainPanel.PlayBox.GotoTrackOffsetTime()
            self.MainPanel.PlayBox.reInitWave = True
            self.MainPanel.PlayBox.OnSize()
        for i in range(len(self.MenuBar.highlightDurationItems)):
            if i == dutaionTypeId:
                self.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check()
            else:
                self.MenuBar.itemHighlightDurationMenu.MenuItems[i].Check(False)

    def OnKeyFormat(self, event):
        for i in range(len(self.MenuBar.itemKeyFormatMenu.MenuItems)):
            if event.Id == i:
                continue
            self.MenuBar.itemKeyFormatMenu.MenuItems[i].Check(False)

    def OnCheckItemsConsistency(self, event):
        self.DialogBox = CheckItemsConsistencyConfirmBox(self)
        x, y, w, h = self.GetRect()
        width, height = self.DialogBox.GetSize()
        self.DialogBox.SetRect((x + (w - width) / 2, y + (h - height) / 2, width, height))
        self.DialogBox.ShowModal()
        self.DialogBox = None
        self.MainPanel.ListBox.reInitBuffer = True

    def __del__(self):
        pass


class MenuBar(wx.MenuBar):

    def __init__(self, parent):
        wx.MenuBar.__init__(self)
        self.parent = parent
        self.InitMenuFile()
        self.InitMenuView()
        self.InitMenuOption()
        self.InitMenuHelp()

    def InitMenuFile(self):
        self.menuFile = wx.Menu()

        self.itemImportTracks = wx.MenuItem(
            self.menuFile, wx.ID_ANY, u'Import Tracks', wx.EmptyString, wx.ITEM_NORMAL)
        self.menuFile.Append(self.itemImportTracks)

        self.itemExportTracklist = wx.MenuItem(
            self.menuFile, wx.ID_ANY, u'Export Tracklist', wx.EmptyString, wx.ITEM_NORMAL)
        self.menuFile.Append(self.itemExportTracklist)

        self.menuFile.AppendSeparator()

        self.itemExit = wx.MenuItem(self.menuFile, wx.ID_ANY, u'Quit', wx.EmptyString, wx.ITEM_NORMAL)
        self.menuFile.Append(self.itemExit)

        self.Append(self.menuFile, u'File')

    def InitMenuView(self):
        self.menuView = wx.Menu()

        self.itemPlayerTopShow = wx.MenuItem(self.menuView, wx.ID_ANY, '&Spectrum', wx.EmptyString, wx.ITEM_CHECK)
        if self.parent.IsPlayerTopShowOn():
            self.itemPlayerTopShow.check()
        self.menuView.Append(self.itemPlayerTopShow)

        self.itemPlayerSideShow = wx.MenuItem(self.menuView, wx.ID_ANY, 'Album Image', wx.EmptyString, wx.ITEM_CHECK)
        if self.parent.IsPlayerSideShowOn():
            self.itemPlayerSideShow.check()
        self.menuView.Append(self.itemPlayerSideShow)

        # self.menuView.AppendSeparator()

        # self.itemScriptEditor = wx.MenuItem(self.menuView,\
        #   wx.ID_ANY, u'Script Editor', wx.EmptyString, wx.ITEM_NORMAL)
        # self.menuView.Append(self.itemScriptEditor)

        self.Append(self.menuView, u"View")

    def InitMenuOption(self):
        self.menuOption = wx.Menu()

        self.itemAlwaysOnTop = wx.MenuItem(
            self.menuOption, wx.ID_ANY, u'Always On Top\tCtrl+T', wx.EmptyString, wx.ITEM_CHECK)
        self.menuOption.Append(self.itemAlwaysOnTop)

        self.menuOption.AppendSeparator()

        self.itemHighlightDurationMenu = wx.Menu()
        self.highlightDurationItems = [8, 16, 32, 48, 64]
        for i, item in enumerate(self.highlightDurationItems):
            title = '%2dbar (Approx %2dseconds)' % (item * 2 / 4, item)
            self.itemHighlightDurationMenu.Append(wx.MenuItem(
                self.itemHighlightDurationMenu, 200 + i + 1, title, wx.EmptyString, wx.ITEM_CHECK))
            self.parent.Bind(wx.EVT_MENU, self.parent.OnHighlightDuration, self.itemHighlightDurationMenu.MenuItems[i])
        # value = self.parent.MainPanel.PlayBox.GetHighlightStaticPeriodTime()
        # idx = [i for i, v in enumerate(self.highlightDurationItems) if value == v][0]
        self.menuOption.Append(wx.ID_ANY, u'Highlight Duration', self.itemHighlightDurationMenu)
        self.menuOption.AppendSeparator()

        self.itemAutoAnalyze = wx.MenuItem(self.menuOption, wx.ID_ANY, u'Auto Analyze', wx.EmptyString, wx.ITEM_CHECK)
        self.menuOption.Append(self.itemAutoAnalyze)
        if self.parent.MainPanel.MFEATS.IsAutoAnalyzerOn():
            self.itemAutoAnalyze.Check()

        self.itemCheckItemsConsistency = wx.MenuItem(
            self.menuOption, wx.ID_ANY, u'Check File Consistency', wx.EmptyString, wx.ITEM_NORMAL)
        self.menuOption.Append(self.itemCheckItemsConsistency)

        self.menuOption.AppendSeparator()

        self.itemPreference = wx.MenuItem(self.menuOption, wx.ID_ANY, u'Preference', wx.EmptyString, wx.ITEM_NORMAL)
        self.menuOption.Append(self.itemPreference)

        self.Append(self.menuOption, u"Option")

    def InitMenuHelp(self):
        self.menuHelp = wx.Menu()

        # self.itemHelp = wx.MenuItem(self.menuHelp, wx.ID_ANY, u'Help', wx.EmptyString, wx.ITEM_NORMAL)
        # self.menuHelp.Append(self.itemHelp)

        # self.menuHelp.AppendSeparator()

        # self.itemLicense = wx.MenuItem(self.menuHelp,\
        #   wx.ID_ANY, u'License', wx.EmptyString, wx.ITEM_NORMAL)
        # self.menuHelp.Append(self.itemLicense)

        self.itemUpdate = wx.MenuItem(self.menuHelp, wx.ID_ANY, u'Check for Update', wx.EmptyString, wx.ITEM_NORMAL)
        self.menuHelp.Append(self.itemUpdate)

        self.menuHelp.AppendSeparator()

        self.itemAbout = wx.MenuItem(self.menuHelp, wx.ID_ANY, u'About MACROBOX', wx.EmptyString, wx.ITEM_NORMAL)
        self.menuHelp.Append(self.itemAbout)

        self.Append(self.menuHelp, u'Help')

    def __del__(self):
        pass
