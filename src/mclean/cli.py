"""mclean: macOS Developer & AI Precision Cleaner CLI Interface."""

import shutil
from pathlib import Path
from typing import List, Optional

import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

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
from mclean.scanners.flutter_dart import FlutterDartScanner
from mclean.scanners.installer import scan_installers
from mclean.scanners.optimizer import run_all_optimizations
from mclean.scanners.system_junk import SystemJunkScanner
from mclean.utils.disk import get_disk_space, get_path_size, safe_delete_path
from mclean.utils.formatters import format_size
from mclean.utils.guard import check_conflicts_for_category, get_active_dev_processes

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
        AiPythonScanner(),
        SystemJunkScanner(),
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
        f"— 100% An toàn, dọn xong [bold underline]KHÔNG BAO GIỜ phải tải lại dữ liệu[/bold underline]."
    )
    console.print(
        f"🟡 [bold yellow]Tier 2 (REVIEW): {format_size(total_review)}[/bold yellow] "
        f"— Model AI, máy ảo cũ (dùng [bold cyan]mclean interactive[/bold cyan] để chọn xoá từng mục)."
    )
    console.print("\n💡 Gõ [bold cyan]mclean clean[/bold cyan] để dọn ngay các mục SAFE.")


@app.command()
def clean(
    category: Optional[str] = typer.Argument(
        None, help="Phân loại muốn dọn: dev, xcode, android, flutter, ai, system, trash, hoặc bỏ trống để dọn tất cả SAFE"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Chạy giả lập kiểm tra, không xoá file thật"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Bật menu chọn lọc để duyệt từng Model AI và máy ảo"),
    force: bool = typer.Option(False, "--force", "-f", help="Bỏ qua xác nhận xác nhận xóa"),
):
    """🧹 Dọn dẹp an toàn các vùng nhớ đệm mà không gây vòng lặp tải lại."""
    print_disk_banner()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task(description="Đang kiểm tra các mục có thể dọn dẹp...", total=None)
        all_targets = run_all_scanners()

    # Filter by category if specified
    if category:
        cat_lower = category.lower()
        all_targets = [t for t in all_targets if cat_lower in t.category.value.lower() or cat_lower in t.name.lower()]

    if not all_targets:
        console.print("[green]✨ Không có mục nào cần dọn dẹp trong danh mục này![/green]")
        return

    # Check for process conflicts
    if category:
        conflicts = check_conflicts_for_category(category)
        if conflicts:
            console.print(f"[bold red]⚠️  Cảnh báo:[/bold red] Các ứng dụng sau đang mở: {', '.join(conflicts)}")
            if not force and not questionary.confirm("Bạn có chắc chắn muốn tiếp tục dọn không?", default=False).ask():
                console.print("[yellow]Đã huỷ dọn dẹp để bảo vệ ứng dụng đang chạy.[/yellow]")
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
    reclaimed = 0
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        for t in targets_to_clean:
            task = progress.add_task(description=f"Đang dọn {t.name}...", total=None)
            success, msg = AppleXcodeScanner().clean(t, dry_run=False)
            if success:
                reclaimed += t.size_bytes
            progress.remove_task(task)

    console.print(f"\n[bold green]🎉 Hoàn tất![/bold green] Đã giải phóng thành công: [bold green]{format_size(reclaimed)}[/bold green]")
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
    """🗑️  Quét sâu các thư mục dự án (Flutter, Node, Python) và dọn build/, .dart_tool/, node_modules/ cũ."""
    scan_root = Path(path).expanduser().resolve() if path else Path.home() / "Desktop"
    console.print(f"[bold cyan]🔍 Quét dọn các build artifacts không hoạt động trong > {older_than} ngày tại: {scan_root}[/bold cyan]")

    scanner = FlutterDartScanner(workspace_roots=[scan_root], inactive_days=older_than)
    targets = scanner.scan_workspace_for_inactive_projects(scan_root, older_than)

    if not targets:
        console.print("[green]✨ Không tìm thấy build artifacts cũ nào cần purge![/green]")
        return

    table = Table(title="Dự Án Không Hoạt Động Có Thể Dọn Dẹp")
    table.add_column("Dự án", style="cyan")
    table.add_column("Đường dẫn", style="dim")
    table.add_column("Dung lượng", justify="right", style="bold yellow")
    table.add_column("Trạng thái", justify="center")

    total_size = sum(t.size_bytes for t in targets)
    for t in targets:
        table.add_row(t.name, str(t.path), format_size(t.size_bytes), "[green]SAFE[/green]")

    console.print(table)
    console.print(f"\nTổng dung lượng có thể giải phóng: [bold green]{format_size(total_size)}[/bold green]")

    if dry_run:
        console.print("[cyan][Dry-run] Kết thúc quét thử nghiệm.[/cyan]")
        return

    if questionary.confirm("Bạn có muốn dọn dẹp các thư mục build cũ này không?", default=True).ask():
        cleaned = 0
        for t in targets:
            ok, _ = safe_delete_path(t.path)
            if ok:
                cleaned += t.size_bytes
        console.print(f"[bold green]🎉 Đã giải phóng: {format_size(cleaned)}[/bold green]")


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

    if questionary.confirm("Bạn có muốn xoá các tệp cài đặt đã chọn không?", default=True).ask():
        cleaned = 0
        for t in targets:
            ok, _ = safe_delete_path(t.path)
            if ok:
                cleaned += t.size_bytes
        console.print(f"[bold green]🎉 Đã giải phóng: {format_size(cleaned)}[/bold green]")


@app.command()
def ui():
    """🖥️  Mở Dashboard tương tác trực quan với thanh tiến trình trực tiếp (chuẩn Mole, siêu mượt, không lag)."""
    from mclean.dashboard import interactive_dashboard_menu
    interactive_dashboard_menu()


if __name__ == "__main__":
    app()
