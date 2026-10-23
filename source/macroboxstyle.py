# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


from utilities import rgb_hex2dec
from utilities import rgb_dec2hex


STYLE_NAMES = sorted(['Dark Red', 'Dark Black', 'Dark Gray', 'Light Gray', 'Snow White'])
DEFAULT_NAME = 'Dark Red'
# the style loaded last (load): the dialogs and the standard controls take its UI colours
CURRENT = None


def current():
    if CURRENT is None:
        return load(DEFAULT_NAME)
    return CURRENT


def load(name, rgbstyle='dec'):
    global CURRENT
    name = ''.join([v.capitalize() for v in (name or DEFAULT_NAME).split(' ')])
    style = eval(name)
    style = style()
    for cname in dir(style):
        if cname.startswith(u'__'):
            continue
        pnames = dir(getattr(eval(name), cname))
        for pname in pnames:
            if pname.startswith(u'__'):
                continue
            namespace = u'%s.%s.%s' % (name, cname, pname)
            v = getattr(getattr(eval(name), cname), pname)
            if rgbstyle == 'dec' and isinstance(v, str) and v.startswith(u'#'):
                v = rgb_hex2dec(v)
                exec(u'%s = v' % (namespace))
            elif rgbstyle == 'hex' and type(v) in (list, tuple) and len(v) == 3:
                v = rgb_dec2hex(v)
                exec(u'%s = v' % (namespace))
            elif rgbstyle == 'hex#' and type(v) in (list, tuple) and len(v) == 3:
                v = u'#' + rgb_dec2hex(v)
                exec(u'%s = v' % (namespace))
            elif rgbstyle == 'hex#' and isinstance(v, str) and len(v) == 6:
                v = u'#' + v
                exec(u'%s = v' % (namespace))
    if rgbstyle == 'dec':
        CURRENT = style
    return style


class Default():

    # the dialogs and the standard controls, by their role. a dark style's are the colours of
    # Windows' dark mode (wx's, measured), which draws the title bar, the menus and the
    # native controls: what is drawn here matches what it draws
    class UI():
        DARK = True
        DIALOG_BG = '#191919'
        PANEL_BG = '#191919'
        RAISED_BG = '#333333'
        TEXT = '#FFFFFF'
        TEXT_FAINT = '#6D6D6D'
        EDIT_BG = '#191919'
        EDIT_FG = '#FFFFFF'
        # a dialog's text field: its ground a shade off the dialog's (no native frame), its
        # edge, lighter while typed in
        FIELD_BG = '#26262B'
        FIELD_EDGE = '#34343A'
        FIELD_FOCUS = '#2F7BEA'
        # the bars (the control strip, the title, the status line) and what is on them
        BAR_BG = '#1E1E1E'
        BAR_LINE = '#2E2E2E'
        BAR_TEXT = '#E8E8E8'
        BAR_TEXT_DIM = '#8C8C8C'
        CONTROL_BG = '#2B2B2B'
        CONTROL_HOVER = '#3B3B3B'
        # pressed: under the face at rest (lighter than the hover, then darkened by
        # draw_face, it came out as the hover)
        CONTROL_DOWN = '#232323'
        CONTROL_FG = '#BDBDBD'
        # a control on, the busy and the warned: blue and orange, apart for red-green
        # colour blindness and by brightness too (never by hue alone)
        ACCENT = '#2F7BEA'
        ACCENT_FG = '#FFFFFF'
        WARN = '#F0A030'
        WARN_FG = '#000000'

    class PLAYBOX():
        PLAY_BG_COLOR = '#000000'
        APIC_BG_COLOR = '#000000'
        APIC_PN_COLOR = '#181818'
        APIC_FG_COLOR = '#101010'
        APIC_CP_COLOR = '#080808'
        VOLUME_BG_COLOR = '#101010'
        VOLUME_PN_COLOR = '#202020'
        VOLUME_FG_COLOR = '#E0E0E8'
        SPECTRUM_STROKE = 1
        SPECTRUM_BG_COLOR = VOLUME_PN_COLOR
        SPECTRUM_FG_COLOR = '#F0F0F8'
        # VECTORSCOPE_BG_COLOR = '#101010'
        VECTORSCOPE_BG_COLOR = PLAY_BG_COLOR
        VECTORSCOPE_PN_COLOR = VOLUME_PN_COLOR
        VECTORSCOPE_FG_COLOR = '#B0B0B8'
        WAVEFORM_BG_COLOR = '#000000'
        WAVEFORM_FG_COLOR = '#A0A0A8'
        # HIGHLIGHT_BG_COLOR = '#200505'
        HIGHLIGHT_BG_COLOR = '#282830'
        HIGHLIGHT_PN_COLOR = '#606060'
        HIGHLIGHT_FG_COLOR = VOLUME_FG_COLOR
        # where it plays: white edged in black, seen on the blue, the orange and the white
        # of the waveform alike (red was lost on the orange to red-green colour blindness)
        PLAYCURSOR_STROKE = 1
        PLAYCURSOR_BG_COLOR = '#FFFFFF'
        PLAYCURSOR_FG_COLOR = '#000000'
        # the header over the play area (black in every style): the title, the line under
        # it and the info chips
        TITLE_FG_COLOR = '#F2F2F2'
        TITLE_DIM_COLOR = '#8C8C8C'
        CHIP_BG_COLOR = '#1C1C1C'
        CHIP_FG_COLOR = '#D8D8D8'
        # the MASTER rack (a plug-in's plate): its ground and edges, its labels, the
        # readouts' display, the meters' unlit segments and the knobs
        RACK_BG_COLOR = '#151518'
        RACK_EDGE_COLOR = '#2A2A30'
        RACK_LABEL_COLOR = '#7E8794'
        RACK_TEXT_COLOR = '#D7DCE3'
        LCD_BG_COLOR = '#0A0B0D'
        LCD_TEXT_COLOR = '#8EC9FF'
        METER_OFF_COLOR = '#22262E'
        KNOB_FACE_COLOR = '#2A2D33'
        KNOB_RING_COLOR = '#3A3E46'

    class LISTBOX():
        BG_COLOR = '#080808'
        LIST_BG_CONTRAST = 1
        # the rows on a neutral dark grey, the rack's (a red-brown before: apart from the
        # blue accent of the selection)
        LIST_BG_COLOR = '#141417'
        LIST_FG_COLOR = '#F0F0F0'
        LIST_PN_COLOR = '#0A0A0C'
        HEADER_BG_COLOR = '#000000'
        HEADER_PN_COLOR = '#202020'
        HEADER_FG_COLOR = '#D0D0D0'
        SCROLLBAR_BG_COLOR = '#101010'
        SCROLLBAR_PN_COLOR = '#404040'
        SCROLLBAR_FG_COLOR = '#101010'
        ANALYZE_NONE_COLOR = '#FF0000'
        ANALYZE_PEND_COLOR = '#4444FF'
        # the selected rows, and the selected playlist in the sidebar: the UI's accent
        # (red-pink before)
        # muted (the accent a third over the rows), its bar at the left in the accent itself:
        # the full accent was the screen's loudest thing
        SELECTED_BG_COLOR = '#1D3861'
        SELECTED_FG_COLOR = '#FFFFFF'
        SELECTED_BAR_COLOR = '#2F7BEA'
        INSERTITEM_CURSOR_COLOR = '#2F7BEA'
        INSERTCOLCURSOR_BG_COLOR = HEADER_BG_COLOR
        INSERTCOLCURSOR_FG_COLOR = '#2F7BEA'
        TOOLBAR_BG_COLOR = '#E0E0E0'

    class EDITBOX(LISTBOX):
        # neutral as the list's rows (a red-brown before)
        EDITOR_BG_COLOR = '#141417'
        EDITOR_FG_COLOR = '#F0F0F0'
        PREVIEW_BG_COLOR = EDITOR_BG_COLOR
        PREVIEW_FG_COLOR = EDITOR_FG_COLOR
        # PREVIEW_BG_COLOR = '#202020'
        # PREVIEW_FG_COLOR = '#404040'
        LINENUM_BG_COLOR = '#202020'
        LINENUM_FG_COLOR = '#606060'
        CARET_BG_COLOR = '#DD6666'
        CARET_FG_COLOR = '#000000'
        BRACE_BG_COLOR = EDITOR_BG_COLOR
        BRACE_FG_COLOR = '#FF6060'
        TOOLBAR_BG_COLOR = '#E0E0E0'


class DarkRed(Default):

    class PLAYBOX(Default.PLAYBOX):
        pass

    class LISTBOX(Default.LISTBOX):
        pass
        # SCROLLBAR_FG_COLOR = '#400505'

    class EDITBOX(Default.EDITBOX):
        pass


class DarkBlack(Default):

    class FRAME():
        TRANSPARENT = 255

    class PLAYBOX(Default.PLAYBOX):
        pass

    class LISTBOX(Default.LISTBOX):
        LIST_BG_COLOR = '#080808'
        LIST_FG_COLOR = '#F0F0F0'
        LIST_PN_COLOR = '#101010'
        # SELECTED_BG_COLOR = '#303030'
        # SELECTED_FG_COLOR = LIST_FG_COLOR
        INSERTITEM_CURSOR_COLOR = '#F0F0F0'
        INSERTCOLCURSOR_FG_COLOR = INSERTITEM_CURSOR_COLOR

    class EDITBOX(Default.EDITBOX):
        EDITOR_BG_COLOR = '#080808'
        EDITOR_FG_COLOR = '#F0F0F0'
        PREVIEW_BG_COLOR = EDITOR_BG_COLOR
        PREVIEW_FG_COLOR = EDITOR_FG_COLOR
        LINENUM_BG_COLOR = '#202020'
        LINENUM_FG_COLOR = '#606060'
        # CARET_BG_COLOR = '#303030'
        # CARET_FG_COLOR = '#F0F0F0'
        BRACE_BG_COLOR = EDITOR_BG_COLOR
        BRACE_FG_COLOR = '#FF6060'
        TOOLBAR_BG_COLOR = '#E0E0E0'


class DarkGray(Default):

    class FRAME():
        TRANSPARENT = 255

    class PLAYBOX(Default.PLAYBOX):
        pass

    class LISTBOX(Default.LISTBOX):
        LIST_BG_COLOR = '#202020'
        LIST_FG_COLOR = '#F0F0F0'
        LIST_PN_COLOR = '#181818'
        # SELECTED_BG_COLOR = '#505050'
        # SELECTED_FG_COLOR = LIST_FG_COLOR
        INSERTITEM_CURSOR_COLOR = '#F0F0F0'
        INSERTCOLCURSOR_FG_COLOR = '#F0F0F0'
        SCROLLBAR_BG_COLOR = '#101010'
        SCROLLBAR_PN_COLOR = '#888888'
        SCROLLBAR_FG_COLOR = '#202020'

    class EDITBOX(Default.EDITBOX):
        EDITOR_BG_COLOR = '#202020'
        EDITOR_FG_COLOR = '#F0F0F0'
        PREVIEW_BG_COLOR = EDITOR_BG_COLOR
        PREVIEW_FG_COLOR = EDITOR_FG_COLOR
        LINENUM_BG_COLOR = EDITOR_BG_COLOR
        LINENUM_FG_COLOR = '#606060'
        # CARET_BG_COLOR = '#505050'
        # CARET_FG_COLOR = '#F0F0F0'
        BRACE_BG_COLOR = EDITOR_BG_COLOR
        BRACE_FG_COLOR = '#FF6060'
        TOOLBAR_BG_COLOR = '#E0E0E0'
        SCROLLBAR_BG_COLOR = '#101010'
        SCROLLBAR_PN_COLOR = '#888888'
        SCROLLBAR_FG_COLOR = '#202020'


class LightGray(Default):

    # light: the colours the dialogs had before (no dark mode)
    class UI(Default.UI):
        DARK = False
        DIALOG_BG = '#E6E6E6'
        PANEL_BG = '#FFFFFF'
        RAISED_BG = '#F0F0F0'
        TEXT = '#000000'
        TEXT_FAINT = '#7D7D7D'
        EDIT_BG = '#FFFFFF'
        EDIT_FG = '#000000'
        FIELD_BG = '#FFFFFF'
        FIELD_EDGE = '#C8C8C8'
        FIELD_FOCUS = '#2F7BEA'
        BAR_BG = '#F0F0F0'
        BAR_LINE = '#D0D0D0'
        BAR_TEXT = '#000000'
        BAR_TEXT_DIM = '#606060'
        CONTROL_BG = '#E2E2E2'
        CONTROL_HOVER = '#D6D6D6'
        CONTROL_DOWN = '#C4C4C4'
        CONTROL_FG = '#303030'
        ACCENT = '#2F6FD6'
        ACCENT_FG = '#FFFFFF'
        WARN = '#C06000'
        WARN_FG = '#FFFFFF'

    class FRAME():
        TRANSPARENT = 255

    class PLAYBOX(Default.PLAYBOX):
        pass

    class LISTBOX(Default.LISTBOX):
        LIST_BG_COLOR = '#E0E0E0'
        LIST_FG_COLOR = '#000000'
        LIST_PN_COLOR = '#E0E0E0'
        # SELECTED_BG_COLOR = '#A0A0A0'
        # SELECTED_FG_COLOR = '#000000'
        SELECTED_BG_COLOR = '#C9DCF8'
        SELECTED_FG_COLOR = '#000000'
        INSERTITEM_CURSOR_COLOR = '#000000'
        INSERTCOLCURSOR_FG_COLOR = '#F8F8F8'
        SCROLLBAR_BG_COLOR = '#E0E0E0'
        SCROLLBAR_PN_COLOR = '#888888'
        SCROLLBAR_FG_COLOR = '#E0E0E0'

    class EDITBOX(Default.EDITBOX):
        EDITOR_BG_COLOR = '#E0E0E0'
        EDITOR_FG_COLOR = '#000000'
        PREVIEW_BG_COLOR = EDITOR_BG_COLOR
        PREVIEW_FG_COLOR = EDITOR_FG_COLOR
        LINENUM_BG_COLOR = EDITOR_BG_COLOR
        LINENUM_FG_COLOR = '#606060'
        # CARET_BG_COLOR = '#C0C0C0'
        # CARET_FG_COLOR = '#000000'
        BRACE_BG_COLOR = EDITOR_BG_COLOR
        BRACE_FG_COLOR = '#FF6060'
        TOOLBAR_BG_COLOR = '#E0E0E0'
        SCROLLBAR_BG_COLOR = '#E0E0E0'
        SCROLLBAR_PN_COLOR = '#888888'
        SCROLLBAR_FG_COLOR = '#E0E0E0'


class SnowWhite(Default):

    # light: the colours the dialogs had before (no dark mode)
    class UI(Default.UI):
        DARK = False
        DIALOG_BG = '#E6E6E6'
        PANEL_BG = '#FFFFFF'
        RAISED_BG = '#F0F0F0'
        TEXT = '#000000'
        TEXT_FAINT = '#7D7D7D'
        EDIT_BG = '#FFFFFF'
        EDIT_FG = '#000000'
        FIELD_BG = '#FFFFFF'
        FIELD_EDGE = '#C8C8C8'
        FIELD_FOCUS = '#2F7BEA'
        BAR_BG = '#F0F0F0'
        BAR_LINE = '#D0D0D0'
        BAR_TEXT = '#000000'
        BAR_TEXT_DIM = '#606060'
        CONTROL_BG = '#E2E2E2'
        CONTROL_HOVER = '#D6D6D6'
        CONTROL_DOWN = '#C4C4C4'
        CONTROL_FG = '#303030'
        ACCENT = '#2F6FD6'
        ACCENT_FG = '#FFFFFF'
        WARN = '#C06000'
        WARN_FG = '#FFFFFF'

    class FRAME():
        TRANSPARENT = 255

    class PLAYBOX(Default.PLAYBOX):
        pass

    class LISTBOX(Default.LISTBOX):
        LIST_BG_COLOR = '#F8F8F8'
        LIST_FG_COLOR = '#000000'
        LIST_PN_COLOR = '#E8E8E8'
        # SELECTED_BG_COLOR = '#C0C0C0'
        # SELECTED_FG_COLOR = '#000000'
        SELECTED_BG_COLOR = '#C9DCF8'
        SELECTED_FG_COLOR = '#000000'
        INSERTITEM_CURSOR_COLOR = '#000000'
        INSERTCOLCURSOR_FG_COLOR = '#F8F8F8'
        SCROLLBAR_BG_COLOR = '#F8F8F8'
        SCROLLBAR_PN_COLOR = '#888888'
        SCROLLBAR_FG_COLOR = '#F0F0F0'

    class EDITBOX(Default.EDITBOX):
        EDITOR_BG_COLOR = '#F8F8F8'
        EDITOR_FG_COLOR = '#000000'
        PREVIEW_BG_COLOR = EDITOR_BG_COLOR
        PREVIEW_FG_COLOR = EDITOR_FG_COLOR
        LINENUM_BG_COLOR = EDITOR_BG_COLOR
        LINENUM_FG_COLOR = '#606060'
        # CARET_BG_COLOR = '#C0C0C0'
        # CARET_FG_COLOR = '#000000'
        BRACE_BG_COLOR = EDITOR_BG_COLOR
        BRACE_FG_COLOR = '#FF6060'
        TOOLBAR_BG_COLOR = '#E0E0E0'
        SCROLLBAR_BG_COLOR = '#F8F8F8'
        SCROLLBAR_PN_COLOR = '#888888'
        SCROLLBAR_FG_COLOR = '#F0F0F0'
