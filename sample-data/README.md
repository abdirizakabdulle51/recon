# Sample data (kept out of git by default)

This folder is intentionally excluded from the repository via `.gitignore`
because it contains **real transaction files** from the clearing house and
participants.

To test the tool, place two files here (a participant file and a CH file) and
load them in the app, or run the engine:

    python3 ../engine/recon_engine.py participant.txt ch.txt ParticipantName

If this repository is PRIVATE and you want the sample data committed, remove the
`sample-data/` line from `.gitignore`.
