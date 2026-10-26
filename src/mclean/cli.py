"""mclean: macOS Developer & AI Precision Cleaner CLI Interface."""

import json
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from mclean.cleaner import execute_clean, split_by_running_apps
from mclean.config import (
    DEFAULT_INACTIVE_DAYS,
    DEFAULT_PROJECT_ROOTS,
    load_ignored_paths,
    save_ignored_paths,
)
from mclean.models import Category, CleanTarget, RiskTier
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
from mclean.utils.disk import get_disk_space, get_path_size, move_to_trash, safe_delete_path
from mclean.utils.formatters import format_size, format_timestamp
from mclean.utils.guard import get_active_dev_processes
from mclean.utils.history import (
    clear_history,
    get_total_lifetime_savings,
    load_history,
    record_cleanup,
)
from mclean.utils.scheduler import (
    get_schedule_status,
    install_schedule,
    remove_schedule,
)

app = typer.Typer(
    name="mclean",
    help="⚡ Precision macOS cleaner for Flutter, AI, and Mobile Developers.",
    add_completion=False,
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def default_entry(ctx: typer.Context):
    """Khi chỉ gõ `mclean` không kèm lệnh, tự động mở Dashboard tương tác mượt mà!"""
    if ctx.invoked_subcommand is None:
        from mclean.dashboard import interactive_dashboard_menu
        interactive_dashboard_menu()
        raise typer.Exit()


def run_all_scanners(workspace_roots: Optional[List[Path]] = None) -> List[CleanTarget]:
    """Execute all scanners concurrently and collect clean targets."""
    scanners = [
        AppleXcodeScanner(),
        AndroidJavaScanner(),
        FlutterDartScanner(workspace_roots=workspace_roots),
        ProjectDepsScanner(workspace_roots=workspace_roots),
        AiPythonScanner(),
        DockerScanner(),
        SystemJunkScanner(),
        BrowserScanner(),
    ]

    all_targets: List[CleanTarget] = []
    for sc in scanners:
        try:
            all_targets.extend(sc.scan())
        except Exception as e:
            console.print(f"[dim red]Error in scanner {sc.name}: {e}[/dim red]")

    # Sort descending by size
    all_targets.sort(key=lambda t: t.size_bytes, reverse=True)
    return all_targets


def print_disk_banner():
    """Print current disk capacity banner."""
    total, used, free = get_disk_space()
    free_pct = (free / total) * 100
    used_pct = (used / total) * 100

    color = "green" if free_pct > 20 else "yellow" if free_pct > 10 else "red"
    console.print(
        Panel(
            f"Ổ đĩa macOS: [bold]{format_size(used)}[/bold] đã dùng ({used_pct:.1f}%) | "
            f"Còn trống: [bold {color}]{format_size(free)}[/bold {color}] ({free_pct:.1f}%) | "
            f"Tổng: [bold]{format_size(total)}[/bold]",
            title="💾 [bold cyan]mclean - macOS Storage Status[/bold cyan]",
            border_style="cyan",
        )
    )


def print_active_process_warning():
    """Display warning if active IDEs or build daemons are currently running."""
    active_procs = get_active_dev_processes()
    if active_procs:
        names = ", ".join(f"[bold yellow]{n}[/bold yellow] (PID {p})" for n, p in active_procs)
        console.print(
            f"[dim yellow]⚠️  Phát hiện tiến trình đang chạy:[/dim yellow] {names}\n"
            f"[dim]    (mclean sẽ tự động bảo vệ các cache liên quan để không gây lỗi phần mềm đang mở)[/dim]\n"
        )


@app.command()
def scan(
    workspace: Optional[str] = typer.Option(
        None, "--workspace", "-w", help="Thư mục chứa dự án để quét sâu (mặc định: ~/Projects, ~/Code, v.v.)"
    ),
):
    """🔍 Quét toàn bộ hệ thống và hiển thị bảng phân tích dung lượng rác."""
    print_disk_banner()
    print_active_process_warning()

    roots = [Path(workspace).expanduser().resolve()] if workspace else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(description="Đang quét bộ nhớ đệm Xcode, Android, Flutter, AI và System...", total=None)
        targets = run_all_scanners(workspace_roots=roots)

    if not targets:
        console.print("[green]✨ Hệ thống của bạn hoàn toàn sạch sẽ, không tìm thấy file rác nào![/green]")
        return

    table = Table(title="📊 Danh Sách Bộ Nhớ Đệm & File Rác Có Thể Dọn Dẹp", show_header=True, header_style="bold magenta")
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
        f"— Model AI, máy ảo, cache tải về: xoá thì lần sau phải tải lại (dùng [bold cyan]mclean interactive[/bold cyan] để chọn từng mục)."
    )
    console.print("\n💡 Gõ [bold cyan]mclean clean[/bold cyan] để dọn ngay các mục SAFE.")


CATEGORY_KEYS = {
    "xcode": Category.XCODE,
    "android": Category.ANDROID,
    "flutter": Category.FLUTTER,
    "ai": Category.AI,
    "dev": Category.DEV,
    "system": Category.SYSTEM,
    "trash": Category.TRASH,
    "browser": Category.BROWSER,
}


def notify_macos(title: str, message: str) -> None:
    """Show a macOS notification (used by the scheduled job)."""
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    subprocess.run(["osascript", "-e", script], capture_output=True, check=False)


def print_blocked(blocked) -> None:
    console.print("\n[bold yellow]⏸  Tạm bỏ qua vì ứng dụng đang dùng:[/bold yellow]")
    for t, conflicts in blocked:
        console.print(f"  • {t.name} [dim]({format_size(t.size_bytes)}) ← {', '.join(conflicts)}[/dim]")
    console.print("[dim]    Đóng các ứng dụng này rồi chạy lại để dọn nốt.[/dim]")


@app.command()
def clean(
    category: Optional[str] = typer.Argument(
        None, help="Phân loại muốn dọn: xcode, android, flutter, ai, dev, system, trash, browser, hoặc bỏ trống để dọn tất cả SAFE"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Chạy giả lập kiểm tra, không xoá file thật"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Bật menu chọn lọc để duyệt từng Model AI và máy ảo"),
    force: bool = typer.Option(False, "--force", "-f", help="Bỏ qua câu hỏi xác nhận (mục đang được ứng dụng dùng vẫn luôn bị bỏ qua)"),
    notify: bool = typer.Option(False, "--notify", help="Gửi thông báo macOS khi xong (dùng cho lịch tự động)"),
):
    """🧹 Dọn dẹp an toàn các vùng nhớ đệm mà không gây vòng lặp tải lại."""
    if category and category.lower() not in CATEGORY_KEYS:
        console.print(f"[red]Không có phân loại '{category}'. Chọn một trong: {', '.join(CATEGORY_KEYS)}[/red]")
        raise typer.Exit(code=2)

    print_disk_banner()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task(description="Đang kiểm tra các mục có thể dọn dẹp...", total=None)
        all_targets = run_all_scanners()

    if category:
        wanted = CATEGORY_KEYS[category.lower()]
        all_targets = [t for t in all_targets if t.category == wanted]

    if not all_targets:
        console.print("[green]✨ Không có mục nào cần dọn dẹp trong danh mục này![/green]")
        return

    # Handle Interactive mode (Questionary)
    if interactive:
        choices = []
        for t in all_targets:
            tier_label = "[SAFE]" if t.is_safe else "[REVIEW]"
            label = f"{tier_label} {t.name} ({format_size(t.size_bytes)}) - {t.description}"
            # Default to checked only for SAFE items
            choices.append(questionary.Choice(title=label, value=t, checked=t.is_safe))

        selected: Optional[List[CleanTarget]] = questionary.checkbox(
            "Dùng phím mũi tên và phím SPACE để chọn/bỏ chọn mục muốn dọn:",
            choices=choices,
        ).ask()

        if not selected:
            console.print("[yellow]Chưa có mục nào được chọn. Đã huỷ thao tác.[/yellow]")
            return

        targets_to_clean = selected
    else:
        # Default mode: Clean only Tier 1 (SAFE) items
        targets_to_clean = [t for t in all_targets if t.is_safe]
        if not targets_to_clean:
            console.print("[yellow]Không có mục SAFE nào cần dọn. (Dùng `mclean clean -i` để chọn các mục REVIEW).[/yellow]")
            return

    # Never delete what an open IDE, emulator or daemon is using
    targets_to_clean, blocked = split_by_running_apps(targets_to_clean)
    if blocked:
        print_blocked(blocked)
    if not targets_to_clean:
        console.print("[yellow]Không còn mục nào dọn được lúc này.[/yellow]")
        if notify:
            notify_macos("mclean Auto-Clean", "Đã bỏ qua: các ứng dụng phát triển đang mở.")
        return

    total_reclaimable = sum(t.size_bytes for t in targets_to_clean)

    if dry_run:
        console.print(f"\n[bold cyan]🧪 CHẾ ĐỘ GIẢ LẬP (DRY-RUN) - Dự kiến giải phóng: {format_size(total_reclaimable)}[/bold cyan]")
        for t in targets_to_clean:
            console.print(f"  • [dim]{t.category.value}:[/dim] {t.name} [yellow]({format_size(t.size_bytes)})[/yellow]")
        return

    # Confirmation
    if not force:
        console.print(f"\nChuẩn bị dọn [bold green]{len(targets_to_clean)} mục[/bold green] — Dự kiến giải phóng: [bold green]{format_size(total_reclaimable)}[/bold green]")
        if not questionary.confirm("Bạn có chắc chắn muốn tiến hành dọn dẹp không?", default=True).ask():
            console.print("[yellow]Đã huỷ dọn dẹp.[/yellow]")
            return

    # Perform cleaning
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task(description="Đang dọn...", total=None)
        report = execute_clean(
            targets_to_clean,
            on_start=lambda t: progress.update(task, description=f"Đang dọn {t.name}..."),
        )

    for t, msg in report.failed:
        console.print(f"[red]✗ {t.name}: {msg}[/red]")
    console.print(f"\n[bold green]🎉 Hoàn tất![/bold green] Đã giải phóng thực tế: [bold green]{format_size(report.reclaimed)}[/bold green]")
    if notify:
        notify_macos("mclean Auto-Clean", f"Đã giải phóng {format_size(report.reclaimed)}, {len(report.failed)} mục lỗi, {len(blocked)} mục bỏ qua.")
    print_disk_banner()


@app.command()
def interactive():
    """🎯 Bật giao diện tương tác Checkbox để chọn dọn từng Model AI, máy ảo, cache."""
    clean(category=None, dry_run=False, interactive=True, force=False)


@app.command()
def purge(
    path: Optional[str] = typer.Argument(
        None, help="Đường dẫn thư mục dự án cần quét (mặc định quét các thư mục Code)"
    ),
    older_than: int = typer.Option(
        DEFAULT_INACTIVE_DAYS, "--older-than", "-d", help="Chỉ dọn dự án không đụng tới hơn số ngày này"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Chạy thử không xoá file thật"),
):
    """🗑️  Quét các dự án lâu không đụng tới: build Flutter (SAFE), node_modules và Pods (bạn chọn)."""
    scan_root = Path(path).expanduser().resolve() if path else Path.home() / "Desktop"
    console.print(f"[bold cyan]🔍 Quét các dự án không hoạt động trong > {older_than} ngày tại: {scan_root}[/bold cyan]")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task("Đang quét dự án...", total=None)
        targets = FlutterDartScanner(workspace_roots=[scan_root], inactive_days=older_than).scan_workspace_for_inactive_projects(scan_root, older_than)
        targets += ProjectDepsScanner(workspace_roots=[scan_root], inactive_days=older_than).scan_root(scan_root)
    targets.sort(key=lambda t: t.size_bytes, reverse=True)

    if not targets:
        console.print("[green]✨ Không tìm thấy dự án cũ nào cần dọn![/green]")
        return

    table = Table(title="Dự Án Không Hoạt Động Có Thể Dọn Dẹp")
    table.add_column("Mục", style="cyan")
    table.add_column("Đường dẫn", style="dim")
    table.add_column("Dung lượng", justify="right", style="bold yellow")
    table.add_column("Mức độ", justify="center")

    for t in targets:
        badge = "[green]SAFE[/green]" if t.is_safe else "[yellow]REVIEW[/yellow]"
        table.add_row(t.name, str(t.metadata.get("project_path", t.path)), format_size(t.size_bytes), badge)

    console.print(table)
    console.print(
        f"\nSAFE (build, không phải tải lại): [bold green]{format_size(sum(t.size_bytes for t in targets if t.is_safe))}[/bold green] | "
        f"REVIEW (node_modules/Pods, cài lại có thể tải): [bold yellow]{format_size(sum(t.size_bytes for t in targets if not t.is_safe))}[/bold yellow]"
    )

    if dry_run:
        console.print("[cyan][Dry-run] Kết thúc quét thử nghiệm.[/cyan]")
        return

    selected = questionary.checkbox(
        "Chọn mục muốn dọn (SPACE để chọn, Enter để xác nhận). Chỉ mục SAFE được chọn sẵn:",
        choices=[
            questionary.Choice(
                title=f"{'[SAFE]' if t.is_safe else '[REVIEW]'} {t.name} ({format_size(t.size_bytes)})",
                value=t,
                checked=t.is_safe,
            )
            for t in targets
        ],
    ).ask()
    if not selected:
        console.print("[yellow]Chưa chọn mục nào. Không xoá gì.[/yellow]")
        return

    report = execute_clean(selected)
    for t, msg in report.failed:
        console.print(f"[red]✗ {t.name}: {msg}[/red]")
    console.print(f"[bold green]🎉 Đã giải phóng: {format_size(report.reclaimed)}[/bold green]")

@app.command()
def analyze(
    path: Optional[str] = typer.Argument(None, help="Đường dẫn thư mục muốn phân tích (mặc định: ~)")
):
    """📊 Phân tích dung lượng các thư mục con theo thứ tự giảm dần (Read-only Explorer)."""
    target_path = Path(path).expanduser().resolve() if path else Path.home()
    console.print(f"[bold cyan]🔍 Đang phân tích dung lượng tại:[/bold cyan] {target_path}\n")

    items = []
    try:
        subdirs = [p for p in target_path.iterdir() if not p.name.startswith(".")]
    except PermissionError:
        console.print("[red]Không có quyền truy cập thư mục này.[/red]")
        return

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Đang đo dung lượng...", total=len(subdirs))
        for p in subdirs:
            size = get_path_size(p)
            items.append((p.name, p.is_dir(), size))
            progress.advance(task)

    items.sort(key=lambda x: x[2], reverse=True)

    table = Table(title=f"Dung lượng chi tiết: {target_path.name}")
    table.add_column("Tên thư mục / File", style="white")
    table.add_column("Loại", style="dim", justify="center")
    table.add_column("Dung lượng", style="bold yellow", justify="right")

    for name, is_dir, sz in items[:25]:
        type_str = "Thư mục" if is_dir else "Tệp"
        table.add_row(name, type_str, format_size(sz))

    console.print(table)


@app.command()
def ignore(
    action: str = typer.Argument("list", help="Hành động: list, add [path], remove [path]"),
    target_path: Optional[str] = typer.Argument(None, help="Đường dẫn cần thêm hoặc bớt"),
):
    """🛡️  Quản lý danh sách các thư mục an toàn không bao giờ bị đụng tới."""
    ignored = load_ignored_paths()

    if action == "list":
        if not ignored:
            console.print("[dim]Danh sách bảo vệ riêng đang trống. (Hệ thống luôn tự động bảo vệ các đường dẫn cốt lõi).[/dim]")
        else:
            console.print("[bold cyan]Danh sách các đường dẫn đang được bảo vệ:[/bold cyan]")
            for p in sorted(ignored):
                console.print(f"  🔒 {p}")
    elif action == "add":
        if not target_path:
            console.print("[red]Vui lòng cung cấp đường dẫn cần thêm: mclean ignore add /path/to/dir[/red]")
            return
        p = Path(target_path).expanduser().resolve()
        ignored.add(p)
        save_ignored_paths(ignored)
        console.print(f"[green]Đã thêm vào danh sách bảo vệ: {p}[/green]")
    elif action == "remove":
        if not target_path:
            console.print("[red]Vui lòng cung cấp đường dẫn cần xoá: mclean ignore remove /path/to/dir[/red]")
            return
        p = Path(target_path).expanduser().resolve()
        if p in ignored:
            ignored.remove(p)
            save_ignored_paths(ignored)
            console.print(f"[green]Đã xoá khỏi danh sách bảo vệ: {p}[/green]")
        else:
            console.print("[yellow]Đường dẫn không có trong danh sách bảo vệ.[/yellow]")


@app.command()
def status():
    """⚡ Kiểm tra nhanh dung lượng ổ cứng và các ứng dụng phát triển đang mở."""
    print_disk_banner()
    print_active_process_warning()


@app.command()
def optimize():
    """🚀 Tối ưu & Tăng tốc macOS: Làm mới DNS, QuickLook, chặn rác .DS_Store (theo chuẩn tw93/Mole)."""
    console.print("[bold cyan]🚀 Đang thực hiện các tác vụ tối ưu & bảo trì hệ thống macOS...[/bold cyan]\n")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Đang tối ưu hệ thống...", total=None)
        results = run_all_optimizations()
        progress.remove_task(task)

    table = Table(title="Kết Quả Tối Ưu Hệ Thống", show_header=True)
    table.add_column("Tác vụ tối ưu", style="white")
    table.add_column("Trạng thái", justify="center")
    table.add_column("Chi tiết", style="dim")

    for title, ok, msg in results:
        status_badge = "[bold green]THÀNH CÔNG[/bold green]" if ok else "[bold red]THẤT BẠI[/bold red]"
        table.add_row(title, status_badge, msg)

    console.print(table)
    console.print("\n✨ [green]Hệ thống macOS đã được làm mới bộ nhớ đệm và tối ưu hoàn tất![/green]")


@app.command()
def installer(
    older_than: int = typer.Option(7, "--older-than", "-d", help="Chỉ dọn các file cũ hơn số ngày này"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Chạy thử không xoá file thật"),
):
    """📦 Quét và dọn các file cài đặt tồn đọng (.dmg, .pkg, .apk, .ipa) trong Downloads."""
    console.print(f"[bold cyan]🔍 Quét các tệp cài đặt & mobile builds trong Downloads (> {older_than} ngày)...[/bold cyan]\n")

    targets = scan_installers(older_than_days=older_than)
    if not targets:
        console.print("[green]✨ Không có tệp cài đặt nào bị bỏ quên trong Downloads![/green]")
        return

    table = Table(title="Tệp Cài Đặt & Mobile Builds Phát Hiện Được")
    table.add_column("Tên tệp", style="white")
    table.add_column("Đường dẫn", style="dim")
    table.add_column("Dung lượng", style="bold yellow", justify="right")
    table.add_column("Mức độ", justify="center")

    total_size = sum(t.size_bytes for t in targets)
    for t in targets:
        badge = "[green]SAFE[/green]" if t.is_safe else "[yellow]REVIEW[/yellow]"
        table.add_row(t.name, str(t.path), format_size(t.size_bytes), badge)

    console.print(table)
    console.print(f"\nTổng dung lượng có thể giải phóng: [bold green]{format_size(total_size)}[/bold green]")

    if dry_run:
        console.print("[cyan][Dry-run] Kết thúc chạy thử nghiệm.[/cyan]")
        return

    selected = select_installers(targets)
    if selected:
        remove_user_files([(t.path, t.size_bytes) for t in selected])


def select_installers(targets: List[CleanTarget]) -> List[CleanTarget]:
    """Let the user pick installers to remove; only old installers are pre-selected."""
    selected = questionary.checkbox(
        "Chọn tệp muốn dọn (SPACE để chọn, Enter để xác nhận). Tệp mới và tệp nén không được chọn sẵn:",
        choices=[
            questionary.Choice(
                title=f"{'[SAFE]' if t.is_safe else '[REVIEW]'} {t.path.name} ({format_size(t.size_bytes)})",
                value=t,
                checked=t.is_safe,
            )
            for t in targets
        ],
    ).ask()
    if not selected:
        console.print("[yellow]Chưa chọn tệp nào. Không xoá gì.[/yellow]")
        return []
    return selected


def remove_user_files(items: List[Tuple[Path, int]]) -> None:
    """Ask whether to move user files to the Trash (recoverable) or delete them permanently, then do it."""
    total = sum(size for _, size in items)
    mode = questionary.select(
        f"Dọn {len(items)} tệp ({format_size(total)}) bằng cách nào?",
        choices=[
            questionary.Choice("🗑️  Chuyển vào Thùng rác (khôi phục được)", value="trash"),
            questionary.Choice("⚠️  Xoá vĩnh viễn (giải phóng ngay)", value="delete"),
            questionary.Choice("❌ Huỷ", value=None),
        ],
    ).ask()
    if not mode:
        return

    done: List[Tuple[Path, int]] = []
    for path, size in items:
        ok, msg = move_to_trash(path) if mode == "trash" else safe_delete_path(path)
        if ok:
            done.append((path, size))
        else:
            console.print(f"[red]✗ {msg}[/red]")
    freed = sum(size for _, size in done)

    if mode == "trash":
        console.print(
            f"[bold green]🗑️  Đã chuyển {len(done)} tệp ({format_size(freed)}) vào Thùng rác.[/bold green] "
            "[dim]Dung lượng được giải phóng khi bạn dọn Thùng rác (`mclean clean trash`).[/dim]"
        )
    else:
        if freed:
            record_cleanup(freed, [p.name for p, _ in done])
        console.print(f"[bold green]🎉 Đã xoá vĩnh viễn {len(done)} tệp, giải phóng {format_size(freed)}[/bold green]")

@app.command()
def ui():
    """🖥️  Mở Dashboard tương tác trực quan với thanh tiến trình trực tiếp (chuẩn Mole, siêu mượt, không lag)."""
    from mclean.dashboard import interactive_dashboard_menu
    interactive_dashboard_menu()


@app.command()
def history(
    clear: bool = typer.Option(False, "--clear", "-c", help="Xoá toàn bộ lịch sử dọn dẹp"),
):
    """📜 Xem nhật ký dọn dẹp và tổng dung lượng ổ cứng đã tiết kiệm từ trước đến nay."""
    if clear:
        if questionary.confirm("Bạn có chắc muốn xoá toàn bộ lịch sử dọn dẹp không?", default=False).ask():
            clear_history()
            console.print("[green]Đã xoá lịch sử dọn dẹp.[/green]")
        return

    records = load_history()
    total_lifetime = get_total_lifetime_savings()

    console.print(
        Panel(
            f"🎉 [bold green]Tổng dung lượng bạn đã tiết kiệm được: {format_size(total_lifetime)}[/bold green]\n"
            f"[dim]Tổng số phiên dọn dẹp đã thực hiện: {len(records)} lần[/dim]",
            title="🏆 [bold cyan]mclean Lifetime Savings[/bold cyan]",
            border_style="green",
        )
    )

    if not records:
        console.print("[dim]Chưa có phiên dọn dẹp nào được ghi nhận. Hãy chạy `mclean clean` để bắt đầu tích luỹ![/dim]")
        return

    table = Table(title="Lịch Sử Các Lần Dọn Dẹp Gần Nhất", show_header=True)
    table.add_column("Thời gian", style="cyan", no_wrap=True)
    table.add_column("Dung lượng giải phóng", style="bold green", justify="right")
    table.add_column("Số mục dọn", justify="center")
    table.add_column("Chi tiết các mục chính", style="dim")

    for r in reversed(records[-15:]):  # Show last 15 records
        items_preview = ", ".join(r.get("items", []))
        if len(items_preview) > 50:
            items_preview = items_preview[:47] + "..."
        table.add_row(
            r.get("timestamp", "").replace("T", " ")[:19],
            format_size(r.get("reclaimed_bytes", 0)),
            str(r.get("items_count", 0)),
            items_preview or "-",
        )

    console.print(table)


@app.command()
def schedule(
    install: bool = typer.Option(False, "--install", "-i", help="Kích hoạt lịch dọn tự động ngầm hàng tuần"),
    remove: bool = typer.Option(False, "--remove", "-r", help="Huỷ bỏ lịch dọn tự động ngầm"),
    status: bool = typer.Option(False, "--status", "-s", help="Xem trạng thái lịch hiện tại"),
    weekday: int = typer.Option(1, "--weekday", "-w", help="Thứ trong tuần (1 = Thứ Hai, 7 = Chủ nhật)"),
    hour: int = typer.Option(9, "--hour", help="Giờ chạy (0-23)"),
    minute: int = typer.Option(0, "--minute", help="Phút chạy (0-59)"),
):
    """⏱️  Quản lý lịch tự động dọn rác định kỳ ngầm qua macOS LaunchAgent."""
    if install:
        ok, msg = install_schedule(weekday=weekday, hour=hour, minute=minute)
        if ok:
            console.print(f"[bold green]✨ {msg}[/bold green]")
            console.print("[dim]Hệ thống sẽ tự động dọn mục SAFE và gửi macOS Notification khi hoàn tất.[/dim]")
        else:
            console.print(f"[bold red]❌ {msg}[/bold red]")
        return

    if remove:
        ok, msg = remove_schedule()
        if ok:
            console.print(f"[bold green]✨ {msg}[/bold green]")
        else:
            console.print(f"[bold red]❌ {msg}[/bold red]")
        return

    # Default: Show schedule status
    info = get_schedule_status()
    table = Table(title="Trạng Thái Lịch Dọn Ngầm (LaunchAgent)", show_header=False)
    table.add_column("Thuộc tính", style="cyan")
    table.add_column("Giá trị", style="white")

    table.add_row("Tình trạng", info.get("installed", ""))
    table.add_row("Hoạt động", info.get("status", ""))
    table.add_row("Đường dẫn Plist", info.get("path", ""))

    console.print(table)
    console.print(
        "\n💡 [dim]Để kích hoạt lịch chạy mỗi sáng Thứ Hai lúc 09:00: [/dim][bold cyan]mclean schedule --install[/bold cyan]\n"
        "💡 [dim]Để huỷ bỏ lịch: [/dim][bold red]mclean schedule --remove[/bold red]"
    )


@app.command()
def docker(
    all_unused: bool = typer.Option(False, "--all", "-a", help="Dọn toàn bộ container và image không dùng (deep clean)"),
):
    """🐳 Dọn dẹp Docker / OrbStack: dangling images và build cache cũ (--all để dọn sâu)."""
    console.print("[bold cyan]🐳 Đang kiểm tra môi trường Docker & Containers...[/bold cyan]\n")

    scanner = DockerScanner()
    if not scanner.is_docker_running():
        console.print("[yellow]⚠️  Docker daemon hiện không mở hoặc chưa được cài đặt.[/yellow]")
        console.print("[dim]Đang kiểm tra các file log/cache tạm của Docker Desktop trên ổ đĩa...[/dim]")
        local_targets = scanner.scan()
        if local_targets:
            total_sz = sum(t.size_bytes for t in local_targets)
            console.print(f"Tìm thấy các file log tạm: [bold yellow]{format_size(total_sz)}[/bold yellow]")
            if questionary.confirm("Dọn các file log tạm này không?", default=True).ask():
                report = execute_clean(local_targets)
                console.print(f"[bold green]🎉 Đã giải phóng: {format_size(report.reclaimed)}[/bold green]")
        return

    prompt = (
        "Deep clean: xoá MỌI image không dùng và container đã dừng (sẽ phải pull lại khi cần). Tiếp tục?"
        if all_unused
        else "Dọn dangling images và build cache không dùng > 30 ngày?"
    )
    if questionary.confirm(prompt, default=not all_unused).ask():
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("Đang dọn dẹp Docker...", total=None)
            ok, output = run_docker_prune(all_unused=all_unused)
            progress.remove_task(task)

        if ok:
            console.print("[bold green]🎉 Hoàn tất dọn dẹp Docker![/bold green]")
            console.print(Panel(output, title="Kết quả Docker Prune", border_style="green"))
        else:
            console.print(f"[bold red]❌ Lỗi dọn dẹp Docker: {output}[/bold red]")


@app.command(name="large-files")
def large_files_cmd(
    path: Optional[str] = typer.Argument(None, help="Thư mục cần quét (mặc định: ~)"),
    min_size: int = typer.Option(500, "--min-size", "-m", help="Dung lượng tối thiểu tính bằng MB"),
    limit: int = typer.Option(25, "--limit", "-l", help="Số lượng tệp tối đa hiển thị"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Bật chế độ chọn để xem trong Finder hoặc xoá"),
):
    """🐘 Quét tìm các tệp siêu nặng (> 500 MB) như model AI, video test, zip thất lạc."""
    scan_root = Path(path).expanduser().resolve() if path else Path.home()
    console.print(f"[bold cyan]🔍 Đang quét các tệp >= {min_size} MB tại: {scan_root}...[/bold cyan]\n")

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Đang rà soát tệp lớn...", total=None)
        items = find_large_files(root=scan_root, min_size_mb=min_size, max_results=limit)
        progress.remove_task(task)

    if not items:
        console.print(f"[green]✨ Tuyệt vời! Không tìm thấy tệp nào lớn hơn {min_size} MB trong thư mục này.[/green]")
        return

    table = Table(title=f"Top {len(items)} Tệp Siêu Nặng Phát Hiện Được", show_header=True)
    table.add_column("Phân loại", style="cyan")
    table.add_column("Tên tệp", style="white")
    table.add_column("Đường dẫn", style="dim")
    table.add_column("Dung lượng", style="bold yellow", justify="right")
    table.add_column("Ngày sửa đổi", style="dim", justify="center")

    total_sz = sum(it.size_bytes for it in items)
    for it in items:
        table.add_row(
            it.file_type,
            it.path.name,
            str(it.path.parent),
            format_size(it.size_bytes),
            format_timestamp(it.mtime),
        )

    console.print(table)
    console.print(f"\nTổng dung lượng các tệp trên: [bold yellow]{format_size(total_sz)}[/bold yellow]")

    if not interactive and not questionary.confirm("Bạn có muốn mở xem hoặc dọn bớt tệp nào không?", default=False).ask():
        return
    choices = [
        questionary.Choice(
            title=f"{it.path.name} ({format_size(it.size_bytes)}) - {it.file_type}",
            value=it,
        )
        for it in items
    ]
    chosen = questionary.select("Chọn tệp bạn muốn thao tác:", choices=choices).ask()
    if chosen:
        action = questionary.select(
            f"Thao tác cho tệp: {chosen.path.name}",
            choices=[
                "1. 📂 Mở vị trí tệp trong macOS Finder",
                "2. 🗑️ Dọn tệp này",
                "3. ❌ Bỏ qua",
            ],
        ).ask()

        if not action:
            return
        if "1. 📂 Mở" in action:
            reveal_in_finder(chosen.path)
            console.print(f"[green]Đã mở vị trí tệp trong Finder: {chosen.path}[/green]")
        elif "2. 🗑️ Dọn" in action:
            remove_user_files([(chosen.path, chosen.size_bytes)])

if __name__ == "__main__":
    app()
