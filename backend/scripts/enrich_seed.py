"""Enrich seed fragments: casual lyrics, projects, suggestions, narratives.

The demo audio is royalty-free loops from Looperman. The lyrics, labels,
suggestions, project groupings and next actions below are AI-generated sample
text written for the demo account. Key and tempo are measured from the audio,
and rescue scores are computed with the app's own formula.

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
    "Chilling": "There is a strong late-night atmosphere here, the kind of piece that works best at low volume with headphones. The lyric matches it: the ceiling fan, the phone on silent, the fridge humming louder than the thoughts. 'This is the song for doing absolutely nothing' is the hook, and it is funny because it is accurate. Keep the vocal in a narrow melodic range, almost spoken, to fit the understated energy. Some vinyl crackle or light tape hiss would push the bed further into lo-fi territory. Repeat the last line twice at the end and let the second one trail off unfinished.",
    "Choir Melody": "The choral texture carries a lot of emotional weight on its own. The harmonic movement is slow and deliberate, which gives it an almost sacred quality. Rather than adding another choral layer, consider writing a solo vocal melody that weaves through the pads, something that enters after the first four bars and uses the choir as a bed rather than a foreground element. The dynamic range here is narrow, which is appropriate for the mood, but a single moment of swelling intensity around the midpoint would give the listener something to hold onto. This has strong potential as the emotional centerpiece of a larger arrangement.",
    "Funkyy": "The groove locks in immediately and the rhythmic pocket is tight. The bass pattern has a syncopation that pulls the listener forward, which is exactly what a funk-adjacent piece needs. The lyric knows its job: 'the bass knows what your body doesn't' is the line to build the chorus around, and 'funky like your grandma's kitchen' is the kind of odd image people remember. Shout the 'hip hip' line as a group vocal. A bass fill every four bars would break up the repetition without losing the pocket, and a B-section that drops the drums to half-time for four bars would make the main groove hit harder on the return.",
    "Motion": "Strong rhythmic energy with an electronic pulse that drives forward relentlessly. The layering is effective but the frequency spectrum is concentrated in the mid-range, which makes it feel slightly compressed. Try pitching the main loop down a semitone and layering it underneath the original for thickness, then high-passing the pitched copy to avoid muddiness. The absence of a melodic hook is fine for this style but a single repeated note, maybe a detuned saw, pulsing on the offbeat would give the ear something to follow. The build potential here is significant. Consider structuring this as a gradual accumulation that peaks around the two-minute mark.",
    "Wanna": "The emotional directness here is the strongest quality. 'I just wanna know why you left like that' carries real vulnerability without overplaying it, and the toothbrush detail does the rest: moving it would make the leaving real, so it stays. The phrasing lands naturally on the beat, which means this verse could sit over a wide range of instrumental beds. The word 'know' wants to be held longer than the syllables around it. Melodically, try approaching the opening line from a higher register and stepping down into it, which would mirror the emotional descent of the question. Save the biggest note for 'really real'.",
    "altabeats hate goodbyes": "The trick here is the understatement. 'Just gonna walk out like I'm getting milk' turns a breakup into an errand, and that avoidance is more revealing than a big farewell would be. The verse keeps a light, conversational rhythm, so set it against the warmth of the instrumental and let the contrast do the work. 'But let me have this one okay' is the most exposed line and it lands last, which is the right place for it. Consider a chorus that finally says the word the verse refuses to say, even just once, so the denial has something to break against.",
    "broken heart": "The details carry this verse. The grey sweater, the cheap laundry soap and the grocery store on a Tuesday do more emotional work than any abstract statement could. 'I said yeah I'm fine just cold, but it's August' is the turn: the excuse falls apart inside the line, and you never have to say the word heartbreak. Keep the delivery close to spoken and let the bed stay sparse underneath. The last two lines already work as a button, so resist adding a moral after them. What is missing is a chorus that steps back from the objects and says the feeling plainly, once.",
    "damn right": "This has swagger and rhythmic confidence. 'Damn right I did and I'd do it again' opens the verse like a hook, and the story behind it follows fast: the money, the safe choice, the bridge burned. 'But safe was killing me slow' is the line that earns the defiance, so give it space and let the beat thin out under it. The consonants in 'damn' and 'right' are percussive enough to work as rhythmic hits, and a bass note that drops on 'damn' would reinforce that. Lift the title phrase out as a chorus of its own and keep this as the verse that explains it.",
    "delight ft ultradiolet": "The imagery is vivid and specific. Sunrise, a car dashboard, forward motion. This has a visual quality that translates well to music. Write a second section set at night to contrast the sunrise opening: 'headlights cutting through nothing' or something equally concrete. The warmth of the audio bed matches the visual warmth of the lyric, which is a good instinct. Consider structuring the song as a journey from dawn to dark, with the musical arrangement following the same arc, brighter instruments giving way to deeper ones. The phrase 'we kept driving' has an open-ended quality that resists closure, which is exactly where a fade-out would work.",
    "gunna polo": "Short, hard and unapologetic. The verse runs on momentum, not narrative: 'drip so heavy might flood the place' and 'say less do more that's the motto' are built for delivery, and the internal rhymes keep the bars moving. Stack ad-libs in the gaps and double the last word of each line to make the pocket feel wider. 'Ain't promised yeah yeah' closes on a thought that is heavier than the rest, which gives the flex some weight; lean on it by dropping the beat out under that line. A sub-bass hit on 'pull up' would make the entrance land. This needs a hook that is simpler than the verse, two or three words at most.",
    "illusion": "The question 'was any of it real or just mirrors' has a lyrical sophistication that the arrangement should match. The mirror image runs into the theatre image, the show, the front row ticket, the clapping, and the last line, 'and called it love', closes the trap neatly. That makes this a strong chorus: it states the whole idea and ends on the phrase worth remembering. Try the first line close to a whisper before the full voice comes in, so the scale grows across the section. Reversed or echoed melodic phrases would suit the mirror idea. Leave a bar of silence after 'called it love' before anything else enters.",
    "into you": "Simple and effective. The scene is clear: two people, a room, a look. The specificity of 'across the room' grounds what could be abstract attraction in a physical space. Add a descending piano line that mirrors the feeling of falling, starting high and stepping down in thirds over the course of the phrase. The audio bed has a gentle pulse that supports the nervous energy of the lyric. Consider a second verse that moves closer, the room shrinking, the distance between the two perspectives collapsing. The arrangement should follow: instruments entering one by one as the emotional proximity increases.",
    "laid back beat": "This groove speaks for itself and does not need much help. The rhythmic pocket is relaxed but not sloppy, which is hard to achieve. Try writing a mumbled scratch vocal over it, nothing polished, just vibes and melodic shapes. The point is to find where a voice naturally wants to sit in the mix. The low end is warm and round, which leaves the mid and high frequencies open for melodic content. A Rhodes piano playing sustained chords on beats two and four would complement the existing texture without competing. This has strong playlist energy as-is, but a bridge section with a key change would elevate it from a loop to a composition.",
    "lake bottoms": "Dark, atmospheric, and submerged. The title and the lyric work together to create a sinking feeling that the audio bed reinforces. Reverse a section of the audio and layer it underneath the forward version for an underwater drowning effect. The phrase 'forgetting how to float' is the strongest image because it implies a skill that was once known and is being lost, which carries more emotional weight than simply drowning. The minor key and the heavy, submerged feel create a consistent mood. Consider breaking that consistency once, a single moment of brightness, maybe a major chord, that represents the surface before the song returns to depth.",
    "leave this place": "Road-trip energy with an open-ended quality. 'We don't need a plan, just the road' has a freedom to it that the arrangement should support. Record yourself humming a topline melody while actually driving, if possible, to capture the physical sensation of movement. The audio has a rhythmic forward motion that pairs well with the lyric. Build a second section from the perspective of having arrived somewhere, the excitement giving way to the reality of being gone. The contrast between the romanticized departure and the quieter arrival would give the song emotional depth beyond the initial rush.",
    "somewhat bouncy bass": "The bass bounce is infectious and immediately physical. The pattern has a call-and-response quality built into it, with the bass phrase asking a question that the space between phrases answers. The chant fits that shape: 'one more time from the top' is both the lyric and the instruction, so let the crowd-style vocal answer the bass instead of sitting on top of it. The energy is high and consistent, which is a strength for a loop but means the contrast has to come from somewhere else. A breakdown that strips to just the bass and a single voice on 'we ain't done yet' would reset the energy before the bounce returns.",
    "song starter": "Placeholder lyrics are exactly right at this stage. The 'la la la, fill this in later' captures the melodic shape without committing to words, which is a useful creative technique. Record three different melody options over this instrumental using nonsense syllables and come back tomorrow with fresh ears to pick the strongest one. The audio bed has enough harmonic and rhythmic information to support multiple approaches. The tempo and key leave room for both an upbeat pop direction and a more contemplative ballad approach depending on where the melody goes. Do not overthink the lyrics yet. The melody should be locked first.",
    "vanlas pillars of the heart and mind": "The build, destroy, rebuild arc in the lyric is structurally rich. 'Tear it down when it's beautiful because beautiful is terrifying' is the centre of it, and the return of 'build it up' in the fifth line gives the section a circular shape that could inform the whole arrangement. Consider starting and ending the song on the same chord, arriving back where you began with a different meaning. 'Leave the cracks showing' wants layered vocals and a wide reverb. The shrug in the last line, 'or whatever that quote says', undercuts the grandeur on purpose; keep it, because it stops the anthem from taking itself too seriously.",
}

# Sample descriptive labels per fragment. Key and tempo are not set here; they
# stay as measured from the audio by seed_account.
LABELS = {
    "Ariana": {
        "structure_hint": "chorus_candidate", "potential": "medium",
        "emotions": ["flirtatious", "playful"], "themes": ["chase", "attraction"],
        "tags": ["lyric", "hook idea", "vocal idea"], "style": ["pop", "electronic"],
    },
    "Chilling": {
        "structure_hint": "hook_candidate", "potential": "medium",
        "emotions": ["calm", "content"], "themes": ["solitude", "doing nothing"],
        "tags": ["lyric", "mundane detail", "humor"], "style": ["lo-fi"],
    },
    "Choir Melody": {
        "structure_hint": "intro_candidate", "potential": "medium",
        "emotions": ["calm", "reverent"], "themes": ["stillness"],
        "tags": ["instrumental", "choir", "melodic motif"], "style": ["vocal", "ambient"],
    },
    "Funkyy": {
        "structure_hint": "chorus_candidate", "potential": "medium",
        "emotions": ["playful", "joyful"], "themes": ["dance", "letting go"],
        "tags": ["groove", "bassline", "chant vocal"], "style": ["funk"],
    },
    "Motion": {
        "structure_hint": "loop_candidate", "potential": "medium",
        "emotions": ["driving", "tense"], "themes": ["momentum"],
        "tags": ["instrumental", "synth", "pulse"], "style": ["electronic"],
    },
    "Wanna": {
        "structure_hint": "verse_candidate", "potential": "high",
        "emotions": ["longing", "melancholy", "vulnerability"],
        "themes": ["heartbreak", "absence"],
        "tags": ["lyric", "vocal idea", "narrative"], "style": ["pop"],
    },
    "altabeats hate goodbyes": {
        "structure_hint": "verse_candidate", "potential": "medium",
        "emotions": ["bittersweet", "wistful"], "themes": ["goodbye", "avoidance"],
        "tags": ["lyric", "conversational"], "style": ["hip-hop"],
    },
    "broken heart": {
        "structure_hint": "verse_candidate", "potential": "high",
        "emotions": ["melancholy", "longing", "vulnerability"],
        "themes": ["heartbreak", "memory"],
        "tags": ["lyric", "imagery", "narrative"], "style": ["pop", "singer-songwriter"],
    },
    "damn right": {
        "structure_hint": "verse_candidate", "potential": "high",
        "emotions": ["defiant", "confident"], "themes": ["independence", "no regrets"],
        "tags": ["lyric", "attitude", "hook idea"], "style": ["electronic", "hip-hop"],
    },
    "delight ft ultradiolet": {
        "structure_hint": "verse_candidate", "potential": "high",
        "emotions": ["hopeful", "wistful"], "themes": ["road trip", "freedom"],
        "tags": ["lyric", "imagery", "narrative"], "style": ["electronic", "indie-pop"],
    },
    "gunna polo": {
        "structure_hint": "verse_candidate", "potential": "medium",
        "emotions": ["confident", "energetic"], "themes": ["status", "ambition"],
        "tags": ["lyric", "flow", "ad-libs"], "style": ["hip-hop"],
    },
    "illusion": {
        "structure_hint": "chorus_candidate", "potential": "high",
        "emotions": ["melancholy", "disillusionment"],
        "themes": ["heartbreak", "performance"],
        "tags": ["lyric", "metaphor", "hook idea"], "style": ["pop"],
    },
    "into you": {
        "structure_hint": "verse_candidate", "potential": "medium",
        "emotions": ["flirtatious", "playful"], "themes": ["attraction", "boredom"],
        "tags": ["lyric", "conversational", "narrative"], "style": ["electronic", "pop"],
    },
    "laid back beat": {
        "structure_hint": "loop_candidate", "potential": "medium",
        "emotions": ["calm", "warm"], "themes": ["late night"],
        "tags": ["instrumental", "groove", "beat"], "style": ["lo-fi"],
    },
    "lake bottoms": {
        "structure_hint": "bridge_candidate", "potential": "medium",
        "emotions": ["melancholy", "exhaustion"], "themes": ["burnout", "drowning"],
        "tags": ["lyric", "water imagery", "atmospheric"], "style": ["electronic", "alt-pop"],
    },
    "leave this place": {
        "structure_hint": "verse_candidate", "potential": "high",
        "emotions": ["restless", "hopeful"], "themes": ["escape", "fresh start"],
        "tags": ["lyric", "imagery", "road song"], "style": ["indie-pop"],
    },
    "somewhat bouncy bass": {
        "structure_hint": "loop_candidate", "potential": "medium",
        "emotions": ["playful", "confident"], "themes": ["dance", "repetition"],
        "tags": ["bassline", "groove", "chant vocal"], "style": ["bounce", "pop"],
    },
    "song starter": {
        "structure_hint": "hook_candidate", "potential": "low",
        "emotions": ["playful", "carefree"], "themes": ["work in progress"],
        "tags": ["placeholder lyric", "melody first"], "style": ["pop"],
    },
    "vanlas pillars of the heart and mind": {
        "structure_hint": "chorus_candidate", "potential": "high",
        "emotions": ["hopeful", "reflective"], "themes": ["rebuilding", "imperfection"],
        "tags": ["lyric", "anthem", "metaphor"], "style": ["pop"],
    },
}

# Reasons and next actions quote the measured key and tempo of each loop.
PROJECTS = [
    {
        "title": "Late Night Feels",
        "fragments": ["broken heart", "illusion", "lake bottoms", "Wanna"],
        "connection_reasons": [
            "Four lyrics circle the same breakup from different distances: the sweater, the toothbrush, the replayed conversations, the sinking.",
            "'broken heart' and 'illusion' are both in A at 117.5 BPM, which makes them same-song candidates and not only thematic neighbours.",
            "'lake bottoms' (A minor, 136 BPM) shares the tonic and reads as the low point of the same story.",
        ],
        "connection_types": ["related_theme", "same_song_candidate", "similar_emotion"],
        "next_action": {
            "action": "Start from the shared ground: 'broken heart' and 'illusion' are both in A at 117.5 BPM. Sing the 'illusion' chorus over the 'broken heart' verse bed at that tempo, then try the 'Wanna' lines as a second verse, transposed from D minor.",
            "estimated_time": "30 min",
        },
        "narratives": {
            "broken heart": "The raw vulnerability here anchors the whole collection. Every other piece in this group circles back to this feeling.",
            "illusion": "Asks the question the other pieces are afraid to. Same key and tempo as 'broken heart', so it can sit as that song's chorus.",
            "lake bottoms": "The darkest corner of this set. Works as a bridge between the softer pieces.",
            "Wanna": "Direct and unguarded. Could open the sequence before the mood deepens.",
        },
    },
    {
        "title": "Bounce Session",
        "fragments": ["somewhat bouncy bass", "Funkyy", "damn right"],
        "connection_reasons": [
            "Three pieces built on groove first and words second, all with a playful, confident attitude.",
            "'somewhat bouncy bass' (129.2 BPM) and 'damn right' (136 BPM) sit within a small tempo stretch of each other.",
        ],
        "connection_types": ["similar_emotion", "related_theme"],
        "next_action": {
            "action": "Set the session to 129 BPM around the 'somewhat bouncy bass' loop and deliver the 'damn right' verse over it; 136 down to 129 is a small stretch. Keep 'Funkyy' (95.7 BPM) aside as a slower breakdown idea.",
            "estimated_time": "20 min",
        },
        "narratives": {
            "somewhat bouncy bass": "The bassline is the backbone. Everything else in this group rides on top of it.",
            "Funkyy": "Shares the bounce, but sits slower at 95.7 BPM, so it needs a tempo decision before it can be layered.",
            "damn right": "Brings the lyrical attitude the groove needs.",
        },
    },
    {
        "title": "Golden Hour",
        "fragments": ["delight ft ultradiolet", "Chilling", "laid back beat"],
        "connection_reasons": [
            "Unhurried, warm material: a sunrise drive, a night of doing nothing, and an instrumental bed that fits under both.",
            "'Chilling' at 68 BPM is exact half-time against 'delight ft ultradiolet' at 136 BPM, and 'laid back beat' shares A minor with 'delight'.",
        ],
        "connection_types": ["related_theme", "similar_emotion"],
        "next_action": {
            "action": "'Chilling' at 68 BPM is exact half-time against 'delight' at 136. Loop the 'Chilling' bed under the 'delight' verse and sing the road-trip lines in a half-time feel. Check G major against A minor by ear before committing.",
            "estimated_time": "25 min",
        },
        "narratives": {
            "delight ft ultradiolet": "Sets the visual tone for the whole collection. Sunrise, warmth, motion.",
            "Chilling": "The night-time counterpart to 'delight', at exactly half its tempo.",
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
        updates.update(LABELS.get(title, {}))
        frag.update(updates)
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
    from tools.rescue_score import compute_rescue_score

    now = datetime.now(UTC)
    for proj in PROJECTS:
        members = [title_to_frag[t] for t in proj["fragments"] if t in title_to_frag]
        if len(members) < 2:
            logger.warning("Skipping project '%s' (only %d fragments)", proj["title"], len(members))
            continue

        project_doc = {
            "user_id": DEMO_USER_ID,
            "title": proj["title"],
            "fragment_ids": [str(f["_id"]) for f in members],
            "connection_reasons": proj["connection_reasons"],
            "connection_types": proj["connection_types"],
            "next_action": proj["next_action"],
            "last_activity_at": now,
            "created_at": now,
        }
        result = db["projects"].insert_one(project_doc)
        project_id = str(result.inserted_id)

        # Same formula and section derivation as agents.producer.refresh_project_score.
        score = compute_rescue_score(members, project_id, now=now)
        sections = sorted(
            {
                f["structure_hint"].replace("_candidate", "").replace("_", " ")
                for f in members
                if f.get("structure_hint")
            }
        )
        db["projects"].update_one(
            {"_id": result.inserted_id},
            {"$set": {
                "rescue_score": score["rescue_score"],
                "score_breakdown": score["components"],
                "sections": sections,
            }},
        )
        logger.info(
            "Created project '%s' with %d fragments, rescue score %s %s",
            proj["title"], len(members), score["rescue_score"], score["components"],
        )

        for frag in members:
            db["fragments"].update_one(
                {"_id": frag["_id"]},
                {"$set": {
                    "project_id": project_id,
                    "project_title": proj["title"],
                    "connection_reason": proj["connection_reasons"][0],
                    "connection_types": proj["connection_types"],
                    "agent_narrative": proj["narratives"].get(frag["title"], ""),
                }},
            )

    logger.info("Done. All seed fragments enriched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
