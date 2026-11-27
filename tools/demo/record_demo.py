#!/usr/bin/env python3
"""Record the FinePrint live-harness demo as a terminal GIF.

Runs the real commands from tools/demo/demo_steps.py in a pty at a
readable typing speed, captures the real output, and renders it to
assets/fineprint-live-demo.gif (turbosearch style: GIF in the branch
README). Also writes tools/demo/demo-transcript.txt (the exact
commands and their output, for review without watching the GIF).

No output is faked: every frame is the terminal screen while a real
command runs. The recorder only controls pace (typing speed, pauses
between steps) and rendering.

Usage:
    python3 tools/demo/record_demo.py [--fps N] [--out PATH]

Requires Pillow (pip install pillow). Stdlib + PIL only.
"""

import argparse
import fcntl
import os
import pty
import re
import select
import struct
import sys
import termios
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
DEMO = REPO / "tools" / "demo"
sys.path.insert(0, str(DEMO))

from demo_steps import STEPS, TYPE_DELAY_MS  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    print("record_demo.py needs Pillow: pip install pillow", file=sys.stderr)
    raise SystemExit(1)

COLS = 100
ROWS = 34
FONT_SIZE = 16
LINE_HEIGHT = 20
BG = (13, 17, 23)       # #0d1117
FG = (201, 209, 217)    # #c9d1d9
PROMPT_FG = (63, 185, 80)  # #3fb950
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
PROMPT = "demo$ "


class Screen:
    """Minimal terminal screen: printable chars, CR/LF/BS, common CSI."""

    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.lines = [""] * rows
        self.x = 0
        self.y = 0
        self._esc = ""

    def _put(self, ch):
        if self.y >= self.rows:
            self.lines.pop(0)
            self.lines.append("")
            self.y = self.rows - 1
        line = self.lines[self.y]
        if len(line) < self.x:
            line = line + " " * (self.x - len(line))
        if self.x < self.cols:
            line = line[:self.x] + ch + line[self.x + 1:]
            self.x += 1
        self.lines[self.y] = line

    def _csi(self, params, final):
        nums = [int(p) if p.isdigit() else 0 for p in params.split(";")] or [0]
        n = nums[0] or 1
        if final == "K":
            line = self.lines[self.y]
            self.lines[self.y] = line[:self.x]
        elif final == "J":
            if nums[0] == 2:
                self.lines = [""] * self.rows
                self.x = self.y = 0
        elif final == "H":
            self.y = (nums[0] - 1) if len(nums) > 0 and nums[0] else 0
            self.x = (nums[1] - 1) if len(nums) > 1 and nums[1] else 0
            self.y = max(0, min(self.rows - 1, self.y))
            self.x = max(0, min(self.cols - 1, self.x))
        elif final == "A":
            self.y = max(0, self.y - n)
        elif final == "B":
            self.y = min(self.rows - 1, self.y + n)
        elif final == "C":
            self.x = min(self.cols - 1, self.x + n)
        elif final == "D":
            self.x = max(0, self.x - n)
        # SGR (m) and private modes (?...) are ignored: demo output is plain.

    def feed(self, text):
        i = 0
        while i < len(text):
            ch = text[i]
            if self._esc:
                self._esc += ch
                if ch.isalpha() or ch in "@`":
                    if self._esc.startswith("\x1b["):
                        self._csi(self._esc[2:-1], ch)
                    self._esc = ""
                i += 1
                continue
            if ch == "\x1b":
                self._esc = ch
            elif ch == "\r":
                self.x = 0
            elif ch == "\n":
                self.y += 1
                if self.y >= self.rows:
                    self.lines.pop(0)
                    self.lines.append("")
                    self.y = self.rows - 1
            elif ch == "\b":
                self.x = max(0, self.x - 1)
            elif ch == "\x07":
                pass
            elif ch >= " ":
                self._put(ch)
            i += 1

    def snapshot(self):
        return [ln.rstrip() for ln in self.lines]


def run_demo(fps=8, out_path=None, transcript_path=None):
    out_path = out_path or REPO / "assets" / "fineprint-live-demo.gif"
    transcript_path = transcript_path or DEMO / "demo-transcript.txt"
    frame_gap = 1.0 / fps
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    char_w = font.getlength("M")
    width = int(COLS * char_w)
    height = ROWS * LINE_HEIGHT

    # pty.fork() makes the pty the child's controlling terminal, so
    # bash gets job control and prints no "cannot set terminal process
    # group" warnings at the top of the recording.
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(REPO)
        os.environ.update(TERM="xterm-256color", PS1=PROMPT,
                          COLUMNS=str(COLS), LINES=str(ROWS),
                          PROMPT_COMMAND="")
        os.execvp("bash", ["bash", "--noprofile", "--norc", "-i"])
    fcntl.ioctl(master, termios.TIOCSWINSZ,
                struct.pack("HHHH", ROWS, COLS, 0, 0))

    screen = Screen(COLS, ROWS)
    frames = []  # (duration_ms, [lines])
    raw_log = []
    start = time.monotonic()
    last_frame_at = start
    last_snapshot = None

    def pump(timeout):
        """Read available pty output for up to timeout seconds."""
        nonlocal last_frame_at, last_snapshot
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            r, _, _ = select.select([master], [], [], 0.05)
            if not r:
                continue
            try:
                data = os.read(master, 65536)
            except OSError:
                return False
            if not data:
                return False
            text = data.decode("utf-8", errors="replace")
            raw_log.append(text)
            screen.feed(text)
            now = time.monotonic()
            if now - last_frame_at >= frame_gap:
                snap = screen.snapshot()
                if snap != last_snapshot:
                    frames.append((int((now - last_frame_at) * 1000), snap))
                    last_snapshot = snap
                    last_frame_at = now
        return True

    def wait_prompt(timeout=120):
        """Wait until the prompt is back and output has been quiet."""
        quiet_since = None
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            pump(0.2)
            snap = screen.snapshot()
            non_empty = [ln for ln in snap if ln.strip()]
            if non_empty and non_empty[-1] == PROMPT.strip():
                if quiet_since is None:
                    quiet_since = time.monotonic()
                elif time.monotonic() - quiet_since > 0.5:
                    return True
            else:
                quiet_since = None
        raise TimeoutError("prompt did not return")

    transcript = []
    try:
        pump(1.0)
        wait_prompt()
        for step in STEPS:
            cmd = step["cmd"]
            mark = len("".join(raw_log))
            for ch in cmd:
                os.write(master, ch.encode())
                pump(TYPE_DELAY_MS / 1000.0)
            os.write(master, b"\r")
            wait_prompt()
            # Transcript: raw output for this step, minus the echo,
            # trailing prompt, and bracketed-paste/control sequences.
            segment = "".join(raw_log)[mark:]
            segment = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z@`]", "", segment)
            lines = segment.replace("\r\n", "\n").split("\n")
            if lines and lines[0].strip() == cmd:
                lines = lines[1:]
            while lines and lines[-1].strip() in ("", PROMPT.strip()):
                lines.pop()
            transcript.append(f"$ {cmd}")
            transcript.extend(lines)
            transcript.append("")
            time.sleep(step.get("pause", 4))
            pump(0.2)
        # Final frame.
        snap = screen.snapshot()
        if snap != last_snapshot:
            frames.append((500, snap))
    finally:
        try:
            os.write(master, b"exit\r")
        except OSError:
            pass
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass
        os.close(master)

    images = []
    durations = []
    for duration_ms, lines in frames:
        img = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(img)
        for row, line in enumerate(lines):
            y = row * LINE_HEIGHT + 2
            if line.startswith(PROMPT):
                draw.text((0, y), PROMPT, font=font, fill=PROMPT_FG)
                draw.text((font.getlength(PROMPT), y), line[len(PROMPT):],
                          font=font, fill=FG)
            else:
                draw.text((0, y), line, font=font, fill=FG)
        images.append(img)
        durations.append(max(duration_ms, 50))
    total_ms = sum(durations)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(out_path, save_all=True, append_images=images[1:],
                   duration=durations, loop=0, optimize=True)
    transcript_path.write_text("\n".join(transcript))
    print(f"frames: {len(images)}  duration: {total_ms / 1000:.1f}s  "
          f"size: {out_path.stat().st_size / 1e6:.1f} MB")
    print(f"wrote {out_path}")
    print(f"wrote {transcript_path}")
    return total_ms / 1000.0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fps", type=int, default=8)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    run_demo(fps=args.fps, out_path=args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
