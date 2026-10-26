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

from mclean.cleaner import execute_clean, split_by_running_apps
from mclean.cli import build_target_choices, print_blocked, remove_user_files, select_installers
from mclean.models import CleanTarget
from mclean.scanners.ai_python import AiPythonScanner
from mclean.scanners.android_java import AndroidJavaScanner
from mclean.scanners.apple_xcode import AppleXcodeScanner
from mclean.scanners.browsers import BrowserScanner
from mclean.scanners.docker import DockerScanner, run_docker_prune
from mclean.scanners.flutter_dart import FlutterDartScanner
from mclean.scanners.installer import scan_installers
from mclean.scanners.large_files import find_large_files, reveal_in_finder
from mclean.scanners.optimizer import run_all_optimizations
from mclean.scanners.project_deps import ProjectDepsScanner
from mclean.scanners.system_junk import SystemJunkScanner
from mclean.utils.disk import get_disk_space
from mclean.utils.formatters import format_size, format_timestamp
from mclean.utils.guard import get_active_dev_processes
from mclean.utils.history import (
    get_total_lifetime_savings,
    load_history,
)
from mclean.utils.scheduler import (
    get_disk_alert_status,
    get_schedule_status,
    install_disk_alert,
    install_schedule,
    remove_disk_alert,
    remove_schedule,
)

console = Console()


def print_header():
    """Print the storage banner and active process warnings."""
    total, used, free = get_disk_space()
    free_pct = (free / total) * 100
    used_pct = (used / total) * 100
    color = "green" if free_pct > 20 else "yellow" if free_pct > 10 else "red"

    total_lifetime = get_total_lifetime_savings()

    console.print()
    console.print(
        Panel(
            f"Ổ đĩa macOS: [bold]{format_size(used)}[/bold] đã dùng ({used_pct:.1f}%) | "
            f"Còn trống: [bold {color}]{format_size(free)}[/bold {color}] ({free_pct:.1f}%) | "
            f"Tổng: [bold]{format_size(total)}[/bold]\n"
            f"🏆 [dim]Tổng dung lượng mclean đã tiết kiệm cho bạn: [/dim][bold green]{format_size(total_lifetime)}[/bold green]",
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
        ("node_modules & Pods của dự án cũ", ProjectDepsScanner()),
        ("AI Models & Python Caches", AiPythonScanner()),
        ("Docker & Container Files", DockerScanner()),
        ("System Junk & Package Managers", SystemJunkScanner()),
        ("Cache trình duyệt", BrowserScanner()),
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
            except Exception:
                progress.update(sub_task, completed=100, found_size="0 B")
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
        f"— Chỉ gồm dữ liệu tự tạo lại tại máy hoặc không dự án nào dùng: dọn xong [bold underline]không phải tải lại[/bold underline]."
    )
    console.print(
        f"🟡 [bold yellow]Tier 2 (REVIEW): {format_size(total_review)}[/bold yellow] "
        f"— Model AI, máy ảo, cache tải về: xoá thì lần sau phải tải lại (chọn lọc từng mục)."
    )
    console.print()


def clean_targets_with_progress(targets_to_clean: List[CleanTarget]) -> int:
    """Clean targets with live progress bar, skipping anything an open app is using."""
    targets_to_clean, blocked = split_by_running_apps(targets_to_clean)
    if blocked:
        print_blocked(blocked)
    if not targets_to_clean:
        console.print("[yellow]Không có mục nào dọn được lúc này.[/yellow]")
        return 0

    total_bytes = sum(t.size_bytes for t in targets_to_clean)
    console.print(f"\n[bold green]🚀 Bắt đầu dọn {len(targets_to_clean)} mục ({format_size(total_bytes)})...[/bold green]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Đang dọn dẹp...", total=len(targets_to_clean))

        started: List[CleanTarget] = []

        def on_start(t: CleanTarget) -> None:
            if started:
                progress.advance(task)
            started.append(t)
            progress.update(task, description=f"Đang dọn: [white]{t.name}[/white]")

        report = execute_clean(targets_to_clean, on_start=on_start)
        progress.update(task, completed=len(targets_to_clean))

    for t, msg in report.failed:
        console.print(f"[red]✗ {t.name}: {msg}[/red]")
    console.print(f"\n[bold green]🎉 Hoàn tất![/bold green] Đã giải phóng thực tế: [bold green]{format_size(report.reclaimed)}[/bold green]\n")
    print_header()
    return report.reclaimed


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
                "1. 🧹 Dọn nhanh toàn bộ mục SAFE (không phải tải lại, bỏ qua mục ứng dụng đang dùng)",
                "2. 🎯 Chọn lọc từng mục (Duyệt chi tiết Model AI, Simulators, AVD)",
                "3. 🚀 Tối ưu hệ thống (Làm mới DNS, QuickLook, chặn rác .DS_Store)",
                "4. 📦 Dọn tệp cài đặt & mobile builds trong Downloads",
                "5. 🐘 Quét tệp siêu lớn (> 500 MB)",
                "6. 🐳 Dọn dẹp Docker & Container",
                "7. 📜 Xem nhật ký dọn dẹp & Tổng dung lượng tiết kiệm",
                "8. ⏱️ Cài đặt lịch dọn tự động & cảnh báo ổ đầy",
                "9. 🔍 Quét lại hệ thống",
                "10. 🩺 Kiểm tra sức khoẻ (doctor)",
                "11. ❌ Thoát",
            ],
        ).ask()

        if not choice or "11. ❌ Thoát" in choice:
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
            selected = questionary.checkbox(
                "↑/↓ di chuyển · SPACE chọn/bỏ · Enter dọn. SAFE được chọn sẵn, REVIEW thì bạn tự chọn:",
                choices=build_target_choices(targets),
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

                selected = select_installers(installer_targets)
                if selected:
                    remove_user_files([(t.path, t.size_bytes) for t in selected])

        elif "5. 🐘 Quét tệp siêu lớn" in choice:
            console.print("\n[bold cyan]🔍 Đang quét các tệp >= 500 MB trong thư mục của bạn...[/bold cyan]")
            items = find_large_files(root=Path.home(), min_size_mb=500, max_results=20)
            if not items:
                console.print("[green]✨ Không có tệp nào lớn hơn 500 MB.[/green]\n")
            else:
                table = Table(title="Top Tệp Siêu Nặng Tìm Thấy")
                table.add_column("Phân loại", style="cyan")
                table.add_column("Tên tệp", style="white")
                table.add_column("Dung lượng", style="bold yellow", justify="right")
                table.add_column("Ngày sửa đổi", style="dim")
                for it in items:
                    table.add_row(it.file_type, it.path.name, format_size(it.size_bytes), format_timestamp(it.mtime))
                console.print(table)

                chosen_file = questionary.select(
                    "Chọn tệp để thao tác (hoặc bỏ qua):",
                    choices=[questionary.Choice(title=f"{it.path.name} ({format_size(it.size_bytes)})", value=it) for it in items] + [questionary.Choice(title="❌ Bỏ qua", value=None)],
                ).ask()

                if chosen_file:
                    act = questionary.select(
                        f"Thao tác cho {chosen_file.path.name}:",
                        choices=["1. 📂 Mở vị trí tệp trong Finder", "2. 🗑️ Dọn tệp này", "3. ❌ Huỷ"],
                    ).ask()
                    if not act:
                        continue
                    if "1. 📂 Mở" in act:
                        reveal_in_finder(chosen_file.path)
                    elif "2. 🗑️ Dọn" in act:
                        remove_user_files([(chosen_file.path, chosen_file.size_bytes)])

        elif "6. 🐳 Dọn dẹp Docker" in choice:
            scanner = DockerScanner()
            if not scanner.is_docker_running():
                console.print("[yellow]Docker daemon hiện đang tắt.[/yellow]\n")
            else:
                if questionary.confirm("Dọn dangling images và build cache không dùng > 30 ngày?", default=True).ask():
                    ok, output = run_docker_prune()
                    console.print(Panel(output, title="Docker Prune Result", border_style="green" if ok else "red"))

        elif "7. 📜 Xem nhật ký" in choice:
            records = load_history()
            total_lt = get_total_lifetime_savings()
            console.print(Panel(f"🏆 Tổng dung lượng đã tiết kiệm: [bold green]{format_size(total_lt)}[/bold green]\nSố lần dọn: {len(records)} lần", border_style="green"))
            if records:
                table = Table(title="Lịch Sử Dọn Dẹp Gần Đây")
                table.add_column("Thời gian", style="cyan")
                table.add_column("Giải phóng", style="bold green", justify="right")
                table.add_column("Số mục", justify="center")
                table.add_column("Chi tiết", style="dim")
                for r in reversed(records[-10:]):
                    table.add_row(r.get("timestamp", "")[:19].replace("T", " "), format_size(r.get("reclaimed_bytes", 0)), str(r.get("items_count", 0)), ", ".join(r.get("items", [])[:4]))
                console.print(table)
            console.print()

        elif "8. ⏱️ Cài đặt lịch" in choice:
            weekly, alert = get_schedule_status(), get_disk_alert_status()
            console.print(f"Dọn hàng tuần: [bold cyan]{weekly['installed']}[/bold cyan] · Cảnh báo ổ đầy: [bold cyan]{alert['installed']}[/bold cyan]")
            sched_act = questionary.select(
                "Tuỳ chọn tác vụ chạy ngầm:",
                choices=[
                    "1. ✅ Bật dọn SAFE tự động mỗi sáng Thứ Hai",
                    "2. ❌ Tắt dọn tự động",
                    "3. 📉 Bật cảnh báo ổ đầy (chỉ báo, không xoá)",
                    "4. 🔕 Tắt cảnh báo ổ đầy",
                    "5. ↩️ Quay lại",
                ],
            ).ask()
            if not sched_act or "5. ↩️" in sched_act:
                continue
            action = {
                "1.": lambda: install_schedule(weekday=1, hour=9, minute=0),
                "2.": remove_schedule,
                "3.": install_disk_alert,
                "4.": remove_disk_alert,
            }[sched_act[:2]]
            ok, msg = action()
            console.print(f"[bold green]{msg}[/bold green]\n" if ok else f"[bold red]{msg}[/bold red]\n")

        elif "10. 🩺 Kiểm tra" in choice:
            from mclean.cli import doctor
            doctor()
            console.print()

        elif "9. 🔍 Quét lại" in choice:
            console.print("\n[bold cyan]🔍 Đang quét lại hệ thống...[/bold cyan]\n")
            targets = scan_with_live_progress()
            console.print()
            display_summary_table(targets)
