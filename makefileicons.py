# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import math
import numpy
import os
import sys

from PIL import Image
from PIL import ImageChops
from PIL import ImageDraw
from PIL import ImageFont


OUTPUT = os.path.join('assets', 'icon', 'filetypes')
# each style's folder in OUTPUT
STYLES = {'color': '', 'light': 'light'}
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

# the light style's sheet top to bottom, its outline and its turned-over corner
PAPER = ((255, 255, 255), (238, 240, 243))
OUTLINE = (140, 146, 154)
FLAP = (220, 224, 230)


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


def get_paper(size):
    share = numpy.linspace(0.0, 1.0, size)[:, None, None]
    top, bottom = (numpy.array(v, dtype=float) for v in PAPER)
    rgb = numpy.broadcast_to(top + (bottom - top) * share, (size, size, 3)).astype(numpy.uint8)
    return Image.fromarray(rgb, 'RGB').convert('RGBA')


def get_layout(size):
    # (page left, top, right, bottom, fold) on a 1.0 canvas; small pages fill it
    if size <= 20:
        return 0.09, 0.0, 0.91, 1.0, 0.30
    if size <= 32:
        return 0.10, 0.0, 0.90, 1.0, 0.27
    return 0.12, 0.02, 0.88, 0.98, 0.25


def get_font(pixels):
    font = ImageFont.truetype(FONT, pixels)
    font.set_variation_by_name(FONT_VARIATION)
    return font


def get_label_font(label, width, height):
    left, top, right, bottom = get_font(100).getbbox('H')
    font = get_font(int(100.0 * height / (bottom - top)))
    if font.getlength(label) > width:
        font = get_font(int(font.size * width / font.getlength(label)))
    return font


def draw_chevron(canvas, centre, height, ink):
    x, y = centre
    points = [(x + (px - 0.5) * height, y + (py - 0.5) * height) for px, py in CHEVRON]
    ImageDraw.Draw(canvas).polygon(points, fill=ink)


def draw_list(canvas, box, ink):
    # three rows after a small chevron, which stands above the first: a playlist
    left, top, right, bottom = box
    row = (bottom - top) / 5.8
    top += row * 0.8
    draw = ImageDraw.Draw(canvas)
    for index in range(3):
        y = top + row * index * 2
        draw.rectangle((left + (row * 3.0 if index == 0 else 0), y, right, y + row), fill=ink)
    draw_chevron(canvas, (left + row * 1.1, top + row * 0.5), row * 2.6, ink)


def get_page_mask(full, box, fold, radius):
    left, top, right, bottom = box
    mask = Image.new('L', (full, full), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((left, top, right - 1, bottom - 1), radius, fill=255)
    # the folded corner is cut away
    draw.polygon(((right - fold, top - 1), (right + 1, top - 1), (right + 1, top + fold)), fill=0)
    draw.rectangle((right - fold, top - 1, right + 1, top), fill=0)
    draw.polygon(((right - fold, top), (right, top + fold), (right - fold, top + fold)), fill=255)
    return mask


def make_page(size, ext):
    full = size * SCALE
    left, top, right, bottom, fold = get_layout(size)
    left, top, right, bottom = (int(v * full) for v in (left, top, right, bottom))
    fold = int(fold * (right - left))
    radius = max(int(full * 0.045), SCALE)

    stops = FAMILIES[ext]
    canvas = get_gradient(full, stops)
    canvas.putalpha(get_page_mask(full, (left, top, right, bottom), fold, radius))

    # the turned-over flap
    flap = tuple(min(255, int(v + (255 - v) * 0.55)) for v in stops[2])
    ImageDraw.Draw(canvas).polygon(
        ((right - fold, top), (right, top + fold), (right - fold, top + fold)), fill=flap + (255,))
    return canvas, (left, top, right, bottom, fold)


def make_light_page(size, ext):
    full = size * SCALE
    left, top, right, bottom, fold = get_layout(size)
    # on the icon's whole pixels, or the outline blurs
    left, top, right, bottom = (round(v * size) * SCALE for v in (left, top, right, bottom))
    fold = round(fold * (right - left) / SCALE) * SCALE
    line = max(1, size // 128) * SCALE
    radius = max(int(full * 0.045), SCALE)

    outer = get_page_mask(full, (left, top, right, bottom), fold, radius)
    canvas = Image.new('RGBA', (full, full), OUTLINE + (0,))
    canvas.paste(OUTLINE + (255,), (0, 0, full, full), outer)
    # the diagonal moves in by the line as the sides do
    inner = get_page_mask(
        full, (left + line, top + line, right - line, bottom - line),
        fold - round(line * (2 - math.sqrt(2))), max(radius - line, 1))
    canvas.paste(get_paper(full), (0, 0), inner)

    x, y = right - fold, top + fold
    flap = Image.new('L', (full, full), 0)
    ImageDraw.Draw(flap).polygon(((x, top), (right, y), (x, y)), fill=255)
    canvas.paste(FLAP + (255,), (0, 0, full, full), ImageChops.multiply(flap, inner))
    edges = Image.new('L', (full, full), 0)
    draw = ImageDraw.Draw(edges)
    draw.rectangle((x, top, x + line - 1, y), fill=255)
    draw.rectangle((x, y - line + 1, right, y), fill=255)
    canvas.paste(OUTLINE + (255,), (0, 0, full, full), ImageChops.multiply(edges, outer))
    return canvas, (left, top, right, bottom, fold)


def draw_glyphs(canvas, size, ext, page):
    left, top, right, bottom, fold = page
    width = right - left
    height = bottom - top
    centre = left + width / 2.0
    middle = top + height / 2.0
    white = 255
    label = ext.upper()

    # the ink is centred on the page: the fold is clear of it at every size
    if size >= 32:
        glyph_height = height * (0.40 if size >= 48 else 0.36)
        font = get_label_font(label, width * 0.84, height * (0.20 if size >= 48 else 0.25))
        label_height = -font.getbbox(label, anchor='ms')[1]
        total = glyph_height + height * 0.10 + label_height
        glyph_y = middle - total / 2.0 + glyph_height / 2.0
        ImageDraw.Draw(canvas).text(
            (centre, middle + total / 2.0), label, font=font, fill=white, anchor='ms')
    else:
        glyph_height = height * 0.60
        glyph_y = middle

    if ext == 'm3u':
        half = width * 0.30
        box = (centre - half, glyph_y - glyph_height / 2.0,
               centre + half, glyph_y + glyph_height / 2.0)
        draw_list(canvas, box, white)
    else:
        draw_chevron(canvas, (centre, glyph_y), glyph_height, white)


def render(size, ext, style):
    if style == 'light':
        canvas, page = make_light_page(size, ext)
        low, mid, high = FAMILIES[ext]
        ink = get_gradient(canvas.width, (low, low, mid))
    else:
        canvas, page = make_page(size, ext)
        ink = Image.new('RGBA', canvas.size, (255, 255, 255, 255))
    mask = Image.new('L', canvas.size, 0)
    draw_glyphs(mask, size, ext, page)
    canvas.paste(ink, (0, 0), mask)
    return canvas.resize((size, size), Image.LANCZOS)


def write_icon(ext, style):
    images = [render(size, ext, style) for size in SIZES]
    path = os.path.join(OUTPUT, STYLES[style], f'{ext}.ico')
    images[-1].save(path, format='ICO', sizes=[(v, v) for v in SIZES], append_images=images[:-1])
    return path


def main():
    for style, folder in STYLES.items():
        os.makedirs(os.path.join(OUTPUT, folder), exist_ok=True)
        for ext in FAMILIES:
            print(write_icon(ext, style))


if __name__ == '__main__':
    sys.exit(main())
