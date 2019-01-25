# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


import gc
import json
import random
import socket
import time
import urllib
import wx

from utilities import string2md5
# from license import generate_code
# from macroboxlib import MACROBOX_BUY_URL
# from macroboxlib import PRODUCT_LICENSE_CHECK_URL
# from macroboxlib import PRODUCT_LOG_REQUEST_URL
# from macroboxlib import TextCtrl
# from utilities import Struct
# from utilities import compress_object
# from utilities import decompress_object
# from utilities import get_hostname
# from utilities import get_macaddress
# from utilities import struct_to_dict
# from macroboxlib import *
# from scripteditor import *
# from listbox import FileOpenDialog
# from listbox import FileSaveDialog
# import hashlib
# import urllib2
# from utilities import get_hostname
# from utilities import get_macaddress
# from utilities import get_external_ip


def get_table(num=True, upper=True, lower=True):
    table = list()
    if num:
        for i in range(48, 58):
            table.append(str(unichr(i)))
    if upper:
        for i in range(65, 91):
            table.append(str(unichr(i)))
    if lower:
        for i in range(97, 123):
            table.append(str(unichr(i)))
    return table


def string2longhex(seed, length):
    code = string2md5(seed)
    longhex = list()
    for i in range(length / 32 + 1):
        code = string2md5(code)
        longhex.append(code)
    return ''.join(longhex)[:length]


def string2longdec(seed, length):
    longhex = string2longhex(seed, length)
    longdec = str(int(longhex, 16))
    return longdec[:length]


def rotate_table(table, seed):
    table_length = len(table)  # 62
    order = int(string2longdec(seed, 64)) % table_length
    table = table[order:] + table[:order]
    table = ''.join(table)
    return table


def get_rotated_table(seed, num=True, upper=True, lower=True):
    table = get_table(num=num, upper=upper, lower=lower)
    return rotate_table(table, seed)


def generate_code(seed, length=64, num=True, upper=True, lower=True):
    longdec = string2longdec(seed, length * 4)
    table = get_rotated_table(seed, num=num, upper=upper, lower=lower)
    table_length = len(table)
    y = list()
    for i in range(0, len(longdec), 4):
        x = int(longdec[i:i + 4]) % table_length
        y.append(table[x])
    return ''.join(y)


def generate_license_code(seed, length=64):
    return generate_code(seed, length=64)


def is_valid_license(seed, code):
    if code != generate_license_code(seed):
        return False
    return True


def generate_random_code(length, num=True, upper=True, lower=True):
    table = ''.join(get_table(num=num, upper=upper, lower=lower))
    code = [random.choice(table) for v in range(length)]
    return ''.join(code)


def generate_random_seeded_code(seed, length, num=True, upper=True, lower=True):
    table = ''.join(get_rotated_table(seed, num=num, upper=upper, lower=lower))
    code = [random.choice(table) for v in range(length)]
    return ''.join(code)


def request_code(email, publickey, product, device, url):
    socket.setdefaulttimeout(5)
    values = {
        'email': email,
        'publickey': publickey,
        'product': product,
        'device': device}
    try:
        data = urllib.urlencode(values)
        req = urllib2.Request(url, data)
        response = urllib2.urlopen(req)
        result = response.read()
        result = json.loads(result)
    except Exception:
        result = None
    return result


def generate_secretkey(email, publickey, product, macaddress):
    seed = ''.join((email, publickey, product, macaddress))
    return generate_license_code(seed)


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
        except Exception:
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
        except Exception:
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
        #   r, g, b = self.DecColor(self.bgcolor)
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


if __name__ == '__main__':
    pass
