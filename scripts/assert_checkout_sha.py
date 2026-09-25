#!/usr/bin/env python3
"""Prove which commit a validation job actually executed.

Prints and asserts identity facts for CI evidence:

    EVENT:           GitHub event name (or an explicit --event)
    EXPECTED SHA:    the SHA the job was supposed to validate
    EXECUTED SHA:    the SHA actually checked out
    BASE SHA:        the base the job ran against (optional)

For exact-head certification, executed SHA must equal expected SHA:

    python3 assert_checkout_sha.py --expected <sha>
    python3 assert_checkout_sha.py --expected <sha> --mode exact-head
    python3 assert_checkout_sha.py --expected <sha> --base <sha> --mode merge-result

Exit codes:
    0  executed SHA resolves and satisfies the mode's requirement
    1  executed SHA does not satisfy the requirement
    2  usage or resolution error
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def git(args):
    try:
        proc = subprocess.run(
            ["git"] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def resolve_sha(value):
    if not value:
        return None
    if len(value) == 40 and git(["cat-file", "-e", value + "^{commit}"]) is not None:
        return value.lower()
    full = git(["rev-parse", "--verify", "-q", value + "^{commit}"])
    return full.lower() if full else None


def main():
    parser = argparse.ArgumentParser(description="Assert the executed checkout SHA (read-only).")
    parser.add_argument("--expected", required=True, help="SHA the job was supposed to validate")
    parser.add_argument("--base", default=None, help="base SHA the job ran against")
    parser.add_argument("--event", default=None, help="event name (e.g. pull_request, push)")
    parser.add_argument("--mode", choices=("exact-head", "merge-result", "none"), default="none",
                        help="exact-head: executed must equal expected; "
                             "merge-result: executed must differ from expected")
    parser.add_argument("--json", action="store_true", help="emit the identity block as JSON")
    args = parser.parse_args()

    executed = resolve_sha(git(["rev-parse", "HEAD"]))
    expected = resolve_sha(args.expected)
    base = resolve_sha(args.base) if args.base else None

    if executed is None:
        print("ERROR: could not resolve the executed checkout SHA (git rev-parse HEAD)",
              file=sys.stderr)
        return 2
    if expected is None:
        print("ERROR: could not resolve expected SHA %r" % args.expected, file=sys.stderr)
        return 2

    facts = {
        "event": args.event,
        "expected_sha": expected,
        "executed_sha": executed,
        "base_sha": base,
    }

    print("EVENT:")
    print(args.event or "unknown")
    print("EXPECTED SHA:")
    print(expected)
    print("EXECUTED SHA:")
    print(executed)
    if base:
        print("BASE SHA:")
        print(base)

    if args.mode == "exact-head" and executed != expected:
        print("FAIL: expected exact-head checkout %s but executed %s" % (expected, executed),
              file=sys.stderr)
        if args.json:
            print(json.dumps({**facts, "satisfied": False}, sort_keys=True))
        return 1
    if args.mode == "merge-result" and executed == expected:
        print("FAIL: merge-result job executed the PR head %s itself; a synthetic "
              "merge SHA was expected" % executed, file=sys.stderr)
        if args.json:
            print(json.dumps({**facts, "satisfied": False}, sort_keys=True))
        return 1

    if args.json:
        print(json.dumps({**facts, "satisfied": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
