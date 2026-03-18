<p align="center">
  <img src="images/logo.png" alt="cliTorrent logo" width="64" height="64" style="border-radius: 50px;"/>
</p>

<h1 align="center">cliTorrent 🧲</h1>

<p>
cliTorrent is a minimal async BitTorrent client built from scratch — handling peer connections, trackers (HTTP/UDP), and piece verification — all inside a terminal.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.x-blue"/>
  <img src="https://img.shields.io/badge/license-MIT-green"/>
</p>


## Demo
Live demo of the client downloading a torrent file

<img src="images/demo.gif" alt="Demo" />

## Features implemented
- ✅ Full `.torrent` file parser (bencode format)
- ✅ Multi-tracker support (HTTP/HTTPS **and UDP**)
- ✅ Concurrent downloads from multiple peers using `asyncio`
- ✅ Single-file and multi-file torrent support
- ✅ SHA-1 piece verification
- ✅ Intelligent stall recovery and peer rotation
- ✅ A simple terminal based UI
- ❌ DHT support
- ❌ Rarest piece first implementation
- ❌ Uploading/seeding to other peers
- ❌ Downlolad multiple torrents at once


## Flow of my bittorent client
```
        ┌─────────────────────────────────────────────────────────────────┐
        │                    BitTorrent Client Flow                       │
        └─────────────────────────────────────────────────────────────────┘

                         ┌──────────────┐
                         │  User Input  │
                         │(Torrent File)│
                         └──────┬───────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │  Parse Torrent File │
                    │  (bencode, torrent) │
                    └────────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
            ┌───────────────┐      ┌──────────────────┐
            │ Extract Meta  │      │ Calculate Info   │
            │ (filename,    │      │ Hash (SHA-1)     │
            │  size, etc)   │      └──────────────────┘
            └───────────────┘
                    │
                    ▼
          ┌──────────────────────┐
          │ Contact Tracker      │
          │ (tracker.py)         │
          │ Get Peer List        │
          └─────────┬────────────┘
                    │
                    ▼
          ┌──────────────────────┐
          │ Establish P2P Conn   │
          │ (peers.py)           │
          │ Download Pieces      │
          └─────────┬────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    ┌────────┐ ┌────────┐ ┌──────────┐
    │Piece 1 │ │Piece 2 │ │Piece N   │
    └─────┬──┘ └────┬───┘ └─────┬────┘
          │         │           │
          └────────┬┴──────────┬─┘
                   ▼           ▼
          ┌──────────────────────┐
          │ Verify Hash & Save   │
          │ (downloader.py)      │
          └─────────┬────────────┘
                    │
                    ▼
          ┌──────────────────────┐
          │ Update UI Status     │
          │ (ui.py)              │
          │ Progress, Speed, etc │
          └──────────────────────┘
```

## Installation
1. Clone the repo
```
git clone https://github.com/siddiqui-ayan/cliTorrent
cd cliTorrent
```
2. Install the required modules
```
pip install -r requirements.txt
```
3. Run the bittorent client
```
python main.py ./examples/onepiece.torrent
```


## Sources
I wouldn't have been able to get this far without the help of the following resources: Markus Eliasson's [bittorent blog](https://markuseliasson.se/article/bittorrent-in-python/), manware's [youtube video](https://www.youtube.com/watch?v=YlzvLc5UdXo) and the [Unofficial bittorent spec](https://wiki.theory.org/BitTorrentSpecification), so thank you :)