"""
notify.py — Zero-dependency cross-platform system notifications.
Uses native OS commands so no pip packages are needed.

macOS  → osascript (always present)
Linux  → notify-send (libnotify, common on all desktop distros)
Windows → PowerShell toast (built into Windows 10/11)
"""

import platform
import subprocess
import sys


_OS = platform.system()


def _run(*cmd: str) -> None:
    """Fire-and-forget subprocess; swallow errors so a missing notifier
    never crashes the worker."""
    try:
        subprocess.run(
            list(cmd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        pass


def send(title: str, message: str, *, success: bool = True) -> None:
    """
    Send a system notification. Safe to call from worker processes.

    Args:
        title:   Notification headline (e.g. task label).
        message: Body text (e.g. duration, error summary).
        success: Controls icon/sound hint where supported.
    """
    if _OS == "Darwin":
        _macos(title, message, success)
    elif _OS == "Linux":
        _linux(title, message, success)
    elif _OS == "Windows":
        _windows(title, message, success)
    else:
        # Graceful fallback — just print to stderr so it surfaces somewhere.
        print(f"\n[notify] {title}: {message}", file=sys.stderr)


# ── Platform implementations ───────────────────────────────────────────────────

def _macos(title: str, body: str, success: bool) -> None:
    # osascript is shipped with every macOS installation.
    sound = "Glass" if success else "Basso"
    script = (
        f'display notification "{_esc(body)}" '
        f'with title "{_esc(title)}" '
        f'sound name "{sound}"'
    )
    _run("osascript", "-e", script)


def _linux(title: str, body: str, success: bool) -> None:
    # notify-send ships with libnotify, present on GNOME/KDE/XFCE desktops.
    icon = "dialog-information" if success else "dialog-error"
    urgency = "normal" if success else "critical"
    _run(
        "notify-send",
        "--icon", icon,
        "--urgency", urgency,
        "--expire-time", "8000",  # ms
        title,
        body,
    )


def _windows(title: str, body: str, success: bool) -> None:
    # PowerShell toast — available on Windows 10 build 1903+.
    ps = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(
    [Windows.UI.Notifications.ToastTemplateType]::ToastText02
)
$template.SelectSingleNode('//text[@id=1]').InnerText = '{_esc(title)}'
$template.SelectSingleNode('//text[@id=2]').InnerText = '{_esc(body)}'
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('CLI Task Queue').Show($toast)
""".strip()
    _run("powershell", "-NoProfile", "-NonInteractive", "-Command", ps)


def _esc(s: str) -> str:
    """Minimal escaping for embedding in shell strings."""
    return s.replace('"', '\\"').replace("'", "\\'").replace("\n", " ")
