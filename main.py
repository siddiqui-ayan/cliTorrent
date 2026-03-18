import sys
import asyncio
from bt.torrent import Torrent
from bt.tracker import TrackerClient
from bt.downloader import TorrentDownloader
from ui import DownloadUI


async def main(torrent_path):
    torrent = Torrent(torrent_path)
    tracker = TrackerClient(torrent)
    peers = tracker.getPeersFromTracker()

    if not peers:
        print("No peers found from tracker.")
        return

    downloader = TorrentDownloader(torrent, peers, maxPeers=50)
    ui = DownloadUI(downloader)

    download_task = asyncio.create_task(downloader.download())
    ui_task = asyncio.create_task(ui.run())

    success = await download_task
    ui.stop()
    await ui_task

    if success:
        print("Download complete!")
    else:
        print("Download failed or incomplete.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path/to/file.torrent>")
        sys.exit(1)

    try:
        asyncio.run(main(sys.argv[1]))
    except KeyboardInterrupt:
        print("\nDownload interrupted by user.")