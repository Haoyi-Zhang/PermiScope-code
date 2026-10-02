#!/usr/bin/env python3
"""Independently check BFIL source coverage, proofs, minima, and classifications."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pcpe.check import load
from pcpe.source_checker import validate_source_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        verdict = validate_source_evidence(load(args.source), load(args.evidence))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps({"accepted": verdict.accepted, "reason": verdict.reason, "steps": verdict.steps}, sort_keys=True))
    raise SystemExit(0 if verdict.accepted else 1)


if __name__ == "__main__":
    main()
