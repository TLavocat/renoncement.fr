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

- **Stateless content**: the Google Sheet is the source of truth. Every hour,
  `scripts/sync.py` reads it via a read-only service account and regenerates
  `content/rex/*.md` in the CI workspace (a validated moderation report = the
  file is absent); Hugo builds and deploys the result. Nothing is committed
  back — REX never enter git history, and the workflow has zero write access
  to the repo. The script never reads the email column and never prints row
  contents (public Actions logs).
- If the repo sees no commit for 60 days, GitHub emails a warning and pauses
  the hourly schedule; the site keeps serving its last build, and one click
  (or any commit) resumes syncing with no data lost.
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
