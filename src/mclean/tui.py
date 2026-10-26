"""Full-featured Terminal User Interface (TUI) Dashboard for mclean using Textual."""

from typing import List, Set
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    ProgressBar,
    Static,
)

from mclean.cli import run_all_scanners
from mclean.models import CleanTarget
from mclean.scanners.apple_xcode import AppleXcodeScanner
from mclean.utils.disk import get_disk_space
from mclean.utils.formatters import format_size


class StorageWidget(Static):
    """Storage overview widget displaying current macOS disk space."""

    def compose(self) -> ComposeResult:
        total, used, free = get_disk_space()
        free_pct = (free / total) * 100
        used_pct = (used / total) * 100

        yield Label("💾 [bold cyan]Ổ ĐĨA HỆ THỐNG MAC[/bold cyan]")
        yield Label(f"Đã dùng: [bold yellow]{format_size(used)}[/bold yellow] ({used_pct:.1f}%)", id="lbl_used")
        yield Label(f"Còn trống: [bold green]{format_size(free)}[/bold green] ({free_pct:.1f}%)", id="lbl_free")
        yield Label(f"Tổng dung lượng: {format_size(total)}", id="lbl_total")
        yield ProgressBar(total=100, show_eta=False, id="disk_progress")

    def on_mount(self) -> None:
        self.refresh_stats()

    def refresh_stats(self) -> None:
        total, used, free = get_disk_space()
        free_pct = (free / total) * 100
        used_pct = (used / total) * 100

        self.query_one("#lbl_used", Label).update(f"Đã dùng: [bold yellow]{format_size(used)}[/bold yellow] ({used_pct:.1f}%)")
        self.query_one("#lbl_free", Label).update(f"Còn trống: [bold green]{format_size(free)}[/bold green] ({free_pct:.1f}%)")
        self.query_one("#disk_progress", ProgressBar).progress = used_pct


class McleanTuiApp(App):
    """Interactive Textual Dashboard for mclean."""

    CSS = """
    Screen {
        background: #121317;
        color: #e1e4ea;
    }
    Header {
        background: #1e293b;
        color: #38bdf8;
    }
    Footer {
        background: #1e293b;
    }
    #sidebar {
        width: 32;
        background: #181b22;
        padding: 1 2;
        border-right: solid #334155;
    }
    #main_content {
        padding: 1;
    }
    #action_bar {
        height: 3;
        margin-top: 1;
        align: right middle;
    }
    DataTable {
        height: 1fr;
        border: solid #334155;
    }
    Button {
        width: 100%;
        margin-bottom: 1;
    }
    .btn-clean {
        background: #16a34a;
        color: white;
    }
    .btn-scan {
        background: #0284c7;
        color: white;
    }
    .btn-select {
        background: #334155;
        color: white;
    }
    #summary_label {
        color: #38bdf8;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("s", "scan", "Quét lại"),
        ("c", "clean", "Dọn mục đã chọn"),
        ("a", "toggle_all", "Chọn all SAFE"),
        ("q", "quit", "Thoát"),
    ]

    def __init__(self):
        super().__init__()
        self.targets: List[CleanTarget] = []
        self.selected_indices: Set[int] = set()
        self.is_scanning = False
        self.is_cleaning = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar"):
                yield StorageWidget(id="storage_box")
                yield Label("\n[bold cyan]⚡ THAO TÁC NHANH[/bold cyan]")
                yield Button("🔍 Quét lại [S]", id="btn_scan", classes="btn-scan")
                yield Button("✅ Chọn all SAFE [A]", id="btn_select_all", classes="btn-select")
                yield Button("🧹 Dọn dẹp [C]", id="btn_clean", classes="btn-clean")
                yield Label("\n[dim]• Click hoặc Space: Chọn\n• S: Quét lại\n• C: Dọn dẹp\n• Q: Thoát[/dim]")
            with Vertical(id="main_content"):
                yield Label("[bold white]📊 DANH SÁCH BỘ NHỚ ĐỆM & FILE RÁC PHÁT HIỆN ĐƯỢC[/bold white]")
                yield DataTable(id="clean_table", cursor_type="row")
                with Horizontal(id="action_bar"):
                    yield Label("Đang khởi tạo...", id="summary_label")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Chọn", "Phân loại", "Tên mục tiêu", "Dung lượng", "Mức độ", "Mô tả / Tác động")
        # Trigger asynchronous background scan so UI renders immediately without freeze
        self.action_scan()

    def action_scan(self) -> None:
        """Trigger scan asynchronously in a background thread."""
        if self.is_scanning or self.is_cleaning:
            return

        self.is_scanning = True
        table = self.query_one(DataTable)
        table.loading = True
        summary = self.query_one("#summary_label", Label)
        summary.update("[bold yellow]⏳ Đang quét toàn bộ hệ thống trong nền... Vui lòng đợi trong giây lát.[/bold yellow]")

        self._scan_worker()

    @work(thread=True)
    def _scan_worker(self) -> None:
        """Background thread worker for disk scanning."""
        targets = run_all_scanners()
        self.call_from_thread(self._on_scan_completed, targets)

    def _on_scan_completed(self, targets: List[CleanTarget]) -> None:
        """Update UI with scan results on main thread."""
        self.targets = targets
        # Select all Tier 1 SAFE targets by default
        self.selected_indices = {i for i, t in enumerate(self.targets) if t.is_safe}
        self.is_scanning = False

        table = self.query_one(DataTable)
        table.loading = False
        self.refresh_table()

        total_safe = sum(t.size_bytes for t in self.targets if t.is_safe)
        self.notify(f"Quét xong! Tìm thấy {len(self.targets)} mục (SAFE: {format_size(total_safe)}).", title="mclean scan")

    def refresh_table(self) -> None:
        """Re-render table rows."""
        table = self.query_one(DataTable)
        table.clear()

        total_selected_size = 0
        for i, t in enumerate(self.targets):
            is_checked = i in self.selected_indices
            check_box = " [bold green]●[/bold green] " if is_checked else " [dim]○[/dim] "
            tier_badge = "[bold green]SAFE[/bold green]" if t.is_safe else "[bold yellow]REVIEW[/bold yellow]"

            if is_checked:
                total_selected_size += t.size_bytes

            table.add_row(
                check_box,
                t.category.value,
                t.name,
                format_size(t.size_bytes),
                tier_badge,
                t.description,
                key=str(i),
            )

        summary = self.query_one("#summary_label", Label)
        summary.update(
            f"Đã chọn: [bold green]{len(self.selected_indices)}[/bold green] mục "
            f"([bold yellow]{format_size(total_selected_size)}[/bold yellow]) | "
            f"Nhấn [bold cyan]C[/bold cyan] để dọn dẹp"
        )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Toggle row selection when clicked or Space/Enter pressed."""
        if self.is_scanning or self.is_cleaning:
            return

        row_key = event.row_key.value
        if row_key is not None:
            idx = int(row_key)
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
            else:
                self.selected_indices.add(idx)
            self.refresh_table()

    def action_toggle_all(self) -> None:
        """Toggle all safe targets."""
        if self.is_scanning or self.is_cleaning:
            return

        safe_indices = {i for i, t in enumerate(self.targets) if t.is_safe}
        if self.selected_indices == safe_indices:
            self.selected_indices.clear()
        else:
            self.selected_indices = safe_indices
        self.refresh_table()

    def action_clean(self) -> None:
        """Clean selected targets asynchronously in a background thread."""
        if self.is_scanning or self.is_cleaning:
            return

        if not self.selected_indices:
            self.notify("Chưa có mục nào được chọn để dọn dẹp!", severity="warning")
            return

        self.is_cleaning = True
        table = self.query_one(DataTable)
        table.loading = True

        targets_to_clean = [self.targets[i] for i in sorted(self.selected_indices)]
        summary = self.query_one("#summary_label", Label)
        summary.update(f"[bold yellow]🧹 Đang dọn {len(targets_to_clean)} mục trong nền...[/bold yellow]")

        self._clean_worker(targets_to_clean)

    @work(thread=True)
    def _clean_worker(self, targets_to_clean: List[CleanTarget]) -> None:
        """Background thread worker for cleaning files."""
        reclaimed = 0
        cleaner = AppleXcodeScanner()
        for t in targets_to_clean:
            ok, _ = cleaner.clean(t, dry_run=False)
            if ok:
                reclaimed += t.size_bytes

        self.call_from_thread(self._on_clean_completed, reclaimed)

    def _on_clean_completed(self, reclaimed: int) -> None:
        """Handle clean completion on main thread."""
        self.is_cleaning = False
        table = self.query_one(DataTable)
        table.loading = False

        self.notify(f"🎉 Đã giải phóng thành công: {format_size(reclaimed)}!", severity="information")

        # Update storage widget
        storage_box = self.query_one("#storage_box", StorageWidget)
        storage_box.refresh_stats()

        # Rescan to reflect updated state
        self.action_scan()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_scan":
            self.action_scan()
        elif event.button.id == "btn_select_all":
            self.action_toggle_all()
        elif event.button.id == "btn_clean":
            self.action_clean()


def launch_dashboard():
    """Launch the interactive Textual TUI dashboard."""
    app = McleanTuiApp()
    app.run()
