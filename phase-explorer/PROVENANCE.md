# Data provenance

Source: https://data.phase-rs.dev/card-data.json (hosted snapshot, phase-rs/phase)
Fetched: 2026-09-21
Snapshot Last-Modified: 2026-04-20
ETag: 835ec8094e883fa623b65ea7e841bb9e
Size: 83,388,014 bytes
Entries: 34,645
License: MIT / Apache-2.0 dual (upstream)

Treated as READ-ONLY input. Nothing here modifies the phase.rs repo.
Schema cross-checked against upstream Rust definitions:
  crates/engine/src/types/card.rs        -> CardFace (per-entry body)
  crates/engine/src/database/card_db.rs  -> CardExportEntry (export wrapper)
No API.md exists in the repo (404); engine-wasm has no separate TS bindings file.

See KNOWN_LIMITATIONS.md for measured caveats and NAME_COLLISIONS.md for the
list of cards the face-name keying silently dropped.
