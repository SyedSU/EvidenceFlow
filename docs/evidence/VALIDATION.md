# 2026-10-23 source validation

Commands executed from EvidenceFlow:

- `python scripts/build_save_adapter.py` — PASS, Debian cc 14.2.0-19, pinned ABI header verified, first-party Linux x64 extension built locally (ignored binary).
- `python scripts/test.py --godot /workspace/work/save-safety/engine/Godot_v4.7.2-stable_linux.x86_64` — PASS: editor import; workflow 37, runner 10, synthetic transport 7, real-scene UI 15 assertions (69 total). Logs are `import.log` and `test_*.log`.
- `/workspace/work/save-safety/engine/Godot_v4.7.2-stable_linux.x86_64 --headless --path . --quit-after 5` — PASS, no script/runtime errors; `startup.log`.
- `git diff --check` — PASS.

`identity-red.log` retains the five pre-fix failures: imported IDs with path/dot/colon, a reserved-style uppercase name and internal-style underscore prefix were accepted by the domain, although the UI adopts IDs as Godot GraphNode names. Validation now uses a bounded lowercase ASCII identity grammar before constructing nodes.

No graphical capture was produced: no DISPLAY/X server/Xvfb exists in this execution environment, no sudo is available, and the configured Debian snapshot package index returned proxy HTTP 403 when an isolated temporary index was attempted. Headless scene instantiation/resize is source integration evidence only, not visual review, physical touch, accessibility or target-device acceptance. No screenshot filename is claimed.

Local model download was previously blocked by HTTP 403 and no genuine model was available to this workstream. HTTP fixtures explicitly return synthetic content. No Windows/Android package, signature, runtime/model redistribution or public download was produced or approved.
