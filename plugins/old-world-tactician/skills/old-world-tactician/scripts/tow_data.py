#!/usr/bin/env python3
"""Query Warhammer: The Old World army data (units, points, options, special
rules, magic items, spells).

Data comes from the community-maintained BSData repository
(github.com/BSData/warhammer-the-old-world), the same data New Recruit uses.
It is downloaded on first use and cached locally; nothing is bundled.

Usage:
  tow_data.py sync [--force]             download / refresh the data cache
  tow_data.py armies                     list army books and army-of-infamy lists
  tow_data.py composition ARMY           category % limits and army-specific restrictions
  tow_data.py units ARMY                 units in an army with category and base cost
  tow_data.py unit ARMY UNIT [UNIT ...]  full entries: profiles, rules, options, costs
  tow_data.py rule NAME [NAME ...] [--army ARMY]  special rule text (fuzzy match)
  tow_data.py items [ARMY] [--type T]    magic items (common + army-specific)
  tow_data.py item NAME [NAME ...]       magic items, with cost and text
  tow_data.py spells [LORE ...]          list lores, or the spells of one or more lores
  tow_data.py search TEXT                search every entry and profile name

ARMY / UNIT / NAME are case-insensitive substrings; the best match wins and
alternatives are listed when the match is ambiguous. unit, rule and item take
several names (spells several lores), so look up everything a list needs in one call.
"""

import argparse
import difflib
import io
import json
import os
import sys
import tarfile
import time
import urllib.request

REPO = "BSData/warhammer-the-old-world"
TARBALL = f"https://codeload.github.com/{REPO}/tar.gz/refs/heads/main"
COMMIT_API = f"https://api.github.com/repos/{REPO}/commits/main"
CACHE = os.environ.get(
    "TOW_CACHE_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "old-world-tactician"),
)
DATA_DIR = os.path.join(CACHE, "bsdata")
STAMP = os.path.join(CACHE, "bsdata.json")
MAX_AGE_DAYS = 7

# Option groups too large to print inline under every unit.
COLLAPSE = ("magic item", "magic standard", "runic item", "runes")
FULL = False
ROOT_UNIT = None  # name of the unit being rendered, to drop options meant for others

MAGIC_TYPES = {
    "Magic Standards", "Arcane Items", "Magic Weapons", "Magic Armour",
    "Talismans", "Enchanted Items",
}


# --------------------------------------------------------------------------
# Cache management

def _get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": "old-world-tactician"})
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def sync(force=False, quiet=False):
    stamp = {}
    if os.path.exists(STAMP):
        with open(STAMP) as f:
            stamp = json.load(f)
    fresh = time.time() - stamp.get("fetched", 0) < MAX_AGE_DAYS * 86400
    if not force and fresh and os.path.isdir(DATA_DIR):
        if not quiet:
            print(f"Cache is fresh ({stamp.get('sha', '?')[:8]}, {DATA_DIR}).")
        return
    try:
        sha = json.loads(_get(COMMIT_API))["sha"]
    except Exception:
        sha = None
    if sha and sha == stamp.get("sha") and os.path.isdir(DATA_DIR):
        stamp["fetched"] = time.time()
    else:
        print(f"Downloading {REPO} ...", file=sys.stderr)
        try:
            blob = _get(TARBALL)
        except Exception as e:
            if os.path.isdir(DATA_DIR) and os.listdir(DATA_DIR):
                print(f"warning: could not refresh army data ({e}); using the cached copy "
                      f"from {time.strftime('%Y-%m-%d', time.localtime(stamp.get('fetched', 0)))}.",
                      file=sys.stderr)
                return
            sys.exit("NETWORK BLOCKED: can't download the army data from GitHub "
                     f"({TARBALL}): {e}\nThis environment needs access to codeload.github.com "
                     "and api.github.com. Without it, answer from the official rules site via "
                     "web fetch and say that points/profiles couldn't be checked against the data.")
        os.makedirs(DATA_DIR, exist_ok=True)
        for name in os.listdir(DATA_DIR):
            os.remove(os.path.join(DATA_DIR, name))
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            for m in tar.getmembers():
                base = os.path.basename(m.name)
                # Only top-level data files; never trust paths from the archive.
                if m.isfile() and base.endswith(".json") and m.name.count("/") == 1:
                    with open(os.path.join(DATA_DIR, base), "wb") as out:
                        out.write(tar.extractfile(m).read())
        stamp = {"sha": sha, "fetched": time.time()}
    with open(STAMP, "w") as f:
        json.dump(stamp, f)
    if not quiet:
        print(f"Data at {DATA_DIR} (commit {(sha or 'unknown')[:8]}).")


# --------------------------------------------------------------------------
# Loading and indexing

class Data:
    def __init__(self):
        sync(quiet=True)
        self.files = {}  # file name -> root object (catalogue / gameSystem)
        for name in sorted(os.listdir(DATA_DIR)):
            with open(os.path.join(DATA_DIR, name)) as f:
                doc = json.load(f)
            root = doc.get("catalogue") or doc.get("gameSystem")
            if root:
                root["_file"] = name
                self.files[name] = root
        self.by_id = {}
        for root in self.files.values():
            self._index(root, root)

    def _index(self, node, root):
        if isinstance(node, dict):
            if "id" in node and "name" in node:
                node.setdefault("_root", root["name"])
                self.by_id.setdefault(node["id"], node)
                for p in node.get("profiles", []):
                    p.setdefault("_owner", node["name"])
            for k, v in node.items():
                if not k.startswith("_"):
                    self._index(v, root)
        elif isinstance(node, list):
            for v in node:
                self._index(v, root)

    def catalogues(self):
        return [r for r in self.files.values() if r.get("type") == "catalogue"]

    def armies(self):
        return [r for r in self.catalogues() if not r.get("library")]

    def find_army(self, query):
        armies = self.armies()
        return pick(query, armies, key=lambda r: r["name"], what="army")

    def scope(self, army):
        """Army catalogue plus everything it links to, plus the game system."""
        roots, todo = [], [army]
        while todo:
            r = todo.pop()
            if r in roots:
                continue
            roots.append(r)
            for link in r.get("catalogueLinks", []):
                t = self.by_id.get(link.get("targetId"))
                if t is not None and t.get("type") == "catalogue":
                    todo.append(t)
        roots += [r for r in self.files.values() if r.get("type") == "gameSystem"]
        return roots

    def resolve(self, link):
        return self.by_id.get(link.get("targetId"), {})


def norm(text):
    """Lowercase, unify apostrophes, drop punctuation and plural 's' for matching."""
    text = text.lower().replace("\u2019", "'").replace("\u2018", "'").replace("'", "")
    words = "".join(ch if ch.isalnum() else " " for ch in text).split()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words)


def pick(query, items, key, what):
    q = norm(query)
    exact = [i for i in items if norm(key(i)) == q]
    if exact:
        return exact[0]
    sub = [i for i in items if q in norm(key(i))]
    if len(sub) == 1:
        return sub[0]
    if sub:
        sub.sort(key=lambda i: len(key(i)))
        others = ", ".join(sorted({key(i) for i in sub[1:8]}))
        print(f"(matched {what} '{key(sub[0])}'; also: {others})", file=sys.stderr)
        return sub[0]
    names = [key(i) for i in items]
    close = difflib.get_close_matches(query, names, n=5, cutoff=0.4)
    best = difflib.get_close_matches(q, [norm(n) for n in names], n=1, cutoff=0.75)
    if best:
        hit = next(i for i in items if norm(key(i)) == best[0])
        print(f"(no exact match; using closest {what} '{key(hit)}')", file=sys.stderr)
        return hit
    sys.exit(f"No {what} matching '{query}'. Closest: {', '.join(close) or 'none'}")


# --------------------------------------------------------------------------
# Rendering helpers

def pts(node):
    for c in node.get("costs", []):
        if c.get("name") == "pts" and c.get("value"):
            v = c["value"]
            return int(v) if float(v).is_integer() else v
    return None


def has_cost_modifier(node):
    return any(m.get("field") == "points" for m in node.get("modifiers", []))


def limits(node):
    lo = hi = None
    for c in node.get("constraints", []):
        if c.get("field") != "selections" or c.get("scope") not in ("parent", None):
            continue
        if c["type"] == "min":
            lo = c["value"]
        elif c["type"] == "max" and c["value"] >= 0:
            hi = c["value"]
    if lo is None and hi is None:
        return ""
    if lo == hi:
        return f" [{lo}]"
    return f" [{lo or 0}-{'' if hi is None else hi}]"


def profile_line(p, compact=False):
    """One-line profile. compact drops empty fields and shortens long notes
    (used inside `unit` trees; `rule` / `item` print the full text)."""
    chars = p.get("characteristics", [])
    if p.get("typeName") in ("Model",) or all(len(c["name"]) <= 3 for c in chars):
        stats = " ".join(f"{c['name']}{c.get('$text', '')}" for c in chars)
        return f"{p['name']}: {stats}"
    if compact and p.get("typeName") == "Base":
        return "base " + " ".join(c.get("$text", "") for c in chars)
    parts = []
    for c in chars:
        text = " ".join(c.get("$text", "").split())
        if compact and text in ("", "-", "N/A"):
            continue
        if compact and len(text) > 140:
            text = text[:130].rsplit(" ", 1)[0] + " …"
        if text:
            parts.append(f"{c['name']}: {text}")
    return f"{p['name']} ({p.get('typeName')}): " + " | ".join(parts)


def gather_profiles(data, node):
    out = list(node.get("profiles", []))
    for g in node.get("infoGroups", []):
        out += gather_profiles(data, g)
    for link in node.get("infoLinks", []):
        t = data.resolve(link)
        if t.get("characteristics") is not None:
            name = t["name"]
            # Values like Fly (9) or Impact Hits (D6) live in unconditional name modifiers.
            for m in link.get("modifiers", []):
                if m.get("field") == "name" and not m.get("conditions") and not m.get("conditionGroups"):
                    name = f"{name} {m['value']}" if m["type"] == "append" else str(m["value"])
            if link.get("hidden"):
                t = dict(t, _cond=True)
            out.append(t if name == t["name"] else dict(t, name=name))
    return out


def children(data, node):
    kids = []
    for e in node.get("selectionEntries", []):
        kids.append((e, e))
    for g in node.get("selectionEntryGroups", []):
        kids.append((g, g))
    for link in node.get("entryLinks", []):
        t = data.resolve(link)
        if t:
            kids.append((link, t))
    kids.sort(key=lambda lt: lt[0].get("sortIndex", 0))
    return kids


def render(data, node, link=None, depth=0, seen=None, rule_names=None, out=None, parent=""):
    seen = seen if seen is not None else set()
    rule_names = rule_names if rule_names is not None else {}
    out = out if out is not None else []
    link = link or node
    ind = "  " * depth
    cost = pts(node) or pts(link)
    flags = []
    if node.get("hidden") or link.get("hidden"):
        f1, o1 = unlocks(data, link)
        f2, o2 = unlocks(data, node)
        why = sorted(f1 | f2 | o1 | o2)
        unit_names = {n["name"] for n in data.by_id.values() if n.get("type") == "unit"}
        if ROOT_UNIT and why and ROOT_UNIT not in why and all(w in unit_names for w in why):
            return out  # option belongs to a different character/unit
        if not (ROOT_UNIT and ROOT_UNIT in why):
            flags.append("conditional" + (": with " + " / ".join(why[:4]) if why else ""))
    if has_cost_modifier(node) or has_cost_modifier(link):
        flags.append("cost varies")
    kind = node.get("type") or ("group" if "selectionEntries" in node or "entryLinks" in node else "")
    line = f"{ind}- {link.get('name') or node.get('name')}"
    if kind and kind not in ("upgrade",):
        line += f" <{kind}>"
    line += limits(link) or limits(node)
    if cost:
        line += f" {cost} pts"
    if flags:
        line += f" ({', '.join(flags)})"
    name = (link.get("name") or node.get("name") or "").lower()
    if not FULL and depth and any(k in name for k in COLLAPSE):
        budget = [c["value"] for c in node.get("constraints", []) + link.get("constraints", [])
                  if c.get("field") == "points" and c["type"] == "max" and c["value"] >= 0]
        out.append(line + (f" — up to {budget[0]} pts" if budget else "") + \
            "  (collapsed: see `items ARMY` or rerun with --full)")
        return out
    out.append(line)
    if node.get("id") in seen:
        return out
    seen.add(node.get("id"))
    owner = link.get("name") or node.get("name")
    for p in gather_profiles(data, node):
        if p.get("typeName") == "Special Rule":
            src = owner if depth else ("a mount or option" if p.get("_cond") else None)
            # The unit's own rules: on the entry itself or its models, unconditionally.
            own = depth <= 1 and not p.get("_cond")
            rule_names.setdefault(p["name"], (p, src, own))
            out.append(f"{ind}    rule: {p['name']}" + (" (conditional)" if p.get("_cond") else ""))
        elif p.get("typeName") == "Command":
            out.append(f"{ind}    ({p['name']})")
        else:
            out.append(f"{ind}    {profile_line(p, compact=not FULL)}")
    if not FULL and "mount" in parent.lower() and node.get("type") == "model":
        # Mount profile and rules, plus a one-line list of its gear (armour matters for saves).
        gear = [f"{lk.get('name') or ch.get('name')}" + (f" {pts(ch) or pts(lk)} pts" if (pts(ch) or pts(lk)) else "")
                for lk, ch in children(data, node)]
        if gear:
            out.append(f"{ind}    gear: {', '.join(gear)}  (--full for profiles)")
        return out
    for lk, child in children(data, node):
        render(data, child, lk, depth + 1, seen, rule_names, out, parent=name)
    return out


def rule_text(p):
    return "\n".join(c.get("$text", "") for c in p.get("characteristics", [])).strip()


# --------------------------------------------------------------------------
# Commands

def unit_category(data, link):
    for c in link.get("categoryLinks", []):
        if c.get("primary"):
            return c["name"]
    t = data.resolve(link)
    for c in t.get("categoryLinks", []):
        if c.get("primary"):
            return c["name"]
    return "Other"


def base_cost(data, entry):
    """Entry cost plus mandatory models at minimum size."""
    total = pts(entry) or 0
    for lk, child in children(data, entry):
        if child.get("type") == "model":
            lo = 0
            for c in lk.get("constraints", []) + child.get("constraints", []):
                if c.get("field") == "selections" and c["type"] == "min":
                    lo = max(lo, c["value"])
            if lo and pts(child):
                total += lo * pts(child)
    return total


def cmd_armies(data, args):
    for r in sorted(data.armies(), key=lambda r: r["name"]):
        print(f"{r['name']}  (rev {r.get('revision')}, {r['_file']})")
    libs = sorted(r["name"] for r in data.catalogues() if r.get("library"))
    print("\nShared libraries:", ", ".join(libs))


def army_units(data, army):
    for link in army.get("entryLinks", []):
        t = data.resolve(link)
        if t:
            yield link, t
    for e in army.get("selectionEntries", []):
        yield e, e


def entry_cap(link):
    """Army-wide limit on how many of this entry the list may include, e.g. 'max 1'."""
    for c in link.get("constraints", []):
        if (c.get("field") == "selections" and c.get("type") == "max" and c.get("value", -1) >= 0
                and c.get("scope") in ("force", "roster")):
            for m in link.get("modifiers", []):
                if m.get("field") == c["id"] and m.get("type") == "increment" and m.get("repeats"):
                    step, per = m["value"], m["repeats"][0].get("value")
                    base = f"{c['value']} + " if c["value"] else ""
                    return f"max {base}{step:g} per {per:,.0f} pts"
            return f"max {c['value']}" if c["value"] else "not normally available"
    return ""


def cmd_units(data, args):
    army = data.find_army(args.army)
    print(f"# {army['name']}\n")
    rows = {}
    for link, t in army_units(data, army):
        rows.setdefault(unit_category(data, link), []).append((link, t))
    order = ["Characters", "Named Characters", "Core", "Special", "Rare", "Mercenaries"]
    for cat in sorted(rows, key=lambda c: (order.index(c) if c in order else 99, c)):
        print(f"## {cat}")
        for link, t in sorted(rows[cat], key=lambda lt: lt[0]["name"]):
            prof = next((p for p in gather_profiles(data, t) if p.get("typeName") == "Unit"), None)
            info = ""
            if prof:
                info = ", ".join(c.get("$text", "") for c in prof.get("characteristics", []))
            hidden = " (conditional)" if link.get("hidden") else ""
            cap = entry_cap(link)
            cap = f" [{cap} in this category]" if cap else ""
            print(f"- {link['name']}: from {base_cost(data, t)} pts; {info}{cap}{hidden}")
        print()


def cmd_unit(data, args):
    army = data.find_army(args.army)
    units = list(army_units(data, army))
    link, entry = pick(args.unit, units, key=lambda lt: lt[0]["name"], what="unit")
    print(f"# {link['name']} ({army['name']}, {unit_category(data, link)})")
    print(f"Base cost at minimum size: {base_cost(data, entry)} pts\n")
    rules = {}
    global ROOT_UNIT
    ROOT_UNIT = entry["name"]
    print("\n".join(render(data, entry, link, rule_names=rules)))
    if args.rules and rules:
        print("\n## Special rules")
        others = []
        for name, (p, owner, own) in rules.items():
            if own or args.full:
                src = f"  (from: {owner} — only if taken)" if owner and not own else ""
                print(f"\n### {name}{src}\n{rule_text(p)}")
            else:
                others.append(f"{name} ({owner})")
        if others:
            print("\nFrom mounts/options, only if taken (text: `rule NAME`, or --full): "
                  + "; ".join(others))
    elif rules:
        print("\n(Use --rules to include the unit's special rule text.)")


def all_profiles(data, roots=None):
    roots = roots or list(data.files.values())
    seen = set()
    for node in data.by_id.values():
        if node.get("characteristics") is not None and node["_root"] in {r["name"] for r in roots}:
            if node["id"] not in seen:
                seen.add(node["id"])
                yield node


_RULE_PAGES = None


def rules_page(name):
    """Best tow.whfb.app page for a rule name, from the cached or bundled page index."""
    global _RULE_PAGES
    if _RULE_PAGES is None:
        cached = os.path.join(CACHE, "rules", "index.json")
        bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "rules-index.txt")
        if os.path.exists(cached):
            with open(cached) as f:
                _RULE_PAGES = json.load(f)
        elif os.path.exists(bundled):
            with open(bundled) as f:
                _RULE_PAGES = [l.strip() for l in f if l.strip()]
        else:
            _RULE_PAGES = []
    base = name.split("(")[0]
    slug = "-".join(base.lower().replace("\u2019", "").replace("'", "").replace("&", "").split())
    if not slug:
        return None
    for prefix in ("/special-rules/", "/weapons-of-war/", "/"):
        hits = [p for p in _RULE_PAGES if p.startswith(prefix) and p.rsplit("/", 1)[-1] == slug]
        if hits:
            return "https://tow.whfb.app" + min(hits, key=len)
    return None


def cmd_rule(data, args):
    roots = data.scope(data.find_army(args.army)) if args.army else None
    rules = [p for p in all_profiles(data, roots) if p.get("typeName") == "Special Rule"]
    q = norm(args.name)
    hits = [p for p in rules if norm(p["name"]) == q] or [p for p in rules if q in norm(p["name"])]
    if not hits:
        close = difflib.get_close_matches(args.name, sorted({p["name"] for p in rules}), n=8, cutoff=0.4)
        sys.exit(f"No rule matching '{args.name}'. Closest: {', '.join(close) or 'none'}")
    army_name = data.find_army(args.army)["name"] if args.army else None

    def rank(p):
        root = p["_root"]
        if root == army_name:
            r = 0
        elif root == "Warhammer The Old World":
            r = 1
        elif "renegade" in root.lower():
            r = 3
        else:
            r = 2
        return (norm(p["name"]) != q, r, len(p["name"]))

    shown = set()
    for p in sorted(hits, key=rank)[:6]:
        text = rule_text(p)
        if (p["name"], text) in shown:
            continue
        shown.add((p["name"], text))
        url = rules_page(p["name"])
        print(f"## {p['name']}  [{p['_root']}]" + (f"\nRules page: {url}" if url else "") + f"\n{text}\n")


def item_entries(data, roots):
    """Selection entries that carry a magic-item profile, with their cost."""
    names = {r["name"] for r in roots}
    for node in data.by_id.values():
        if node["_root"] not in names or "type" not in node or node.get("characteristics") is not None:
            continue
        for p in gather_profiles(data, node):
            if p.get("typeName") in MAGIC_TYPES:
                yield node, p
                break


def unlocks(data, node):
    """Factions and other requirements that un-hide a conditional entry."""
    factions, other = set(), set()

    def walk(group):
        for c in group.get("conditions", []):
            name = data.by_id.get(c.get("childId"), {}).get("name")
            if name and c.get("type") in ("instanceOf", "atLeast"):
                if name.startswith("Faction: "):
                    factions.add(name[len("Faction: "):])
                else:
                    other.add(name)
        for g in group.get("conditionGroups", []):
            walk(g)

    for m in node.get("modifiers", []):
        if m.get("field") == "hidden" and m.get("value") is False:
            walk(m)
    return factions, other


def available_to(army_name, factions):
    base = army_name.split(" - ")[0]
    return army_name in factions or base in factions


def cmd_items(data, args):
    army = data.find_army(args.army) if args.army else None
    roots = data.scope(army) if army else [r for r in data.catalogues() if r.get("library")]
    rows = {}
    for node, p in item_entries(data, roots):
        if args.type and args.type.lower() not in p["typeName"].lower():
            continue
        note = ""
        if node.get("hidden"):
            factions, other = unlocks(data, node)
            if army and factions and not available_to(army["name"], factions):
                continue
            parts = []
            if factions and army:
                parts.append("army-specific")
            elif factions:
                parts.append("armies: " + ", ".join(sorted(factions)))
            if other:
                parts.append("requires: " + ", ".join(sorted(other)))
            note = f" ({'; '.join(parts) or 'conditional'})"
        rows.setdefault((p["typeName"], node["_root"]), {})[node["name"]] = (pts(node), note)
    for (t, src), items in sorted(rows.items()):
        print(f"## {t} — {src}")
        for name, (cost, note) in sorted(items.items()):
            print(f"- {name}: {cost if cost is not None else '?'} pts{note}")
        print()


def cmd_item(data, args):
    found = list(item_entries(data, list(data.files.values())))
    node, p = pick(args.name, found, key=lambda np_: np_[0]["name"], what="item")
    print(f"## {node['name']} — {p['typeName']}, {pts(node)} pts  [{node['_root']}]")
    for c in node.get("constraints", []):
        if c.get("type") == "max" and c.get("field") == "selections" and c["value"] >= 0:
            print(f"Max {c['value']} per {c.get('scope')}")
    if node.get("hidden"):
        factions, other = unlocks(data, node)
        if factions:
            print("Armies:", ", ".join(sorted(factions)))
        if other:
            print("Requires:", ", ".join(sorted(other)))
    print(profile_line(p))


def cmd_spells(data, args):
    by_lore = {}
    for p in all_profiles(data):
        if p.get("typeName") == "Spell":
            lore = f"{p.get('_owner', '?')}  [{p['_root']}]"
            by_lore.setdefault(lore, {}).setdefault(p["name"], p)
    if args.lore:
        q = args.lore.lower()
        by_lore = {k: v for k, v in by_lore.items() if q in k.lower()} or {
            k: {n: p for n, p in v.items() if q in n.lower()}
            for k, v in by_lore.items() if any(q in n.lower() for n in v)
        }
        if not by_lore:
            sys.exit(f"No lore or spell matching '{args.lore}'. Run 'spells' to list lores.")
        for lore, spells in sorted(by_lore.items()):
            print(f"# {lore}")
            for p in spells.values():
                print(f"\n## {p['name']}\n{profile_line(p)}")
            print()
    else:
        for lore, spells in sorted(by_lore.items()):
            print(f"- {lore}: {', '.join(spells)}")


def cmd_composition(data, args):
    army = data.find_army(args.army)
    print(f"# Army composition — {army['name']}\n")
    gs = next(r for r in data.files.values() if r.get("type") == "gameSystem")
    print("## Category limits by game mode (percent of the points limit)")
    for fe in gs.get("forceEntries", []):
        parts = []
        for c in fe.get("categoryLinks", []):
            for k in c.get("constraints", []):
                if k.get("percentValue"):
                    sign = "max" if k["type"] == "max" else "min"
                    adj = " *" if c.get("modifiers") else ""
                    parts.append(f"{c['name']} {sign} {k['value']}%{adj}")
        print(f"- {fe['name']}: {', '.join(parts) or 'no percentage limits'}")
    print("  (* adjusted by modifiers for some armies or modes — confirm with "
          "`tow_rules.py get matched-play/combined-arms` or the army book)\n")
    print("## Army-specific restrictions")
    rules = [c["name"] for c in army.get("categoryEntries", [])
             if any(ch.isdigit() for ch in c["name"]) or "per " in c["name"].lower()]
    print("\n".join(f"- {r}" for r in rules) or "- none encoded in the data")
    print("\nAlso see: tow_rules.py get matched-play/army-composition, matched-play/combined-arms, "
          "matched-play/grand-melee")


def cmd_search(data, args):
    q = " ".join(args.text).lower()
    hits = {}
    for node in data.by_id.values():
        if q in node["name"].lower() and "targetId" not in node:
            kind = node.get("typeName") or node.get("type") or "link"
            if kind == "link":
                continue
            hits.setdefault((node["name"], kind, node["_root"]), node)
    for (name, kind, root) in sorted(hits)[:80]:
        print(f"- {name}  <{kind}>  [{root}]")
    if len(hits) > 80:
        print(f"... {len(hits) - 80} more; refine the search.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sync"); s.add_argument("--force", action="store_true")
    sub.add_parser("armies")
    s = sub.add_parser("composition"); s.add_argument("army")
    s = sub.add_parser("units"); s.add_argument("army")
    s = sub.add_parser("unit"); s.add_argument("army"); s.add_argument("unit", nargs="+")
    s.add_argument("--rules", action="store_true", help="include special rule text")
    s.add_argument("--full", action="store_true", help="expand magic item option groups")
    s = sub.add_parser("rule"); s.add_argument("name", nargs="+"); s.add_argument("--army")
    s = sub.add_parser("items"); s.add_argument("army", nargs="?"); s.add_argument("--type")
    s = sub.add_parser("item"); s.add_argument("name", nargs="+")
    s = sub.add_parser("spells"); s.add_argument("lore", nargs="*")
    s = sub.add_parser("search"); s.add_argument("text", nargs="+")
    args = ap.parse_args()
    if args.cmd == "sync":
        return sync(force=args.force)
    global FULL
    FULL = getattr(args, "full", False)
    data = Data()
    cmd = globals()[f"cmd_{args.cmd}"]
    if args.cmd == "spells":
        args.lore = args.lore or [None]
    batch_key = {"unit": "unit", "rule": "name", "item": "name", "spells": "lore"}.get(args.cmd)
    if not batch_key:
        return cmd(data, args)
    names = getattr(args, batch_key)
    for i, name in enumerate(names):
        if i:
            print("\n" + "-" * 60 + "\n")
        setattr(args, batch_key, name)
        try:
            cmd(data, args)
        except SystemExit as e:  # a miss shouldn't abort the rest of the batch
            if len(names) == 1:
                raise
            print(e.code)


if __name__ == "__main__":
    main()
