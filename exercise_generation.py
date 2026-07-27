"""
Batch-generates exercise instruction images.

Reads every prompt in exercise_prompts/<slug>.txt, calls the OpenAI images
API, and writes the result to exercises/<slug>.jpg.

Usage:
    python exercise_generation.py                  # generate every exercise missing a fresh image
    python exercise_generation.py --force           # regenerate everything, overwriting existing jpgs
    python exercise_generation.py --only goblet-squat,side-plank
    python exercise_generation.py --list            # show what would run and exit

Requires OPENAI_API_KEY to be set in the environment.
"""

import argparse
import sys
import time
from pathlib import Path

from openai import OpenAI

PROMPTS_DIR = Path(__file__).parent / "exercise_prompts"
OUTPUT_DIR = Path(__file__).parent / "exercises"
MODEL = "gpt-image-2"
SIZE = "1536x1024"
QUALITY = "medium"


def load_prompts(only=None):
    files = sorted(PROMPTS_DIR.glob("*.txt"))
    if only:
        wanted = set(only)
        files = [f for f in files if f.stem in wanted]
        missing = wanted - {f.stem for f in files}
        if missing:
            print(f"warning: no prompt file for: {', '.join(sorted(missing))}", file=sys.stderr)
    return [(f.stem, f.read_text(encoding="utf-8")) for f in files]


def generate_one(client, slug, prompt, quality, attempts=3):
    out_path = OUTPUT_DIR / f"{slug}.jpg"
    last_err = None
    for attempt in range(1, attempts + 1):
        try:
            result = client.images.generate(
                model=MODEL,
                prompt=prompt,
                size=SIZE,
                quality=quality,
                output_format="jpeg",
            )
            image_bytes = result.data[0].b64_json
            import base64

            out_path.write_bytes(base64.b64decode(image_bytes))
            return True
        except Exception as e:
            last_err = e
            if attempt < attempts:
                time.sleep(2 * attempt)
    print(f"  FAILED after {attempts} attempts: {last_err}", file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="regenerate images that already exist")
    parser.add_argument("--only", help="comma-separated list of exercise slugs to generate")
    parser.add_argument("--list", action="store_true", help="print the work plan and exit without calling the API")
    parser.add_argument("--quality", choices=["low", "medium", "high"], default=QUALITY, help=f"image quality tier (default: {QUALITY})")
    args = parser.parse_args()

    only = [s.strip() for s in args.only.split(",")] if args.only else None
    prompts = load_prompts(only)

    if not args.force:
        prompts = [(slug, p) for slug, p in prompts if not (OUTPUT_DIR / f"{slug}.jpg").exists()]

    if not prompts:
        print("Nothing to do — all requested images already exist. Use --force to regenerate.")
        return

    print(f"{len(prompts)} image(s) to generate:")
    for slug, _ in prompts:
        print(f"  - {slug}")

    if args.list:
        return

    client = OpenAI()
    succeeded, failed = [], []
    for i, (slug, prompt) in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] {slug} ...", end=" ", flush=True)
        start = time.time()
        ok = generate_one(client, slug, prompt, args.quality)
        elapsed = time.time() - start
        if ok:
            print(f"done ({elapsed:.1f}s)")
            succeeded.append(slug)
        else:
            failed.append(slug)

    print(f"\n{len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed: " + ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
