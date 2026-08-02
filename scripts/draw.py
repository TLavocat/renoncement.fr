"""Annual lottery draw (Règlement §3).

Log-safe by construction: email addresses are NEVER printed — the winner is
announced as a sheet row number (open the spreadsheet at that row to read the
address) plus a truncated hash. This makes the script safe to run either
locally or from the manual "Lottery draw" GitHub Action, even though Actions
logs of a public repo are world-readable.

    python scripts/draw.py --dry-run   # ticket table only, no draw
    python scripts/draw.py             # the real draw

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
from dataclasses import dataclass

from sync import (
    REX_WORKSHEET,
    compute_rex_id,
    fetch_quarantined_ids,
    fetch_rex_rows,
    get_spreadsheet,
    parse_row,
)

EMAIL_HEADER = "Adresse e-mail"
FIRST_DATA_ROW = 2  # sheet row 1 is the header


def ticket_value(n: int) -> float:
    """Ticket value of a participant's n-th published REX (1-indexed)."""
    return 2.0 ** (1 - math.ceil(n / 3))


def tickets_for(count: int) -> float:
    return sum(ticket_value(n) for n in range(1, count + 1))


@dataclass
class Participant:
    email_hash: str  # sha256 hex, truncated — safe to print
    first_row: int   # sheet row number of the participant's first REX
    count: int = 0


def eligible_participants(raw_rows: list[dict], quarantined: set[str]) -> dict[str, Participant]:
    """Group published REX rows by email. Keys are emails (never printed);
    Participant carries only log-safe fields."""
    participants: dict[str, Participant] = {}
    for index, raw in enumerate(raw_rows):
        entry = parse_row(raw)
        if entry is None:
            continue
        if compute_rex_id(entry.timestamp_raw) in quarantined:
            continue
        email = raw.get(EMAIL_HEADER, "").strip().lower()
        if not email:
            continue
        if email not in participants:
            participants[email] = Participant(
                email_hash=hashlib.sha256(email.encode()).hexdigest()[:8],
                first_row=FIRST_DATA_ROW + index,
            )
        participants[email].count += 1
    return participants


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    sheet = get_spreadsheet()
    raw_rows = fetch_rex_rows(sheet)
    quarantined = fetch_quarantined_ids(sheet)
    participants = eligible_participants(raw_rows, quarantined)

    if not participants:
        print("No eligible participants (no published REX with an email).")
        sys.exit(0)

    emails = sorted(participants)
    weights = [tickets_for(participants[email].count) for email in emails]

    print(f"{'participant (sha256:8)':>24} {'rex':>4} {'tickets':>8}")
    for email, weight in zip(emails, weights):
        participant = participants[email]
        print(f"{participant.email_hash:>24} {participant.count:>4} {weight:>8.3f}")
    print(f"total participants={len(emails)} total tickets={sum(weights):.3f}")

    if dry_run:
        print("Dry run: no draw performed.")
        return

    winner = participants[random.choices(emails, weights=weights, k=1)[0]]
    print(
        f"\nWinner: participant {winner.email_hash} — "
        f"open the spreadsheet, worksheet '{REX_WORKSHEET}', ROW {winner.first_row} "
        f"(their first REX) and read the email address there."
    )
    print("Reminder: verify flight activity (trace CFD) before awarding the prize,")
    print("and purge the email column one month after the draw (Règlement §3).")


if __name__ == "__main__":
    main()
