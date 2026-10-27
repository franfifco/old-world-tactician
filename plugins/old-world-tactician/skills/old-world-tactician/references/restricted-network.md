# When the network is restricted

Some environments (Claude chat and cloud sandboxes) only let scripts reach an
allowlist of hosts. The scripts detect this and print a line starting with
`NETWORK BLOCKED:` instead of failing silently. Don't keep retrying a blocked
script; handle it like this:

- **Rules site blocked** (`tow_rules.py`): `search` still works from a bundled
  list of page paths. For the page text, open the printed `https://tow.whfb.app/...`
  URL with your **web fetch tool**, which runs outside the script sandbox. If web
  fetch is unavailable too, try a web search restricted to `site:tow.whfb.app`.
  Only fall back to the army data's rule text (`tow_data.py rule`) when none of
  those work, and say so.
- **GitHub blocked** (`tow_data.py`): it reuses the cached army data if there is
  any. With no data at all, answer rules from the rules site and say that points
  and profiles couldn't be checked.
- **New Recruit blocked** (`nr_api.py`): tournament features only work in Claude
  Code on the user's own computer (it also needs their keychain). Say so once,
  briefly, and continue with everything else.

Tell the user in one line which source was missing, and that allowing that host
for code execution in their Claude settings (or asking their admin) would fix it.
