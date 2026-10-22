#!/usr/bin/env python3
from pathlib import Path
import math, os, shutil, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "05-dark-video"
FRAMES = OUT / "frames"
W = H = 1080
FPS = 30
DUR = 6.0
N = int(FPS * DUR)
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
MONO_FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

def font(size, mono=False):
    return ImageFont.truetype(MONO_FONT if mono else FONT, size)

def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def lerp(a, b, t):
    return a + (b - a) * t

def bg():
    y, x = np.mgrid[0:H, 0:W]
    cx, cy = W * .5, H * .42
    d = np.sqrt(((x - cx) / W) ** 2 + ((y - cy) / H) ** 2)
    base = np.zeros((H, W, 3), dtype=np.float32)
    base[..., 0] = 7 + 10 * np.clip(1 - d * 2.2, 0, 1)
    base[..., 1] = 6 + 6 * np.clip(1 - d * 2.2, 0, 1)
    base[..., 2] = 9 + 5 * np.clip(1 - d * 2.2, 0, 1)
    # warm bloom bottom right
    d2 = np.sqrt(((x - W * .86) / W) ** 2 + ((y - H * .76) / H) ** 2)
    glow = np.clip(1 - d2 * 3.2, 0, 1) ** 2
    base[..., 0] += glow * 55
    base[..., 1] += glow * 14
    base[..., 2] += glow * 3
    # vignette
    v = np.clip(1 - d * 1.05, 0, 1)[..., None]
    base *= .45 + .55 * v
    return Image.fromarray(np.uint8(np.clip(base, 0, 255)))

def text_layer(size, xy, s, f, fill, anchor="mm"):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, s, font=f, fill=fill, anchor=anchor)
    return layer

def glow_text(img, xy, s, f, fill=(255, 255, 255, 255), glow=(255, 78, 24), blur=18, anchor="mm"):
    g = text_layer((W, H), xy, s, f, glow + (255,), anchor)
    g = g.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(g)
    img.alpha_composite(text_layer((W, H), xy, s, f, fill, anchor))
    return img

def panel(draw, box, fill=(255, 255, 255, 12), outline=(255, 255, 255, 34), r=18, w=2):
    draw.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=w)

def main():
    if FRAMES.exists(): shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)
    cover = None
    f_big = font(176, mono=True)
    f_title = font(62)
    f_sub = font(24)
    f_small = font(18, mono=True)
    f_mid = font(34)

    for i in range(N):
        t = i / FPS
        img = bg().convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # grid
        for x in range(0, W, 72):
            d.line([(x, 0), (x, H)], fill=(255, 255, 255, 7), width=1)
        for y in range(0, H, 72):
            d.line([(0, y), (W, y)], fill=(255, 255, 255, 7), width=1)

        # top chrome
        d.text((54, 48), "TRACE / DEV TOOL", font=f_small, fill=(255, 255, 255, 120))
        d.text((W - 54, 48), "00:06 / 1080P", font=f_small, fill=(255, 255, 255, 90), anchor="ra")
        d.line([(54, 86), (W - 54, 86)], fill=(255, 255, 255, 22), width=1)

        # scene 1 title
        a1 = ease((t - 0.05) / .45) * (1 - ease((t - 1.55) / .35))
        if a1 > .01:
            title = text_layer((W, H), (W/2, 300), "一次 Agent 开发任务", f_title, (255, 255, 255, int(255*a1)))
            img.alpha_composite(title)
            sub = text_layer((W, H), (W/2, 366), "真实 trace · 20 events · 4596 tokens", f_sub, (255, 210, 190, int(220*a1)))
            img.alpha_composite(sub)
            # growing line
            wline = int(480 * ease((t - .35) / .8))
            d.line([(W/2 - wline/2, 432), (W/2 + wline/2, 432)], fill=(255, 91, 31, int(255*a1)), width=3)

        # scene 2 big number
        a2 = ease((t - 1.15) / .4) * (1 - ease((t - 3.15) / .35))
        if a2 > .01:
            val = int(4596 * ease((t - 1.25) / 1.45))
            # ring
            cx, cy, r = W/2, H*.48, 238
            d.arc([cx-r, cy-r, cx+r, cy+r], start=-90, end=-90 + 360*ease((t-1.2)/1.7), fill=(255, 86, 30, int(180*a2)), width=2)
            # faint ring
            d.arc([cx-r, cy-r, cx+r, cy+r], start=0, end=359, fill=(255, 255, 255, int(18*a2)), width=1)
            glow_text(img, (W/2, H*.48 - 18), f"{val:,}", f_big, (255, 255, 255, int(255*a2)), (255, 66, 18), 22)
            d.text((W/2, H*.48 + 112), "TOKENS · 3 LLM CALLS", font=f_small, fill=(255, 160, 120, int(210*a2)), anchor="mm")

        # scene 3 cards
        a3 = ease((t - 2.85) / .45) * (1 - ease((t - 4.55) / .35))
        if a3 > .01:
            cards = [("3", "LLM CALLS"), ("3", "TOOL CALLS"), ("0", "EXIT CODE")]
            for k, (num, lab) in enumerate(cards):
                x = 150 + k * 285
                y = 690 + (1 - ease((t - 2.9 - k*.08) / .5)) * 30
                panel(d, [x, y, x+250, y+112], (255,255,255,int(10*a3)), (255,255,255,int(40*a3)))
                d.text((x+22, y+22), num, font=font(44, mono=True), fill=(255, 120, 64, int(255*a3)))
                d.text((x+22, y+82), lab, font=f_small, fill=(255, 255, 255, int(150*a3)))
            # small bars
            for k, h in enumerate([76, 48, 24]):
                x = 150 + k * 285
                d.rectangle([x+200, 780-h, x+208, 780], fill=(255, 92, 36, int(160*a3)))

        # scene 4 JSON
        a4 = ease((t - 4.35) / .45) * (1 - ease((t - 5.72) / .3))
        if a4 > .01:
            d.text((96, 290), "数据真的跑出来了", font=font(38), fill=(255,255,255,int(255*a4)))
            d.text((96, 344), "run_python → exit 0 → JSON", font=f_small, fill=(255,170,130,int(200*a4)))
            rows = [
                ('A', '2', '40.0', '20.0'),
                ('B', '2', '60.0', '30.0'),
                ('C', '1', '50.0', '50.0'),
            ]
            for k, (cat, cnt, total, avg) in enumerate(rows):
                y = 430 + k * 78
                panel(d, [96, y, 984, y+58], (255,255,255,int(9*a4)), (255,255,255,int(30*a4)), 12, 1)
                d.text((122, y+29), cat, font=font(28, mono=True), fill=(255,120,64,int(255*a4)), anchor="lm")
                d.text((196, y+29), f"count {cnt}", font=f_small, fill=(255,255,255,int(170*a4)), anchor="lm")
                d.text((410, y+29), f"sum {total}", font=f_small, fill=(255,255,255,int(120*a4)), anchor="lm")
                d.text((620, y+29), f"avg {avg}", font=f_small, fill=(255,255,255,int(120*a4)), anchor="lm")
                # mini bar
                bw = int(180 * (float(avg) / 50))
                d.rectangle([790, y+34, 790+bw, y+40], fill=(255, 87, 32, int(190*a4)))

        # closing
        a5 = ease((t - 5.72) / .22)
        if a5 > .01:
            d.text((W/2, H*.52), "AGENT DATA FLOW", font=font(34), fill=(255,255,255,int(230*a5)), anchor="mm")
            d.text((W/2, H*.52+46), "one run · one sequence · every packet visible", font=f_small, fill=(255,160,120,int(180*a5)), anchor="mm")

        # scanlines / grain
        scan = Image.new("RGBA", (W, H), (0,0,0,0))
        sd = ImageDraw.Draw(scan)
        for y in range(0, H, 4):
            sd.line([(0,y),(W,y)], fill=(0,0,0,12), width=1)
        img.alpha_composite(scan)

        img.alpha_composite(ov)
        frame = img.convert("RGB")
        frame.save(FRAMES / f"{i:04d}.png", quality=90)
        if cover is None and t >= 2.72:
            cover = frame.copy()

    if cover is not None:
        cover.save(OUT / "cover.png")

    exe = imageio_ffmpeg.get_ffmpeg_exe()
    mp4 = OUT / "demo.mp4"
    cmd = [exe, "-y", "-framerate", str(FPS), "-i", str(FRAMES / "%04d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(FRAMES)
    print("video", mp4, mp4.stat().st_size, "cover", OUT/"cover.png")

if __name__ == "__main__":
    main()
