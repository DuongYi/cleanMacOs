#!/usr/bin/env bash
# mclean installer
#
#   Cài hoặc cập nhật:  curl -fsSL https://raw.githubusercontent.com/DuongYi/cleanMacOs/main/install.sh | bash
#   Gỡ cài đặt:         curl -fsSL https://raw.githubusercontent.com/DuongYi/cleanMacOs/main/install.sh | bash -s -- --uninstall
#   Từ bản clone:       ./install.sh            (dùng luôn thư mục repo này, không clone thêm)
#
# Biến môi trường tuỳ chọn:
#   MCLEAN_DIR=~/somewhere      nơi cài (mặc định ~/.mclean)
#   MCLEAN_REPO=<git url>       repo nguồn
#   MCLEAN_NONINTERACTIVE=1     không hỏi bật lịch tự động
set -euo pipefail

REPO_URL="${MCLEAN_REPO:-https://github.com/DuongYi/cleanMacOs.git}"
INSTALL_DIR="${MCLEAN_DIR:-$HOME/.mclean}"
BIN_DIR="$HOME/.local/bin"
LINK="$BIN_DIR/mclean"
MARKER=".git/installed-by-mclean-installer"  # inside .git so it never shows in git status
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"  # added by mclean installer'

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  \033[36m•\033[0m %s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

# Ask a yes/no question on the real terminal, even when the script is piped from curl
ask() {
    [ "${MCLEAN_NONINTERACTIVE:-0}" = "1" ] && return 1
    (: </dev/tty) 2>/dev/null || return 1   # no terminal (CI, cron): never ask
    printf '  \033[35m?\033[0m %s [y/N] ' "$1"
    local answer=""
    read -r answer </dev/tty || answer=""
    [[ "$answer" =~ ^[YyCc] ]]   # y/yes, or "có"
}

# A directory is a mclean checkout if its pyproject declares our package
is_mclean_repo() { [ -f "$1/pyproject.toml" ] && grep -q 'name = "mac-dev-cleaner"' "$1/pyproject.toml"; }

uninstall() {
    bold "Gỡ cài đặt mclean"
    local agents="$HOME/Library/LaunchAgents"
    if [ -x "$LINK" ]; then
        if [ -f "$agents/com.mclean.autoclean.plist" ]; then
            "$LINK" schedule --remove >/dev/null 2>&1 && ok "Đã tắt lịch dọn hàng tuần"
        fi
        if [ -f "$agents/com.mclean.diskalert.plist" ]; then
            "$LINK" schedule --alert-off >/dev/null 2>&1 && ok "Đã tắt cảnh báo ổ đầy"
        fi
    fi
    if [ -L "$LINK" ]; then rm -f "$LINK" && ok "Đã xoá lệnh $LINK"; fi
    if [ -f "$INSTALL_DIR/$MARKER" ]; then
        rm -rf "$INSTALL_DIR" && ok "Đã xoá $INSTALL_DIR"
    elif [ -d "$INSTALL_DIR" ]; then
        warn "Giữ nguyên $INSTALL_DIR vì thư mục này không do installer tạo ra"
    fi
    info "Cấu hình và lịch sử vẫn còn ở ~/.config/mclean (xoá tay nếu không cần)"
    exit 0
}

[ "${1:-}" = "--uninstall" ] && uninstall

bold "Cài đặt mclean"

# 1. Requirements
[ "$(uname -s)" = "Darwin" ] || die "mclean chỉ chạy trên macOS."
command -v git >/dev/null 2>&1 || die "Chưa có git. Chạy: xcode-select --install rồi chạy lại lệnh cài."
PYTHON="$(command -v python3 || true)"
[ -n "$PYTHON" ] || die "Chưa có python3. Chạy: xcode-select --install rồi chạy lại lệnh cài."
"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 9))' \
    || die "Cần Python 3.9 trở lên (đang có $("$PYTHON" --version 2>&1))."
ok "macOS, git và $("$PYTHON" --version 2>&1)"

# 2. Source code: this checkout when run as ./install.sh, otherwise clone or update ~/.mclean
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
if [ -n "$SCRIPT_DIR" ] && is_mclean_repo "$SCRIPT_DIR"; then
    INSTALL_DIR="$SCRIPT_DIR"
    ok "Dùng bản clone tại $INSTALL_DIR"
elif [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only --quiet || die "Không cập nhật được $INSTALL_DIR (có thay đổi cục bộ?)."
    ok "Đã cập nhật mã nguồn tại $INSTALL_DIR"
elif [ -e "$INSTALL_DIR" ]; then
    die "$INSTALL_DIR đã tồn tại nhưng không phải repo mclean. Đặt MCLEAN_DIR sang chỗ khác."
else
    git clone --quiet --depth 1 "$REPO_URL" "$INSTALL_DIR" || die "Không clone được $REPO_URL"
    touch "$INSTALL_DIR/$MARKER"
    ok "Đã tải mã nguồn vào $INSTALL_DIR"
fi

# 3. Virtual environment and dependencies (recreated if broken, e.g. after a Python upgrade)
VENV="$INSTALL_DIR/.venv"
if [ -d "$VENV" ] && ! "$VENV/bin/python" -c 'import sys' >/dev/null 2>&1; then
    rm -rf "$VENV"
fi
[ -d "$VENV" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/pip" install --quiet --disable-pip-version-check -e "$INSTALL_DIR" || die "Cài thư viện thất bại."
ok "Đã cài thư viện vào $VENV"

# 4. `mclean` command on PATH
mkdir -p "$BIN_DIR"
if [ -e "$LINK" ] && [ "$(readlink "$LINK" 2>/dev/null)" != "$INSTALL_DIR/mclean" ]; then
    warn "Thay lệnh cũ $LINK → $(readlink "$LINK" 2>/dev/null || echo 'tệp thường')"
fi
ln -sfn "$INSTALL_DIR/mclean" "$LINK"
ok "Lệnh mclean: $LINK"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        added=""
        for rc in "$HOME/.zshrc" "$HOME/.bash_profile"; do
            if { [ "$rc" = "$HOME/.zshrc" ] || [ -f "$rc" ]; } && ! grep -qF "added by mclean installer" "$rc" 2>/dev/null; then
                printf '\n%s\n' "$PATH_LINE" >> "$rc"
                added="yes"
            fi
        done
        if [ -n "$added" ]; then
            warn "Đã thêm ~/.local/bin vào PATH. Mở Terminal mới (hoặc chạy: source ~/.zshrc) để dùng lệnh mclean."
        else
            warn "~/.local/bin đã có trong ~/.zshrc nhưng chưa có trong Terminal này. Mở Terminal mới để dùng lệnh mclean."
        fi
        ;;
esac

VERSION="$("$LINK" --version 2>/dev/null)" || die "Cài xong nhưng không chạy được $LINK"
ok "$VERSION đã sẵn sàng"

# 5. Optional background jobs
echo
if ask "Bật dọn mục SAFE tự động mỗi Thứ Hai 09:00?"; then
    "$LINK" schedule --install || warn "Không bật được lịch dọn."
fi
if ask "Bật cảnh báo khi ổ đĩa sắp đầy (chỉ báo, không xoá)?"; then
    "$LINK" schedule --alert-on || warn "Không bật được cảnh báo."
fi

echo
bold "Xong! Thử ngay:"
info "mclean doctor     kiểm tra máy"
info "mclean scan       xem có gì dọn được (không xoá gì)"
info "mclean            mở Dashboard"
info "mclean update     cập nhật bản mới"
