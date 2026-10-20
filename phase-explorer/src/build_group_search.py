#!/usr/bin/env python3
"""Group search from the main search box. NEW FILES ONLY (build/group_search/*, reports/group-search.md); the one corrections file this script may write is corrections/group_descriptions.json, and only with --draft.
Names, aliases and short descriptions of GROUPS are searched; the text of cards is not. Nothing is placed, no figure changes.

    python src/build_group_search.py            # a few seconds; run build_manual_layer.py first
    python src/build_group_search.py --draft    # (re)write the DRAFTED descriptions in corrections/group_descriptions.json; hand "edits" in that file are never touched

GROUP_SEARCH = True builds the files; False writes nothing and removes this script's own outputs, so the page draws no group section and the build directory is exactly the build without this layer.

Inputs: build/manual_index.json (the groups the page can open and place into), build/ability_taxonomy.json, tentative_placements.json, loose_groups.json, tag_placements.json, hand_group_hits.json, keyword_facet.json,
ability_taxonomy_cards.json / _members.json / _lookup.json (example lines, the word list), corrections/group_aliases.json (hand-edited), corrections/group_descriptions.json (drafts + hand edits), data/english_words.txt.

Outputs (build/group_search/): meta.json (the page reads only this at load), index.json (read on the first keystroke), words.txt (the real-word list, read only when a typed word needs checking).
A group is in the index only if the page can open it: leaf, keyword block, replacement block, hand-defined (not retired), tentative, plain loose, community tag, and the keyword facet. NOT: the 25 loose catch-alls and
"less common" buckets, sub-headings that were not promoted, the 404 annotation views, the 3 wide tags, retired groups, families, nodes and the pile pages.
"""
import collections
import io
import json
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manual_common as M

GROUP_SEARCH = True
HERE = M.HERE
BUILD = os.path.join(HERE, "build")
OUTDIR = os.environ.get("GROUP_SEARCH_OUT") or os.path.join(BUILD, "group_search")          # the env override is for the tests only
OUT_MD = os.path.join(HERE, "reports", "group-search.md")
if os.environ.get("GROUP_SEARCH_OUT"):
    OUT_MD = os.path.join(os.environ["GROUP_SEARCH_OUT"], "group-search.md")
CORR = os.environ.get("GROUP_SEARCH_CORR") or os.path.join(HERE, "corrections")
ALIASES = os.path.join(CORR, "group_aliases.json")
DESCS = os.path.join(CORR, "group_descriptions.json")
ENGLISH = os.path.join(HERE, "data", "english_words.txt")
HASHED = ("leaf", "tent", "loose")                    # ids that are hashes of a signature or a group key: they can change between builds (34 of 1,273 leaf ids did)
MAX_ALIAS_GROUPS = 5
MAX_ALIAS_LEN = 40
MAX_DESC = 200
LAYER_CODE = {"leaf": "l", "kw": "k", "rp": "r", "tent": "t", "loose": "o", "tag": "c", "hand": "h", "yk": "y"}
STOP = set("a an the of to and or for in on at by with from your you it its that this is are be as".split())


def jl(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def norm(s):
    """The search's folding: ASCII letters and digits, lower case, apostrophes dropped, anything else a space."""
    s = re.sub(r"['’]", "", str(s).lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


def page_key(gid):
    layer, rest = gid.split(":", 1)
    return {"leaf": "l:" + rest, "tent": "tg:" + rest, "loose": "lg:" + rest, "tag": "ct:" + rest, "kw": "kl:" + gid, "rp": "gl:" + rest, "hand": "hg:" + rest, "yk": "yk:" + rest}[layer]


def clip(s, n):
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0].rstrip(",;:.- ")
    return cut + "…"


def first_sentence(s, skip=()):
    """The first sentence that does not start with a skip prefix (provenance such as 'Read on 2026-10-16 ...', 'Phase 2: ...'); markdown links become their text; '(4 matches)' asides are dropped."""
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    for m in re.finditer(r"(.+?[.!?])(?:\s+|$)", s.strip()):
        t = m.group(1).strip()
        if not t.startswith(tuple(skip)):
            return re.sub(r"\s*\((?:\d[\d,]* (?:matches|cards)[^)]*)\)", "", t)
    return s.strip()


def load_groups():
    """-> list of dicts, one per searchable group (see the module docstring), sorted by gid."""
    mi = jl(os.path.join(BUILD, "manual_index.json"))
    tent = jl(os.path.join(BUILD, "tentative_placements.json"))
    loose = jl(os.path.join(BUILD, "loose_groups.json"))
    tag = jl(os.path.join(BUILD, "tag_placements.json"))
    tax = jl(os.path.join(BUILD, "ability_taxonomy.json"))
    hg = jl(os.path.join(BUILD, "hand_group_hits.json"))["groups"]
    kf = jl(os.path.join(BUILD, "keyword_facet.json"))["keywords"]
    out = []
    for gid, g in mi["groups"].items():
        if not g[4]:
            continue                                     # not offered: catch-alls, buckets, annotation views, retired hand groups
        layer, rest = gid.split(":", 1)
        e = {"gid": gid, "layer": layer, "name": g[0], "path": g[2], "size": g[1], "auto": 0, "slug": "", "twin": "", "desc_src": "", "full": g[0]}
        if layer == "leaf":
            lf = tax["leaves"][rest]
            e["auto"] = 1 if lf.get("auto_named") else 0
        elif layer == "tent":
            e["name"] = tent["groups"][rest]["short"]
            if rest in loose["groups"]:
                e["twin"] = "lg:" + rest                 # with "show tentative placements" off the same cards open as the loose group
        elif layer == "loose":
            e["name"] = loose["groups"][rest]["short"]
        elif layer == "tag":
            t = tag["groups"][rest]
            e["slug"] = t["slug"]
            e["desc_src"] = t["description"]
        elif layer == "hand":
            if hg[rest].get("retired"):
                continue
            e["desc_src"] = hg[rest]["note"]
        e["key"] = page_key(gid)
        out.append(e)
    for k, v in kf.items():
        out.append({"gid": "yk:" + k, "layer": "yk", "name": v["d"], "path": "By keyword", "size": v["n"], "auto": 0, "slug": "", "twin": "", "desc_src": "", "key": "yk:" + k})
    out.sort(key=lambda e: e["gid"])
    return out


def example_lines(groups):
    """gid -> list of the rules lines of the group's most popular members (up to 7), '~' replaced by 'this card'."""
    mi = jl(os.path.join(BUILD, "manual_index.json"))
    cards = jl(os.path.join(BUILD, "ability_taxonomy_cards.json"))["cards"]
    mem = jl(os.path.join(BUILD, "ability_taxonomy_members.json"))["leaves"]
    tent = jl(os.path.join(BUILD, "tentative_placements.json"))["groups"]
    loose = jl(os.path.join(BUILD, "loose_groups.json"))["groups"]
    tax = jl(os.path.join(BUILD, "ability_taxonomy.json"))
    pop = lambda o: (mi["cards"][o][4] if mi["cards"].get(o) and mi["cards"][o][4] is not None else 10 ** 9)
    res = {}
    for e in groups:
        layer, rest = e["gid"].split(":", 1)
        rows = []                                         # (oid, line)
        if layer == "leaf":
            for oid, ai in mem.get(rest, []):
                c = cards.get(oid)
                if c and ai is not None and ai < len(c["ab"]) and c["ab"][ai][0]:
                    rows.append((oid, c["ab"][ai][0]))
        elif layer == "tent":
            rows = [(r[0], r[1]) for r in tent[rest]["m"] if r[1]]
        elif layer == "loose":
            rows = [(r[0], r[1]) for r in loose[rest]["m"] if r[1]]
        elif layer == "rp":
            for oid in tax["blocks"]["replacement"]["leaves"][rest]["cards"]:
                c = cards.get(oid)
                if c and c["t"]:
                    rows.append((oid, c["t"].split("\n")[0]))
        rows.sort(key=lambda r: (pop(r[0]), r[0]))
        seen, lines = set(), []
        for oid, line in rows:
            line = line.replace("~", "this card")
            if line not in seen:
                seen.add(line)
                lines.append(line)
            if len(lines) >= 7:
                break
        res[e["gid"]] = lines
    return res


def draft_description(e, lines):
    """-> (text, basis). One short sentence from data that already exists; never from a model."""
    layer = e["layer"]
    if layer == "tag" and e["desc_src"]:
        return clip(first_sentence(e["desc_src"]), 140), "tag description"
    if layer == "hand" and e["desc_src"]:
        return clip(first_sentence(e["desc_src"], ("Read ", "Phase 2", "No 'not'", "The 'not'")), 160), "hand note"
    if layer == "kw":
        n = e["name"]
        if n.endswith(": other combinations"):
            return "Rules text is only keywords, including %s in combinations that have no group of their own." % n.split(":")[0], "keyword name"
        return "Rules text is only the keyword%s %s." % ("s" if "+" in n else "", n.replace(" + ", " and ")), "keyword name"
    if layer == "yk":
        return "Every card with the keyword %s, wherever it is placed. A filter, not a placement." % e["name"], "keyword name"
    if lines:
        # the most typical of the first 5 lines: the one sharing the most words with the others (a line from a card that does something else shares few); ties go to the shorter
        ws = [set(norm(x).split()) for x in lines[:5]]
        sc = [sum(len(ws[i] & ws[j]) / float(len(ws[i] | ws[j]) or 1) for j in range(len(ws)) if j != i) for i in range(len(ws))]
        pick = max(range(len(ws)), key=lambda i: (round(sc[i], 6), -len(lines[i]), lines[i]))
        pick = lines[pick]
        return "Example: “%s”" % clip(pick, 110), "member line"
    return "", ""


def read_json_or(path, default):
    if os.path.exists(path):
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return default


def draft(groups):
    """Write the drafts section of corrections/group_descriptions.json (creating the file); 'edits' and every other key stay exactly as they are."""
    doc = read_json_or(DESCS, None) or {
        "_about": "Short descriptions of groups, shown as a one-line subtitle on a search result and searched after the name (labelled 'matched: description'). 'drafts' are written by "
                  "src/build_group_search.py --draft from existing data (tag descriptions, hand-group notes, the lines of the most popular members) and are flagged auto_described; they are rewritten each time. "
                  "'edits' are written by hand, keyed by the same group id, and always win; --draft never touches them. Prefer stable ids (hand:, kw:, rp:, tag:); leaf:, tent: and loose: ids are hashes and can change between builds "
                  "(about 34 of 1,273 leaf ids did), and an edit whose id vanishes is reported as an orphan on every build.",
        "v": 1, "edits": {}}
    lines = example_lines(groups)
    drafts = {}
    for e in groups:
        text, basis = draft_description(e, lines[e["gid"]])
        if text:
            drafts[e["gid"]] = {"text": text, "auto_described": True, "basis": basis, "name": e["name"]}
    doc["drafts"] = drafts
    with io.open(DESCS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print("drafted %d descriptions into %s (%d hand edits kept)" % (len(drafts), DESCS, len(doc.get("edits", {}))))
    return doc


def check_aliases(groups, doc):
    """-> (aliases {phrase: {g, fit, note}}, errors, warnings, stats). A bad alias is an ERROR (the build fails); a stale name or a hashed id is a warning."""
    by = {e["gid"]: e for e in groups}
    errs, warns, out = [], [], {}
    seen = {}
    names = {norm(e["name"]) for e in groups}
    hashed = 0
    for phrase, a in sorted((doc.get("aliases") or {}).items()):
        k = norm(phrase)
        if not k or len(k) > MAX_ALIAS_LEN:
            errs.append("alias %r: empty or longer than %d characters after folding" % (phrase, MAX_ALIAS_LEN))
            continue
        if k in seen:
            errs.append("alias %r duplicates %r after folding" % (phrase, seen[k]))
            continue
        seen[k] = phrase
        gl = a.get("groups") if isinstance(a, dict) else None
        if not isinstance(gl, list) or not 1 <= len(gl) <= MAX_ALIAS_GROUPS:
            errs.append("alias %r: needs 1 to %d groups" % (phrase, MAX_ALIAS_GROUPS))
            continue
        if a.get("fit") not in ("good", "partial"):
            errs.append("alias %r: fit must be good or partial" % phrase)
        if a.get("fit") == "partial" and not str(a.get("note") or "").strip():
            errs.append("alias %r: a partial alias needs a note saying what it leaves out" % phrase)
        ids = []
        for g in gl:
            gid = g.get("id") if isinstance(g, dict) else None
            if gid in ids:
                errs.append("alias %r lists %s twice" % (phrase, gid))
            elif gid not in by:
                errs.append("alias %r: %s is not a group the page can open (unknown, not offered or retired)" % (phrase, gid))
            else:
                ids.append(gid)
                if g.get("name") and g["name"] not in (by[gid]["name"], by[gid].get("full")):
                    warns.append("alias %r: %s was named %r, now %r" % (phrase, gid, g["name"], by[gid]["name"]))
                if gid.split(":")[0] in HASHED:
                    hashed += 1
                if by[gid]["size"] < 5:
                    warns.append("alias %r: %s has only %d cards" % (phrase, gid, by[gid]["size"]))
        if k in names:
            warns.append("alias %r is also a group name (harmless: the exact name ranks first)" % phrase)
        if ids:
            out[k] = {"p": phrase, "g": ids, "fit": a.get("fit", "good"), "note": str(a.get("note") or "")}
    return out, errs, warns, {"hashed_refs": hashed, "groups_referenced": len({g for v in out.values() for g in v["g"]})}


def check_descriptions(groups, doc):
    by = {e["gid"]: e for e in groups}
    errs, orphans, hashed_edits = [], {"edits": [], "drafts": []}, []
    desc = {}
    for part in ("drafts", "edits"):                      # edits last, so they win
        for gid, d in sorted((doc.get(part) or {}).items()):
            text = d.get("text") if isinstance(d, dict) else None
            if gid not in by:
                orphans[part].append(gid)
                continue
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_DESC or re.search(r"[\x00-\x1f]", text):
                errs.append("%s %s: text must be 1 to %d characters with no control characters" % (part, gid, MAX_DESC))
                continue
            desc[gid] = (text.strip(), 1 if part == "drafts" else 0)
            if part == "edits" and gid.split(":")[0] in HASHED:
                hashed_edits.append(gid)
    return desc, errs, orphans, hashed_edits


def words_list(groups, aliases):
    """The real-word list: standard English + card-name words + oracle-text words + group words (letters only, 3+ letters)."""
    w = set()
    tok = lambda s: [t for t in norm(s).split() if re.fullmatch(r"[a-z]{3,}", t)]
    if os.path.exists(ENGLISH):
        with io.open(ENGLISH, encoding="utf-8") as fh:
            w.update(x.strip() for x in fh if x.strip())
    look = jl(os.path.join(BUILD, "ability_taxonomy_lookup.json"))
    for ent in look["entries"]:
        for n in [ent[1]] + list(ent[2]):
            w.update(tok(n))
    for c in jl(os.path.join(BUILD, "ability_taxonomy_cards.json"))["cards"].values():
        w.update(tok(c["t"]))
    for e in groups:
        w.update(tok(e["name"]))
        w.update(tok(e["slug"]))
    for a in aliases.values():
        w.update(tok(a["p"]))
    return sorted(w)


def build(force=None, draft_only=False):
    on = GROUP_SEARCH if force is None else force
    ready = on and os.path.exists(os.path.join(BUILD, "manual_index.json"))
    if not ready:
        if not os.environ.get("GROUP_SEARCH_OUT"):
            if os.path.isdir(OUTDIR):
                shutil.rmtree(OUTDIR)
            if os.path.exists(OUT_MD):
                os.remove(OUT_MD)
        print("GROUP_SEARCH is off (or build/manual_index.json is missing): nothing written")
        return 0
    groups = load_groups()
    if draft_only:
        draft(groups)
        return 0
    adoc = read_json_or(ALIASES, {"aliases": {}})
    ddoc = read_json_or(DESCS, {})
    aliases, aerr, awarn, astat = check_aliases(groups, adoc)
    desc, derr, orphans, hashed_edits = check_descriptions(groups, ddoc)
    if aerr or derr:
        for m in aerr + derr:
            print("ERROR", m)
        print("group search NOT built: %d error(s)" % (len(aerr) + len(derr)))
        return 1
    rows = []
    for e in groups:
        d = desc.get(e["gid"], ("", 0))
        rows.append([e["gid"], e["key"], e["name"], e["path"], LAYER_CODE[e["layer"]], e["size"], e["auto"], d[0], d[1], e["twin"], e["slug"]])
    words = words_list(groups, aliases)
    by_layer = collections.Counter(e["layer"] for e in groups)
    meta = {"v": 1, "enabled": True, "groups": len(rows), "by_layer": dict(sorted(by_layer.items())), "aliases": len(aliases), "described": sum(1 for r in rows if r[7]),
            "auto_described": sum(1 for r in rows if r[7] and r[8]), "words": len(words)}
    dump(os.path.join(OUTDIR, "index.json"), {"v": 1, "groups": rows, "aliases": aliases})
    dump(os.path.join(OUTDIR, "meta.json"), meta)
    with io.open(os.path.join(OUTDIR, "words.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(words) + "\n")
    # ---- the report (deterministic: no dates)
    L = ["# Group search", "", "Built by `src/build_group_search.py` (flag `GROUP_SEARCH`). Names, aliases and short descriptions of groups; never the text of cards. Nothing is placed and no figure changes.", "",
         "## Groups in the search: %d" % len(rows), ""]
    L += ["| layer | groups |", "|---|---|"] + ["| %s | %d |" % (k, v) for k, v in sorted(by_layer.items())]
    L += ["", "## Aliases: %d (%d groups referenced)" % (len(aliases), astat["groups_referenced"]), ""]
    L.append("- aliases pointing at a hashed id (leaf, tentative or loose; about 34 of 1,273 leaf ids changed between earlier builds): **%d** of %d references" % (astat["hashed_refs"], sum(len(v["g"]) for v in aliases.values())))
    L.append("- partial aliases (each carries a note saying what it leaves out): %s" % ", ".join(sorted(v["p"] for v in aliases.values() if v["fit"] == "partial")))
    cand = adoc.get("candidate_groups") or {}
    if cand:
        L.append("- candidate groups (a term with no group to point at): " + "; ".join("**%s** - %s" % (k, v) for k, v in sorted(cand.items())))
    L += ["- warnings: %d" % len(awarn)] + ["  - " + w for w in awarn]
    L += ["", "## Descriptions: %d of %d groups (%d drafted, %d by hand)" % (meta["described"], len(rows), meta["auto_described"], meta["described"] - meta["auto_described"]), ""]
    L.append("- orphaned hand edits (id no longer a searchable group): %s" % (", ".join(orphans["edits"]) or "none"))
    L.append("- orphaned drafts (rewrite them with `--draft`): %d" % len(orphans["drafts"]))
    L.append("- hand edits at a hashed id (can orphan): %s" % (", ".join(hashed_edits) or "none"))
    L += ["", "## Real-word list: %d words" % len(words), ""]
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print("group search built: %d groups, %d aliases, %d described (%d drafted), %d words; alias warnings %d; orphaned edits %d, drafts %d" % (
        len(rows), len(aliases), meta["described"], meta["auto_described"], len(words), len(awarn), len(orphans["edits"]), len(orphans["drafts"])))
    for w in awarn:
        print("warning", w)
    return 0


def main(force=None):
    return build(force=force, draft_only="--draft" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
