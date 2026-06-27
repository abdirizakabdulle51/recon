# Clearing House Reconciliation Engine

Reconciles a **participant file** (telecom or hawala — Telesom, Hormuud, Golis,
Taaj, Durdur, …) against the **clearing house (CH) file** for the same day.
Replaces the manual `CSV → TXT → Beyond Compare` workflow.

## What it does

Takes two files, matches every transaction by transfer ID, and sorts them into:

- **Clean matches** — identical (handling the debit/credit mirror between the two parties).
- **Expected interconnect fees** — amount gaps that match a known CH fee tier. Not chased.
- **Exceptions to chase:**
  - Missing from CH (participant has it, CH doesn't)
  - Missing from participant (CH has it, participant doesn't)
  - Unexplained differences (a gap that no known fee explains)

## Why it's correct (validated on real data)

Tested on real files (Telesom vs CH, 30-Dec-25, ~142,000 transactions; Durdur vs
CH, clean day). Two things a naive file-diff gets wrong, which this handles:

1. **Column order differs** between files (`CREDIT,DEBIT,...` vs `DEBIT,CREDIT,...`).
   Columns are mapped by header name, or by standard order when there's no header.
2. **Debit/Credit are mirrored** between the two parties (one side's debit is the
   other's credit). A match is direct OR mirrored equality.

## Usage

```bash
python3 recon_engine.py <participant_file> <ch_file> [ParticipantName]
```

Example:
```bash
python3 recon_engine.py Telsom.txt CH_4.txt Telesom
```

## Making fee-checking exact

The engine currently treats amount gaps matching `KNOWN_FEE_TIERS` as expected
fees. Real data shows the fee is **tiered (fixed amounts) for small transactions
and a percentage for large ones**. With the official **ServiceRates table**
(amount-band × transaction-type → fee), `reconcile()` can compute the exact
expected fee per transaction and flag any *miscalculated* fee — turning the tool
from "finds missing transactions" into "audits whether the CH charged correctly."

Two inputs upgrade accuracy:
- **ServiceRates table** → exact fee per transaction.
- **Transaction type / status** per row → apply the right fee column, and explain
  why some transactions are "missing" (pending/returned, resolving next day).
