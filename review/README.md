# Pinned downloaded Windows inspection

Inspection is read-only and does not build, sign, publish, overwrite or promote assets. inspection-lock.json freezes the exact already-passed original source/run/release tag and all four server SHA256/size identities. A different inspector source commit never relabels those package bytes.

The main-only workflow checks out its immutable GitHub SHA. GitHub requires contents-write even for reading private drafts; the first-party inspector uses GET/download only and strips GH_TOKEN/GITHUB_TOKEN before running the downloaded executable. After verifying all downloaded asset bytes and receipt identities it rejects unsafe Windows paths, aliases, case collisions, symlinks/reparse entries, extras and manifest-byte mismatches before extraction. PE0.1.0.0, native write/read, actual JSON readback and headless UI initialization run in an isolated profile from the extracted directory.

This is not rendered UI, physical device, genuine inference, production signing or Android acceptance. The package has no model/runtime bundled. Existing moving Actions tags remain a production dependency review/pin prerequisite. Original draft packages are retained unchanged.

Fresh independent source review found no important blocker. Deferred hardening: receipt attempt/product/tag checks are redundant with the pinned receipt bytes but could be made explicit; pure tests could add broader manifest/receipt permutations. Current guards have seven real-byte/path/identity negative test cases. Actual Windows job results must be recorded before marking inspection PASS.
