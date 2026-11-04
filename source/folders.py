# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import library
import os
import radio
import re
import stat
import threading
import wx

from macroboxlib import GetPreference
from macroboxlib import ListBoxColumn
from macroboxlib import MakeMusicFileItem
from macroboxlib import SUPPORTED_AUDIO_TYPE
from macroboxlib import SetPreference
from utilities import Struct


# the sidebar's folders: roots as rows, one folder open at a time in its tab
# cached: the sidebar asks at every drawing, GetPreference opens the file
STATE = None
# a newer folder read stops the one before
JOB = [0]
# the folder shown, and each folder left: (scroll, selected path)
SHOWN = [None]
# the folder open when the player was last closed
STARTED = [None]
PLACES = dict()
PLACES_MOST = 500
HIDDEN = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM
# rows filled in from their files at a time
FILL_BATCH = 25
# a folder row's status, and the parent's name
FOLDER_STATUS = 'folder'
PARENT_NAME = '..'


def get_state():
    global STATE
    if STATE is None:
        STATE = Struct(roots=list(GetPreference('folder_roots') or []),
                       current=GetPreference('folder_current'),
                       analyzed=list(GetPreference('folder_analyzed') or []))
        STARTED[0] = STATE.current
    return STATE


def get_current():
    return get_state().current


def get_key(path):
    return os.path.normcase(os.path.abspath(path))


def is_same(one, other):
    return one is not None and other is not None and get_key(one) == get_key(other)


def is_under(path, root):
    # path is root or in it, at any depth
    key, top = get_key(path), get_key(root)
    return key == top or key.startswith(top.rstrip('\\/') + os.sep)


def get_name(path):
    # a drive's root by its letter (D:\)
    return os.path.basename(path.rstrip('\\/')) or path


def sort_key(path):
    # as the Explorer sorts: numbers by value (2 before 10)
    return [int(v) if v.isdigit() else v for v in re.split(r'(\d+)', get_name(path).lower())]


def read_dir(path):
    '''(subfolders, songs as (path, size)), hidden and system left out, or None'''
    folders, songs = [], []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.stat().st_file_attributes & HIDDEN:
                        continue
                    if entry.is_dir():
                        folders.append(entry.path)
                    elif os.path.splitext(entry.name)[1][1:].lower() in SUPPORTED_AUDIO_TYPE:
                        songs.append((entry.path, entry.stat().st_size))
                except OSError:
                    continue
    except OSError:
        return None
    folders.sort(key=sort_key)
    songs.sort(key=lambda v: sort_key(v[0]))
    return folders, songs


def get_owner(path):
    # the nearest root (a root may be in another)
    roots = [v for v in get_state().roots if is_under(path, v)]
    return max(roots, key=lambda v: len(get_key(v))) if roots else None


def is_analyzed(path):
    # path is under a root chosen for the analysis
    owner = get_owner(path) if path is not None else None
    return owner is not None and any(is_same(v, owner) for v in get_state().analyzed)


def is_browsed_only(inner):
    '''the folder's tab, its root not chosen for the analysis'''
    return inner.title == library.FOLDER_TITLE and is_analyzed(get_state().current) is False


def toggle_analyzed(mainpanel, root):
    '''the root's songs queued for the analysis, or no more: True when queued'''
    state = get_state()
    on = any(is_same(v, root) for v in state.analyzed) is False
    state.analyzed = [v for v in state.analyzed if is_same(v, root) is False]
    if on:
        state.analyzed.append(root)
    SetPreference('folder_analyzed', state.analyzed)
    scheduler = mainpanel.MFEATS
    if on is False:
        playing = mainpanel.PlayBox.cue.path
        scheduler.taskpath = [v for v in scheduler.taskpath
                              if v == playing or is_under(v, root) is False]
    # off: the playlists' songs let go with them queued again
    scheduler.AutoAnalyzer()
    if scheduler.IsAutoAnalyzerOn() is False:
        radio.tell(mainpanel, 'Auto Analyze is off (Option menu)', warn=True)
    return on


def get_entries():
    '''the sidebar's folder rows, Struct(path, name, kind)'''
    entries = [Struct(path=root, name=get_name(root), kind='root')
               for root in get_state().roots]
    entries.append(Struct(path=None, name='Add Folder...', kind='add'))
    return entries


def save_state():
    state = get_state()
    SetPreference('folder_roots', state.roots)
    SetPreference('folder_current', state.current)
    SetPreference('folder_analyzed', state.analyzed)


def add_root(path):
    state = get_state()
    path = os.path.abspath(path)
    if any(is_same(v, path) for v in state.roots) is False:
        state.roots.append(path)
    save_state()


def remove_root(path):
    # only its row taken off the sidebar, the folder left
    state = get_state()
    state.roots = [v for v in state.roots if is_same(v, path) is False]
    state.analyzed = [v for v in state.analyzed if is_same(v, path) is False]
    if state.current is not None and get_owner(state.current) is None:
        state.current = None
    save_state()


def ask_root(mainpanel):
    # a root chosen in the system's dialog, opened
    if not mainpanel:
        return
    state = get_state()
    start = state.current or (state.roots[-1] if state.roots else '')
    dialog = wx.DirDialog(mainpanel, 'Add a folder to the sidebar', start,
                          style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
    try:
        if dialog.ShowModal() != wx.ID_OK:
            return
        path = dialog.GetPath()
    finally:
        dialog.Destroy()
    add_root(path)
    open_folder(mainpanel, path)


def open_in_explorer(path):
    try:
        os.startfile(path)
    except OSError:
        pass


def open_folder(mainpanel, path, focus=None):
    '''rows at once from the names, the songs' tags filled in after'''
    state = get_state()
    state.current = path
    SetPreference('folder_current', path)
    JOB[0] += 1
    job = JOB[0]

    def read():
        found = read_dir(path)
        if JOB[0] != job:
            return
        folders, songs = found if found is not None else ([], [])
        wx.CallAfter(show_folder, mainpanel, path, folders, songs, found is not None, focus,
                     job)
        fill_rows(mainpanel, [v[0] for v in songs], job)

    threading.Thread(target=read, daemon=True).start()


def open_root(mainpanel, root):
    '''the folder open under root shown again, else the root itself'''
    current = get_state().current
    owner = get_owner(current) if current is not None else None
    if is_folder_view(mainpanel.ListBox) is False and is_same(owner, root):
        open_folder(mainpanel, current)
    else:
        open_folder(mainpanel, root)


def go_up(mainpanel):
    '''the parent opened, not over its root: False when there is none'''
    current = get_state().current
    owner = get_owner(current) if current is not None else None
    if owner is None or is_same(owner, current):
        return False
    open_folder(mainpanel, os.path.dirname(current.rstrip('\\/')), focus=current)
    return True


def open_row(mainpanel, item):
    listbox = mainpanel.ListBox
    if listbox.GetItemValueByColumnKey(item, 'filename') == PARENT_NAME:
        go_up(mainpanel)
    else:
        open_folder(mainpanel, listbox.GetItemValueByColumnKey(item, 'path'))


def is_folder_view(listbox):
    return listbox.innerList[listbox.selectedList].title == library.FOLDER_TITLE


def is_folder_item(listbox, item, listIdx=None):
    # another tab's columns may have no status (a station's)
    inner = listbox.innerList[listbox.selectedList if listIdx is None else listIdx]
    if inner.title != library.FOLDER_TITLE:
        return False
    try:
        return listbox.GetItemValueByColumnKey(item, 'status', listIdx) == FOLDER_STATUS
    except IndexError:
        return False


def get_selected_folders(listbox):
    if is_folder_view(listbox) is False:
        return []
    return [v for v in listbox.GetSelectedItems() if is_folder_item(listbox, v)]


def get_drag_paths(listbox, paths):
    # subfolders dragged whole, not '..'
    if is_folder_view(listbox) is False:
        return paths
    parents = set(listbox.GetItemValueByColumnKey(v, 'path')
                  for v in get_selected_folders(listbox)
                  if listbox.GetItemValueByColumnKey(v, 'filename') == PARENT_NAME)
    return [v for v in paths if v not in parents]


def arrange(items, keys):
    # '..' first, the subfolders, the songs, each kept in its order
    statusIdx, nameIdx = keys.index('status'), keys.index('filename')

    def rank(row):
        if row[statusIdx] != FOLDER_STATUS:
            return 2
        return 0 if row[nameIdx] == PARENT_NAME else 1
    return sorted(items, key=rank)


def make_folder_row(path, name, order, keys):
    values = dict(status=FOLDER_STATUS, order=order, path=path, filename=name)
    return tuple(values.get(k, '') for k in keys)


def make_quick_row(path, size, order, keys):
    # from its name alone, its file read after
    values = dict(status='', order=order, path=path, mdx=audio.makemdx(path) or '',
                  filename=os.path.splitext(os.path.basename(path))[0],
                  size=f'{size / 1024.0 ** 2:.2f} MB')
    return tuple(values.get(k, '') for k in keys)


def get_tab(listbox):
    index = [i for i, v in enumerate(listbox.innerList) if v.title == library.FOLDER_TITLE]
    if index:
        return index[0]
    listbox.AddInnerList(library.FOLDER_TITLE)
    return len(listbox.innerList) - 1


def show_folder(mainpanel, path, folders, songs, readable, focus, job):
    if not mainpanel or JOB[0] != job:
        return
    listbox = mainpanel.ListBox
    # the filter let go
    search = mainpanel.ListSearch
    if search.SearchText.GetValue():
        search.SearchText.ChangeValue('')
    listbox.SetFilterOffAll()
    index = get_tab(listbox)
    inner = listbox.innerList[index]
    keys = [v.key for v in inner.columns]
    pathIdx = keys.index('path')
    # first shown: the rows saved are the folder open when the player closed
    previous = SHOWN[0] if SHOWN[0] is not None or not inner.items else STARTED[0]
    if previous is not None:
        selected = inner.focus.item
        cursor = inner.items[selected][pathIdx] if 0 <= selected < len(inner.items) else None
        PLACES.pop(get_key(previous), None)
        PLACES[get_key(previous)] = (inner.rects.offset.y, cursor)
        while len(PLACES) > PLACES_MOST:
            PLACES.pop(next(iter(PLACES)))
    place = PLACES.get(get_key(path))
    offset, cursor = place if place is not None else (0, None)
    rows = []
    owner = get_owner(path)
    if owner is not None and is_same(owner, path) is False:
        rows.append(make_folder_row(os.path.dirname(path.rstrip('\\/')), PARENT_NAME, 1, keys))
    for folder in folders:
        rows.append(make_folder_row(folder, get_name(folder), len(rows) + 1, keys))
    for song, size in songs:
        rows.append(make_quick_row(song, size, len(rows) + 1, keys))
    inner.items = rows
    inner.filterCache = None
    inner.filterQuery = None
    inner.selectedItems = []
    inner.lastSortedColumn = [keys.index('order') if 'order' in keys else None, 1]
    inner.rects.offset.y = offset
    SHOWN[0] = path
    listbox.SetSelectedList(index)
    # rows may be fewer now: the scroll kept in them
    listbox.SetVirtualPositionY(listbox.GetVirtualPositionY())
    # the folder come from, else the row selected when left, else the first
    focus = focus if focus is not None else cursor
    found = [i for i, row in enumerate(rows)
             if focus is not None and is_same(row[pathIdx], focus)]
    # come back to: the scroll as left, the selected row not scrolled to
    if rows and place is not None:
        item = found[0] if found else 0
        inner.selectedItems = [item]
        inner.focus.item = inner.focus.shift = item
    elif rows:
        listbox.SelectAndFocusItem(found[0] if found else 0)
    # the search field's hint
    search.SetMode(search.GetMode(), force=True)
    if readable is False:
        radio.tell(mainpanel, f'{path} cannot be read', warn=True)
    else:
        radio.tell(mainpanel, f'{len(folders)} folders, {len(songs)} tracks in '
                              f'{get_name(path)}')
    mainpanel.ListTab.TabList.reInitBuffer = True
    mainpanel.ListTab.SliderV.reInitBuffer = True


def fill_rows(mainpanel, paths, job):
    # read from their files, put in by path in batches on the GUI thread
    columns = ListBoxColumn()
    keys = [v.key for v in columns]
    found = dict()
    for path in paths:
        if JOB[0] != job:
            return
        item = MakeMusicFileItem(path, 0, columns)
        if item is None:
            continue
        found[path] = dict(zip(keys, item))
        if len(found) >= FILL_BATCH:
            wx.CallAfter(put_rows, mainpanel, found, job)
            found = dict()
    if found:
        wx.CallAfter(put_rows, mainpanel, found, job)
    wx.CallAfter(queue_rows, mainpanel, job)


def queue_rows(mainpanel, job):
    # out of date songs queued, all under a root chosen for the analysis
    if not mainpanel or JOB[0] != job:
        return
    mainpanel.MFEATS.AutoAnalyzer()


def put_rows(mainpanel, found, job):
    if not mainpanel or JOB[0] != job:
        return
    listbox = mainpanel.ListBox
    for inner in listbox.innerList:
        if inner.title != library.FOLDER_TITLE:
            continue
        keys = [v.key for v in inner.columns]
        pathIdx = keys.index('path')
        # rows are tuples, replaced whole; their order kept (sorted, or moved)
        for rows in (inner.items, inner.filterCache or []):
            for i, row in enumerate(rows):
                values = found.get(row[pathIdx])
                if values is None:
                    continue
                rows[i] = tuple(row[k] if key == 'order' else values.get(key, row[k])
                                for k, key in enumerate(keys))
    listbox.reInitBuffer = True
    listbox.List.reInitBuffer = True
