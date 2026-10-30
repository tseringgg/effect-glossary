#!/usr/bin/env python3
"""Loader for the browse-group probe (READ ONLY). Reads build/ and corrections/ files, writes nothing.

Fine groups = the 1,942 groups the page offers (manual_index.json "groups" with offered = 1): leaf, tent, loose, tag, kw, rp, hand.
Not groups for this probe (filters/pages, never placements): keyword-facet pages (yk:), type pages, ability-type pages, merged pages (display only; they are the first rule of the draft).
A group's cards = every card the page lists in it: all sources in manual_index.json (precise, broad, soft) plus the hand placements (corrections/manual_placements.json, action add);
a hand-defined group's own rule matches are suggestions, not members, so only its hand placements count.
"""
import collections
import gzip
import io
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
CORR = os.path.join(HERE, "corrections")


def jl(p):
    with io.open(p, encoding="utf-8") as fh:
        return json.load(fh)


def layer_of(gid):
    return gid.split(":", 1)[0]


def core_name(name):
    """The name once the qualifiers are removed (text in parentheses, text after an em dash): the same rule as src/propose_merged_groups.py core(), plus the 'Family › ' prefix of
    tentative and loose groups and the 'less common kinds' suffix."""
    n = re.sub(r"\s*\([^)]*\)", "", re.sub(r"\s+—.*$", "", name))
    if " › " in n:
        n = n.split(" › ", 1)[1]
    n = re.sub(r",?\s*less common kinds$", "", n.strip())
    n = re.sub(r"[^a-z0-9+/ ]+", " ", n.lower().replace("’", "").replace("'", ""))
    return re.sub(r"\s+", " ", n).strip()


class Data:
    def __init__(self):
        mi = jl(os.path.join(BUILD, "manual_index.json"))
        self.mi = mi
        self.groups_all = mi["groups"]                       # gid -> [name, size, path, layer, offered]
        self.fine = {g: v for g, v in mi["groups"].items() if v[4] == 1}
        self.cards = {}                                      # oid -> {name, rank, gids}
        self.members = collections.defaultdict(set)          # gid -> set(oid)
        self.src = collections.defaultdict(dict)             # gid -> oid -> source letter
        for oid, v in mi["cards"].items():
            self.cards[oid] = {"name": v[0], "state": v[1], "rank": v[4]}
            for g, s in v[3]:
                self.members[g].add(oid)
                self.src[g][oid] = s
        mp = jl(os.path.join(CORR, "manual_placements.json"))
        self.hand_adds = 0
        for oid, e in mp["edits"].items():
            for g, x in e["groups"].items():
                if x["action"] == "add" and g in self.groups_all and oid in self.cards:
                    self.members[g].add(oid)
                    self.src[g].setdefault(oid, "H")
                    self.hand_adds += 1
        self.search_doc = jl(os.path.join(BUILD, "group_search", "index.json"))
        self.sidx = {g[0]: g for g in self.search_doc["groups"]}           # search entry by gid (page:/yk: included)
        self.slug = {g[0]: g[10] for g in self.search_doc["groups"] if len(g) > 10 and g[10]}
        self.buckets_doc = jl(os.path.join(BUILD, "buckets", "map.json"))
        keys = list(mi["groups"].keys())
        self.bucket_names = [b[1] for b in self.buckets_doc["b"]]
        self.bucket_ids = [b[0] for b in self.buckets_doc["b"]]
        self.bucket_of = {}                                  # gid -> [bucket ids]
        for g, mask in zip(keys, self.buckets_doc["m"]):
            self.bucket_of[g] = [self.bucket_ids[i] for i in range(len(self.bucket_ids)) if mask >> i & 1]
        self.merged = jl(os.path.join(CORR, "merged_groups.json"))["pages"]
        self.aliases = jl(os.path.join(CORR, "group_aliases.json"))["aliases"]
        self.desc = {}
        dd = jl(os.path.join(CORR, "group_descriptions.json"))
        for k, v in dd["drafts"].items():
            self.desc[k] = v["text"]
        for k, v in dd["edits"].items():
            self.desc[k] = v["text"] if isinstance(v, dict) else v
        for g in self.search_doc["groups"]:
            if g[7] and g[0] not in self.desc:
                self.desc[g[0]] = g[7]
        tax = jl(os.path.join(BUILD, "ability_taxonomy.json"))
        self.tax = tax
        self.node_of = {}                                    # leaf gid -> (family, node name, node id)
        for f in tax["families"]:
            for nd in f["nodes"]:
                for lid in nd["leaves"] + nd["rolled"]:
                    self.node_of["leaf:" + lid] = (f["name"], nd["name"], nd["id"])
        self.leaf_sig = {"leaf:" + k: v.get("sig", "") for k, v in tax["leaves"].items()}
        self.leaf_flags = {"leaf:" + k: v.get("flags", []) for k, v in tax["leaves"].items()}
        te = jl(os.path.join(BUILD, "tentative_placements.json"))
        lo = jl(os.path.join(BUILD, "loose_groups.json"))
        self.fam_of = {}                                     # tent:/loose: gid -> family name (the parser effect family)
        for gid, g in te["groups"].items():
            self.fam_of["tent:" + gid] = g["fam"]
        for gid, g in lo["groups"].items():
            self.fam_of.setdefault("loose:" + gid, g["fam"])
        tf = {}
        for f in te["families"]:
            for gid in f["groups"]:
                tf["tent:" + gid] = f["name"]
        for f in lo["families"]:
            for gid in f["groups"]:
                tf.setdefault("loose:" + gid, f["name"])
        self.family_name = tf
        for gid, (fam, nd, ni) in self.node_of.items():
            self.family_name[gid] = fam
        kb = tax["blocks"]["keyword"]
        self.kw_branch = {lid: br["name"] for br in kb["branches"] for lid in br["leaves"]}
        self.kw_cards = kb["leaves"]
        self.hand_groups = jl(os.path.join(CORR, "hand_groups.json"))["groups"]

    def size(self, gid):
        return len(self.members.get(gid, ()))

    def name(self, gid):
        return self.groups_all[gid][0]

    def layer(self, gid):
        return layer_of(gid)
