# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import numpy
import os
import sys

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


OUTPUT = os.path.join('assets', 'icon', 'filetypes')
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
# small sizes drawn at this multiple, then reduced
SCALE = 8
FONT = 'C:\\Windows\\Fonts\\bahnschrift.ttf'
FONT_VARIATION = b'Bold Condensed'

# the app icon's chevron on a unit square
CHEVRON = ((0.375, 0.0), (0.875, 0.5), (0.375, 1.0), (0.125, 0.75), (0.38, 0.5), (0.125, 0.25))

# bottom-left to top-right; hues differ by more than red and green
WARM = ((201, 52, 36), (222, 110, 72), (240, 184, 150))
COOL = ((26, 74, 168), (52, 124, 214), (150, 200, 240))
SLATE = ((38, 42, 50), (70, 78, 92), (140, 150, 166))

FAMILIES = {
    'mp3': WARM, 'm4a': WARM, 'aac': WARM, 'ogg': WARM, 'wma': WARM, 'mp2': WARM, 'ac3': WARM,
    'flac': COOL, 'wav': COOL, 'aiff': COOL,
    'm3u': SLATE,
}


def get_gradient(size, stops):
    # across the page, as the app icon's
    axis = numpy.linspace(0.0, 1.0, size)
    x, y = numpy.meshgrid(axis, axis)
    share = numpy.clip((x + (1.0 - y)) / 2.0, 0.0, 1.0)[..., None]
    low, mid, high = (numpy.array(v, dtype=float) for v in stops)
    lower = low + (mid - low) * numpy.clip(share * 2.0, 0.0, 1.0)
    upper = mid + (high - mid) * numpy.clip(share * 2.0 - 1.0, 0.0, 1.0)
    rgb = numpy.where(share < 0.5, lower, upper).astype(numpy.uint8)
    return Image.fromarray(rgb, 'RGB').convert('RGBA')


def get_layout(size):
    # (page left, top, right, bottom, fold) on a 1.0 canvas; small pages fill it
    if size <= 20:
        return 0.09, 0.0, 0.91, 1.0, 0.30
    if size <= 32:
        return 0.10, 0.0, 0.90, 1.0, 0.27
    return 0.12, 0.02, 0.88, 0.98, 0.25


def draw_label(canvas, label, centre, width, height, ink):
    font = ImageFont.truetype(FONT, 100)
    font.set_variation_by_name(FONT_VARIATION)
    left, top, right, bottom = font.getbbox('H')
    pixels = int(100.0 * height / (bottom - top))
    font = ImageFont.truetype(FONT, pixels)
    font.set_variation_by_name(FONT_VARIATION)
    if font.getlength(label) > width:
        pixels = int(pixels * width / font.getlength(label))
        font = ImageFont.truetype(FONT, pixels)
        font.set_variation_by_name(FONT_VARIATION)
    ImageDraw.Draw(canvas).text(centre, label, font=font, fill=ink, anchor='mm')


def draw_chevron(canvas, centre, height, ink):
    x, y = centre
    points = [(x + (px - 0.5) * height, y + (py - 0.5) * height) for px, py in CHEVRON]
    ImageDraw.Draw(canvas).polygon(points, fill=ink)


def draw_list(canvas, box, ink):
    # three rows after a small chevron: a playlist
    left, top, right, bottom = box
    height = bottom - top
    row = height / 5.0
    draw = ImageDraw.Draw(canvas)
    for index in range(3):
        y = top + row * index * 2
        draw.rectangle((left + (row * 3.0 if index == 0 else 0), y, right, y + row), fill=ink)
    draw_chevron(canvas, (left + row * 1.1, top + row * 0.5), row * 2.6, ink)


def make_page(size, ext):
    full = size * SCALE
    left, top, right, bottom, fold = get_layout(size)
    left, top, right, bottom = (int(v * full) for v in (left, top, right, bottom))
    fold = int(fold * (right - left))
    radius = max(int(full * 0.045), SCALE)

    mask = Image.new('L', (full, full), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((left, top, right - 1, bottom - 1), radius, fill=255)
    # the folded corner is cut away
    draw.polygon(((right - fold, top - 1), (right + 1, top - 1), (right + 1, top + fold)), fill=0)
    draw.rectangle((right - fold, top - 1, right + 1, top), fill=0)
    draw.polygon(((right - fold, top), (right, top + fold), (right - fold, top + fold)), fill=255)

    stops = FAMILIES[ext]
    canvas = get_gradient(full, stops)
    canvas.putalpha(mask)

    # the turned-over flap
    flap = tuple(min(255, int(v + (255 - v) * 0.55)) for v in stops[2])
    ImageDraw.Draw(canvas).polygon(
        ((right - fold, top), (right, top + fold), (right - fold, top + fold)), fill=flap + (255,))
    return canvas, (left, top, right, bottom, fold)


def draw_glyphs(canvas, size, ext, page):
    left, top, right, bottom, fold = page
    width = right - left
    height = bottom - top
    white = (255, 255, 255, 255)
    labelled = size >= 32
    if labelled:
        band = height * 0.34
        glyph = (left + width / 2.0, top + (height - band) * 0.56)
        glyph_height = height * (0.40 if size >= 48 else 0.36)
    else:
        glyph = (left + width / 2.0, top + height * 0.58)
        glyph_height = height * 0.60

    if ext == 'm3u':
        half = width * 0.30
        box = (glyph[0] - half, glyph[1] - glyph_height * 0.45,
               glyph[0] + half, glyph[1] + glyph_height * 0.45)
        draw_list(canvas, box, white)
    else:
        draw_chevron(canvas, glyph, glyph_height, white)

    if labelled:
        draw_label(canvas, ext.upper(), (left + width / 2.0, bottom - band * 0.52),
                   width * 0.84, height * (0.20 if size >= 48 else 0.25), white)


def render(size, ext):
    canvas, page = make_page(size, ext)
    draw_glyphs(canvas, size, ext, page)
    return canvas.resize((size, size), Image.LANCZOS)


def write_icon(ext):
    images = [render(size, ext) for size in SIZES]
    path = os.path.join(OUTPUT, f'{ext}.ico')
    images[-1].save(path, format='ICO', sizes=[(v, v) for v in SIZES], append_images=images[:-1])
    return path


def main():
    os.makedirs(OUTPUT, exist_ok=True)
    for ext in FAMILIES:
        print(write_icon(ext))


if __name__ == '__main__':
    sys.exit(main())
