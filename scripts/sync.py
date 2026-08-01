"""Sync REX entries from the private Google Sheet into content/rex/.

Read-only on the sheet, desired-state on the filesystem: after a successful
run, content/rex/*.md (minus PROTECTED) exactly matches the published rows.
Both worksheets are fetched completely before any filesystem write; any
fetch or parse problem exits non-zero first, leaving the previous site
deployed untouched.

Log hygiene: this runs in a public repo whose Actions logs are world-readable.
Only counts, rex_ids and sheet HEADERS may be printed — never cell contents.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# gspread is imported lazily inside get_spreadsheet() so the offline test
# suite can import this module without the Google dependencies installed.

REX_WORKSHEET = "Réponses au formulaire 1"
MOD_WORKSHEET = "Réponses au formulaire 2"
CONTENT_DIR = Path(__file__).resolve().parent.parent / "content" / "rex"
PROTECTED = {"_index.md", "exemple.md"}

# Moderation form report link, shown in each REX footer. Empty until the
# moderation form exists (SETUP.md step B): the footer then shows the rex_id
# without a link.
REPORT_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSet36j_pft9KbgyV9Jikts3eZeAvBRLKenrGkeaBK1XU0Vk0Q/viewform"
)
REPORT_ENTRY_ID = "entry.1217368245"

TIMESTAMP_FMT = "%d/%m/%Y %H:%M:%S"  # French sheet locale
TZ = ZoneInfo("Europe/Paris")
SUMMARY_TRIGGER_LEN = 100

# Logical name -> exact sheet header (= form question text). Renaming a form
# question breaks this mapping; the sync then fails loudly listing both sides.
# The email and photo columns are deliberately absent: never read, never output.
REX_COLUMNS = {
    "timestamp": "Horodateur",
    "envie": "Qu'est-ce qui te faisait vraiment envie d'aller voler aujourd'hui ?",
    "plan": "Quel était le plan de vol ?",
    "flight_date": "Quand était prévu le vol ?",
    "factors_human": "Signaux faibles: Facteurs Humains",
    "factors_social": "Signaux faibles: Facteurs Sociaux",
    "factors_aero": "Signaux faibles: Facteurs Aérologiques & Environnement",
    "signals_detail": (
        "Précise concrètement comment les signaux cochés ci-dessus se sont "
        "manifestés et comment tu les as perçus sur le moment"
    ),
    "trigger": (
        'Quel a été l\'élément déclencheur EXACT qui t\'a fait dire "Non, '
        'je plie/je pose ou Je n\'y vais pas ?"'
    ),
    "hardest_factor": (
        "Parmi les éléments suivants, quel facteur a été le plus difficile "
        "à ignorer avant de renoncer ?"
    ),
    "earlier_decision": "Avec le recul, aurais-tu pu prendre cette décision plus tôt ?",
    "bilan": "Bilan personnel : Quelle leçon tires-tu de ce renoncement pour tes futurs vols ?",
    "decision": "Étais-tu seul(e) à prendre cette décision ?",
    "sentiment": (
        "Comment évalues-tu ton sentiment général après avoir pris cette "
        "décision de renoncement ?"
    ),
    "stress": (
        "Sur une échelle de 1 à 5, quel était ton niveau de stress ou de "
        "doute juste avant de prendre ta décision ?"
    ),
    "experience": "Comment décrirais-tu ton niveau d'expérience en vol libre ?",
    "confidence": (
        "Dans quelle mesure penses-tu que ce renoncement a renforcé ta "
        "confiance en tes capacités de jugement pour tes prochains vols ?"
    ),
}

MOD_COLUMNS = {
    "rex_id": "rex_id",
    "validated": "Validé",
}

TRUTHY = {"TRUE", "VRAI", "OUI", "1"}


@dataclass(frozen=True)
class RexEntry:
    timestamp_raw: str
    envie: str
    plan: str
    flight_date: str
    factors_human: str
    factors_social: str
    factors_aero: str
    signals_detail: str
    trigger: str
    hardest_factor: str
    earlier_decision: str
    bilan: str
    decision: str
    sentiment: str
    stress: str
    experience: str
    confidence: str


def get_spreadsheet():
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds).open_by_key(os.environ["GOOGLE_SHEET_ID"])


def compute_rex_id(timestamp_raw: str) -> str:
    return hashlib.sha256(timestamp_raw.encode()).hexdigest()[:10]


def split_checkboxes(cell: str) -> list[str]:
    """Split a Google Forms multi-select cell on ', ' at parenthesis depth 0.

    Checkbox labels contain commas inside parentheses, e.g.
    "Biais cognitifs (Envie de rentabiliser le trajet, rando, ...)".
    """
    items: list[str] = []
    depth = 0
    current: list[str] = []
    i = 0
    while i < len(cell):
        char = cell[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if depth == 0 and cell.startswith(", ", i):
            items.append("".join(current).strip())
            current = []
            i += 2
            continue
        current.append(char)
        i += 1
    items.append("".join(current).strip())
    return [item for item in items if item]


def rows_as_dicts(values: list[list[str]], expected_headers: set[str], worksheet: str) -> list[dict]:
    if not values:
        return []
    headers = [h.strip() for h in values[0]]
    missing = expected_headers - set(headers)
    if missing:
        print(f"Header mismatch in worksheet '{worksheet}'.", file=sys.stderr)
        print(f"Expected (missing): {sorted(missing)}", file=sys.stderr)
        print(f"Actual headers: {headers}", file=sys.stderr)
        sys.exit(1)
    rows = []
    for raw in values[1:]:
        padded = list(raw) + [""] * (len(headers) - len(raw))
        rows.append(dict(zip(headers, padded)))
    return rows


def fetch_rex_rows(sheet) -> list[dict]:
    values = sheet.worksheet(REX_WORKSHEET).get_all_values()
    return rows_as_dicts(values, set(REX_COLUMNS.values()), REX_WORKSHEET)


def quarantined_ids_from_values(values: list[list[str]]) -> set[str]:
    rows = rows_as_dicts(values, {MOD_COLUMNS["rex_id"]}, MOD_WORKSHEET)
    if not rows:
        return set()
    # The Validé column is hand-typed by the maintainer (not a form question),
    # so match it case-insensitively.
    headers = [h.strip() for h in values[0]]
    wanted = MOD_COLUMNS["validated"].casefold()
    validated_header = next((h for h in headers if h.casefold() == wanted), None)
    if validated_header is None:
        print(
            f"Missing '{MOD_COLUMNS['validated']}' column in worksheet "
            f"'{MOD_WORKSHEET}'. Actual headers: {headers}",
            file=sys.stderr,
        )
        sys.exit(1)
    quarantined = set()
    for row in rows:
        if str(row.get(validated_header, "")).strip().upper() in TRUTHY:
            quarantined.add(row[MOD_COLUMNS["rex_id"]].strip())
    return quarantined


def fetch_quarantined_ids(sheet) -> set[str]:
    try:
        worksheet = sheet.worksheet(MOD_WORKSHEET)
    except Exception:
        # Moderation form not created yet (SETUP.md step B): nothing quarantined.
        print(f"Worksheet '{MOD_WORKSHEET}' not found; no quarantine applied.")
        return set()
    return quarantined_ids_from_values(worksheet.get_all_values())


def _single_line(text: str) -> str:
    return " ".join(text.split())


def _block(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def parse_row(raw: dict) -> RexEntry | None:
    values = {logical: raw.get(header, "") for logical, header in REX_COLUMNS.items()}
    if not values["timestamp"].strip():
        return None
    if not any(str(value).strip() for logical, value in values.items() if logical != "timestamp"):
        return None
    return RexEntry(
        timestamp_raw=values["timestamp"].strip(),
        envie=_single_line(values["envie"]),
        plan=_single_line(values["plan"]),
        flight_date=_single_line(values["flight_date"]),
        factors_human=values["factors_human"].strip(),
        factors_social=values["factors_social"].strip(),
        factors_aero=values["factors_aero"].strip(),
        signals_detail=_single_line(values["signals_detail"]),
        trigger=_block(values["trigger"]),
        hardest_factor=_single_line(values["hardest_factor"]),
        earlier_decision=_single_line(values["earlier_decision"]),
        bilan=_block(values["bilan"]),
        decision=_single_line(values["decision"]),
        sentiment=_single_line(values["sentiment"]),
        stress=_single_line(values["stress"]),
        experience=_single_line(values["experience"]),
        confidence=_single_line(values["confidence"]),
    )


def parse_timestamp(timestamp_raw: str) -> datetime:
    return datetime.strptime(timestamp_raw, TIMESTAMP_FMT).replace(tzinfo=TZ)


def build_summary(entry: RexEntry) -> str:
    meta = " · ".join(part for part in (entry.experience, entry.decision) if part)
    trigger = _single_line(entry.trigger)
    if len(trigger) > SUMMARY_TRIGGER_LEN:
        trigger = trigger[:SUMMARY_TRIGGER_LEN].rstrip() + "…"
    if meta and trigger:
        return f"{meta} — « {trigger} »"
    if trigger:
        return f"« {trigger} »"
    return meta


def _bullet(label: str, value: str) -> str:
    return f"* {label} {value}\n" if value else ""


def render_markdown(entry: RexEntry) -> str:
    rex_id = compute_rex_id(entry.timestamp_raw)
    date = parse_timestamp(entry.timestamp_raw)
    title_date = entry.flight_date or date.strftime("%d/%m/%Y")

    front = "---\n"
    front += f"title: {json.dumps(f'Renoncement du {title_date}', ensure_ascii=False)}\n"
    front += f"date: {date.isoformat()}\n"
    summary = build_summary(entry)
    if summary:
        front += f"summary: {json.dumps(summary, ensure_ascii=False)}\n"
    front += "draft: false\n"
    front += "---\n"

    body = f"**Expérience :** {entry.experience or '—'} | **Décision :** {entry.decision or '—'}\n"

    context = ""
    context += _bullet("**Pourquoi voler ?**", entry.envie)
    context += _bullet("**Plan :**", entry.plan)
    context += _bullet("**Vol prévu le :**", entry.flight_date)
    if context:
        body += "\n### Le Contexte\n" + context

    signals = ""
    signals += _bullet("**Facteurs humains :**", ", ".join(split_checkboxes(entry.factors_human)))
    signals += _bullet("**Facteurs sociaux :**", ", ".join(split_checkboxes(entry.factors_social)))
    signals += _bullet(
        "**Facteurs aérologiques & environnement :**",
        ", ".join(split_checkboxes(entry.factors_aero)),
    )
    signals += _bullet("**Comment ils se sont manifestés :**", entry.signals_detail)
    if signals:
        body += "\n### Signaux Faibles\n" + signals

    if entry.trigger:
        body += "\n### Le déclencheur\n" + entry.trigger + "\n"

    if entry.bilan:
        body += "\n### Bilan\n" + entry.bilan + "\n"

    analysis = ""
    analysis += _bullet("**Sentiment :**", entry.sentiment)
    analysis += _bullet("**Facteur le plus difficile à ignorer :**", entry.hardest_factor)
    analysis += _bullet("**Décision possible plus tôt ?**", entry.earlier_decision)
    scores = []
    if entry.stress:
        scores.append(f"**Stress :** {entry.stress}/5")
    if entry.confidence:
        scores.append(f"**Confiance renforcée :** {entry.confidence}/5")
    if scores:
        analysis += "* " + " | ".join(scores) + "\n"
    if analysis:
        body += "\n### Analyse\n" + analysis

    body += "\n---\n"
    if REPORT_FORM_URL and REPORT_ENTRY_ID:
        report_url = f"{REPORT_FORM_URL}?usp=pp_url&{REPORT_ENTRY_ID}={rex_id}"
        body += f"*Identifiant : `{rex_id}` — [Signaler ce REX]({report_url})*\n"
    else:
        body += f"*Identifiant : `{rex_id}`*\n"

    return front + body


def sync_content_dir(desired: dict[str, str], content_dir: Path = CONTENT_DIR) -> tuple[int, int]:
    """Make content_dir match desired ({rex_id: markdown}). Returns (written, removed)."""
    written = removed = 0
    desired_names = {f"{rex_id}.md" for rex_id in desired}
    for path in sorted(content_dir.glob("*.md")):
        if path.name in PROTECTED or path.name in desired_names:
            continue
        path.unlink()
        removed += 1
    for rex_id, markdown in sorted(desired.items()):
        path = content_dir / f"{rex_id}.md"
        if not path.exists() or path.read_text(encoding="utf-8") != markdown:
            path.write_text(markdown, encoding="utf-8")
            written += 1
    return written, removed


def main() -> None:
    for var in ("GOOGLE_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_JSON"):
        if not os.environ.get(var):
            print(f"Missing environment variable {var}; see SETUP.md.", file=sys.stderr)
            sys.exit(1)

    sheet = get_spreadsheet()
    raw_rows = fetch_rex_rows(sheet)
    quarantined = fetch_quarantined_ids(sheet)

    entries = [entry for raw in raw_rows if (entry := parse_row(raw))]
    ids = [compute_rex_id(entry.timestamp_raw) for entry in entries]
    if len(ids) != len(set(ids)):
        print(
            "rex_id collision (two submissions in the same second). "
            "Nudge the Horodateur cell of one NOT-yet-published row by one second.",
            file=sys.stderr,
        )
        sys.exit(1)

    desired = {
        rex_id: render_markdown(entry)
        for rex_id, entry in zip(ids, entries)
        if rex_id not in quarantined
    }
    written, removed = sync_content_dir(desired)
    print(
        f"published={len(desired)} written={written} removed={removed} "
        f"quarantined={len(quarantined & set(ids))} skipped_blank={len(raw_rows) - len(entries)}"
    )


if __name__ == "__main__":
    main()
