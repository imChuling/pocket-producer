# Maintainer notes

The maintainer's own memo: facts about the system, how it is deployed, and
the constraints the evaluation runs under. It is not a contributing guide;
the repository does not take outside contributions. It exists because a
documentation branch opened from a five-week-old base cost a merge, and
because a deploy once replaced the whole Cloud Run environment and broke
uploads for twelve days.

## Where things are

- Paper-facing code: `backend/ranking/` and `research/`; artifacts in `artifacts/`.
- Session flow (the demo): `frontend/src/app/audiotool/`, `frontend/src/lib/audiotool/`.
- Capture and library: `backend/api/pipeline/`, `backend/agents/`, `frontend/src/app/capture/`.
- Deployment: `backend/deploy/`.

## Branching

- Always start from the current `origin/main`: `git fetch origin && git
  checkout -b <name> origin/main`. Never branch from a stale checkout.
- One topic per branch. Docs-only branches are fine; keep code out of
  them, and keep docs out of code branches when they can be separated.
- Rebase on `origin/main` before merging if main moved.
- `main` is pushed only from the maintainer's machine. Work from any other
  checkout goes to a branch and stops there. Never force-push.
- CI runs on pull requests into `main` and on `main` itself, not on a bare
  branch push; open a pull request to get a run.

## What "done" means for a code change

Run all of these locally and say so in the pull request:

```bash
cd backend && .venv/bin/ruff check . && .venv/bin/pytest -q
cd frontend && npx eslint src && npx tsc --noEmit && npx vitest run
python research/check_paper_numbers.py        # must stay 151 passed when docs/ismir2026 exists
```

Ranking behaviour is covered by tests that encode design decisions, not
just regressions. If a change makes one fail, the test is probably right;
read its name and docstring before editing it.

## Facts about the system that documents keep getting wrong

- `rules-v1` has seven signals (tempo, key, role gap, intent, tag novelty,
  tag overlap, recency) and is the default. The offline stand-in used in the
  paper is three of them (tempo, key, tag overlap) with frozen ratios.
- `fusion-5sig-v1` is user-selectable, not default. Its five signals are
  mean CLAP cosine, max CLAP cosine, tempo, key (always 0 online), tag Jaccard.
- `harmonic-fit-v1` is wired online: chroma is computed in `/session-embed`
  and at ingest (`representations.chroma`). All eight registered rankers
  serve without fallback given full inputs.
- MS-CLAP is one shared instance (`backend/ranking/adapters/shared.py`).
  Never construct `MsClapAdapter()` elsewhere.
- Rankers skip candidates they cannot score and raise when none remain;
  they never serve a zero-score, evidence-free proposal.
- Rate limits are per signed-in user. LLM-backed actions have a 30/day
  allowance per user (`POCKET_DAILY_LLM_QUOTA`).
- `/` redirects signed-in users to `/capture`; the Audiotool session flow is `/audiotool`, the last tab.
- The paper source (`docs/ismir2026/`) and `CHANGELOG.md` are gitignored on
  purpose. `check_paper_numbers.py` skips tex assertions when they are
  absent; do not "fix" that.
- Numbers in README, MODEL_CARD and VERIFICATION must match
  `artifacts/`. Do not round or restate a number without checking its JSON.

## Deployment

- Backend: only through `backend/deploy/deploy.sh`. It reads
  `deploy/cloudrun.env.yaml` and binds secrets explicitly. A bare
  `gcloud run deploy` drops configuration.
- `deploy.sh --config` re-applies env and scaling without a rebuild.
- Every `deploy.sh` build stores a 2 GB image in Artifact Registry
  (`cloud-run-source-deploy`), billed monthly. The repository has a cleanup
  policy (`deploy/artifact-cleanup-policy.json`: keep the 3 newest per
  service, delete anything older than 30 days); re-apply it with
  `gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy
  --location us-central1 --policy backend/deploy/artifact-cleanup-policy.json
  --no-dry-run` if the repository is ever recreated.
- Frontend: deploy by hand with `vercel --prod` from `frontend/` (the Vercel
  project is `pocketproducer`). Nothing deploys on push: the GitHub
  integration is not connected, so a green CI run on `main` says nothing
  about what pocketproducer.vercel.app is serving.
- After a backend deploy, check `/ready` and the logs for
  "CLAP warmup complete" and "role probe warmup complete".
- The backend scales to zero and bills per instance-second with CPU always
  allocated. Anything that hits it every few minutes keeps one instance alive
  around the clock (a tab polling `/api/notifications` every 30 s cost 201
  instance-hours in October 2026). Every browser poller goes through
  `frontend/src/lib/idle.ts` so hidden and idle tabs stay quiet; never add an
  uptime check or keep-warm cron without deciding to pay for a warm instance.
- Nothing but the maintainer's own machine deploys or touches Cloud Run,
  Vercel, Firebase, Mongo Atlas or Audiotool developer settings.

## Evaluation rules

- No human evaluation with external participants. The only human
  evaluation is the author's own pre-registered N-of-1 rating
  (`research/prereg_human_v1.md`).
- Pre-registered documents are frozen once data collection starts; record
  any later change in their deviations log, never silently.
- Negative results are kept and documented (`research/README.md`,
  supporting artifacts table).
