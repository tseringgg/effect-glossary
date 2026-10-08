#!/usr/bin/env python3
"""How often is each "not recorded" field actually present in the parse, for the members of the leaves flagged for it?

    python src/measure_field_presence.py   # -> build/ability_taxonomy_field_presence.json

Run BEFORE the sign / recipient fields enter the signature: it reads the current build/ability_taxonomy*.json (the build
with the flags) and the parsed chunks. Measurement only; nothing is changed.

Sign of a power/toughness change (decidable when every part is a fixed signed number, or a Variable "X" / "-X"):
  Pump / PumpAll effects      effect.power, effect.toughness (a quantity node; absent = 0)
  grants and statics          modifications AddPower / AddToughness (signed integers); AddDynamicPower / AddDynamicToughness
                              hold a Ref (a count): undecidable
  Quantity {value: Ref} and Ref nodes: undecidable
Damage recipient: DamageEachPlayer.player_filter, DamageAll.player_filter (players hit besides the matching creatures).
Who loses or gains life: player_scope, a player-kind target, or effect.player.
"""
import collections
import io
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(HERE, "build")
PT = ("AddPower", "AddToughness", "AddDynamicPower", "AddDynamicToughness")


def jl(n):
    return json.load(io.open(os.path.join(BUILD, n), encoding="utf-8"))


def qsign(n):
    """'+', '-', '0' or '?' for one quantity node (or None = absent = 0)."""
    if n is None:
        return "0"
    if isinstance(n, int):
        return "+" if n > 0 else "-" if n < 0 else "0"
    if isinstance(n, dict):
        t = n.get("type")
        if t == "Fixed":
            return qsign(n.get("value"))
        if t == "Variable":
            v = str(n.get("value") or "")
            return "-" if v.startswith("-") else "+" if v else "?"
    return "?"


def sign_class(effect, statics):
    """('+'|'-'|'+/-'|'0'|'?') or None when the ability has no power/toughness change."""
    parts = []
    t = (effect or {}).get("type")
    if t in ("Pump", "PumpAll"):
        parts += [qsign(effect.get("power")), qsign(effect.get("toughness"))]
    for s in statics or []:
        for m in s.get("modifications") or []:
            if isinstance(m, dict) and m.get("type") in PT:
                parts.append("?" if m["type"].startswith("AddDynamic") else qsign(m.get("value")))
    if not parts:
        return None
    if "?" in parts:
        return "?"
    nz = {p for p in parts if p != "0"}
    return "0" if not nz else "+" if nz == {"+"} else "-" if nz == {"-"} else "+/-"


def main():
    T, G = jl("ability_taxonomy.json"), jl("ability_taxonomy_ledger.json")
    L = T["leaves"]
    idx = {r["id"]: r for r in jl("index.json")["rows"]}
    rec = jl("placements.json")["recovered"]["chunk"]
    chunks = {}

    def entry(fid):
        if fid in idx:
            ch = idx[fid]["ch"]
            if ch not in chunks:
                chunks[ch] = jl("chunks/%d.json" % ch)
            return chunks[ch][fid]
        return rec[fid]

    SIGN = "sign of the power/toughness change is not recorded"
    DMG = "who is damaged is not fully recorded"
    LIFE = "who loses or gains life is not recorded"
    out = {"sign": collections.Counter(), "sign_by_class": collections.Counter(), "dmg": collections.Counter(), "life": collections.Counter(),
           "life_all": collections.Counter()}
    sign_leaf = collections.defaultdict(collections.Counter)
    for r in G["rows"]:
        oid, face, b, i, mode, text, state, reason, leaf = r
        if not leaf or leaf not in L:
            continue
        fl = L[leaf]["flags"]
        sig = L[leaf]["sig"]
        e = entry(face)
        it = e[b][i]
        ex = it if b == "abilities" else (it.get("execute") or {})
        if mode is not None:
            ex = (ex.get("mode_abilities") or [])[mode]
        eff = ex.get("effect") if b != "static_abilities" else None
        # skip wrappers the way the build does: the flagged effect may sit one step down; keep it simple and measure the head
        statics = (eff.get("static_abilities") if isinstance(eff, dict) and eff.get("type") == "GenericEffect" else None)
        if b == "static_abilities":
            statics = [it]
        if SIGN in fl:
            sc = sign_class(eff, statics)
            out["sign"]["members_of_sign_flagged_leaves"] += 1
            if sc is None:
                out["sign"]["no_power_toughness_change_found_at_head"] += 1
            else:
                out["sign"]["has_change"] += 1
                out["sign_by_class"][sc] += 1
                if sc != "?":
                    out["sign"]["decidable"] += 1
                    sign_leaf[leaf][sc] += 1
        ft = sig.split(" · ")[1].split("=", 1)[1]
        if DMG in fl and isinstance(eff, dict):
            if ft == "DamageEachPlayer":
                out["dmg"]["DamageEachPlayer_members"] += 1
                out["dmg"]["DamageEachPlayer_with_player_filter"] += bool(eff.get("player_filter"))
            elif ft == "Damage":
                out["dmg"]["DamageAll_members"] += 1
                out["dmg"]["DamageAll_with_player_filter"] += bool(eff.get("player_filter"))
            elif ft == "DealDamage":
                out["dmg"]["DealDamage_members"] += 1
                tg = eff.get("target")
                out["dmg"]["DealDamage_with_a_target_node"] += bool(tg)
                out["dmg"]["DealDamage_target_has_no_type_filter"] += bool(isinstance(tg, dict) and tg.get("type") == "Typed" and not tg.get("type_filters"))
        if LIFE in fl and isinstance(eff, dict):
            out["life"]["members_of_life_flagged_leaves"] += 1
            tg = eff.get("target")
            out["life"]["with_player_scope"] += bool(ex.get("player_scope"))
            out["life"]["with_effect_player_field"] += bool(eff.get("player"))
            out["life"]["with_a_target_node"] += bool(tg)
            out["life"]["target_type:" + (tg.get("type") if isinstance(tg, dict) else "none")] += 1
        if ft in ("LoseLife", "GainLife") and isinstance(eff, dict) and state in ("placed", "placed_broad"):
            out["life_all"][ft + "_abilities"] += 1
            has = bool(ex.get("player_scope") or eff.get("player") or (isinstance(eff.get("target"), dict) and eff["target"].get("type") in
                       ("Player", "Controller", "TriggeringPlayer", "DefendingPlayer", "ParentTargetController")))
            out["life_all"][ft + "_who_recorded"] += has
    # purity of sign leaves among decidable members
    pure = mixed = 0
    for leaf, c in sign_leaf.items():
        n = sum(c.values())
        if n >= 5:
            if c.most_common(1)[0][1] / n >= 0.95:
                pure += n
            else:
                mixed += n
    out["sign"]["decidable_members_in_leaves_that_are_>=95%_one_class"] = pure
    out["sign"]["decidable_members_in_leaves_that_mix_classes"] = mixed
    res = {k: dict(v) for k, v in out.items()}
    s = res["sign"]
    res["summary"] = {
        "sign_present_for_share_of_members": round(s.get("decidable", 0) / max(1, s.get("has_change", 1)), 3),
        "damage_each_player_recipient_present_share": round(res["dmg"].get("DamageEachPlayer_with_player_filter", 0) / max(1, res["dmg"].get("DamageEachPlayer_members", 1)), 3),
        "damage_all_players_hit_present_share": round(res["dmg"].get("DamageAll_with_player_filter", 0) / max(1, res["dmg"].get("DamageAll_members", 1)), 3),
        "life_who_present_share_all_lose_gain_abilities": round(
            (res["life_all"].get("LoseLife_who_recorded", 0) + res["life_all"].get("GainLife_who_recorded", 0)) /
            max(1, res["life_all"].get("LoseLife_abilities", 0) + res["life_all"].get("GainLife_abilities", 0)), 3)}
    with io.open(os.path.join(BUILD, "ability_taxonomy_field_presence.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
