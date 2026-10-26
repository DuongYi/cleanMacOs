"""Snappy, lightweight, lag-free interactive dashboard using Rich & Questionary."""

from pathlib import Path
from typing import List, Optional

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from mclean.models import CleanTarget
from mclean.scanners.ai_python import AiPythonScanner
from mclean.scanners.android_java import AndroidJavaScanner
from mclean.scanners.apple_xcode import AppleXcodeScanner
from mclean.scanners.flutter_dart import FlutterDartScanner
from mclean.scanners.installer import scan_installers
from mclean.scanners.optimizer import run_all_optimizations
from mclean.scanners.system_junk import SystemJunkScanner
from mclean.utils.disk import get_disk_space, safe_delete_path
from mclean.utils.formatters import format_size
from mclean.utils.guard import get_active_dev_processes

console = Console()


def print_header():
    """Print the storage banner and active process warnings."""
    total, used, free = get_disk_space()
    free_pct = (free / total) * 100
    used_pct = (used / total) * 100
    color = "green" if free_pct > 20 else "yellow" if free_pct > 10 else "red"

    console.print()
    console.print(
        Panel(
            f"Ổ đĩa macOS: [bold]{format_size(used)}[/bold] đã dùng ({used_pct:.1f}%) | "
            f"Còn trống: [bold {color}]{format_size(free)}[/bold {color}] ({free_pct:.1f}%) | "
            f"Tổng: [bold]{format_size(total)}[/bold]",
            title="💾 [bold cyan]mclean - macOS Storage Status[/bold cyan]",
            border_style="cyan",
        )
    )

    active_procs = get_active_dev_processes()
    if active_procs:
        names = ", ".join(f"[bold yellow]{n}[/bold yellow] (PID {p})" for n, p in active_procs)
        console.print(
            f"⚠️  [dim yellow]Phát hiện tiến trình đang chạy:[/dim yellow] {names}\n"
            f"[dim]    (mclean sẽ tự động bảo vệ các cache liên quan để không làm gián đoạn ứng dụng)[/dim]\n"
        )


def scan_with_live_progress() -> List[CleanTarget]:
    """Execute scanners with real-time animated progress bars."""
    scanners = [
        ("Xcode & iOS Simulators", AppleXcodeScanner()),
        ("Android SDK & Gradle Caches", AndroidJavaScanner()),
        ("Flutter Projects Cũ (>14 ngày)", FlutterDartScanner()),
        ("AI Models & Python Caches", AiPythonScanner()),
        ("System Junk & Package Managers", SystemJunkScanner()),
    ]

    all_targets: List[CleanTarget] = []

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        TextColumn("[bold yellow]{task.fields[found_size]}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        overall_task = progress.add_task("[bold white]Tổng quan quét hệ thống[/bold white]", total=len(scanners), found_size="")

        for name, sc in scanners:
            sub_task = progress.add_task(f"  • Quét {name}...", total=100, found_size="Đang tính...")
            try:
                targets = sc.scan()
                all_targets.extend(targets)
                cat_size = sum(t.size_bytes for t in targets)
                progress.update(sub_task, completed=100, found_size=format_size(cat_size))
            except Exception as e:
                progress.update(sub_task, completed=100, found_size=f"[red]Lỗi[/red]")
            progress.advance(overall_task)

    all_targets.sort(key=lambda t: t.size_bytes, reverse=True)
    return all_targets


def display_summary_table(targets: List[CleanTarget]):
    """Render the clean targets summary table."""
    table = Table(
        title="📊 Danh Sách Bộ Nhớ Đệm & File Rác Phát Hiện Được",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Phân loại", style="cyan", no_wrap=True)
    table.add_column("Tên mục tiêu", style="white")
    table.add_column("Dung lượng", justify="right", style="bold yellow", no_wrap=True)
    table.add_column("Mức độ", justify="center", no_wrap=True)
    table.add_column("Mô tả / Tác động", style="dim")

    total_safe = 0
    total_review = 0

    for t in targets:
        if t.is_safe:
            total_safe += t.size_bytes
            badge = "[bold green]SAFE[/bold green]"
        else:
            total_review += t.size_bytes
            badge = "[bold yellow]REVIEW[/bold yellow]"

        table.add_row(
            t.category.value,
            t.name,
            format_size(t.size_bytes),
            badge,
            t.description,
        )

    console.print(table)
    console.print()
    console.print(
        f"🟢 [bold green]Tier 1 (SAFE): {format_size(total_safe)}[/bold green] "
        f"— 100% An toàn, dọn xong [bold underline]KHÔNG BAO GIỜ phải tải lại dữ liệu[/bold underline]."
    )
    console.print(
        f"🟡 [bold yellow]Tier 2 (REVIEW): {format_size(total_review)}[/bold yellow] "
        f"— Model AI, máy ảo cũ (chọn lọc từng mục trước khi xoá)."
    )
    console.print()


def clean_targets_with_progress(targets_to_clean: List[CleanTarget]) -> int:
    """Clean targets with live progress bar."""
    if not targets_to_clean:
        console.print("[yellow]Không có mục nào được chọn để dọn.[/yellow]")
        return 0

    total_bytes = sum(t.size_bytes for t in targets_to_clean)
    console.print(f"\n[bold green]🚀 Bắt đầu dọn {len(targets_to_clean)} mục ({format_size(total_bytes)})...[/bold green]")

    reclaimed = 0
    cleaner = AppleXcodeScanner()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Đang dọn dẹp...", total=len(targets_to_clean))

        for t in targets_to_clean:
            progress.update(task, description=f"Đang dọn: [white]{t.name}[/white]")
            ok, _ = cleaner.clean(t, dry_run=False)
            if ok:
                reclaimed += t.size_bytes
            progress.advance(task)

    console.print(f"\n[bold green]🎉 Hoàn tất![/bold green] Đã giải phóng thành công: [bold green]{format_size(reclaimed)}[/bold green]\n")
    print_header()
    return reclaimed


def interactive_dashboard_menu():
    """Main interactive dashboard loop inspired by tw93/Mole."""
    print_header()

    console.print("[bold cyan]🔍 Đang quét toàn bộ hệ thống với thanh tiến trình trực quan...[/bold cyan]\n")
    targets = scan_with_live_progress()
    console.print()
    display_summary_table(targets)

    while True:
        choice = questionary.select(
            "Chọn thao tác bạn muốn thực hiện (Dùng phím mũi tên ↑/↓ và bấm Enter):",
            choices=[
                "1. 🧹 Dọn nhanh toàn bộ mục SAFE (Không bao giờ phải tải lại dữ liệu)",
                "2. 🎯 Chọn lọc từng mục (Duyệt chi tiết Model AI, Simulators, AVD)",
                "3. 🚀 Tối ưu hệ thống (Làm mới DNS, QuickLook, chặn rác .DS_Store)",
                "4. 📦 Dọn tệp cài đặt & mobile builds trong Downloads",
                "5. 🔍 Quét lại hệ thống",
                "6. ❌ Thoát",
            ],
        ).ask()

        if not choice or "6. ❌ Thoát" in choice:
            console.print("[dim]Tạm biệt![/dim]")
            break

        if "1. 🧹 Dọn nhanh" in choice:
            safe_targets = [t for t in targets if t.is_safe]
            if not safe_targets:
                console.print("[yellow]Không còn mục SAFE nào cần dọn![/yellow]")
            else:
                total_safe = sum(t.size_bytes for t in safe_targets)
                if questionary.confirm(f"Bạn có chắc muốn dọn {len(safe_targets)} mục SAFE ({format_size(total_safe)})?", default=True).ask():
                    clean_targets_with_progress(safe_targets)
                    targets = scan_with_live_progress()

        elif "2. 🎯 Chọn lọc" in choice:
            choices = []
            for t in targets:
                tier_label = "[SAFE]" if t.is_safe else "[REVIEW]"
                label = f"{tier_label} {t.name} ({format_size(t.size_bytes)}) - {t.description}"
                choices.append(questionary.Choice(title=label, value=t, checked=t.is_safe))

            selected = questionary.checkbox(
                "Dùng phím mũi tên và phím SPACE để chọn/bỏ chọn, Enter để dọn:",
                choices=choices,
            ).ask()

            if selected:
                total_sel = sum(t.size_bytes for t in selected)
                if questionary.confirm(f"Tiến hành dọn {len(selected)} mục đã chọn ({format_size(total_sel)})?", default=True).ask():
                    clean_targets_with_progress(selected)
                    targets = scan_with_live_progress()

        elif "3. 🚀 Tối ưu" in choice:
            console.print("\n[bold cyan]🚀 Đang thực hiện các tác vụ tối ưu hệ thống macOS...[/bold cyan]")
            results = run_all_optimizations()
            table = Table(title="Kết Quả Tối Ưu Hệ Thống", show_header=True)
            table.add_column("Tác vụ tối ưu", style="white")
            table.add_column("Trạng thái", justify="center")
            table.add_column("Chi tiết", style="dim")
            for title, ok, msg in results:
                status_badge = "[bold green]THÀNH CÔNG[/bold green]" if ok else "[bold red]THẤT BẠI[/bold red]"
                table.add_row(title, status_badge, msg)
            console.print(table)
            console.print()

        elif "4. 📦 Dọn tệp cài đặt" in choice:
            installer_targets = scan_installers(older_than_days=7)
            if not installer_targets:
                console.print("[green]✨ Không có tệp cài đặt nào tồn đọng trong Downloads![/green]")
            else:
                table = Table(title="Tệp Cài Đặt & Mobile Builds Tìm Thấy")
                table.add_column("Tên tệp", style="white")
                table.add_column("Dung lượng", style="bold yellow", justify="right")
                table.add_column("Mức độ", justify="center")
                for t in installer_targets:
                    table.add_row(t.name, format_size(t.size_bytes), "[green]SAFE[/green]" if t.is_safe else "[yellow]REVIEW[/yellow]")
                console.print(table)

                total_ins = sum(t.size_bytes for t in installer_targets)
                if questionary.confirm(f"Dọn {len(installer_targets)} tệp cài đặt ({format_size(total_ins)})?", default=True).ask():
                    cleaned = 0
                    for t in installer_targets:
                        ok, _ = safe_delete_path(t.path)
                        if ok:
                            cleaned += t.size_bytes
                    console.print(f"[bold green]🎉 Đã giải phóng: {format_size(cleaned)}[/bold green]\n")

        elif "5. 🔍 Quét lại" in choice:
            console.print("\n[bold cyan]🔍 Đang quét lại hệ thống...[/bold cyan]\n")
            targets = scan_with_live_progress()
            console.print()
            display_summary_table(targets)
