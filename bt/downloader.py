import asyncio
import hashlib
import os
import time
from collections import deque
from .torrent import Torrent
from .peers import AsyncBittorentPeer


async def downloadPieceFromPeer(peer: AsyncBittorentPeer, pieceIndex, pieceLength, blockSize=16384):
    """Download a single piece from a peer.
    
    Keyword arguments:
    peer -- Takes in the AsyncBittorentPeer object
    pieceIndex -- Takes in the index of the piece to download
    pieceLength -- The total length/size of the piece

    Returns: dict of {offset: block_data} or None if failed.
    """
    if not peer:
        return None
    
    if not peer.isInterested:
        await peer.sendInterested()

    waitTime = 0
    while peer.peerChoking and waitTime < 5:
        msg_id, payload = await peer.readMessage()
        if msg_id is not None:
            await peer.handleMessage(msg_id, payload)
        await asyncio.sleep(0.1)
        waitTime += 0.1

    if peer.peerChoking:
        return None

    blocksNeeded = []

    for begin in range(0, pieceLength, blockSize):
        length = min(blockSize, pieceLength - begin)
        blocksNeeded.append((begin, length))
        await peer.requestPiece(pieceIndex, begin, length)

    pieceData = {}
    timeoutCounter = 0
    maxTimeout = 100
    
    while len(pieceData) < len(blocksNeeded) and timeoutCounter < maxTimeout:

        msg_id, payload = await peer.readMessage()
        if msg_id is None:

            timeoutCounter += 1
            await asyncio.sleep(0.1)
            continue

        result = await peer.handleMessage(msg_id, payload)

   
        if result and result[0] == 'piece':
            _, idx, begin, block = result
            if idx == pieceIndex:
                pieceData[begin] = block
                timeoutCounter = 0
    
    if len(pieceData) < len(blocksNeeded):
        return None
    
    return pieceData


class TorrentDownloader:
    """Manages concurrent downloading from multiple peers
    
    Keyword arguments:
    torrent -- Takes in a Torrent object
    peers -- Takes in the AsyncBittorentPeer object
    maxPeers -- The maximum number of peers to connect to.
    """

    def __init__(self, torrent: Torrent, peers, maxPeers=10):
        self.torrent = torrent
        self.peers = peers
        self.maxPeers = maxPeers
        self.info = self.torrent.info
        self.infoHash = self.torrent.infoHash

        self.pieceLength = self.info[b'piece length']

        self.pieceHash = self.info[b'pieces']
        self.numPieces = len(self.pieceHash) // 20
        self.peerId = self.torrent.peerId

        if b'length' in self.info:
            self.totalLength = self.info[b'length']
        else:
            self.totalLength = sum(f[b'length'] for f in self.info[b'files'])

        # PIECE MANAGEMENT
        self.downloadedPieces = {}
        self.pieceLocks = {i: asyncio.Lock() for i in range(self.numPieces)}
        self.piecesInProgress = set()
        self.pieceClaimTimes = {}
        self.connectedPeers = []

        # LOGGING & STATS
        self.logs = deque(maxlen=200)
        self._byteSamples = deque(maxlen=30)
        self._startTime = time.monotonic()
        self.complete = False

        self._log(f"Torrent: {self.numPieces} pieces, {self.totalLength} bytes total")

    def _log(self, message):
        self.logs.append(message)

    @property
    def downloadedBytes(self):
        return sum(len(self.downloadedPieces[i]) for i in self.downloadedPieces)

    @property
    def downloadSpeed(self):
        if len(self._byteSamples) < 2:
            return 0.0
        oldest_time, oldest_bytes = self._byteSamples[0]
        newest_time, newest_bytes = self._byteSamples[-1]
        dt = newest_time - oldest_time
        if dt <= 0:
            return 0.0
        return (newest_bytes - oldest_bytes) / dt

    @property
    def progress(self):
        if self.numPieces == 0:
            return 0.0
        return len(self.downloadedPieces) / self.numPieces

    def sampleProgress(self):
        self._byteSamples.append((time.monotonic(), self.downloadedBytes))

    def getPieceLength(self, pieceIdx):
        if pieceIdx == self.numPieces - 1:
            return self.totalLength - (pieceIdx * self.pieceLength)
        return self.pieceLength

    
    def getPieceHash(self, pieceIdx):
        """Get the hash for a specific piece"""
        return self.pieceHash[pieceIdx * 20:(pieceIdx + 1) * 20]
    
    def verifyPiece(self, pieceIdx, pieceData):
        calculatedHash = hashlib.sha1(pieceData).digest()
        expectedHash = self.getPieceHash(pieceIdx)
        return calculatedHash == expectedHash

    def _to_path_string(self, pathValue):
        if isinstance(pathValue, bytes):
            return pathValue.decode("utf-8", errors="replace")
        return str(pathValue)

    def writeDownloadedFiles(self, outputFile=None):
        allData = b"".join(self.downloadedPieces[i] for i in range(self.numPieces))
        fileSpecs = self.torrent.filesNames

        if len(fileSpecs) <= 1:
            targetPath = outputFile
            if not targetPath:
                targetPath = self._to_path_string(fileSpecs[0]["path"])
            with open(targetPath, "wb") as f:
                f.write(allData)
            return [targetPath]

        cursor = 0
        writtenPaths = []
        for fileSpec in fileSpecs:
            filePath = self._to_path_string(fileSpec["path"])
            fileLength = fileSpec["length"]
            fileChunk = allData[cursor:cursor + fileLength]

            parentDir = os.path.dirname(filePath)
            if parentDir:
                os.makedirs(parentDir, exist_ok=True)

            with open(filePath, "wb") as f:
                f.write(fileChunk)

            writtenPaths.append(filePath)
            cursor += fileLength

        return writtenPaths

    def releaseStaleClaims(self, staleSeconds=45):
        now = time.monotonic()
        stalePieces = [
            pieceIdx
            for pieceIdx, claimedAt in self.pieceClaimTimes.items()
            if (now - claimedAt) > staleSeconds and pieceIdx not in self.downloadedPieces
        ]
        for pieceIdx in stalePieces:
            self.piecesInProgress.discard(pieceIdx)
            self.pieceClaimTimes.pop(pieceIdx, None)

        if stalePieces:
            self._log(f"Released {len(stalePieces)} stale piece claims")

    async def peerWorker(self, ip, port):
        """Worker coroutine for a single peer"""
        peer = AsyncBittorentPeer(ip, port, self.infoHash, self.peerId)
        activePiece = None
        noUsefulPieceRounds = 0

        if not await peer.connect():
            return
        
        if not await peer.handshake():
            await peer.close()
            return

        self.connectedPeers.append(peer)

        for _ in range(10):
  
            msgId, payload = await peer.readMessage()
            if msgId is not None:
                await peer.handleMessage(msgId, payload)
            
            if peer.bitfield is not None:
                break
            await asyncio.sleep(0.1)
        
        try:
            while len(self.downloadedPieces) < self.numPieces:
                self.releaseStaleClaims()
                pieceIdx = None
                for i in range(self.numPieces):
                    if (i not in self.downloadedPieces) and (i not in self.piecesInProgress) and peer.hasPiece(i):
                        self.piecesInProgress.add(i)
                        self.pieceClaimTimes[i] = time.monotonic()
                        pieceIdx = i
                        break

                if pieceIdx is None:
                    noUsefulPieceRounds += 1
                    if noUsefulPieceRounds >= 25:
                        break
                    await asyncio.sleep(1)
                    continue
                noUsefulPieceRounds = 0
                activePiece = pieceIdx
                    
                # Download the piece
                pieceLength = self.getPieceLength(pieceIdx)
                pieceBlocks = await downloadPieceFromPeer(peer, pieceIdx, pieceLength)
                
                if pieceBlocks:
                    # Assemble piece
                    completePiece = b''.join(pieceBlocks[offset] for offset in sorted(pieceBlocks.keys()))
        
                    if self.verifyPiece(pieceIdx, completePiece):
                        async with self.pieceLocks[pieceIdx]:
                            self.downloadedPieces[pieceIdx] = completePiece
                            self.piecesInProgress.discard(pieceIdx)
                            self.pieceClaimTimes.pop(pieceIdx, None)
                            activePiece = None
                        
                        progress = len(self.downloadedPieces)
                        self._log(f"✓ Piece {pieceIdx} downloaded from {ip}:{port} ({progress}/{self.numPieces})")
                    else:
                        self._log(f"✗ Piece {pieceIdx} failed verification from {ip}:{port}")
                        async with self.pieceLocks[pieceIdx]:
                            self.piecesInProgress.discard(pieceIdx)
                            self.pieceClaimTimes.pop(pieceIdx, None)
                            activePiece = None
                else:
                    # Failed to download
                    async with self.pieceLocks[pieceIdx]:
                        self.piecesInProgress.discard(pieceIdx)
                        self.pieceClaimTimes.pop(pieceIdx, None)
                        activePiece = None
                    await asyncio.sleep(0.5)
        
        except Exception as e:
            self._log(f"Error in peer worker {ip}:{port}: {e}")
        finally:
            if activePiece is not None:
                self.piecesInProgress.discard(activePiece)
                self.pieceClaimTimes.pop(activePiece, None)
            await peer.close()
            if peer in self.connectedPeers:
                self.connectedPeers.remove(peer)

    async def download(self, output_file=None):
        """Start concurrent download from multiple peers."""
        peerPool = list(self.peers)
        nextPeerIdx = 0
        retryRounds = 0
        maxRetryRounds = 2
        activeTasks = {}
        lastProgress = -1
        stallTicks = 0

        while True:
            while len(activeTasks) < self.maxPeers and nextPeerIdx < len(peerPool):
                ip, port = peerPool[nextPeerIdx]
                nextPeerIdx += 1
                task = asyncio.create_task(self.peerWorker(ip, port))
                activeTasks[task] = (ip, port)
                await asyncio.sleep(0.05)

            if len(self.downloadedPieces) >= self.numPieces:
                break

            if not activeTasks:
                if retryRounds >= maxRetryRounds:
                    break
                retryRounds += 1
                nextPeerIdx = 0
                self._log(f"No active peers left, retrying peer list (round {retryRounds}/{maxRetryRounds})")
                continue

            await asyncio.sleep(1)

            finishedTasks = [task for task in activeTasks if task.done()]
            for task in finishedTasks:
                activeTasks.pop(task, None)

            currentProgress = len(self.downloadedPieces)
            if currentProgress == lastProgress:
                stallTicks += 1
            else:
                stallTicks = 0
                lastProgress = currentProgress

            if stallTicks >= 20:
                # Force reclaim pieces that may be stuck due to dropped peers
                self.releaseStaleClaims(staleSeconds=5)
                stallTicks = 0

            self.sampleProgress()

        for task in list(activeTasks.keys()):
            if not task.done():
                task.cancel()

        if activeTasks:
            await asyncio.gather(*activeTasks.keys(), return_exceptions=True)
        
        # Write to file if complete
        if len(self.downloadedPieces) == self.numPieces:
            self._log("Download complete! Writing to file...")
            writtenPaths = self.writeDownloadedFiles(output_file)
            if len(writtenPaths) == 1:
                self._log(f"✓ File saved to {writtenPaths[0]}")
            else:
                self._log(f"✓ Wrote {len(writtenPaths)} files from torrent metadata")
            self.complete = True
            return True
        else:
            self._log(f"✗ Download incomplete: {len(self.downloadedPieces)}/{self.numPieces} pieces")
            return False

async def downloadFromPeersAsync(torrentFile, peers, outputFile=None, maxPeers=5):
    """
    Download a torrent using multiple peers concurrently.
    
    Args:
        torrent_file: Path to .torrent file
        peers: List of (ip, port) tuples
        output_file: Optional output path for single-file torrents
        max_peers: Maximum number of concurrent peer connections
    """
    torrent = torrentFile if isinstance(torrentFile, Torrent) else Torrent(torrentFile)
    downloader = TorrentDownloader(torrent, peers, maxPeers)
    success = await downloader.download(outputFile)
    return success