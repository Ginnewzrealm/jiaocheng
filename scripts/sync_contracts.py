#!/usr/bin/env python3
"""Vendor the protocol so each skill can still be installed on its own."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("gin-answer", "gin-outline", "gin-draft", "gin-qc", "xiejiaocheng")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = (ROOT / "shared/tutorial_contract.py").read_bytes()
    mismatches = []
    targets = [(skill, 'tutorial_contract.py', source) for skill in SKILLS]
    coverage = (ROOT / 'shared/source_coverage.py').read_bytes()
    targets += [(skill, 'source_coverage.py', coverage) for skill in
                ('gin-tutorial-source-scan', 'gin-tutorial-harvest')]
    for skill, filename, content in targets:
        target = ROOT / skill / 'scripts' / filename
        if args.check:
            if not target.is_file() or target.read_bytes() != content:
                mismatches.append(skill + '/' + filename)
        else:
            target.write_bytes(content)
    if mismatches:
        print("协议副本需同步：" + ", ".join(mismatches))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
