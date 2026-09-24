---
name: trace-artifact-provenance
description: "Establish immutable lineage from source commit to build to artifact to digest to release to deployment, and emit a provenance manifest another reviewer can independently check. Use for APK, container image, release archive, package, Vercel deployment, server deployment, or generated bundle when asked where an artifact came from, whether a deployment matches a commit, or which build produced a release. Produces checksum-pinned evidence at E4 or higher. For PR evidence freshness use certify-pr-head; for the complete release gate use certify-release."
---

# Trace artifact provenance

An artifact without a digest and a source commit is unverifiable. This skill pins the chain `source SHA -> build -> artifact -> digest -> release -> deployment` and emits a manifest a second reviewer can re-check independently.

Vocabulary comes from `references/operating-contract.md`. The chain reaches `E4 IMMUTABLE ARTIFACT` once a digest is computed; deployment observation raises it to `E5`.

## When to use

- Asked where a released artifact, image, APK, bundle, or deployment came from.
- Asked whether a deployment matches a specific commit.
- Asked which build produced a release, or whether two environments run the same bytes.
- Building a release and needing a checkable record of what was produced.
- Auditing an artifact whose provenance is claimed but unproven.

Do not use it to certify PR head evidence (`certify-pr-head`) or to run the full release gate (`certify-release`).

## Artifact kinds

```text
apk                Android package
container-image    OCI/Docker image
release-archive    tarball or zip of a release
package            published package artifact
vercel-deployment  a Vercel deployment
server-deployment  a deployment to a server or host
generated-bundle   a built JS/CSS/asset bundle
other              anything else with a stable digest
```

## The chain

```text
source SHA      the exact commit the build ran from
build           the build identity: pipeline, run id, builder, inputs
artifact        the produced file, image, or deployment
digest          a cryptographic hash of the artifact bytes
release         the release identity that contains the artifact
deployment      the environment where the artifact runs, and its identity
```

Every link is optional only if the task does not need it. A link that is unknown is recorded as unknown, never guessed.

## Workflow

1. Fix the source SHA. It is a full commit id, not a branch name.
2. Identify the build: pipeline name, run id, and builder. Record what inputs it consumed.
3. Locate the artifact. For a file or directory, compute the digest locally. For a container image or platform deployment, use the digest the platform reports.
4. Run `scripts/provenance_manifest.py` to compute digests and emit the manifest.
5. Attach the release and deployment identity when they exist.
6. Mark each link `PROVEN`, `SUPPORTED`, or `UNKNOWN` and record the evidence level.
7. State how a reviewer independently re-checks each digest.

## Digest rules

- Prefer SHA-256. Record the algorithm with the digest.
- For a directory or bundle, hash a deterministic listing: relative paths sorted, then each file's bytes. Record the file count.
- Never hash a re-encoded or re-zipped artifact and call it the original. Hash the exact bytes distributed.
- For a container image, the image digest is the identity, not the mutable tag.
- Two artifacts with the same digest are the same bytes. Same tag is not the same bytes.

## Manifest

The manifest is the deliverable. It is JSON so a reviewer can diff and verify it. The full schema is in `references/manifest-schema.md`. It contains at minimum:

```text
manifest_version
generated_at
source:     {sha, ref, repository}
build:      {id, pipeline, builder, inputs}
artifact:   {kind, name, path, size_bytes, digest, digest_algorithm, file_count}
release:    {id, name, url}
deployment: {kind, target, environment, version, digest}
verification: {recheck_commands, evidence_level}
status:     {proven, supported, unknown}
```

## Independent re-check

The manifest must let a reviewer reproduce each digest without trusting the author. Record the exact command or procedure per artifact. Example re-checks:

```text
file:      sha256sum <path>
directory: run provenance_manifest.py --artifact <path> --verify <manifest.json>
image:     the platform's digest field, compared to the recorded digest
platform:  the deployment's reported commit and build id
```

## Hard rules

- Pin the source commit SHA. A branch or tag is not provenance.
- Record the digest algorithm. A bare hex string is ambiguous.
- Never infer a deployment's commit from timing. Read the platform's reported value.
- Never claim a deployment matches a commit without comparing the platform's commit field to the source SHA.
- Mark unknown links unknown. `E4` requires a real digest; do not report it otherwise.
- Do not invent build ids, pipeline names, or platform fields.

## Output contract

```text
PROVENANCE: COMPLETE | PARTIAL | UNVERIFIABLE
EVIDENCE: E0..E6
SOURCE SHA: <full sha or unknown>
ARTIFACT: <kind>, digest <algo:hex> or unknown
RELEASE: <id or unknown>
DEPLOYMENT: <target and version or unknown>
CHAIN: <per link: PROVEN, SUPPORTED, or UNKNOWN>
RECHECK: <commands or procedures>
BLOCKERS: <type and detail, or none>
NEXT: <the single next action>
```

`UNVERIFIABLE` is correct when the artifact bytes or the source SHA cannot be obtained. Report it instead of asserting provenance.
