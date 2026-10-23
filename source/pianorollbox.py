# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import instruments
import instrumentsbox
import synth
import uikit
import wx

from rackbox import HEADER
from rackbox import RackModule
from rackbox import colour
from rackbox import get_font


# PIANO ROLL: a synth's notes (SY-4's, VR-1's: INSTRUMENTS' NOTES opens it on one) over its
# bars, a key a row (the song's key's rows lighter, its root's named), a step a column.
# a click on nothing puts a note there (or a chord: CHORD's, in the key), a drag to the
# right holds it longer; a note dragged moves (time and pitch), its right edge dragged
# holds it longer or shorter; a right click (or a double click) takes it away; the keys at
# the left heard on a click; the wheel moves up and down the keys. Del takes the picked
# notes away. the device's notes made again (heard) when the mouse is let go

ROLL_HEIGHT = 300
KEYS_WIDTH = 46
RULER = 14
NOTE_ROW = 10
EDGE_GRAB = 6
LENGTHS = ((1, '1/16'), (2, '1/8'), (4, '1/4'), (8, '1/2'), (16, '1 BAR'))
NOTE_NAMES = instruments.NOTE_NAMES
LOWEST, HIGHEST = 24, 108
BLACK = (1, 3, 6, 8, 10)
# a move or a drawing's length taken from the mouse after this many pixels (a click alone
# picks)
DRAG_AFTER = 3


class PianoRollPanel(RackModule):

    TITLE = 'PIANO ROLL'
    PREFERENCE = 'piano_roll_panel'
    PARTS = (('roll', 'ROLL', ROLL_HEIGHT),)

    def __init__(self, parent):
        self.target = None
        # the highest key shown (its top row)
        self.top = 72
        self.chord = 'note'
        self.length = 2
        self.picked = set()
        # a drag: ('draw' | 'move' | 'size', its start's (x, y), the notes as they were,
        # the picked as they were); the notes shown while it lasts
        self.drag = None
        self.preview = None
        self.frame = None
        RackModule.__init__(self, parent)

    def GetControl(self):
        return getattr(self.parent, 'AudioControl', None)

    # its device

    def GetTargets(self):
        control = self.GetControl()
        if control is None:
            return []
        return [dev for dev in control.GetDevices()
                if control.GetDeviceKind(dev) in control.SYNTH_KINDS]

    def GetTarget(self):
        targets = self.GetTargets()
        if self.target not in targets:
            self.target = targets[0] if targets else None
        return self.target

    def GetSource(self):
        control = self.GetControl()
        target = self.GetTarget()
        if control is None or target is None:
            return None
        return control.GetInstrument(target) or control.SetInstrument(target, True,
                                                                      start=False)

    def GetTint(self):
        target = self.GetTarget()
        if target is None:
            return uikit.ui().ACCENT
        return instrumentsbox.PLATES[target.split('-')[0]][2]

    def Open(self, dev):
        # shown on a device's notes, its notes in sight
        self.target = dev
        self.picked = set()
        source = self.GetSource()
        if source is not None and source.notes:
            middle = (min(n[0] for n in source.notes) + max(n[0] for n in source.notes)) // 2
            self.top = min(max(middle + self.GetRows() // 2, LOWEST + self.GetRows()), HIGHEST)
        if not self.shown:
            self.Toggle()
        else:
            self.Repaint()

    def GetRows(self):
        return (ROLL_HEIGHT - RULER - 10) // NOTE_ROW

    def GetNotes(self):
        if self.preview is not None:
            return self.preview
        source = self.GetSource()
        return [list(note) for note in source.notes] if source is not None else []

    # told, its chips

    def IsActive(self):
        source = self.GetSource()
        return source is not None and source.armed

    def GetState(self):
        control = self.GetControl()
        target = self.GetTarget()
        if target is None:
            return ('ADD SY-4 OR VR-1 (INSTRUMENTS + ADD) TO DRAW NOTES', False)
        source = self.GetSource()
        kind = self.hovered[0] if isinstance(self.hovered, tuple) else None
        hint = {'grid': 'CLICK PUTS A NOTE  DRAG RIGHT HOLDS IT  DRAG A NOTE MOVES IT  '
                        'RIGHT-CLICK TAKES IT AWAY',
                'keys': 'A KEY: HEARD'}.get(kind)
        if hint:
            return (hint, False)
        return ('%s  %s  %d BARS' % (control.GetDeviceLabel(target),
                                     source.key if source is not None else '',
                                     source.bars if source is not None else 0), False)

    def GetChips(self):
        chord = dict(synth.CHORDS).get(self.chord, 'NOTE')
        chips = [('clear', 'CLEAR', False, False),
                 ('length', 'LEN %s' % dict(LENGTHS)[self.length], False, False),
                 ('chord', 'CHORD %s' % chord, self.chord != 'note', False)]
        if len(self.GetTargets()) > 1:
            control = self.GetControl()
            chips.append(('target', 'ON %s' % control.GetDeviceLabel(self.GetTarget()),
                          True, False))
        return chips

    def OnChip(self, key):
        if key == 'chord':
            kinds = [k for k, _ in synth.CHORDS]
            self.chord = kinds[(kinds.index(self.chord) + 1) % len(kinds)]
        elif key == 'length':
            lengths = [k for k, _ in LENGTHS]
            self.length = lengths[(lengths.index(self.length) + 1) % len(lengths)]
        elif key == 'target':
            targets = self.GetTargets()
            if targets:
                at = targets.index(self.GetTarget()) if self.GetTarget() in targets else -1
                self.Open(targets[(at + 1) % len(targets)])
                return
        elif key == 'clear':
            self.Commit([])
        self.Repaint()

    # drawn

    def DirectDraw(self):
        # (drawn when what it shows moves: the step heard, the mouse, a drag, its notes)
        source = self.GetSource()
        heard = self.GetHeard(source)
        frame = (self.GetTarget(), heard, self.hovered, self.drag is not None,
                 id(self.preview), tuple(map(tuple, source.notes)) if source is not None
                 else None, self.top, tuple(self.GetSize()), self.IsShown())
        if frame == self.frame and self.buffer.bmp is not None:
            return
        lap = self.buffer.lap
        RackModule.DirectDraw(self)
        self.frame = frame if self.buffer.lap != lap else None

    def Repaint(self):
        self.frame = None
        self.reInitBuffer = False
        if self.IsShown() and self.GetSize()[0] > 0:
            self.InitBuffer()
            self.Refresh(False)
            self.Update()

    def GetHeard(self, source):
        control = self.GetControl()
        if source is None or not source.armed or control is None:
            return None
        clock = control.SongClock()
        if clock is None:
            return None
        step = 60.0 / clock['bpm'] / 4.0
        return int((clock['position'] - clock['anchor']) // step) % source.GetLength()

    def GetGridRect(self, x, y, width):
        return (x + KEYS_WIDTH, y + RULER + 4, width - KEYS_WIDTH, self.GetRows() * NOTE_ROW)

    def DrawPart(self, gc, key, x, y, width):
        st = self.parent.st
        source = self.GetSource()
        if source is None:
            gc.SetFont(get_font(uikit.LABEL), colour(st.RACK_LABEL_COLOR))
            gc.DrawText('No synth in the rack: INSTRUMENTS + ADD, then SY-4 or VR-1', x, y + 20)
            return
        tint = colour(self.GetTint())
        gx, gy, gw, gh = self.GetGridRect(x, y, width)
        self.grid_rect = (gx, gy, gw, gh)
        length = source.GetLength()
        column = gw / float(length)
        rows = self.GetRows()
        root, minor = instruments.parse_key(source.key)
        scale = instruments.MINOR if minor else instruments.MAJOR
        lcd = colour(st.LCD_BG_COLOR)
        # the rows: a key each, the key's own lighter, its root's named
        for r in range(rows):
            midi = self.top - r
            ry = gy + r * NOTE_ROW
            place = (midi - root) % 12
            ground = uikit.mix(lcd, (255, 255, 255), 0.06 if place in scale else 0.0)
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(ground)))
            gc.DrawRectangle(gx, ry, gw, NOTE_ROW)
            # a piano's keys: white the whole width, a black one over its left (as on the
            # keyboard's side), the one under the mouse lighter
            black = midi % 12 in BLACK
            hovered = self.hovered == ('keys', midi)
            ivory = colour('#C9CED6')
            gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.mix(ivory, (255, 255, 255), 0.3)
                                                if hovered and not black else ivory)))
            gc.DrawRectangle(x, ry, KEYS_WIDTH - 4, NOTE_ROW)
            if black:
                ebony = colour('#24262B')
                gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.mix(ebony, (255, 255, 255), 0.25)
                                                    if hovered else ebony)))
                gc.DrawRoundedRectangle(x, ry + 1, (KEYS_WIDTH - 4) * 0.62, NOTE_ROW - 2, 1.5)
            elif midi % 12 in (4, 11):
                # (between E and F, B and C: a white key's edge)
                gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour('#8B909A')).Width(1)))
                gc.StrokeLine(x, ry + 0.5, x + KEYS_WIDTH - 4, ry + 0.5)
                gc.SetPen(wx.NullGraphicsPen)
            if midi % 12 == 0 or place == 0:
                name = '%s%d' % (NOTE_NAMES[midi % 12], midi // 12 - 1)
                gc.SetFont(get_font(7, bold=place == 0), colour('#2A2D33'))
                tw = gc.GetTextExtent(name)[0]
                gc.DrawText(name, x + KEYS_WIDTH - 7 - tw, ry + (NOTE_ROW - 9) / 2.0)
            self.hits.append((wx.Rect(int(x), int(ry), KEYS_WIDTH - 2, NOTE_ROW), 'keys', midi))
            if midi % 12 == 0:
                gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(lcd, (255, 255, 255), 0.14))
                                       .Width(1)))
                gc.StrokeLine(gx, ry + NOTE_ROW - 0.5, gx + gw, ry + NOTE_ROW - 0.5)
        # the columns: beats faint, bars clear; the bars' numbers on the ruler
        gc.SetFont(get_font(8, bold=True), colour(st.RACK_LABEL_COLOR))
        for k in range(length + 1):
            if k % 4:
                continue
            cx = gx + k * column
            strong = k % 16 == 0
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(
                lcd, (255, 255, 255), 0.22 if strong else 0.08)).Width(1)))
            gc.StrokeLine(cx + 0.5, gy, cx + 0.5, gy + gh)
            if strong and k < length:
                gc.DrawText('%d' % (k // 16 + 1), cx + 3, y + 2)
            elif k < length:
                gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour(st.RACK_LABEL_COLOR))
                                       .Width(1)))
                gc.StrokeLine(cx + 0.5, y + RULER - 2, cx + 0.5, y + RULER + 2)
        # the step heard
        heard = self.GetHeard(source)
        if heard is not None:
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(wx.Brush(uikit.mix(lcd, (255, 255, 255), 0.1))))
            gc.DrawRectangle(gx + heard * column, gy, column, gh)
        # the notes: the device's colour (softer the softer), the picked edged white
        for index, (midi, start, held, velocity) in enumerate(self.GetNotes()):
            r = self.top - midi
            if r < 0 or r >= rows:
                continue
            nx, ny = gx + start * column, gy + r * NOTE_ROW
            nw = max(min(held, length - start) * column - 1.0, 2.0)
            playing = heard is not None and start <= heard < start + held
            fill = colour('#F2F2F2') if playing else uikit.mix(
                tint, lcd.Get()[:3], 0.1 + 0.4 * (1.0 - velocity))
            picked = index in self.picked
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(colour('#FFFFFF') if picked else
                                                      uikit.mix(fill, (0, 0, 0), 0.4))
                                   .Width(1.5 if picked else 1)))
            gc.SetBrush(gc.CreateBrush(wx.Brush(fill)))
            gc.DrawRoundedRectangle(nx + 0.5, ny + 1, nw, NOTE_ROW - 2, 2)
            # its right edge's grip
            gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(fill, (0, 0, 0), 0.5)).Width(1)))
            gc.StrokeLine(nx + nw - 2, ny + 3, nx + nw - 2, ny + NOTE_ROW - 3)
        self.hits.append((wx.Rect(int(gx), int(gy), int(gw), int(gh)), 'grid', None))
        # its frame
        gc.SetPen(gc.CreatePen(wx.GraphicsPenInfo(uikit.mix(lcd, (255, 255, 255), 0.14))
                               .Width(1)))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRectangle(gx + 0.5, gy + 0.5, gw - 1, gh - 1)

    # handled

    def GetCell(self, X, Y):
        # (midi, step) under the panel's point
        gx, gy, gw, gh = getattr(self, 'grid_rect', (0, 0, 1, 1))
        source = self.GetSource()
        length = source.GetLength() if source is not None else instruments.STEPS
        step = int((X - gx) / (gw / float(length)))
        midi = self.top - int((Y - gy) // NOTE_ROW)
        return min(max(midi, LOWEST), HIGHEST), min(max(step, 0), length - 1)

    def FindNote(self, notes, midi, step):
        for index in range(len(notes) - 1, -1, -1):
            m, start, held, _ = notes[index]
            if m == midi and start <= step < start + held:
                return index
        return None

    def NearEnd(self, note, X):
        gx, gy, gw, gh = self.grid_rect
        source = self.GetSource()
        column = gw / float(source.GetLength())
        end = gx + (note[1] + note[2]) * column
        return end - EDGE_GRAB <= X <= end + 2

    def HandleHit(self, event, hit):
        kind, value = hit
        source = self.GetSource()
        if source is None:
            return
        if kind == 'keys':
            if event.LeftDown or event.LeftDClick:
                source.Audition(value)
            return
        if kind != 'grid':
            return
        notes = self.GetNotes()
        midi, step = self.GetCell(event.X, event.Y)
        index = self.FindNote(notes, midi, step)
        if event.RightDown or (event.LeftDClick and index is not None):
            if index is not None:
                del notes[index]
                self.picked = set()
                self.Commit(notes)
            return
        if not (event.LeftDown or event.LeftDClick):
            return
        shift = bool(getattr(event, 'ShiftDown', False))
        if index is not None:
            # picked (shift: with the others), moved or held longer by a drag
            if shift:
                self.picked ^= {index}
            elif index not in self.picked:
                self.picked = {index}
            mode = 'size' if self.NearEnd(notes[index], event.X) else 'move'
            self.drag = (mode, (event.X, event.Y), [list(n) for n in notes], set(self.picked),
                         (midi, step))
            self.preview = [list(n) for n in notes]
            self.Repaint()
            return
        # a note (a chord, CHORD's, in the key) put there, held longer by a drag
        root, minor = instruments.parse_key(source.key)
        scale = instruments.MINOR if minor else instruments.MAJOR
        made = [[m, step, self.length, 0.85]
                for m in synth.chord_notes(self.chord, midi, root, scale)
                if LOWEST <= m <= HIGHEST]
        notes = notes + made
        self.picked = set(range(len(notes) - len(made), len(notes)))
        self.drag = ('draw', (event.X, event.Y), [list(n) for n in notes], set(self.picked),
                     (midi, step))
        self.preview = notes
        source.Audition(midi if len(made) == 1 else made[0][0], self.length)
        self.Repaint()

    def IsDragging(self):
        return self.drag is not None

    def HandleDrag(self, event):
        if self.drag is None:
            return False
        mode, (x0, y0), before, picked, (midi0, step0) = self.drag
        source = self.GetSource()
        if source is None:
            self.drag = None
            return True
        if event.LeftIsDown:
            if abs(event.X - x0) < DRAG_AFTER and abs(event.Y - y0) < DRAG_AFTER:
                return True
            midi, step = self.GetCell(event.X, event.Y)
            length = source.GetLength()
            notes = [list(n) for n in before]
            if mode == 'move':
                semis, steps = midi - midi0, step - step0
                for index in picked:
                    m, start, held, velocity = notes[index]
                    notes[index] = [min(max(m + semis, LOWEST), HIGHEST),
                                    min(max(start + steps, 0), length - held if held < length
                                        else 0), held, velocity]
            else:
                # (drawn or its edge dragged: as long as to the step under the mouse)
                for index in picked:
                    start = notes[index][1]
                    if mode == 'size':
                        held = before[index][2] + (step - step0)
                    else:
                        held = step - start + 1
                    notes[index][2] = min(max(held, 1), length - start)
            if notes != self.preview:
                self.preview = notes
                self.Repaint()
            return True
        # let go: kept, made again
        notes = self.preview if self.preview is not None else before
        self.drag = None
        self.preview = None
        self.Commit(notes)
        return True

    def Commit(self, notes):
        source = self.GetSource()
        if source is None:
            return
        picked = [tuple(notes[k][:3]) for k in self.picked if k < len(notes)]
        source.SetNotes(notes)
        # (the picked found again where they are now: the notes kept in their order)
        self.picked = set(k for k, note in enumerate(source.notes)
                          if tuple(note[:3]) in picked)
        control = self.GetControl()
        if control is not None:
            control.KeepInstruments()
        panel = getattr(self.parent, 'Instruments', None)
        if panel is not None and panel.IsShown():
            panel.Repaint()
        self.Repaint()

    def CATCH_EVT_MOUSEWHEEL(self, event):
        # up and down the keys (a notch: three)
        if self.onClient is False or self.GetTarget() is None:
            return
        up = event.WheelRotation > 0
        rows = self.GetRows()
        self.top = min(max(self.top + (3 if up else -3), LOWEST + rows), HIGHEST)
        self.Repaint()

    TAKEN_KEYS = (wx.WXK_DELETE, wx.WXK_BACK, wx.WXK_NUMPAD_DELETE)

    def TakesKey(self, event):
        '''Del with notes picked and the mouse over it: its (the list's Del took tracks
        away)'''
        if not self.picked or not self.IsShown() or not self.onClient:
            return False
        if event.EventType not in (wx.EVT_KEY_DOWN.evtType[0], wx.EVT_CHAR_HOOK.evtType[0]):
            return False
        return event.GetKeyCode() in self.TAKEN_KEYS

    def CATCH_EVT_KEY_DOWN(self, event):
        if event.KeyCode in self.TAKEN_KEYS and self.picked and self.onClient:
            notes = [n for k, n in enumerate(self.GetNotes()) if k not in self.picked]
            self.picked = set()
            self.Commit(notes)
