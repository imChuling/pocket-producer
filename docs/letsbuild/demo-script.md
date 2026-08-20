# Let's Build 2026 Demo Script

Target length: 2:30 (official allowance 2-5 min; shorter and dense beats long).
One continuous story: every shot proves one claim. Record raw one-take
evidence footage first, then cut the polished version from it.

Recording setup:
- 1920x1080, macOS screen recording (Cmd+Shift+5), system audio on for previews
- One browser window: Pocket Producer left, Audiotool right (or tab-switch)
- Use one prepared session throughout: a real unfinished Audiotool project
  with a few tracks (drums + something), tempo set, 10+ fragments in the library
- Closed captions in the edit (also reusable for the ISMIR video later)

## Shot list

**00:00-00:12 — Hook (voiceover over Audiotool project)**
> "This is a track I never finished. I have dozens of my own loops and
> sketches somewhere in my library. The problem isn't making more sounds,
> it's knowing which of them could grow into *this*."

**00:12-00:30 — Connect and read (claim: real Nexus read)**
- Open pocketproducer.vercel.app/audiotool, click Connect Audiotool
- OAuth consent appears, approve
- Session summary fills in: tempo, track roles, playhead
> "Pocket Producer connects through Audiotool's Nexus SDK and reads the
> open session: tempo, what roles are already covered, where I am."

**00:30-00:50 — Fingerprint honesty (claim: transparent context)**
- Point at the session summary panel; edit the text intent field
> "It shows exactly what it read, nothing it didn't. I can add intent in
> my own words: say, 'dark bass to sit under these drums'."

**00:50-01:20 — Top 3 with evidence (claim: grounded ranking, not magic)**
- Ranked candidates appear; hover the evidence chips
> "It ranks my own fragments by whether they could belong to this piece.
> Every suggestion carries its evidence: tempo proximity, role it fills,
> tag overlap. These come from the ranker's actual features, never
> generated prose. The default ranker is a hand-tuned rules baseline;
> a learned fusion is selectable, because our offline evaluation says
> its advantage depends on how you construct the labels, and we'd rather
> show you that honestly than pretend the model is always right."

**01:20-01:45 — Preview, insert (claim: real Nexus write)**
- Preview a candidate (audio audible), click Insert
- Switch to Audiotool: the sample is on the timeline at the playhead
> "Preview, then insert. One Nexus transaction, at the playhead,
> into the real project."

**01:45-01:58 — Undo (claim: reversible, agency preserved)**
- Click Undo in Pocket Producer; entity disappears in Audiotool
> "And undo restores the exact prior state. The system proposes;
> I decide."

**01:58-02:18 — The research beat (claim: model is not decoration)**
- Cut to the README results table / sensitivity figure
> "Under the hood this is a measured system: six baselines, a frozen
> held-out split, and a sensitivity analysis that tells us when the
> learned ranker helps and when it doesn't. That's why the fusion is
> user-selectable instead of silently in charge."

**02:18-02:30 — Close**
- Back to the session, suggestions visible
> "Pocket Producer is creative memory, not autopilot. It helps you
> re-enter unfinished music, and every action it takes, you can undo."

## Rules for the edit

- No shot may claim something the raw footage doesn't show
- Keep the OAuth screen visible for a beat (judges look for real integration)
- Show the Audiotool timeline before AND after insert, and after undo
- No fabricated UI states; if a state is slow, cut the wait, not the state
- Keep the raw one-take file; archive under docs/letsbuild/evidence/
