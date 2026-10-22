# Changelog

## 0.1.0 (21 Oct 2026)

- naming: `<show>_<seq>_<shot>_<task>_v###[.frame][.ext]` convention; parse / build / check_paths with plain-English reasons.
- scaffold: show tree from a JSON template with `{seq}` / `{shot}` placeholders; idempotent; `--dry-run`.
- publish: immutable versioned publishes under `<root>/<show>/shots/<seq>/<shot>/publish/<task>/`; sha256-verified copy; atomic manifest sidecar; `latest` as a relative symlink with a `latest.json` fallback.
- sequences: image-sequence scan (`name.####.ext` and `name_####.ext`), missing / empty / mixed-padding detection, farm-style range compression.
- maya_check: unknown nodes, non-unique names, default names, units and fps, unloaded references, scene-name convention; `cmds` injected for testing.
- cli: `init`, `check`, `publish`, `latest`, `verify`, `ingest`, `doctor`; exit codes 0/1/2; `--json`.
- tests: 37 pytest cases, no Maya required.
- packaging (22 Oct 2026): SPDX `license` field and `license-files`; GitHub Actions workflow runs the suite on Ubuntu and Windows with Python 3.9 and 3.12.
