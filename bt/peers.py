import struct
import hashlib
import asyncio
from .torrent import Torrent
from .tracker import TrackerClient


class AsyncBittorentPeer:
    def __init__(self, ip, port, infoHash, peerId, timeout=10):
        self.ip = ip
        self.port = port
        self.infoHash = infoHash
        self.peerId = peerId
        self.timeout = timeout
        self.reader = None
        self.writer = None
        self.isInterested = False
        self.peerChoking = True
        self.bitfield = None

    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port),
                timeout=self.timeout
            )
            return True
        except Exception:
            return False

    async def handshake(self):
        try:
            self.writer.write(self.buildHandshake())
            await self.writer.drain()

            response = await asyncio.wait_for(
                self.reader.readexactly(68),
                timeout=self.timeout
            )

            if response[28:48] != self.infoHash:
                return False

            return True

        except Exception:
            return False

    async def sendInterested(self):
        try:
            self.writer.write(struct.pack(">IB", 1, 2))
            await self.writer.drain()
            self.isInterested = True
        except Exception:
            pass

    async def readMessage(self):
        length_data = await asyncio.wait_for(self.reader.readexactly(4), timeout=self.timeout)
        length = struct.unpack(">I", length_data)[0]
        if length == 0:
            return None, None
        message = await asyncio.wait_for(self.reader.readexactly(length), timeout=self.timeout)
        return message[0], message[1:]

    async def requestPiece(self, pieceIndex, offset, length=16384):
        self.writer.write(struct.pack(">IBIII", 13, 6, pieceIndex, offset, length))
        await self.writer.drain()

    def verifyPiece(self, expectedHash, data):
        return hashlib.sha1(data).digest() == expectedHash

    async def handleMessage(self, msgId, payload):
        if msgId is None:
            return None

        if msgId == 0:
            self.peerChoking = True

        elif msgId == 1:
            self.peerChoking = False
            await self.requestPiece(pieceIndex=0, offset=0)  # start requesting

        elif msgId == 2:
            self.isInterested = True

        elif msgId == 3:
            self.isInterested = False

        # elif msgId == 4:
        #     piece_index = struct.unpack(">I", payload)[0]
        
        elif msgId == 5:
            self.bitfield = payload

        elif msgId == 7:
            index = struct.unpack(">I", payload[0:4])[0]
            begin = struct.unpack(">I", payload[4:8])[0]
            block = payload[8:]
            return ('piece', index, begin, block)

    def buildHandshake(self):
        """Build a 68 byte long handshake message
        
        Returns: 
            bytes: A 68-byte handshake message ready to be sent to a peer.
        """
        
        pstr = b"BitTorrent protocol"
        return struct.pack(
            ">B19s8s20s20s",
            len(pstr),
            pstr,
            b"\x00" * 8,
            self.infoHash,
            self.peerId
        )
    
    def hasPiece(self, piece_index):
        """Check if peer has a specific piece."""
        if self.bitfield is None:
            return False
        byteIndex = piece_index // 8
        bitIndex = 7 - (piece_index % 8)
        if byteIndex >= len(self.bitfield):
            return False
        
        return bool((self.bitfield[byteIndex] >> bitIndex) & 1)
    
    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()

        # self.connect
    # async def messageLoop(self):
    #     try:
    #         while True:
    #             msgId, payload = await self.readMessage()
    #             result = await self.handleMessage(msgId, payload)
    #             if result and result[0] == "piece":
    #                 _, index, begin, block = result
    #                 print(f"Received block {index}:{begin}")
    #     except asyncio.IncompleteReadError:
    #         print(f"[INFO] Connection closed by {self.ip}:{self.port}")
    #     except Exception as e:
    #         print(f"[ERROR] messageLoop error with {self.ip}:{self.port} - {e}")

if __name__ == "__main__":
    async def main():
        torrent = Torrent('./examples/onepiece.torrent')
        trackerClient = TrackerClient(torrent)
        peers = trackerClient.getPeersFromTracker()

        for ip, port in peers[:10]:
            peer = AsyncBittorentPeer(ip, port, torrent.infoHash, torrent.peerId)

            if await peer.connect():
                if await peer.handshake():
                    await peer.sendInterested()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
