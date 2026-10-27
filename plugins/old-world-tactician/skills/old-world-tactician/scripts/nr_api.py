#!/usr/bin/env python3
"""Client for the New Recruit tournament API (https://www.newrecruit.eu).

The API needs a New Recruit account that the NR team has enabled for API
access. Credentials are looked up in this order:
  1. NR_LOGIN / NR_PASSWORD environment variables
  2. the OS keychain (macOS Keychain; elsewhere via the optional `keyring` package)
  3. ~/.config/old-world-tactician/newrecruit.json, only if chmod 600

Usage:
  nr_api.py login                              store credentials in the keychain (interactive;
                                               run it yourself in a terminal)
  nr_api.py logout                             remove them from the keychain
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
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

API = "https://www.newrecruit.eu/api"
SERVICE = "old-world-tactician-newrecruit"
NOT_REACHABLE = (
    "NETWORK BLOCKED: www.newrecruit.eu can't be reached from this environment. "
    "Tournament features need Claude Code on the user's own computer (network access "
    "plus their keychain). Tell the user once and carry on without tournament data."
)
CONFIG = os.path.join(os.path.expanduser("~"), ".config", "old-world-tactician", "newrecruit.json")
SYSTEM_CACHE = os.path.join(
    os.environ.get("TOW_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".cache", "old-world-tactician")),
    "nr_system_id",
)


# --------------------------------------------------------------------------
# Credentials: environment -> OS keychain -> config file (owner-only).
# The password is never printed, logged or passed on a command line.

def _keychain_read():
    if sys.platform == "darwin" and shutil.which("security"):
        attrs = subprocess.run(["security", "find-generic-password", "-s", SERVICE],
                               capture_output=True, text=True)
        if attrs.returncode != 0:
            return None, None
        m = re.search(r'"acct"<blob>="(.*)"', attrs.stdout)
        pw = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-w"],
                            capture_output=True, text=True)
        if m and pw.returncode == 0:
            return m.group(1), pw.stdout.rstrip("\n")
        return None, None
    try:
        import keyring  # optional, for Windows / Linux secret stores
    except ImportError:
        return None, None
    login = keyring.get_password(SERVICE, "__login__")
    return login, keyring.get_password(SERVICE, login) if login else None


def _config_read():
    if not os.path.exists(CONFIG):
        return None, None
    if os.name == "posix" and os.stat(CONFIG).st_mode & 0o077:
        sys.exit(f"Refusing to read {CONFIG}: it is readable by other users. Run: chmod 600 '{CONFIG}'")
    with open(CONFIG) as f:
        cfg = json.load(f)
    return cfg.get("login"), cfg.get("password")


def credentials():
    login, password = os.environ.get("NR_LOGIN"), os.environ.get("NR_PASSWORD")
    if not (login and password):
        login, password = _keychain_read()
    if not (login and password):
        login, password = _config_read()
    if not (login and password):
        sys.exit(
            "New Recruit API credentials not found.\n"
            "Store them in your OS keychain by running this yourself in a terminal:\n"
            f"  python3 {os.path.abspath(__file__)} login\n"
            "API access must be enabled for your account by the New Recruit team.\n"
            "If this is a Claude chat or cloud session, tournament features aren't available "
            "here: run them from Claude Code on your own computer."
        )
    return login, password


def cmd_login():
    if not sys.stdin.isatty():
        sys.exit("`login` is interactive: run it yourself in a terminal so the password "
                 "is typed only into the keychain prompt.")
    login = input("New Recruit username: ").strip()
    if not login:
        sys.exit("No username given.")
    if sys.platform == "darwin" and shutil.which("security"):
        subprocess.run(["security", "delete-generic-password", "-s", SERVICE],
                       capture_output=True)
        print("macOS will now ask for the password (typed twice); it goes straight into your login keychain.")
        # A trailing -w with no value makes `security` prompt for the password itself.
        r = subprocess.run(["security", "add-generic-password", "-s", SERVICE, "-a", login,
                            "-l", "New Recruit API (old-world-tactician)", "-w"])
        if r.returncode != 0:
            sys.exit("Could not save to the keychain.")
    else:
        try:
            import keyring
        except ImportError:
            sys.exit("No OS keychain available. Install the `keyring` package "
                     "(pip install keyring), or use NR_LOGIN / NR_PASSWORD.")
        keyring.set_password(SERVICE, "__login__", login)
        keyring.set_password(SERVICE, login, getpass.getpass("New Recruit password: "))
    print("Saved. The first API call may show a keychain access prompt; choose 'Always Allow' "
          "for python3 if you don't want to be asked each time.")


def cmd_logout():
    if sys.platform == "darwin" and shutil.which("security"):
        r = subprocess.run(["security", "delete-generic-password", "-s", SERVICE], capture_output=True)
        print("Removed from keychain." if r.returncode == 0 else "Nothing stored in the keychain.")
    else:
        try:
            import keyring
            login = keyring.get_password(SERVICE, "__login__")
            if login:
                keyring.delete_password(SERVICE, login)
                keyring.delete_password(SERVICE, "__login__")
            print("Removed from keyring." if login else "Nothing stored in the keyring.")
        except ImportError:
            print("No keyring available; nothing to remove.")


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
        try:
            data = json.loads(detail)  # New Recruit answers errors in JSON
        except ValueError:
            sys.exit(NOT_REACHABLE + f"\n(HTTP {e.code}: {detail[:200]})")
    except (urllib.error.URLError, OSError) as e:
        sys.exit(NOT_REACHABLE + f"\n({e})")
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
    sub.add_parser("login")
    sub.add_parser("logout")
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

    if args.cmd == "login":
        return cmd_login()
    if args.cmd == "logout":
        return cmd_logout()
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
