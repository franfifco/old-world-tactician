# Reviewing an army list

A list review has two halves: **is it legal and correctly costed**, and **will it
win games**. Do the first mechanically with the scripts, then spend most of your
thinking on the second.

## 1. Parse

Common formats:
- **New Recruit text export**: header with army, points, game mode; then units by
  category with `[pts]` and indented options.
- **Old World Builder** (old-world-builder.com) export: army name, points, then
  units grouped as Characters / Core / Special / Rare / Mercenaries / Allies, each
  with cost and options, magic items listed per character.
- **Free text / screenshots / forum posts**: be generous in interpretation and
  list your assumptions ("I've read 'GW' as great weapon").

Write down, before analysing: army (and Army of Infamy if any), points limit,
game mode / event rules, General, Battle Standard Bearer, wizards with level and
lore, every unit with size and options.

## 2. Validate

Look up all the list's units in one call (`tow_data.py unit <army> "<unit 1>" "<unit 2>" ...`)
and its magic items in another (`item "<item 1>" "<item 2>" ...`), then check:
- Unit cost = per-model cost × models + options (watch per-model vs per-unit
  options, champions/musicians/standards, mounts, and items).
- The option exists for that unit and isn't conditional on something absent.
- Unit size within limits.
- Magic items within the character's allowance; magic standards only on units
  that can take them; each named magic item at most once per army unless the
  data says otherwise; one magic weapon/armour/etc. per character (check the
  rules page for magic item rules if unsure).

Then for the army:
- `tow_data.py composition <army>`: category percentages and army-specific
  per-1,000-point caps.
- Combined Arms / Grand Melee extra limits if used (rules site, matched-play).
  Combined Arms caps count copies of the **same unit entry** (e.g. max 4 of any
  one Core unit at 2,000 pts), not the category total.
- Total points ≤ limit.

Report legality as a short table: entry, listed cost, computed cost, issue. If
everything checks out, say so in one line and move on.

## 3. Understand the plan

Classify every unit by its job. A unit can have two jobs but rarely three:
- **Hammer** – wins combats and breaks units (shock cavalry, elite infantry,
  monsters, chariots with impact hits).
- **Anvil** – holds a combat long enough for the hammer to arrive (big ranked
  block, Stubborn/Unbreakable/Steady units, high-toughness monsters).
- **Chaff / redirector** – cheap, fast, expendable units that block, bait
  charges, redirect frenzied or impetuous enemies, and screen.
- **Shooting / war machines** – remove the opponent's key pieces before combat
  or thin out chaff.
- **Magic** – wizards: augments, hexes, missiles, vortexes; also dispel defence.
- **Scoring / objective players** – what holds objectives and claims scenario
  points in the event's scenarios.
- **Characters** – General (Leadership bubble), Battle Standard Bearer, combat
  lords, character killers.

Then answer:
- **How does this list win?** Name the 2–3 units that actually do it. If the
  answer is "everything fights a bit", that's a weakness.
- **Redundancy**: if the main hammer dies turn 1 to a cannon, is there a second?
- **Speed profile**: who reaches combat on turn 2? Is the army split between fast
  and slow parts that will arrive piecemeal?
- **Drops**: count deployment drops (units, with characters per the deployment
  rules). Fewer drops tends to win the choice of first turn, more drops gives
  information advantage. Check the scenario/deployment rules for how it works.
- **Magic phase**: power level, lores chosen, dispel defence, item support.
- **Shooting & war machines**: volume, Strength/AP, range; what can it threaten
  on turn 1?
- **Leadership & psychology**: General range coverage, BSB, Fear/Terror,
  Immune to Psychology, Stupidity/Frenzy/Impetuous liabilities.
- **Combat resolution sources**: ranks, standards, champions, flank charges,
  Unit Strength advantages (and rules like Massed Infantry), and what that means
  for breaking enemy units vs. just killing models.
- **Scenario fit**: can it take and hold objectives, protect its baggage, score
  secondary objectives in the event's pack?

## 4. Stress test against archetypes

Briefly game it against common opponent types and note where it struggles:
- **Big monsters / dragons** – does it have high-Strength, Multiple Wounds,
  cannon/bolt thrower or Killing Blow-type answers?
- **Heavily armoured cavalry / knights** – Armour Bane, high AP, Strength 5+
  shooting, or a way to hold them (Stubborn, steady anvils, spears/halberds)?
- **Hordes / Unit Strength armies** – can it beat static combat resolution?
- **Gunlines / heavy shooting** – terrain usage, fast units, magic missiles,
  vanguard/scouts to close the gap.
- **Magic-heavy** – dispel dice/items, wizards of its own, Magic Resistance.
- **Elusive / fast skirmishers & flyers** – does it have chaff and shooting to
  deny them?
- **Ethereal / ward-heavy** – magical attacks, magic weapons, spells.

Use `dice.py` for the key duels (e.g. "can my knights break that unit on the
charge?", "how many turns does my cannon need to kill that dragon?").

## 5. Suggest changes

- Keep the list legal and at (or just under) the points limit; show the maths
  for every swap.
- Explain what each change fixes and what it costs (the trade-off).
- Offer 2–3 distinct directions when the list's identity is open ("more
  anvil", "more shooting", "faster"), and respect the user's theme and models.
- Prefer small, high-value changes before a rebuild.
- Present the final suggested list in the same format the user gave you.
