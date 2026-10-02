#!/usr/bin/env python3
"""Produce BFIL lower/upper permission evidence for one bounded source program."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pcpe.check import load
from pcpe.evidence import build_evidence


def write_new(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except BaseException:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        source = load(args.source)
        evidence, stats = build_evidence(source)
        write_new(args.out, evidence)
    except (OSError, ValueError, RecursionError, AssertionError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps({"accepted": True, "output": str(args.out), "stats": stats}, sort_keys=True))


if __name__ == "__main__":
    main()
