"""Formatting helpers for sizes, time, and badges."""

from datetime import datetime
import time


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    val = float(size_bytes)
    while val >= 1024.0 and unit_index < len(units) - 1:
        val /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(val)} B"
    if unit_index == 1:
        return f"{val:.0f} KB"
    return f"{val:.2f} {units[unit_index]}"


def format_timestamp(timestamp: float) -> str:
    """Format Unix timestamp into human-readable relative time and date."""
    if timestamp <= 0:
        return "Unknown"
    dt = datetime.fromtimestamp(timestamp)
    diff = time.time() - timestamp
    days = int(diff / 86400)
    if days == 0:
        return f"Today ({dt.strftime('%H:%M')})"
    if days == 1:
        return f"Yesterday ({dt.strftime('%H:%M')})"
    if days < 30:
        return f"{days} days ago"
    months = days // 30
    return f"{months} mo ago ({dt.strftime('%Y-%m-%d')})"
