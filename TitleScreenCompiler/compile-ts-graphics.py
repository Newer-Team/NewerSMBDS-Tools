# 12/14/16, RoadrunnerWMC

import collections
import io
import itertools
import json
import os, os.path
import struct
import subprocess
import sys
import tempfile

import libimagequant as liq  # pip install libimagequant
import libimagequant_integrations.PIL  # pip install libimagequant-integrations
import PIL.Image
from PyQt5 import QtCore, QtGui; Qt = QtCore.Qt

import ndspy.lz10
import ndspy.rom

VERSION = 'Ver. 1.15'



def grouper(iterable, n, fillvalue=None):
    """
    Collect data into fixed-length chunks or blocks
    https://docs.python.org/3/library/itertools.html#itertools-recipes
    """
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def findAutocropSize(img):
    """
    Return the x, y, w, h of the image if it were autocropped
    """
    if not isinstance(img, QtGui.QImage):
        img = img.toImage()
    minX, minY, maxX, maxY = 0, 0, img.width() - 1, img.height() - 1
    alphaAt = lambda x, y: img.pixel(x, y) >> 24
    rowClear = lambda y: all(alphaAt(x, y) == 0 for x in range(img.width()))
    colClear = lambda x: all(alphaAt(x, y) == 0 for y in range(img.height()))
    while colClear(minX): minX += 1
    while rowClear(minY): minY += 1
    while colClear(maxX): maxX -= 1
    while rowClear(maxY): maxY -= 1
    return minX, minY, maxX - minX, maxY - minY


def antiantialias(image):
    """
    Return a copy of the image that has antialiasing removed.
    """
    image = QtGui.QPixmap.toImage(image)
    new = QtGui.QPixmap(image.size())
    new.fill(Qt.transparent)

    p = QtGui.QPainter(new)
    p.setPen(Qt.NoPen)

    for y in range(image.height()):
        for x in range(image.width()):
            argb = image.pixel(x, y)
            a = argb >> 24
            if a < 127: continue
            p.setBrush(QtGui.QColor.fromRgb((argb >> 16) & 255, (argb >> 8) & 255, argb & 255))
            p.drawRect(x, y, 1, 1)
    del p

    return new


def hex2QColor(hexColor):
    return QtGui.QColor.fromRgb(int(hexColor, 16))


def qImageToPilImage(qimage):
    """
    Convert a QImage to a PIL Image.
    http://stackoverflow.com/a/1756587/4718769
    """
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.ReadWrite)
    qimage.save(buffer, 'PNG')

    bio = io.BytesIO()
    bio.write(buffer.data())
    buffer.close()
    bio.seek(0)
    return PIL.Image.open(bio)


def enpgToImage(enpg):
    """
    Render an ENPG.
    """
    img = PIL.Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    colors = []
    for i in range(256):
        rgb555, = struct.unpack_from('<H', enpg, 256 * 256 + 2 * i)
        b, g, r = (rgb555 >> 10) & 0x1F, (rgb555 >> 5) & 0x1F, rgb555 & 0x1F
        r, g, b = int(r * 0xFF / 0x1F), int(g * 0xFF / 0x1F), int(b * 0xFF / 0x1F)
        r, g, b = min(r, 255), min(g, 255), min(b, 255)
        a = 0 if rgb555 >> 15 else 255
        colors.append((r, g, b, a))
    assert len(colors) == 256
    for y in range(256):
        for x in range(256):
            img.putpixel((x, y), colors[enpg[y * 256 + x]])
    return img


def convertAllToEnpg(imgs):
    """
    Palette-reduce the two images to 256-colors (both with the same
    palette), save them as PNGs, and save them as ENPGs
    Currently assumes both images are 256x256.
    """
    n = len(imgs)

    # Combine into one PIL image
    comb = PIL.Image.new('RGBA', (256 * n, 256), (0, 0, 0, 0))
    for i, img in enumerate(imgs):
        comb.paste(qImageToPilImage(img), (256 * i, 0))

    # Quantize
    # combQ = comb.quantize(255, 3) # leave one color for transparent
    attr = liq.Attr()
    attr.max_colors = 255 # leave one color for transparent
    comb_liq = libimagequant_integrations.PIL.to_liq(comb, attr)
    combQ = libimagequant_integrations.PIL.from_liq(comb_liq.quantize(attr), comb_liq)

    # Create the ENPG data arrays
    ENPG_LEN = 256 * 256 + 256 * 2
    enpgs = [bytearray(ENPG_LEN) for i in range(n)]

    # Convert the palette to RGB555 and put it in both the enpgs
    pal888 = combQ.getpalette()[:255*3]
    for enpg in enpgs:
        struct.pack_into('<H', enpg, 256**2, 0x8000)
    shrink = lambda c: min((c + 4) >> 3, 0x1F) & 0x1F
    for i, (r, g, b) in enumerate(grouper(pal888, 3)):
        rgb = shrink(b) << 10 | shrink(g) << 5 | shrink(r)
        for enpg in enpgs:
            struct.pack_into('<H', enpg, 256**2 + 2 * i + 2, rgb)

    # Put the color indices in the enpgs
    for i, enpg in enumerate(enpgs):
        for y in range(256):
            for x in range(256):
                alpha = comb.getpixel((256 * i + x, y))[3]
                if alpha < 255:
                    col = 0
                else:
                    col = combQ.getpixel((256 * i + x, y)) + 1
                enpg[y * 256 + x] = col

    return enpgs


FONT_NAME = ('New Super Mario Font (Mario Party 9)', 50)
FONT_OUTLINE = ((0, 0, 0), 18)
def renderText(text, relativeSize, maxWidth=240):
    w, h = 2500, 384
    textBoard = QtGui.QPixmap(w, h)
    textBoard.fill(Qt.transparent)
    textBoardP = QtGui.QPainter(textBoard)

    # Split by special characters
    textList = [[False, '']] # (isIcon, text), ...
    for c in text:
        if c == '[':
            textList.append([True, ''])
        elif c == ']':
            textList.append([False, ''])
        else:
            textList[-1][1] += c

    # Convert shorthand r'\w's and r'\r's to HTML markup Qt understands
    es = '</span>'
    cw, cr = '<span style="color:white;">', '<span style="color:#ff2828;">'
    for i, (isIcon, text) in enumerate(textList):
        if not isIcon:
            textList[i][1] = (cw + text.replace(r'\w', es + cw
                                               ).replace(r'\r', es + cr)
                              + es)

    # Draw the text (and *only* the text), but keep track of where the
    # icons would go and leave room for them
    f = QtGui.QFont(*FONT_NAME)
    f.setStyleStrategy(f.NoAntialias)
    textBoardP.setFont(f)
    textBoardP.setPen(Qt.white)

    x = 32
    PAD = 12
    iconPlacement = []
    for isIcon, text in textList:
        if isIcon:
            icon = QtGui.QPixmap('characters/' + text + '.png')
            iconPlacement.append((icon, x))
            x += icon.width() + PAD
        else:
            st = QtGui.QStaticText(text)
            st.setTextWidth(w)
            textBoardP.drawStaticText(x, 32, st)
            x += st.size().width() + PAD

    # And now outline the text
    # https://en.wikipedia.org/wiki/Dilation_(morphology)
    textBoardP.setCompositionMode(textBoardP.CompositionMode_DestinationOver)
    textBoardP.setPen(Qt.NoPen)
    textBoardP.setBrush(QtGui.QColor.fromRgb(*FONT_OUTLINE[0]))
    textBoardImg = textBoard.toImage()
    outline = FONT_OUTLINE[1]
    for y in range(h):
        for x in range(w):
            if textBoardImg.pixel(x, y) >> 24 > 0:
                textBoardP.drawEllipse(x - outline, y - outline,
                                       2 * outline, 2 * outline)

    # And draw all the icons in
    for icon, x in iconPlacement:
        textBoardP.drawPixmap(x, 68, icon)

    # Add shadow
    textBoardP.setCompositionMode(textBoardP.CompositionMode_DestinationOver)
    p = makePixmapShadow(textBoard, 8)
    textBoardP.setOpacity(0.8)
    textBoardP.drawPixmap(0, 3, p)
    textBoardP.setOpacity(1.0)

    del textBoardP

    # Now autocrop it
    textBoard = textBoard.copy(*findAutocropSize(textBoard))

    # Now shrink it to the size requested
    if relativeSize * textBoard.width() < maxWidth:
        textBoard = textBoard.scaledToWidth(
            relativeSize * textBoard.width(),
            Qt.SmoothTransformation)
    else:
        textBoard = textBoard.scaled(
            relativeSize * textBoard.width(),
            relativeSize * textBoard.height(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation)

    return textBoard


def makePixmapShadow(pix, amount):
    # http://im.snibgo.com/selblur.htm#blrxy
    blurCommand = f'Blur:0x{amount},90'

    commands = ['-channel', 'RGB', # Only looking at the RGB channels...
                '-black-threshold', '101%', # set them all to black
                '-channel', 'RGBA', # Looking at all the channels again...
                #'-morphology', 'Convolve', blurCommand,
                '-blur', f'{amount*3}x{amount}',
                ]
    return QtGui.QPixmap.fromImage(runImageMagick(pix.toImage(), *commands))


def runImageMagick(*command):
    """
    Run ImageMagick with the command given. Commands are a list of
    arguments, not unlike sys.argv. Where filenames are expected, just
    put a QImage instance. Don't add anything where the output filename
    would normally go. The resulting QImage will be returned.
    """

    OUTPUT_FN = 'output.png'

    command = list(command)

    imgs = {}
    for i, part in enumerate(command):
        if isinstance(part, QtGui.QImage):
            fn = f'img{i}.png'
            imgs[fn] = part

    def fnFor(img):
        return [fn for fn, img2 in imgs.items() if img2 is img][0]

    with tempfile.TemporaryDirectory() as tmpdirname:
        def addDir(fn): return os.path.join(tmpdirname, fn)

        imgs = {addDir(fn): img for fn, img in imgs.items()}

        for fn, img in imgs.items():
            img.save(fn)

        command2 = ['convert']
        for part in command:
            if isinstance(part, QtGui.QImage):
                command2.append(fnFor(part))
            else:
                command2.append(part)
        command2.append(addDir(OUTPUT_FN))

        if sys.platform == 'win32':
            subprocess.run(command2, shell=True)
        else:
            subprocess.run(command2)

        return QtGui.QImage(addDir(OUTPUT_FN))


def addVersionNumber(base):
    namePix = renderText(VERSION, 1)
    namePix = namePix.scaledToHeight(17, Qt.SmoothTransformation)
    p = QtGui.QPainter(base)
    p.drawPixmap(192, 175, namePix)
    del p
    return base


def makeImages():
    imgFNs = [
        ('ts-0', '3089 BASE.enpg'),
        ('ts-1', '3090 WORLD1.enpg'),
        ('ts-2', '3091 WORLD2.enpg'),
        ('ts-3', '3092 WORLD3.enpg'),
        ('ts-4', '3093 WORLD4.enpg'),
        ('ts-5', '3094 WORLD5.enpg'),
        ('ts-6', '3095 WORLD6.enpg'),
        ('ts-7', '3096 WORLD7.enpg'),
        ('ts-8', '3097 WORLD8.enpg'),
        ]
    FIRST_FILE_ID = 3089

    imgs = []
    for fn, _ in imgFNs:
        imgs.append(QtGui.QImage(f'{fn}.png'))

    imgs[0] = addVersionNumber(imgs[0])

    converted = convertAllToEnpg(imgs)

    with open('Newer Super Mario Bros. DS.nds', 'rb') as f:
        rom = ndspy.rom.NintendoDSRom(f.read())

    for i, ((fn, gamefn), enpg) in enumerate(zip(imgFNs, converted)):
        compressed = ndspy.lz10.compress(enpg)
        with open(f'out-enpg/{gamefn}', 'wb') as f:
            f.write(enpg)
        with open(f'out-enpg-lz/{gamefn}', 'wb') as f:
            f.write(compressed)
        rom.files[FIRST_FILE_ID + i] = compressed
        enpgToImage(enpg).save(f'out-enpg-png/{gamefn}.png')

    with open('Newer Super Mario Bros. DS.nds', 'wb') as f:
        f.write(rom.save())

def main():
    app = QtGui.QGuiApplication([])

    makeImages()

main()
