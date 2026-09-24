#!/usr/bin/env python3
"""Compute artifact digests and emit a provenance manifest.

Read-only with respect to the artifact. Writes only the manifest when asked.
Plain Python 3 standard library only.

Usage:
    python3 provenance_manifest.py --artifact ./dist/app.apk --kind apk \
        --source-sha <sha> --output manifest.json
    python3 provenance_manifest.py --artifact ./dist --kind generated-bundle
    python3 provenance_manifest.py --artifact ./dist --verify manifest.json

Exit codes:
    0  success
    1  verification mismatch
    2  usage or artifact error
"""

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

MANIFEST_VERSION = 1
SUPPORTED_ALGORITHMS = ("sha256", "sha512")


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


def file_digest(path, algorithm):
    hasher = hashlib.new(algorithm)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def tree_digest(root, algorithm):
    """Deterministic digest over a directory tree.

    Sorted relative paths, then per file: path bytes, then content bytes.
    """
    hasher = hashlib.new(algorithm)
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            files.append((rel, full))
    files.sort(key=lambda item: item[0].encode("utf-8"))
    for rel, full in files:
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        with open(full, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        hasher.update(b"\0")
    return hasher.hexdigest(), len(files)


def describe_artifact(path, algorithm):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if os.path.isdir(path):
        digest, count = tree_digest(path, algorithm)
        size = 0
        for dirpath, _dirnames, filenames in os.walk(path):
            for name in filenames:
                full = os.path.join(dirpath, name)
                if not os.path.islink(full):
                    size += os.path.getsize(full)
        return {"kind_path": "directory", "digest": digest, "size_bytes": size,
                "file_count": count}
    digest = file_digest(path, algorithm)
    return {"kind_path": "file", "digest": digest,
            "size_bytes": os.path.getsize(path), "file_count": 1}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")


def build_manifest(args):
    info = describe_artifact(args.artifact, args.digest_algorithm)

    source_sha = args.source_sha
    source_sha_status = "PROVEN" if source_sha else "UNKNOWN"
    if not source_sha:
        ok, sha = run(["git", "rev-parse", "HEAD"], cwd=args.cwd)
        if ok and sha:
            source_sha = sha
            source_sha_status = "PROVEN"

    source_ref = args.source_ref
    if not source_ref:
        ok, ref = run(["git", "symbolic-ref", "-q", "HEAD"], cwd=args.cwd)
        if ok and ref:
            source_ref = ref

    repository = args.repository
    if not repository:
        ok, url = run(["git", "remote", "get-url", "origin"], cwd=args.cwd)
        if ok and url:
            repository = url

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "generated_at": now_iso(),
        "source": {
            "repository": repository,
            "ref": source_ref,
            "sha": source_sha,
            "sha_status": source_sha_status,
        },
        "build": {
            "id": args.build_id,
            "pipeline": args.build_pipeline,
            "builder": args.build_builder,
            "inputs": args.build_input or [],
            "status": "PROVEN" if args.build_id else "UNKNOWN",
        },
        "artifact": {
            "kind": args.kind,
            "name": args.name or os.path.basename(os.path.abspath(args.artifact)),
            "path": os.path.abspath(args.artifact),
            "size_bytes": info["size_bytes"],
            "digest": info["digest"],
            "digest_algorithm": args.digest_algorithm,
            "file_count": info["file_count"],
            "status": "PROVEN",
        },
        "release": {
            "id": args.release_id,
            "name": args.release_name,
            "url": args.release_url,
            "status": "SUPPORTED" if args.release_id else "UNKNOWN",
        },
        "deployment": {
            "kind": args.deployment_kind,
            "target": args.deployment_target,
            "environment": args.deployment_environment,
            "version": args.deployment_version,
            "digest": args.deployment_digest,
            "status": "PROVEN" if (args.deployment_target and
                                   (args.deployment_version or args.deployment_digest))
                      else "UNKNOWN",
        },
        "verification": {
            "evidence_level": "E4",
            "recheck_commands": [
                "%s %s" % ("sha256sum" if args.digest_algorithm == "sha256" else "sha512sum",
                           os.path.abspath(args.artifact)),
                "python3 provenance_manifest.py --artifact %s --verify <manifest.json>" % os.path.abspath(args.artifact),
            ],
        },
    }
    return manifest


def verify(args):
    with open(args.verify, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    recorded = manifest.get("artifact", {})
    algorithm = recorded.get("digest_algorithm", "sha256")
    if algorithm not in SUPPORTED_ALGORITHMS:
        print("unsupported algorithm in manifest: %s" % algorithm, file=sys.stderr)
        return 2
    try:
        info = describe_artifact(args.artifact, algorithm)
    except FileNotFoundError:
        print("artifact not found: %s" % args.artifact, file=sys.stderr)
        return 2
    ok = info["digest"] == recorded.get("digest")
    print("VERIFY: %s" % ("MATCH" if ok else "MISMATCH"))
    print("  algorithm: %s" % algorithm)
    print("  manifest:  %s" % recorded.get("digest"))
    print("  artifact:  %s" % info["digest"])
    if not ok:
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="Compute artifact digests and emit a provenance manifest.")
    parser.add_argument("--artifact", required=True, help="file or directory to hash")
    parser.add_argument("--kind", default="other")
    parser.add_argument("--name", default=None)
    parser.add_argument("--digest-algorithm", default="sha256", choices=list(SUPPORTED_ALGORITHMS))
    parser.add_argument("--source-sha", default=None)
    parser.add_argument("--source-ref", default=None)
    parser.add_argument("--repository", default=None)
    parser.add_argument("--build-id", default=None)
    parser.add_argument("--build-pipeline", default=None)
    parser.add_argument("--build-builder", default=None)
    parser.add_argument("--build-input", action="append", default=None)
    parser.add_argument("--release-id", default=None)
    parser.add_argument("--release-name", default=None)
    parser.add_argument("--release-url", default=None)
    parser.add_argument("--deployment-kind", default=None)
    parser.add_argument("--deployment-target", default=None)
    parser.add_argument("--deployment-environment", default=None)
    parser.add_argument("--deployment-version", default=None)
    parser.add_argument("--deployment-digest", default=None)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--output", default=None)
    parser.add_argument("--verify", default=None, help="verify an artifact against an existing manifest")
    parser.add_argument("--json", action="store_true", help="print the manifest to stdout")
    args = parser.parse_args()

    if args.verify:
        return verify(args)

    try:
        manifest = build_manifest(args)
    except FileNotFoundError as exc:
        print("artifact not found: %s" % exc, file=sys.stderr)
        return 2

    text = json.dumps(manifest, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print("manifest written: %s" % args.output)
    if args.json or not args.output:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
