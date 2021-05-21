# 12/14/16, RoadrunnerWMC
# Newer DS Level Intro Graphics Compiler

import collections
import io
import itertools
import json
import os
import struct
import subprocess
import sys
import tempfile

import libimagequant as liq  # pip install libimagequant
import libimagequant_integrations.PIL  # pip install libimagequant-integrations
import ndspy.lz10
import ndspy.rom
import PIL.Image
from PyQt5 import QtCore, QtGui; Qt = QtCore.Qt

import lz77


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


def loadResources():
    checkerboardCorner = QtGui.QPixmap('static/checkerboard.png')
    checkerboardCornerImg = checkerboardCorner.toImage()

    fullCheckerboard = QtGui.QPixmap(32, 32)
    fullCheckerboard.fill(Qt.transparent)
    p = QtGui.QPainter(fullCheckerboard)
    p.drawPixmap(0, 0, checkerboardCorner)
    p.drawImage(16, 0, checkerboardCornerImg.mirrored(True, False))
    p.drawImage(0, 16, checkerboardCornerImg.mirrored(False, True))
    p.drawImage(16, 16, checkerboardCornerImg.mirrored(True, True))
    del p

    imgMask = QtGui.QPixmap('static/img-mask.png')

    # Find the center of imgMask's non-transparent area
    imgMaskX, imgMaskY, imgMaskW, imgMaskH = findAutocropSize(imgMask)
    imgMaskCenter = (imgMaskX + imgMaskW // 2, imgMaskY + imgMaskH // 2)
    imgMaskSize = (imgMaskW, imgMaskH)

    return {
        'fullCheckerboard': fullCheckerboard,
        'imgMask': imgMask,
        'imgMaskCenter': imgMaskCenter,
        'imgMaskSize': imgMaskSize,
        'imgOutline': QtGui.QPixmap('static/img-outline.png'),
        'numberfont': QtGui.QPixmap('static/numberfont.png'),
        'numberfontMask': QtGui.QPixmap('static/numberfont-mask.png'),
        'teethLighting': QtGui.QPixmap('static/teeth-lighting.png'),
        'bannerShadow': QtGui.QPixmap('static/banner-shadow.png'),
        }


def averageColor(color1, color2):
    """
    Return the color between color1 and color2.
    """
    # Doing this in HSV because it's probably more accurate to human
    # vision than RGB, question mark?
    color1, color2 = color1.toHsv(), color2.toHsv()
    h1, h2 = color1.hsvHue(), color2.hsvHue()
    s1, s2 = color1.hsvSaturation(), color2.hsvSaturation()
    v1, v2 = color1.value(), color2.value()
    a1, a2 = color1.alpha(), color2.alpha()
    h = round((h1 + h2) / 2)
    s = round((s1 + s2) / 2)
    v = round((v1 + v2) / 2)
    a = round((a1 + a2) / 2)
    return QtGui.QColor.fromHsv(h, s, v, a)


def makePixmapShadow(pix, amount):
    commands = ['-channel', 'RGB', # Only looking at the RGB channels...
                '-black-threshold', '101%', # set them all to black
                '-channel', 'RGBA', # Looking at all the channels again...
                '-morphology', 'Convolve', f'Blur:0x{amount},90', # http://im.snibgo.com/selblur.htm#blrxy
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


def makeTopScreenIntroGraphics(
        resources,
        title, name,
        background1, background2,
        banner1, banner2,
        preview,
        ):
    """
    Create both intro graphics images for the top screen.
    """

    if title is None: niceTitle = ''
    else: niceTitle = title.replace(r'\w', '').replace(r'\r', '')
    if name is None: niceName = ''
    else: niceName = name.replace(r'\w', '').replace(r'\r', '')
    nameStr = (niceTitle + ' ' + niceName).strip()
    print('Rendering graphics for "' + nameStr + '"')

    # Make the main image
    img1 = QtGui.QPixmap(256, 256)
    img1.fill(Qt.transparent)
    img1P = QtGui.QPainter(img1)
    img1P.setPen(Qt.NoPen)

    # Draw the checkerboard background
    img1P.setBrush(background1)
    img1P.drawRect(0, 0, 256, 192)

    # Make the checkerboard overlay and draw it
    cboard = QtGui.QPixmap(256, 192)
    cboard.fill(Qt.transparent)
    cboardP = QtGui.QPainter(cboard)
    cboardP.setPen(Qt.NoPen)
    cboardP.setBrush(background2)
    cboardP.drawRect(0, 0, 256, 192)
    cboardP.setCompositionMode(cboardP.CompositionMode_DestinationIn)
    cboardP.drawTiledPixmap(0, 0, 256, 192, resources['fullCheckerboard'])
    del cboardP
    img1P.drawPixmap(0, 0, cboard)

    # Draw the preview image outline
    img1P.drawPixmap(0, 0, resources['imgOutline'])

    # And the preview image itself
    if preview.width() < resources['imgMaskSize'][0]:
        print('Preview image is not wide enough!! D:')
    if preview.height() < resources['imgMaskSize'][1]:
        print('Preview image is not tall enough!! D:')
    previewPos = (
        resources['imgMaskCenter'][0] - preview.width() // 2,
        resources['imgMaskCenter'][1] - preview.height() // 2,
        )
    previewOverlay = QtGui.QPixmap(256, 192)
    previewOverlay.fill(Qt.transparent)
    previewOverlayP = QtGui.QPainter(previewOverlay)
    previewOverlayP.drawPixmap(*previewPos, preview)
    previewOverlayP.setCompositionMode(previewOverlayP.CompositionMode_DestinationIn)
    previewOverlayP.drawPixmap(0, 0, resources['imgMask'])
    del previewOverlayP
    img1P.drawPixmap(0, 0, previewOverlay)

    # Draw the checkerboard backgrounds for the icons and numberfont

    def copyVRAMTile(w, h, dx, dy, sx, sy):
        """
        REVERSE copyVRAMTile! This takes the appropriate bit of
        background pattern from dest and puts it at src. Then, when the
        game makes the call to actual copyVRAMTile, the pattern will
        match perfectly.
        The arguments match those of actual copyVRAMTile, so it'll be
        fairly easy to keep the graphics in sync with the code should
        the layout change.
        If dx or dy is None, the background color will be the average
        pattern color (in an attempt to look good no matter where the
        image is pasted).
        """
        if None in [dx, dy]:
            img1P.setPen(Qt.NoPen)
            img1P.setBrush(averageColor(background1, background2))
            img1P.drawRect(sx, sy, w, h)
        else:
            img1P.drawPixmap(sx, sy, img1.copy(dx, dy, w, h))

    copyVRAMTile(160, 20, None, None,   0, 196) # Number font
    copyVRAMTile(36,  32,   10,   96,   0, 216) # [Mario head]❌
    copyVRAMTile(36,  32,   10,   96,  40, 216) # [Luigi head]❌
    copyVRAMTile( 8,   8,   20,  129, 128, 217) # "●"
    copyVRAMTile( 8,   8,   20,  129, 136, 217) # "•"
    copyVRAMTile(10,   8,   14,  129, 134, 233) # "Ⓐ"
    copyVRAMTile(34,   9,   30,  128, 146, 216) # "Select"
    copyVRAMTile(44,   9,   24,  128, 144, 232) # "Confirm"
    copyVRAMTile( 8,  20, None, None,  80, 220) # Normal ▷
    copyVRAMTile(10,  20,    0,  100,  88, 220) # Normal ◁
    copyVRAMTile( 8,  20, None, None, 104, 220) # Pressed ▷
    copyVRAMTile(10,  20,    0,  100, 112, 220) # Pressed ◁

    # Draw the icons and numberfont themselves
    img1P.drawPixmap(0, 192, resources['numberfont'])

    # Add the numberfont mask
    # (if you change the mask, remember that every horizontal pair of
    # pixels must be the same)
    img1P.save()
    img1P.setCompositionMode(img1P.CompositionMode_DestinationIn)
    img1P.drawPixmap(0, 192, resources['numberfontMask'])
    img1P.restore()

    del img1P

    # Make the aux image
    img2 = QtGui.QPixmap(256, 256)
    img2.fill(Qt.transparent)
    img2P = QtGui.QPainter(img2)
    img2P.setPen(Qt.NoPen)

    # Make the teeth's black background
    img2P.setBrush(Qt.black)
    img2P.drawRect(0, 0, 32, 192)
    img2P.drawRect(224, 0, 32, 160)

    # Make the teeth: for the left edge, right edge and behind the banner
    # bottom edge
    # - Checkerboard first layer
    img2P.setBrush(background1)
    img2P.drawRect(16, 0, 16, 192)
    img2P.drawRect(224, 0, 16, 160)
    img2P.drawRect(0, 224, 256, 32)
    # - Checkerboard second layer
    cboard = QtGui.QPixmap(256, 256)
    cboard.fill(Qt.transparent)
    cboardP = QtGui.QPainter(cboard)
    cboardP.setPen(Qt.NoPen)
    cboardP.setBrush(background2)
    cboardP.drawRect(0, 0, 32, 192)
    cboardP.drawRect(224, 64, 32, 96)
    cboardP.drawRect(0, 224, 256, 32)
    cboardP.setCompositionMode(cboardP.CompositionMode_DestinationIn)
    cboardP.drawTiledPixmap(0, 0, 32, 192, resources['fullCheckerboard'])
    cboardP.drawTiledPixmap(224, 0, 32, 160, resources['fullCheckerboard'])
    cboardP.drawTiledPixmap(0, 224, 256, 32, resources['fullCheckerboard'])
    del cboardP
    img2P.drawPixmap(0, 0, cboard)

    # Copy the portion of the main image that goes behind the banner
    # Note that it has to be done this way because the preview image
    # border may clip into these regions
    img2P.drawPixmap(32, 0, img1.copy(0, 0, 128, 64))
    img2P.drawPixmap(32, 64, img1.copy(128, 0, 128, 64))

    # Banner shadows
    img2P.drawTiledPixmap(32, 32, 128, 32, resources['bannerShadow'])
    img2P.drawTiledPixmap(32, 96, 128, 32, resources['bannerShadow'])
    img2P.drawTiledPixmap(0, 224, 256, 32, resources['bannerShadow'])
    img2P.drawTiledPixmap(224, 32, 32, 32, resources['bannerShadow'])

    # And now remove pixels exactly matching background1 from the bottom
    # 32px of the image.
    img2Img = img2.toImage()
    img2P.setCompositionMode(img2P.CompositionMode_DestinationOut)
    for x in range(256):
        for y in range(224, 256):
            if img2Img.pixel(x, y) == background1.rgb():
                img2P.drawRect(x, y, 1, 1)
    img2P.setCompositionMode(img2P.CompositionMode_SourceOver)

    # Now to make the banner.
    
    # Banner checkerboard background
    img2P.setBrush(banner1)
    img2P.drawRect(32, 0, 128, 48 - 2)
    img2P.drawRect(32, 64, 128, 48 - 2)
    img2P.drawRect(32, 160, 224, 32)
    img2P.drawRect(0, 192, 256, 64 - 16 - 2)
    img2P.drawRect(224, 0, 16, 32 + 16 - 2)

    # Banner checkerboard foreground
    cboard = QtGui.QPixmap(256, 256)
    cboard.fill(Qt.transparent)
    cboardP = QtGui.QPainter(cboard)
    cboardP.setPen(Qt.NoPen)
    cboardP.setBrush(banner2)
    cboardP.drawRect(32, 0, 128, 64 - 2)
    cboardP.drawRect(32, 64, 128, 64 - 2)
    cboardP.drawRect(32, 160, 224, 32)
    cboardP.drawRect(0, 192, 256, 64 - 2)
    cboardP.drawRect(224, 0, 32, 64 - 2)
    cboardP.setCompositionMode(cboardP.CompositionMode_DestinationIn)
    cboardP.drawTiledPixmap(32, 0, 128, 64 - 2, resources['fullCheckerboard'], 0, 2)
    cboardP.drawTiledPixmap(32, 64, 128, 64 - 2, resources['fullCheckerboard'], 0, 2)
    cboardP.drawTiledPixmap(32, 160, 224, 32, resources['fullCheckerboard'], 0, 2)
    cboardP.drawTiledPixmap(0, 192, 256, 64 - 2, resources['fullCheckerboard'], 0, 2)
    cboardP.drawTiledPixmap(224, 0, 32, 64 - 2, resources['fullCheckerboard'], 0, 2)
    del cboardP
    img2P.drawPixmap(0, 0, cboard)

    # Hard lighting
    img2P.setCompositionMode(img2P.CompositionMode_HardLight)
    lightingL = resources['teethLighting']
    lightingR = QtGui.QPixmap.fromImage(lightingL.toImage().mirrored(True, False))
    img2P.drawTiledPixmap(0, 0, 32, 192, lightingL)
    img2P.drawTiledPixmap(224, 0, 32, 64 - 2, lightingR, 0, 2)
    img2P.drawTiledPixmap(224, 64, 32, 96, lightingR)
    img2P.setCompositionMode(img2P.CompositionMode_SourceOver)

    # Last thing: text.
    if sys.platform == 'win32':
        # Windows limits font names to 31 characters, apparently
        FONT_NAME = ('New Super Mario Font (Mario Par', 50)
    else:
        FONT_NAME = ('New Super Mario Font (Mario Party 9)', 50)
    FONT_OUTLINE = ((85, 85, 85), 18)
    def renderText(text, relativeSize, maxWidth=240):
        w, h = 4000, 384
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
                opt = st.textOption()
                opt.setWrapMode(opt.NoWrap)
                st.setTextOption(opt)
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
        p = makePixmapShadow(textBoard, 5)
        textBoardP.setOpacity(0.8)
        textBoardP.drawPixmap(0, 10, p)
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
                maxWidth,
                relativeSize * textBoard.height(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation)

        return textBoard

    # Make the level name and title text images
    if name is None:
        titleFontSize, nameFontSize = 0.14, None
        titleY, nameY = 14, None
    elif title is None:
        titleFontSize, nameFontSize = None, 0.14
        titleY, nameY = None, 14
    else:
        titleFontSize, nameFontSize = 0.10, 0.135
        titleY, nameY = 3, 20

    titleImg = nameImg = None
    if title is not None:
        titleImg = renderText(title, titleFontSize)
    if name is not None:
        nameImg = renderText(name, nameFontSize)

    # And put them where they go
    if title is not None:
        titleX = 128 - titleImg.width() // 2
        img2P.drawPixmap(titleX, 192 + titleY, titleImg)
    if name is not None:
        nameX = 128 - nameImg.width() // 2
        img2P.drawPixmap(nameX, 192 + nameY, nameImg)

    # Copy that over to the other banner, too
    img2P.drawPixmap(32, 0, img2.copy(0, 192, 128, 48))
    img2P.drawPixmap(32, 64, img2.copy(128, 192, 128, 48))

    del img2P

    return img1, img2


def makeBottomScreenIntroGraphics(
        resources,
        background1, background2,
        banner1, banner2,
        icon,
    ):
    """
    Create both intro graphics images for the bottom screen.
    """

    # Make the main image
    img1 = QtGui.QPixmap(256, 256)
    img1.fill(Qt.transparent)
    img1P = QtGui.QPainter(img1)
    img1P.setPen(Qt.NoPen)

    # Draw the checkerboard background
    img1P.setBrush(background1)
    img1P.drawRect(0, 0, 256, 192)

    # Make the checkerboard overlay and draw it
    cboard = QtGui.QPixmap(256, 192)
    cboard.fill(Qt.transparent)
    cboardP = QtGui.QPainter(cboard)
    cboardP.setPen(Qt.NoPen)
    cboardP.setBrush(background2)
    cboardP.drawRect(0, 0, 256, 192)
    cboardP.setCompositionMode(cboardP.CompositionMode_DestinationIn)
    cboardP.drawTiledPixmap(0, 0, 256, 192, resources['fullCheckerboard'])
    del cboardP
    img1P.drawPixmap(0, 0, cboard)

    # Draw the icon
    iconX = 128 - icon.width() // 2
    iconY = 96 - icon.height() // 2
    img1P.drawPixmap(iconX, iconY, icon)

    del img1P

    # Make the aux image
    img2 = QtGui.QPixmap(256, 256)
    img2.fill(Qt.transparent)
    img2P = QtGui.QPainter(img2)
    img2P.setPen(Qt.NoPen)

    # Make the teeth's black background
    img2P.setBrush(Qt.black)
    img2P.drawRect(0, 0, 32, 192)
    img2P.drawRect(224, 0, 32, 192)

    # Make the teeth: for the left edge, right edge and behind the banner
    # bottom edge
    # - Checkerboard first layer
    img2P.setBrush(background1)
    img2P.drawRect(16, 0, 16, 192)
    img2P.drawRect(224, 0, 16, 192)
    # - Checkerboard second layer
    cboard = QtGui.QPixmap(256, 256)
    cboard.fill(Qt.transparent)
    cboardP = QtGui.QPainter(cboard)
    cboardP.setPen(Qt.NoPen)
    cboardP.setBrush(background2)
    cboardP.drawRect(0, 0, 32, 192)
    cboardP.drawRect(224, 0, 32, 192)
    cboardP.setCompositionMode(cboardP.CompositionMode_DestinationIn)
    cboardP.drawTiledPixmap(0, 0, 32, 192, resources['fullCheckerboard'])
    cboardP.drawTiledPixmap(224, 0, 32, 192, resources['fullCheckerboard'])
    del cboardP
    img2P.drawPixmap(0, 0, cboard)

    # Hard lighting
    img2P.setCompositionMode(img2P.CompositionMode_HardLight)
    lightingL = resources['teethLighting']
    lightingR = QtGui.QPixmap.fromImage(lightingL.toImage().mirrored(True, False))
    img2P.drawTiledPixmap(0, 0, 32, 192, lightingL)
    img2P.drawTiledPixmap(224, 0, 32, 192, lightingR)
    img2P.setCompositionMode(img2P.CompositionMode_SourceOver)

    del img2P

    return img1, img2


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


def saveImagePair(img1, img2, fn1, fn2, rom, firstFileID):
    """
    Palette-reduce the two images to 256-colors (both with the same
    palette), save them as PNGs, and save them as ENPGs
    Currently assumes both images are 256x256.
    """

    # Temp
    img1.save('out-png/' + fn1 + '.png')
    img2.save('out-png/' + fn2 + '.png')

    # Convert both to PIL Images
    pimg1, pimg2 = map(qImageToPilImage, [img1, img2])

    # Combine
    comb = PIL.Image.new('RGBA', (512, 256), (0, 0, 0, 0))
    comb.paste(pimg1, (0, 0))
    comb.paste(pimg2, (256, 0))

    # Quantize
    # combQ = comb.quantize(255, 3) # leave one color for transparent
    attr = liq.Attr()
    attr.max_colors = 255 # leave one color for transparent
    comb_liq = libimagequant_integrations.PIL.to_liq(comb, attr)
    combQ = libimagequant_integrations.PIL.from_liq(comb_liq.quantize(attr), comb_liq)

    # Create the ENPG data arrays
    ENPG_LEN = 256 * 256 + 256 * 2
    enpg1, enpg2 = bytearray(ENPG_LEN), bytearray(ENPG_LEN)

    # Convert the palette to RGB555 and put it in both the enpgs
    pal888 = combQ.getpalette()[:255*3]
    struct.pack_into('<H', enpg1, 256**2, 0x8000)
    struct.pack_into('<H', enpg2, 256**2, 0x8000)
    shrink = lambda c: min((c + 4) >> 3, 0x1F) & 0x1F
    for i, (r, g, b) in enumerate(grouper(pal888, 3)):
        rgb = shrink(b) << 10 | shrink(g) << 5 | shrink(r)
        struct.pack_into('<H', enpg1, 256**2 + 2 * i + 2, rgb)
        struct.pack_into('<H', enpg2, 256**2 + 2 * i + 2, rgb)

    # Put the color indices in the enpgs
    for y in range(256):
        for x in range(256):
            alpha = comb.getpixel((x, y))[3]
            if alpha < 255:
                col = 0
            else:
                col = combQ.getpixel((x, y)) + 1
            enpg1[y * 256 + x] = col
    for y in range(256):
        for x in range(256):
            alpha = comb.getpixel((x + 256, y))[3]
            if alpha < 255:
                col = 0
            else:
                col = combQ.getpixel((x + 256, y)) + 1
            enpg2[y * 256 + x] = col

    # Compress them
    enpg1Compressed = ndspy.lz10.compress(enpg1)
    enpg2Compressed = ndspy.lz10.compress(enpg2)

    # Save them
    with open('out-enpg/' + fn1 + '.enpg', 'wb') as f:
        f.write(enpg1)
    with open('out-enpg/' + fn2 + '.enpg', 'wb') as f:
        f.write(enpg2)
    with open('out-enpg-lz/' + fn1 + '.enpg', 'wb') as f:
        f.write(enpg1Compressed)
    with open('out-enpg-lz/' + fn2 + '.enpg', 'wb') as f:
        f.write(enpg2Compressed)

    # Insert them into the rom
    rom.files[firstFileID] = enpg1Compressed
    rom.files[firstFileID + 1] = enpg2Compressed
    rom.filenames['zc_crsin'].files[firstFileID - rom.filenames['zc_crsin'].firstID] = f'{fn1}.enpg'
    rom.filenames['zc_crsin'].files[firstFileID - rom.filenames['zc_crsin'].firstID + 1] = f'{fn2}.enpg'

    # Render them as PNGs and save them elsewhere (for quality inspection)
    enpgPng1, enpgPng2 = map(enpgToImage, [enpg1, enpg2])
    enpgPng1.save('out-enpg-png/' + fn1 + '.png')
    enpgPng2.save('out-enpg-png/' + fn2 + '.png')


def makeImages():

    resources = loadResources()

    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f, object_pairs_hook=collections.OrderedDict)

    with open('Newer Super Mario Bros. DS Orig.nds', 'rb') as f:
        rom = ndspy.rom.NintendoDSRom(f.read())

    for i in range(2128, 2488):
        rom.filenames['zc_crsin'].files[i - rom.filenames['zc_crsin'].firstID] = f'{i} Dummy'
        rom.files[i] = b'DUMMY'

    fileIdMap = {}

    def fileIdGen():
        fid = 2128
        while True:
            yield fid
            fid += 2
    fileId = fileIdGen()

    # Make the top-screen images
    bottomImagesToMake = []
    topPairs = []
    for levelName, levelConfig in config['levels'].items():
        theme = config['themes'][levelConfig['theme']]
        main, aux = makeTopScreenIntroGraphics(
            resources = resources,
            title = levelConfig.get('title'),
            name = levelConfig.get('name'),
            background1 = hex2QColor(theme['background1']),
            background2 = hex2QColor(theme['background2']),
            banner1 = hex2QColor(theme['banner1']),
            banner2 = hex2QColor(theme['banner2']),
            preview = QtGui.QPixmap('previews/' + levelConfig['preview']),
            )

        topId = next(fileId)

        mainFn = '%d_%s_main' % (topId, levelName)
        auxFn = '%d_%s_aux' % (topId + 1, levelName)
        saveImagePair(main, aux, mainFn, auxFn, rom, topId)
        topPairs.append([mainFn, auxFn])

        bottomImageId = (levelConfig['theme'], levelConfig['bottom'])
        if bottomImageId not in bottomImagesToMake:
            bottomImagesToMake.append(bottomImageId)

        fileIdMap[(levelConfig['world'] - 1) * 24 + levelConfig['number']] = \
            (topId, bottomImagesToMake.index(bottomImageId))

    # Make the bottom-screen images
    bottomFileIds = []
    bottomPairs = []
    for i, (themeName, btm) in enumerate(bottomImagesToMake):
        print(f'Rendering bottom-screen graphics for {btm.split(".")[0]}'
            f' with the "{themeName}" theme ({i+1}/{len(bottomImagesToMake)})...')
        theme = config['themes'][themeName]
        main, aux = makeBottomScreenIntroGraphics(
            resources = resources,
            background1 = hex2QColor(theme['background1']),
            background2 = hex2QColor(theme['background2']),
            banner1 = hex2QColor(theme['banner1']),
            banner2 = hex2QColor(theme['banner2']),
            icon = QtGui.QPixmap('bottoms/' + btm),
            )

        btmId = next(fileId)
        bottomFileIds.append(btmId)

        mainFn = '_'.join([str(btmId),
                           'btm',
                           btm.split('.')[0],
                           themeName,
                           'main'])
        auxFn = '_'.join([str(btmId + 1),
                          'btm',
                          btm.split('.')[0],
                          themeName,
                          'aux'])
        saveImagePair(main, aux, mainFn, auxFn, rom, btmId)
        bottomPairs.append([mainFn, auxFn])

    print('Saving everything...')

    fileIdData = [0] * 2 * (max(fileIdMap) + 1)

    for idx, (topId, btmIdx) in fileIdMap.items():
        fileIdData[idx * 2] = topId
        fileIdData[idx * 2 + 1] = bottomFileIds[btmIdx]

    fileIdBytes = struct.pack('<%dH' % len(fileIdData), *fileIdData)
    fileIdBytesComp = ndspy.lz10.compress(fileIdBytes)
    with open('fileIDs.nerds', 'wb') as f:
        f.write(fileIdBytes)
    with open('fileIDs.nerds.lz', 'wb') as f:
        f.write(fileIdBytesComp)
    rom.files[2127] = fileIdBytesComp
    rom.filenames['zc_crsin'].files[0] = f'2127 fileIDs.nerds'

    with open('conversionInfo.json', 'w', encoding='utf-8') as f:
        json.dump({'top': topPairs, 'bottom': bottomPairs}, f)

    with open('Newer Super Mario Bros. DS.nds', 'wb') as f:
        f.write(rom.save())

    print('Done! :D')


def main():
    app = QtGui.QGuiApplication([])

    makeImages()

main()