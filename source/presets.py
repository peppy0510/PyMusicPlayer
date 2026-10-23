# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import json
import os
import re


# INSTRUMENTS' presets: a machine's sound (RT909 its slots and their voices, PS1200 its
# grabbed bar and its slices' settings, BT303 its tone) and its pattern (RT909 its steps by
# sound, PS1200 the slice each step plays, BT303 its line), saved apart: a sound with
# another pattern, a pattern on another sound. built in (BUILT_IN) and saved by the user (a
# JSON file each, in the app's folder, its name the file's)

WHATS = ('sound', 'pattern')


def get_folder(machine, what):
    folder = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'PyMusicPlayer', 'presets',
                          machine, what)
    os.makedirs(folder, exist_ok=True)
    return folder


def to_file_name(name):
    # (a name as a file's: what Windows does not take left out)
    return re.sub(r'[\\/:*?"<>|]+', '', name).strip()[:60]


def list_saved(machine, what):
    folder = get_folder(machine, what)
    return sorted(name[:-5] for name in os.listdir(folder) if name.endswith('.json'))


def save(machine, what, name, data):
    name = to_file_name(name)
    if not name:
        return None
    path = os.path.join(get_folder(machine, what), name + '.json')
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=1)
    return name


def load_saved(machine, what, name):
    path = os.path.join(get_folder(machine, what), to_file_name(name) + '.json')
    try:
        with open(path, encoding='utf-8') as file:
            return json.load(file)
    except (OSError, ValueError):
        return None


def delete_saved(machine, what, name):
    path = os.path.join(get_folder(machine, what), to_file_name(name) + '.json')
    try:
        os.remove(path)
    except OSError:
        pass


# built-in patterns, written as a bar of sixteenths: x a hit, X an accented one, . none

def steps(text):
    return [1.0 if c == 'X' else (0.75 if c == 'x' else (0.45 if c == 'o' else 0))
            for c in text.replace(' ', '')][:16]


def drums(**rows):
    # RT909's: a row a sound (its slots found by their sound, added when missing)
    return dict(kind='rt909', rows=[dict(kind=kind.replace('_', ' '), steps=steps(text))
                                    for kind, text in rows.items()])


BUILT_IN = dict(rt909=dict(pattern={
    'House': drums(kick='X...x...x...x...', clap='....x.......x...',
                   hat='o.o.o.o.o.o.o.o.', open_hat='..x...x...x...x.'),
    'Deep house': drums(kick='X...x...x...x...', clap='....x.......x...',
                        hat='o.oo.oo.o.oo.ooo', open_hat='..x...x...x...x.',
                        rim='...x.......x..x.'),
    'Techno': drums(kick='X...x...x...x...', rim='....x.......x...',
                    hat='oooooooooooooooo', open_hat='..x...x...x...x.'),
    'Disco': drums(kick='X...x...x...x...', snare='....x.......x...',
                   hat='o.o.o.o.o.o.o.o.', open_hat='..x...x...x...x.'),
    'Boom bap': drums(kick='X......x..x.....', snare='....X.......X...',
                      hat='x.x.x.x.x.x.x.x.'),
    'Trap': drums(kick='X.........x.....', clap='........X.......',
                  hat='x.x.x.x.x.xxx.xx', open_hat='......x.........'),
    'Breakbeat (Amen)': drums(kick='X.x.......xx....', snare='....X..x.x..X..x',
                              cymbal='x.x.x.x.x.x.x.x.'),
    'UK garage 2-step': drums(kick='X.........x.....', snare='....X.......X...',
                              hat='..x...x...x...x.', rim='.......x......x.'),
    'Drum and bass': drums(kick='X.........x.....', snare='....X.......X...',
                           hat='x.x.x.x.x.x.x.x.'),
    'Dembow': drums(kick='X...x...x...x...', snare='...x..x....x..x.',
                    hat='x.x.x.x.x.x.x.x.'),
    'Electro': drums(kick='X.....x...x.....', snare='....X.......X...',
                     hat='xxxxxxxxxxxxxxxx', cowbell='..x.......x...x.'),
}), bt303=dict(pattern={
    # (degree of the scale, accent, slide) a step, None a rest
    'Acid roll': dict(kind='bt303', line=[
        [0, True, False], [0, False, False], [7, False, True], [0, False, False], None,
        [0, True, False], [2, False, True], [0, False, False], [0, True, False], None,
        [4, False, False], [0, False, True], [5, True, False], [4, False, False],
        [2, False, False], [1, False, False]]),
    'Octave pump': dict(kind='bt303', line=[
        [0, True, False], [7, False, False], [0, False, False], [7, False, False],
        [0, True, False], [7, False, False], [0, False, False], [7, False, True],
        [0, True, False], [7, False, False], [0, False, False], [7, False, False],
        [0, True, False], [7, False, False], [3, False, True], [4, False, False]]),
    'Rolling sixteenths': dict(kind='bt303', line=[
        [0, False, False], [0, False, False], [0, True, False], [0, False, False],
        [4, False, False], [4, False, False], [4, True, False], [4, False, False],
        [3, False, False], [3, False, False], [3, True, False], [3, False, False],
        [2, False, True], [1, False, True], [0, True, False], [0, False, False]]),
    'Minor walk': dict(kind='bt303', line=[
        [0, True, False], None, [0, False, False], [2, False, False], None,
        [3, True, False], None, [4, False, True], [6, False, False], None,
        [4, True, False], None, [3, False, False], [2, False, True], [0, False, False],
        None]),
}), ps1200=dict(pattern={
    # the slice each step plays (1 to 16), 0 none
    'As grabbed': dict(kind='ps1200', order=list(range(1, 17))),
    'Half time': dict(kind='ps1200', order=[1, 0, 2, 0, 3, 0, 4, 0, 5, 0, 6, 0, 7, 0, 8, 0]),
    'Reverse order': dict(kind='ps1200', order=list(range(16, 0, -1))),
    'Stutter': dict(kind='ps1200', order=[1, 1, 1, 1, 5, 6, 7, 8, 9, 9, 9, 9, 13, 14, 15, 16]),
    'Chop': dict(kind='ps1200', order=[1, 2, 5, 6, 3, 4, 7, 8, 9, 10, 13, 14, 11, 12, 15, 16]),
    'Kick and snare': dict(kind='ps1200', order=[1, 0, 1, 0, 5, 0, 1, 1, 0, 1, 1, 0, 5, 0,
                                                 5, 5]),
}))


# the library: a genre's parts (its kicks, its backbeats, its hats, what else it plays)
# combined into its variations ('Genre/Genre 01'...), well-known records' grooves as they
# are commonly transcribed ('Famous grooves/...': close, not checked against the records),
# bass lines (rhythms by contours), slice orders. built once, at import

def row(kind, text):
    return (kind, text)


GENRES = (
    ('House', ['X...x...x...x...'],
     [row('clap', '....x.......x...'), row('snare', '....x.......x...')],
     [[row('hat', 'o.o.o.o.o.o.o.o.'), row('open hat', '..x...x...x...x.')],
      [row('hat', 'oooooooooooooooo')], [row('open hat', '..x...x...x...x.')],
      [row('hat', 'o.oo.oo.o.oo.oo.')]],
     [[], [row('rim', '...x.......x..x.')], [row('cowbell', '......x.......x.')]]),
    ('Deep house', ['X...x...x...x...', 'X...x...x...x..x'],
     [row('clap', '....x.......x...'), row('rim', '....x.......x...')],
     [[row('hat', 'o.oo.oo.o.oo.ooo'), row('open hat', '..x...x...x...x.')],
      [row('open hat', '..x...x...x...x.')], [row('hat', '.o.o.o.o.o.o.o.o')]],
     [[], [row('rim', '...x.......x..x.')], [row('tom', '.......x......x.')]]),
    ('Tech house', ['X...x...x...x...', 'X...x...x...x.x.'],
     [row('clap', '....x.......x...'), row('snare', '....x.......x..o')],
     [[row('hat', 'oooooooooooooooo'), row('open hat', '..x...x...x...x.')],
      [row('hat', '.o.o.o.o.o.o.o.o')], [row('open hat', '..x...x...x...x.')]],
     [[], [row('rim', '..x..x....x..x..')], [row('cowbell', '...x.......x....')]]),
    ('Techno', ['X...x...x...x...', 'X...x...x...x..x', 'X..xx...x...x...'],
     [row('rim', '....x.......x...'), row('clap', '....x.......x...'),
      row('snare', '....x......xx...')],
     [[row('hat', 'oooooooooooooooo'), row('open hat', '..x...x...x...x.')],
      [row('open hat', '..x...x...x...x.')], [row('cymbal', 'x.x.x.x.x.x.x.x.')]],
     [[], [row('tom', '......x.......x.')]]),
    ('Minimal', ['X...x...x...x...', 'X.....x...x.....'],
     [row('rim', '.......x......x.'), row('clap', '....x.......x...')],
     [[row('hat', '..o...o...o...o.')], [row('hat', 'o.o.o.o.o.o.o.o.')],
      [row('open hat', '..x.......x.....')]],
     [[], [row('cowbell', '...x.....x......')]]),
    ('Disco', ['X...x...x...x...'],
     [row('snare', '....x.......x...'), row('clap', '....x.......x...')],
     [[row('hat', 'o.o.o.o.o.o.o.o.'), row('open hat', '..x...x...x...x.')],
      [row('hat', 'oooooooooooooooo'), row('open hat', '..x...x...x...x.')]],
     [[], [row('tom', '............x.x.')], [row('cowbell', 'x...x...x...x...')]]),
    ('Nu disco', ['X...x...x...x...', 'X.....x.x...x...'],
     [row('clap', '....x.......x...'), row('snare', '....x..o....x...')],
     [[row('hat', 'o.o.o.o.o.o.o.o.')], [row('open hat', '..x...x...x...x.')]],
     [[], [row('rim', '...x...x...x...x')]]),
    ('UK garage', ['X.........x.....', 'X.....x...x.....', 'X........xx.....'],
     [row('snare', '....x.......x...'), row('clap', '....x.......x...')],
     [[row('hat', '..x...x...x...x.')], [row('hat', '.oxo.oxo.oxo.oxo')],
      [row('open hat', '..x.......x.....')]],
     [[], [row('rim', '.......x......x.')]]),
    ('Speed garage', ['X...x...x...x...'],
     [row('snare', '....x.......x...'), row('clap', '....x.......x...')],
     [[row('hat', '..x...x...x...x.')], [row('open hat', '..x...x...x...x.')]],
     [[], [row('rim', '.......x.x....x.')]]),
    ('Drum and bass', ['X.........x.....', 'X.........x..x..', 'X.x.......x.....'],
     [row('snare', '....x.......x...'), row('snare', '....x..o....x..o')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'oooooooooooooooo')],
      [row('cymbal', 'x.x.x.x.x.x.x.x.')]],
     [[], [row('open hat', '......x.........')]]),
    ('Jungle', ['X.x.......xx....', 'X.........x.x...'],
     [row('snare', '....x..x.x..x..x'), row('snare', '....x..o.x..x...')],
     [[row('cymbal', 'x.x.x.x.x.x.x.x.')], [row('hat', 'oooooooooooooooo')]],
     [[], [row('rim', '..x.......x.....')]]),
    ('Breakbeat', ['X.x.......x.....', 'X.....x.x.......', 'X.x.....x.x.....'],
     [row('snare', '....x.......x...'), row('snare', '....x..x....x..x')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('open hat', '..x...x...x...x.')]],
     [[], [row('tom', '..............xx')]]),
    ('Big beat', ['X.x.....x.x.....', 'X.....x...x.....'],
     [row('snare', '....X.......X...'), row('clap', '....x.......x...')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('open hat', 'x.x.x.x.x.x.x.x.')]],
     [[], [row('tom', '............xxxx')]]),
    ('Boom bap', ['X......x..x.....', 'X.x.......x.....', 'X......x.xx.....'],
     [row('snare', '....X.......X...'), row('clap', '....X.......X...')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'x.x.x.x.x.x.x.xx')],
      [row('open hat', '..............x.')]],
     [[], [row('rim', '..x.........x...')]]),
    ('Lo-fi hip hop', ['X......x..x.....', 'X.....x...x..x..'],
     [row('snare', '....x.......x...'), row('rim', '....x.......x...')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'o.o.o.oxo.o.o.ox')]],
     [[], [row('open hat', '......x.......x.')]]),
    ('Trap', ['X.........x.....', 'X......x..x.....', 'X.....x.......x.'],
     [row('clap', '........X.......'), row('snare', '........X.......')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'x.x.x.x.x.xxx.xx')],
      [row('hat', 'xxxxx.x.x.x.xxxx')]],
     [[], [row('open hat', '......x.........')]]),
    ('Drill', ['X......x..x.....', 'X.....x....x..x.'],
     [row('snare', '........X.......'), row('clap', '...x....X.......')],
     [[row('hat', 'x..x..x.x..x..x.')], [row('hat', 'x.xx..x.x.xx..x.')]],
     [[], [row('rim', '.......x......x.')]]),
    ('Dembow', ['X...x...x...x...'],
     [row('snare', '...x..x....x..x.'), row('rim', '...x..x....x..x.')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'oooooooooooooooo')]],
     [[], [row('clap', '...x..x....x..x.')]]),
    ('Afrobeats', ['X.....x...x.....', 'X..x..x...x.....'],
     [row('rim', '...x..x...x.x...'), row('clap', '....x.......x...')],
     [[row('hat', 'x.xxx.xxx.xxx.xx')], [row('open hat', '..x...x...x...x.')]],
     [[], [row('cowbell', 'x..x..x...x.x...')], [row('tom', '......x......x..')]]),
    ('Electro', ['X.....x...x.....', 'X.....x.x.......'],
     [row('snare', '....X.......X...'), row('clap', '....x.......x...')],
     [[row('hat', 'xxxxxxxxxxxxxxxx')], [row('hat', 'x.x.x.x.x.x.x.x.')]],
     [[], [row('cowbell', '..x.......x...x.')], [row('tom', '..........x.x...')]]),
    ('Miami bass', ['X.....x.x.....x.', 'X..x..x...x.....'],
     [row('clap', '....x.......x...'), row('snare', '....x.......x...')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'xxxxxxxxxxxxxxxx')]],
     [[], [row('cowbell', '..x...x...x...x.')]]),
    ('Dubstep', ['X.........x.....', 'X..........x....'],
     [row('snare', '........X.......'), row('clap', '........X.......')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'x..x..x.x..x..x.')]],
     [[], [row('tom', '..............x.')]]),
    ('Funk', ['X.x....x..x.....', 'X..x...x..x..x..', 'X.x...x...x.....'],
     [row('snare', '....x..o.o..x..o'), row('snare', '....x.......x...')],
     [[row('hat', 'xxxxxxxxxxxxxxxx'), row('open hat', '.......x........')],
      [row('hat', 'x.x.x.x.x.x.x.x.')]],
     [[], [row('cowbell', 'x...x...x...x...')]]),
    ('Rock', ['X.......x.x.....', 'X.x.....x.......', 'X.......x...x...'],
     [row('snare', '....X.......X...')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('cymbal', 'x.x.x.x.x.x.x.x.')],
      [row('open hat', 'x.x.x.x.x.x.x.x.')]],
     [[], [row('tom', '............xxxx')], [row('cymbal', 'x...............')]]),
    ('Pop', ['X.......x.......', 'X.....x.x.......'],
     [row('clap', '....x.......x...'), row('snare', '....x.......x...')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', 'oooooooooooooooo')]],
     [[], [row('rim', '..........x.....')]]),
    ('Reggae one drop', ['........X.......'],
     [row('rim', '........x.......'), row('snare', '........x.......')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('hat', '..x...x...x...x.')]],
     [[], [row('open hat', '..............x.')]]),
    ('Latin', ['X.....x.X.....x.'],
     [row('rim', 'x..x..x...x.x...'), row('rim', '..x.x...x..x..x.')],
     [[row('hat', 'x.x.x.x.x.x.x.x.')], [row('cowbell', 'x.x.x.x.x.x.x.x.')]],
     [[], [row('tom', '...........x..xx')]]),
)

# well-known records' grooves (a bar each, as commonly transcribed: close, not checked
# against the records)
FAMOUS = (
    ('Amen break (The Winstons)', dict(kick='X.x.......xx....', snare='....X..x.x..X..x',
                                       cymbal='x.x.x.x.x.x.x.x.')),
    ('Funky Drummer (James Brown)', dict(kick='X.x...x...x..x..', snare='....X..o.o.oX..o',
                                         hat='xxxxxxx.xxxxxxxx', open_hat='.......x........')),
    ('Think break (Lyn Collins)', dict(kick='X.x.......x.....', snare='....X..x....X...',
                                       hat='x.x.x.x.x.x.x.x.')),
    ('Impeach the President', dict(kick='X......x..x.....', snare='....X.......X...',
                                   hat='x.x.x.x.x.x.x.x.', open_hat='..............x.')),
    ('When the Levee Breaks', dict(kick='XX.....x..x.....', snare='....X.......X...',
                                   hat='x.x.x.x.x.x.x.x.')),
    ('Billie Jean', dict(kick='X.......x.......', snare='....x.......x...',
                         hat='x.x.x.x.x.x.x.x.')),
    ('Superstition', dict(kick='X.....x...x.....', snare='....x.......x...',
                          hat='xxxxxxx.xxxxxxxx', open_hat='.......x.......x')),
    ('Cissy Strut (The Meters)', dict(kick='X..x..x...x.....', snare='....x..o.o..x...',
                                      hat='x.x.x.x.x.x.x.x.')),
    ('Walk This Way', dict(kick='X.......x.x.....', snare='....X.......X...',
                           hat='x.x.x.x.x.x.x.x.')),
    ('We Will Rock You', dict(kick='X.x.....X.x.....', clap='....X.......X...')),
    ('Back in Black', dict(kick='X.......x.......', snare='....X.......X...',
                           hat='x.x.x.x.x.x.x.x.')),
    ('Planet Rock (808)', dict(kick='X.....x...x.....', snare='....X.......X...',
                               hat='xxxxxxxxxxxxxxxx', cowbell='..x...x...x.x...')),
    ('Sexual Healing (808)', dict(kick='X..x....X..x....', snare='....x.......x...',
                                  hat='x.xxx.xxx.xxx.xx', clap='....x.......x...')),
    ('Blue Monday', dict(kick='X...x...x...xxxx', snare='....x.......x...',
                         open_hat='..x...x...x...x.')),
    ('Around the World', dict(kick='X...x...x...x...', clap='....x.......x...',
                              open_hat='..x...x...x...x.', hat='o.o.o.o.o.o.o.o.')),
    ('Show Me Love (house)', dict(kick='X...x...x...x...', clap='....x.......x...',
                                  hat='oooooooooooooooo', rim='...x..x....x..x.')),
    ('Strings of Life (Detroit)', dict(kick='X...x...x...x...', clap='....x.......x...',
                                       open_hat='..x...x...x...x.', rim='x..x..x...x.....')),
    ('Energy Flash (techno)', dict(kick='X...x...x...x...', hat='oooooooooooooooo',
                                   open_hat='..x...x...x...x.', clap='....x.......x...')),
    ('Re-Rewind (UK garage)', dict(kick='X.........x.....', snare='....x.......x...',
                                   hat='.oxo.oxo.oxo.oxo')),
    ('In Da Club', dict(kick='X......x..x.....', clap='....X.......X...',
                        hat='xxxxxxxxxxxxxxxx')),
    ('Dem Bow (Shabba Ranks)', dict(kick='X...x...x...x...', snare='...x..x....x..x.',
                                    hat='x.x.x.x.x.x.x.x.')),
    ('Son clave 3-2', dict(rim='x..x..x...x.x...', kick='X.......X.......',
                           hat='x.x.x.x.x.x.x.x.')),
    ('Bossa nova', dict(rim='x..x..x...x..x..', kick='X..x....X..x....',
                        hat='xxxxxxxxxxxxxxxx')),
    ('One drop (reggae)', dict(kick='........X.......', rim='........x.......',
                               hat='x.x.x.x.x.x.x.x.')),
    ('Half-time dubstep', dict(kick='X.........x.....', snare='........X.......',
                               hat='x.x.x.x.x.x.x.x.')),
    ('Two-step (drum and bass)', dict(kick='X.........x.....', snare='....X.......X...',
                                      hat='x.x.x.x.x.x.x.x.')),
    ('Volt mix (baile funk)', dict(kick='X..x..x...x.....', snare='....x.......x...',
                                   clap='...x..x....x..x.')),
    ('Purdie shuffle (straight)', dict(kick='X.....x.X.....x.', snare='..o.X.o...o.X.o.',
                                       hat='x.x.x.x.x.x.x.x.')),
    ('Motown backbeat', dict(kick='X.x.....X.x.....', snare='....x.......x...',
                             hat='x.x.x.x.x.x.x.x.', clap='....x.......x...')),
    ('Footwork (straight)', dict(kick='X..x..x..x..x...', clap='....x.......x...',
                                 hat='x.x.x.x.x.x.x.x.')),
)


def make_library():
    library = {}
    for name, rows in FAMOUS:
        library['Famous grooves/' + name] = drums(**rows)
    for genre, kicks, backs, hats, extras in GENRES:
        count = 0
        for extra in extras:
            for hat in hats:
                for back in backs:
                    for kick in kicks:
                        if count >= 16:
                            break
                        count += 1
                        parts = [('kick', kick), back] + list(hat) + list(extra)
                        rows = {}
                        for kind, text in parts:
                            rows.setdefault(kind.replace(' ', '_'), text)
                        library['%s/%s %02d' % (genre, genre, count)] = drums(**rows)
    return library


# BT303's: rhythms (a step's gate: x a note, X accented, - slid into from the one before,
# . a rest) by contours (the degrees the notes walk)
BASS_RHYTHMS = (
    ('Acid', ('X.x-x.X.x-.xX.x.', 'x-xx.X.x-x.xX..x', 'Xx.xX.x-xx.Xx.x-')),
    ('Rolling', ('xxxxxxxxxxxxxxxx', 'x.xxx.xxx.xxx.xx', 'Xxx.Xxx.Xxx.Xxx.')),
    ('Octave', ('x.x.x.x.x.x.x.x.', 'X.x.X.x.X.x.X.x.', 'x-x-x-x-x-x-x-x-')),
    ('Walking', ('x...x...x...x...', 'x.x...x.x...x.x.', 'x..x..x.x..x..x.')),
    ('Minimal', ('x.......x.......', 'x.....x...x.....', '..x...x...x...x.')),
    ('Funk', ('X..x..x.x..x.x..', 'x.xX..x..x.xX...', 'X.x..x.xX.x..x..')),
)
CONTOURS = (
    (0,), (0, 7), (0, 0, 7, 0), (0, 2, 4, 5), (0, 4, 3, 2), (0, -1, 0, 2), (0, 3, 5, 7),
    (0, 0, 2, 0, 4, 0, 5, 4), (7, 5, 4, 2, 0), (0, 5, 4, 0, 2, 0, 1, 0),
)


def make_bass_library():
    library = {}
    for style, rhythms in BASS_RHYTHMS:
        count = 0
        for contour in CONTOURS:
            for rhythm in rhythms:
                if count >= 20:
                    break
                count += 1
                line, walk = [], 0
                for k, mark in enumerate(rhythm):
                    if mark == '.':
                        line.append(None)
                        continue
                    degree = contour[walk % len(contour)]
                    if style == 'Octave':
                        degree = contour[walk % len(contour)] + (7 if walk % 2 else 0)
                    walk += 1
                    line.append([degree, mark == 'X', False])
                # (a '-' slides into its note from the one before)
                for k, mark in enumerate(rhythm):
                    if mark == '-' and k and line[k - 1] is not None:
                        line[k - 1][2] = True
                library['%s/%s %02d' % (style, style, count)] = dict(kind='bt303', line=line)
    return library


def make_slice_library():
    # PS1200's: its beats (four slices each) reordered, stuttered, halved, reversed
    import itertools
    library = {}
    beats = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]]
    for k, order in enumerate(list(itertools.permutations(range(4)))[:24]):
        library['Beat swaps/Swap %02d' % (k + 1)] = dict(
            kind='ps1200', order=sum((beats[b] for b in order), []))
    for k in range(16):
        first = beats[k % 4]
        library['Stutters/Stutter %02d' % (k + 1)] = dict(kind='ps1200', order=(
            [first[0]] * (1 + k % 4) + list(range(2 + k % 4, 17)))[:16])
    for k, start in enumerate((1, 5, 9, 13)):
        library['Half time/Half from beat %d' % (k + 1)] = dict(kind='ps1200', order=[
            (start + n // 2 - 1) % 16 + 1 if n % 2 == 0 else 0 for n in range(16)])
    for k in range(4):
        library['Reverse/Beat %d backwards' % (k + 1)] = dict(kind='ps1200', order=sum(
            (beats[b][::-1] if b == k else beats[b] for b in range(4)), []))
    for k in range(12):
        library['Chops/Chop %02d' % (k + 1)] = dict(kind='ps1200', order=[
            ((n * (k + 3)) % 16) + 1 if (n + k) % 5 else 0 for n in range(16)])
    return library


# SY-4's progressions (the key's degrees, as the song's key makes them) in rhythms: each a
# chord a bar over four bars (two in a bar for the eight chord ones)
PROGRESSIONS = (
    ('Epic i VI III VII', (0, 5, 2, 6), 'triad'),
    ('Sad i iv VI v', (0, 3, 5, 4), 'triad'),
    ('Pop I V vi IV', (0, 4, 5, 3), 'triad'),
    ('Axis vi IV I V', (5, 3, 0, 4), 'triad'),
    ('Jazz ii V I vi', (1, 4, 0, 5), 'seventh'),
    ('House i VII VI VII', (0, 6, 5, 6), 'triad'),
    ('Trance i VI VII v', (0, 5, 6, 4), 'triad'),
    ('Dorian i IV', (0, 3, 0, 3), 'seventh'),
    ('Andalusian i VII VI V', (0, 6, 5, 4), 'triad'),
    ('Royal road IV V iii vi', (3, 4, 2, 5), 'seventh'),
    ('Lift VI VII i i', (5, 6, 0, 0), 'add9'),
    ('Deep i iv7', (0, 3, 0, 3), 'seventh'),
    ('Suspended i iv', (0, 3, 0, 3), 'sus2'),
    ('Canon I V vi iii IV I IV V', (0, 4, 5, 2, 3, 0, 3, 4), 'triad'),
)
# (where in a bar a chord is struck, steps held each)
RHYTHMS = (
    ('Pad', ((0, 16),)),
    ('Stabs', ((2, 1), (6, 1), (10, 1), (14, 1))),
    ('Eighths', tuple((k, 1) for k in range(0, 16, 2))),
    ('Gate', tuple((k, 1) for k in range(16) if k % 4 != 3)),
    ('Push', ((0, 3), (3, 3), (6, 10))),
    ('Offbeat holds', ((2, 2), (6, 2), (10, 2), (14, 2))),
)


def make_chord_library():
    library = {}
    for name, degrees, kind in PROGRESSIONS:
        per_bar = 2 if len(degrees) > 4 else 1
        for style, hits in RHYTHMS:
            chords = []
            for k, degree in enumerate(degrees):
                bar_start = (k // per_bar) * 16 + (k % per_bar) * (16 // per_bar)
                for at, held in hits:
                    if at >= 16 // per_bar:
                        continue
                    chords.append([degree, kind, bar_start + at, min(held, 16 // per_bar - at),
                                   0])
            library['%s/%s' % (style, name)] = dict(kind='sy4', bars=4, chords=chords)
    return library


# VR-1's lines (the key's degrees: [degree, start, steps held, accent]): basses and leads
LINES = {
    'Bass/Offbeat': [[0, k, 2, k == 2] for k in (2, 6, 10, 14)],
    'Bass/Rolling sixteenths': [[0, k, 1, k % 4 == 0] for k in range(16)],
    'Bass/Octave bounce': [[0 if k % 4 < 2 else 7, k, 1, k % 4 == 0] for k in range(0, 16, 2)],
    'Bass/Gallop': [[0, k, 1, k % 4 == 0] for k in range(16) if k % 4 != 1],
    'Bass/Walk up': [[d, k * 4, 3, True] for k, d in enumerate((0, 2, 4, 5))],
    'Bass/Minor drop': [[0, 0, 6, True], [-2, 6, 2, False], [-3, 8, 6, True], [-1, 14, 2, False]],
    'Bass/Reese hold': [[0, 0, 8, True], [5, 8, 8, False]],
    'Bass/Acid slide': [[0, 0, 2, True], [0, 2, 1, False], [7, 3, 2, True], [0, 6, 1, False],
                        [3, 8, 2, True], [2, 10, 2, False], [0, 12, 3, True], [6, 15, 1, False]],
    'Lead/Arp up': [[(0, 2, 4, 7)[k % 4], k, 1, k % 4 == 0] for k in range(16)],
    'Lead/Arp down': [[(7, 4, 2, 0)[k % 4], k, 1, k % 4 == 0] for k in range(16)],
    'Lead/Arp bounce': [[(0, 4, 7, 4)[k % 4], k, 1, k % 8 == 0] for k in range(16)],
    'Lead/Trance gate': [[(0, 0, 4, 0, 2, 0, 4, 7)[k % 8], k, 1, k % 4 == 0]
                         for k in range(16) if k % 4 != 3],
    'Lead/Hook rise': [[0, 0, 2, True], [2, 2, 2, False], [4, 4, 4, True], [7, 8, 2, False],
                       [6, 10, 2, False], [4, 12, 4, True]],
    'Lead/Hook fall': [[7, 0, 3, True], [6, 3, 1, False], [4, 4, 4, True], [2, 8, 3, False],
                       [1, 11, 1, False], [0, 12, 4, True]],
    'Lead/Call answer': [[4, 0, 2, True], [4, 2, 1, False], [2, 3, 3, False], [0, 8, 2, True],
                         [2, 10, 1, False], [4, 11, 5, True]],
    'Lead/Long tones': [[0, 0, 8, True], [4, 8, 8, False]],
}


def make_line_library():
    library = {}
    for name, line in LINES.items():
        octave = 36 if name.startswith('Bass/') else 60
        library[name] = dict(kind='vr1', bars=1, line=line, octave=octave)
    return library


def make_synth_sounds(machine):
    import synth
    return dict((name, dict(kind=machine, patch=patch))
                for name, patch in synth.PATCHES[machine].items())


BUILT_IN['rt909']['pattern'].update(make_library())
BUILT_IN['bt303']['pattern'].update(make_bass_library())
BUILT_IN['ps1200']['pattern'].update(make_slice_library())
BUILT_IN['sy4'] = dict(sound=make_synth_sounds('sy4'), pattern=make_chord_library())
BUILT_IN['vr1'] = dict(sound=make_synth_sounds('vr1'), pattern=make_line_library())
# MP-60's: RT909's patterns on its pads (its first pads' sounds: kick 1, snare 2, clap 3,
# hat 4, open hat 5, tom 6, rim 7, cowbell 8, cymbal 16)
PAD_OF = {'kick': 1, 'snare': 2, 'clap': 3, 'hat': 4, 'open hat': 5, 'tom': 6, 'rim': 7,
          'cowbell': 8, 'cymbal': 16}
BUILT_IN['mp60'] = dict(sound={}, pattern=dict(
    (name, dict(kind='mp60', steps=dict(('pad %d' % PAD_OF[row['kind']], row['steps'])
                                        for row in data['rows'] if row['kind'] in PAD_OF)))
    for name, data in BUILT_IN['rt909']['pattern'].items()))
BUILT_IN['sy4']['pattern'].update(('Leads/' + name.split('/')[1], dict(data, kind='sy4'))
                                  for name, data in make_line_library().items()
                                  if name.startswith('Lead/'))
BUILT_IN['vr1']['pattern'].update(('Chords/' + name.split('/', 1)[1], dict(data, kind='vr1'))
                                  for name, data in make_chord_library().items()
                                  if name.startswith('Pad/'))


def list_built_in(machine, what):
    return list(BUILT_IN.get(machine, {}).get(what, {}))


def load_built_in(machine, what, name):
    return BUILT_IN.get(machine, {}).get(what, {}).get(name)
