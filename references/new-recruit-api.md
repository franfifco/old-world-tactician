# New Recruit API

New Recruit (https://www.newrecruit.eu) runs list building and tournaments for
The Old World. Its API is documented at https://www.newrecruit.eu/tutorials/systems
(plus `/tutorials/tournaments`, `/tutorials/tournament`, `/tutorials/reports`).

## Access

Every call needs a New Recruit username and password **that the NR team has
enabled for API access**. Without that, every endpoint returns
`Wrong username/password, please contact NR if you need to access this API`.
Ask the user to contact New Recruit (their Discord or site contact) to request
access; don't try other accounts or workarounds.

Configure once, either:
```
export NR_LOGIN=yourname
export NR_PASSWORD=yourpassword
```
or create `~/.config/old-world-tactician/newrecruit.json` with
`{"login": "...", "password": "..."}` and `chmod 600` it. Never ask the user to
paste their password into the chat; have them set it up themselves.

## Endpoints (all POST, JSON body)

| Endpoint | Body | Returns |
|---|---|---|
| `/api/systems` | none | `[{id, name}]` game systems |
| `/api/tournaments` | `start`, `end` (YYYY-MM-DD), `id_game_system`, optional `status` (0 pending, 1 open, 2 ongoing, 3 closed), `page` (50 per page) | `{tournaments: [{_id, name, start, end, status}], total}` |
| `/api/tournament` | `id` | `{name, teams: [{name, players: [{name, lists}]}], type, visibility, showlists}` or `null` |
| `/api/reports` | `id_tournament` (or `id_tourny`) and/or `player` | array of game reports, with `exported_list` when available |

`nr_api.py` wraps all of these and finds The Old World's system id automatically.

## Doing meta analysis

1. `nr_api.py --out t.json tournaments --start 2026-07-01 --status 3` for closed
   events in a window (page through with `--page` if `total` > 50).
2. For each relevant event: `nr_api.py --out reports_<id>.json reports --tournament <id>`.
3. Inspect one record first to learn the actual field names (the report schema
   isn't documented), then write a short Python script to aggregate: games and
   win rate per army, most common units/items in winning lists, matchup tables.
4. Report sample sizes. With fewer than ~20 games for an army, describe trends,
   not rates.

Lists may be hidden if the tournament's `showlists` setting doesn't allow it.
