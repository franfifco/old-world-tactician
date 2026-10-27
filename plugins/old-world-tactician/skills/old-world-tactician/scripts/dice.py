#!/usr/bin/env python3
"""Exact damage odds for an attack sequence: hit -> wound -> armour -> ward/regen.

Takes the target numbers you have already worked out from the rules
(e.g. hit on 4+, wound on 3+, enemy saves on 5+ after AP), so it works for
combat, shooting, impact hits and spells alike.

Examples:
  dice.py -n 12 --hit 3 --wound 4 --save 5
  dice.py -n 4 --hit 4 --wound 2 --save 0 --ward 5 --multi D3 --reroll-wound fail
  dice.py -n 2D6 --hit 0 --wound 4 --save 4          # 2D6 automatic hits
  dice.py -n 10 --hit 4 --wound 4 --save 4 --compare -n2 10 --hit2 3

Rules that change Strength/AP per hit (e.g. losing Strength per rank) can be
modelled by running each step separately and adding the results.

A target of 0 means "automatic" (no roll / no save). A roll of 1 always fails
to hit and to wound, and a natural 1 always fails a save.
"""

import argparse
import re
from fractions import Fraction


def p_success(target, reroll=None):
    """Probability a D6 meets target+ with optional reroll ('fail' or 'ones')."""
    if not target:
        return Fraction(1)
    target = min(max(target, 2), 7)
    p = Fraction(7 - target, 6) if target <= 6 else Fraction(0)
    if reroll == "fail":
        p = p + (1 - p) * p
    elif reroll == "ones":
        p = p + Fraction(1, 6) * p
    return p


def p_fail_save(target, reroll=None):
    if not target or target > 6:
        return Fraction(1)
    return 1 - p_success(target, reroll)


def dist_from_spec(spec):
    """Distribution {value: prob} for '7', 'D3', 'D6', '2D6', 'D3+1'."""
    spec = str(spec).upper().replace(" ", "")
    m = re.fullmatch(r"(\d*)D(\d+)([+-]\d+)?|(\d+)", spec)
    if not m:
        raise SystemExit(f"Bad dice spec: {spec}")
    if m.group(4):
        return {int(m.group(4)): Fraction(1)}
    count, sides, mod = int(m.group(1) or 1), int(m.group(2)), int(m.group(3) or 0)
    dist = {0: Fraction(1)}
    for _ in range(count):
        new = {}
        for v, p in dist.items():
            for face in range(1, sides + 1):
                new[v + face] = new.get(v + face, 0) + p / sides
        dist = new
    return {v + mod: p for v, p in dist.items()}


def convolve(a, b):
    out = {}
    for x, px in a.items():
        for y, py in b.items():
            out[x + y] = out.get(x + y, 0) + px * py
    return out


def run(n, hit, wound, save, ward, regen, multi, rr_hit, rr_wound, rr_save, cap, bane=0):
    p_wound = p_success(wound, rr_wound)
    if bane and wound and save:
        # Successful wound rolls are uniform over the passing faces, so a
        # natural 6 is 1/(7-target) of them; those worsen the save by `bane`.
        p_six = p_wound / (7 - min(max(wound, 2), 6))
        p_fail_armour = (p_wound - p_six) * p_fail_save(save, rr_save) + p_six * p_fail_save(save + bane, rr_save)
    else:
        p_fail_armour = p_wound * p_fail_save(save, rr_save)
    p_unsaved = p_success(hit, rr_hit) * p_fail_armour * p_fail_save(ward) * p_fail_save(regen)
    per_attack = {0: 1 - p_unsaved}
    for v, p in dist_from_spec(multi).items():
        per_attack[v] = per_attack.get(v, 0) + p_unsaved * p
    total = {0: Fraction(0)}
    for n_val, pn in dist_from_spec(n).items():
        d = {0: Fraction(1)}
        for _ in range(n_val):
            d = convolve(d, per_attack)
        for v, p in d.items():
            v = min(v, cap) if cap else v
            total[v] = total.get(v, 0) + p * pn
    return p_unsaved, total


def report(label, p_unsaved, total):
    mean = sum(v * p for v, p in total.items())
    print(f"{label}: P(an attack causes an unsaved wound) = {float(p_unsaved):.3f}; "
          f"expected wounds = {float(mean):.2f}")
    acc = Fraction(0)
    for v in sorted(total, reverse=True):
        acc += total[v]
        total[v] = acc  # now P(>= v)
    shown = [v for v in sorted(total) if v > 0 and total[v] > 0.005][:12]
    print("  " + "  ".join(f"≥{v}: {float(total[v]):.0%}" for v in shown))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", default="1", help="attacks/shots/hits: number or dice (D6, 2D6, D3+1)")
    ap.add_argument("--hit", type=int, default=4, help="to hit target (0 = auto-hit)")
    ap.add_argument("--wound", type=int, default=4, help="to wound target")
    ap.add_argument("--save", type=int, default=0, help="armour save after AP (0 = none)")
    ap.add_argument("--ward", type=int, default=0, help="ward save (0 = none)")
    ap.add_argument("--regen", type=int, default=0, help="regeneration save (0 = none)")
    ap.add_argument("--multi", default="1", help="wounds per unsaved hit (Multiple Wounds): 2, D3, D6")
    ap.add_argument("--armour-bane", type=int, default=0,
                    help="Armour Bane (X): natural 6s to wound worsen the save by X more")
    ap.add_argument("--reroll-hit", choices=["fail", "ones"])
    ap.add_argument("--reroll-wound", choices=["fail", "ones"])
    ap.add_argument("--reroll-save", choices=["fail", "ones"], help="defender rerolls armour saves")
    ap.add_argument("--cap", type=int, help="cap per-volley wounds (e.g. target's remaining Wounds)")
    ap.add_argument("--compare", action="store_true", help="also run a variant using the *2 options")
    for k in ("n", "hit", "wound", "save", "multi"):
        ap.add_argument(f"--{k}2" if k != "n" else "-n2")
    a = ap.parse_args()
    base = dict(n=a.n, hit=a.hit, wound=a.wound, save=a.save, ward=a.ward, regen=a.regen,
                multi=a.multi, rr_hit=a.reroll_hit, rr_wound=a.reroll_wound,
                rr_save=a.reroll_save, cap=a.cap, bane=a.armour_bane)
    report("A", *run(**base))
    if a.compare:
        alt = dict(base)
        for k in ("n", "hit", "wound", "save", "multi"):
            v = getattr(a, f"{k}2")
            if v is not None:
                alt[k] = int(v) if k in ("hit", "wound", "save") else v
        report("B", *run(**alt))


if __name__ == "__main__":
    main()
