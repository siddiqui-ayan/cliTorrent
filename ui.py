
# I vibe coded the UI cause I hate the working on frontend T_T
import os
import asyncio
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.table import Table
from rich.console import Console


class DownloadUI:
    def __init__(self, downloader):
        self.downloader = downloader
        self._running = False
        self.console = Console()

    @staticmethod
    def _format_bytes(b):
        for unit in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return f"{b:.1f} {unit}"
            b /= 1024
        return f"{b:.1f} TB"

    def _format_speed(self, bps):
        return self._format_bytes(bps) + "/s"

    def _get_filename(self):
        files = self.downloader.torrent.filesNames
        if files:
            path = files[0]["path"]
            if isinstance(path, bytes):
                path = path.decode("utf-8", errors="replace")
            return os.path.basename(str(path))
        return "unknown"

    def _build_status_panel(self):
        dl = self.downloader
        progress_pct = dl.progress * 100

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold cyan", width=14)
        table.add_column()

        table.add_row("Downloading", self._get_filename())

        bar_width = 40
        filled = int(bar_width * dl.progress)
        bar = "█" * filled + "░" * (bar_width - filled)
        table.add_row("Progress", f"{bar}  {progress_pct:.0f}%")

        table.add_row("Peers", f"{len(dl.connectedPeers)} connected")
        table.add_row("Speed", self._format_speed(dl.downloadSpeed))

        dl_bytes = dl.downloadedBytes
        total_bytes = dl.totalLength
        table.add_row(
            "Downloaded",
            f"{self._format_bytes(dl_bytes)} / {self._format_bytes(total_bytes)}",
        )

        return Panel(table, title="Download", border_style="blue")

    def _build_log_panel(self):
        logs = list(self.downloader.logs)
        recent = logs[-20:]
        log_text = Text()
        for line in recent:
            if line.startswith("✓"):
                log_text.append(line + "\n", style="green")
            elif (
                line.startswith("✗")
                or "error" in line.lower()
                or "fail" in line.lower()
            ):
                log_text.append(line + "\n", style="red")
            else:
                log_text.append(line + "\n", style="dim")

        return Panel(log_text, title="Log", border_style="dim")

    def _build_display(self):
        layout = Layout()
        layout.split_column(
            Layout(name="status", size=9),
            Layout(name="logs"),
        )
        layout["status"].update(self._build_status_panel())
        layout["logs"].update(self._build_log_panel())
        return layout

    async def run(self):
        self._running = True
        with Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=2,
            screen=False,
        ) as live:
            while self._running:
                self.downloader.sampleProgress()
                live.update(self._build_display())
                await asyncio.sleep(0.5)

    def stop(self):
        self._running = False
