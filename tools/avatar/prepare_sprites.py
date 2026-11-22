"""Builds sprite-avatar assets for the desktop app from aligned source images.

Usage (from the repo root):
    tools/avatar/.venv/bin/python tools/avatar/prepare_sprites.py characters/*/avatar.yaml

Each config lives in characters/<id>/avatar.yaml; the sprite id is the folder name and
source images are read from characters/<id>/art/ (or `source_dir`, relative to it).

Two modes:
- static (only `base`): one image. Background removed, cropped, downscaled.
- layered (`base`, `blink`, `mouth_open`, `expressions`, `regions`):
  1. Validates that every source image has the same size and that pixels outside the
     face regions barely change (i.e. variants were inpainted, not regenerated).
  2. Removes the background of the base image once (rembg) and crops to the character.
  3. Exports feathered eye/mouth crops per source image.
Both write a manifest.json that the renderer loads (apps/desktop/src/renderer/src/avatar/sprite/).
"""

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "apps/desktop/src/renderer/src/avatar/sprite/assets"
LAYERED_KEYS = ("blink", "mouth_open", "expressions", "regions")
DEFAULT_MAX_HEIGHT = 1600  # static sprites only; layered regions are in source pixels
MANIFEST_VERSION = 1
CHANGE_THRESHOLD = 30  # summed RGB difference that counts as "changed"
MAX_CHANGE_OUTSIDE_FACE = 0.01  # fraction of pixels; above this the image is misaligned
CROP_MARGIN = 16
WEBP_QUALITY = 92


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def box(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def offset(self, dx: int, dy: int) -> "Rect":
        return Rect(self.x - dx, self.y - dy, self.width, self.height)

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


def load_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "base" not in config:
        sys.exit(f"{path}: missing key 'base'")
    present = [key for key in LAYERED_KEYS if key in config]
    if present and len(present) != len(LAYERED_KEYS):
        missing = sorted(set(LAYERED_KEYS) - set(present))
        sys.exit(f"{path}: layered avatars also need: {', '.join(missing)}")
    return config


def flatten(image: Image.Image) -> Image.Image:
    """RGB on white. Transparent areas would otherwise turn black (and confuse rembg)."""
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(canvas, rgba).convert("RGB")
    return image.convert("RGB")


def load_sources(source_dir: Path, names: set[str]) -> dict[str, Image.Image]:
    images = {}
    for name in sorted(names):
        path = source_dir / f"{name}.png"
        if not path.exists():
            sys.exit(f"Missing source image: {path}")
        images[name] = flatten(Image.open(path))
    sizes = {img.size for img in images.values()}
    if len(sizes) != 1:
        sys.exit(f"All source images must have the same size, got: {sizes}")
    return images


def check_alignment(images: dict[str, Image.Image], base: str, regions: list[Rect]) -> None:
    reference = np.asarray(images[base], dtype=np.int16)
    outside = np.ones(reference.shape[:2], dtype=bool)
    for rect in regions:
        x0, y0, x1, y1 = rect.box
        outside[y0:y1, x0:x1] = False
    for name, image in images.items():
        changed = (
            np.abs(np.asarray(image, dtype=np.int16) - reference).sum(axis=2) > CHANGE_THRESHOLD
        )
        fraction = changed[outside].mean()
        status = "ok" if fraction <= MAX_CHANGE_OUTSIDE_FACE else "MISALIGNED"
        print(f"  {name:16} {fraction * 100:5.2f}% changed outside face  {status}")
        if fraction > MAX_CHANGE_OUTSIDE_FACE:
            sys.exit(f"'{name}' differs outside the face regions; regenerate it by inpainting.")


def remove_background(image: Image.Image, model: str) -> Image.Image:
    from rembg import new_session, remove  # imported lazily: slow and heavy

    print(f"  removing background with {model}…")
    result = remove(image, session=new_session(model))
    return result if isinstance(result, Image.Image) else Image.open(result)


def character_bounds(cutout: Image.Image, max_aspect: float | None = None) -> Rect:
    bbox = cutout.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
    if bbox is None:
        sys.exit("Background removal left nothing; is the character visible?")
    left, top, right, bottom = bbox
    left, top = max(0, left - CROP_MARGIN), max(0, top - CROP_MARGIN)
    right = min(cutout.width, right + CROP_MARGIN)
    bottom = min(cutout.height, bottom + CROP_MARGIN)
    if max_aspect:  # very tall art (full body): keep the top part, where the face is
        bottom = min(bottom, top + round((right - left) * max_aspect))
    return Rect(left, top, right - left, bottom - top)


def feather_mask(width: int, height: int, feather: int) -> Image.Image:
    """Alpha ramp from 0 at the edges to 255 at `feather` pixels inside."""
    ramp_x = np.minimum(np.arange(width), np.arange(width)[::-1]) / max(feather, 1)
    ramp_y = np.minimum(np.arange(height), np.arange(height)[::-1]) / max(feather, 1)
    alpha = np.clip(np.minimum.outer(ramp_y, ramp_x), 0, 1)
    return Image.fromarray((alpha * 255).astype(np.uint8), mode="L")


def export_layer(
    image: Image.Image, body_alpha: Image.Image, rect: Rect, feather: int, path: Path
) -> None:
    crop = image.crop(rect.box).convert("RGBA")
    mask = np.minimum(
        np.asarray(feather_mask(rect.width, rect.height, feather)),
        np.asarray(body_alpha.crop(rect.box)),
    )
    crop.putalpha(Image.fromarray(mask, mode="L"))
    crop.save(path, "WEBP", quality=WEBP_QUALITY)


def build_static(config: dict, images: dict[str, Image.Image], output_dir: Path) -> dict:
    cutout = remove_background(
        images[config["base"]], config.get("background_model", "birefnet-general")
    )
    base = cutout.crop(character_bounds(cutout, config.get("max_aspect")).box)
    max_height = int(config.get("max_height", DEFAULT_MAX_HEIGHT))
    if base.height > max_height:
        base = base.resize(
            (round(base.width * max_height / base.height), max_height), Image.LANCZOS
        )
    base.save(output_dir / "base.webp", "WEBP", quality=WEBP_QUALITY)
    return {"kind": "static", "canvas": {"width": base.width, "height": base.height}}


def build_layered(config: dict, images: dict[str, Image.Image], output_dir: Path) -> dict:
    feather = int(config.get("feather", 6))
    regions = {name: Rect(**values) for name, values in config["regions"].items()}
    check_alignment(images, config["base"], list(regions.values()))

    print("  building base image…")
    cutout = remove_background(
        images[config["base"]], config.get("background_model", "birefnet-general")
    )
    bounds = character_bounds(cutout)
    body_alpha = cutout.getchannel("A")
    cutout.crop(bounds.box).save(output_dir / "base.webp", "WEBP", quality=WEBP_QUALITY)

    print("  exporting face layers…")
    for sub in regions:
        (output_dir / sub).mkdir(parents=True, exist_ok=True)
    for name in sorted(images):
        for layer, rect in regions.items():
            export_layer(
                images[name], body_alpha, rect, feather, output_dir / layer / f"{name}.webp"
            )

    return {
        "kind": "layered",
        "canvas": {"width": bounds.width, "height": bounds.height},
        "regions": {
            name: rect.offset(bounds.x, bounds.y).as_dict() for name, rect in regions.items()
        },
        "sources": sorted(images),
        "expressions": config["expressions"],
        "blink": config["blink"],
        "mouthOpen": config["mouth_open"],
    }


def prepare(config_path: Path) -> None:
    config = load_config(config_path)
    sprite_id = config_path.parent.name
    source_dir = config_path.parent / config.get("source_dir", "art")
    output_dir = OUTPUT_ROOT / sprite_id
    layered = "blink" in config
    print(f"[{sprite_id}] {'layered' if layered else 'static'} sprite")

    if layered:
        sources = {
            config["base"],
            config["blink"],
            config["mouth_open"],
            *config["expressions"].values(),
        }
    else:
        sources = {config["base"]}
    images = load_sources(source_dir, sources)

    # Generated output only: start clean so stale layers never ship.
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True)
    details = (build_layered if layered else build_static)(config, images, output_dir)

    manifest = {"version": MANIFEST_VERSION, "id": sprite_id, "base": "base.webp", **details}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  done: {output_dir.relative_to(REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("configs", type=Path, nargs="+", help="characters/<id>/avatar.yaml")
    for config_path in parser.parse_args().configs:
        prepare(config_path.resolve())


if __name__ == "__main__":
    main()
