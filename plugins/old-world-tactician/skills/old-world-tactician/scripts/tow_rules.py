#!/usr/bin/env python3
"""Look up Warhammer: The Old World core rules on the online rules index
(https://tow.whfb.app), including matched play, FAQ and errata.

Pages are fetched on demand and cached locally; no rules text is bundled.
If this environment can't reach the site (e.g. a sandbox with a network
allowlist), `search` falls back to a bundled list of page paths and `get`
prints the URL to open with a web fetch tool instead.

Usage:
  tow_rules.py search TERMS...    find rule pages whose path matches all terms
  tow_rules.py get PATH|URL       print a page as plain text (e.g. special-rules/stubborn)
  tow_rules.py sections           list the top-level sections of the index
  tow_rules.py refresh            re-download the page index
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://tow.whfb.app"
CACHE = os.path.join(
    os.environ.get("TOW_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".cache", "old-world-tactician")),
    "rules",
)
INDEX = os.path.join(CACHE, "index.json")
BUNDLED_INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "rules-index.txt")
PAGE_MAX_AGE = 7 * 86400
BLOCKED_EXIT = 3


class Blocked(Exception):
    """The rules site can't be reached from this environment."""


def blocked_message(path):
    return (f"NETWORK BLOCKED: tow.whfb.app can't be reached from this environment.\n"
            f"Open this page with your web fetch tool instead: {BASE}{path}")


def fetch(path):
    url = path if path.startswith("http") else BASE + "/" + path.lstrip("/")
    req = urllib.request.Request(url, headers={"User-Agent": "old-world-tactician"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise
        raise Blocked(f"HTTP {e.code}") from e  # e.g. a sandbox egress proxy refusing the host
    except (urllib.error.URLError, OSError) as e:
        raise Blocked(str(e)) from e


def build_index(force=False):
    if not force and os.path.exists(INDEX) and time.time() - os.path.getmtime(INDEX) < PAGE_MAX_AGE:
        with open(INDEX) as f:
            return json.load(f)
    paths = set()
    for page in ("/", "/sitemap", "/sitemap/armies"):
        try:
            paths |= set(re.findall(r'href="(/[a-z0-9][^"#?]*)"', fetch(page)))
        except (Blocked, urllib.error.HTTPError):
            break
    paths = sorted(p for p in paths if not p.startswith(("/_next", "/icons", "/api")))
    if not paths:
        # Offline: use the bundled path list, and don't cache it so the
        # live index is picked up as soon as the site is reachable.
        global OFFLINE
        OFFLINE = True
        with open(BUNDLED_INDEX) as f:
            return [l.strip() for l in f if l.strip()]
    os.makedirs(CACHE, exist_ok=True)
    with open(INDEX, "w") as f:
        json.dump(paths, f)
    return paths


def page_text(raw):
    raw = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<(br|/p|/div|/h\d|/li|/tr)[^>]*>", "\n", raw, flags=re.I)
    raw = re.sub(r"<h(\d)[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", raw)
    raw = re.sub(r"<li[^>]*>", "- ", raw)
    raw = re.sub(r"<t[dh][^>]*>", " | ", raw)
    text = html.unescape(re.sub(r"<[^>]+>", "", raw))
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    text = "\n".join(l for l in lines if l)
    # Drop site chrome before the title and after the content.
    start = text.find("Table of Contents")
    if start != -1:
        text = text[start + len("Table of Contents"):]
    for marker in ("\nPrevious - ", "\nNext - ", "\nSwitch Index"):
        end = text.find(marker)
        if end != -1:
            text = text[:end]
    return text.replace("URL Copied!", "").strip()


def cmd_get(path):
    if path.startswith(BASE):
        path = path[len(BASE):]
    path = "/" + path.strip("/")
    key = hashlib.sha1(path.encode()).hexdigest()
    cached = os.path.join(CACHE, key + ".txt")
    if os.path.exists(cached) and time.time() - os.path.getmtime(cached) < PAGE_MAX_AGE:
        with open(cached) as f:
            text = f.read()
    else:
        try:
            raw = fetch(path)
            missing = "<title>Loading..." in raw or len(page_text(raw)) < 40
        except urllib.error.HTTPError:
            missing = True
        except Blocked:
            print(blocked_message(path))
            sys.exit(BLOCKED_EXIT)
        if missing:
            words = [w for w in path.strip("/").split("/")[-1].split("-") if len(w) > 2]
            hits = search(words) or search(words[-1:])
            sys.exit(f"No rules page at {path}. Candidates: {', '.join(hits[:10]) or 'none — try `search`'}")
        text = page_text(raw)
        os.makedirs(CACHE, exist_ok=True)
        with open(cached, "w") as f:
            f.write(text)
    print(f"Source: {BASE}{path}\n")
    print(text)


OFFLINE = False


def search(terms):
    terms = [t.lower() for t in terms]
    paths = build_index()
    hits = [p for p in paths if all(t in p.lower() for t in terms)]
    # Prefer shorter, more specific paths.
    return sorted(hits, key=lambda p: (p.count("/"), len(p)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("terms", nargs="+")
    s = sub.add_parser("get"); s.add_argument("path")
    sub.add_parser("sections")
    sub.add_parser("refresh")
    args = ap.parse_args()
    if args.cmd == "search":
        hits = search(args.terms)
        print("\n".join(hits[:40]) or "No matching pages. Try fewer or shorter terms, or `sections`.")
        if len(hits) > 40:
            print(f"... {len(hits) - 40} more")
        if OFFLINE:
            print(f"\n(Offline: matched against the bundled page list. tow.whfb.app is not reachable "
                  f"from here, so open pages with your web fetch tool, e.g. {BASE}{hits[0] if hits else '/'})")
    elif args.cmd == "get":
        cmd_get(args.path)
    elif args.cmd == "sections":
        counts = {}
        for p in build_index():
            counts[p.split("/")[1]] = counts.get(p.split("/")[1], 0) + 1
        for sec, n in sorted(counts.items()):
            print(f"/{sec}  ({n} pages)")
    elif args.cmd == "refresh":
        print(f"{len(build_index(force=True))} pages indexed.")


if __name__ == "__main__":
    main()
