# 5/12/17
# ughh

import io
import math

import imageio
import PIL.ImageQt
from PyQt5 import QtCore, QtGui, QtWidgets

# Each frame is 102 px wide: we can fit two and a half horizontally
# Each frame is 23px tall: we can fit 11 vertically
# So that's 11 + 11 + 5 = 27 frames total.
# 15 for intro/outtro, 12 for the loop.
# And that's OK if we make the top layer overlap by exactly 44 px. Which
# means that we can make those shadows extend into the next stripe a bit, actually.

# [22:51:52] * RoadrunnerWMC measures the speed at which the text pulses in NSMBU
# [22:52:27] <RoadrunnerWMC> 20 pulses in 12.6 seconds
# [22:52:40] <RoadrunnerWMC> or, probably 19 pulses, since I started counting at 1
# [22:52:57] <RoadrunnerWMC> So, 1.4 pulses per second
# [22:58:14] <RoadrunnerWMC> .5 images/frame * 60 frames/sec * (1 / 1.4) sec/pulse * 0.5 pulses/animation ≈ 11 images/animation
# [22:59:04] * RoadrunnerWMC goes up to 12 images/animation


INTRO_FRAMES = 6
LOOP_FRAMES = 12

XLPct = 116 / 173
HighPct = 96 / 173
LowPct = HighPct * 0.95

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

def qImageToImageio(qimage):
    """
    Convert a QImage to an imageio image.
    """
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.ReadWrite)
    qimage.save(buffer, 'PNG')

    return imageio.imread(bytes(buffer.data()))

def iterFrameParameters():
    EndPct = (LowPct + HighPct) / 2
    for i in range(INTRO_FRAMES):
        w = EndPct + (XLPct - EndPct) * ((INTRO_FRAMES - i) / INTRO_FRAMES)
        a = (i + 1) / (INTRO_FRAMES + 1)
        yield w, a

    for i in range(LOOP_FRAMES):
        w = LowPct + (HighPct - LowPct) * math.sin((i / LOOP_FRAMES + 0.5) * math.pi)
        yield w, 1

def emptyFrame():
    return QtGui.QImage('Anim-BG.png')

def iterFrames():
    bgImg = emptyFrame()
    textImg = QtGui.QImage('Press-A.png')
    for w, a in iterFrameParameters():
        img = QtGui.QImage(bgImg)
        p = QtGui.QPainter(img)
        p.setOpacity(a)
        p.setRenderHint(p.SmoothPixmapTransform)
        p.translate(bgImg.width() / 2, bgImg.height() / 2)
        p.scale(w, w)
        p.drawImage(-textImg.width() / 2, -textImg.height() / 2, textImg)
        del p
        yield img

def iterFramePositions():
    for y in range(0, 216, 24):
        yield (0, y)
    for y in range(0, 216, 24):
        yield (128, y)

def makeImage():
    img = QtGui.QImage(256, 256, QtGui.QImage.Format_ARGB32)
    p = QtGui.QPainter(img)
    for pos, frame in zip(iterFramePositions(), iterFrames()):
        p.drawImage(*pos, frame)
    del p
    return img

def makeGifFrames():
    def double(img):
        return img.scaledToWidth(img.width() * 2)
    empty = [emptyFrame()]
    allFrames = list(map(qImageToPilImage, map(double, empty + list(iterFrames()))))
    return allFrames[:1], allFrames[:1+INTRO_FRAMES], allFrames[1+INTRO_FRAMES:]

def imagesToGif(frames):
    # http://stackoverflow.com/a/35943809/4718769
    images = list(map(qImageToImageio, frames))
    imageio.mimsave('/tmp/movie.gif', images, duration=1/30)
    with open('/tmp/movie.gif', 'rb') as f:
        return f.read()

def main():
    print('Making image')
    anim = makeImage()
    anim.save('anim.png')

    print('Adding bottoms and saving')
    bottoms = QtGui.QImage('bottoms.png')
    for i in range(8):
        anin = QtGui.QImage(anim)
        p = QtGui.QPainter(anin)
        p.drawImage(0, 216, bottoms.copy(0, i * 40, 256, 40))
        del p
        anin.save(f'ts-{i+1}.png')

    print('Making animated GIF of Press (A)! animation')
    emptyFrame, introFrames, loopFrames = makeGifFrames()
    r = lambda a: list(reversed(a))
    fullLoop = loopFrames[6:] + r(loopFrames) + loopFrames[:6]
    gifFrames = introFrames + fullLoop * 5 + r(introFrames) + emptyFrame * 60
    with open('anim.gif', 'wb') as f:
        f.write(imagesToGif(gifFrames))

    print('Done.')

main()
