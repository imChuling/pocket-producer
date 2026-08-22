# Let's Build 2026 Submission Copy

Portal: developer.audiotool.com (login required). Deadline 23 Aug 2026, 6pm EST.
Four required materials: working app URL, demo video (2-5 min), README, source link.

## Form fields (paste-ready)

**App name**
Pocket Producer

**One-liner**
A session-aware retrieval instrument for unfinished music: it reads the
Audiotool project you have open, ranks your own fragments by whether they
could grow into that piece, and lets you preview, insert, and undo.

**Category**
Primary: Songstarter (also fits: Composition, Connect / DAW Integration)

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

Technical highlights:
- Real Nexus read AND write: session fingerprinting, sample upload, insert
  at playhead in one transaction, exact undo via an insert receipt
- OAuth tokens never leave the browser; the backend sees only the session
  fingerprint and candidate metadata
- Graceful degradation: if the model service is down, the rules ranker
  answers; the closed loop never depends on a remote model
- 316 automated tests across frontend (Vitest) and backend (pytest),
  including offline Nexus fixtures so CI needs no live account
- Reproducible research pipeline: versioned artifacts, a frozen split, and
  a 151-assertion consistency check tying every public number to its JSON

**Team**
Solo: Chuling Li (chuling.li.cs@gmail.com)

## Judging criteria mapping (for our own reference)

- Innovation (30%): compatibility-not-similarity framing; evidence-grounded
  proposals; honest uncertainty handling as a design principle
- Technical execution (25%): full Nexus read/write/undo loop, token
  isolation, fallback architecture, test coverage
- Musical value (25%): re-entering unfinished work is a real musician
  problem; suggestions come from the musician's own material
- User experience (20%): one primary action per state, preview before
  commit, undo always available, evidence chips instead of black-box scores

## Pre-submit checklist

- [ ] App loads in an incognito window; full loop works on a fresh profile
- [ ] Demo video public/unlisted and plays without login
- [ ] README top screen has the video link and quickstart
- [ ] Repo stays private; judge access path confirmed on the form
      (invite handle or comment-field note); repo free of secrets
- [ ] All four form links tested from the incognito window
- [ ] Screenshot the submitted form for the archive
