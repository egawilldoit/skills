# Provenance manifest schema

The manifest is the artifact of `trace-artifact-provenance`. It is JSON so a reviewer can diff it, store it, and re-check it. This file documents each field and how it is verified.

## Schema

```json
{
  "manifest_version": 1,
  "generated_at": "2026-01-01T00:00:00Z",
  "source": {
    "repository": "host/owner/name",
    "ref": "refs/heads/main",
    "sha": "full-40-char-commit-sha",
    "sha_status": "PROVEN"
  },
  "build": {
    "id": "run id or build number",
    "pipeline": "pipeline or workflow name",
    "builder": "builder identity or image",
    "inputs": ["lockfile digest", "toolchain version"],
    "status": "PROVEN"
  },
  "artifact": {
    "kind": "apk | container-image | release-archive | package | vercel-deployment | server-deployment | generated-bundle | other",
    "name": "human readable name",
    "path": "local path or registry reference",
    "size_bytes": 12345,
    "digest": "hex",
    "digest_algorithm": "sha256",
    "file_count": 1,
    "status": "PROVEN"
  },
  "release": {
    "id": "release id",
    "name": "release name",
    "url": "release URL",
    "status": "SUPPORTED"
  },
  "deployment": {
    "kind": "vercel | server | registry | other",
    "target": "project or host",
    "environment": "production | staging | preview",
    "version": "deployed version or commit",
    "digest": "deployed artifact digest",
    "status": "PROVEN"
  },
  "verification": {
    "evidence_level": "E4",
    "recheck_commands": [
      "sha256sum <path>",
      "python3 provenance_manifest.py --artifact <path> --verify <manifest.json>"
    ]
  }
}
```

## Field status values

Each link carries a status from the operating contract's knowledge states:

```text
PROVEN        demonstrated by a digest, a platform field, or a command
SUPPORTED     consistent evidence, not exhaustive
UNKNOWN       not obtained; record, do not guess
CONTRADICTED  evidence disagrees; resolve before trusting the manifest
```

## How each field is verified

```text
source.sha          git rev-parse of the built commit; full 40 chars
build.id            the pipeline run id, read from the build system
artifact.digest     computed from the exact distributed bytes
artifact.path       points at the bytes that were hashed
release.id          read from the release record, linked to the artifact
deployment.version  read from the platform, not inferred from time
deployment.digest   read from the platform's artifact identity
```

## Directory and bundle digests

For a directory, the digest is computed over a deterministic listing:

1. Enumerate all regular files under the root.
2. Sort by relative path, byte-wise.
3. For each file, hash the relative path and then the file bytes into the running hash.
4. Record the file count.

The script uses this method so two runs over the same tree produce the same digest, and a changed byte changes the digest.

## Independent re-check

A reviewer who does not trust the author:

1. Obtains the artifact bytes by the recorded path or registry reference.
2. Runs the recorded digest command and compares to `artifact.digest`.
3. Reads `source.sha` from the repository and confirms the commit exists.
4. Reads the release record and confirms it references the artifact.
5. Reads the deployment platform and confirms `deployment.version` and `deployment.digest`.

If any step disagrees, the link is `CONTRADICTED` and the manifest is not trustworthy until resolved.

## Anti-patterns

- Recording a tag where a digest is required. Tags move; digests do not.
- Hashing a re-packed archive. The distributed bytes are the artifact.
- Inferring the deployment commit from deploy time. Read the platform field.
- Omitting the digest algorithm. The same hex string means nothing without it.
- Marking a link `PROVEN` when the value came from a claim rather than a command or platform field.
