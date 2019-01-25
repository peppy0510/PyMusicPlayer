# encoding: utf-8


# author: Taehong Kim
# email: peppy0510@hotmail.com


from utilities import rgb_hex2dec
from utilities import rgb_dec2hex


STYLE_NAMES = sorted(['Dark Red', 'Dark Black', 'Dark Gray', 'Light Gray', 'Snow White'])


def load(name, rgbstyle='dec'):
    name = ''.join([v.capitalize() for v in name.split(' ')])
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
    return style


class Default():

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
        VECTORSCOPE_BG_COLOR = '#101010'
        VECTORSCOPE_PN_COLOR = VOLUME_PN_COLOR
        VECTORSCOPE_FG_COLOR = '#B0B0B8'
        WAVEFORM_BG_COLOR = '#000000'
        WAVEFORM_FG_COLOR = '#A0A0A8'
        HIGHLIGHT_BG_COLOR = '#200505'
        HIGHLIGHT_PN_COLOR = '#606060'
        HIGHLIGHT_FG_COLOR = VOLUME_FG_COLOR
        PLAYCURSOR_STROKE = 1
        PLAYCURSOR_BG_COLOR = '#FF0000'
        PLAYCURSOR_FG_COLOR = '#FF0000'

    class LISTBOX():
        BG_COLOR = '#080808'
        LIST_BG_CONTRAST = 1
        LIST_BG_COLOR = '#180808'
        LIST_FG_COLOR = '#F0F0F0'
        LIST_PN_COLOR = '#080808'
        HEADER_BG_COLOR = '#000000'
        HEADER_PN_COLOR = '#202020'
        HEADER_FG_COLOR = '#D0D0D0'
        SCROLLBAR_BG_COLOR = '#101010'
        SCROLLBAR_PN_COLOR = '#404040'
        SCROLLBAR_FG_COLOR = '#101010'
        ANALYZE_NONE_COLOR = '#FF0000'
        ANALYZE_PEND_COLOR = '#4444FF'
        SELECTED_BG_COLOR = '#DD6666'
        SELECTED_FG_COLOR = '#000000'
        INSERTITEM_CURSOR_COLOR = SELECTED_BG_COLOR
        INSERTCOLCURSOR_BG_COLOR = HEADER_BG_COLOR
        INSERTCOLCURSOR_FG_COLOR = SELECTED_BG_COLOR
        TOOLBAR_BG_COLOR = '#E0E0E0'

    class EDITBOX(LISTBOX):
        EDITOR_BG_COLOR = '#281010'
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
