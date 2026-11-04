# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import audio
import collections
import io
import mfeats
import math
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
from PIL import ImageOps
from PIL import ImageStat
from utilities import get_user_docapp_path


# cover and waveform cells made on a worker, newest first; covers cached on disk
COVER_SIZE = 64
CACHE_ITEMS = 3000


class ListImages():

    def __init__(self, on_ready):
        # on_ready: called on the GUI thread when a picture is in
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
        '''the cell's bitmap, or None while it is being made'''
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
            # old ground's picture until the new one is made, or it blinks
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
        # song reanalyzed or its cover changed: make it anew
        with self.lock:
            for store in (self.bitmaps, self.images):
                for key in [k for k in store if k[1] == mdx and k[0] == kind]:
                    store.pop(key, None)
            self.asked = set(k for k in self.asked if not (k[1] == mdx and k[0] == kind))
        if kind == 'cover':
            try:
                os.remove(os.path.join(self.folder, f'{mdx}.png'))
            except OSError:
                pass

    def Run(self):
        while True:
            key, path = self.jobs.get()
            try:
                image = self.Make(key, path)
            except Exception:
                image = False
            # none kept as none until the analysis comes in
            with self.lock:
                self.images[key] = False if image is None else image
                while len(self.images) > CACHE_ITEMS:
                    self.images.popitem(last=False)
            # one failure must not end the thread
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
        thumbnail = os.path.join(self.folder, f'{mdx}.png')
        if os.path.isfile(thumbnail):
            # empty file: no cover
            if os.path.getsize(thumbnail) == 0:
                return False
            picture = Image.open(thumbnail).convert('RGB')
        else:
            if audio.is_stream_path(path):
                # station favicon, read on this worker
                data = radio.fetch_picture(path)
            else:
                data = read_cover(path)
            if data is None:
                open(thumbnail, 'wb').close()
                return False
            picture = Image.open(io.BytesIO(data)).convert('RGB')
            picture.thumbnail((COVER_SIZE, COVER_SIZE))
            picture.save(thumbnail)
        # fitted in the square as it is, or cut to the square first
        if square:
            picture = picture.crop(get_square_box(*picture.size))
        side = min(width, height)
        scale = 1.0 * side / max(picture.size)
        size = tuple(max(1, int(round(v * scale))) for v in picture.size)
        picture = picture.resize(size, Image.LANCZOS)
        canvas = Image.new('RGB', (width, height), tuple(int(v) for v in ground))
        canvas.paste(picture, ((width - size[0]) // 2, (height - size[1]) // 2))
        return numpy.asarray(canvas, dtype=numpy.uint8)


# picture types taken as the cover: front or unspecified
FRONT = 3
COVER_TYPES = (0, FRONT)
# cover width cap; JPEG or PNG within it kept as is
COVER_MOST = 1000


def read_cover(path):
    # front cover in the tags, else the first picture, or None
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
    '''(bytes, mime, width, height) for tags, or None'''
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
    # None: not a picture
    try:
        width, height = Image.open(io.BytesIO(data)).size
    except Exception:
        return None
    return width == height


# straighten: max angle, least gain over level
TILT_MOST = 5.0
TILT_STEP = 0.1
TILT_GAIN = 1.08
# size the tilt is found at
TILT_SIZE = 400
# trim: max edge share, extra share past it
TRIM_MOST = 0.06
TRIM_EXTRA = 0.01
TRIM_UNLIKE = 32
TRIM_SHARE = 0.75
# square: slide to the most mirror-like spot, least gain over the middle
CENTER_GAIN = 0.85
# all found at this size
FIND_SIZE = 240
# narrower than this is no scan
SCAN_LEAST = 32


def find_tilt(picture):
    # degrees to level it (PIL rotate, counter-clockwise)
    small = picture.convert('L')
    small.thumbnail((TILT_SIZE, TILT_SIZE))
    pixels = numpy.asarray(small, dtype=numpy.float32)
    edges = numpy.abs(numpy.diff(pixels, axis=0))[:, :-1] + \
        numpy.abs(numpy.diff(pixels, axis=1))[:-1, :]
    # leave out the scan's own level rim
    down, across = (int(v * TRIM_MOST) + 1 for v in edges.shape)
    edges = edges[down:-down, across:-across]
    # sample pixels anywhere in them, not at the middle, or level always wins
    jitter = numpy.random.RandomState(0).random_sample((2,) + edges.shape) - 0.5
    ys, xs = numpy.indices(edges.shape) + jitter
    ys = (ys - edges.shape[0] / 2.0).ravel()
    xs = (xs - edges.shape[1] / 2.0).ravel()
    # strong edges count the most
    weights = (edges ** 2).ravel()
    reach = int(math.hypot(*edges.shape)) + 1

    def score(angle):
        # sum edges along the turned rows and columns, not a turned picture
        sine, cosine = math.sin(math.radians(angle)), math.cos(math.radians(angle))
        rows = numpy.bincount(numpy.rint(ys * cosine - xs * sine).astype(int) + reach,
                              weights=weights)
        columns = numpy.bincount(numpy.rint(xs * cosine + ys * sine).astype(int) + reach,
                                 weights=weights)
        return (rows ** 2).sum() + (columns ** 2).sum()

    # steps of five, then around the best
    count = int(TILT_MOST / TILT_STEP)
    scores = dict((k, score(k * TILT_STEP)) for k in range(-count, count + 1, 5))
    near = max(scores, key=scores.get)
    for k in range(max(near - 4, -count), min(near + 4, count) + 1):
        if k not in scores:
            scores[k] = score(k * TILT_STEP)
    best = max(scores, key=scores.get)
    # not >: a flat picture would turn the most
    if not scores[best] > scores[0] * TILT_GAIN:
        return 0.0
    return best * TILT_STEP


def straighten(picture, angle):
    # turned, cut to the largest whole rectangle
    if angle == 0:
        return picture
    width, height = picture.size
    sine, cosine = abs(math.sin(math.radians(angle))), math.cos(math.radians(angle))
    scale = min(width / (width * cosine + height * sine),
                height / (width * sine + height * cosine))
    turned = picture.rotate(angle, Image.BICUBIC)
    across, down = int(width * scale), int(height * scale)
    left, top = (width - across) // 2, (height - down) // 2
    return turned.crop((left, top, left + across, top + down))


def find_trim_box(picture):
    # (left, top, right, bottom) without the edge
    width, height = picture.size
    small = picture.convert('RGB')
    small.thumbnail((FIND_SIZE, FIND_SIZE))
    pixels = numpy.asarray(small, dtype=numpy.float32)

    def side(lines):
        # share cut from the edge: the last line most unlike the inside
        depth = len(lines)
        most = max(1, int(depth * TRIM_MOST))
        inside = numpy.median(lines[most:most + max(2, int(depth * 0.04))], axis=0)
        cut = 0
        for i in range(most):
            unlike = numpy.abs(lines[i] - inside).mean(axis=1) > TRIM_UNLIKE
            if unlike.mean() >= TRIM_SHARE:
                cut = i + 1
        return cut / float(depth) + TRIM_EXTRA

    across = pixels.transpose(1, 0, 2)
    left, right = side(across), side(across[::-1])
    top, bottom = side(pixels), side(pixels[::-1])
    return (int(round(width * left)), int(round(height * top)),
            width - int(round(width * right)), height - int(round(height * bottom)))


def find_square_middle(picture):
    # offset along the longer side most like its mirror
    width, height = picture.size
    long, side = max(width, height), min(width, height)
    small = picture.convert('L')
    small.thumbnail((FIND_SIZE, FIND_SIZE))
    pixels = numpy.asarray(small, dtype=numpy.float32)
    axis = 1 if width >= height else 0
    count = pixels.shape[axis]
    window = max(1, int(round(side * count / float(long))))
    scores = dict()
    # doubled so a half-pixel middle works
    for double in range(window, 2 * count - window + 1):
        length = window - (window - double) % 2
        first = (double - length) // 2
        part = numpy.take(pixels, range(first, first + length), axis=axis)
        scores[double] = numpy.abs(part - numpy.flip(part, axis=axis)).mean()
    if count not in scores:
        return long / 2.0
    best = min(scores, key=scores.get)
    if scores[best] > scores[count] * CENTER_GAIN:
        best = count
    return long * best / (2.0 * count)


def get_subject_square_box(picture):
    # square of the shorter side slid to the subject
    width, height = picture.size
    side = min(width, height)
    middle = find_square_middle(picture)
    start = min(max(int(round(middle - side / 2.0)), 0), max(width, height) - side)
    if width >= height:
        return (start, 0, start + side, side)
    return (0, start, side, start + side)


def cut_picture(picture, scan=False, square=False):
    '''scan straightened and trimmed, cut square on its subject'''
    if scan and min(picture.size) >= SCAN_LEAST:
        picture = straighten(picture, find_tilt(picture))
        picture = picture.crop(find_trim_box(picture))
    if square and picture.size[0] != picture.size[1]:
        picture = picture.crop(get_subject_square_box(picture))
    return picture


def cut_cover(data, scan=False, square=False):
    '''the picture cut as cut_picture; None if not a picture'''
    try:
        picture = Image.open(io.BytesIO(data))
        picture.load()
    except Exception:
        return None
    kind = picture.format
    picture = cut_picture(picture, scan, square)
    out = io.BytesIO()
    if kind == 'PNG':
        picture.save(out, 'PNG')
    else:
        picture.convert('RGB').save(out, 'JPEG', quality=92)
    return out.getvalue()


# auto brightness: lift below the first mean, lower above the second, by gamma
BRIGHTNESS_RANGE = (100, 185)
GAMMA_MOST = (0.55, 1.4)
# auto color: gray-world strength, 0-1
COLOR_PULL = 0.6


def adjust_cover(data, scan=False, square=False, contrast=False, brightness=False,
                 color=False):
    '''the picture prepared for Look Up Cover'''
    if not (scan or square or contrast or brightness or color):
        return data
    try:
        picture = Image.open(io.BytesIO(data))
        picture.load()
    except Exception:
        return data
    kind = picture.format
    picture = cut_picture(picture, scan, square)
    if contrast or brightness or color:
        alpha = picture.getchannel('A') if picture.mode in ('RGBA', 'LA') else None
        picture = picture.convert('RGB')
        if color:
            means = ImageStat.Stat(picture).mean
            gray = sum(means) / 3.0
            gains = [1 + COLOR_PULL * (gray / max(v, 1) - 1) for v in means]
            bands = [band.point(lambda v, g=g: min(255, int(v * g + 0.5)))
                     for band, g in zip(picture.split(), gains)]
            picture = Image.merge('RGB', bands)
        if contrast:
            picture = ImageOps.autocontrast(picture, cutoff=1, preserve_tone=True)
        if brightness:
            mean = ImageStat.Stat(picture.convert('L')).mean[0]
            low, high = BRIGHTNESS_RANGE
            aim = low if mean < low else high if mean > high else None
            if aim is not None and 0 < mean < 255:
                least, most = GAMMA_MOST
                gamma = min(max(math.log(aim / 255.0) / math.log(mean / 255.0), least), most)
                table = [int(255 * (v / 255.0) ** gamma + 0.5) for v in range(256)]
                picture = picture.point(table * 3)
        if alpha is not None and kind == 'PNG':
            picture.putalpha(alpha)
    out = io.BytesIO()
    if kind == 'PNG':
        picture.save(out, 'PNG')
    else:
        picture.convert('RGB').save(out, 'JPEG', quality=92)
    return out.getvalue()


def write_cover(path, data):
    '''put the picture in the tags as the front cover'''
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
        raise ValueError(f'covers are not put in {kind.lstrip(".").upper()} files')


def remove_cover(path):
    '''remove every picture from the song's tags'''
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
        raise ValueError(f'covers are not taken out of {kind.lstrip(".").upper()} files')
