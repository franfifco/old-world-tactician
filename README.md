# Old World Tactician

A [Claude skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview) for
**Warhammer: The Old World**. It turns Claude into a rules expert, list builder and
coach that checks its answers against live sources instead of half-remembered
Warhammer Fantasy rules.

What it does:
- **Rules questions**: looks up the official online rules index, FAQ and errata, and
  walks through interactions step by step.
- **List review**: checks your army list for points and composition, explains its
  game plan and weak spots, and suggests legal changes with the points maths.
- **Theorycrafting**: costs combinations of units, items and spells and compares them
  with exact dice odds.
- **Opponent scouting**: finds the threats in an opponent's list and builds a game plan
  for your list against it.
- **Tournament data**: pulls tournaments, lists and game reports from New Recruit (needs
  API access).

## Data sources

Nothing from Games Workshop is bundled here; the scripts fetch it on demand and
cache it in `~/.cache/old-world-tactician/`:

| Source | Used for |
|---|---|
| [tow.whfb.app](https://tow.whfb.app) | Official online rules index, FAQ, errata, matched play |
| [BSData/warhammer-the-old-world](https://github.com/BSData/warhammer-the-old-world) | Army data used by New Recruit: profiles, points, options, special rules, magic items, spells |
| [New Recruit API](https://www.newrecruit.eu/tutorials/systems) | Tournaments, players' lists, game reports (credentials required) |

## Install

**Claude Code**: clone into your skills folder:
```bash
git clone https://github.com/<you>/old-world-tactician ~/.claude/skills/old-world-tactician
```

**Claude.ai / Claude desktop**: zip the folder and upload it under Settings → Capabilities → Skills.

Requires Python 3.8+ (standard library only).

### New Recruit API (optional)

The tournament features need a New Recruit account with API access enabled by the New
Recruit team. Then either set `NR_LOGIN` / `NR_PASSWORD`, or create
`~/.config/old-world-tactician/newrecruit.json`:
```json
{"login": "your-user", "password": "your-password"}
```
and `chmod 600` it.

## Scripts

```bash
python3 scripts/tow_rules.py search charge reaction      # find rules pages
python3 scripts/tow_rules.py get special-rules/stubborn  # read one
python3 scripts/tow_data.py armies                       # list armies
python3 scripts/tow_data.py composition "dark elves"     # composition limits
python3 scripts/tow_data.py units "dark elves"           # units and starting costs
python3 scripts/tow_data.py unit "dark elves" "black guard" --rules
python3 scripts/tow_data.py items "empire" --type weapon
python3 scripts/tow_data.py spells "dark magic"
python3 scripts/dice.py -n 12 --hit 3 --wound 4 --save 5
python3 scripts/nr_api.py tournaments --status 3
```

## Example prompts

- "Is this 2,000 pt Dwarf list legal for Combined Arms, and how does it handle dragons?" (paste the list)
- "My opponent plays Tomb Kings with a Casket of Souls and two Necrosphinxes. What should I watch for with my Wood Elves?"
- "Sword of Might or Biting Blade on my Chaos Lord on Juggernaut?"
- "Can a unit that fled as a charge reaction rally in the same turn?"
- "What have the top Bretonnian lists at recent tournaments looked like?"

## Disclaimer

Unofficial fan project, not affiliated with or endorsed by Games Workshop. Warhammer:
The Old World and all associated names are trademarks of Games Workshop Ltd. Army data
is maintained by the BSData community; check your army book and the latest errata when
it matters.
