# Evidence Flow development build

The README product promise remains the scope. This Godot 4.7.2 source implements a visual document → extraction → translation → report workflow, editable steps/options/connections, inspectable intermediate output, cancellation, explicit local/template modes, workspace save/reopen/recovery-copy and report export. It is a development build, not an approved Windows or Android release.

## Run and verify

Use the reviewed Godot 4.7.2 editor. Build the first-party native durability extension with a host C compiler before import (the compiler and Python are developer tools, not player requirements):

```sh
python scripts/build_save_adapter.py
python scripts/test.py --godot /absolute/path/to/Godot_v4.7.2-stable_linux.x86_64
/absolute/path/to/Godot_v4.7.2-stable_linux.x86_64 --path .
```

Windows host builds use the Visual Studio x64 C toolchain. The build helper also accepts `--android-ndk` for the reviewed NDK 28.2.13676358 arm64/API26 adapter; this alone does not produce or validate an Android application. Native binaries, Godot cache and build output are deliberately ignored. The pinned MIT Godot interface header and its license are under `native/durability/`.

## Use and recovery

Import a UTF-8 TXT or Markdown document of 1–65,536 bytes. Choose a step to inspect its current output or change its option. Drag graph connections, or use the source/destination menus and Connect/Disconnect controls. Run requires an acyclic graph with one input per non-read step. Disconnected drafts cannot be saved or run until repaired. Up to 16 steps are supported; graph layout is regenerated when edited or reopened.

Template mode performs literal line extraction, retains the original text with a conspicuous unavailable-translation label, and formats reports. It makes no AI or translation claim. Local AI mode sends bounded, nonstreaming OpenAI-compatible requests only to a literal `http://127.0.0.1:PORT/v1/chat/completions` server. Supply the alias that server actually serves. Redirects and remote endpoints are refused. Failed local inference does not switch to templates. Review generated content before use.

Workspace data lives in the separate EvidenceFlow Godot user-data directory. Run saves before starting and after each intermediate output. Completed partial outputs survive cancellation; interrupted runs reopen as interrupted and require an explicit new run. Save uses the shared first-party durability adapter, generation backup and stale-writer checks. Corrupt originals are preserved and cannot be silently overwritten. Preserve the whole directory if a save fails; inspect the error and recovery files. Open a valid `.backup` separately, then use Save copy with a new filename. Export also requires a new filename and records the output mode and run status. No automatic network export is provided.

## Evidence and remaining acceptance

`docs/evidence/` retains exact source-test logs, including initial failures and the unsafe visual node identity regression (five failures before validation was tightened). Headless UI tests instantiate the real scene, import a real file, execute template steps, save/reopen/export, preserve state after rejected import, edit/connect/disconnect and resize to 390 pixels. Synthetic HTTP fixtures check protocol handling only; they are not model inference.

Actual bundled local-model inference, runtime/model delivery and licensing/notice/hash verification, Windows installer/export acceptance, Android application packaging/touch/lifecycle/storage/runtime integration, physical device tests, accessibility review with assistive technology, signing and public release acceptance remain unimplemented or unverified. No bundled runtime/model is supplied by this source, and no cloud inference is substituted. Linux source tests cannot close those release gates. Public downloads must remain blocked until canonical programme gates pass.
