"""Shape the demo account like a real one: audio loops, lyric fragments, projects.

The demo audio is royalty-free loops from Looperman. Audio fragments carry no
text: these loops have no transcribed words, so their tags, emotions and
suggestions describe the sound, using the key, tempo, level, brightness and
onset density measured from the audio. Six short lyric fragments are text
fragments of their own, shaped the way the capture pipeline shapes text.
Projects group fragments on a stated emotional or thematic link, as the
product does; everything else stays ungrouped. Loop titles that carry an
artist or uploader name are renamed (RENAMES). The labels, suggestions,
narratives and lyrics are AI-generated sample text written for the demo, not
output of the live pipeline. Rescue scores and sections use the app's own
formula, computed as of each project's newest member.

Idempotent: lyric fragments and projects have fixed ids.

Run from backend/:
  .venv/bin/python -m scripts.enrich_seed            # apply to the database
  .venv/bin/python -m scripts.enrich_seed --dry-run  # write the snapshot only

--dry-run reads the current snapshot in frontend/public/demo-data/, applies
the same changes in memory and rewrites the snapshot through
scripts/export_demo_snapshot.py. It never connects to the database.
"""
# ruff: noqa: E501

import argparse
import json
import logging
import os
import pathlib
import sys
from datetime import UTC, datetime, timedelta

from bson import ObjectId

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("enrich")

DEMO_USER_ID = "demo-seed-user"
SNAPSHOT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo-data"

# Original loop titles that carry an artist or uploader name, or a known song
# title, renamed to the kind of title a musician gives their own sketch.
RENAMES = {
    "Ariana": "light busy loop",
    "gunna polo": "dark low pattern",
    "altabeats hate goodbyes": "long beat in G",
    "vanlas pillars of the heart and mind": "bright long take",
    "delight ft ultradiolet": "bright full run",
    "into you": "fast bright loop",
}

# Sound-only analysis for each audio loop, keyed by (new) title.
AUDIO = {
    "light busy loop": {
        "tags": ["loop", "rhythmic figure", "quiet dynamics"], "emotions": ["playfulness"],
        "themes": [], "style": [], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A 28-second loop at 136 BPM in C# major, quiet overall but with a busy rhythmic surface of about 3.6 onsets per second. The low level means it will sit under almost anything without fighting it, so treat it as a texture rather than a lead. Try doubling its rhythm with a filtered percussion layer to hear whether the figure carries more weight when it is reinforced. Because the energy stays flat across the loop, a second part that drops out for one bar in every eight would give it shape. Its tempo is a common one, so it is easy to set into a session without stretching.",
    },
    "Chilling": {
        "tags": ["loop", "slow groove", "warm low end"], "emotions": ["peacefulness"],
        "themes": [], "style": ["lo-fi"], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A slow, dark loop at 68 BPM in G major: the sound sits low, with the spectral centroid around 700 Hz, and the attacks are sparse, under two per second. That leaves the whole upper range open, so a melody or a voice placed above it will not have to compete. At this tempo the loop also reads as half-time against anything near 136 BPM, which gives two ways to use it. Keep added parts sparse too; one sustained line will suit it better than a busy one. A little room reverb on whatever goes on top would match its unhurried feel.",
    },
    "Choir Melody": {
        "tags": ["choir", "melodic motif", "sustained"], "emotions": ["peacefulness", "transcendence"],
        "themes": [], "style": ["ambient"], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "The choral texture carries a lot of emotional weight on its own. The harmonic movement is slow and deliberate, which gives it an almost sacred quality. Rather than adding another choral layer, consider writing a solo vocal melody that weaves through the pads, something that enters after the first four bars and uses the choir as a bed rather than a foreground element. The dynamic range here is narrow, which is appropriate for the mood, but a single moment of swelling intensity around the midpoint would give the listener something to hold onto. This has strong potential as the emotional centerpiece of a larger arrangement.",
    },
    "damn right": {
        "tags": ["short loop", "dense rhythm", "minor key"], "emotions": ["tension", "power"],
        "themes": [], "style": [], "structure_hint": "hook_candidate", "potential": "medium",
        "suggestion": "A short 14-second loop at 136 BPM in E minor with the busiest rhythm in the library, close to five onsets per second. Its length and density make it work like a hook: something to drop in for four bars rather than run underneath a whole section. Try cutting it into two halves and alternating them to hear which half carries the identity. The mid-range tone is neither dark nor bright, so a sub-bass under the downbeats would give it weight without clouding it. Because it is minor and driving, it would also make a strong contrast against one of the calmer loops.",
    },
    "bright full run": {
        "tags": ["full arrangement", "bright mix", "long-form"], "emotions": ["joyful_activation"],
        "themes": [], "style": [], "structure_hint": None, "potential": "medium",
        "suggestion": "At two and a half minutes this is a full piece rather than a loop: A minor at 136 BPM, loud and bright, with the spectral centroid above 2.6 kHz and a noisier texture than most of the library. Listen through once and mark where the energy changes; those points are where it could be cut into sections to reuse. The brightness means anything added on top needs to be darker or it will crowd the high end. Try pulling out a single eight-bar stretch and looping it to hear whether it holds up on its own. If it does, it becomes a bed to write over; if not, it works better as a reference for mood.",
    },
    "dark low pattern": {
        "tags": ["loop", "dark tone", "dense rhythm"], "emotions": ["tension"],
        "themes": [], "style": ["hip-hop"], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A dark, quiet loop at 136 BPM in G major with a dense rhythm, about 4.6 onsets per second, and almost all of its energy below 600 Hz. That combination suits a beat: the low weight gives a floor and the busy pattern gives drive. Bring the level up before judging it; at this loudness the detail is easy to miss. A bright element on top, such as hats or a high pluck, would fill the space it leaves above. Keep the arrangement around it simple so the pattern stays at the centre.",
    },
    "song starter": {
        "tags": ["sparse", "slow", "open space"], "emotions": ["peacefulness"],
        "themes": [], "style": [], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A slow, sparse piece at 78.3 BPM in A# major, quiet and fairly bright, with fewer than two attacks per second over 70 seconds. It leaves a lot of room, which is what a starting point needs: hum or sing over it without words first and keep whatever melody comes back twice. The space between attacks is long enough for a vocal phrase to breathe without crowding. It shares its tempo and key with 'Choir Melody', so the two can be tried together in a session. Leave percussion out for now and settle the melody first.",
    },
    "bright long take": {
        "tags": ["full arrangement", "bright mix", "long-form"], "emotions": ["wonder"],
        "themes": [], "style": [], "structure_hint": None, "potential": "medium",
        "suggestion": "The longest piece in the library at almost four minutes: A# major at 89.1 BPM, the brightest mix here (spectral centroid near 2.8 kHz) and a steady, moderate rhythm. With that much material, the first job is to find its strongest sixteen bars and loop them as a bed. The high brightness gives it an open, lifted quality; a warm, low part underneath would balance it. Listen for the moment the arrangement is at its fullest and use that as the target for anything built on it. Shorter excerpts will be easier to combine with other ideas than the whole piece.",
    },
    "Funkyy": {
        "tags": ["groove", "syncopated rhythm", "short loop"], "emotions": ["joyful_activation", "playfulness"],
        "themes": [], "style": ["funk"], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A loud, busy 20-second groove at 95.7 BPM in A# minor, with a syncopated feel and about 3.7 onsets per second. The pocket is tight, so the main job is to leave it room: anything added should play in the gaps rather than on top of the pattern. A short fill every four bars would break up the repetition without losing the groove. Try a section that drops to half-time for four bars; the main groove will hit harder when it returns. Its energy is high from the first beat, so plan where the quieter moments of a track would come from.",
    },
    "Motion": {
        "tags": ["synth", "pulse", "driving rhythm"], "emotions": ["tension"],
        "themes": [], "style": ["electronic"], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "Strong rhythmic energy with an electronic pulse that drives forward relentlessly. The layering is effective but the frequency spectrum is concentrated in the mid-range, which makes it feel slightly compressed. Try pitching the main loop down a semitone and layering it underneath the original for thickness, then high-passing the pitched copy to avoid muddiness. The absence of a melodic hook is fine for this style but a single repeated note, maybe a detuned saw, pulsing on the offbeat would give the ear something to follow. The build potential here is significant. Consider structuring this as a gradual accumulation that peaks around the two-minute mark.",
    },
    "Wanna": {
        "tags": ["loop", "minor key", "quiet dynamics"], "emotions": ["melancholy"],
        "themes": [], "style": [], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A quiet 40-second loop at 129.2 BPM in D minor, mid-range in tone and moderately busy. Its low level and minor key give it a subdued, inward quality, so it suits a part that stays in the background. Raise it a few decibels against the rest of the library before deciding where it fits; quiet loops are easy to underrate. A single sustained line above it, in the same key, would bring out the mood without adding clutter. For contrast, pair its restraint with one louder section rather than making the loop itself busier.",
    },
    "long beat in G": {
        "tags": ["full arrangement", "beat", "long-form"], "emotions": ["joyful_activation"],
        "themes": [], "style": [], "structure_hint": None, "potential": "medium",
        "suggestion": "A two-and-a-half-minute beat at 136 BPM in G major, loud, fairly bright and rhythmically busy throughout. It already sounds like a finished instrumental, so the useful question is what it is missing rather than what to add. Listen for a section where the energy drops; if there is none, that is the gap to fill with a breakdown. Its tempo matches several shorter loops in the library, which makes it a natural bed to try them against in a session. A topline written over it should stay simple, since the beat already fills a lot of space.",
    },
    "broken heart": {
        "tags": ["sparse", "bright tone", "long-form"], "emotions": ["tenderness"],
        "themes": [], "style": [], "structure_hint": None, "potential": "medium",
        "suggestion": "A long, sparse piece at 117.5 BPM in A major: quiet, bright in tone and with only about one and a half attacks per second over two and a half minutes. The space in it is its strength; resist filling every gap. A voice or a single close-miked instrument over it would sit well in that room. Because it is long, mark the passage you like most and work from that rather than from the start. It shares its tempo and tonic with 'illusion', which is worth trying in a session.",
    },
    "illusion": {
        "tags": ["dense rhythm", "dark tone", "long-form"], "emotions": ["tension"],
        "themes": [], "style": [], "structure_hint": None, "potential": "medium",
        "suggestion": "A three-minute piece at 117.5 BPM in A major, darker in tone than most of the library and rhythmically busy, around four onsets per second. The density keeps it moving even at a moderate level. Its low brightness leaves the top of the range open for something lighter. Try isolating one sixteen-bar stretch to use as a loop; the full length is more than most ideas need. It shares its tempo and tonic with 'broken heart', so the two are easy to try together in a session.",
    },
    "fast bright loop": {
        "tags": ["fast tempo", "bright mix", "loop"], "emotions": ["tension", "joyful_activation"],
        "themes": [], "style": [], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A loud, bright 79-second piece in C minor with a measured tempo of 198.8 BPM; that may be a double-time reading, so check whether it feels closer to 99. Either way it has a lot of energy and a noisier, brighter texture than most of the library. Decide on the felt tempo first, because it changes what can sit on top of it. At the slower feel a half-time vocal would work over it; at the fast one, keep any added parts short and percussive. The minor key under the bright mix gives it an edge worth keeping.",
    },
    "laid back beat": {
        "tags": ["beat", "groove", "relaxed"], "emotions": ["peacefulness"],
        "themes": [], "style": ["lo-fi"], "structure_hint": None, "potential": "medium",
        "suggestion": "This groove speaks for itself and does not need much help. The rhythmic pocket is relaxed but not sloppy, which is hard to achieve. Try writing a mumbled scratch vocal over it, nothing polished, just vibes and melodic shapes. The point is to find where a voice naturally wants to sit in the mix. The low end is warm and round, which leaves the mid and high frequencies open for melodic content. A Rhodes piano playing sustained chords on beats two and four would complement the existing texture without competing. This has strong playlist energy as-is, but a bridge section with a key change would elevate it from a loop to a composition.",
    },
    "lake bottoms": {
        "tags": ["loop", "minor key", "subdued"], "emotions": ["melancholy"],
        "themes": [], "style": [], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A quiet 28-second loop at 136 BPM in A minor, mid-range in tone and moderately busy. The low level and minor key give it a heavy, submerged feel even at this tempo. Reversing a section and layering it under the forward version would deepen that underwater quality. Its mood is the same from start to end; consider breaking it once, with a single brighter chord or a filter opening, before it returns to depth. Keep anything added above it soft so the weight of the loop stays in front.",
    },
    "leave this place": {
        "tags": ["loop", "sparse", "bright tone"], "emotions": ["longing"],
        "themes": [], "style": [], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A short, sparse loop at 123 BPM in D minor, bright in tone and with the fewest attacks in the library, about 1.3 per second. It has a sense of open space and forward lean at once, which suits a part that moves without crowding. A steady, simple pulse underneath would add motion without filling the gaps. The brightness leaves room below for a warm bass line. Try it as the opening of an arrangement, where its spaciousness can set the tone.",
    },
    "somewhat bouncy bass": {
        "tags": ["bassline", "groove", "low end"], "emotions": ["playfulness", "power"],
        "themes": [], "style": [], "structure_hint": "melodic_motif", "potential": "medium",
        "suggestion": "A loud 20-second bassline loop at 129.2 BPM in G minor, with nearly all of its energy at the bottom of the spectrum and a bouncing pattern of about 3.5 onsets per second. It is the loudest and darkest loop in the library, so it naturally becomes the floor of whatever it joins. Leave the low end to it and build upward: drums with a clear top end, then a melodic part in the mid-range. Because the energy is high and constant, the contrast has to come from the arrangement; strip back to the bass alone for two bars before bringing everything back in. A short gap of silence before a drop would also suit it.",
    },
}

# Lyric fragments, shaped like a text capture. Fixed ids keep reruns idempotent.
TEXTS = [
    {
        "_id": "6b2000000000000000000001", "created_at": "2026-11-11T00:21:40",
        "title": "Absolutely Nothing",
        "text": "no plans tonight just the ceiling fan\nthe fridge hums louder than my thoughts\nthis is the song for doing absolutely nothing",
        "tags": ["lyric", "humor", "everyday detail"], "emotions": ["peacefulness", "playfulness"],
        "themes": ["solitude"], "structure_hint": "hook_candidate", "potential": "medium",
        "suggestion": "'This is the song for doing absolutely nothing' is the hook, and it is funny because it is accurate. The ceiling fan and the humming fridge set the scene in two lines. Keep the melody in a narrow range, almost spoken, to match the low energy. Repeat the last line at the end and let the second time trail off.",
    },
    {
        "_id": "6b2000000000000000000002", "created_at": "2026-11-11T00:24:30",
        "title": "The Grey Sweater",
        "text": "still got your sweater the grey one\nI wore it to the grocery store Tuesday\nsome lady asked if I was okay\nI said yeah I'm fine just cold but it's August",
        "tags": ["lyric", "imagery", "everyday detail"], "emotions": ["longing", "melancholy"],
        "themes": ["heartbreak", "nostalgia-memory"], "structure_hint": "verse_candidate", "potential": "high",
        "suggestion": "The details do the work: a grey sweater, a grocery store on a Tuesday, a stranger asking if you are okay. 'But it's August' is the turn; the excuse falls apart inside the line, and the word heartbreak never has to appear. Keep the delivery close to spoken. What is missing is a chorus that steps back from the objects and says the feeling plainly, once.",
    },
    {
        "_id": "6b2000000000000000000003", "created_at": "2026-11-11T00:25:30",
        "title": "Three Weeks",
        "text": "it's been three weeks now\nand your toothbrush is still here\nI should probably move it\nbut then it's really real",
        "tags": ["lyric", "understatement"], "emotions": ["melancholy", "loss"],
        "themes": ["heartbreak", "home"], "structure_hint": "verse_candidate", "potential": "medium",
        "suggestion": "Four plain lines hold a whole situation: three weeks, a toothbrush, and the reason it stays. 'But then it's really real' is the line everything leans on, so give it the longest note. The understatement is the strength; do not add an explanation after it. This could open a verse that a later chorus answers.",
    },
    {
        "_id": "6b2000000000000000000004", "created_at": "2026-11-11T00:26:30",
        "title": "Front Row Ticket",
        "text": "was any of it real or just mirrors\nmaybe it was always a show\nand I just bought a front row ticket\nand called it love",
        "tags": ["lyric", "metaphor", "hook idea"], "emotions": ["vulnerability", "melancholy"],
        "themes": ["heartbreak"], "structure_hint": "chorus_candidate", "potential": "high",
        "suggestion": "This states a whole idea in four lines and ends on the phrase worth remembering, which is what a chorus needs. The mirror image runs into the theatre image, the show and the front row ticket, and 'and called it love' closes it. Try the first line close to a whisper and let the voice open up by the last. Leave a beat of silence after 'called it love'.",
    },
    {
        "_id": "6b2000000000000000000005", "created_at": "2026-11-11T00:28:50",
        "title": "Tired of Swimming",
        "text": "used to be able to hold my breath\nfor the length of a whole song\nthe water's not cold it's just heavy\nand I'm just tired of swimming",
        "tags": ["lyric", "water imagery"], "emotions": ["sadness", "melancholy"],
        "themes": ["mental-health"], "structure_hint": "bridge_candidate", "potential": "medium",
        "suggestion": "The image of a skill being lost, holding your breath for a whole song, carries more weight than drowning would. 'The water's not cold it's just heavy' refuses the obvious reading, which keeps it honest. It reads as a turn in a larger piece, a moment where the mood drops lower before anything resolves. Sing it close and low.",
    },
    {
        "_id": "6b2000000000000000000006", "created_at": "2026-11-11T00:29:20",
        "title": "Coffee Order",
        "text": "leave the dishes in the sink\nthe dog can come obviously\nI want to be somewhere\nwhere nobody knows my coffee order",
        "tags": ["lyric", "humor", "everyday detail"], "emotions": ["longing", "playfulness"],
        "themes": ["freedom-escape", "home"], "structure_hint": "verse_candidate", "potential": "medium",
        "suggestion": "Leaving, told through small and funny details: the dishes, the dog, the coffee order. 'Where nobody knows my coffee order' is a sharp way to say you want to be a stranger somewhere, and it could be the title line. Keep the rhythm conversational. A second verse from the other side, after arriving, would give it somewhere to go.",
    },
]

# Projects on a stated emotional or thematic link. Members are titles.
PROJECTS = [
    {
        "_id": "6b2100000000000000000001",
        "title": "Things Left Behind",
        "members": ["The Grey Sweater", "Three Weeks", "Front Row Ticket"],
        "connection_reasons": [
            "Three lyrics about the same aftermath: things a person left behind that cannot be moved yet (the grey sweater, the toothbrush) and the question of whether any of it was real.",
            "All three share the same longing and the same refusal to say the ending out loud.",
        ],
        "connection_types": ["related_theme", "similar_emotion"],
        "next_action": {"action": "Write a chorus that says plainly what the sweater and the toothbrush are avoiding, and try ending it on 'and called it love'.", "estimated_time": "20 min"},
        "narratives": {
            "The Grey Sweater": "The sweater is the first thing left behind in this set. I put it with the toothbrush and the front row ticket: all three are about an ending nobody says out loud.",
            "Three Weeks": "Like the sweater, the toothbrush stays because moving it would make the ending real. I grouped it with the other two lyrics about the same aftermath.",
            "Front Row Ticket": "This asks the question the other two lines circle around, whether any of it was real. It reads like the chorus for the sweater and toothbrush verses.",
        },
    },
    {
        "_id": "6b2100000000000000000002",
        "title": "Too Heavy to Swim",
        "members": ["Tired of Swimming", "lake bottoms"],
        "connection_reasons": [
            "The lyric is about being too tired to keep swimming, and you named this quiet, minor-key loop 'lake bottoms'. Both are about sinking under a weight.",
        ],
        "connection_types": ["related_theme", "similar_emotion"],
        "next_action": {"action": "Sing the swimming lines quietly over 'lake bottoms' and mark the one place where the loop could brighten for a moment.", "estimated_time": "25 min"},
        "narratives": {
            "Tired of Swimming": "Your lyric about being too tired to swim belongs with the loop you called 'lake bottoms'. Both sink under the same weight.",
            "lake bottoms": "The loop's low, subdued sound and its name meet the swimming lyric on the same image: going under. I grouped them on that.",
        },
    },
    {
        "_id": "6b2100000000000000000003",
        "title": "Nobody Knows My Order",
        "members": ["Coffee Order", "leave this place"],
        "connection_reasons": [
            "A lyric about leaving with no plan and a sparse, open loop you named 'leave this place': the same wish to be somewhere new.",
        ],
        "connection_types": ["related_theme"],
        "next_action": {"action": "Speak or half-sing the coffee-order lines over 'leave this place', then write two lines about arriving somewhere.", "estimated_time": "20 min"},
        "narratives": {
            "Coffee Order": "This is about leaving for somewhere nobody knows you. You named a loop 'leave this place', so I put the two together.",
            "leave this place": "The loop's name and its open, spacious sound match the coffee-order lyric's wish to leave. That shared wish is the link.",
        },
    },
    {
        "_id": "6b2100000000000000000004",
        "title": "Absolutely Nothing",
        "members": ["Absolutely Nothing", "Chilling"],
        "connection_reasons": [
            "A lyric about a night of doing nothing and a slow, unhurried loop you named 'Chilling': the same contentment in having no plans.",
        ],
        "connection_types": ["similar_emotion", "related_theme"],
        "next_action": {"action": "Hum a melody for 'this is the song for doing absolutely nothing' over 'Chilling', keeping it almost spoken.", "estimated_time": "15 min"},
        "narratives": {
            "Absolutely Nothing": "A night with no plans, and you already have a loop called 'Chilling' that moves at the same unhurried pace. I grouped them on that calm.",
            "Chilling": "The slow, low loop shares its contentment with the lyric about doing absolutely nothing.",
        },
    },
]

# What the grouping step says about fragments it leaves on their own.
UNGROUPED = {
    "light busy loop": "This loop has its own light, busy feel. Nothing else in your library shares its mood closely enough yet, so it stays on its own for now.",
    "Choir Melody": "The choir sits in a calm, reverent place that nothing else here reaches yet. Keeping it on its own until something joins it.",
    "damn right": "A short, tense hook with nothing else in the library on the same emotional edge yet. It stays ungrouped for now.",
    "bright full run": "A bright, full piece that does not clearly share a feeling or theme with anything else yet. Keeping it on its own.",
    "dark low pattern": "Dark and driving, but nothing in your library carries the same tension with a shared idea behind it. Ungrouped for now.",
    "song starter": "A quiet starting point without words yet. When a lyric or idea shows up that matches its mood, I will suggest pairing them.",
    "bright long take": "A long, bright piece with its own lifted feel. Nothing else shares it closely enough to group yet.",
    "Funkyy": "Playful and loud, but no lyric or idea here shares that energy with a specific link yet. It stays on its own.",
    "Motion": "Tense and driving, with no fragment yet that shares a feeling or a theme with it. Ungrouped for now.",
    "Wanna": "Subdued and inward. Its mood is close to some lyrics here, but there is no specific link to name yet, so it stays on its own.",
    "long beat in G": "A finished-sounding beat that does not yet connect to a feeling or theme elsewhere in your library. Keeping it separate.",
    "broken heart": "Tender and spacious, but nothing here shares a specific idea with it yet. It stays on its own for now.",
    "illusion": "Dark and busy, without a fragment that shares a stated link with it yet. Ungrouped for now.",
    "fast bright loop": "Loud and bright with an edge. Nothing in the library shares that feeling with a clear connection yet.",
    "laid back beat": "A relaxed groove with its own calm. It is close in mood to 'Chilling', but there is no specific link beyond that, so it stays on its own.",
    "somewhat bouncy bass": "A heavy, bouncing bassline that nothing else here shares an idea with yet. It stays on its own until something joins it.",
}

_PROJECT_FIELDS = ("project_id", "project_title", "connection_reason", "connection_types", "agent_narrative")


def _dt(value) -> datetime:
    """Naive UTC datetime, as MongoDB returns them."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    return datetime.fromisoformat(str(value).replace("Z", "")).replace(tzinfo=None)


def text_fragment(spec: dict) -> dict:
    """A lyric fragment with the fields the capture pipeline gives a text capture."""
    return {
        "_id": ObjectId(spec["_id"]),
        "user_id": DEMO_USER_ID,
        "type": "text",
        "title": spec["title"],
        "text": spec["text"],
        "raw_text": spec["text"],
        "audio_url": None,
        "upload": None,
        "prompt_injection_flag": False,
        "tags": spec["tags"],
        "emotions": spec["emotions"],
        "themes": spec["themes"],
        "style": [],
        "key": None,
        "bpm": None,
        "suggestion": spec["suggestion"],
        "structure_hint": spec["structure_hint"],
        "potential": spec["potential"],
        "transcript": None,
        "status": "ready",
        "pipeline_step": "done",
        "seed": True,
        "created_at": _dt(spec["created_at"]),
    }


def build(audio_docs: list[dict]) -> tuple[list[dict], list[dict]]:
    """The target fragments and projects, from the current audio fragment documents."""
    from tools.rescue_score import compute_rescue_score

    fragments = []
    for doc in audio_docs:
        if doc.get("type") != "audio":
            continue
        title = RENAMES.get(doc["title"], doc["title"])
        spec = AUDIO.get(title)
        if spec is None:
            raise SystemExit(f"No sound analysis for audio fragment {doc['title']!r}")
        updated = {k: v for k, v in doc.items() if k not in _PROJECT_FIELDS}
        updated.update(spec)
        updated["title"] = title
        # No words were transcribed from these loops, so they carry no text.
        updated.update({"text": None, "raw_text": None, "transcript": None})
        updated["created_at"] = _dt(doc["created_at"])
        fragments.append(updated)
    if len(fragments) != len(AUDIO):
        raise SystemExit(f"Expected {len(AUDIO)} audio fragments, found {len(fragments)}")
    fragments += [text_fragment(spec) for spec in TEXTS]

    by_title = {f["title"]: f for f in fragments}
    projects = []
    for spec in PROJECTS:
        members = [by_title[t] for t in spec["members"]]
        # Scored when the newest member arrived, as the grouping step does.
        grouped_at = max(m["created_at"] for m in members) + timedelta(minutes=1)
        project_id = spec["_id"]
        score = compute_rescue_score(members, project_id, now=grouped_at.replace(tzinfo=UTC))
        sections = sorted(
            {
                m["structure_hint"].replace("_candidate", "").replace("_", " ")
                for m in members
                if m.get("structure_hint")
            }
        )
        projects.append({
            "_id": ObjectId(project_id),
            "user_id": DEMO_USER_ID,
            "title": spec["title"],
            "fragment_ids": [str(m["_id"]) for m in members],
            "connection_reasons": spec["connection_reasons"],
            "connection_types": spec["connection_types"],
            "next_action": spec["next_action"],
            "rescue_score": score["rescue_score"],
            "score_breakdown": score["components"],
            "sections": sections,
            "last_activity_at": grouped_at,
            "created_at": grouped_at,
        })
        for member in members:
            member.update({
                "project_id": project_id,
                "project_title": spec["title"],
                "connection_reason": spec["connection_reasons"][0],
                "connection_types": spec["connection_types"],
                "agent_narrative": spec["narratives"][member["title"]],
            })

    for fragment in fragments:
        if "project_id" not in fragment:
            fragment["agent_narrative"] = UNGROUPED[fragment["title"]]
    missing = [f["title"] for f in fragments if not f.get("agent_narrative")]
    if missing:
        raise SystemExit(f"No narrative for: {missing}")
    return fragments, projects


class _Cursor(list):
    def sort(self, key, direction=1):
        keys = key if isinstance(key, list) else [(key, direction)]
        for field, order in reversed(keys):
            super().sort(key=lambda d, f=field: (d.get(f) is None, d.get(f)), reverse=order < 0)
        return self

    def limit(self, n):
        return _Cursor(self[:n])


class _Collection:
    """Enough of a MongoDB collection for the demo payload functions."""

    def __init__(self, docs):
        self.docs = docs

    @staticmethod
    def _matches(doc, query):
        for key, want in query.items():
            if isinstance(want, dict) and "$in" in want:
                if doc.get(key) not in want["$in"]:
                    return False
            elif doc.get(key) != want:
                return False
        return True

    @staticmethod
    def _project(doc, projection):
        if not projection:
            return dict(doc)
        if all(v == 0 for v in projection.values()):
            return {k: v for k, v in doc.items() if k not in projection}
        return {k: v for k, v in doc.items() if k == "_id" or k in projection}

    def find(self, query, projection=None):
        return _Cursor(self._project(d, projection) for d in self.docs if self._matches(d, query))

    def find_one(self, query, projection=None):
        found = self.find(query, projection)
        return found[0] if found else None

    def count_documents(self, query):
        return len(self.find(query))


def _snapshot_audio() -> list[dict]:
    data = json.loads((SNAPSHOT / "fragments.json").read_text())
    docs = []
    for doc in data["fragments"]:
        if doc.get("type") == "audio":
            doc = dict(doc, _id=ObjectId(doc["_id"]))
            docs.append(doc)
    return docs


def dry_run() -> int:
    from scripts.export_demo_snapshot import export

    fragments, projects = build(_snapshot_audio())
    db = {"fragments": _Collection(fragments), "projects": _Collection(projects)}
    for path in sorted(SNAPSHOT.glob("projects/*.json")):
        path.unlink()
    for path in export(db, SNAPSHOT):
        logger.info("wrote %s", path)
    return 0


def apply(db) -> int:
    audio = list(db["fragments"].find({"user_id": DEMO_USER_ID, "seed": True, "type": "audio"}))
    fragments, projects = build(audio)
    for fragment in fragments:
        db["fragments"].update_one(
            {"_id": fragment["_id"], "user_id": DEMO_USER_ID},
            {
                "$set": {k: v for k, v in fragment.items() if k != "_id"},
                "$unset": {k: "" for k in _PROJECT_FIELDS if k not in fragment},
            },
            upsert=fragment["type"] == "text",
        )
    keep = [p["_id"] for p in projects]
    db["projects"].delete_many({"user_id": DEMO_USER_ID, "_id": {"$nin": keep}})
    for project in projects:
        db["projects"].replace_one({"_id": project["_id"]}, project, upsert=True)
    logger.info("Applied %d fragments and %d projects", len(fragments), len(projects))
    return 0


def _load_env():
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="rewrite the static snapshot only; no database access")
    args = parser.parse_args()
    if args.dry_run:
        return dry_run()
    _load_env()
    from api.deps import get_db

    return apply(get_db())


if __name__ == "__main__":
    raise SystemExit(main())
