"""Enrich seed fragments: casual lyrics, projects, suggestions, narratives.

The demo audio is royalty-free loops from Looperman. The lyrics, suggestions,
project groupings and narratives below are AI-generated sample text written
for the demo account; none of it comes from the production pipeline.

Run from backend/:
  .venv/bin/python -m scripts.enrich_seed [--dry-run]
"""
# ruff: noqa: E501

import argparse
import logging
import os
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("enrich")

DEMO_USER_ID = "demo-seed-user"

LYRICS = {
    "Ariana": "mmm yeah catch me if you can\nrunning through the halls again\nyou said wait but I was gone\nlaughing with the lights still on\ndon't pretend you didn't see\nthe way I looked back at you\ncatch me if you can baby\ncatch me if you want to",
    "Chilling": "no plans tonight just the ceiling fan\nphone on silent since like 10\nthinking bout nothing and everything\nthe fridge hums louder than my thoughts\nmaybe I'll make tea or maybe not\nthis is the song for doing absolutely nothing",
    "Choir Melody": None,
    "Funkyy": "move your feet don't think about it\nthe bass knows what your body doesn't\nslide to the left now bring it back\nevery time I try to stop\nmy shoes just won't cooperate\nhip hip and away we go\nfunky like your grandma's kitchen",
    "Motion": None,
    "Wanna": "I just wanna know why you left like that\nno note on the counter no text back\nI keep checking the door like maybe\nyou forgot something and you're coming back\nbut it's been three weeks now\nand your toothbrush is still here\nI should probably move it\nbut then it's really real",
    "altabeats hate goodbyes": "hate goodbyes so I won't say it\njust gonna walk out like I'm getting milk\nleave my key under the mat\nand pretend this is a see you later\nnot a forever thing\nyeah I know that's not how it works\nbut let me have this one okay",
    "broken heart": "still got your sweater the grey one\nstill smells like you and cheap laundry soap\nI wore it to the grocery store Tuesday\nsome lady asked if I was okay\nI said yeah I'm fine just cold\nbut it's August\nI should probably throw it out\nbut probably is doing a lot of work there",
    "damn right": "damn right I did and I'd do it again\nlooked him dead in the eye and said no\nthey said I was crazy for walking away\nfrom that kind of money that kind of safe\nbut safe was killing me slow\nso yeah damn right\nI burned the bridge and danced in the light\nno regrets just a little smoke",
    "delight ft ultradiolet": "sunrise on the dash we kept driving\nwindows down since the state line\nyour playlist ran out somewhere in Nevada\nso we just listened to the wind\nand the sound of tires on nothing\npulled over at a gas station\nthat only sold jerky and hope\nkept driving anyway",
    "gunna polo": "pull up no cap fresh out the gate\ndrip so heavy might flood the place\nthey watching they talking they know the name\nrolling with the crew no need to explain\nsay less do more that's the motto\nfull send every day like tomorrow\nain't promised yeah yeah",
    "illusion": "was any of it real or just mirrors\nI keep replaying conversations\ntrying to find the moment it shifted\nfrom honest to performance\nmaybe it was always a show\nand I just bought a front row ticket\nclapped at all the right moments\nand called it love",
    "into you": "can't stop looking at you across the room\nyou're talking to someone about something boring\nI can tell by the way you keep\ntouching your ear like you do\nwhen you want to leave\ncome over here instead\nI have nothing interesting to say either\nbut at least we'd be bored together",
    "laid back beat": None,
    "lake bottoms": "sinking slow forgetting how to float\nused to be good at this\nused to be able to hold my breath\nfor the length of a whole song\nnow I can't even make it\nthrough the chorus\nthe water's not cold it's just heavy\nand I'm just tired of swimming",
    "leave this place": "we don't need a plan just the road\nthrow the bags in the back\nleave the dishes in the sink\nleave the bills on the table\nthe dog can come obviously\nbut everything else stays\nI want to be somewhere\nwhere nobody knows my coffee order",
    "somewhat bouncy bass": "one more time from the top\nyeah bring it back bring it back\nthe bass hits different the second time\nwhen you know where the drop is\nbounce with me don't be shy\neven your shadow's got rhythm\none more time from the top\nwe ain't done yet",
    "song starter": "la la la fill this in later\nda da da something something moon\nthis is the part where the chorus goes\nor maybe the bridge I'm not sure yet\nna na na rhymes with June\nI'll figure out the words tomorrow\nthe melody is the important part\nwords are just furniture",
    "vanlas pillars of the heart and mind": "build it up from nothing\nwatch it grow past the ceiling\ntear it down when it's beautiful\nbecause beautiful is terrifying\nbuild it up again with the rubble\nthis time leave the cracks showing\nthey let the light in\nor whatever that quote says",
}

SUGGESTIONS = {
    "Ariana": "The vocal hook has a natural bounce that sits well against the rhythmic bed. The melodic contour rises on 'catch me' and drops on 'if you can,' which gives it a playful tension. Consider doubling this phrase with a harmony a third above on the second pass, then letting the original sit alone on the third repeat to create a call-and-response dynamic. The space between phrases is where this really breathes. A muted guitar stab or a short synth pluck in that gap would reinforce the chase energy without crowding the vocal.",
    "Chilling": "There is a strong late-night atmosphere here, the kind of sound that works best at low volume with headphones. The tonal warmth suggests lo-fi territory but it has not fully committed to that aesthetic yet. Layering in some vinyl crackle or subtle tape hiss would push it further into that world. The low end is present but could use a gentle sidechain pump to give the kick more room. Consider writing a vocal topline that stays in a narrow melodic range, almost spoken, to match the understated energy. This would work well as an intro or interlude piece in a longer project.",
    "Choir Melody": "The choral texture carries a lot of emotional weight on its own. The harmonic movement is slow and deliberate, which gives it an almost sacred quality. Rather than adding another choral layer, consider writing a solo vocal melody that weaves through the pads, something that enters after the first four bars and uses the choir as a bed rather than a foreground element. The dynamic range here is narrow, which is appropriate for the mood, but a single moment of swelling intensity around the midpoint would give the listener something to hold onto. This has strong potential as the emotional centerpiece of a larger arrangement.",
    "Funkyy": "The groove locks in immediately and the rhythmic pocket is tight. The bass pattern has a syncopation that pulls the listener forward, which is exactly what you want in a funk-adjacent piece. Adding a bass fill every four bars would break up the repetition without losing the pocket. The high-frequency content is sparse, which leaves room for a crispy hi-hat pattern or a wah guitar. The overall energy level stays consistent throughout, so consider building a B-section that drops the drums to half-time for four bars before snapping back. That contrast would make the main groove hit even harder on the return.",
    "Motion": "Strong rhythmic energy with an electronic pulse that drives forward relentlessly. The layering is effective but the frequency spectrum is concentrated in the mid-range, which makes it feel slightly compressed. Try pitching the main loop down a semitone and layering it underneath the original for thickness, then high-passing the pitched copy to avoid muddiness. The absence of a melodic hook is fine for this style but a single repeated note, maybe a detuned saw, pulsing on the offbeat would give the ear something to follow. The build potential here is significant. Consider structuring this as a gradual accumulation that peaks around the two-minute mark.",
    "Wanna": "The emotional directness here is the strongest quality. 'I just wanna know why you left like that' carries genuine vulnerability without overplaying it. The phrasing lands naturally on the beat, which suggests this could sit over a wide range of instrumental beds. Write a pre-chorus that builds rhythmic tension, maybe shorter phrases stacking on top of each other, before this line drops in as the release. The word 'know' wants to be held longer than the surrounding syllables. Melodically, try approaching it from a higher register and stepping down into the phrase, which would mirror the emotional descent of the question.",
    "altabeats hate goodbyes": "One strong line that says everything it needs to. The defiance in 'so I won't say it' turns what could be sentimental into something with backbone. Build a full verse around the feeling of walking away without looking back, using short, punchy phrases that mirror the decisiveness of the sentiment. The instrumental bed has warmth that contrasts with the lyrical edge, which is a productive tension. Consider a structure where this line appears first as a whisper, then returns at full volume at the end of the chorus. The repetition would shift its meaning from avoidance to a declaration.",
    "broken heart": "Three concrete images in three lines. The sweater detail is the strongest because it is specific and sensory. 'Still smells like you' does more emotional work than any abstract statement could. Try cutting to just the sweater line and letting four bars of instrumental silence follow, letting the absence do the talking. If you keep all three lines, the last one, 'I should probably throw it out,' works as a self-aware moment that keeps the song from being too heavy. The word 'probably' is doing a lot of work there. The hesitation is the whole story.",
    "damn right": "This has swagger and rhythmic confidence. The repetition of 'damn right I did and I'd do it again' creates a loop-like quality that works well over a beat. Pair it with a half-time drum pattern and let the space between words carry the attitude. The consonants in 'damn' and 'right' are percussive enough to function as rhythmic elements. Consider building a verse around the circumstances that led to this moment of defiance, keeping the language equally direct. A bass line that drops on 'damn' and slides up to 'right' would reinforce the swagger. This is a hook, not a verse, so build outward from it.",
    "delight ft ultradiolet": "The imagery is vivid and specific. Sunrise, a car dashboard, forward motion. This has a visual quality that translates well to music. Write a second section set at night to contrast the sunrise opening: 'headlights cutting through nothing' or something equally concrete. The warmth of the audio bed matches the visual warmth of the lyric, which is a good instinct. Consider structuring the song as a journey from dawn to dark, with the musical arrangement following the same arc, brighter instruments giving way to deeper ones. The phrase 'we kept driving' has an open-ended quality that resists closure, which is exactly where a fade-out would work.",
    "gunna polo": "Short, hard, and unapologetic. Two words and a phrase that function more as a sonic event than a lyric. Stack ad-libs around it and treat the whole thing as a drop moment rather than trying to make it into a verse. The energy here is about impact, not narrative. Layer three or four vocal takes with slightly different deliveries and pan them across the stereo field. A sub-bass hit on 'pull up' followed by a beat drop would maximize the moment. This works best as an intro, a transition, or a beat switch, not as the foundation of a full song. Let it be what it is.",
    "illusion": "The question 'was any of it real or just mirrors' has a lyrical sophistication that the rest of the arrangement should match. The mirror metaphor opens up possibilities for production choices: reversed audio, reflected melodic phrases that echo each other. Try whispering the line over the instrumental rather than singing it at full voice. The intimacy of a whisper against a full production creates a scale contrast that draws the listener in. Consider following this question with silence rather than an answer. The uncertainty is more powerful than any resolution. This could anchor a bridge or serve as the emotional climax of a quiet song.",
    "into you": "Simple and effective. The scene is clear: two people, a room, a look. The specificity of 'across the room' grounds what could be abstract attraction in a physical space. Add a descending piano line that mirrors the feeling of falling, starting high and stepping down in thirds over the course of the phrase. The audio bed has a gentle pulse that supports the nervous energy of the lyric. Consider a second verse that moves closer, the room shrinking, the distance between the two perspectives collapsing. The arrangement should follow: instruments entering one by one as the emotional proximity increases.",
    "laid back beat": "This groove speaks for itself and does not need much help. The rhythmic pocket is relaxed but not sloppy, which is hard to achieve. Try writing a mumbled scratch vocal over it, nothing polished, just vibes and melodic shapes. The point is to find where a voice naturally wants to sit in the mix. The low end is warm and round, which leaves the mid and high frequencies open for melodic content. A Rhodes piano playing sustained chords on beats two and four would complement the existing texture without competing. This has strong playlist energy as-is, but a bridge section with a key change would elevate it from a loop to a composition.",
    "lake bottoms": "Dark, atmospheric, and submerged. The title and the lyric work together to create a sinking feeling that the audio bed reinforces. Reverse a section of the audio and layer it underneath the forward version for an underwater drowning effect. The phrase 'forgetting how to float' is the strongest image because it implies a skill that was once known and is being lost, which carries more emotional weight than simply drowning. The minor key and slow tempo create a consistent mood. Consider breaking that consistency once, a single moment of brightness, maybe a major chord, that represents the surface before the song returns to depth.",
    "leave this place": "Road-trip energy with an open-ended quality. 'We don't need a plan, just the road' has a freedom to it that the arrangement should support. Record yourself humming a topline melody while actually driving, if possible, to capture the physical sensation of movement. The audio has a rhythmic forward motion that pairs well with the lyric. Build a second section from the perspective of having arrived somewhere, the excitement giving way to the reality of being gone. The contrast between the romanticized departure and the quieter arrival would give the song emotional depth beyond the initial rush.",
    "somewhat bouncy bass": "The bass bounce is infectious and immediately physical. The rhythmic pattern has a call-and-response quality built into it, with the bass phrase asking a question that the space between phrases answers. Write a vocal that plays against the rhythm rather than sitting on top of it, entering slightly before or after the beat to create tension. The energy is high and consistent, which is a strength for a hook section but means you will need to build contrast elsewhere. A breakdown that strips to just the bass and a single vocal would reset the energy before the bounce returns at full force.",
    "song starter": "Placeholder lyrics are exactly right at this stage. The 'la la la, fill this in later' captures the melodic shape without committing to words, which is a useful creative technique. Record three different melody options over this instrumental using nonsense syllables and come back tomorrow with fresh ears to pick the strongest one. The audio bed has enough harmonic and rhythmic information to support multiple approaches. The tempo and key leave room for both an upbeat pop direction and a more contemplative ballad approach depending on where the melody goes. Do not overthink the lyrics yet. The melody should be locked first.",
    "vanlas pillars of the heart and mind": "The build-destroy-rebuild arc in the lyric is structurally rich. Map it directly to a song structure: verse one builds up, chorus tears it down, bridge rebuilds from the rubble. The repetition of 'build it up' at the beginning and end creates a circular quality that could inform the arrangement. Consider starting and ending the song with the same chord, arriving back where you began but with different meaning. The title itself has a grandeur that the production should match. Layered vocals, wide reverb, and a gradual accumulation of instruments would support the architectural metaphor. This wants to be an anthem, not an aside.",
}

PROJECTS = [
    {
        "title": "Late Night Feels",
        "fragments": ["broken heart", "illusion", "lake bottoms", "Wanna"],
        "connection_reason": "Melancholic minor-key pieces that share an introspective, late-night emotional space",
        "connection_types": ["related_theme", "harmonic_proximity"],
        "narratives": {
            "broken heart": "The raw vulnerability here anchors the whole collection. Every other piece in this group circles back to this feeling.",
            "illusion": "Asks the question the other pieces are afraid to. Sits at the emotional center of this group.",
            "lake bottoms": "The darkest corner of this set. Works as an outro or a bridge between the softer pieces.",
            "Wanna": "Direct and unguarded. Could open the sequence before the mood deepens.",
        },
    },
    {
        "title": "Bounce Session",
        "fragments": ["somewhat bouncy bass", "Funkyy", "damn right"],
        "connection_reason": "High-energy rhythmic pieces built around groove and attitude",
        "connection_types": ["same_song_candidate", "rhythmic_match"],
        "narratives": {
            "somewhat bouncy bass": "The bassline is the backbone. Everything else in this group rides on top of it.",
            "Funkyy": "Shares the same bounce DNA. These two could be layered directly.",
            "damn right": "Brings the lyrical attitude this instrumental set needs.",
        },
    },
    {
        "title": "Golden Hour",
        "fragments": ["delight ft ultradiolet", "Chilling", "laid back beat"],
        "connection_reason": "Warm, relaxed pieces with a golden-hour aesthetic and gentle tempos",
        "connection_types": ["related_theme", "tonal_match"],
        "narratives": {
            "delight ft ultradiolet": "Sets the visual tone for the whole collection. Sunrise, warmth, motion.",
            "Chilling": "The lo-fi texture complements the visual warmth. Night-time counterpart to 'delight'.",
            "laid back beat": "Pure instrumental mood-setter. Glues the vocal pieces together.",
        },
    },
]


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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    _load_env()

    from api.deps import get_db
    db = get_db()

    fragments = list(db["fragments"].find(
        {"user_id": DEMO_USER_ID, "seed": True},
    ))
    logger.info("Found %d seed fragments", len(fragments))

    title_to_frag = {f["title"]: f for f in fragments}

    if args.dry_run:
        for title, frag in title_to_frag.items():
            has_lyrics = title in LYRICS and LYRICS[title] is not None
            has_suggestion = title in SUGGESTIONS
            logger.info("  %s  lyrics=%s  suggestion=%s", title, has_lyrics, has_suggestion)
        return 0

    # 1. Update lyrics and suggestions on fragments
    for title, frag in title_to_frag.items():
        updates = {}
        if title in LYRICS:
            new_text = LYRICS[title]
            updates["text"] = new_text
            updates["raw_text"] = new_text
        if title in SUGGESTIONS:
            updates["suggestion"] = SUGGESTIONS[title]
        if updates:
            db["fragments"].update_one(
                {"_id": frag["_id"]},
                {"$set": updates},
            )
            logger.info("Updated %s: %s", title, list(updates.keys()))

    # 2. Remove old project assignments and projects
    db["fragments"].update_many(
        {"user_id": DEMO_USER_ID, "seed": True},
        {"$unset": {
            "project_id": "",
            "project_title": "",
            "connection_reason": "",
            "connection_types": "",
            "agent_narrative": "",
        }},
    )
    db["projects"].delete_many({"user_id": DEMO_USER_ID})
    logger.info("Cleared old project assignments and demo projects")

    # 3. Create projects and assign fragments
    now = datetime.now(UTC)
    for proj in PROJECTS:
        frag_ids = []
        oids = []
        for title in proj["fragments"]:
            if title in title_to_frag:
                frag_ids.append(str(title_to_frag[title]["_id"]))
                oids.append(title_to_frag[title]["_id"])

        if len(oids) < 2:
            logger.warning("Skipping project '%s' (only %d fragments)", proj["title"], len(oids))
            continue

        project_doc = {
            "user_id": DEMO_USER_ID,
            "title": proj["title"],
            "fragment_ids": frag_ids,
            "connection_reasons": [proj["connection_reason"]],
            "connection_types": proj["connection_types"],
            "sections": [],
            "rescue_score": None,
            "last_activity_at": now,
            "created_at": now,
        }
        result = db["projects"].insert_one(project_doc)
        project_id = str(result.inserted_id)
        logger.info("Created project '%s' (%s) with %d fragments", proj["title"], project_id, len(oids))

        for title in proj["fragments"]:
            if title not in title_to_frag:
                continue
            narrative = proj["narratives"].get(title, "")
            db["fragments"].update_one(
                {"_id": title_to_frag[title]["_id"]},
                {"$set": {
                    "project_id": project_id,
                    "project_title": proj["title"],
                    "connection_reason": proj["connection_reason"],
                    "connection_types": proj["connection_types"],
                    "agent_narrative": narrative,
                }},
            )

    logger.info("Done. All seed fragments enriched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
