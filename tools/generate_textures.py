#!/usr/bin/env python3
"""
Membuat semua texture resource pack Valence (panel menu, logo, ikon) beserta
font JSON dan definisi item. Hasilnya ke oraxen-pack/assets/valence/.

    pip install pillow numpy
    python tools/generate_textures.py            # tulis pack + docs/preview-menu.png
    python tools/generate_textures.py --debug    # tambah preview dengan garis bantu slot

Mau ganti warna/tata letak? Ubah PAL dan fungsi build_panel() lalu jalankan ulang.
Font: Inter (SIL OFL). Ubah INTER kalau path-nya beda di komputermu.
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "oraxen-pack", "assets", "valence")
DOCS = os.path.join(ROOT, "docs")
INTER = os.environ.get("VALENCE_FONT_DIR", "/usr/share/fonts/opentype/inter") + "/Inter-{}.otf"

SS = 4  # supersampling saat menggambar

PAL = {
    "ink": "#0a1d4a",
    "deep": "#143a8c",
    "royal": "#2a63d0",
    "azure": "#4a86ee",
    "sky": "#9fc4fb",
    "mist": "#e4edfc",
    "white": "#ffffff",
}

# Karakter di font valence:ui (area private-use, tidak bentrok dengan font lain)
CH_MENU = ""
CH_LOGO = ""
SPACES = {1: "", 2: "", 4: "", 8: "", 16: "", 32: "", 64: "", 128: ""}

# Ukuran menu 4 baris (generic_54, rows=4): 176 x 186 GUI px
GUI_W, GUI_H = 176, 186
PANEL_TEX = 2  # texel per GUI px


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def rgba(h, a=255):
    return rgb(h) + (a,)


def font(weight, px):
    return ImageFont.truetype(INTER.format(weight), max(1, int(round(px))))


CAP = 0.7275  # tinggi huruf kapital Inter relatif terhadap em


class Art:
    """Kanvas dengan satuan sendiri (GUI px atau texel), digambar 4x lalu diperkecil."""

    def __init__(self, gw, gh, tex):
        self.gw, self.gh, self.tex = gw, gh, tex
        self.k = tex * SS
        self.w, self.h = int(gw * self.k), int(gh * self.k)
        self.img = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))

    # -- dasar
    def mask(self):
        return Image.new("L", (self.w, self.h), 0)

    def composite(self, mask, fill):
        if isinstance(fill, tuple):
            layer = Image.new("RGBA", (self.w, self.h), fill)
        else:
            layer = fill.copy()
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        self.img = Image.alpha_composite(self.img, layer)

    def gfill(self, box, stops, mode="v"):
        """Gradien yang hanya mengisi `box` (satuan kanvas); selebihnya transparan."""
        x0, y0, x1, y1 = [v * self.k for v in box]
        w, h = max(1, int(round(x1 - x0))), max(1, int(round(y1 - y0)))
        if mode == "v":
            t = np.tile(np.linspace(0, 1, h)[:, None], (1, w))
        elif mode == "h":
            t = np.tile(np.linspace(0, 1, w)[None, :], (h, 1))
        else:
            yy, xx = np.mgrid[0:h, 0:w]
            t = (xx / max(1, w - 1) + yy / max(1, h - 1)) / 2
        ts = [s[0] for s in stops]
        cols = np.array([rgb(s[1]) for s in stops], float)
        arr = np.zeros((h, w, 4), np.uint8)
        arr[..., 3] = 255
        for c in range(3):
            arr[..., c] = np.interp(t, ts, cols[:, c])
        g = Image.fromarray(arr, "RGBA")
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        layer.paste(g, (int(round(x0)), int(round(y0))))
        return layer

    # -- bentuk
    def rrect(self, box, r, fill, outline=None, ow=0.0):
        k = self.k
        x0, y0, x1, y1 = [v * k for v in box]
        m = self.mask()
        ImageDraw.Draw(m).rounded_rectangle((x0, y0, x1, y1), radius=r * k, fill=255)
        self.composite(m, fill)
        if outline is not None and ow > 0:
            inner = self.mask()
            ImageDraw.Draw(inner).rounded_rectangle(
                (x0 + ow * k, y0 + ow * k, x1 - ow * k, y1 - ow * k),
                radius=max(0, r - ow) * k, fill=255)
            self.composite(ImageChops.subtract(m, inner), outline)

    def rect(self, box, fill):
        self.rrect(box, 0, fill)

    def shape(self, ops, fill):
        """ops(draw, s): menggambar di mask; 255 = isi, 0 = lubang."""
        m = self.mask()
        ops(ImageDraw.Draw(m), lambda v: v * self.k)
        self.composite(m, fill)

    def dots(self, pts, r, alpha_fn):
        m = self.mask()
        d = ImageDraw.Draw(m)
        k = self.k
        for (x, y) in pts:
            a = alpha_fn(x, y)
            d.ellipse(((x - r) * k, (y - r) * k, (x + r) * k, (y + r) * k), fill=a)
        self.composite(m, (255, 255, 255, 255))

    def text_width(self, s, weight, cap, tracking):
        f = font(weight, cap * self.k / CAP)
        return sum(f.getlength(c) for c in s) / self.k + tracking * (len(s) - 1)

    def text(self, x, cy, s, weight, cap, fill, tracking=0.0, anchor="l"):
        k = self.k
        f = font(weight, cap * k / CAP)
        wtot = self.text_width(s, weight, cap, tracking)
        if anchor == "r":
            x -= wtot
        elif anchor == "c":
            x -= wtot / 2
        base = (cy + cap / 2) * k
        m = self.mask()
        d = ImageDraw.Draw(m)
        cx = x * k
        for c in s:
            d.text((cx, base), c, font=f, fill=255, anchor="ls")
            cx += f.getlength(c) + tracking * k
        self.composite(m, fill)
        return wtot

    def line(self, pts, width, fill):
        m = self.mask()
        k = self.k
        ImageDraw.Draw(m).line([(x * k, y * k) for x, y in pts], fill=255,
                               width=max(1, int(width * k)), joint="curve")
        self.composite(m, fill)

    def done(self):
        return self.img.resize((int(self.gw * self.tex), int(self.gh * self.tex)), Image.LANCZOS)


# --------------------------------------------------------------------------- panel menu

CARD_X = (44, 80, 116)            # kolom item slot 11, 13, 15 (x kiri item)
CARD_LABELS = ("TERAKHIR", "KOTA", "BAJU")
SLOT_ITEM = {11: (44, 36), 13: (80, 36), 15: (116, 36), 31: (80, 72)}
HEAD = 91                          # batas bagian biru / baki inventaris


def mark_poly(x0, y0, s):
    pts = [(0, 0), (2.7, 0), (4.5, 5.4), (6.3, 0), (9, 0), (5.9, 9), (3.1, 9)]
    return [(x0 + x * s, y0 + y * s) for x, y in pts]


def build_panel():
    a = Art(GUI_W, GUI_H, PANEL_TEX)

    # bagian atas: biru tua ke biru royal
    a.rect((0, 0, GUI_W, HEAD), a.gfill((0, 0, GUI_W, HEAD),
           [(0, PAL["ink"]), (0.6, PAL["deep"]), (1, PAL["royal"])], "v"))
    # titik halus, makin pudar ke bawah
    pts = [(x, y) for x in range(2, GUI_W, 4) for y in range(2, HEAD, 4)]
    a.dots(pts, 0.28, lambda x, y: int(46 * (1 - 0.75 * y / HEAD)))

    # baki bawah: biru sangat muda ke putih
    a.rect((0, HEAD, GUI_W, GUI_H), a.gfill((0, HEAD, GUI_W, GUI_H),
           [(0, PAL["mist"]), (1, "#f8fbff")], "v"))
    # garis aksen gradasi biru -> putih di sambungan
    a.rect((0, HEAD, GUI_W, HEAD + 1), a.gfill((0, HEAD, GUI_W, HEAD + 1),
           [(0, PAL["royal"]), (1, PAL["white"])], "h"))

    # header: tanda V + nama + keterangan kanan
    a.shape(lambda d, s: d.polygon([(s(x), s(y)) for x, y in mark_poly(8, 3.6, 0.9)], fill=255),
            a.gfill((8, 3.6, 16.1, 11.7), [(0, PAL["white"]), (1, PAL["sky"])], "d"))
    wm_w = a.text_width("VALENCE", "ExtraBold", 5.2, 1.15)
    a.text(20.2, 7.7, "VALENCE", "ExtraBold", 5.2,
           a.gfill((20.2, 0, 20.2 + wm_w, 16), [(0, PAL["white"]), (1, PAL["sky"])], "h"), 1.15)
    a.text(168, 7.7, "PILIH LOKASI", "SemiBold", 3.5, rgba(PAL["sky"], 235), 0.75, "r")
    a.rect((8, 15.5, 168, 16), (255, 255, 255, 48))
    a.text(8, 21.2, "Pilih tempat kamu mulai.", "Medium", 3.2, rgba("#b9d2fb", 225), 0.15)

    # tiga kartu pilihan
    for i, ix in enumerate(CARD_X):
        a.rrect((ix - 8, 26, ix + 24, 64), 3.4, (255, 255, 255, 22),
                outline=(255, 255, 255, 70), ow=0.6)
        a.text(ix - 5.0, 30.0, "0%d" % (i + 1), "SemiBold", 2.6, rgba(PAL["sky"], 210), 0.35)
        a.text(ix + 8, 58.6, CARD_LABELS[i], "SemiBold", 3.3, (255, 255, 255, 238), 0.5, "c")

    # tombol SPAWN
    a.rrect((44, 71, 132, 89), 5, a.gfill((44, 71, 132, 89),
            [(0, PAL["white"]), (1, "#a9c9fb")], "h"))
    a.text(50.5, 80, "SPAWN", "ExtraBold", 4.0, rgba(PAL["ink"]), 0.9)
    for cx in (115.5, 121.5):
        a.line([(cx - 1.5, 77.4), (cx + 1.5, 80), (cx - 1.5, 82.6)], 0.9, rgba(PAL["ink"], 215))

    # slot inventaris pemain (posisi vanilla untuk menu 4 baris)
    for ry in (102, 120, 138, 160):
        for c in range(9):
            x = 7 + 18 * c
            a.rrect((x + 0.4, ry + 0.4, x + 17.6, ry + 17.6), 2.2, (255, 255, 255, 190),
                    outline=rgba("#b6c8ea"), ow=0.6)
    return a.done()


# --------------------------------------------------------------------------- logo judul

def build_logo():
    a = Art(640, 96, 1)
    s = 8.2
    a.shape(lambda d, sc: d.polygon([(sc(x), sc(y)) for x, y in mark_poly(6, 11, s)], fill=255),
            a.gfill((6, 11, 6 + 9 * s, 11 + 9 * s), [(0, PAL["white"]), (1, PAL["sky"])], "d"))
    x0 = 6 + 9 * s + 24
    wm_w = a.text_width("VALENCE", "ExtraBold", 56, 9)
    a.text(x0, 48, "VALENCE", "ExtraBold", 56,
           a.gfill((x0, 0, x0 + wm_w, 96), [(0, PAL["white"]), (0.55, PAL["sky"]), (1, PAL["azure"])], "h"), 9)
    img = a.done()
    bbox = img.getchannel("A").getbbox()
    return img.crop((bbox[0], 0, bbox[2], 96))


# --------------------------------------------------------------------------- ikon item (32x32)

def icon(kind, active):
    a = Art(32, 32, 1)
    navy = rgba("#0d2a66")
    if kind == "spawn":
        a.shape(lambda d, s: d.ellipse((s(0.8), s(0.8), s(31.2), s(31.2)), fill=255),
                a.gfill((0, 0, 32, 32), [(0, PAL["ink"]), (1, PAL["royal"])], "d"))
        glyph_fill = (255, 255, 255, 255)
    elif active:
        a.shape(lambda d, s: d.ellipse((s(0.8), s(0.8), s(31.2), s(31.2)), fill=255),
                a.gfill((0, 0, 32, 32), [(0, PAL["white"]), (1, "#6ea3f5")], "d"))
        glyph_fill = navy
    else:
        m = a.mask()
        k = a.k
        d = ImageDraw.Draw(m)
        d.ellipse((0.9 * k, 0.9 * k, 31.1 * k, 31.1 * k), fill=255)
        d.ellipse((2.0 * k, 2.0 * k, 30.0 * k, 30.0 * k), fill=0)
        a.composite(m, (200, 220, 255, 95))
        glyph_fill = (214, 228, 255, 240)

    def pin(d, s):
        d.ellipse((s(8.5), s(5.5), s(23.5), s(20.5)), fill=255)
        d.polygon([(s(9.4), s(16.8)), (s(22.6), s(16.8)), (s(16), s(27.6))], fill=255)
        d.ellipse((s(13), s(10), s(19), s(16)), fill=0)

    def city(d, s):
        d.rectangle((s(6), s(14), s(12.5), s(26.5)), fill=255)
        d.rectangle((s(12.5), s(6.5), s(19.5), s(26.5)), fill=255)
        d.rectangle((s(19.5), s(17), s(26), s(26.5)), fill=255)
        d.rectangle((s(4), s(26.5), s(28), s(28.2)), fill=255)
        for x in (14.2, 16.9):
            for y in (9.5, 13.5, 17.5):
                d.rectangle((s(x), s(y), s(x + 1.6), s(y + 1.6)), fill=0)
        for y in (17.5, 21.5):
            d.rectangle((s(8.1), s(y), s(9.7), s(y + 1.6)), fill=0)
        d.rectangle((s(21.7), s(20), s(23.3), s(21.6)), fill=0)

    def shirt(d, s):
        pts = [(9, 8), (13, 6), (14.5, 6.2), (16, 8.4), (17.5, 6.2), (19, 6), (23, 8), (26.5, 13),
               (23.5, 15), (21.5, 13.3), (21.5, 26), (10.5, 26), (10.5, 13.3), (8.5, 15), (5.5, 13)]
        d.polygon([(s(x), s(y)) for x, y in pts], fill=255)

    def arrow(d, s):
        d.rectangle((s(8), s(14.4), s(19), s(17.6)), fill=255)
        d.polygon([(s(17.5), s(9)), (s(24.5), s(16)), (s(17.5), s(23))], fill=255)

    a.shape({"last": pin, "city": city, "outfit": shirt, "spawn": arrow}[kind], glyph_fill)
    return a.done()


ICONS = [("icon_last", "last", False), ("icon_last_on", "last", True),
         ("icon_city", "city", False), ("icon_city_on", "city", True),
         ("icon_outfit", "outfit", False), ("icon_spawn", "spawn", False)]


# --------------------------------------------------------------------------- tulis pack

def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)


def preview(panel, debug):
    k = 4
    bg = Image.new("RGBA", (GUI_W * k, GUI_H * k), (44, 44, 44, 255))
    bg.alpha_composite(panel.resize((GUI_W * k, GUI_H * k), Image.NEAREST))
    for slot, (x, y) in SLOT_ITEM.items():
        name, kind, act = {11: ICONS[1], 13: ICONS[2], 15: ICONS[4], 31: ICONS[5]}[slot]
        ic = icon(kind, act).resize((16 * k, 16 * k), Image.NEAREST)
        bg.alpha_composite(ic, (x * k, y * k))
    d = ImageDraw.Draw(bg)
    d.text((8 * k, 92 * k), "Inventory", font=ImageFont.truetype(INTER.format("Regular"), 8 * k), fill=(64, 64, 64, 255))
    if debug:
        for r in range(4):
            for c in range(9):
                x, y = 8 + 18 * c, 18 + 18 * r
                d.rectangle(((x - 1) * k, (y - 1) * k, (x + 17) * k, (y + 17) * k), outline=(255, 0, 120, 160))
        for ry in (103, 121, 139, 161):
            for c in range(9):
                x = 8 + 18 * c
                d.rectangle(((x - 1) * k, (ry - 1) * k, (x + 17) * k, (ry + 17) * k), outline=(255, 0, 120, 160))
    return bg


def main():
    debug = "--debug" in sys.argv
    panel = build_panel()
    logo = build_logo()

    os.makedirs(os.path.join(OUT, "textures", "font"), exist_ok=True)
    panel.save(os.path.join(OUT, "textures", "font", "menu.png"), optimize=True)
    logo.save(os.path.join(OUT, "textures", "font", "logo.png"), optimize=True)

    # font: spasi negatif + dua gambar
    providers = [
        {"type": "space", "advances": {SPACES[n]: -n for n in SPACES}},
        # ascent 13 = sisi atas gambar tepat di sisi atas jendela menu (judul vanilla ada di y=6)
        {"type": "bitmap", "file": "valence:font/menu.png", "ascent": 13, "height": GUI_H, "chars": [CH_MENU]},
        {"type": "bitmap", "file": "valence:font/logo.png", "ascent": 8, "height": 10, "chars": [CH_LOGO]},
    ]
    write(os.path.join(OUT, "font", "ui.json"), json.dumps({"providers": providers}, indent=2) + "\n")

    for name, kind, act in ICONS:
        p = os.path.join(OUT, "textures", "item", name + ".png")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        icon(kind, act).save(p, optimize=True)
        write(os.path.join(OUT, "models", "item", name + ".json"), json.dumps(
            {"parent": "minecraft:item/generated", "textures": {"layer0": "valence:item/" + name}}, indent=2) + "\n")
        write(os.path.join(OUT, "items", name + ".json"), json.dumps(
            {"model": {"type": "minecraft:model", "model": "valence:item/" + name}}, indent=2) + "\n")

    os.makedirs(DOCS, exist_ok=True)
    preview(panel, False).convert("RGB").save(os.path.join(DOCS, "preview-menu.png"))
    if debug:
        preview(panel, True).convert("RGB").save(os.path.join(DOCS, "preview-menu-debug.png"))
    print("selesai ->", OUT)


if __name__ == "__main__":
    main()
