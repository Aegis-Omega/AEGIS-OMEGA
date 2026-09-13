"""Capture only the verifier's bytes, excluding outer action shell traces."""

import argparse
import subprocess
from pathlib import Path


def capture(query: Path, directory: Path, output: Path) -> None:
    query = query.resolve(strict=True)
    directory = directory.resolve(strict=True)
    with output.open("wb") as log:
        subprocess.run(
            ["coqtop", "-q", "-quiet", "-batch", "-l", str(query)],
            cwd=directory,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    capture(args.query, args.directory, args.output)
