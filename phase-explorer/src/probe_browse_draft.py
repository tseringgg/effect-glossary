#!/usr/bin/env python3
"""Part 2 of the browse-group probe: a deterministic DRAFT mapping of every fine group to a proposed browse group. READ ONLY on corrections/ and build/; writes build/browse_groups_draft.json (new file).

    python src/probe_browse_draft.py [OUT_JSON]

No leaf, group, id, placement, suggestion, correction, site file or figure is touched. Nothing here is a hand edit: every assignment comes from a rule, and every mapping records its basis and confidence.

THE RULES, in the order the brief gave them (the first that applies decides the primary browse group):
  1 merged page       the 13 hand-merged pages in corrections/merged_groups.json (union the members)                                    basis "merged page"             confidence high
  2 name twin         groups with the same core name (qualifiers, 'Family ›' prefix and 'less common kinds' removed) form one UNIT        basis "name twin"               high (medium if 2+ layers)
  3 alias             the hand aliases in corrections/group_aliases.json name deckbuilder concepts; aliases whose group lists overlap are one concept
                      (Jaccard >= 0.5), and a unit that holds a group listed under an alias goes to that concept                           basis "alias"                   high (fit good) / medium (partial)
  4 tag slug          a community tag's slug root ("removal-bounce" -> "removal"): joins the alias concept the root names, else the root's own concept (2+ tags)   basis "tag slug"   medium
  5 keyword           a keyword block goes to its keyword's concept; a two-keyword combination goes to both (the only structural second mapping)   basis "keyword"      high
  6 broad bucket      a leaf goes to its taxonomy node (family › node: the existing 'broad bucket' under the 15 topics); a tentative or loose group goes to the leaf unit whose name
                      shares the most words with it (>= 0.5), else to the taxonomy node whose name does (>= 0.34), else 'Other <family>'    basis "bucket node" / "name words" / "family fallback"   medium / medium / low
  7 own idea          a hand-defined group no rule reaches is its own browse group (Initiative, Cataclysm, Siege ...)                      basis "own idea"                medium
CARD OVERLAP is a HINT ONLY. It never assigns. It records the browse group the group overlaps most (>= 70% of the group inside it) when that is not its own, as 'overlap_hint' for a human to look at.
A second browse group (at most two): a keyword combination (both keywords), and an alias that names a second concept for a unit. Nothing else.
"""
import collections
import hashlib
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import browse_probe_data as P

STOP = set("a an the of to and or for in on at by with from your you it its that this is are be as card cards permanent permanents creature creatures target player players".split())
KEEPSTOP = set()


def toks(s):
    s = P.core_name(s) if " › " in s or "(" in s else re.sub(r"[^a-z0-9+/ ]+", " ", s.lower())
    out = set()
    for w in s.split():
        if w in STOP or len(w) < 2:
            continue
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


class UF:
    def __init__(self, items):
        self.p = {i: i for i in items}

    def f(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def u(self, a, b):
        a, b = self.f(a), self.f(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def title(s):
    s = s.strip()
    return s[:1].upper() + s[1:]


def build(D):
    fine = sorted(D.fine)
    uf = UF(fine)
    unit_basis = {}                                         # gid -> set of unit-forming bases
    # ---- 1 merged pages
    for slug, pg in D.merged.items():
        if pg.get("retired"):
            continue
        mem = [m for m in pg["members"] if m in D.fine]
        for m in mem[1:]:
            uf.u(mem[0], m)
        for m in mem:
            unit_basis.setdefault(m, set()).add("merged page")
    # ---- 2 name twins
    cores = collections.defaultdict(list)
    for g in fine:
        c = P.core_name(D.name(g))
        if c:
            cores[c].append(g)
    for c, gs in cores.items():
        if len(gs) > 1:
            for m in gs[1:]:
                uf.u(gs[0], m)
            for m in gs:
                unit_basis.setdefault(m, set()).add("name twin")
    units = collections.defaultdict(list)
    for g in fine:
        units[uf.f(g)].append(g)
    unit_of = {g: uf.f(g) for g in fine}
    unit_card_set = {u: set().union(*[D.members.get(g, set()) for g in gs]) for u, gs in units.items()}

    # ---- 3 alias concepts
    al = [(k, v) for k, v in D.aliases.items()]
    aset = {k: {g["id"] for g in v["groups"] if g["id"] in D.fine} for k, v in al}
    auf = UF([k for k, _ in al])
    for i, (k1, _) in enumerate(al):
        for k2, _ in al[i + 1:]:
            if aset[k1] and aset[k2] and jac(aset[k1], aset[k2]) >= 0.5:
                auf.u(k1, k2)
    aliases_by_concept = collections.defaultdict(list)
    for k, _ in al:
        aliases_by_concept[auf.f(k)].append(k)
    concept_of_alias = {}
    alias_concepts = {}                                      # key -> {name, aliases, fit, gids}
    order = {k: i for i, (k, _) in enumerate(al)}
    for root, ks in aliases_by_concept.items():
        # name: the alias with the most groups; ties -> the one with more words; ties -> file order
        best = sorted(ks, key=lambda k: (-len(aset[k]), -len(k.split()), order[k]))[0]
        key = "alias:" + best
        gids = set()
        for k in ks:
            gids |= aset[k]
        fits = {D.aliases[k].get("fit") for k in ks}
        alias_concepts[key] = {"name": title(best), "aliases": sorted(ks, key=lambda k: order[k]), "fit": "good" if "good" in fits else "partial", "gids": gids}
        for k in ks:
            concept_of_alias[k] = key
    gid_alias_concepts = collections.defaultdict(list)       # gid -> [concept keys] in file order
    for k, v in al:
        for g in aset[k]:
            c = concept_of_alias[k]
            if c not in gid_alias_concepts[g]:
                gid_alias_concepts[g].append(c)

    # ---- 4 tag slug roots
    root_of = {}
    for g in fine:
        if P.layer_of(g) == "tag" and g in D.slug:
            root_of[g] = D.slug[g].split("-")[0]
    root_n = collections.Counter(root_of.values())
    alias_words = collections.defaultdict(set)               # a word -> alias concept keys whose alias text has it as a whole word or starts with it
    for key, c in alias_concepts.items():
        for a in c["aliases"]:
            for w in a.split():
                alias_words[w].add(key)
    # also the explicit tag hints in the alias lists: a tag listed under an alias is already in that concept (rule 3)

    # ---- 5/6 structure per group
    kw_primary, kw_second = {}, {}
    for g in fine:
        if P.layer_of(g) == "kw":
            br = D.kw_branch.get(g)
            if g.startswith("kw:other:"):
                br = g[len("kw:other:"):]
            if g.startswith("kw:Landwalk"):
                br = "Landwalk"
            if not br:
                br = D.name(g).split(":")[0].split(" + ")[0]
            kw_primary[g] = br
            nm = D.name(g)
            if " + " in nm:
                parts = [p.strip() for p in nm.split(" + ")]
                other = [p for p in parts if p.lower() != br.lower()]
                if other:
                    kw_second[g] = other[0]
    rp_branch = {}
    for br in D.tax["blocks"]["replacement"]["branches"]:
        for lid in br["leaves"]:
            rp_branch[lid if lid.startswith("rp:") else "rp:" + lid] = br["name"]

    node_leaf_names = collections.defaultdict(list)          # node id -> [(leaf gid, tokens)]
    for g in fine:
        if g in D.node_of:
            node_leaf_names[D.node_of[g][2]].append(g)
    node_info = {}
    for f in D.tax["families"]:
        for nd in f["nodes"]:
            node_info[nd["id"]] = (f["name"], nd["name"])
    node_name_count = collections.Counter(n for _, n in node_info.values())
    leaf_tok = {g: toks(D.name(g)) for g in fine}
    fam_by_unit_leaf = {}

    def node_concept(nid):
        fam, nm = node_info[nid]
        label = nm if node_name_count[nm] == 1 else "%s (%s)" % (nm, fam)
        return "node:" + nid, label

    # ---- assign units
    assign = {}                                              # unit -> dict(primary key, name, basis, conf, second, notes)
    concept_name = {}
    for key, c in alias_concepts.items():
        concept_name[key] = c["name"]

    def unit_alias_choice(gs):
        cnt = collections.Counter()
        for g in gs:
            for c in gid_alias_concepts.get(g, ()):
                cnt[c] += 1
        if not cnt:
            return None, None
        ranked = sorted(cnt, key=lambda c: (-cnt[c], len(alias_concepts[c]["gids"]), c))
        return ranked[0], (ranked[1] if len(ranked) > 1 else None)

    for u in sorted(units):
        gs = sorted(units[u])
        layers = {P.layer_of(g) for g in gs}
        res = {"key": None, "name": None, "basis": None, "conf": None, "second": None, "second_basis": None, "notes": []}
        # 3 alias (a unit with a group listed under a hand alias)
        c1, c2 = unit_alias_choice(gs)
        if c1:
            res.update(key=c1, name=alias_concepts[c1]["name"], basis="alias", conf="high" if alias_concepts[c1]["fit"] == "good" else "medium")
            if c2:
                res.update(second=c2, second_basis="alias")
            assign[u] = res
            continue
        # 5 keyword
        if layers == {"kw"} or ("kw" in layers and len(layers) == 1):
            br = kw_primary.get(gs[0]) or D.name(gs[0])
            key = "kw:" + br.lower().replace(" ", "")
            concept_name[key] = br
            res.update(key=key, name=br, basis="keyword", conf="high")
            sec = kw_second.get(gs[0])
            if sec:
                skey = "kw:" + sec.lower().replace(" ", "")
                concept_name.setdefault(skey, sec)
                res.update(second=skey, second_basis="keyword")
            assign[u] = res
            continue
        # replacement block
        if layers == {"rp"}:
            br = rp_branch.get(gs[0], "Replacement effects")
            key = "rp:" + br.lower().replace(" ", "")
            concept_name[key] = br
            res.update(key=key, name=br, basis="bucket node", conf="medium")
            assign[u] = res
            continue
        # 4 tag slug
        tag_gs = [g for g in gs if g in root_of]
        if tag_gs:
            root = collections.Counter(root_of[g] for g in tag_gs).most_common(1)[0][0]
            keys = alias_words.get(root, set())
            if len(keys) == 1:
                k = next(iter(keys))
                res.update(key=k, name=alias_concepts[k]["name"], basis="tag slug", conf="medium")
                assign[u] = res
                continue
            if root_n[root] >= 2 and root not in ("synergy", "gives", "gains", "typal", "hate", "protects", "repeatable", "conjure", "scales", "multi", "multiple", "opponent", "power", "toughness", "castable", "cast", "per", "death"):
                key = "tagroot:" + root
                concept_name[key] = title(root.replace("-", " "))
                res.update(key=key, name=title(root), basis="tag slug", conf="medium")
                assign[u] = res
                continue
            if root_n[root] >= 2 and root in ("synergy", "gives", "gains", "typal", "hate", "protects", "repeatable", "conjure"):
                nm = {"synergy": "Synergy: cares about a particular thing", "gives": "Gives a keyword to your creatures", "gains": "Gains a keyword", "typal": "Tribal: cares about a creature type",
                      "hate": "Hate: works against a kind of card", "protects": "Protects your permanents", "repeatable": "Repeatable effects", "conjure": "Conjure cards (Alchemy)"}[root]
                key = "tagroot:" + root
                concept_name[key] = nm
                res.update(key=key, name=nm, basis="tag slug", conf="medium")
                assign[u] = res
                continue
        # 6 bucket node (leaf)
        leaf_gs = [g for g in gs if g in D.node_of]
        if leaf_gs:
            nid = collections.Counter(D.node_of[g][2] for g in leaf_gs).most_common(1)[0][0]
            sg = D.leaf_sig.get(leaf_gs[0], "")
            mt = re.search(r"obj=(\w+) · (?:[a-z]+=[^·]+· )*tok=[^|·]*\|name:([^·]+?)\s*$", sg)
            if node_info[nid][0] == "Tokens" and mt and mt.group(1) == "Artifact":       # a named artifact token (Treasure, Food, Clue ...) is a choice of its own
                tn = mt.group(2).strip()
                key = "tok:" + tn.lower()
                concept_name[key] = tn + " tokens"
                res.update(key=key, name=tn + " tokens", basis="bucket node + token name", conf="medium")
                assign[u] = res
                continue
            key, nm = node_concept(nid)
            concept_name[key] = nm
            res.update(key=key, name=nm, basis="bucket node", conf="medium")
            assign[u] = res
            continue
        # tentative / loose
        tl = [g for g in gs if P.layer_of(g) in ("tent", "loose")]
        if tl:
            best, bj = None, 0.0
            tt = set().union(*[toks(D.name(g)) for g in tl])
            for u2 in sorted(units):
                if u2 == u or not any(g in D.node_of for g in units[u2]):
                    continue
                tt2 = set().union(*[leaf_tok[g] for g in units[u2] if g in D.node_of])
                j = jac(tt, tt2)
                if j > bj:
                    best, bj = u2, j
            if best and bj >= 0.5:
                nid = collections.Counter(D.node_of[g][2] for g in units[best] if g in D.node_of).most_common(1)[0][0]
                key, nm = node_concept(nid)
                concept_name[key] = nm
                res.update(key=key, name=nm, basis="name words", conf="medium")
                res["notes"].append("name words %.2f with %s" % (bj, D.name(sorted(units[best])[0])[:50]))
                assign[u] = res
                continue
            fam = D.family_name.get(tl[0]) or "Other"
            bn, bnj = None, 0.0
            for nid, (f, nm) in node_info.items():
                if f != fam:
                    continue
                j = jac(tt, toks(nm))
                if j > bnj:
                    bn, bnj = nid, j
            if bn and bnj >= 0.34:
                key, nm = node_concept(bn)
                concept_name[key] = nm
                res.update(key=key, name=nm, basis="name words", conf="medium")
                res["notes"].append("name words %.2f with node '%s'" % (bnj, nm))
                assign[u] = res
                continue
            key = "fam:" + fam
            concept_name[key] = "Other: " + fam
            res.update(key=key, name="Other: " + fam, basis="family fallback", conf="low")
            assign[u] = res
            continue
        # 7 own idea
        g0 = gs[0]
        key = "own:" + g0
        concept_name[key] = D.name(g0)
        res.update(key=key, name=D.name(g0), basis="own idea", conf="medium")
        assign[u] = res

    # ---- C1: concepts whose display names are the same (once normalised) are one idea: merge them (the name-twin rule, applied to the concepts)
    by_nm = collections.defaultdict(list)
    for u, r in assign.items():
        for k in (r["key"], r["second"]):
            if k:
                by_nm[re.sub(r"[^a-z0-9+/]+", " ", concept_name[k].lower()).strip()].append(k)
    remap = {}
    for nm, ks in by_nm.items():
        ks = sorted(set(ks))
        if nm and len(ks) > 1:
            for k in ks[1:]:
                remap[k] = ks[0]
    merged_concepts = {}
    for u, r in assign.items():
        for f in ("key", "second"):
            k = r[f]
            if k in remap:
                merged_concepts.setdefault(remap[k], set()).update([k, remap[k]])
                r[f] = remap[k]
                r["notes"].append("same name as another concept: merged")
        if r["second"] and r["second"] == r["key"]:
            r["second"] = None
    # ---- browse groups
    bgs = collections.OrderedDict()
    members = collections.defaultdict(list)                  # concept key -> [(gid, role)]
    for u, r in assign.items():
        for g in units[u]:
            members[r["key"]].append((g, "primary"))
            if r["second"]:
                members[r["second"]].append((g, "second"))
    # unit-forming basis refines the confidence of the single mapping
    mapping = {}
    for u, r in assign.items():
        for g in units[u]:
            b, conf = r["basis"], r["conf"]
            ub = unit_basis.get(g, set())
            note = list(r["notes"])
            if "merged page" in ub:
                b = "merged page" if b in ("bucket node", "name words", "family fallback") else b + " + merged page"
                conf = "high" if conf in ("medium",) else conf
            elif "name twin" in ub and b in ("bucket node", "name words", "family fallback"):
                b = b + " + name twin"
            if len(units[u]) > 1 and len({P.layer_of(x) for x in units[u]}) > 1 and "name twin" in ub:
                note.append("twins across layers")
            mapping[g] = {"primary": r["key"], "basis": b, "conf": conf, "second": r["second"], "second_basis": r["second_basis"], "notes": note}

    # ---- a group whose name shares no content word with its browse group's name is a weak mapping, whatever the basis: low (a human reads these first)
    for g, mp in mapping.items():
        if mp["basis"].split(" + ")[0] in ("bucket node", "tag slug", "name words") and mp["conf"] != "high":
            gt, bt = toks(D.name(g)), toks(concept_name[mp["primary"]])
            if gt and bt and not (gt & bt):
                mp["conf"] = "low"
                mp["notes"].append("its name shares no word with the browse group's name")
    # ---- overlap hint (never assigns, never changes a confidence)

    bg_cards = {k: set().union(*[D.members.get(g, set()) for g, _ in v]) for k, v in members.items()}
    for g, mp in mapping.items():
        mine = D.members.get(g, set())
        if not mine:
            mp["overlap_own"] = None
            continue
        rest = set()
        for g2, role in members[mp["primary"]]:
            if g2 != g:
                rest |= D.members.get(g2, set())
        own = len(mine & rest) / len(mine) if rest else None
        mp["overlap_own"] = None if own is None else round(own, 2)
        if len(mine) >= 5:
            best, bo = None, 0.0
            for k, cs in bg_cards.items():
                if k == mp["primary"] or k == mp["second"]:
                    continue
                o = len(mine & cs) / len(mine)
                if o > bo or (o == bo and best and k < best):
                    best, bo = k, o
            if best and bo >= 0.70 and len(bg_cards[best]) < 6 * len(mine) + 400:
                mp["overlap_hint"] = {"bg": best, "overlap": round(bo, 2)}
    return {"fine": fine, "units": units, "mapping": mapping, "members": members, "concept_name": concept_name, "alias_concepts": alias_concepts, "bg_cards": bg_cards,
            "unit_basis": unit_basis}


def bucket_stats(D, gids):
    cnt = collections.Counter()
    for g in gids:
        for b in D.bucket_of.get(g, []):
            cnt[b] += max(1, D.size(g))
    return cnt


def finish(D, B, out_path):
    mapping, members, cname, ac = B["mapping"], B["members"], B["concept_name"], B["alias_concepts"]
    # unique names: a clash that survives the same-name merge is told apart by the parser family, then by a number (the size order), so a reviewer sees both
    names = collections.defaultdict(list)
    for k in members:
        names[cname[k]].append(k)
    final_name = {}
    for nm, ks in names.items():
        if len(ks) == 1:
            final_name[ks[0]] = nm
        else:
            for k in ks:
                gs = [g for g, r in members[k] if r == "primary"]
                fams = collections.Counter(D.family_name.get(g, "") for g in gs if D.family_name.get(g))
                fam = fams.most_common(1)[0][0] if fams else k.split(":")[0]
                final_name[k] = "%s (%s)" % (nm, fam)
    seen = collections.defaultdict(list)
    for k, nm in final_name.items():
        seen[nm].append(k)
    for nm, ks in seen.items():
        if len(ks) > 1:
            for i, k in enumerate(sorted(ks, key=lambda k: (-len(B["bg_cards"][k]), k)), 1):
                final_name[k] = "%s [%d]" % (nm, i)
    # ids: sequence in a fixed order (topic, size desc, name) -- provisional, frozen on first import
    def topic_of(k):
        gs = [g for g, _ in members[k]]
        st = bucket_stats(D, gs)
        return [b for b, _ in st.most_common(2)]
    keys = list(members)
    keys.sort(key=lambda k: (-len(B["bg_cards"][k]), final_name[k]))
    out = {"_about": "DRAFT browse groups from a deterministic rule pass (src/probe_browse_draft.py). Read-only probe output; not read by the site. Provisional ids bg:bNNN are assigned in size order for this draft only.",
           "v": 0, "next_id": len(keys) + 1, "groups": {}, "fine_to_bg": {}}
    desc_of = {}
    for i, k in enumerate(keys, 1):
        gid = "bg:b%03d" % i
        mem = sorted(members[k], key=lambda x: (x[1] != "primary", -D.size(x[0]), x[0]))
        mgids = [g for g, _ in mem]
        # description: the alias concept's? the largest primary member's description
        d = ""
        for g in mgids:
            t = D.desc.get(g, "")
            if t:
                d = t
                break
        # aliases: hand + drafted aliases of the members, plus the concept's alias names
        al = []
        if k in ac:
            al += [a for a in ac[k]["aliases"] if a != ac[k]["name"].lower()]
        for a, v in D.search_doc["aliases"].items():
            if any(g in v.get("g", []) for g in mgids) and a not in al and a != final_name[k].lower() and len(al) < 8:
                al.append(a)
        tb = topic_of(k)
        bases = collections.Counter(mapping[g]["basis"] for g, r in mem if r == "primary")
        out["groups"][gid] = {"name": final_name[k], "description": d, "aliases": al, "topic": [D.bucket_names[D.bucket_ids.index(b)] for b in tb],
                              "members": [{"id": g, "role": r} for g, r in mem], "key": k, "cards": len(B["bg_cards"][k]), "bases": dict(bases), "retired": False}
    key_to_id = {v["key"]: bid for bid, v in out["groups"].items()}
    for g, mp in mapping.items():
        out["fine_to_bg"][g] = {"bg": [key_to_id[mp["primary"]]] + ([key_to_id[mp["second"]]] if mp["second"] else []), "basis": mp["basis"], "confidence": mp["conf"], "notes": mp["notes"],
                                "overlap_own": mp.get("overlap_own"), "overlap_hint": ({"bg": key_to_id[mp["overlap_hint"]["bg"]], "overlap": mp["overlap_hint"]["overlap"]} if mp.get("overlap_hint") else None)}
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, sort_keys=False)
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P.BUILD, "browse_groups_draft.json")
    D = P.Data()
    B = build(D)
    out = finish(D, B, out_path)
    print("wrote", out_path, "browse groups", len(out["groups"]), "fine groups mapped", len(out["fine_to_bg"]))
    return D, B, out


if __name__ == "__main__":
    main()
