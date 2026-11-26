import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from PIL import Image


def validate_all(repo_root: str) -> list[str]:
    errors = []

    # 1. Validate profile-data.json
    data_path = os.path.join(repo_root, "assets", "profile-data.json")
    if not os.path.exists(data_path):
        errors.append("Missing assets/profile-data.json")
    else:
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in ("username", "user", "contributions", "languages", "featured_repos"):
                if key not in data:
                    errors.append(f"profile-data.json missing key: {key}")
            if not data.get("contributions", {}).get("cells"):
                errors.append("profile-data.json has empty contributions.cells")
        except Exception as exc:
            errors.append(f"Invalid profile-data.json: {exc}")

    # 2. Validate design/tokens.json
    tokens_path = os.path.join(repo_root, "design", "tokens.json")
    if not os.path.exists(tokens_path):
        errors.append("Missing design/tokens.json")
    else:
        try:
            with open(tokens_path, "r", encoding="utf-8") as f:
                json.load(f)
        except Exception as exc:
            errors.append(f"Invalid design/tokens.json: {exc}")

    # 3. Validate all SVG files for well-formed XML and zero <script>/<foreignObject>
    assets_dir = os.path.join(repo_root, "assets")
    svg_count = 0
    for root, _, files in os.walk(assets_dir):
        for fname in files:
            if fname.lower().endswith(".svg"):
                svg_count += 1
                fpath = os.path.join(root, fname)
                try:
                    tree = ET.parse(fpath)
                    xml_str = ET.tostring(tree.getroot(), encoding="unicode")
                    if "<script" in xml_str.lower():
                        errors.append(f"SVG contains disallowed <script>: {fpath}")
                    if "foreignobject" in xml_str.lower():
                        errors.append(f"SVG contains disallowed <foreignObject>: {fpath}")
                except Exception as exc:
                    errors.append(f"Malformed SVG XML {fpath}: {exc}")
    if svg_count < 20:
        errors.append(f"Expected >= 20 SVG assets, found {svg_count}")

    # 4. Validate GIF integrity
    gif_path = os.path.join(assets_dir, "gta6-contribution.gif")
    if not os.path.exists(gif_path):
        errors.append("Missing assets/gta6-contribution.gif")
    else:
        try:
            with Image.open(gif_path) as im:
                n_frames = getattr(im, "n_frames", 1)
                if n_frames < 60:
                    errors.append(f"GIF frame count too low: {n_frames}")
                if im.size != (920, 280):
                    errors.append(f"Unexpected GIF size {im.size}, expected (920, 280)")
        except Exception as exc:
            errors.append(f"Invalid GIF {gif_path}: {exc}")

    # 5. Validate README.md local asset references exist on disk
    readme_path = os.path.join(repo_root, "README.md")
    if not os.path.exists(readme_path):
        errors.append("Missing README.md")
    else:
        with open(readme_path, "r", encoding="utf-8") as f:
            readme = f.read()
        refs = re.findall(r'(?:src|srcset)="(\./[^"]+)"', readme)
        if not refs:
            errors.append("README.md has no local ./assets references")
        for ref in sorted(set(refs)):
            target = os.path.join(repo_root, ref.lstrip("./"))
            if not os.path.exists(target):
                errors.append(f"README.md references missing local file: {ref}")
        if "logo=windows11" in readme or "logo=xbox" in readme:
            errors.append("README.md still uses broken shields.io Simple Icons slugs")

    return errors


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    errs = validate_all(root)
    if errs:
        print("VALIDATION FAILED:")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    print("VALIDATION PASSED: All JSON, SVGs, GIF, and README asset references are valid.")
