#!/usr/bin/env python3
"""Gather deterministic repository facts for preflight-repository.

Read-only. Never mutates the repository. Uses git, and gh only when present.
The model interprets ambiguity; this script establishes facts.

Usage:
    python3 preflight.py [--repo PATH] [--default-branch NAME] [--json]

Exit codes:
    0  facts gathered (verdict is still the model's call)
    2  not inside a git work tree
"""

import argparse
import json
import os
import shutil
import subprocess
import sys


def run(cmd, cwd=None):
    """Run a command, return (ok, stdout_stripped)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False, ""
    if proc.returncode != 0:
        return False, ""
    return True, proc.stdout.strip()


def git(args, cwd=None):
    return run(["git"] + args, cwd=cwd)


def parse_remote(url):
    """Parse a git remote URL into host/owner/name, best effort."""
    if not url:
        return {"host": None, "owner": None, "name": None}
    raw = url.strip()
    if raw.endswith(".git"):
        raw = raw[:-4]
    host = owner = name = None
    if raw.startswith("git@") and ":" in raw:
        host, path = raw[4:].split(":", 1)
    elif "://" in raw:
        rest = raw.split("://", 1)[1]
        if "@" in rest.split("/", 1)[0]:
            rest = rest.split("@", 1)[1]
        host, _, path = rest.partition("/")
    elif "/" in raw:
        host, path = None, raw
    else:
        path = raw
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        owner = parts[-2]
        name = parts[-1]
    elif parts:
        name = parts[-1]
    return {"host": host, "owner": owner, "name": name}


def main():
    parser = argparse.ArgumentParser(description="Gather repository facts (read-only).")
    parser.add_argument("--repo", default=".", help="path inside the work tree")
    parser.add_argument("--default-branch", default=None, help="override default branch")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    start = os.path.abspath(args.repo)

    ok, inside = git(["rev-parse", "--is-inside-work-tree"], cwd=start)
    if not ok or inside != "true":
        print("not inside a git work tree", file=sys.stderr)
        return 2

    ok, root = git(["rev-parse", "--show-toplevel"], cwd=start)
    ok_gd, git_dir = git(["rev-parse", "--git-dir"], cwd=start)
    ok_gc, git_common = git(["rev-parse", "--git-common-dir"], cwd=start)

    ok, head_sha = git(["rev-parse", "HEAD"], cwd=root)
    head_sha = head_sha if ok else None

    ok, branch = git(["symbolic-ref", "--short", "-q", "HEAD"], cwd=root)
    detached = not ok
    branch = branch if ok else None

    # default branch
    default_branch = args.default_branch
    if not default_branch:
        ok, sym = git(["symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD"], cwd=root)
        if ok and sym:
            default_branch = sym.split("/", 1)[-1]
    if not default_branch:
        for candidate in ("main", "master"):
            ok, _ = git(["rev-parse", "--verify", "-q", candidate], cwd=root)
            if ok:
                default_branch = candidate
                break

    # merge base against default branch
    merge_base = None
    if default_branch:
        for ref in ("refs/remotes/origin/" + default_branch, default_branch):
            ok, mb = git(["merge-base", "HEAD", ref], cwd=root)
            if ok and mb:
                merge_base = mb
                break

    # dirty state
    ok, porcelain = git(["status", "--porcelain"], cwd=root)
    changed = [l for l in porcelain.splitlines() if l.strip()] if ok else []
    staged = sum(1 for l in changed if l[:2].strip() and l[0] not in " ?")
    unstaged = sum(1 for l in changed if len(l) > 1 and l[1] not in " ?" and l[0] != "?")
    untracked = sum(1 for l in changed if l.startswith("??"))

    # upstream and ahead/behind
    upstream = None
    ahead = behind = None
    ok, up = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"], cwd=root)
    if ok and up:
        upstream = up
        ok, counts = git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], cwd=root)
        if ok and counts:
            left, _, right = counts.partition("\t")
            try:
                ahead, behind = int(left), int(right)
            except ValueError:
                ahead = behind = None

    # remote parity: local HEAD vs upstream SHA
    remote_parity = "unknown"
    if upstream:
        ok, up_sha = git(["rev-parse", upstream], cwd=root)
        if ok and up_sha and head_sha:
            remote_parity = "yes" if up_sha == head_sha else "no"

    # worktree kind
    ok, toplevel = git(["rev-parse", "--show-toplevel"], cwd=root)
    ok, wt_list = git(["worktree", "list", "--porcelain"], cwd=root)
    is_linked = False
    if ok and wt_list:
        # A linked worktree's first entry is the main worktree; count entries.
        is_linked = wt_list.count("worktree ") > 1
    is_submodule = os.path.exists(os.path.join(root, ".git")) and os.path.isfile(os.path.join(root, ".git"))

    # remotes
    ok, remotes_raw = git(["remote", "-v"], cwd=root)
    fetch_url = push_url = None
    if ok:
        for line in remotes_raw.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "origin":
                if parts[2] == "(fetch)":
                    fetch_url = parts[1]
                elif parts[2] == "(push)":
                    push_url = parts[1]
    identity = parse_remote(fetch_url or push_url)
    push_matches_fetch = (fetch_url == push_url) if (fetch_url or push_url) else None

    # associated PR and checks via gh, only if present
    pr = None
    checks = None
    gh_present = shutil.which("gh") is not None
    if gh_present and head_sha:
        ok, pr_json = run(
            ["gh", "pr", "list", "--head", branch or "", "--state", "open",
             "--json", "number,baseRefName,headRefName,headRefOid,url,mergeStateStatus"],
            cwd=root,
        )
        if ok and pr_json:
            try:
                prs = json.loads(pr_json)
            except ValueError:
                prs = []
            if prs:
                item = prs[0]
                pr = {
                    "number": item.get("number"),
                    "base": item.get("baseRefName"),
                    "head": item.get("headRefName"),
                    "head_sha": item.get("headRefOid"),
                    "url": item.get("url"),
                    "merge_state": item.get("mergeStateStatus"),
                }
        if pr and pr.get("number"):
            ok, checks_json = run(
                ["gh", "pr", "checks", str(pr["number"]), "--json", "name,state,link"],
                cwd=root,
            )
            if ok and checks_json:
                try:
                    checks = json.loads(checks_json)
                except ValueError:
                    checks = None

    facts = {
        "repository": {
            "identity": identity,
            "root": root,
            "git_dir": git_dir if ok_gd else None,
            "git_common_dir": git_common if ok_gc else None,
            "fetch_url": fetch_url,
            "push_url": push_url,
            "push_matches_fetch": push_matches_fetch,
        },
        "branch": {
            "current": branch,
            "detached": detached,
            "default": default_branch,
            "upstream": upstream,
        },
        "commit": {
            "head_sha": head_sha,
            "merge_base": merge_base,
        },
        "worktree": {
            "is_linked": is_linked,
            "is_submodule": is_submodule,
        },
        "tree": {
            "clean": len(changed) == 0,
            "changed_count": len(changed),
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
        },
        "sync": {
            "ahead": ahead,
            "behind": behind,
            "remote_parity": remote_parity,
        },
        "pull_request": pr,
        "checks": checks,
        "deployment": {
            "identity": "unknown",
            "note": "fill from the deployment platform when relevant",
        },
        "tooling": {
            "gh_present": gh_present,
        },
        "verdict_inputs": {
            "identity_proven": bool(identity.get("owner") and identity.get("name")),
            "root_proven": bool(root),
            "head_proven": bool(head_sha),
            "tree_clean": len(changed) == 0,
            "default_branch_proven": bool(default_branch),
            "detached_head": detached,
            "remote_parity": remote_parity,
        },
    }

    if args.json:
        print(json.dumps(facts, indent=2, sort_keys=True))
    else:
        print("REPOSITORY: {host}/{owner}/{name}".format(**{
            "host": identity.get("host") or "?",
            "owner": identity.get("owner") or "?",
            "name": identity.get("name") or "?",
        }))
        print("ROOT:       %s" % root)
        print("BRANCH:     %s%s" % (branch or "(detached)", "" if not detached else " [detached]"))
        print("HEAD:       %s" % (head_sha or "unknown"))
        print("DEFAULT:    %s" % (default_branch or "unknown"))
        print("MERGE BASE: %s" % (merge_base or "unknown"))
        print("TREE:       %s" % ("clean" if len(changed) == 0 else "dirty(%d)" % len(changed)))
        print("SYNC:       ahead=%s behind=%s parity=%s" % (ahead, behind, remote_parity))
        print("PR:         %s" % (("PR #%s base=%s head=%s" % (
            pr.get("number"), pr.get("base"), pr.get("head_sha"))) if pr else "none"))
        print("CHECKS:     %s" % ("present" if checks else "unknown"))
        print("WORKTREE:   linked=%s submodule=%s" % (is_linked, is_submodule))
        print("GH:         %s" % ("present" if gh_present else "absent"))
        print("--- verdict inputs ---")
        for key, value in facts["verdict_inputs"].items():
            print("%-24s %s" % (key, value))
    return 0


if __name__ == "__main__":
    sys.exit(main())
