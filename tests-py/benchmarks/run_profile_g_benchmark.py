#!/usr/bin/env python3
"""Run and publish the SVD-090 Profile G performance workload."""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).parent.parent
sys.path.insert(0, str(TESTS))

from benchmarks.profile_g_performance import ProfileGBenchmark, write_outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload", type=Path, default=Path(__file__).with_name("profile_g_workload.json"))
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parents[2] / "docs" / "testing" / "profile-g-performance")
    parser.add_argument("--store-dir", type=Path, help="retain peer stores here (a temporary directory is used by default)")
    args = parser.parse_args()
    temporary = None
    store_dir = args.store_dir
    if store_dir is None:
        temporary = Path(tempfile.mkdtemp(prefix="profile-g-benchmark-"))
        store_dir = temporary
    elif store_dir.exists():
        if any(store_dir.iterdir()):
            parser.error("--store-dir must be empty")
    try:
        result = ProfileGBenchmark.from_file(args.workload, store_dir).run()
        write_outputs(result, args.output_dir)
        print(f"{'PASS' if result['accepted'] else 'FAIL'}: {args.output_dir / 'report.md'}")
        return 0 if result["accepted"] else 1
    finally:
        if temporary is not None:
            shutil.rmtree(temporary)


if __name__ == "__main__":
    raise SystemExit(main())
