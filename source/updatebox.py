# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import bisect
import macroboxstyle
import uikit
import wx

from macroboxlib import RectBox


CAPTIONS = {'skip': 'Skip this version', 'later': 'Later', 'cancel': 'Cancel'}
UPDATE_CAPTIONS = {'installer': 'Update now', 'git': 'Update now', 'page': 'Release page'}


def fit_text(gc, text, width):
    # cut with an ellipsis where it would run past width
    if width <= 0:
        return ''
    if gc.GetTextExtent(text)[0] <= width:
        return text
    room = width - gc.GetTextExtent('…')[0]
    count = bisect.bisect_right(gc.GetPartialTextExtents(text), room)
    return f'{text[:count].rstrip()}…' if count > 0 else ''


def wrap_text(gc, text, width):
    # a word wider than the line keeps a line of its own and is cut when drawn
    lines = []
    for paragraph in text.split('\n'):
        line = ''
        for word in paragraph.split(' '):
            trial = f'{line} {word}' if line else word
            if not line or gc.GetTextExtent(trial)[0] <= width:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


class UpdateBox(RectBox):

    '''newer release notice over the search row'''

    PAD = 8
    GAP = 8
    # the keys as tall as the search row's, on its rows
    KEY_HEIGHT = 21
    KEY_PAD = 14
    KEY_LEAST = 60
    MESSAGE_GAP = 12
    NOTES_GAP = 4
    LINE_ROW = 17
    NOTES_LINES = 6
    PROGRESS_WIDTH = 80
    PROGRESS_HEIGHT = 4
    SCROLL_WIDTH = 2

    def __init__(self, parent, on_action):
        RectBox.__init__(self, parent)
        self.on_action = on_action
        self.SetBackgroundColour(macroboxstyle.current().UI.BAR_BG)
        self.release = None
        self.version = ''
        # 'found', then 'busy' while updating and 'failed' with a message after an error
        self.state = 'found'
        self.message = ''
        self.progress = None
        self.lines = []
        self.top_line = 0
        self.wrapped_width = None
        self.stacked = False
        self.rects = []
        self.drawn = None
        # text extents from the renderer the box draws with
        self.measure = wx.GraphicsContext.Create()
        self.Hide()

    def ShowRelease(self, release, version):
        self.release = release
        self.version = version
        self.state = 'found'
        self.message = ''
        self.progress = None
        self.top_line = 0
        self.wrapped_width = None
        self.Show()
        self.PlaceParts()

    def HideRelease(self):
        self.release = None
        self.Hide()

    def SetBusy(self, message, progress=None):
        self.state = 'busy'
        self.message = message
        self.progress = progress
        self.PlaceParts()

    def SetFailed(self, message):
        self.state = 'failed'
        self.message = message
        self.progress = None
        self.PlaceParts()

    def GetButtons(self):
        if self.state == 'busy':
            # a pull cannot stop halfway
            return [('cancel', CAPTIONS['cancel'])] if self.progress is not None else []
        update = 'Retry' if self.state == 'failed' else UPDATE_CAPTIONS[self.release['kind']]
        return [('skip', CAPTIONS['skip']), ('later', CAPTIONS['later']), ('update', update)]

    def GetTitle(self):
        return f'PyMusicPlayer {self.release["version"]} is available'

    def GetMessage(self):
        return self.message or f'You have {self.version}'

    def GetTextWidth(self, font, text):
        uikit.set_font(self.measure, font, wx.BLACK)
        return self.measure.GetTextExtent(text)[0]

    def GetKeyWidths(self):
        font = uikit.get_font(10, bold=True)
        return [max(self.KEY_LEAST, round(self.GetTextWidth(font, caption)) + self.KEY_PAD * 2)
                for key, caption in self.GetButtons()]

    def IsStacked(self, width):
        # the keys under the notes when the title and its message would not fit beside them
        keys = sum(self.GetKeyWidths()) + self.GAP * len(self.GetButtons())
        title = self.GetTextWidth(uikit.get_font(12, bold=True), self.GetTitle())
        message = self.GetTextWidth(uikit.get_font(12), self.GetMessage())
        return self.PAD + title + self.MESSAGE_GAP + message + self.GAP + keys + self.PAD > width

    def Wrap(self, width):
        text_width = width - self.PAD * 2 - self.SCROLL_WIDTH * 3
        if text_width == self.wrapped_width:
            return
        self.wrapped_width = text_width
        notes = self.release['notes'] if self.release else ''
        uikit.set_font(self.measure, uikit.get_font(12), wx.BLACK)
        self.lines = wrap_text(self.measure, notes, text_width) if notes else []
        self.top_line = min(self.top_line, self.GetScrollLimit())

    def GetVisibleLines(self):
        return min(len(self.lines), self.NOTES_LINES)

    def GetScrollLimit(self):
        return max(0, len(self.lines) - self.NOTES_LINES)

    def GetHeight(self, width=None):
        # 0 while hidden: the list keeps the room
        if self.release is None or self.IsShown() is False:
            return 0
        width = self.GetParent().GetClientSize().width if width is None else width
        self.Wrap(width)
        self.stacked = self.IsStacked(width)
        height = 1 + self.PAD + self.KEY_HEIGHT
        if self.lines:
            height += self.NOTES_GAP + self.LINE_ROW * self.GetVisibleLines()
        if self.stacked and (self.GetButtons() or self.progress is not None):
            height += self.GAP + self.KEY_HEIGHT
        # a line over it and under it, apart from the player's control row and the search row
        return height + self.PAD + 1

    def PlaceParts(self):
        # the panel lays the list out again when the height changed (MainPanel.SetListRects)
        width, height = self.GetSize()
        if self.GetHeight(width) != height:
            self.parent.OnSize()
        else:
            self.PlaceKeys()
            self.reInitBuffer = True
            self.DirectDraw()

    def PlaceKeys(self):
        width, height = self.GetClientSize()
        right = width - self.PAD
        top = height - 1 - self.PAD - self.KEY_HEIGHT if self.stacked else 1 + self.PAD
        self.rects = []
        for (key, caption), key_width in reversed(list(zip(self.GetButtons(),
                                                           self.GetKeyWidths()))):
            right -= key_width
            self.rects.insert(0, (key, caption, wx.Rect(right, top, key_width, self.KEY_HEIGHT)))
            right -= self.GAP

    def OnSize(self, event=None):
        if self.release is None:
            return
        width, height = self.GetClientSize()
        if self.GetHeight(width) != height:
            # the parent lays out again after this size settles
            wx.CallAfter(self.Relayout)
            return
        self.PlaceKeys()
        self.reInitBuffer = True
        self.DirectDraw()

    def Relayout(self):
        if self and self.release is not None:
            self.parent.OnSize()

    def GetRectIdx(self, xy):
        if self.onClient is False:
            return None
        for index, (key, caption, rect) in enumerate(self.rects):
            if rect.Contains(xy):
                return index
        return None

    def CATCH_EVT_GLOBAL(self, event):
        if self.release is None or self.parent.HasToSkipEvent():
            return
        # under the mouse and pressed, drawn again when that changes
        pressed = event.LeftIsDown and event.down.rectIdx is not None\
            and event.down.rectIdx == event.rectIdx
        state = (event.rectIdx, pressed)
        if state != self.drawn:
            self.drawn = state
            self.reInitBuffer = True
            self.DirectDraw()
        if event.LeftUp and event.rectIdx is not None and event.rectIdx == event.down.rectIdx\
                and event.rectIdx < len(self.rects):
            self.on_action(self.rects[event.rectIdx][0])

    def CATCH_EVT_MOUSEWHEEL(self, event):
        limit = self.GetScrollLimit()
        if self.release is None or self.onClient is False or not limit:
            return
        lines = int(round(event.WheelRotation / 120.0))
        top_line = min(limit, max(0, self.top_line - lines))
        if top_line != self.top_line:
            self.top_line = top_line
            self.reInitBuffer = True
            self.DirectDraw()

    def SetRectDraw(self, dc):
        if self.release is None:
            return
        tokens = macroboxstyle.current().UI
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        width, height = self.GetClientSize()
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(tokens.BAR_LINE)))
        gc.DrawRectangle(0, 0, width, 1)
        gc.DrawRectangle(0, height - 1, width, 1)

        left = self.PAD
        top = 1 + self.PAD
        keys_left = self.rects[0][2].x if self.rects else width - self.PAD
        limit = (width - self.PAD if self.stacked else keys_left - self.GAP) - left
        title_font = uikit.get_font(12, bold=True)
        uikit.set_font(gc, title_font, tokens.BAR_TEXT)
        title = fit_text(gc, self.GetTitle(), limit)
        gc.DrawText(title, left, uikit.get_caps_top(title_font, top, self.KEY_HEIGHT))
        after = left + gc.GetTextExtent(title)[0] + self.MESSAGE_GAP

        # the version here, or what the update is doing (an error in the warning's orange)
        font = uikit.get_font(12)
        ink = tokens.WARN if self.state == 'failed' else tokens.BAR_TEXT_DIM
        uikit.set_font(gc, font, ink)
        room = left + limit - after
        if self.progress is not None:
            room -= self.PROGRESS_WIDTH + self.GAP
        message = fit_text(gc, self.GetMessage(), room)
        gc.DrawText(message, after, uikit.get_caps_top(font, top, self.KEY_HEIGHT))
        if self.progress is not None and room > 0:
            self.DrawProgress(gc, after + gc.GetTextExtent(message)[0] + self.GAP,
                              top + (self.KEY_HEIGHT - self.PROGRESS_HEIGHT) // 2)
        top += self.KEY_HEIGHT

        if self.lines:
            top += self.NOTES_GAP
            self.DrawNotes(gc, left, top, width - self.PAD * 2)
        del gc

        pressed = self.drawn[1] if self.drawn else False
        hovered = self.drawn[0] if self.drawn else None
        for index, (key, caption, rect) in enumerate(self.rects):
            uikit.draw_button(dc, rect, label=caption, on=key == 'update',
                              down=pressed and index == hovered,
                              hover=index == hovered)

    def DrawNotes(self, gc, left, top, limit):
        tokens = macroboxstyle.current().UI
        font = uikit.get_font(12)
        uikit.set_font(gc, font, tokens.BAR_TEXT)
        text_limit = limit - self.SCROLL_WIDTH * 3
        shown = self.lines[self.top_line:self.top_line + self.NOTES_LINES]
        for index, line in enumerate(shown):
            gc.DrawText(fit_text(gc, line, text_limit), left,
                        uikit.get_caps_top(font, top + self.LINE_ROW * index, self.LINE_ROW))
        scroll = self.GetScrollLimit()
        if scroll:
            # where the notes are scrolled to, by the wheel
            track = self.LINE_ROW * len(shown)
            thumb = max(12, round(track * self.NOTES_LINES / len(self.lines)))
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(tokens.BAR_TEXT_DIM)))
            gc.DrawRectangle(left + limit - self.SCROLL_WIDTH,
                             top + round((track - thumb) * self.top_line / scroll),
                             self.SCROLL_WIDTH, thumb)

    def DrawProgress(self, gc, left, top):
        # as the status line's analysis bar
        tokens = macroboxstyle.current().UI
        gc.SetPen(wx.NullGraphicsPen)
        gc.SetBrush(gc.CreateBrush(wx.Brush(tokens.CONTROL_BG)))
        gc.DrawRectangle(left, top, self.PROGRESS_WIDTH, self.PROGRESS_HEIGHT)
        done = round(self.PROGRESS_WIDTH * min(1.0, max(0.0, self.progress)))
        if done:
            gc.SetBrush(gc.CreateBrush(wx.Brush(tokens.ACCENT)))
            gc.DrawRectangle(left, top, done, self.PROGRESS_HEIGHT)
