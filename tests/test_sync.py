"""Offline tests for scripts/sync.py and scripts/draw.py — no network, no Google deps."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

import sync
from draw import EMAIL_HEADERS, eligible_participants, ticket_value, tickets_for

LEGACY_EMAIL_HEADER = EMAIL_HEADERS[1]
OPTIONAL_EMAIL_HEADER = EMAIL_HEADERS[0]

# Fixture values mirror the real sheet's headers and answer style.
REAL_HUMAN_FACTORS = (
    "Biais cognitifs (Envie de rentabiliser le trajet, rando, excès de confiance...)"
)
REAL_AERO_FACTORS = (
    "Contradiction modèles / réalité (Le vent ou les nuages ne sont pas ceux prévus), "
    "Relevés directs (Balises qui forcissent, mauvaise orientation), "
    "Observation du trafic (Trop de sketchs au déco, ailes qui reculent ou se font secouer en l'air)"
)


def make_raw(**overrides):
    values = {
        "timestamp": "31/07/2026 13:29:39",
        "envie": "ma première transition chartreuse belledonne",
        "plan": "déco pravouta, aulp, st genis, chamrousse puis retour lumbin",
        "flight_date": "30/07/2026",
        "factors_human": REAL_HUMAN_FACTORS,
        "factors_social": "Bruit informationnel (Canal WhatsApp qui s'enflamme, fausses bonnes infos)",
        "factors_aero": REAL_AERO_FACTORS,
        "signals_detail": "la brise de pente était si forte qu'elle ne pouvait qu'être renforcée",
        "trigger": "le déco + vol du gars de pravouta",
        "hardest_factor": "L'investissement logistique et temps déjà consenti",
        "earlier_decision": "Non, la décision devait se prendre au déco.",
        "bilan": "je ne regrette pas d'être allé voir",
        "decision": "Décision collective",
        "sentiment": "Satisfait(e) d'avoir fait le bon choix",
        "stress": "1",
        "experience": "Débutant (en progression)",
        "confidence": "4",
    }
    values.update(overrides)
    return {sync.REX_COLUMNS[logical]: value for logical, value in values.items()}


class TestSplitCheckboxes:
    def test_commas_inside_parentheses_do_not_split(self):
        assert sync.split_checkboxes(REAL_HUMAN_FACTORS) == [REAL_HUMAN_FACTORS]

    def test_real_multi_select_cell(self):
        items = sync.split_checkboxes(REAL_AERO_FACTORS)
        assert len(items) == 3
        assert items[0] == (
            "Contradiction modèles / réalité (Le vent ou les nuages ne sont pas ceux prévus)"
        )
        assert items[2].startswith("Observation du trafic")

    def test_empty_cell(self):
        assert sync.split_checkboxes("") == []


class TestRexId:
    def test_deterministic_and_short(self):
        rex_id = sync.compute_rex_id("31/07/2026 13:29:39")
        assert rex_id == sync.compute_rex_id("31/07/2026 13:29:39")
        assert len(rex_id) == 10
        assert rex_id != sync.compute_rex_id("31/07/2026 13:29:40")


class TestParseRow:
    def test_blank_row_skipped(self):
        raw = {header: "" for header in sync.REX_COLUMNS.values()}
        assert sync.parse_row(raw) is None

    def test_timestamp_only_row_skipped(self):
        raw = {header: "" for header in sync.REX_COLUMNS.values()}
        raw["Horodateur"] = "31/07/2026 13:29:39"
        assert sync.parse_row(raw) is None

    def test_accents_preserved(self):
        entry = sync.parse_row(make_raw())
        assert entry.envie == "ma première transition chartreuse belledonne"
        assert entry.decision == "Décision collective"

    def test_multiline_bullet_field_collapsed(self):
        entry = sync.parse_row(make_raw(signals_detail="ligne un\nligne deux"))
        assert entry.signals_detail == "ligne un ligne deux"

    def test_multiline_block_field_kept(self):
        entry = sync.parse_row(make_raw(bilan="ligne un\r\nligne deux"))
        assert entry.bilan == "ligne un\nligne deux"


class TestDates:
    def test_summer_timestamp_gets_cest_offset(self):
        markdown = sync.render_markdown(sync.parse_row(make_raw()))
        assert "date: 2026-07-31T13:29:39+02:00\n" in markdown

    def test_winter_timestamp_gets_cet_offset(self):
        raw = make_raw(timestamp="15/01/2026 10:00:00")
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert "date: 2026-01-15T10:00:00+01:00\n" in markdown

    def test_bad_timestamp_fails_loudly(self):
        raw = make_raw(timestamp="2026-07-31 13:29:39")
        with pytest.raises(ValueError):
            sync.render_markdown(sync.parse_row(raw))


class TestRenderMarkdown:
    def test_byte_exact_output(self, monkeypatch):
        monkeypatch.setattr(sync, "REPORT_FORM_URL", "")
        monkeypatch.setattr(sync, "REPORT_ENTRY_ID", "")
        entry = sync.parse_row(make_raw())
        rex_id = sync.compute_rex_id(entry.timestamp_raw)
        expected = f"""---
title: "Renoncement du 30/07/2026"
date: 2026-07-31T13:29:39+02:00
summary: "Débutant (en progression) · Décision collective — « le déco + vol du gars de pravouta »"
draft: false
---
**Expérience :** Débutant (en progression) | **Décision :** Décision collective

### Le Contexte
* **Pourquoi voler ?** ma première transition chartreuse belledonne
* **Plan :** déco pravouta, aulp, st genis, chamrousse puis retour lumbin
* **Vol prévu le :** 30/07/2026

### Signaux Faibles
* **Facteurs humains :** {REAL_HUMAN_FACTORS}
* **Facteurs sociaux :** Bruit informationnel (Canal WhatsApp qui s'enflamme, fausses bonnes infos)
* **Facteurs aérologiques & environnement :** {REAL_AERO_FACTORS}
* **Comment ils se sont manifestés :** la brise de pente était si forte qu'elle ne pouvait qu'être renforcée

### Le déclencheur
le déco + vol du gars de pravouta

### Bilan
je ne regrette pas d'être allé voir

### Analyse
* **Sentiment :** Satisfait(e) d'avoir fait le bon choix
* **Facteur le plus difficile à ignorer :** L'investissement logistique et temps déjà consenti
* **Décision possible plus tôt ?** Non, la décision devait se prendre au déco.
* **Stress :** 1/5 | **Confiance renforcée :** 4/5

---
*Identifiant : `{rex_id}`*

{sync.LICENSE_LINE}
"""
        assert sync.render_markdown(entry) == expected

    def test_render_is_deterministic(self):
        entry = sync.parse_row(make_raw())
        assert sync.render_markdown(entry) == sync.render_markdown(entry)

    def test_html_injection_stays_inert_text(self):
        raw = make_raw(bilan='<script>alert("x")</script>')
        markdown = sync.render_markdown(sync.parse_row(raw))
        # The script tag stays verbatim markdown text; goldmark (unsafe=false)
        # strips raw HTML at render time, so it never reaches the page as HTML.
        assert '<script>alert("x")</script>' in markdown

    def test_quotes_in_summary_are_escaped(self):
        raw = make_raw(trigger='il a dit "non"')
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert 'summary: "Débutant (en progression) · Décision collective — « il a dit \\"non\\" »"\n' in markdown

    def test_long_trigger_truncated_in_summary(self):
        raw = make_raw(trigger="x" * 200)
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert "…" in markdown.split("summary:")[1].split("\n")[0]

    def test_footer_without_report_form(self, monkeypatch):
        monkeypatch.setattr(sync, "REPORT_FORM_URL", "")
        monkeypatch.setattr(sync, "REPORT_ENTRY_ID", "")
        entry = sync.parse_row(make_raw())
        rex_id = sync.compute_rex_id(entry.timestamp_raw)
        markdown = sync.render_markdown(entry)
        assert f"*Identifiant : `{rex_id}`*\n" in markdown
        assert markdown.endswith(sync.LICENSE_LINE + "\n")
        assert "Signaler" not in markdown

    def test_footer_with_report_form(self, monkeypatch):
        monkeypatch.setattr(sync, "REPORT_FORM_URL", "https://forms.example/viewform")
        monkeypatch.setattr(sync, "REPORT_ENTRY_ID", "entry.123")
        entry = sync.parse_row(make_raw())
        rex_id = sync.compute_rex_id(entry.timestamp_raw)
        markdown = sync.render_markdown(entry)
        assert (
            f"[Signaler ce REX](https://forms.example/viewform?usp=pp_url&entry.123={rex_id})"
            in markdown
        )

    def test_empty_optional_fields_omit_bullets(self):
        raw = make_raw(envie="", factors_social="", stress="")
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert "Pourquoi voler" not in markdown
        assert "Facteurs sociaux" not in markdown
        assert "Stress" not in markdown
        assert "**Confiance renforcée :** 4/5" in markdown

    def test_no_emojis_in_output(self):
        markdown = sync.render_markdown(sync.parse_row(make_raw()))
        assert all(ord(char) < 0x1F000 for char in markdown)


class TestSyncContentDir:
    def test_desired_state(self, tmp_path):
        (tmp_path / "_index.md").write_text("index", encoding="utf-8")
        (tmp_path / "exemple.md").write_text("exemple", encoding="utf-8")
        (tmp_path / "stale00001.md").write_text("old", encoding="utf-8")
        desired = {"aaaaaaaaaa": "content a", "bbbbbbbbbb": "content b"}

        written, removed = sync.sync_content_dir(desired, tmp_path)

        assert (written, removed) == (2, 1)
        names = {path.name for path in tmp_path.glob("*.md")}
        assert names == {"_index.md", "exemple.md", "aaaaaaaaaa.md", "bbbbbbbbbb.md"}
        assert (tmp_path / "_index.md").read_text(encoding="utf-8") == "index"

    def test_quarantined_id_removed(self, tmp_path):
        (tmp_path / "quarantine1.md").write_text("bad", encoding="utf-8")
        written, removed = sync.sync_content_dir({}, tmp_path)
        assert (written, removed) == (0, 1)
        assert list(tmp_path.glob("*.md")) == []

    def test_idempotent_second_run(self, tmp_path):
        desired = {"aaaaaaaaaa": "content a"}
        sync.sync_content_dir(desired, tmp_path)
        before = (tmp_path / "aaaaaaaaaa.md").stat().st_mtime_ns
        written, removed = sync.sync_content_dir(desired, tmp_path)
        assert (written, removed) == (0, 0)
        assert (tmp_path / "aaaaaaaaaa.md").stat().st_mtime_ns == before


class TestHeaderValidation:
    def test_missing_header_exits_listing_both(self, capsys):
        values = [["Horodateur", "Autre question"], ["x", "y"]]
        with pytest.raises(SystemExit):
            sync.rows_as_dicts(values, set(sync.REX_COLUMNS.values()), "test")
        err = capsys.readouterr().err
        assert "Header mismatch" in err
        assert "Quel était le plan de vol ?" in err

    def test_extra_columns_are_fine(self):
        headers = list(sync.REX_COLUMNS.values()) + ["Adresse e-mail", "Colonne photo"]
        values = [headers, [""] * len(headers)]
        rows = sync.rows_as_dicts(values, set(sync.REX_COLUMNS.values()), "test")
        assert len(rows) == 1

    def test_short_rows_padded(self):
        headers = list(sync.REX_COLUMNS.values())
        values = [headers, ["31/07/2026 13:29:39"]]
        rows = sync.rows_as_dicts(values, set(sync.REX_COLUMNS.values()), "test")
        assert rows[0]["Quel était le plan de vol ?"] == ""


class TestQuarantine:
    HEADERS = ["Horodateur", "rex_id", "pourquoi vous le signalez ?", "validé"]

    def test_lowercase_valide_header_accepted(self):
        values = [
            self.HEADERS,
            ["01/08/2026 10:00:00", "aaaaaaaaaa", "spam", "TRUE"],
            ["01/08/2026 10:01:00", "bbbbbbbbbb", "haine", ""],
        ]
        assert sync.quarantined_ids_from_values(values) == {"aaaaaaaaaa"}

    def test_vrai_and_checkbox_true_are_truthy(self):
        values = [
            ["rex_id", "Validé"],
            ["aaaaaaaaaa", "VRAI"],
            ["bbbbbbbbbb", "FALSE"],
            ["cccccccccc", "OUI"],
        ]
        assert sync.quarantined_ids_from_values(values) == {"aaaaaaaaaa", "cccccccccc"}

    def test_missing_valide_column_fails_loudly(self, capsys):
        values = [["rex_id"], ["aaaaaaaaaa"]]
        with pytest.raises(SystemExit):
            sync.quarantined_ids_from_values(values)
        assert "Validé" in capsys.readouterr().err

    def test_empty_tab_means_no_quarantine(self):
        assert sync.quarantined_ids_from_values([]) == set()
        assert sync.quarantined_ids_from_values([["rex_id", "Validé"]]) == set()


class TestTickets:
    def test_ticket_values_follow_geometric_tranches(self):
        assert [ticket_value(n) for n in range(1, 10)] == [
            1, 1, 1, 0.5, 0.5, 0.5, 0.25, 0.25, 0.25,
        ]

    def test_totals(self):
        assert tickets_for(1) == 1
        assert tickets_for(3) == 3
        assert tickets_for(6) == 4.5
        assert tickets_for(9) == 5.25

    def test_asymptotic_cap_of_six(self):
        # The series converges to 6; float rounding may land exactly on it.
        assert 5.99 < tickets_for(300) <= 6


class TestEligibleParticipants:
    def rows(self):
        return [
            {**make_raw(timestamp="01/06/2026 10:00:00"), LEGACY_EMAIL_HEADER: "alice@example.org"},
            {**make_raw(timestamp="02/06/2026 10:00:00"), LEGACY_EMAIL_HEADER: "Alice@Example.org"},
            {**make_raw(timestamp="03/06/2026 10:00:00"), LEGACY_EMAIL_HEADER: "bob@example.org"},
            {**make_raw(timestamp="04/06/2026 10:00:00"), LEGACY_EMAIL_HEADER: ""},
        ]

    def test_grouping_is_email_case_insensitive(self):
        participants = eligible_participants(self.rows(), set())
        assert participants["alice@example.org"].count == 2
        assert participants["bob@example.org"].count == 1

    def test_rows_without_email_are_skipped(self):
        participants = eligible_participants(self.rows(), set())
        assert len(participants) == 2

    def test_first_row_is_sheet_row_number(self):
        participants = eligible_participants(self.rows(), set())
        assert participants["alice@example.org"].first_row == 2
        assert participants["bob@example.org"].first_row == 4

    def test_quarantined_rex_do_not_count(self):
        quarantined = {sync.compute_rex_id("03/06/2026 10:00:00")}
        participants = eligible_participants(self.rows(), quarantined)
        assert "bob@example.org" not in participants

    def test_printable_fields_never_contain_the_email(self):
        participant = eligible_participants(self.rows(), set())["alice@example.org"]
        assert "alice" not in participant.email_hash
        assert len(participant.email_hash) == 8

    def test_optional_email_column_takes_priority_over_legacy(self):
        rows = [
            {
                **make_raw(timestamp="05/06/2026 10:00:00"),
                OPTIONAL_EMAIL_HEADER: "carol@example.org",
                LEGACY_EMAIL_HEADER: "stale@example.org",
            },
            {**make_raw(timestamp="06/06/2026 10:00:00"), OPTIONAL_EMAIL_HEADER: "dave@example.org"},
        ]
        participants = eligible_participants(rows, set())
        assert set(participants) == {"carol@example.org", "dave@example.org"}
