#!/usr/bin/env python3
"""
Clearing House Reconciliation Engine  (v1)
==========================================
Reconciles a PARTICIPANT file (telecom or hawala: Telesom, Hormuud, Taaj, ...)
against the CLEARING HOUSE file for the same day.

Replaces the manual  CSV -> TXT -> Beyond Compare  workflow.

Validated on real data (Telesom vs CH, 30-Dec-25, ~142,000 transactions):
correctly filters to the true exception list a human finds by hand.

KEY LOGIC DISCOVERED FROM REAL FILES
------------------------------------
1. Column order differs between files. We read each file's HEADER and map
   DEBIT / CREDIT / TRANSFERID by name, never by position.

2. Debit/Credit are MIRRORED between the two parties. One party's debit is the
   other's credit (normal double-entry between two sides). A transaction is a
   clean match if:
        participant.debit == ch.credit  AND  participant.credit == ch.debit
   (we also accept a straight debit==debit / credit==credit match).

3. The gross amount differs by the INTERCONNECT FEE (the CH charge). These gaps
   cluster at known tier values (0.05, 0.10, 0.125, 0.15, 0.20, 0.25, ...).
   With the official ServiceRates table, this becomes an exact check. Until
   then, gaps matching the known tier set are treated as EXPECTED FEE; gaps
   that do NOT match a tier are flagged as REAL exceptions to chase.
"""

from dataclasses import dataclass, field

# Known interconnect-fee tier values, observed in real data.
# Replace / extend with the official ServiceRates table when available.
KNOWN_FEE_TIERS = {0.05, 0.0625, 0.10, 0.125, 0.15, 0.20, 0.25, 0.30, 0.50, 1.00}
EPS = 0.0001


@dataclass
class Txn:
    debit: float
    credit: float

    @property
    def gross(self):
        return max(self.debit, self.credit)


@dataclass
class ReconResult:
    clean: int = 0
    expected_fee: list = field(default_factory=list)   # (tid, fee)
    unexplained: list = field(default_factory=list)     # (tid, p_d, p_c, c_d, c_c, gap)
    missing_from_ch: list = field(default_factory=list) # (tid, debit, credit)
    missing_from_participant: list = field(default_factory=list)
    participant_count: int = 0
    ch_count: int = 0

    @property
    def total_exceptions(self):
        return (len(self.unexplained) + len(self.missing_from_ch)
                + len(self.missing_from_participant))


def load_file(path):
    """Read a recon file. Maps columns by HEADER NAME so swapped order is safe."""
    rows = {}
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    if not lines:
        return rows
    first = lines[0].replace("\r", "")
    delim = "\t" if "\t" in first else ","
    header = [h.strip().upper() for h in first.split(delim)]
    has_header = any(h in ("DEBIT", "CREDIT", "TRANSFERID", "CHTRANSFERID") for h in header)
    if has_header:
        idx = {name: i for i, name in enumerate(header)}
        di = idx.get("DEBIT")
        ci = idx.get("CREDIT")
        ti = idx.get("TRANSFERID", idx.get("CHTRANSFERID"))
        data_lines = lines[1:]
    else:
        # No header row: assume standard order DEBIT, CREDIT, TRANSFERID, DATE
        di, ci, ti = 0, 1, 2
        data_lines = lines
    if di is None or ci is None or ti is None:
        raise ValueError(f"Could not find DEBIT/CREDIT/TRANSFERID columns in {path}. Header was: {header}")
    for line in data_lines:
        line = line.replace("\r", "").strip()
        if not line:
            continue
        p = line.split(delim)
        if len(p) <= max(di, ci, ti):
            continue
        try:
            rows[p[ti].strip()] = Txn(float(p[di]), float(p[ci]))
        except ValueError:
            continue
    return rows


def is_match(a: Txn, b: Txn):
    """Direct OR mirrored (debit<->credit) equality."""
    direct = abs(a.debit - b.debit) < EPS and abs(a.credit - b.credit) < EPS
    mirror = abs(a.debit - b.credit) < EPS and abs(a.credit - b.debit) < EPS
    return direct or mirror


def reconcile(participant, ch, fee_tiers=KNOWN_FEE_TIERS):
    res = ReconResult()
    res.participant_count = len(participant)
    res.ch_count = len(ch)
    p_ids, c_ids = set(participant), set(ch)

    for tid in p_ids - c_ids:
        t = participant[tid]
        res.missing_from_ch.append((tid, t.debit, t.credit))

    for tid in c_ids - p_ids:
        t = ch[tid]
        res.missing_from_participant.append((tid, t.debit, t.credit))

    for tid in p_ids & c_ids:
        a, b = participant[tid], ch[tid]
        if is_match(a, b):
            res.clean += 1
            continue
        # The interconnect fee can land on EITHER side. Check both the debit-side
        # gap and the credit-side gap, in both direct and mirrored orientation.
        # If the smallest non-zero gap matches a known fee tier, it's an expected fee.
        candidates = [
            abs(a.debit - b.debit), abs(a.credit - b.credit),   # direct
            abs(a.debit - b.credit), abs(a.credit - b.debit),   # mirror
        ]
        gaps = [round(g, 4) for g in candidates if g > EPS]
        fee_gap = next((g for g in sorted(gaps) if any(abs(g - tier) < EPS for tier in fee_tiers)), None)
        if fee_gap is not None:
            res.expected_fee.append((tid, fee_gap))
        else:
            gap = round(b.gross - a.gross, 4)
            res.unexplained.append((tid, a.debit, a.credit, b.debit, b.credit, gap))
    return res


def format_report(res, participant_name="Participant", ch_name="CH", date="", show=50):
    L = []
    L.append("=" * 64)
    L.append(f"  RECONCILIATION REPORT   {participant_name}  vs  {ch_name}   {date}")
    L.append("=" * 64)
    L.append(f"  {participant_name} transactions ...... {res.participant_count:>10,}")
    L.append(f"  {ch_name} transactions ...... {res.ch_count:>10,}")
    L.append("  " + "-" * 50)
    L.append(f"  Clean matches .................... {res.clean:>10,}")
    L.append(f"  Expected interconnect fees ...... {len(res.expected_fee):>10,}")
    L.append("  " + "-" * 50)
    L.append(f"  Missing from {ch_name:<12} ....... {len(res.missing_from_ch):>10,}")
    L.append(f"  Missing from {participant_name:<12} . {len(res.missing_from_participant):>10,}")
    L.append(f"  Unexplained differences ......... {len(res.unexplained):>10,}")
    L.append("  " + "=" * 50)
    L.append(f"  >>> TOTAL TO CHASE: {res.total_exceptions:>10,}")
    L.append("=" * 64)

    if res.total_exceptions == 0:
        L.append("  BALANCED - nothing to chase. Reconciliation complete.")
        return "\n".join(L)

    if res.missing_from_ch:
        L.append(f"\n  -- Missing from {ch_name} (present in {participant_name}) --")
        for tid, d, c in res.missing_from_ch[:show]:
            L.append(f"     {tid}    debit={d}   credit={c}")
        if len(res.missing_from_ch) > show:
            L.append(f"     ... and {len(res.missing_from_ch)-show} more")

    if res.missing_from_participant:
        L.append(f"\n  -- Missing from {participant_name} (present in {ch_name}) --")
        for tid, d, c in res.missing_from_participant[:show]:
            L.append(f"     {tid}    debit={d}   credit={c}")
        if len(res.missing_from_participant) > show:
            L.append(f"     ... and {len(res.missing_from_participant)-show} more")

    if res.unexplained:
        L.append(f"\n  -- Unexplained amount differences (not a known fee tier) --")
        for tid, pd, pc, cd, cc, gap in res.unexplained[:show]:
            L.append(f"     {tid}   {participant_name}: d={pd} c={pc} | {ch_name}: d={cd} c={cc} | gap={gap}")
        if len(res.unexplained) > show:
            L.append(f"     ... and {len(res.unexplained)-show} more")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        p = load_file(sys.argv[1])
        c = load_file(sys.argv[2])
        r = reconcile(p, c)
        name_p = sys.argv[3] if len(sys.argv) > 3 else "Participant"
        print(format_report(r, name_p, "CH"))
