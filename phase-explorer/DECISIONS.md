# Decision log

Newest first. Each entry records what was decided, the numbers it was decided
on, and what it does *not* establish.

> This file was started on `main` on 2026-09-24. An earlier decision log exists
> on the `archive/zone-choice-leaf-map` branch and was never merged here; it is
> not duplicated into this file.

---

## 2026-09-24 — Type sub-branches: the mixing is hidden, not fixed

Sub-branches make the browsing experience look clean, but the underlying
leaf-level mixing — **74 leaves / 2,784 cards** from the type audit — is
unchanged: it is hidden from the user, not fixed. **Ramp** is the one branch
where this pass happened to be complete (100% of its exposure was tier A);
**Burn** and **Tutor** are still mostly tier-B exposure and were not addressed
by this pass.

### The numbers behind it

| | leaf-level exposure | tier A (addressed) | tier B (untouched) |
|---|---|---|---|
| Ramp | 49% | 49% | 0% |
| Tutor | 51% | 12% | 38% |
| Burn | 46% | 11% | 35% |

The sub-branch layer verifies clean — 89 typed sub-branches, **0** still
type-heterogeneous under the identical 50% test. That is a real result about
the *containers*, and only about the containers.

### What this does NOT establish

- **It does not establish that the leaves were fixed.** Nothing was
  re-clustered. Leaf 44 is still 513 cards at Creature 44% / Land 30% /
  Artifact 28%, and `reports/leaf-type-audit.md` still reports all 74 leaves.
- **It does not establish that Burn and Tutor are resolved.** Their queue
  entries for leaves 567 and 374 were recorded as `split` to make the queue
  reflect reality, since their parents were split via other tier-A leaves — but
  no tier-B work was done, and their tier-B exposure (35% / 38%) stands.
- **"Exposure dropped to 0%" is only true of the sub-branch layer.** Saying it
  of the branch would be measuring one layer and naming another.

Removing the mixing at its source means re-clustering with card type in the
feature set, which invalidates every leaf id, branch assignment, both leaf maps
and the sector geometry. That decision has not been taken.

Artifacts: [`reports/sub-branches.md`](reports/sub-branches.md) ·
[`reports/leaf-type-audit.md`](reports/leaf-type-audit.md) ·
`src/sub_branches.py` · `src/audit_leaf_types.py`
