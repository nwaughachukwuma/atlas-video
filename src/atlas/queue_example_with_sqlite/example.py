"""
example.py — Demonstrates taskqueue in a video-processing CLI.

Run with:
    python example.py encode video1.mp4 video2.mp4 video3.mp4

Each file is queued immediately and the CLI returns. System notifications
fire as each encode completes. Press Ctrl-C once to see the warning;
press it again to force-quit.
"""

import sys
from pathlib import Path

# ── Simulated task (must be a module-level, importable function) ──────────────


def encode_video(src: str, dst: str, quality: int = 23) -> None:
    """
    Placeholder for a real ffmpeg/handbrake encode.
    Simulates a long-running job that takes a few seconds per 'minute of video'.
    """
    import random
    import time

    duration = random.uniform(4, 8)  # simulate variable encode time
    time.sleep(duration)  # replace with actual subprocess call
    # e.g.: subprocess.run(["ffmpeg", "-i", src, "-crf", str(quality), dst], check=True)
    print(f"  → Encoded {src} to {dst} (simulated {duration:.1f}s)", flush=True)


def analyse_video(src: str) -> None:
    """Placeholder: run scene detection, generate thumbnails, etc."""
    import time

    time.sleep(3)
    print(f"  → Analysed {src}", flush=True)


# ── CLI entry point ────────────────────────────────────────────────────────────


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print("Usage: python example.py <file1.mp4> [file2.mp4 ...]")
        sys.exit(1)

    # Import here so ProcessPoolExecutor workers can find the functions above
    # via their module path (example.encode_video / example.analyse_video).
    from taskqueue import TaskQueue

    queue = TaskQueue(max_workers=4)  # change to suit your machine

    for src in argv:
        src_path = Path(src)
        dst_path = src_path.with_stem(src_path.stem + "_encoded")

        # Queue the encode — returns immediately with a task ID.
        task_id = queue.submit(
            encode_video,
            str(src_path),
            str(dst_path),
            quality=20,
            label=f"Encode {src_path.name}",
        )

        # Optionally chain a second task — in practice you'd do this in a
        # callback or a follow-up CLI command; for demo we just queue both.
        queue.submit(
            analyse_video,
            str(src_path),
            label=f"Analyse {src_path.name}",
        )

    print(
        f"\n[cli] {queue.active_count()} tasks queued and running in the background.\n"
        "      You'll get a system notification when each one finishes.\n"
        "      Close this terminal and the workers continue until done.\n"
        "      (Press Ctrl-C to see the safety warning.)\n",
        file=sys.stderr,
    )

    # For a real CLI you'd return here — the monitor thread keeps the process
    # alive. For this demo we just wait so you can see the notifications.
    queue.wait()
    print("[cli] All tasks finished.", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
