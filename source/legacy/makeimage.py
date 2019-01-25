# encoding: utf-8


'''
author: Taehong Kim
email: peppy0510@hotmail.com
'''


import os
import wx.tools.img2py as img2py

from PIL import Image


PATH = r'packages/images/a/icon-list-tab-close.png'


def makeimage(path, write=False):
    path = os.path.abspath(path)
    im = Image.open(path)
    if 'icc_profile' in im.info:
        im.info.pop('icc_profile')
    im.save(path, 'PNG')
    image_file = path
    python_file = '.'.join((os.path.splitext(path)[0], 'py'))
    imgName = os.path.splitext(os.path.split(path)[-1])[0]
    # compatible = img2py.DEFAULT_COMPATIBLE
    img2py.img2py(image_file, python_file, append=False, imgName=imgName)
    f = open(python_file, 'rb')
    print(f.read())
    f.close()
    if write is False:
        os.remove(python_file)


if __name__ == '__main__':
    makeimage(PATH)
