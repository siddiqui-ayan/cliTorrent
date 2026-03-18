from .bencode import bencode, bdecode
import hashlib
import time
import os


class Torrent:
    """Initialize a torrent from a given path"""
    def __init__(self, torrentPath):
        # print(torrentPath)
        metadata = open(torrentPath,'rb').read()
        self.decoded, _ = bdecode(metadata)

        if b'info' not in self.decoded:
            raise ValueError("Torrent file does not contain any info value")

        self.info = self.decoded[b'info']
        self.infoHash = self.calcInfoHash(self.info)
        self.creationDate = self.decoded[b'creation date'] if b'creation date' in self.decoded else 'unkown'
        self.name = self.decoded[b'name'] if b'name' in self.decoded else 'unkown'
        self.announceList = self.decoded[b'announce-list'] if b'announce-list' in self.decoded else [[self.decoded[b'announce']]]
        self.peerId = self.generatePeerId()
        self.totalLength: int = 0
        self.filesNames = []
        self.fileNames = self.filesNames
        self.numPieces = len(self.info[b"pieces"]) // 20
        self.pieceLength = self.info[b'piece length']

        self.initFiles()

    def calcInfoHash(self, info):
        """Takes in the encoded info of a torrent file and returns an sha1 hash"""
        infoBencoded = bencode(info)
        infoHash = hashlib.sha1(infoBencoded).digest()
        return infoHash
    
    def initFiles(self):
        root = self.info[b'name']
        if b'files' in self.info:
            if not os.path.exists(root):
                os.mkdir(root, 0o0766 )

            for file in self.info[b'files']:
                pathFile = os.path.join(root, *file[b"path"])

                if not os.path.exists(os.path.dirname(pathFile)):
                    os.makedirs(os.path.dirname(pathFile))

                self.filesNames.append({"path": pathFile , "length": file[b"length"]})
                self.totalLength += file[b"length"]
        else:
            self.filesNames.append({"path": root, "length": self.info[b'length']})
            self.totalLength = self.info[b'length']

    def generatePeerId(self):
        seed = str(time.time())
        return hashlib.sha1(seed.encode('utf-8')).digest()
    # def getAnnounceList(self):
        
        
    