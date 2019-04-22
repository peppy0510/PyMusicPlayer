# Copyright(c) 2006 Eric Faurot <eric.faurot@gmail.com>
# See LICENSE for details.

# Python 3 adaptation by Maxim Kolosov


import struct

from sys import hexversion


# CHAR_CODEC = 'utf-8'
CHAR_CODEC = 'cp1251'

if hexversion < 0x03000000:
    _range = xrange  # noqa
    _chr = chr
else:
    _range = range

    def _chr(value):
        return bytes([value])


_crc = (
    0x00000000, 0x04c11db7, 0x09823b6e, 0x0d4326d9,
    0x130476dc, 0x17c56b6b, 0x1a864db2, 0x1e475005,
    0x2608edb8, 0x22c9f00f, 0x2f8ad6d6, 0x2b4bcb61,
    0x350c9b64, 0x31cd86d3, 0x3c8ea00a, 0x384fbdbd,
    0x4c11db70, 0x48d0c6c7, 0x4593e01e, 0x4152fda9,
    0x5f15adac, 0x5bd4b01b, 0x569796c2, 0x52568b75,
    0x6a1936c8, 0x6ed82b7f, 0x639b0da6, 0x675a1011,
    0x791d4014, 0x7ddc5da3, 0x709f7b7a, 0x745e66cd,
    0x9823b6e0, 0x9ce2ab57, 0x91a18d8e, 0x95609039,
    0x8b27c03c, 0x8fe6dd8b, 0x82a5fb52, 0x8664e6e5,
    0xbe2b5b58, 0xbaea46ef, 0xb7a96036, 0xb3687d81,
    0xad2f2d84, 0xa9ee3033, 0xa4ad16ea, 0xa06c0b5d,
    0xd4326d90, 0xd0f37027, 0xddb056fe, 0xd9714b49,
    0xc7361b4c, 0xc3f706fb, 0xceb42022, 0xca753d95,
    0xf23a8028, 0xf6fb9d9f, 0xfbb8bb46, 0xff79a6f1,
    0xe13ef6f4, 0xe5ffeb43, 0xe8bccd9a, 0xec7dd02d,
    0x34867077, 0x30476dc0, 0x3d044b19, 0x39c556ae,
    0x278206ab, 0x23431b1c, 0x2e003dc5, 0x2ac12072,
    0x128e9dcf, 0x164f8078, 0x1b0ca6a1, 0x1fcdbb16,
    0x018aeb13, 0x054bf6a4, 0x0808d07d, 0x0cc9cdca,
    0x7897ab07, 0x7c56b6b0, 0x71159069, 0x75d48dde,
    0x6b93dddb, 0x6f52c06c, 0x6211e6b5, 0x66d0fb02,
    0x5e9f46bf, 0x5a5e5b08, 0x571d7dd1, 0x53dc6066,
    0x4d9b3063, 0x495a2dd4, 0x44190b0d, 0x40d816ba,
    0xaca5c697, 0xa864db20, 0xa527fdf9, 0xa1e6e04e,
    0xbfa1b04b, 0xbb60adfc, 0xb6238b25, 0xb2e29692,
    0x8aad2b2f, 0x8e6c3698, 0x832f1041, 0x87ee0df6,
    0x99a95df3, 0x9d684044, 0x902b669d, 0x94ea7b2a,
    0xe0b41de7, 0xe4750050, 0xe9362689, 0xedf73b3e,
    0xf3b06b3b, 0xf771768c, 0xfa325055, 0xfef34de2,
    0xc6bcf05f, 0xc27dede8, 0xcf3ecb31, 0xcbffd686,
    0xd5b88683, 0xd1799b34, 0xdc3abded, 0xd8fba05a,
    0x690ce0ee, 0x6dcdfd59, 0x608edb80, 0x644fc637,
    0x7a089632, 0x7ec98b85, 0x738aad5c, 0x774bb0eb,
    0x4f040d56, 0x4bc510e1, 0x46863638, 0x42472b8f,
    0x5c007b8a, 0x58c1663d, 0x558240e4, 0x51435d53,
    0x251d3b9e, 0x21dc2629, 0x2c9f00f0, 0x285e1d47,
    0x36194d42, 0x32d850f5, 0x3f9b762c, 0x3b5a6b9b,
    0x0315d626, 0x07d4cb91, 0x0a97ed48, 0x0e56f0ff,
    0x1011a0fa, 0x14d0bd4d, 0x19939b94, 0x1d528623,
    0xf12f560e, 0xf5ee4bb9, 0xf8ad6d60, 0xfc6c70d7,
    0xe22b20d2, 0xe6ea3d65, 0xeba91bbc, 0xef68060b,
    0xd727bbb6, 0xd3e6a601, 0xdea580d8, 0xda649d6f,
    0xc423cd6a, 0xc0e2d0dd, 0xcda1f604, 0xc960ebb3,
    0xbd3e8d7e, 0xb9ff90c9, 0xb4bcb610, 0xb07daba7,
    0xae3afba2, 0xaafbe615, 0xa7b8c0cc, 0xa379dd7b,
    0x9b3660c6, 0x9ff77d71, 0x92b45ba8, 0x9675461f,
    0x8832161a, 0x8cf30bad, 0x81b02d74, 0x857130c3,
    0x5d8a9099, 0x594b8d2e, 0x5408abf7, 0x50c9b640,
    0x4e8ee645, 0x4a4ffbf2, 0x470cdd2b, 0x43cdc09c,
    0x7b827d21, 0x7f436096, 0x7200464f, 0x76c15bf8,
    0x68860bfd, 0x6c47164a, 0x61043093, 0x65c52d24,
    0x119b4be9, 0x155a565e, 0x18197087, 0x1cd86d30,
    0x029f3d35, 0x065e2082, 0x0b1d065b, 0x0fdc1bec,
    0x3793a651, 0x3352bbe6, 0x3e119d3f, 0x3ad08088,
    0x2497d08d, 0x2056cd3a, 0x2d15ebe3, 0x29d4f654,
    0xc5a92679, 0xc1683bce, 0xcc2b1d17, 0xc8ea00a0,
    0xd6ad50a5, 0xd26c4d12, 0xdf2f6bcb, 0xdbee767c,
    0xe3a1cbc1, 0xe760d676, 0xea23f0af, 0xeee2ed18,
    0xf0a5bd1d, 0xf464a0aa, 0xf9278673, 0xfde69bc4,
    0x89b8fd09, 0x8d79e0be, 0x803ac667, 0x84fbdbd0,
    0x9abc8bd5, 0x9e7d9662, 0x933eb0bb, 0x97ffad0c,
    0xafb010b1, 0xab710d06, 0xa6322bdf, 0xa2f33668,
    0xbcb4666d, 0xb8757bda, 0xb5365d03, 0xb1f740b4
)


def checksum(header, body):
    reg = 0
    for c in header:
        reg = ((reg << 8) & 0xffffffff) ^ _crc[((reg >> 24) & 0xff) ^ ord(c)]
    for i in (0, 0, 0, 0):
        reg = ((reg << 8) & 0xffffffff) ^ _crc[((reg >> 24) & 0xff) ^ i]
    for c in body:
        reg = ((reg << 8) & 0xffffffff) ^ _crc[((reg >> 24) & 0xff) ^ ord(c)]
    return reg


def split_segments(data, segs):
    segments = []
    start = 0
    stop = 0
    map_segs = segs
    if hexversion < 0x03000000:
        map_segs = map(ord, segs)
    for length in map_segs:
        if length:
            stop += length
            segments.append(data[start:stop])
            start = stop
        else:
            segments.append(b'')
    return segments


def segmentsToPackets(segments):
    packets = []
    packet = []
    for segment in segments:
        packet.append(segment)
        if len(segment) != 255:
            packets.append(b''.join(packet))
            packet = []
    return packets, packet


class OggPage(object):
    version = 0
    headerType = None
    streamID = None
    granulePosition = None
    sequenceNumber = None
    segments = None
    checksum = None
    rawData = None

    def continued(self):
        return self.segments[-1] == 255
    continued = property(continued)

    def packetCount(self):
        return len([s for s in self.segments if len(s) != 255])

    def getPackets(self):
        return segmentsToPackets(self.segments)

    def dataLength(self):
        return sum(map(len, self.segments))

    def pageOverhead(self):
        return 27 + len(self.segments)

    def payload(self):
        return self.pageOverhead() + self.dataLength()

    def pack(self):
        header = struct.pack("<4sBBqLL", b'OggS', self.version, self.headerType,
                             self.granulePosition, self.streamID, self.sequenceNumber)

        def _(s):
            return _chr(len(s))

        body = b''.join([_chr(len(self.segments))] + map(_, self.segments) + self.segments)
        return b''.join([header, struct.pack("<L", checksum(header, body)), body])

    def __repr__(self):
        return ('<OggPage version=%r headerType=%r streamID=%r granulePosition=%r '
                'sequenceNumber=%r continued=%r segments=%r payload=%r>') % (
            self.version, self.headerType, self.streamID, self.granulePosition,
            self.sequenceNumber, self.continued, len(self.segments), self.payload())


class iobuffer(object):

    def __init__(self, data=b''):
        self.data = data
        self.offset = 0
        self.bytes = 0
        self.length = len(data)

    def write(self, data):
        self.data = b''.join([self.data[self.offset:], data])
        self.offset = 0
        self.length += len(data)

    def __len__(self):
        return self.length

    def read(self, count):
        assert self.length >= count
        chunk = self.data[self.offset:self.offset + count]
        self.length -= count
        self.offset += count
        self.bytes += len(chunk)
        return chunk

    def unpack(self, format, size=None):
        if size is None:
            size = struct.calcsize(format)
        return struct.unpack(format, self.read(size))

    def unread(self, data):
        self.data = b''.join([data, self.data[self.offset:]])
        self.offset = 0
        self.length += len(data)


class Parser(object):
    expected = 0
    processed = 0

    def __init__(self, expected):
        self._buffer = iobuffer()
        self.expected = expected

    def buffered(self):
        return self._buffer.data[self._buffer.offset:]

    def required(self):
        return self.expected - len(self._buffer)

    def process(self, data):
        self._buffer.write(data)
        while len(self._buffer) >= self.expected:
            chunk = self._buffer.read(self.expected)
            try:
                self.expected = self.processChunk(chunk)
                self.processed += len(chunk)
            except Exception:
                raise

    def processChunk(self, chunk):
        raise NotImplementedError


class OggReader(Parser):
    pages = 0
    HEADER_LENGTH = 27

    def __init__(self):
        Parser.__init__(self, self.HEADER_LENGTH)
        self.__currentPage = None
        self.processChunk = self.processHeader

    def processHeader(self, data):
        self.__currentPage = p = OggPage()
        (magic, p.version, p.headerType, p.granulePosition, p.streamID,
         p.sequenceNumber, p.checksum, nseg) = struct.unpack("<4sBBqLLLB", data)
        if magic != b'OggS':
            raise ValueError('Not an ogg page')
        self.__raw = [data]
        self.processChunk = self.processSegmentTable
        return nseg

    def processSegmentTable(self, data):
        self.__segmentTable = data
        self.__raw.append(data)
        self.processChunk = self.processSegments
        if hexversion < 0x03000000:
            return sum(map(ord, data))
        else:
            return sum(data)

    def processSegments(self, data):
        page = self.__currentPage
        page.segments = split_segments(data, self.__segmentTable)
        self.__raw.append(data)
        page.rawData = b''.join(self.__raw)
        self.pageReceived(page)
        self.pages += 1
        self.processChunk = self.processHeader
        return self.HEADER_LENGTH

    def outOfBandDataReceived(self, data):
        pass

    def pageReceived(self, page):
        raise NotImplementedError


class OggDemultiplexer(OggReader):

    def __init__(self):
        OggReader.__init__(self)
        self.streams = {}
        self.readingHeaders = True

    def buildStream(self, packet):
        return self.streamFactory(self, packet)

    def pageReceived(self, page):
        if self.readingHeaders:
            if page.headerType & 0x02:
                assert page.headerType & 0x01 == 0
                assert page.headerType & 0x04 == 0
                assert page.streamID not in self.streams
                assert not page.continued
                packets, left = page.getPackets()
                assert len(packets) == 1
                stream = self.buildStream(packets[0])
                stream.processPage(page)
                self.streams[page.streamID] = stream
                return
            self.readingHeaders = False
        assert page.headerType & 0x02 == 0
        assert page.streamID in self.streams
        stream = self.streams[page.streamID]
        stream.processPage(page)
        if page.headerType & 0x04:
            stream.endStream()
            del self.streams[page.streamID]
            if len(self.streams) == 0:
                self.allStreamsEnded()

    def outOfBandPageReceived(self, page):
        pass

    def allStreamsEnded(self):
        self.readingHeaders = True


class SimpleDemultiplexer(OggDemultiplexer):

    def __init__(self, streamReader):
        OggDemultiplexer.__init__(self)
        self.streamReader = streamReader

    def buildStream(self, packet):
        assert len(self.streams) == 0
        return self.streamReader


class VorbisIdentification(object):
    version = None
    audioChannels = None
    sampleRate = None
    maximumBitrate = None
    nominalBitrate = None
    minimumBitrate = None
    blocksize = None
    # ~ PACKET_HEADER = chr(1) + b'vorbis'
    PACKET_HEADER = b'\x01vorbis'

    def __repr__(self):
        return ('<VorbisIdentification version=%r audioChannels=%r '
                'sampleRate=%r bitrates=[ %r, %r, %r ] blocksize=%r>') % (
            self.version, self.audioChannels, self.sampleRate, self.minimumBitrate,
            self.nominalBitrate, self.maximumBitrate, self.blocksize)

    def positionToSeconds(self, position):
        return float(position) / self.sampleRate

    def pack(self):
        return ''.join([self.PACKET_HEADER, s.pack(
            "<IBIiiiBB", self.version, self.audioChannels, self.sampleRate, self.maximumBitrate,
            self.nominalBitrate, self.minimumBitrate, self.blocksize, 1), ])


class VorbisComments(object):
    vendor = None
    comments = None
    # ~ PACKET_HEADER = chr(3) + b'vorbis'
    PACKET_HEADER = b'\x03vorbis'

    def pack(self):
        vendor = self.vendor.encode(CHAR_CODEC)
        data = [self.PACKET_HEADER, struct.pack("<L", len(vendor)), vendor, struct.pack("<L", len(self.comments))]
        for key, value in self.comments:
            key = key.upper()
            value = value.encode(CHAR_CODEC)
            data.append(struct.pack("<L", len(key) + 1 + len(value)))
            data.append(key)
            data.append(b'=')
            data.append(value)
        data.append(b'\x01')
        return ''.join(data)


class VorbisSetup(object):
    codebooks = None
    timeDomainTransforms = None
    floorType = None
    residues = None
    mappings = None
    modes = None
    # ~ PACKET_HEADER = chr(5) + b'vorbis'
    PACKET_HEADER = b'\x05vorbis'

    def pack(self):
        return self.rawPacket


class OggStreamReader(object):
    pages = 0
    __segments = None

    def endStream(self):
        pass

    def processPage(self, page):
        position = page.granulePosition
        if self.__segments is None:
            self.__segments = []
        self.__segments.extend(page.segments)
        packets, self.__segments = segmentsToPackets(self.__segments)
        if packets:
            self.packetsReceived(packets, position)
        else:
            assert position == -1
        self.pages += 1

    def packetsReceived(self, packets, position):
        pass


class VorbisStreamReader(OggStreamReader):
    identification = None
    comments = None
    setup = None

    def __init__(self):
        OggStreamReader.__init__(self)
        self.__expected = 'identification'

    def packetsReceived(self, packets, position):
        if not self.__expected:
            return self.audioPacketsReceived(packets, position)
        assert position == 0
        for packet in packets:
            handler = getattr(self, 'read_%s' % self.__expected)
            handler(packet)

    def read_identification(self, packet):
        s = iobuffer(packet)
        header = VorbisIdentification.PACKET_HEADER
        assert s.read(len(header)) == header
        i = VorbisIdentification()
        (i.version, i.audioChannels, i.sampleRate, i.maximumBitrate, i.nominalBitrate,
         i.minimumBitrate, i.blocksize, framingFlag) = s.unpack("<IBIiiiBB")
        assert len(s) == 0
        self.__expected = 'comments'
        self.identificationReceived(i)

    def read_comments(self, packet):
        s = iobuffer(packet)
        header = VorbisComments.PACKET_HEADER
        assert s.read(len(header)) == header
        length, = s.unpack("<L")
        comments = VorbisComments()
        comments.vendor = s.read(length).decode(CHAR_CODEC)
        comments.comments = []
        ncomments, = s.unpack("<L")
        for i in _range(ncomments):
            length, = s.unpack("<L")
            key, value = s.read(length).split(b'=', 1)
            comments.comments.append([key.upper(), value.decode(CHAR_CODEC)])
        assert s.read(1) == b'\x01'
        assert len(s) == 0
        self.__expected = 'setup'
        self.commentsReceived(comments)

    def read_setup(self, packet):
        assert packet.startswith(VorbisSetup.PACKET_HEADER)
        setup = VorbisSetup()
        setup.rawPacket = packet
        self.__expected = None
        self.setupReceived(setup)

    def identificationReceived(self, identification):
        self.identification = identification

    def commentsReceived(self, comments):
        self.comments = comments

    def setupReceived(self, setup):
        self.setup = setup

    def audioPacketsReceived(self, packets, position):
        pass


class VorbisStreamInfo(VorbisStreamReader):
    lastPosition = None
    startPosition = None
    payload = 0
    overhead = 0
    pageCount = 0
    audioPackets = 0
    audioPacketLength = 0
    stop = 0
    start = 0

    def pageReceived(self, page):
        self.pageCount += 1
        self.payload += page.payload()
        self.overhead += page.pageOverhead()
        VorbisStreamReader.pageReceived(self, page)

    def audioPacketsReceived(self, packets, position):
        if self.startPosition is None:
            self.startPosition = position
        self.lastPosition = position
        self.audioPackets += len(packets)
        self.audioPacketLength += sum(map(len, packets))

    def identificationReceived(self, identification):
        self.identification = identification

    def setupReceived(self, setup):
        self.setup = setup

    def commentsReceived(self, comments):
        self.comments = comments

    def endStream(self):
        self.stop = self.identification.positionToSeconds(self.lastPosition)
        self.start = self.identification.positionToSeconds(self.startPosition)


if __name__ == '__main__':
    from sys import hexversion
    info = VorbisStreamInfo()
    stream = SimpleDemultiplexer(info)
    stream.process(open('test.ogg', 'rb').read())
    print('size            : %d' % info.payload)
    print('overhead        : %d' % info.overhead)
    print('pages           : %d' % info.pageCount)
    print('audio packets   : %d' % info.audioPackets)
    print('audio length    : %d' % info.audioPacketLength)
    print('vendor          : %s' % info.comments.vendor)
    print('comment entries : %d' % len(info.comments.comments))
    for key, value in info.comments.comments:
        if hexversion < 0x03000000:
            print('- %s: %s' % (key, value.encode(CHAR_CODEC)))
        else:
            print('- %s: %s' % (key, value))
    print('sample rate     : %d' % info.identification.sampleRate)
    print('audio channels  : %d' % info.identification.audioChannels)
    print('nominal bitrate : %d' % info.identification.nominalBitrate)
    print('first frame     : %fs' % info.start)
    import datetime
    print('duration        : %s' % datetime.timedelta(seconds=info.stop - info.start))
