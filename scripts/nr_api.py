#!/usr/bin/env python3
"""Client for the New Recruit tournament API (https://www.newrecruit.eu).

The API needs a New Recruit account that the NR team has enabled for API
access. Credentials are read from the environment (NR_LOGIN, NR_PASSWORD) or
from ~/.config/old-world-tactician/newrecruit.json:
  {"login": "...", "password": "..."}

Usage:
  nr_api.py systems                            list game systems (id, name)
  nr_api.py tournaments [--start D] [--end D] [--status N] [--page N] [--system ID]
                                               tournaments for The Old World (default: last 90 days)
  nr_api.py tournament ID                      tournament details: teams, players, lists
  nr_api.py reports (--tournament ID | --player NAME)
                                               game reports, with exported lists when available
  nr_api.py lists ID                           just the players' exported lists for a tournament

Add --out FILE to save the raw JSON instead of printing it; large tournament
dumps are easier to analyse from a file.
Status values: 0 pending, 1 open, 2 ongoing, 3 closed.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://www.newrecruit.eu/api"
CONFIG = os.path.join(os.path.expanduser("~"), ".config", "old-world-tactician", "newrecruit.json")
SYSTEM_CACHE = os.path.join(
    os.environ.get("TOW_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".cache", "old-world-tactician")),
    "nr_system_id",
)


def credentials():
    login, password = os.environ.get("NR_LOGIN"), os.environ.get("NR_PASSWORD")
    if not (login and password) and os.path.exists(CONFIG):
        with open(CONFIG) as f:
            cfg = json.load(f)
        login, password = cfg.get("login"), cfg.get("password")
    if not (login and password):
        sys.exit(
            "New Recruit API credentials not found.\n"
            "Set NR_LOGIN and NR_PASSWORD, or create " + CONFIG + "\n"
            'containing {"login": "...", "password": "..."} (chmod 600).\n'
            "API access must be enabled for your account by the New Recruit team."
        )
    return login, password


def call(endpoint, body=None):
    login, password = credentials()
    req = urllib.request.Request(
        f"{API}/{endpoint}",
        data=json.dumps(body or {}).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "NR-Login": login,
            "NR-Password": password,
            "User-Agent": "old-world-tactician",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        sys.exit(f"New Recruit API error {e.code} on /{endpoint}: {detail}")
    if isinstance(data, dict) and (data.get("message") or data.get("error")) and len(data) == 1:
        sys.exit(f"New Recruit API: {data.get('message') or data.get('error')}")
    return data


def old_world_system_id():
    if os.path.exists(SYSTEM_CACHE):
        with open(SYSTEM_CACHE) as f:
            return int(f.read().strip())
    systems = call("systems")
    match = [s for s in systems if "old world" in s["name"].lower()]
    if not match:
        sys.exit("Could not find The Old World in /api/systems; pass --system ID (see `systems`).")
    match.sort(key=lambda s: len(s["name"]))
    os.makedirs(os.path.dirname(SYSTEM_CACHE), exist_ok=True)
    with open(SYSTEM_CACHE, "w") as f:
        f.write(str(match[0]["id"]))
    return match[0]["id"]


def emit(data, out):
    if out:
        with open(out, "w") as f:
            json.dump(data, f, indent=1)
        size = len(data) if isinstance(data, list) else 1
        print(f"Saved {size} record(s) to {out}")
    else:
        json.dump(data, sys.stdout, indent=1)
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write JSON to this file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("systems")
    s = sub.add_parser("tournaments")
    today = dt.date.today()
    s.add_argument("--start", default=str(today - dt.timedelta(days=90)))
    s.add_argument("--end", default=str(today))
    s.add_argument("--status", type=int, choices=[0, 1, 2, 3])
    s.add_argument("--page", type=int, default=1)
    s.add_argument("--system", type=int, help="game system id (default: The Old World)")
    s = sub.add_parser("tournament"); s.add_argument("id")
    s = sub.add_parser("lists"); s.add_argument("id")
    s = sub.add_parser("reports")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--tournament")
    g.add_argument("--player")
    args = ap.parse_args()

    if args.cmd == "systems":
        data = call("systems")
    elif args.cmd == "tournaments":
        body = {"start": args.start, "end": args.end, "page": args.page,
                "id_game_system": args.system or old_world_system_id()}
        if args.status is not None:
            body["status"] = args.status
        data = call("tournaments", body)
    elif args.cmd == "tournament":
        data = call("tournament", {"id": args.id})
    elif args.cmd == "lists":
        t = call("tournament", {"id": args.id}) or {}
        data = [
            {"team": team.get("name"), "player": p.get("name"), "lists": p.get("lists")}
            for team in t.get("teams", []) for p in team.get("players", [])
        ]
    else:
        body = {"id_tournament": args.tournament} if args.tournament else {"player": args.player}
        data = call("reports", body)
    emit(data, args.out)


if __name__ == "__main__":
    main()
