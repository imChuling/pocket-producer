# Let's Build 2026 Demo Script

Target length: ~3:30 (official allowance 2-5 min). One continuous story in
three acts: what the library is (four surfaces), how it meets Audiotool
(the integration), why you can trust it (honest uncertainty). Record raw
one-take evidence footage first, then cut the polished version from it.

Slide references point to `media/letsbuild-deck.html` (open in browser,
arrow keys to navigate). App shots are live footage of
pocketproducer.vercel.app. Alternate deck → app → deck so every claim is
immediately proven on screen.

Recording setup:
- 1920x1080, macOS screen recording (Cmd+Shift+5), system audio ON for previews
- Two browser windows ready: Pocket Producer and Audiotool (the same project
  open in both), plus the deck in a third tab
- Prepared state: an unfinished Audiotool project with 2-3 audio tracks and
  tempo set; 15+ fragments already in the library; one project (e.g. "Fancy
  Arrow") NOT yet imported so the import flow can run live
- Closed captions in the edit (reusable for the ISMIR video later)

## Act 1 — The library (0:00-1:20)

**00:00-00:12 — Hook** · deck slides 1-2, then cut to Audiotool project
> "This is a track I never finished. I have dozens of my own loops and
> sketches. The problem isn't making more sounds — it's knowing which of
> them could grow into *this*. Pocket Producer answers that question."

**00:12-00:22 — Four surfaces** · deck slide 3
> "It's one fragment library with four surfaces: Capture everything,
> Projects that assemble themselves, a DNA profile of how you create,
> and a two-way Audiotool workflow."

**00:22-00:45 — Capture** · live app: /  (Capture page)
- Show the record button, then scroll the fragment cards; hover one card's
  tags and AI suggestion; open a comment thread briefly
> "Capture takes anything: tap to record, type a lyric, drop an audio
> file, or import a whole Audiotool project. Every input becomes a
> fragment — key, tempo, instruments, emotions, themes, and one concrete
> suggestion for where it could go next. Not a folder of files: a library
> that knows what's in it."

**00:45-01:05 — Projects** · live app: /projects, open "Cold Shadow Language"
- Show the rescue score, connection reasons, next action; point at
  "same song candidate" chips
> "You never file anything. Agents group related fragments into projects
> and say *why*: same-song candidates, shared themes, similar emotion.
> Each project gets a rescue score — how alive it still is — and one
> concrete next action, with real keys and tempos, not vibes."

**01:05-01:20 — DNA** · live app: /dna, slow scroll
> "The same library, turned inward. My creative archetype, emotion flow,
> sound palette, and when ideas actually happen — computed from what I
> made, not what I claim I make."

## Act 2 — The Audiotool integration (1:20-2:50)

**01:20-01:30 — Architecture beat** · deck slide 7 (Tour · Audiotool)
for the first sentence, then slide 9 (architecture) for the rest
> "The fourth surface is the reason this app exists. Here's how it meets
> Audiotool: the browser talks to the open project through the Nexus
> SDK. OAuth tokens never leave the browser — the backend only ever sees
> a session fingerprint and candidate metadata."

**01:30-01:48 — Connect and read** · live app: /audiotool
- Click Connect, let the OAuth consent screen stay visible for a beat,
  approve, pick the project; session summary fills in
> "I connect, open my unfinished project, and Pocket Producer reads the
> session through Nexus: tempo, tracks, playhead. It shows exactly what
> it read — Audiotool documents carry no key signature, so it says 'not
> available' instead of guessing. And I can add intent in my own words:
> 'dark bass to sit under these drums'."

**01:48-02:10 — Rank with evidence** · live app, click Suggest 3
- Hover the evidence chips on each card; point at "Served by rules-v1"
> "It ranks my own fragments by whether they could belong to this piece.
> Every suggestion carries its evidence — tempo proximity, the role it
> fills, tag overlap — drawn from the ranker's actual features, never
> generated prose. The badge tells me which model served: the default is
> a rules baseline, and a learned fusion is selectable. I'll come back
> to why that's a choice."

**02:10-02:35 — Preview, insert — the money shot** · live, both windows
- Preview a candidate (audio audible), click Insert, then IMMEDIATELY
  switch to the Audiotool window: sample sits on the timeline at the
  playhead; show the track count tick up in the fingerprint
> "Preview, then insert. One Nexus transaction: upload the sample, wait
> for the server to confirm, place it at the playhead. And there it is —
> in the real project, on the real timeline."

**02:35-02:50 — Undo, then import** · live
- Click Undo; switch to Audiotool: entity gone. Then click "Import
  samples to library", show progress and the imported count
> "Undo restores the exact prior entity set from an insert receipt — an
> exact reversal, not 'delete last thing'. And it works both ways: one
> click imports this project's samples into my library, so my Audiotool
> back catalog becomes searchable creative memory too."

## Act 3 — Why you can trust it (2:50-3:30)

**02:50-03:10 — Honest uncertainty** · deck slides 19-20
> "Under the hood this is a measured system: six baselines, a frozen
> held-out split, submitted to ISMIR as a Late-Breaking/Demo paper. Our
> own evaluation shows the learned ranker's advantage is sensitive to
> how you configure it — nearly eight points on the hardest examples.
> That's exactly why the fusion is opt-in instead of silently in charge:
> the model proposes, the musician decides."

**03:10-03:30 — Close** · deck slide 22, then back to the session
> "Pocket Producer is creative memory, not autopilot. It helps you
> re-enter unfinished music with your own material — and every action it
> takes, you can see why, and you can reverse it. Try it at
> pocketproducer dot vercel dot app."

## Rules for the edit

- No shot may claim something the raw footage doesn't show
- Keep the OAuth screen visible for a beat (judges look for real integration)
- Show the Audiotool timeline before AND after insert, and after undo
- No fabricated UI states; if a state is slow, cut the wait, not the state
- The 7.8 pp finding is configuration *sensitivity* — never phrase it as
  one factor causing the difference
- Keep the raw one-take file; archive under docs/letsbuild/evidence/

## Teleprompter — full voiceover, continuous read

This is a track I never finished. I have dozens of my own loops and
sketches. The problem isn't making more sounds — it's knowing which of
them could grow into this. Pocket Producer answers that question.

It's one fragment library with four surfaces: Capture everything,
Projects that assemble themselves, a DNA profile of how you create, and
a two-way Audiotool workflow.

Capture takes anything: tap to record, type a lyric, drop an audio file,
or import a whole Audiotool project. Every input becomes a fragment —
key, tempo, instruments, emotions, themes, and one concrete suggestion
for where it could go next. Not a folder of files: a library that knows
what's in it.

You never file anything. Agents group related fragments into projects
and say why: same-song candidates, shared themes, similar emotion. Each
project gets a rescue score — how alive it still is — and one concrete
next action, with real keys and tempos, not vibes.

The same library, turned inward. My creative archetype, emotion flow,
sound palette, and when ideas actually happen — computed from what I
made, not what I claim I make.

The fourth surface is the reason this app exists. Here's how it meets
Audiotool: the browser talks to the open project through the Nexus SDK.
OAuth tokens never leave the browser — the backend only ever sees a
session fingerprint and candidate metadata.

I connect, open my unfinished project, and Pocket Producer reads the
session through Nexus: tempo, tracks, playhead. It shows exactly what it
read — Audiotool documents carry no key signature, so it says "not
available" instead of guessing. And I can add intent in my own words:
dark bass to sit under these drums.

It ranks my own fragments by whether they could belong to this piece.
Every suggestion carries its evidence — tempo proximity, the role it
fills, tag overlap — drawn from the ranker's actual features, never
generated prose. The badge tells me which model served: the default is a
rules baseline, and a learned fusion is selectable. I'll come back to
why that's a choice.

Preview, then insert. One Nexus transaction: upload the sample, wait for
the server to confirm, place it at the playhead. And there it is — in
the real project, on the real timeline.

Undo restores the exact prior entity set from an insert receipt — an
exact reversal, not "delete last thing". And it works both ways: one
click imports this project's samples into my library, so my Audiotool
back catalog becomes searchable creative memory too.

Under the hood this is a measured system: six baselines, a frozen
held-out split, submitted to ISMIR as a Late-Breaking/Demo paper. Our
own evaluation shows the learned ranker's advantage is sensitive to how
you configure it — nearly eight points on the hardest examples. That's
exactly why the fusion is opt-in instead of silently in charge: the
model proposes, the musician decides.

Pocket Producer is creative memory, not autopilot. It helps you re-enter
unfinished music with your own material — and every action it takes, you
can see why, and you can reverse it. Try it at pocketproducer dot vercel
dot app.
