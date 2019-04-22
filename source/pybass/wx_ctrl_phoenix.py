# Copyright Max Kolosov 2009-2013 pyirrlicht@gmail.com
# http://pybass.sf.net
# BSD license


import pybass
import sys


try:
    import pybassmidi
except Exception:
    pybassmidi = None


try:
    from exe import wx
except Exception:
    import wx


from wx.lib.ticker import Ticker


def print_error():
    exc, err, traceback = sys.exc_info()
    print('%s %s ERROR ON LINE %d %s\n' % (exc, traceback.tb_frame.f_code.co_filename, traceback.tb_lineno, err))
    del exc, err, traceback


class memory_stream:

    def __init__(self, data, name='memory_stream'):
        self.name = name
        self.current_position = 0
        self.data = data
        self.end_position = len(self.data) - 1
        self.decode_length = 0
        self.seconds = 0

    def read(self, size=1024):
        result = ''
        if self.current_position is not self.end_position and size > 0:
            last_index = self.current_position + size
            if last_index > self.end_position:
                last_index = self.end_position
            result = self.data[self.current_position: last_index]
            self.current_position = last_index
        return result

    def write(self, value=''):
        self.data += value

    def seek(self, position, whence=0):
        if whence is 0:
            if position <= self.end_position:
                self.current_position = position
        elif whence is 1:
            if position + self.current_position <= self.end_position:
                self.current_position += position
        elif whence is 2:
            if position < 0:
                position *= -1
            if self.end_position - position > 0:
                self.current_position = self.end_position - position

    def tell(self):
        return self.current_position

    def isatty(self):
        return 1

    def flush(self):
        pass

    def is_eof(self):
        return self.current_position == self.end_position


class slider_ctrl(wx.Slider):

    def __init__(self, *args, **kwargs):
        self.timer_interval = 500
        self.player_ctrl = args[0]
        wx.Slider.__init__(self, *args, **kwargs)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_LEFT_DOWN, self.event_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.event_left_up)
        self.Bind(wx.EVT_TIMER, self.event_timer)

    def __del__(self):
        if hasattr(self, 'timer'):
            self.timer.Stop()

    def timer_start(self):
        if not self.timer.IsRunning():
            self.timer.Start(self.timer_interval)

    def timer_stop(self):
        if self.timer.IsRunning():
            self.timer.Stop()

    def event_timer(self, event):
        if self.player_ctrl.method_get_position() < self.player_ctrl.method_get_length() - 1:
            self.SetValue(self.player_ctrl.method_get_position())
        else:
            self.player_ctrl.method_stop_audio()

    def event_left_down(self, event):
        self.timer_stop()
        event.Skip()

    def event_left_up(self, event):
        self.player_ctrl.method_set_position(self.GetValue())
        self.timer_start()
        event.Skip()


class player_ctrl(wx.Panel):

    def __init__(self, *args, **kwargs):

        self.stream = kwargs.pop('stream', None)
        self.name_stream = kwargs.pop('name_stream', 'memory_stream')
        self.bass_handle = 0
        self.sound_font = 0

        result = pybass.BASS_Init(-1, 44100, 0, 0, 0)
        if not result:
            bass_error_code = pybass.BASS_ErrorGetCode()
            if bass_error_code != pybass.BASS_ERROR_ALREADY:
                self.slider.Enable(False)
                self.btn_play.Enable(False)
                self.btn_stop.Enable(False)
                print('BASS_Init error %s' % pybass.get_error_description(bass_error_code))
        self.plugins = {}
        self.plugins['aac'] = (pybass.BASS_PluginLoad('bass_aac.dll', 0), '|AAC|*.aac')
        self.plugins['ac3'] = (pybass.BASS_PluginLoad('bass_ac3.dll', 0), '|AC3|*.ac3')
        self.plugins['aix'] = (pybass.BASS_PluginLoad('bass_aix.dll', 0), '|AIX|*.aix')
        self.plugins['ape'] = (pybass.BASS_PluginLoad('bass_ape.dll', 0), '|APE|*.ape')
        self.plugins['mpc'] = (pybass.BASS_PluginLoad('bass_mpc.dll', 0), '|MPC|*.mpc')
        self.plugins['ofr'] = (pybass.BASS_PluginLoad('bass_ofr.dll', 0), '|OFR|*.ofr')
        self.plugins['spx'] = (pybass.BASS_PluginLoad('bass_spx.dll', 0), '|SPX|*.spx')
        self.plugins['tta'] = (pybass.BASS_PluginLoad('bass_tta.dll', 0), '|TTA|*.tta')
        self.plugins['cda'] = (pybass.BASS_PluginLoad('basscd.dll', 0), '|CDA|*.cda')
        self.plugins['flac'] = (pybass.BASS_PluginLoad('bassflac.dll', 0), '|FLAC|*.flac')
        self.plugins['wma'] = (pybass.BASS_PluginLoad('basswma.dll', 0), '|WMA, WMV|*.wma;*.wmv')
        if pybassmidi:
            sound_font_file_name = 'CT4MGM.SF2'
            self.sound_font = pybassmidi.BASS_MIDI_FontInit(sound_font_file_name, 0)
            if self.sound_font == 0:
                print('BASS_MIDI_FontInit error %s (sound font file must be %s)' %
                      (pybass.get_error_description(pybass.BASS_ErrorGetCode()), sound_font_file_name))
            else:
                self.plugins['midi'] = (pybass.BASS_PluginLoad('bassmidi.dll', 0), '|MID|*.mid')
        else:
            print('pybassmidi module not accessible')

        wx.Panel.__init__(self, *args, **kwargs)

        sizer_h = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_play = wx.Button(self, wx.ID_ANY, _('Play'), style=wx.NO_BORDER)
        self.btn_play.SetToolTip(_('Play media data'))
        self.Bind(wx.EVT_BUTTON, self.event_play, self.btn_play)
        sizer_h.Add(self.btn_play)

        self.btn_stop = wx.Button(self, wx.ID_ANY, _('Stop'), style=wx.NO_BORDER)
        self.Bind(wx.EVT_BUTTON, self.event_stop, self.btn_stop)
        sizer_h.Add(self.btn_stop)

        self.btn_open = wx.Button(self, wx.ID_OPEN, _('Open'), style=wx.NO_BORDER)
        self.Bind(wx.EVT_BUTTON, self.event_open, self.btn_open)
        sizer_h.Add(self.btn_open)

        sizer_v = wx.BoxSizer(wx.VERTICAL)

        self.status_line = Ticker(self, fgcolor='#000062', bgcolor='#7F7F8F',
                                  start=False, ppf=1, fps=50, direction='ltr')
        sizer_v.Add(self.status_line, 0, wx.EXPAND)

        self.slider = slider_ctrl(self, wx.ID_ANY, 0, 0, 1)
        sizer_v.Add(self.slider, 0, wx.EXPAND)

        sizer_v.Add(sizer_h)

        self.SetSizer(sizer_v)
        self.SetAutoLayout(True)

        self.volume_slider = wx.Slider(self, wx.ID_ANY, pybass.BASS_GetVolume() * 100, 0, 100)
        self.Bind(wx.EVT_SCROLL, self.event_volume_slider, self.volume_slider)
        sizer_h.Add(self.volume_slider, 0, wx.EXPAND)

        self.method_check_controls()

    def method_load_file(self):
        import os
        wildcard = 'music sounds (MO3, IT, XM, S3M, MTM, MOD, UMX)|*.mo3;*.it;*.xm;*.s3m;*.mtm;*.mod;*.umx'
        wildcard += '|stream sounds (MP3, MP2, MP1, OGG, WAV, AIFF)|*.mp3;*.mp2;*.mp1;*.ogg;*.wav;*.aiff'
        for plugin in self.plugins.itervalues():
            if plugin[0] > 0:
                wildcard += plugin[1]
        wildcard += '|All files (*.*)|*.*'
        dlg = wx.FileDialog(self, message=_('Choose a file'), defaultDir=os.getcwd(),
                            defaultFile='', wildcard=wildcard, style=wx.FD_OPEN | wx.FD_CHANGE_DIR)
        if dlg.ShowModal() == wx.ID_OK:
            self.name_stream = file_name = dlg.GetPath()
            if os.path.isfile(file_name):
                flags = 0
                if isinstance(file_name, unicode):
                    flags |= pybass.BASS_UNICODE
                    try:
                        pybass.BASS_CHANNELINFO._fields_.remove(('filename', pybass.ctypes.c_char_p))
                    except Exception:
                        pass
                    else:
                        pybass.BASS_CHANNELINFO._fields_.append(('filename', pybass.ctypes.c_wchar_p))
                error_msg = 'BASS_StreamCreateFile error %s'
                new_bass_handle = 0
                if dlg.GetFilterIndex() == 0:  # BASS_CTYPE_MUSIC_MOD
                    flags |= pybass.BASS_MUSIC_PRESCAN
                    new_bass_handle = pybass.BASS_MusicLoad(False, file_name, 0, 0, flags, 0)
                    error_msg = 'BASS_MusicLoad error %s'
                else:  # other sound types
                    new_bass_handle = pybass.BASS_StreamCreateFile(False, file_name, 0, 0, flags)
                if new_bass_handle == 0:
                    print(error_msg % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
                else:
                    self.method_stop_audio()
                    self.bass_handle = new_bass_handle
                    self.stream = None
                    self.method_slider_set_range()
                    self.method_check_controls()

    def method_load_wav_file(self):
        import os
        wildcard = 'wav (*.wav)|*.wav|All files (*.*)|*.*'
        dlg = wx.FileDialog(self, message=_('Choose a file'), defaultDir=os.getcwd(),
                            defaultFile='', wildcard=wildcard, style=wx.OPEN | wx.CHANGE_DIR)
        if dlg.ShowModal() == wx.ID_OK:
            self.name_stream = file_name = dlg.GetPath()
            if os.path.isfile(file_name):
                flags = 0
                if isinstance(file_name, unicode):
                    flags |= pybass.BASS_UNICODE
                    try:
                        pybass.BASS_CHANNELINFO._fields_.remove(('filename', pybass.ctypes.c_char_p))
                    except Exception:
                        pass
                    else:
                        pybass.BASS_CHANNELINFO._fields_.append(('filename', pybass.ctypes.c_wchar_p))

                def stream_callback(handle, buffer, length, user):
                    b = pybass.ctypes.cast(buffer, pybass.ctypes.c_char_p)
                    pybass.ctypes.memset(b, 0, length)
                    data = pybass.ctypes.c_char_p(self.stream.read(length))
                    pybass.ctypes.memmove(b, data, length)
                    if self.stream.is_eof():
                        length |= pybass.BASS_STREAMPROC_END
                        self.stream.current_position = 0
                    return length
                self.stream_callback = stream_callback
                self.user_func = pybass.STREAMPROC(self.stream_callback)
                self.stream = memory_stream(open(file_name, 'rb').read(), file_name)
                new_bass_handle = pybass.BASS_StreamCreate(44100, 2, flags, self.user_func, 0)
                if new_bass_handle == 0:
                    print('BASS_StreamCreate error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
                else:
                    self.method_stop_audio()
                    self.bass_handle = new_bass_handle
                    self.stream = None
                    self.method_slider_set_range()
                    self.method_check_controls()

    def method_load_data(self, stream, name_stream='memory_stream'):
        if stream is not None:
            if isinstance(stream, (str, list, tuple, buffer)):
                self.stream = memory_stream(stream, name_stream)
            else:
                self.stream = stream
            if isinstance(self.stream, memory_stream):
                system = pybass.STREAMFILE_BUFFER
                flags = 0

                def callback_close(user):
                    self.stream.current_position = 0
                self.callback_close = callback_close

                def callback_length(user):
                    return len(self.stream.data)
                self.callback_length = callback_length

                def callback_read(buffer, length, user):
                    b = pybass.ctypes.cast(buffer, pybass.ctypes.c_char_p)
                    pybass.ctypes.memset(b, 0, length)
                    data = pybass.ctypes.c_char_p(self.stream.read(length))
                    pybass.ctypes.memmove(b, data, length)
                    return length
                self.callback_read = callback_read

                def callback_seek(offset, user):
                    self.stream.seek(offset)
                    return True
                self.callback_seek = callback_seek
                self.bass_file_procs = pybass.BASS_FILEPROCS()
                self.bass_file_procs.close = pybass.FILECLOSEPROC(self.callback_close)
                self.bass_file_procs.length = pybass.FILELENPROC(self.callback_length)
                self.bass_file_procs.read = pybass.FILEREADPROC(self.callback_read)
                self.bass_file_procs.seek = pybass.FILESEEKPROC(self.callback_seek)
                new_bass_handle = pybass.BASS_StreamCreateFileUser(
                    system, flags, self.bass_file_procs, id(self.stream.data))
                if new_bass_handle == 0:
                    print('BASS_StreamCreateFileUser error %s' %
                          pybass.get_error_description(pybass.BASS_ErrorGetCode()))
                else:
                    self.method_stop_audio()
                    self.bass_handle = new_bass_handle
                    channel_info = self.method_get_channel_info()
                    if channel_info.ctype == pybass.BASS_CTYPE_STREAM_OGG:
                        import pyogginfo
                        ogg_info = pyogginfo.VorbisStreamInfo()
                        stream = pyogginfo.SimpleDemultiplexer(ogg_info)
                        if isinstance(self.stream.data, str):
                            stream.process(self.stream.data)
                        else:
                            stream.process(str(self.stream.data))
                        self.stream.decode_length = ogg_info.lastPosition
                        self.stream.seconds = ogg_info.stop
                        try:
                            for key, value in ogg_info.comments.comments:
                                if key == 'TITLE':
                                    if value.strip() > '':
                                        self.stream.name = value
                        except Exception:
                            pass
                    self.method_slider_set_range()
                    self.method_check_controls()

    def method_get_channel_info(self):
        channel_info = pybass.BASS_CHANNELINFO()
        if not pybass.BASS_ChannelGetInfo(self.bass_handle, channel_info):
            print('BASS_ChannelGetInfo error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
        return channel_info

    def method_get_state(self):
        return pybass.BASS_ChannelIsActive(self.bass_handle)

    def method_get_length(self):
        result = pybass.BASS_ChannelGetLength(self.bass_handle, pybass.BASS_POS_BYTE)
        if result <= 0 and isinstance(self.stream, memory_stream):
            result = self.stream.decode_length
        return result

    def method_get_position(self):
        return pybass.BASS_ChannelGetPosition(self.bass_handle, pybass.BASS_POS_BYTE)

    def method_set_position(self, value):
        if not pybass.BASS_ChannelSetPosition(self.bass_handle, value, pybass.BASS_POS_BYTE):
            print('BASS_ChannelSetPosition error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))

    def method_slider_set_range(self):
        self.slider.SetRange(0, self.method_get_length())

    def method_check_controls(self):
        if self.bass_handle:
            self.slider.Enable(True)
            self.btn_play.Enable(True)
            if self.method_get_state() == pybass.BASS_ACTIVE_STOPPED:
                self.btn_stop.Enable(False)
            else:
                self.btn_stop.Enable(True)

            if hasattr(self.stream, 'name'):
                text = self.stream.name + ' (' + pybass.seconds_to_string(self.stream.seconds) + ')'
            else:
                # ~ channel_info = self.method_get_channel_info()
                # ~ text = channel_info.filename
                text = self.name_stream + ' (' + pybass.stream_length_as_hms(self.bass_handle) + ')'
            self.status_line.SetText(text)
            if self.status_line.GetText() != '':
                self.status_line.Start()
        else:
            self.slider.Enable(False)
            self.btn_play.Enable(False)
            self.btn_stop.Enable(False)
            if self.status_line.GetText() == '':
                if self.status_line.IsTicking():
                    self.status_line.Stop()

    def method_is_end(self):
        return self.method_get_state() == pybass.BASS_ACTIVE_STOPPED and self.method_get_position() == 0

    def method_play(self):
        if self.bass_handle:
            if self.method_get_state() in (pybass.BASS_ACTIVE_STOPPED, pybass.BASS_ACTIVE_PAUSED):
                if not pybass.BASS_ChannelPlay(self.bass_handle, False):
                    print('BASS_ChannelPlay error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
                else:
                    self.slider.timer_start()
                    self.btn_play.SetLabel(_('Pause'))
                    self.btn_stop.Enable(True)
            else:
                if not pybass.BASS_ChannelPause(self.bass_handle):
                    print('BASS_ChannelPause error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
                else:
                    self.slider.timer_stop()
                    self.btn_play.SetLabel(_('Unpause'))

    def event_volume_slider(self, event):
        pybass.BASS_SetVolume(event.GetPosition() / 100.0)

    def event_play(self, event):
        self.method_play()

    def event_open(self, event):
        self.method_load_file()

    def event_stop(self, event):
        self.method_stop_audio()

    def method_stop_audio(self):
        self.method_stop_audio_stream()
        self.btn_play.SetLabel(_('Play'))
        self.slider.SetValue(0)
        self.btn_stop.Enable(False)

    def method_stop_audio_stream(self):
        self.slider.timer_stop()
        if self.bass_handle:
            if not pybass.BASS_ChannelStop(self.bass_handle):
                print('BASS_ChannelStop error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
            else:
                self.method_set_position(0)

    def method_free_handle(self):
        if self.bass_handle:
            channel_info = self.method_get_channel_info()
            if channel_info.ctype >= pybass.BASS_CTYPE_MUSIC_MOD:
                if not pybass.BASS_MusicFree(self.bass_handle):
                    print('BASS_MusicFree error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
                else:
                    self.bass_handle = 0
            elif channel_info.ctype >= pybass.BASS_CTYPE_STREAM:
                if not pybass.BASS_StreamFree(self.bass_handle):
                    print('BASS_StreamFree error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
                else:
                    self.bass_handle = 0

    def method_reset(self):
        self.method_free_handle()
        self.status_line.SetText('')
        self.method_check_controls()

    def __del__(self):
        self.method_free_handle()
        if self.sound_font != 0 and pybassmidi:
            if pybassmidi.BASS_MIDI_FontFree(self.sound_font):
                print('BASS_MIDI_FontFree error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))
        for plugin in self.plugins.itervalues():
            if plugin[0] > 0:
                if pybass.BASS_PluginFree(plugin[0]):
                    print('BASS_PluginFree error %s' % pybass.get_error_description(pybass.BASS_ErrorGetCode()))


if __name__ == '__main__':
    import os
    import gettext
    from locale import getdefaultlocale, setlocale, LC_ALL
    from wx.lib.agw.aui import AuiManager
    from wx.lib.agw.aui import AuiPaneInfo
    # from wx.lib.agw.aui import AuiToolBar
    # from wx.lib.agw.aui import AUI_TB_DEFAULT_STYLE
    # from wx.lib.agw.aui import AUI_TB_OVERFLOW
    from wx.html import HtmlHelpController
    setlocale(LC_ALL, '')

    class log_ctrl(wx.TextCtrl):

        def __init__(self, *args, **kwargs):
            self.file_name = kwargs.pop('file_name', 'log.txt')
            self.main_frame = kwargs.pop('main_frame', None)
            self.add_to_file = kwargs.pop('add_to_file', False)
            if self.main_frame is None:
                self.main_frame = args[0]
            super(log_ctrl, self).__init__(*args, **kwargs)

        def __write__(self, content):
            self.WriteText(content)

        def show_control(self, ctrl_name='log_ctrl'):
            if self.main_frame is not None:
                if hasattr(self.main_frame, 'aui_manager'):
                    self.main_frame.show_aui_pane_info(ctrl_name)
            self.SetInsertionPointEnd()
            if self.add_to_file:
                self.flush()

        def write(self, content):
            self.show_control()
            self.__write__(content)

        def writelines(self, l):
            self.show_control()
            map(self.__write__, l)

        def flush(self):
            self.SaveFile(self.file_name)

    class main_frame(wx.Frame):

        def __init__(self, *args, **kwargs):
            self.app = kwargs.pop('app', None)
            wx.Frame.__init__(self, *args, **kwargs)
            # =============== Logging Text Control ================
            self.log_ctrl = log_ctrl(self, style=wx.TE_MULTILINE, add_to_file=True)
            sys.stdout = self.log_ctrl
            sys.stderr = self.log_ctrl
            self.log = wx.LogTextCtrl(self.log_ctrl)
            self.log.SetLogLevel(wx.LOG_Error)
            # ~ wx.Log_SetActiveTarget(self.log)
            # =============== player Control ================
            self.player = player_ctrl(self)
            # =============== StatusBar ================
            statusbar = self.CreateStatusBar(2)
            statusbar.SetStatusWidths([-1, -1])
            statusbar.SetStatusText(_('Welcome into application!'), 0)
            # =============== AuiManager ================
            self.aui_manager = AuiManager()
            self.aui_manager.SetManagedWindow(self)
            self.aui_manager.AddPane(self.player, AuiPaneInfo().Name('player').CenterPane())
            self.aui_manager.AddPane(self.log_ctrl, AuiPaneInfo().Name(
                'log_ctrl').Bottom().Layer(0).BestSize((100, 100)).Hide())
            if self.log_ctrl.GetValue() != '':
                self.aui_manager.GetPane('log_ctrl').Show()
            self.aui_manager.Update()

        def DoUpdate(self):
            self.aui_manager.Update()

        def show_aui_pane_info(self, name):
            if not self.aui_manager.GetPane(name).IsShown():
                self.aui_manager.GetPane(name).Show()
            self.aui_manager.Update()

        def show_hide_aui_pane_info(self, name):
            if self.aui_manager.GetPane(name).IsShown():
                self.aui_manager.GetPane(name).Hide()
            else:
                self.aui_manager.GetPane(name).Show()
            self.aui_manager.Update()

    # ~ class application(wx.PySimpleApp):
    class application(wx.App):
        app_version = '0.4'
        app_path = os.getcwd()
        app_name = os.path.basename(sys.argv[0].split('.')[0])
        help_file = app_path + '/' + app_name + '.htb'
        settings_name = app_path + '/' + app_name + '.cfg'

        def start(self):
            result = True
            self.help_file = self.app_name + '.htb'
            # SETUP LANGUAGE
            lang_catalog = getdefaultlocale()[0]
            list_trans = []
            current_trans = -1
            i = 0
            if os.path.exists('lang/%s' % lang_catalog):
                for dir_name in os.listdir('lang'):
                    if os.path.exists('lang/%s/%s.mo' % (dir_name, self.app_name)):
                        if dir_name == lang_catalog:
                            current_trans = i
                            self.help_file = 'lang/' + dir_name + '/' + self.help_file
                        list_trans.append(gettext.GNUTranslations(
                            open('lang/%s/%s.mo' % (dir_name, self.app_name), 'rb')))
                        i += 1
                if len(list_trans) > 0:
                    try:
                        list_trans[current_trans].install(unicode=True)  # wx.USE_UNICODE
                    except Exception:
                        print_error()
            if current_trans == -1:
                trans = gettext.NullTranslations()
                trans.install(unicode=True)  # wx.USE_UNICODE
            # SETUP WX LANGUAGE TRANSLATION TO OS DEFAULT LANGUAGE
            # WX DIRECTORY MUST BE TO CONTAIN LANG DIRECTORY
            self.locale = wx.Locale(wx.LANGUAGE_DEFAULT)
            # CHECK EXISTS INSTANCE
            name_user = wx.GetUserId()
            name_instance = self.app_name + '::'
            self.instance_checker = wx.SingleInstanceChecker(name_instance + name_user)
            if self.instance_checker.IsAnotherRunning():
                wx.MessageBox(_('Software is already running.'), _('Warning'))
                return False
            # CREATE HTML HELP CONTROLLER
            # ~ wx.FileSystem.AddHandler(wx.ZipFSHandler())
            self.help_controller = HtmlHelpController()
            if os.path.exists(self.help_file):
                self.help_controller.AddBook(self.help_file)
            # ABOUT APPLICATION
            self.developers = [_('Maxim Kolosov')]
            self.copyright = _('(C) 2013 Max Kolosov')
            self.web_site = ('http://pybass.sf.net', _('Home page'))
            self.email = ('mailto:pyirrlicht@gmail.com', _('email for feedback'))
            self.license = _('BSD license')
            self.about_description = _('wxPython bass music player.')
            # CREATE MAIN FRAME
            self.main_frame = main_frame(None, wx.ID_ANY, self.app_name, app=self)
            self.SetTopWindow(self.main_frame)
            self.main_frame.Show()
            return result

        def OnExit(self):
            try:
                del self.instance_checker
            except Exception:
                print_error()

    app = application(0)
    if app.start():
        app.MainLoop()
    else:
        app.OnExit()
