# Let's Build 2026 Submission Copy

Portal: per Discord staff guidance (2026-08-20), submission is via a Google Form
posted in the Let's Build Discord -- find the form link in the Discord submission
thread before submitting (the FAQ's mention of a developer-hub portal appears
outdated). Deadline: Discord guidance said 23 Aug 2026 6pm EST, but the
official site (checked 2026-08-23) says submissions are open until
28 Sep 2026 -- VERIFY in Discord which applies before assuming either;
submitting by the earlier date is always safe.
Four required materials: working app URL, demo video (2-5 min), README, source link.

## Form fields (paste-ready)

**App name**
Pocket Producer

**One-liner**
A session-aware retrieval instrument for unfinished music: it reads the
Audiotool project you have open, ranks your own fragments by whether they
could grow into that piece, and lets you preview, insert, and undo.

**Category**
Primary: Creation ("instruments, sequencers, and tools that shape how music
is made"). Judges tag categories themselves and one project can win in
several; if the form asks, Creation is ours.

**App URL**
https://pocketproducer.vercel.app/audiotool

**Demo video**
[YouTube link — fill in after upload]

**Source code**
https://github.com/imChuling/pocket-producer
(private; judge access granted on request — invite any GitHub handle the
jury names, or note in the form's comment field that access is available)

**Description (longer field, if the form has one)**

Re-opening a half-finished track is the hardest moment in amateur music
making. You have dozens of your own loops and sketches, but no way to ask
"which of these could grow into the piece I have open right now?"

Pocket Producer answers that question inside the real workflow. Through the
Nexus SDK it reads the open session (tempo, track roles, playhead) and a
short statement of intent in the musician's own words. It then ranks the
musician's private fragment library by session compatibility and returns
three suggestions. Every suggestion carries structured evidence drawn from
the ranker's own features ("121 BPM is close to the project's 120 BPM",
"adds a role this session doesn't have yet"), never generated prose. A
click previews the fragment; another inserts it at the playhead through a
single Nexus transaction; undo restores the exact prior entity set,
validated against the official Nexus document validator.

The ranking is a measured system, not decoration. The default is a
hand-tuned rules ranker over interpretable signals; a learned five-signal
fusion is user-selectable. We evaluated both offline on the Freesound Loop
Dataset against six baseline families with a frozen held-out split, and
found the learned fusion's advantage depends on how the weak-supervision
labels are constructed. So the product tells the truth about that: the
model proposes under uncertainty, the musician stays in charge, and every
recommendation is inspectable and reversible. The same evaluation is
submitted to ISMIR 2026 as a Late-Breaking/Demo paper.

First run tip for judges: a fresh account starts with an empty library.
Connect Audiotool and click "Import samples to library" on any of your
projects — your own samples become an analyzed, rankable fragment
library in under a minute, and the full suggest → preview → insert →
undo loop is live from there.

Technical highlights:
- Real Nexus read AND write: session fingerprinting, sample upload, insert
  at playhead in one transaction, exact undo via an insert receipt
- We found and patched a Nexus SDK 0.0.17 bug during development:
  insertSample crashes in any minified production build, because an
  internal check compares protobuf classes by constructor name and
  minification collapses all class names. Our one-line fix (compare
  typeName instead) ships as a pnpm patch in the repo, with the full
  root-cause analysis — happy to upstream it as an issue/PR
- Your Audiotool history becomes searchable memory: one click imports an
  existing project's samples into the fragment library through the same
  Nexus download API, so old work can be recommended into new sessions
- OAuth tokens never leave the browser; the backend sees only the session
  fingerprint and candidate metadata
- Graceful degradation: if the model service is down, the rules ranker
  answers; the closed loop never depends on a remote model
- 322 automated tests across frontend (Vitest) and backend (pytest),
  including offline Nexus fixtures so CI needs no live account
- Reproducible research pipeline: versioned artifacts, a frozen split, and
  a 151-assertion consistency check tying every public number to its JSON

**Team**
Solo: Chuling Li (chuling.li.cs@gmail.com)

## What the contest rewards (verified 2026-08-23 from audiotool.com/LetsBuild)

Official categories: Creation / Games / Listening / Education; judges tag
submissions and one project can win in several. No published criteria
weights. What the site and press releases emphasize, and how we map:

- Built with the Nexus SDK (the series' stated axis): we are the deep
  case — session read, transactional write, exact undo, plus a root-caused
  SDK patch shipped in the repo
- Jury is largely musicians and educators (Berklee, NYU, Fraunhofer IDMT,
  working producers), not ML researchers: the demo leads with the musician
  story and working features; research appears only as a trust beat
- "AI-powered music software" / "anyone can build": AI that proposes with
  evidence while the musician stays in charge; import makes onboarding
  instant from any Audiotool account
- Working, shipped tools over concepts: live URL, 322 tests, reversible
  writes against real projects

## Pre-submit checklist

- [ ] App loads in an incognito window; full loop works on a fresh profile
- [ ] Demo video public/unlisted and plays without login
- [ ] README top screen has the video link and quickstart
- [ ] Repo stays private; judge access path confirmed on the form
      (invite handle or comment-field note); repo free of secrets
- [ ] All four form links tested from the incognito window
- [ ] Screenshot the submitted form for the archive
