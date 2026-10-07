# Stable approved sources

`content/sources.json` assigns source IDs independent of upload filenames or machine paths. Exercise packages cite IDs, a manifest version and a section or printed page range. The manifest hashes identify the exact supplied document bytes, not normalized text or an arbitrary copy of the same edition.

GURU-004 will bind IDs to local files through an ignored `var/source-bindings.json` mapping (source ID to absolute local path). That resolver is not implemented in this increment. At ingestion, require the source ID to exist in the pinned manifest, verify the file's SHA-256, and then extract only the referenced material. Missing files, mismatches and unresolved printed-page mappings must block ingestion rather than trigger browsing. A different PDF encoding requires an explicitly revised approved manifest. Printed pages 16–19 must be mapped to PDF pages during ingestion; they are not assumed to be PDF indices.

The manifest includes metadata and hashes only. Neither the source documents nor machine-specific bindings belong in Git. Do not silently replace version 1 of a manifest after use.

D01 is now exercise version 2 because its source metadata changed. Existing version-1 sessions still resume their stored snapshot and remain intact. Starting the new package while a version-1 session is active is intentionally refused; this increment does not migrate or delete learner history.
