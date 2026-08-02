# renoncement.fr

Static community site where paraglider pilots anonymously share REX
("retours d'expérience") about deciding **not** to fly. Live at
[renoncement.fr](https://renoncement.fr).

## Architecture

100% static, zero-maintenance, self-feeding:

```
Google Forms → private Google Sheet → GitHub Actions (scripts/sync.py)
            → Hugo (PaperMod) → GitHub Pages
```

- `scripts/sync.py` runs hourly in CI: it reads the private response sheet via
  a read-only service account and regenerates `content/rex/*.md` as a pure
  desired state (a validated moderation report = the file is absent). It never
  reads the email column and never prints row contents (public Actions logs).
- `.github/workflows/sync-and-deploy.yml` is a single workflow (test → sync →
  commit → build → deploy) because pushes made with `GITHUB_TOKEN` cannot
  trigger other workflows.
- Comments are GitHub Discussions via giscus. No cookies, no tracking.
- `scripts/draw.py` is the annual lottery draw, run via the manual "Lottery
  draw" workflow. Log-safe by construction: it announces the winner as a sheet
  row number + hash and never prints an email address.

## Development

```bash
git clone --recurse-submodules git@github.com:TLavocat/renoncement.fr.git
hugo server            # Hugo >= 0.164.0 extended
python -m pytest tests/  # offline, no Google credentials needed
```

Site content is French; code, commits and identifiers are English.

## Activation

All manual steps (forms, Google Cloud service account, GitHub secrets, Pages,
DNS, giscus) are documented click-by-click in [SETUP.md](SETUP.md).
