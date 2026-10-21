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
import numpy
import os
import queue
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

    def GetBitmap(self, kind, mdx, path, width, height, ground):
        '''the cell's bitmap, or None while it is being made'''
        key = (kind, mdx, width, height, tuple(ground))
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
            return None
        if image is False:
            return False
        h, w, _ = image.shape
        bitmap = wx.Bitmap.FromBuffer(w, h, image.tobytes())
        self.bitmaps[key] = bitmap
        while len(self.bitmaps) > CACHE_ITEMS:
            self.bitmaps.popitem(last=False)
        return bitmap

    def Forget(self, mdx):
        # a song analyzed (again): its waveform made anew
        with self.lock:
            for store in (self.bitmaps, self.images):
                for key in [k for k in store if k[1] == mdx and k[0] == 'wave']:
                    store.pop(key, None)
            self.asked = set(k for k in self.asked if not (k[1] == mdx and k[0] == 'wave'))

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
        kind, mdx, width, height, ground = key
        if kind == 'wave':
            return self.MakeWave(mdx, width, height, ground)
        return self.MakeCover(mdx, path, width, height, ground)

    def MakeWave(self, mdx, width, height, ground):
        resp = mfeats.getby_key_value('mdx', mdx)
        if resp is None or audio.is_waveform_3band(resp.waveform) is False:
            return None
        return audio.paint_waveform_3band(resp.waveform, width, height, ground=ground)

    def MakeCover(self, mdx, path, width, height, ground):
        thumbnail = os.path.join(self.folder, '%s.png' % (mdx))
        if os.path.isfile(thumbnail):
            # an empty file: the song has no cover
            if os.path.getsize(thumbnail) == 0:
                return False
            picture = Image.open(thumbnail).convert('RGB')
        else:
            data = read_cover(path)
            if data is None:
                open(thumbnail, 'wb').close()
                return False
            picture = Image.open(io.BytesIO(data)).convert('RGB')
            picture.thumbnail((COVER_SIZE, COVER_SIZE))
            picture.save(thumbnail)
        side = min(width, height)
        picture = picture.resize((side, side), Image.LANCZOS)
        canvas = Image.new('RGB', (width, height), tuple(int(v) for v in ground))
        canvas.paste(picture, ((width - side) // 2, (height - side) // 2))
        return numpy.asarray(canvas, dtype=numpy.uint8)


def read_cover(path):
    # the first picture in the song's tags (ID3 APIC, FLAC or MP4 cover), or None
    tags = mutagen.File(path)
    if tags is None:
        return None
    pictures = getattr(tags, 'pictures', None)
    if pictures:
        return pictures[0].data
    if tags.tags is None:
        return None
    for key in tags.tags.keys():
        if key.startswith('APIC'):
            return tags.tags[key].data
    covers = tags.tags.get('covr') if hasattr(tags.tags, 'get') else None
    if covers:
        return bytes(covers[0])
    return None
