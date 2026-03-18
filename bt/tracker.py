import requests
import socket
import struct
import logging
import random
from urllib.parse import urlparse
from .bencode import bdecode

MAX_PEERS_TRY_CONNECT = 30
MAX_PEERS_CONNECTED = 8



class TrackerClient:
    def __init__(self, torrent):
        self.torrent = torrent
        self.peerList = set()   # no duplicates
        self.timeout = 5

    def getPeersFromTracker(self):
        for tier in self.torrent.announceList:
            try:
                trackerUrl = tier[0] if isinstance(tier, (list, tuple)) else tier
                if isinstance(trackerUrl, bytes):
                    trackerUrl = trackerUrl.decode("utf-8", errors="replace")

                if trackerUrl.startswith("http"):
                    peersBinary = self.httpScraper(trackerUrl)
                    peers = self.parse_compact_peers(peersBinary)
                elif trackerUrl.startswith("udp"):
                    peers = self.udpScraper(trackerUrl)
                else:
                    continue

                self.peerList.update(peers)

            except Exception as e:
                logging.warning(f"Tracker failed: {trackerUrl} -> {e}")

        return list(self.peerList)

    def httpScraper(self, tracker):
        params = {
            "info_hash": self.torrent.infoHash,
            "peer_id": self.torrent.peerId,
            "uploaded": 0,
            "downloaded": 0,
            "left": self.torrent.totalLength,
            "port": 6881,
            "compact": 1,      # we want binary peers
            "event": "started"
        }

        res = requests.get(tracker, params=params, timeout=self.timeout)
        res.raise_for_status()

        decoded, _ = bdecode(res.content)

        if b"failure reason" in decoded:
            raise Exception(decoded[b"failure reason"].decode())

        return decoded.get(b"peers", b"")

    def parse_compact_peers(self, peersBinary):
        peers = []

        if len(peersBinary) % 6 != 0:
            logging.warning("Malformed peer list")
            return peers

        for i in range(0, len(peersBinary), 6):
            ip = socket.inet_ntoa(peersBinary[i:i+4])
            port = struct.unpack(">H", peersBinary[i+4:i+6])[0]
            peers.append((ip, port))

        return peers

    def udpScraper(self, trackerUrl):
        parsed = urlparse(trackerUrl)
        host = parsed.hostname
        port = parsed.port or 80
        if not host:
            raise ValueError("Invalid UDP tracker URL")

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            transactionId = random.randint(0, 0xFFFFFFFF)

    
            connectRequest = struct.pack(">QII", 0x41727101980, 0, transactionId)
            sock.sendto(connectRequest, (host, port))
            connectResponse, _ = sock.recvfrom(2048)

            if len(connectResponse) < 16:
                raise ValueError("Short UDP connect response")

            action, respTransactionId, connectionId = struct.unpack(">IIQ", connectResponse[:16])
            if action != 0 or respTransactionId != transactionId:
                raise ValueError("Invalid UDP connect response")

            announceTx = random.randint(0, 0xFFFFFFFF)
            announceRequest = struct.pack(
                ">QII20s20sQQQIIIiH",
                connectionId,
                1,
                announceTx,
                self.torrent.infoHash,
                self.torrent.peerId,
                0,
                self.torrent.totalLength,
                0,
                2,
                0,
                random.randint(0, 0xFFFFFFFF),
                -1,
                6881,
            )
            sock.sendto(announceRequest, (host, port))
            announceResponse, _ = sock.recvfrom(65536)

            if len(announceResponse) < 20:
                raise ValueError("Short UDP announce response")

            action, respTransactionId, _, _, _ = struct.unpack(">IIIII", announceResponse[:20])
            if action != 1 or respTransactionId != announceTx:
                raise ValueError("Invalid UDP announce response")

            return self.parse_compact_peers(announceResponse[20:])
        finally:
            sock.close()