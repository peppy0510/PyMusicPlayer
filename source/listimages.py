# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import collections
import io
import mfeats
import mutagen
import mutagen.flac
import mutagen.id3
import mutagen.mp4
import numpy
import os
import queue
import radio
import threading
import wx

from PIL import Image
from utilities import get_user_docapp_path


# the list's cover and waveform cells: made on a thread of their own, the rows last asked
# for first (the ones on screen), and kept; a cover once read is kept on disk as a small
# thumbnail, so scrolling never opens the songs again
COVER_SIZE = 64
CACHE_ITEMS = 3000


class ListImages():

    def __init__(self, on_ready):
        # on_ready: called on the GUI thread when a picture asked for is in
        self.on_ready = on_ready
        self.folder = os.path.join(get_user_docapp_path(), 'covers')
        os.makedirs(self.folder, exist_ok=True)
        self.images = collections.OrderedDict()
        self.bitmaps = collections.OrderedDict()
        self.asked = set()
        self.lock = threading.Lock()
        self.jobs = queue.LifoQueue()
        threading.Thread(target=self.Run, daemon=True).start()

    def GetBitmap(self, kind, mdx, path, width, height, ground, square=False):
        '''the cell's bitmap, or None while it is being made (square: a cover cut to a
        square on its middle, View's Square Album Images)'''
        key = (kind, mdx, width, height, tuple(ground), square)
        bitmap = self.bitmaps.get(key)
        if bitmap is not None:
            self.bitmaps.move_to_end(key)
            return bitmap
        with self.lock:
            image = self.images.get(key)
        if image is None:
            if key not in self.asked:
                self.asked.add(key)
                self.jobs.put((key, path))
            # while it is made on its new ground (a row selected, or let go), the same
            # picture on the ground it had: none drawn in the meantime blinked at every
            # click
            return next((v for k, v in reversed(self.bitmaps.items()) if k[:4] == key[:4]),
                        None)
        if image is False:
            return False
        h, w, _ = image.shape
        bitmap = wx.Bitmap.FromBuffer(w, h, image.tobytes())
        self.bitmaps[key] = bitmap
        while len(self.bitmaps) > CACHE_ITEMS:
            self.bitmaps.popitem(last=False)
        return bitmap

    def Forget(self, mdx, kind='wave'):
        # a song analyzed (again): its waveform made anew; a cover put in its tags: its
        # cover read again (the thumbnail on disk too)
        with self.lock:
            for store in (self.bitmaps, self.images):
                for key in [k for k in store if k[1] == mdx and k[0] == kind]:
                    store.pop(key, None)
            self.asked = set(k for k in self.asked if not (k[1] == mdx and k[0] == kind))
        if kind == 'cover':
            try:
                os.remove(os.path.join(self.folder, '%s.png' % (mdx)))
            except OSError:
                pass

    def Run(self):
        while True:
            key, path = self.jobs.get()
            try:
                image = self.Make(key, path)
            except Exception:
                image = False
            # none (a waveform not analyzed yet) kept as none until the song's analysis
            # comes in (Forget), not asked for again at every drawing
            with self.lock:
                self.images[key] = False if image is None else image
                while len(self.images) > CACHE_ITEMS:
                    self.images.popitem(last=False)
            # never let one failure end the thread (no more pictures for the rest of the run)
            try:
                wx.CallAfter(self.on_ready)
            except Exception:
                pass

    def Make(self, key, path):
        kind, mdx, width, height, ground, square = key
        if kind == 'wave':
            return self.MakeWave(mdx, width, height, ground)
        return self.MakeCover(mdx, path, width, height, ground, square)

    def MakeWave(self, mdx, width, height, ground):
        resp = mfeats.getby_key_value('mdx', mdx)
        if resp is None or audio.is_waveform_3band(resp.waveform) is False:
            return None
        return audio.paint_waveform_3band(resp.waveform, width, height, ground=ground)

    def MakeCover(self, mdx, path, width, height, ground, square=False):
        thumbnail = os.path.join(self.folder, '%s.png' % (mdx))
        if os.path.isfile(thumbnail):
            # an empty file: the song has no cover
            if os.path.getsize(thumbnail) == 0:
                return False
            picture = Image.open(thumbnail).convert('RGB')
        else:
            if audio.is_stream_path(path):
                # a station's picture (its favicon), read on this worker
                data = radio.fetch_picture(path)
            else:
                data = read_cover(path)
            if data is None:
                open(thumbnail, 'wb').close()
                return False
            picture = Image.open(io.BytesIO(data)).convert('RGB')
            picture.thumbnail((COVER_SIZE, COVER_SIZE))
            picture.save(thumbnail)
        # fitted in the cell's square as it is (a cover not square was stretched to one),
        # the room it leaves the row's ground; or cut to the square first
        if square:
            picture = picture.crop(get_square_box(*picture.size))
        side = min(width, height)
        scale = 1.0 * side / max(picture.size)
        size = tuple(max(1, int(round(v * scale))) for v in picture.size)
        picture = picture.resize(size, Image.LANCZOS)
        canvas = Image.new('RGB', (width, height), tuple(int(v) for v in ground))
        canvas.paste(picture, ((width - size[0]) // 2, (height - size[1]) // 2))
        return numpy.asarray(canvas, dtype=numpy.uint8)


# a picture's types in the tags: the front cover, or one not said (taken for the cover)
FRONT = 3
COVER_TYPES = (0, FRONT)
# a cover put in a song's tags at most this wide (a photo of 4000 px made every song
# several MB larger) and kept as it is when JPEG or PNG and no wider
COVER_MOST = 1000


def read_cover(path):
    # the front cover in the song's tags (ID3 APIC, FLAC or MP4 cover), else the first
    # picture, or None
    tags = mutagen.File(path)
    if tags is None:
        return None
    pictures = getattr(tags, 'pictures', None)
    if pictures:
        return next((v for v in pictures if v.type == FRONT), pictures[0]).data
    if tags.tags is None:
        return None
    frames = [tags.tags[k] for k in tags.tags.keys() if k.startswith('APIC')]
    if frames:
        return next((v for v in frames if v.type == FRONT), frames[0]).data
    covers = tags.tags.get('covr') if hasattr(tags.tags, 'get') else None
    if covers:
        return bytes(covers[0])
    return None


def make_cover(data):
    '''(bytes, mime, width, height) of a picture to put in tags: JPEG or PNG as it is
    when no wider than COVER_MOST, else made a JPEG that wide; None if not a picture'''
    try:
        picture = Image.open(io.BytesIO(data))
        picture.load()
    except Exception:
        return None
    kind = picture.format
    width, height = picture.size
    if kind in ('JPEG', 'PNG') and max(width, height) <= COVER_MOST:
        return (data, 'image/jpeg' if kind == 'JPEG' else 'image/png', width, height)
    picture = picture.convert('RGB')
    picture.thumbnail((COVER_MOST, COVER_MOST), Image.LANCZOS)
    out = io.BytesIO()
    picture.save(out, 'JPEG', quality=92)
    return (out.getvalue(), 'image/jpeg') + picture.size


def get_square_box(width, height):
    # (left, top, right, bottom) of the middle square
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return (left, top, left + side, top + side)


def is_square(data):
    # (None: not a picture)
    try:
        width, height = Image.open(io.BytesIO(data)).size
    except Exception:
        return None
    return width == height


def crop_square(data):
    '''the picture cut to a square on its middle, its shorter side's size (the tag editor's
    cover menu); PNG kept PNG, any other made a JPEG; None if not a picture'''
    try:
        picture = Image.open(io.BytesIO(data))
        picture.load()
    except Exception:
        return None
    kind = picture.format
    picture = picture.crop(get_square_box(*picture.size))
    out = io.BytesIO()
    if kind == 'PNG':
        picture.save(out, 'PNG')
    else:
        picture.convert('RGB').save(out, 'JPEG', quality=92)
    return out.getvalue()


def write_cover(path, data):
    '''the picture put in the song's tags as its front cover (MP3, FLAC, MP4/M4A), the
    other pictures (a back cover, the artist) kept; raises ValueError for a picture or a
    file it cannot'''
    cover = make_cover(data)
    if cover is None:
        raise ValueError('not a picture')
    data, mime, width, height = cover
    kind = os.path.splitext(path)[1].lower()
    if kind == '.mp3':
        try:
            tags = mutagen.id3.ID3(path)
        except mutagen.id3.ID3NoHeaderError:
            tags = mutagen.id3.ID3()
        for key in [k for k in tags.keys() if k.startswith('APIC')]:
            if tags[key].type in COVER_TYPES:
                del tags[key]
        tags.add(mutagen.id3.APIC(encoding=3, mime=mime, type=FRONT, desc='', data=data))
        tags.save(path)
    elif kind == '.flac':
        song = mutagen.flac.FLAC(path)
        kept = [v for v in song.pictures if v.type not in COVER_TYPES]
        song.clear_pictures()
        picture = mutagen.flac.Picture()
        picture.type, picture.mime, picture.data = FRONT, mime, data
        picture.width, picture.height, picture.depth = width, height, 24
        for v in [picture] + kept:
            song.add_picture(v)
        song.save()
    elif kind in ('.m4a', '.mp4', '.aac', '.alac'):
        song = mutagen.mp4.MP4(path)
        if song.tags is None:
            song.add_tags()
        imageformat = mutagen.mp4.MP4Cover.FORMAT_PNG if mime == 'image/png'\
            else mutagen.mp4.MP4Cover.FORMAT_JPEG
        song.tags['covr'] = [mutagen.mp4.MP4Cover(data, imageformat=imageformat)]
        song.save()
    else:
        raise ValueError('covers are not put in %s files' % (kind.lstrip('.').upper()))


def remove_cover(path):
    '''every picture taken out of the song's tags (MP3, FLAC, MP4/M4A: the front cover
    alone left the back one shown as its cover); raises ValueError for a file it cannot'''
    kind = os.path.splitext(path)[1].lower()
    if kind == '.mp3':
        try:
            tags = mutagen.id3.ID3(path)
        except mutagen.id3.ID3NoHeaderError:
            return
        tags.delall('APIC')
        tags.save(path)
    elif kind == '.flac':
        song = mutagen.flac.FLAC(path)
        song.clear_pictures()
        song.save()
    elif kind in ('.m4a', '.mp4', '.aac', '.alac'):
        song = mutagen.mp4.MP4(path)
        if song.tags is not None and 'covr' in song.tags:
            del song.tags['covr']
            song.save()
    else:
        raise ValueError('covers are not taken out of %s files' % (kind.lstrip('.').upper()))
