"""Annual lottery draw (Règlement §3). LOCAL-ONLY — never run in CI.

This script reads the email column, which must never appear in the public
Actions logs; run it on the maintainer's machine with the two environment
variables exported (see SETUP.md step H):

    export GOOGLE_SHEET_ID=...
    export GOOGLE_SERVICE_ACCOUNT_JSON="$(cat service-account.json)"
    python scripts/draw.py [--dry-run]

Each participant's published REX count is converted to tickets with a
diminishing-returns formula: entry n is worth 2 ** (1 - ceil(n / 3)) tickets
(1, 1, 1, 1/2, 1/2, 1/2, 1/4, ...), an asymptotic cap of 6 tickets per email.
Quarantined REX do not count (Règlement §2, rétorsion).
"""

from __future__ import annotations

import hashlib
import math
import random
import sys

from sync import (
    REX_COLUMNS,
    compute_rex_id,
    fetch_quarantined_ids,
    fetch_rex_rows,
    get_spreadsheet,
    parse_row,
)

EMAIL_HEADER = "Adresse e-mail"


def ticket_value(n: int) -> float:
    """Ticket value of a participant's n-th published REX (1-indexed)."""
    return 2.0 ** (1 - math.ceil(n / 3))


def tickets_for(count: int) -> float:
    return sum(ticket_value(n) for n in range(1, count + 1))


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    sheet = get_spreadsheet()
    raw_rows = fetch_rex_rows(sheet)
    quarantined = fetch_quarantined_ids(sheet)

    counts: dict[str, int] = {}
    for raw in raw_rows:
        entry = parse_row(raw)
        if entry is None:
            continue
        if compute_rex_id(entry.timestamp_raw) in quarantined:
            continue
        email = raw.get(EMAIL_HEADER, "").strip().lower()
        if not email:
            continue
        counts[email] = counts.get(email, 0) + 1

    if not counts:
        print("No eligible participants (no published REX with an email).")
        sys.exit(0)

    emails = sorted(counts)
    weights = [tickets_for(counts[email]) for email in emails]

    print(f"{'participant (sha256:8)':>24} {'rex':>4} {'tickets':>8}")
    for email, weight in zip(emails, weights):
        digest = hashlib.sha256(email.encode()).hexdigest()[:8]
        print(f"{digest:>24} {counts[email]:>4} {weight:>8.3f}")
    print(f"total participants={len(emails)} total tickets={sum(weights):.3f}")

    if dry_run:
        print("Dry run: no draw performed.")
        return

    winner = random.choices(emails, weights=weights, k=1)[0]
    print(f"\nWinner: {winner}")
    print("Reminder: verify flight activity (trace CFD) before awarding the prize,")
    print("and purge the email column one month after the draw (Règlement §3).")


if __name__ == "__main__":
    main()
