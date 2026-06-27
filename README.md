# Reconcile.so

**Clearing house reconciliation — reconcile a full day in one second, not three hours.**

Reconcile.so matches a participant's daily transaction file (telecom or hawala)
against the clearing house (CH) file, automatically recognises interconnect
fees, and returns only the handful of transactions that need a human to check.
It replaces the manual `CSV → TXT → Beyond Compare` workflow.

Validated against real data for five participants — **Telesom, Hormuud, Golis,
Durdur, Taaj** vs CH — matching what an analyst produces by hand in Beyond
Compare, in one second.

---

## What's in this project

```
reconcile-so/
├── web/
│   └── index.html          ← THE PRODUCT. Open in a browser. Runs entirely
│                              client-side; no server, no upload, no database.
├── engine/
│   ├── recon_engine.py     ← The same logic in Python (for testing / batch use)
│   └── README.md           ← Engine internals & logic notes
├── sample-data/            ← Real validated files for testing
│   ├── Durdur.txt  CH_6.txt              (a clean day)
│   ├── Telesom_messy.txt  CH_messy.txt   (a messy day, 95 real exceptions)
│   ├── Telesom_23.txt  CH_23.txt         (today-style telecom day)
│   └── Taaj_23.txt  CH_Taaj_23.txt       (hawala, balance format)
└── sample-reports/         ← Example outputs from the engine
```

---

## How the tool works (no database needed)

The whole reconciliation runs **in the browser**. The user drags in two files,
clicks Reconcile, and sees the result. Files never leave their computer — which
is exactly what a finance team at a telecom or hawala needs. That's also why it
deploys as a simple static site with nothing to host or secure.

### What it handles correctly (learned from real data)
1. **Two file formats, auto-detected:**
   - Telecoms: `DEBIT, CREDIT, TRANSFERID, CREATEDDATE`
   - Hawalas: `BALANCE, REFNO/TRANSFERID, CREATEDDATE`
2. **Column order differs** between files — columns mapped by header name.
3. **Debit/Credit are mirrored** between the two parties (one side's debit is the
   other's credit). Matching accounts for this.
4. **Interconnect fee** — small amount gaps that match known fee tiers are cleared
   automatically as "expected fee"; the fee can sit on either side.
5. Everything else becomes the **exception list to chase**: missing on one side,
   or a difference no known fee explains.

---

## Deploying to Cloudflare Pages (free, no backend)

**Method 1 — Direct upload (simplest):**
1. Go to dash.cloudflare.com → **Workers & Pages** → **Create** → **Pages** tab → **Upload assets**.
2. Name the project (e.g. `reconcile-so`).
3. Drag in the contents of the `web/` folder (the `index.html`).
4. **Deploy** → you get a live URL like `https://reconcile-so.pages.dev`.

**Method 2 — Connect to GitHub (for ongoing updates):**
1. Push this project to a GitHub repo.
2. Cloudflare → **Create** → **Pages** → **Connect to Git** → pick the repo.
3. Build command: *(leave empty)*. Output directory: `web`.
4. **Save and Deploy**. Every push auto-deploys.

> Custom domain (if you register reconcile.so): Pages project → **Custom domains**
> → add `reconcile.so` and follow the steps.

> Note: the live link is a fully working tool. Share it deliberately with people
> you're courting — not publicly — until you've locked in a customer.

---

## Using the Python engine (optional)

```bash
python3 engine/recon_engine.py <participant_file> <ch_file> [ParticipantName]

# examples:
python3 engine/recon_engine.py sample-data/Telesom_messy.txt sample-data/CH_messy.txt Telesom
python3 engine/recon_engine.py sample-data/Taaj_23.txt sample-data/CH_Taaj_23.txt Taaj
```

---

## Next step: exact fee auditing (the ServiceRates upgrade)

Today the tool recognises fees by matching known tier values. To make fee
checking **exact** — and to catch when the CH charges the *wrong* fee (the
feature a telecom will pay for) — wire in the CH's `SERVICERATE` table.

Two answers still needed from the CH side:
1. **Which `RATETYPEID` means percentage vs fixed amount?** (We know at least one
   type is a percentage. Likely: small transactions = fixed tiers, large = %.)
2. **For a transaction in the recon file, how is its `SERVICEID` (type) and
   source/target network determined?** The rate depends on service + network pair
   + amount slab, but the recon file only has amount, ID, and date — so we need
   the link from a transaction to its rate-table row.

With those two answers, fee detection moves from pattern-matching to exact
calculation per the CH's own rate table.
