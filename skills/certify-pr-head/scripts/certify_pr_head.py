#!/usr/bin/env python3
"""Compare PR acceptance evidence SHAs against the exact current PR head.

Read-only. Establishes deterministic SHA facts. The model decides which
sources are required and how to act on the verdict.

Usage:
    python3 certify_pr_head.py --pr 123
    python3 certify_pr_head.py --pr 123 --reviewed <sha> --tested <sha> --ci <sha>
    python3 certify_pr_head.py --pr 123 --evidence-head <sha> --reviewed <sha>
    python3 certify_pr_head.py --head <sha> --reviewed <sha>
    python3 certify_pr_head.py --pr 123 --evidence evidence.json

evidence.json shape:
    {"reviewed": "<sha>", "tested": "<sha>", "ci": "<sha>", "head": "<sha>"}

--evidence-head is the head SHA that was current when the evidence was
produced. Supplying it lets the script distinguish HEAD_MOVED from
STALE_EVIDENCE.

Exit codes:
    0  verdict emitted
    2  reference head could not be resolved
"""

import argparse
import json
import shutil
import subprocess
import sys


def run(cmd, cwd=None):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    if proc.returncode != 0:
        return False, ""
    return True, proc.stdout.strip()


def expand_sha(sha, cwd):
    """Expand an abbreviated SHA to full 40 chars when possible."""
    if not sha:
        return None
    if len(sha) == 40:
        return sha.lower()
    ok, full = run(["git", "rev-parse", "--verify", "-q", sha + "^{commit}"], cwd=cwd)
    if ok and full:
        return full.lower()
    return None


def classify(evidence_sha, reference, cwd):
    """Return (status, full_sha, detail)."""
    if not evidence_sha:
        return "missing", None, "not provided"
    full = expand_sha(evidence_sha, cwd)
    if full is None:
        return "missing", evidence_sha, "abbreviated or unresolvable; cannot certify"
    if full == reference:
        return "match", full, "exact head"
    ok, _ = run(["git", "merge-base", "--is-ancestor", full, reference], cwd=cwd)
    if ok:
        return "stale", full, "ancestor of head"
    return "stale", full, "does not match head"


def main():
    parser = argparse.ArgumentParser(description="Certify PR head evidence (read-only).")
    parser.add_argument("--pr", type=int, default=None, help="pull request number")
    parser.add_argument("--repo", default=None, help="owner/name for gh")
    parser.add_argument("--head", default=None, help="reference head SHA (skips gh lookup)")
    parser.add_argument("--evidence-head", default=None, help="head SHA current when evidence was produced")
    parser.add_argument("--reviewed", default=None)
    parser.add_argument("--tested", default=None)
    parser.add_argument("--ci", default=None)
    parser.add_argument("--evidence", default=None, help="JSON file with evidence SHAs")
    parser.add_argument("--cwd", default=".", help="repo path for sha expansion")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    reviewed, tested, ci = args.reviewed, args.tested, args.ci
    evidence_head = args.evidence_head
    if args.evidence:
        with open(args.evidence, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        reviewed = reviewed or data.get("reviewed")
        tested = tested or data.get("tested")
        ci = ci or data.get("ci")
        evidence_head = evidence_head or data.get("head")

    reference = args.head
    pr_number = args.pr
    source = "argument"

    if not reference and pr_number is not None:
        if shutil.which("gh") is None:
            print("gh not found and no --head given", file=sys.stderr)
            return 2
        cmd = ["gh", "pr", "view", str(pr_number), "--json",
               "headRefOid,number,url,baseRefName,headRefName"]
        if args.repo:
            cmd += ["--repo", args.repo]
        ok, out = run(cmd, cwd=args.cwd)
        if not ok or not out:
            print("could not resolve PR head via gh", file=sys.stderr)
            return 2
        info = json.loads(out)
        reference = info.get("headRefOid")
        source = "gh"
    if not reference:
        print("no reference head resolved; pass --pr or --head", file=sys.stderr)
        return 2
    reference = reference.lower()

    results = {}
    statuses = {}
    for name, value in (("reviewed", reviewed), ("tested", tested), ("ci", ci)):
        status, full, detail = classify(value, reference, args.cwd)
        results[name] = {"sha": full, "status": status, "detail": detail}
        statuses[name] = status

    provided = {k: v for k, v in statuses.items() if v != "missing"}
    evidence_head_full = expand_sha(evidence_head, args.cwd) if evidence_head else None

    if not provided:
        verdict = "INCOMPLETE"
        reason = "no evidence SHA could be resolved"
    elif evidence_head_full and evidence_head_full != reference:
        matches_old_head = any(v == "match" for v in provided.values())
        # All evidence must have matched the old head for this to be a clean move.
        all_match_old = all(
            results[name]["sha"] == evidence_head_full
            for name in provided
        )
        if all_match_old or matches_old_head:
            verdict = "HEAD_MOVED"
            reason = "head changed from %s to %s after evidence was produced" % (
                evidence_head_full, reference)
        else:
            verdict = "STALE_EVIDENCE"
            reason = "evidence does not match the current head"
    elif any(v == "stale" for v in provided.values()):
        verdict = "STALE_EVIDENCE"
        reason = "evidence covers an older commit; head is unchanged"
    elif any(v == "missing" for v in statuses.values()):
        verdict = "INCOMPLETE"
        reason = "one or more evidence sources are missing"
    else:
        verdict = "EXACT_HEAD_CERTIFIED"
        reason = "all provided evidence matches the exact head"

    output = {
        "verdict": verdict,
        "reason": reason,
        "reference_head": reference,
        "reference_source": source,
        "evidence_head": evidence_head_full,
        "pr": pr_number,
        "evidence": results,
    }

    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print("VERDICT: %s" % verdict)
        print("REASON: %s" % reason)
        print("REFERENCE HEAD: %s (%s)" % (reference, source))
        if evidence_head_full:
            print("EVIDENCE HEAD: %s" % evidence_head_full)
        if pr_number is not None:
            print("PR: #%s" % pr_number)
        for name in ("reviewed", "tested", "ci"):
            item = results[name]
            print("%-9s %s -> %s (%s)" % (
                name.upper() + ":", item["sha"], item["status"], item["detail"]))
        blocking = [k for k, v in statuses.items() if v in ("stale", "missing")]
        print("BLOCKING SOURCES: %s" % (", ".join(blocking) if blocking else "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
