# This file <s>is</s> was part of NSMB Editor 5, before it was ported
# to Python by RoadrunnerWMC on 12/20/16.

# NSMB Editor 5 is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# NSMB Editor 5 is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with NSMB Editor 5.  If not, see <http://www.gnu.org/licenses/>.


import struct


def LZ77_Compress_Search(data, pos):
    maxMatchDiff = 4096
    maxMatchLen = 18
    match = length = 0

    start = pos - maxMatchDiff
    start = max(start, 0)

    for thisMatch in range(start, pos):
        thisLength = 0
        while (thisLength < maxMatchLen
               and thisMatch + thisLength < pos
               and pos + thisLength < len(data)
               and data[pos + thisLength] == data[thisMatch + thisLength]):
            thisLength += 1

        if thisLength > length:
            match = thisMatch
            length = thisLength

        # We can't improve the max match length again...
        if length == maxMatchLen:
            return match, length

    return match, length

def LZ77_Compress(data, header=False):
    res = bytearray()
    if header:
        res.extend(b'LZ77')

    res.extend(struct.pack('<I', len(data) << 8 | 0x10))

    tempBuffer = bytearray(16)

    # Current byte to compress.
    current = 0

    while current < len(data):
        tempBufferCursor = 0
        blockFlags = 0
        for i in range(8):
            # Not sure if this is needed. The DS probably ignores this data.
            if current >= len(data):
                tempBuffer[tempBufferCursor] = 0
                tempBufferCursor += 1
                continue

            searchPos, searchLen = LZ77_Compress_Search(data, current)
            searchDisp = current - searchPos - 1
            if searchLen > 2: # We found a big match, let's write a compressed block.
                blockFlags |= 1 << (7 - i)
                tempBuffer[tempBufferCursor] = (((searchLen - 3) & 0xF) << 4) + ((searchDisp >> 8) & 0xF)
                tempBuffer[tempBufferCursor+1] = searchDisp & 0xFF
                tempBufferCursor += 2
                current += searchLen
            else:
                tempBuffer[tempBufferCursor] = data[current]
                tempBufferCursor += 1; current += 1

        res.extend(bytes([blockFlags]) + tempBuffer[:tempBufferCursor])

    return bytes(res)