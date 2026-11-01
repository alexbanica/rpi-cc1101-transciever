#!/usr/bin/env python3
"""Strict conversion from supported release tags to PEP 440 versions."""
import argparse
import os
import re

TAG_RE = re.compile(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-beta([1-9][0-9]*))?\Z")


def parse_release_tag(tag: str) -> str:
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"unsupported release tag {tag!r}; expected [v]X.Y.Z or [v]X.Y.Z-betaN")
    major, minor, patch, beta = match.groups()
    return f"{major}.{minor}.{patch}" + (f"b{beta}" if beta else "")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=os.environ.get("RELEASE_TAG"))
    args = parser.parse_args(argv)
    if not args.tag:
        parser.error("--tag or RELEASE_TAG is required")
    try:
        print(parse_release_tag(args.tag))
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
