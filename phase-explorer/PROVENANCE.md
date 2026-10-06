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

Layers added on top of the snapshot (the snapshot file itself is never modified):
  data/overlay/recovered-cards.json          63 cards the face-name keying dropped (oracle-gen v0.1.15)
  data/overlay/commander-*.json, unrecognized-restriction-fix.json,
  data/overlay/activation-timing-split-fix.json    parser-fix overlays (see KNOWN_LIMITATIONS.md)
  data/overlay/new-release-cards.json        1,383 cards released after the snapshot, generated
                                             2026-10-03 by oracle-gen v0.1.15 + the local fixes from
                                             MTGJSON AtomicCards 5.3.0+20261003
                                             (data/AtomicCards-20261003.json.gz, the source of ONLY those
                                             cards; data/AtomicCards.json.gz, 5.3.0+20260921, remains the
                                             universe and the gate's control set)
The hosted file was checked again on 2026-10-03: data.phase-rs.dev/card-data.json is still the
April export (Last-Modified 2026-04-20, same ETag); upstream's current build is at a content-hashed
URL (card-data-b365361edafd3d90.json, MTGJSON 5.3.0+20261002) and re-parses 93.5% of the existing
cards differently, so it is deliberately not used.

See KNOWN_LIMITATIONS.md for measured caveats and NAME_COLLISIONS.md for the
list of cards the face-name keying silently dropped.
