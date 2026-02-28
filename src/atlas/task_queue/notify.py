"""
Cross-platform system notifications. Never raises
"""

from __future__ import annotations

import platform
import subprocess

_PLATFORM = platform.system()


def notify(title: str, message: str, *, success: bool = True) -> None:
    """Send a cross-platform system notification. Never raises."""
    try:
        if _PLATFORM == "Darwin":
            sound = "Glass" if success else "Basso"
            script = f'display notification "{_esc(message)}" with title "{_esc(title)}" sound name "{sound}"'
            subprocess.run(
                ["osascript", "-e", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        elif _PLATFORM == "Linux":
            icon = "dialog-information" if success else "dialog-error"
            subprocess.run(
                ["notify-send", "--icon", icon, "--expire-time", "8000", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        elif _PLATFORM == "Windows":
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager,"
                " Windows.UI.Notifications, ContentType=WindowsRuntime] > $null\n"
                "$t = [Windows.UI.Notifications.ToastNotificationManager]::"
                "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)\n"
                f"$t.SelectSingleNode('//text[@id=1]').InnerText = '{_esc(title)}'\n"
                f"$t.SelectSingleNode('//text[@id=2]').InnerText = '{_esc(message)}'\n"
                "$toast = [Windows.UI.Notifications.ToastNotification]::new($t)\n"
                "[Windows.UI.Notifications.ToastNotificationManager]::"
                "CreateToastNotifier('Atlas').Show($toast)"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    except Exception:
        pass  # never crash the caller


def _esc(s: str) -> str:
    """Minimal escaping for embedding in shell/PS strings."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
