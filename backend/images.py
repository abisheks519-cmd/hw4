"""Compressed product images for fast page loads.

For every JPEG in products/, make two WebP copies in products/optimized/:
  <name>-480.webp  the product page image (the originals are about 457px, so this is full size)
  <name>-320.webp  product cards, chat cards, cart and compare thumbnails

and, for the storefront design, two "cutout" copies with the photo background removed
(transparent WebP), so every product sits on the same stage whatever its photo background:
  <name>-cut-640.webp, <name>-cut-320.webp
The background is the black or white area connected to the photo's edges. A cutout is only kept
when it is stable (removing a little more or less background barely changes it); otherwise the
product keeps its original photo.

The originals are left untouched. Runs when the API starts and only redoes images whose
JPEG is newer than its WebP copy, so it's quick after the first run. Also runnable by hand:
    python images.py
"""

from pathlib import Path

from db import OPTIMIZED_DIR, PRODUCTS_DIR

SIZES = {"480": 480, "320": 320}
CUT_SIZES = {"cut-640": 640, "cut-320": 320}
QUALITY = 78
MARK = (1, 254, 3)  # temporary fill colour for background pixels
# (tolerance on black backgrounds, tolerance on white backgrounds), gentlest last
LEVELS = [(40, 60), (20, 30), (10, 15), (5, 8)]
# Photos whose cutout passes the checks but still looks rough on review (this one has white
# patches along the garment's edge in the photo itself), so they keep the original photo.
KEEP_PHOTO = {"basic-hoodie-big-yale"}


def _background_mask(im, tol_black: int, tol_white: int):
    """White where the product is, black where the edge-connected background is."""
    from PIL import Image, ImageChops, ImageDraw

    w, h = im.size
    work = im.copy()
    seeds = []
    for d in (0, 4):  # the edge, and a few pixels in (some photos have a thin frame)
        seeds += [(x, d) for x in range(0, w, 3)] + [(x, h - 1 - d) for x in range(0, w, 3)]
        seeds += [(d, y) for y in range(0, h, 3)] + [(w - 1 - d, y) for y in range(0, h, 3)]
    for xy in seeds:
        px = work.getpixel(xy)
        if px == MARK:
            continue
        if max(px) < 45:
            ImageDraw.floodfill(work, xy, MARK, thresh=tol_black)
        elif min(px) > 205:
            ImageDraw.floodfill(work, xy, MARK, thresh=tol_white)
    diff = ImageChops.difference(work, Image.new("RGB", (w, h), MARK)).convert("L")
    return diff.point(lambda v: 255 if v else 0)


def cutout(src: Path):
    """The product on a transparent square canvas, or None if the background can't be removed cleanly."""
    from PIL import Image, ImageFilter, ImageStat

    with Image.open(src) as raw:
        im = raw.convert("RGB")
    im.thumbnail((720, 720))
    masks = [_background_mask(im, *lvl) for lvl in LEVELS]
    cover = [ImageStat.Stat(m).mean[0] / 255 for m in masks]
    # Use the strongest removal that a gentler pass agrees with; if none agree, the product
    # blends into its background (e.g. light gray on white), so keep the photo instead.
    pick = next((i for i in range(3) if cover[i + 1] - cover[i] <= 0.02 and cover[3] - cover[i] <= 0.04), None)
    if pick is None or not 0.12 < cover[pick] < 0.92:
        return None
    alpha = masks[pick].filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.7))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    box = alpha.point(lambda v: 255 if v > 40 else 0).getbbox()
    if box is None:
        return None
    out = out.crop(box)
    side = round(max(out.size) * 1.08)  # a little breathing room around the product
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(out, ((side - out.width) // 2, (side - out.height) // 2), out)
    return canvas


def optimize_all() -> dict:
    """Create any missing or out-of-date WebP copies. Returns before/after byte totals."""
    try:
        from PIL import Image
    except ImportError:  # Pillow not installed: the site serves the original JPEGs instead.
        return {"optimized": False}
    OPTIMIZED_DIR.mkdir(exist_ok=True)
    totals = {"optimized": True, "images": 0, "original_bytes": 0, "large_bytes": 0, "thumb_bytes": 0}
    for src in sorted(PRODUCTS_DIR.glob("*.jpg")):
        totals["images"] += 1
        totals["original_bytes"] += src.stat().st_size
        for label, width in SIZES.items():
            out = OPTIMIZED_DIR / f"{src.stem}-{label}.webp"
            if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
                with Image.open(src) as im:
                    im = im.convert("RGB")
                    if im.width > width:
                        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
                    im.save(out, "WEBP", quality=QUALITY, method=6)
            totals["large_bytes" if label == "480" else "thumb_bytes"] += out.stat().st_size
        cut_files = [OPTIMIZED_DIR / f"{src.stem}-{label}.webp" for label in CUT_SIZES]
        marker = OPTIMIZED_DIR / f"{src.stem}.nocut"  # remembers photos that can't be cut out
        if src.stem in KEEP_PHOTO:
            marker.touch()
            for f in cut_files:
                f.unlink(missing_ok=True)
        elif any(not f.exists() or f.stat().st_mtime < src.stat().st_mtime for f in cut_files) and not (
            marker.exists() and marker.stat().st_mtime >= src.stat().st_mtime
        ):
            cut = cutout(src)
            if cut is None:
                marker.touch()
                for f in cut_files:
                    f.unlink(missing_ok=True)
            else:
                for f, width in zip(cut_files, CUT_SIZES.values()):
                    img = cut.resize((width, width), Image.LANCZOS) if cut.width > width else cut
                    img.save(f, "WEBP", quality=QUALITY, method=6)
        totals["cutouts"] = totals.get("cutouts", 0) + int(cut_files[0].exists())
    return totals


if __name__ == "__main__":
    t = optimize_all()
    if not t["optimized"]:
        print("Pillow isn't installed: pip install pillow")
    else:
        kb = lambda b: f"{b / 1024:,.0f} KB"
        print(f"{t['images']} images: originals {kb(t['original_bytes'])}, "
              f"product-page WebP {kb(t['large_bytes'])}, card thumbnails {kb(t['thumb_bytes'])}, "
              f"{t['cutouts']} background-free cutouts")
