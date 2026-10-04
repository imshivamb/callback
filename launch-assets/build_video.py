"""Build the launch video, README GIF, backup still and social preview from one real recording.

Source: hosted run, barge-in call 1. The recording is read from the path given on the command
line; caller words come from events.jsonl (the scripted lines), agent words from local Whisper
(small and base.en agreed), with times from the energy of each channel.

Usage: python build_video.py <calls/barge-in--t1> <display font .ttf> [video gif still social sheet]
Needs numpy, soundfile, pillow and imageio-ffmpeg.
"""
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
OUT = Path(__file__).parent
RUN = Path(sys.argv[1])
FONT_DISPLAY = sys.argv[2]
FONT_BODY = "/System/Library/Fonts/Avenir Next.ttc"

W, H, FPS = 1280, 720, 25
MX, MY = round(W * 0.05), round(H * 0.05)  # safe margin: 5% on every side
T0, T1 = 10.0, 32.0  # call-time window used for the video (played at normal speed)
BG, PANEL, INK, MUTE = (17, 20, 24), (22, 27, 34), (240, 242, 245), (150, 158, 168)
CALLER, AGENT, CHAOS, AMBER = (138, 140, 255), (43, 217, 190), (240, 110, 215), (245, 179, 66)

# (start, end, speaker, text). Times: energy edges of each channel, call seconds.
CAPTIONS = [
    (10.72, 14.44, "Caller", "I would like something vegetarian that takes under thirty minutes."),
    (17.98, 19.44, "Agent", "How about a creamy pesto pasta?"),
    (18.38, 20.24, "Caller", "Sorry, make that for six people."),
    (22.42, 23.52, "Agent", "No problem at all."),
    (24.16, 25.78, "Agent", "We’ll just scale up the ingredients for six."),
    (24.26, 26.64, "Caller", "Okay, and what do I need to buy from the shop?"),
    (28.98, 32.0, "Agent", "You’ll need one pound and six ounces of pasta…"),
]
CUT_IN, AGENT_STOPS = 18.38, 19.44  # 1.06 s here; RESULTS.md reports 1.04 s (its own edge detection)
LABEL = "Caller cuts in. The agent kept talking for 1.04 s (Callback’s default: 0.6 s)"
LABEL_FROM, LABEL_TO = CUT_IN - 1.0, AGENT_STOPS + 2.0


def font(path, size):
    return ImageFont.truetype(path, size)


FD = {"hook": font(FONT_DISPLAY, 76), "big": font(FONT_DISPLAY, 112)}
FB = {k: font(FONT_BODY, s) for k, s in (("head", 36), ("sub", 30), ("tag", 34), ("lab", 34), ("cap", 38), ("card", 42))}

x, sr = sf.read(RUN / "call.wav", dtype="float32", always_2d=True)
seg = x[int(T0 * sr):int(T1 * sr)]
DUR = len(seg) / sr

VIOLATIONS: list[str] = []


def text(d, xy, s, fnt, fill):
    """Draw text and record it if it leaves the 5% safe margin."""
    d.text(xy, s, font=fnt, fill=fill)
    box = d.textbbox(xy, s, font=fnt)
    if box[0] < MX - 1 or box[2] > W - MX + 1 or box[1] < MY - 1 or box[3] > H - MY + 1:
        VIOLATIONS.append(f"{s!r} {box}")


def wrap(d, s, fnt, width):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) == 2:  # balance the two lines so no single word is left alone
        words = s.split()
        k = min(range(1, len(words)), key=lambda i: max(d.textlength(" ".join(words[:i]), font=fnt), d.textlength(" ".join(words[i:]), font=fnt)))
        lines = [" ".join(words[:k]), " ".join(words[k:])]
    return lines


def peaks(ch, n):
    e = np.abs(seg[:, ch])
    edges = np.linspace(0, len(e), n + 1).astype(int)
    return np.minimum(1.0, np.maximum.reduceat(e, edges[:-1])) ** 0.5


GUT = 130  # lane names sit in a left gutter, so nothing is written on a waveform
L, R = MX + 6 + GUT, W - MX - 6
LANE_H = 100
LABEL_ROW = 124  # the two line labels sit here, above the lanes
LANES = {0: (172, "Caller", CALLER), 1: (172 + LANE_H + 24, "Agent", AGENT)}
LANE_BOTTOM = LANES[1][0] + LANE_H
NPK = R - L
PEAKS = {ch: peaks(ch, NPK) for ch in (0, 1)}


def tx(t):
    return L + (t - T0) / DUR * NPK


def base_frame():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    text(d, (MX, MY), "LiveKit’s agent-starter-python, unmodified, default models", FB["head"], INK)
    text(d, (MX, MY + 44), "Hosted run · barge-in · call 1", FB["sub"], MUTE)
    for ch, (y, name, col) in LANES.items():
        d.rounded_rectangle((MX, y - 4, R + 6, y + LANE_H + 4), 10, fill=PANEL)
        text(d, (MX + 12, y + LANE_H // 2 - 22), name, FB["tag"], col)
        mid = y + LANE_H // 2
        for i, v in enumerate(PEAKS[ch]):
            h = max(1, int(v * (LANE_H / 2 - 18)))
            d.line((L + i, mid - h, L + i, mid + h), fill=tuple(int(c * 0.38) for c in col))
    return im


BASE = base_frame()


def caption_at(t):
    return [c for c in CAPTIONS if c[0] - 0.05 <= t <= c[1] + 0.35][-2:]


def frame(t):
    """t is call time."""
    im = BASE.copy()
    d = ImageDraw.Draw(im)
    for ch, (y, _name, col) in LANES.items():
        mid = y + LANE_H // 2
        upto = int((min(t, T1) - T0) / DUR * NPK)
        for i in range(upto):
            h = max(1, int(PEAKS[ch][i] * (LANE_H / 2 - 18)))
            d.line((L + i, mid - h, L + i, mid + h), fill=col)
    # vertical lines with a small label each, placed above the lanes (cut-in label to the left
    # of its line, stop label to the right of its line, so they never meet or cover a waveform)
    if t >= CUT_IN:
        xc = tx(CUT_IN)
        d.line((xc, LABEL_ROW + 4, xc, LANE_BOTTOM + 4), fill=CHAOS, width=4)
        s = "Caller cuts in"
        text(d, (xc - 10 - d.textlength(s, font=FB["lab"]), LABEL_ROW - 6), s, FB["lab"], CHAOS)
    if t >= AGENT_STOPS:
        xs = tx(AGENT_STOPS)
        d.line((xs, LABEL_ROW + 4, xs, LANE_BOTTOM + 4), fill=AMBER, width=4)
        text(d, (xs + 10, LABEL_ROW - 6), "Agent stops", FB["lab"], AMBER)
    px = tx(min(t, T1))
    d.line((px, LANES[0][0] - 8, px, LANE_BOTTOM + 4), fill=(255, 255, 255), width=3)
    top = LANE_BOTTOM + 24
    if LABEL_FROM <= t <= LABEL_TO:
        lines = wrap(d, LABEL, FB["card"], W - 2 * MX - 40)
        bh = 24 + 50 * len(lines)
        d.rounded_rectangle((MX, top, W - MX, top + bh), 14, fill=(40, 34, 20), outline=AMBER, width=3)
        for k, ln in enumerate(lines):
            text(d, (MX + 20, top + 10 + 50 * k), ln, FB["card"], AMBER)
        top += bh + 12
    y = top
    for _a, _b, who, s in caption_at(t):
        col = CALLER if who == "Caller" else AGENT
        tag = who + ":"
        indent = d.textlength(tag + " ", font=FB["cap"])
        lines = wrap(d, s, FB["cap"], W - 2 * MX - indent)
        text(d, (MX, y), tag, FB["cap"], col)
        for ln in lines:
            text(d, (MX + indent, y), ln, FB["cap"], INK)
            y += 48
    return im


def card(hook_lines, sub, big=False):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((MX, 150, MX + 130, 156), fill=CHAOS)
    y = 190
    f = FD["big"] if big else FD["hook"]
    for ln in hook_lines:
        text(d, (MX, y), ln, f, INK)
        y += f.size + 14
    y += 26
    for s, fnt, col in sub:
        for ln in wrap(d, s, fnt, W - 2 * MX):
            text(d, (MX, y), ln, fnt, col)
            y += fnt.size + 14
    return im


TITLE = card(
    ["What a voice agent does", "when you interrupt it"],
    [("LiveKit’s agent-starter-python, unmodified, default models", FB["card"], INK)],
)
END = card(
    ["Callback"],
    [("Chaos testing for voice agents.", FB["card"], INK),
     ("github.com/imshivamb/callback", FB["card"], AGENT),
     ("pip install callback-voice", FB["lab"], MUTE)],
    big=True,
)

TITLE_S, END_S = 2.0, 5.0


def write_video(path):
    wav = OUT / "_audio.wav"
    mono = seg.mean(axis=1)
    fade = int(0.4 * sr)
    mono[-fade:] *= np.linspace(1, 0, fade)
    pad = np.zeros(int(TITLE_S * sr), dtype="float32")
    tail = np.zeros(int(END_S * sr), dtype="float32")
    sf.write(wav, np.concatenate([pad, mono, tail]), sr, subtype="PCM_16")
    cmd = [FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(wav), "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart", "-shortest", str(path)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for _ in range(int(TITLE_S * FPS)):
        p.stdin.write(TITLE.tobytes())
    for i in range(int(DUR * FPS)):
        p.stdin.write(frame(T0 + i / FPS).tobytes())
    for _ in range(int(END_S * FPS)):
        p.stdin.write(END.tobytes())
    p.stdin.close()
    p.wait()
    wav.unlink()


def write_gif(path, a=16.4, b=26.4, width=800, fps=12):
    frames = [frame(a + i / fps).resize((width, int(H * width / W)), Image.LANCZOS) for i in range(int((b - a) * fps))]
    pal = [f.quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=int(1000 / fps), loop=0, optimize=True, disposal=1)


def write_sheet(path):
    """One frame per second of the finished video, in order."""
    total = TITLE_S + DUR + END_S
    shots = []
    for s in range(int(total)):
        t = s + 0.5
        if t < TITLE_S:
            im = TITLE
        elif t < TITLE_S + DUR:
            im = frame(T0 + t - TITLE_S)
        else:
            im = END
        shots.append(im)
    cols, tw, th = 4, 480, 270
    rows = -(-len(shots) // cols)
    sheet = Image.new("RGB", (cols * (tw + 6) + 6, rows * (th + 6) + 6), (60, 60, 66))
    for i, im in enumerate(shots):
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (6 + (i % cols) * (tw + 6), 6 + (i // cols) * (th + 6)))
    sheet.save(path)
    print(len(shots), "frames in the sheet, total", round(total, 1), "s")


def write_social(path):
    """1280x640 repository preview: name, one line, and the two-lane waveform of the same call."""
    im = Image.new("RGB", (1280, 640), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((70, 70, 190, 76), fill=CHAOS)
    d.text((70, 96), "Callback", font=FD["big"], fill=INK)
    d.text((74, 244), "Chaos testing for voice agents", font=FB["card"], fill=MUTE)
    a, b = 16.4, 26.4
    x0, x1 = 70, 1210
    for ch, (y, col) in enumerate(((340, CALLER), (470, AGENT))):
        d.rounded_rectangle((x0 - 10, y - 6, x1 + 10, y + 116), 10, fill=PANEL)
        e = np.abs(seg[int((a - T0) * sr):int((b - T0) * sr), ch])
        n = x1 - x0
        edges = np.linspace(0, len(e), n + 1).astype(int)
        pk = np.minimum(1.0, np.maximum.reduceat(e, edges[:-1])) ** 0.5
        for i, v in enumerate(pk):
            h = max(1, int(v * 48))
            d.line((x0 + i, y + 55 - h, x0 + i, y + 55 + h), fill=col)
    xc = x0 + (CUT_IN - a) / (b - a) * (x1 - x0)
    xs = x0 + (AGENT_STOPS - a) / (b - a) * (x1 - x0)
    d.line((xc, 334, xc, 586), fill=CHAOS, width=3)
    d.line((xs, 334, xs, 586), fill=AMBER, width=3)
    d.text((x0, 598), "caller", font=FB["lab"], fill=CALLER)
    d.text((x0 + 110, 598), "agent", font=FB["lab"], fill=AGENT)
    im.save(path)


if __name__ == "__main__":
    what = sys.argv[3:] or ["video", "gif", "still", "social", "sheet"]
    if "video" in what:
        write_video(OUT / "callback-livekit-starter-barge-in.mp4")
    if "gif" in what:
        write_gif(OUT / "callback-barge-in.gif")
    if "still" in what:
        frame(19.5).save(OUT / "callback-barge-in-still.png")
    if "social" in what:
        write_social(OUT / "social-preview-1280x640.png")
    if "sheet" in what:
        write_sheet(OUT / "_contact-sheet.png")
    print("text outside the 5% margin:", sorted(set(VIOLATIONS)) or "none")
    for n in ("social-preview-1280x640.png", "callback-livekit-starter-barge-in.mp4", "callback-barge-in.gif", "callback-barge-in-still.png"):
        if (OUT / n).exists():
            print(n, (OUT / n).stat().st_size // 1024, "KB")
