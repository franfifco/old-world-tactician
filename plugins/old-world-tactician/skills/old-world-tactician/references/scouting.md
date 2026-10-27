# Scouting an opponent's list

The goal is a report the user can read in five minutes before the game (or
during deployment) and actually use. Concrete beats comprehensive.

## Before writing

1. Parse the opponent's list the same way as for a review (army, Army of
   Infamy, characters, wizards and lores, items, units with options). Players
   often use names from older Warhammer Fantasy editions or shorthand; find the
   TOW entry with `tow_data.py search` / `units` and state the mapping you used.
   Quickly cost **both** lists: if either is far off the stated points, the
   list you were given is probably incomplete or out of date — say so, and ask
   for the full list, but still give the best report you can. Flag anything
   that looks illegal (it may be a typo, or a real problem worth raising
   politely before the game).
2. Look up everything you aren't certain about, batched into a few calls
   (`unit`, `rule` and `item` each take many names): every special rule on their
   key units, every magic item, every spell in the lores they can take. The
   surprises in TOW live in army special rules and magic items.
3. If you have the user's own list, look up its key units too, so the
   matchup analysis is grounded in both sides' profiles.
4. Ask (or assume and state) the scenario and deployment, if known.

## Report template

### The plan in one line
"Gunline that wants you to walk into two cannons and a Steam Tank anvil", etc.

### Threats (3–5, ranked)
For each: unit, why it's dangerous (profile/rules/items with numbers), what it
will try to kill, and the answer from the user's list. Include `dice.py` odds
where it sharpens the point, e.g. "their 5 knights on the charge kill 4.1 of
your Spearmen on average; you keep ranks 60% of the time".

### Weaknesses to exploit
Low Leadership, poor armour, psychology (Stupidity, Frenzy, Impetuous),
small/brittle units, a key character the army depends on, exposed war machines,
lack of magic defence, slow speed, few drops, weak against flank charges.

### What to expect, turn by turn
Deployment tendencies, likely first-turn moves (vanguard, scouts, ambushers,
fliers), when their main combat hits, what their magic phase will look for.

### Your game plan
- Deployment: where to put what, what to refuse, how to handle drops.
- Target priority for shooting/magic (and what NOT to waste shots on).
- What to chaff/redirect and with what.
- Which combats to take, which to avoid, and how to get the flank charges.
- Magic: which spells to stop at all costs, which to let through.
- Scenario: how you score versus how they score.

### Traps and gotchas
Rules and items that commonly catch people out in this matchup (look them up
— e.g. a once-per-game item, a charge reaction, a character that can join a
unit mid-game, a unit that can't be charged in some arc). Each with a one-line
counter.

## Archetype reminders

These are thinking prompts, not facts about current points or rules; check
specifics with the scripts.
- **Monster / dragon lords**: identify everything in your list that can hurt
  them, and plan to keep them out of your flanks.
- **Knight hammers**: they win if they charge where they want. Screens, bait,
  and making them charge something that can hold (or flee) win the game.
- **Big blocks / Unit Strength**: avoid frontal grind unless you can out-resolve;
  look for flanks and shooting the support pieces.
- **Gunlines & war machines**: use terrain lines, threat ranges, fast units and
  ambushers; trade chaff for time.
- **Magic-heavy**: decide in advance what you must dispel; count their power.
- **Skirmish / harassment**: chaff of your own, shooting, and not over-chasing.
