import struct
import sys

def loopSWAV(data):
    data = bytearray(data)
    data[0x19] = 1 # set "looped" flag
    data[0x1E] = data[0x1F] = 0 # set loop start to 0
    struct.pack_into('<H', data, 0x20, # set loop end to the total length of the audio
        (struct.unpack_from('<I', data, 0x14)[0] - 0x14) // 4)
    return data

for fn in sys.argv[1:]:
    with open(fn, 'rb') as f:
        d = f.read()
    d2 = loopSWAV(d)
    with open(fn[:-5] + '-looped.swav', 'wb') as f:
        f.write(d2)