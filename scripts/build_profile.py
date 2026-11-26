import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from github_data import collect_and_save
from svg_engine import generate_all_svgs
from generate_gta_contributions import build_animation


def main():
    repo_root = os.path.dirname(SCRIPT_DIR)
    print("=== [1/3] Fetching live GitHub profile & contribution telemetry ===")
    data = collect_and_save(repo_root)

    print("=== [2/3] Generating Obsidian & Alabaster SVG suite ===")
    generate_all_svgs(repo_root, data)

    print("=== [3/3] Rendering 2x-supersampled Drift Contribution Highway ===")
    build_animation(data)

    print("=== Profile build complete ===")


if __name__ == "__main__":
    main()
