"""Seed 30+ diverse fragments into MongoDB for testing clustering.

Each fragment gets real Voyage AI embeddings. Fragments are grouped into
5 thematic clusters (6 fragments each) plus 5 outliers to test separation.

Run: .venv/bin/python tests/seed_30_fragments.py
"""

import os
import pathlib
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import pymongo  # noqa: E402
import voyageai  # noqa: E402

USER_ID = "test_30plus"
NOW = datetime.now(UTC)

CLUSTERS = {
    "rain_walk": {
        "project_id": "proj_rain_walk",
        "fragments": [
            {
                "raw_input": "Walking alone in the drizzle, no umbrella, just the sound of my shoes on wet asphalt",
                "tags": {
                    "emotion": ["melancholy", "longing"],
                    "theme": ["isolation", "nature"],
                    "structure_hint": "verse_candidate",
                    "style": ["indie", "folk"],
                    "potential": "high",
                },
                "days_ago": 2,
            },
            {
                "raw_input": "Rain keeps falling and I keep walking, nowhere to go, nowhere to be, just me and the grey sky",
                "tags": {
                    "emotion": ["melancholy", "acceptance"],
                    "theme": ["isolation", "introspection"],
                    "structure_hint": "verse_candidate",
                    "style": ["indie", "folk"],
                    "potential": "high",
                },
                "days_ago": 2,
            },
            {
                "raw_input": "Let the rain wash it all away, wash away everything I couldn't say",
                "tags": {
                    "emotion": ["melancholy", "hope"],
                    "theme": ["loss-grief", "nature"],
                    "structure_hint": "chorus_candidate",
                    "style": ["indie", "pop"],
                    "potential": "high",
                },
                "days_ago": 1,
            },
            {
                "raw_input": "Puddles on the sidewalk catching streetlights, little mirrors showing another world",
                "tags": {
                    "emotion": ["nostalgia", "tenderness"],
                    "theme": ["nature", "memory"],
                    "structure_hint": "bridge_candidate",
                    "style": ["indie"],
                    "potential": "medium",
                },
                "days_ago": 1,
            },
            {
                "raw_input": "Da da da daaaa, descending melody, raindrops on a window pattern",
                "tags": {
                    "emotion": ["melancholy"],
                    "theme": ["nature"],
                    "structure_hint": "hook_candidate",
                    "style": ["indie", "folk"],
                    "potential": "medium",
                },
                "days_ago": 3,
            },
            {
                "raw_input": "Soaked through my jacket but I don't mind, there's something honest about being this exposed",
                "tags": {
                    "emotion": ["vulnerability", "acceptance"],
                    "theme": ["introspection", "nature"],
                    "structure_hint": "verse_candidate",
                    "style": ["indie", "folk"],
                    "potential": "medium",
                },
                "days_ago": 1,
            },
        ],
    },
    "club_energy": {
        "project_id": "proj_club_energy",
        "fragments": [
            {
                "raw_input": "BASS DROP hit so hard the floor shakes, everyone jumping, hands in the air",
                "tags": {
                    "emotion": ["euphoria", "excitement"],
                    "theme": ["celebration", "youth"],
                    "structure_hint": "hook_candidate",
                    "style": ["electronic", "hip-hop"],
                    "potential": "high",
                },
                "days_ago": 5,
            },
            {
                "raw_input": "Turn up the volume, feel the beat through your chest, tonight we don't stop",
                "tags": {
                    "emotion": ["excitement", "joy"],
                    "theme": ["celebration", "freedom"],
                    "structure_hint": "chorus_candidate",
                    "style": ["electronic", "pop"],
                    "potential": "high",
                },
                "days_ago": 4,
            },
            {
                "raw_input": "Strobe lights painting faces in the dark, every stranger feels like a friend",
                "tags": {
                    "emotion": ["euphoria", "trust"],
                    "theme": ["celebration", "friendship"],
                    "structure_hint": "verse_candidate",
                    "style": ["electronic"],
                    "potential": "medium",
                },
                "days_ago": 5,
            },
            {
                "raw_input": "Four on the floor, synth stab, filter sweep building to the drop",
                "tags": {
                    "emotion": ["anticipation", "excitement"],
                    "theme": ["celebration"],
                    "structure_hint": "verse_candidate",
                    "style": ["electronic"],
                    "potential": "medium",
                },
                "days_ago": 6,
            },
            {
                "raw_input": "After the drop everything goes quiet for one beat, then the crowd explodes",
                "tags": {
                    "emotion": ["euphoria", "surprise"],
                    "theme": ["celebration"],
                    "structure_hint": "bridge_candidate",
                    "style": ["electronic"],
                    "potential": "medium",
                },
                "days_ago": 4,
            },
            {
                "raw_input": "We came alive when the speakers hit, running through the night like it's the last one",
                "tags": {
                    "emotion": ["excitement", "freedom"],
                    "theme": ["youth", "celebration"],
                    "structure_hint": "verse_candidate",
                    "style": ["electronic", "pop"],
                    "potential": "high",
                },
                "days_ago": 3,
            },
        ],
    },
    "heartbreak_slow": {
        "project_id": "proj_heartbreak",
        "fragments": [
            {
                "raw_input": "Your side of the bed is cold, I still reach for you in my sleep",
                "tags": {
                    "emotion": ["sadness", "longing"],
                    "theme": ["heartbreak", "love"],
                    "structure_hint": "verse_candidate",
                    "style": ["r-and-b", "soul"],
                    "potential": "high",
                },
                "days_ago": 10,
            },
            {
                "raw_input": "I keep your voicemail just to hear you laugh, even though it breaks me every time",
                "tags": {
                    "emotion": ["sadness", "nostalgia"],
                    "theme": ["heartbreak", "memory"],
                    "structure_hint": "verse_candidate",
                    "style": ["r-and-b", "pop"],
                    "potential": "high",
                },
                "days_ago": 9,
            },
            {
                "raw_input": "Gone, gone, you're gone, and I'm still here pretending I'm whole",
                "tags": {
                    "emotion": ["sadness", "vulnerability"],
                    "theme": ["heartbreak", "self-identity"],
                    "structure_hint": "chorus_candidate",
                    "style": ["r-and-b", "soul"],
                    "potential": "high",
                },
                "days_ago": 8,
            },
            {
                "raw_input": "Slow piano chords, Am to F, the kind of progression that sounds like crying",
                "tags": {
                    "emotion": ["sadness", "tenderness"],
                    "theme": ["heartbreak"],
                    "structure_hint": "melodic_motif",
                    "style": ["soul", "classical"],
                    "potential": "medium",
                },
                "audio_features": {"bpm": 72, "key": "Am"},
                "days_ago": 11,
            },
            {
                "raw_input": "Maybe in another life we get it right, maybe there we don't say goodbye",
                "tags": {
                    "emotion": ["longing", "hope"],
                    "theme": ["heartbreak", "love"],
                    "structure_hint": "bridge_candidate",
                    "style": ["r-and-b", "pop"],
                    "potential": "medium",
                },
                "days_ago": 7,
            },
            {
                "raw_input": "Three months and I still smell your perfume on the couch, ghost of what we were",
                "tags": {
                    "emotion": ["sadness", "nostalgia"],
                    "theme": ["heartbreak", "memory"],
                    "structure_hint": "verse_candidate",
                    "style": ["r-and-b"],
                    "potential": "medium",
                },
                "days_ago": 8,
            },
        ],
    },
    "hometown_nostalgia": {
        "project_id": "proj_hometown",
        "fragments": [
            {
                "raw_input": "Drove past the old school today, playground's smaller than I remember",
                "tags": {
                    "emotion": ["nostalgia", "tenderness"],
                    "theme": ["hometown", "memory"],
                    "structure_hint": "verse_candidate",
                    "style": ["country", "folk"],
                    "potential": "high",
                },
                "days_ago": 15,
            },
            {
                "raw_input": "Friday nights at the gas station parking lot, cheap beer and big dreams under the stars",
                "tags": {
                    "emotion": ["nostalgia", "joy"],
                    "theme": ["hometown", "youth"],
                    "structure_hint": "verse_candidate",
                    "style": ["country", "rock"],
                    "potential": "high",
                },
                "days_ago": 14,
            },
            {
                "raw_input": "Take me back to the backroads, take me back to when we were free",
                "tags": {
                    "emotion": ["nostalgia", "longing"],
                    "theme": ["hometown", "freedom"],
                    "structure_hint": "chorus_candidate",
                    "style": ["country"],
                    "potential": "high",
                },
                "days_ago": 13,
            },
            {
                "raw_input": "Mama's kitchen always smelled like Sunday morning, biscuits and gospel radio",
                "tags": {
                    "emotion": ["nostalgia", "tenderness"],
                    "theme": ["hometown", "home"],
                    "structure_hint": "verse_candidate",
                    "style": ["country", "folk"],
                    "potential": "medium",
                },
                "days_ago": 16,
            },
            {
                "raw_input": "The water tower still has our initials, faded but not gone, like everything else here",
                "tags": {
                    "emotion": ["nostalgia", "melancholy"],
                    "theme": ["hometown", "time"],
                    "structure_hint": "bridge_candidate",
                    "style": ["country"],
                    "potential": "medium",
                },
                "days_ago": 12,
            },
            {
                "raw_input": "Acoustic guitar, open G tuning, that front porch fingerpicking sound",
                "tags": {
                    "emotion": ["nostalgia"],
                    "theme": ["hometown"],
                    "structure_hint": "melodic_motif",
                    "style": ["country", "folk"],
                    "potential": "medium",
                },
                "audio_features": {"bpm": 95, "key": "G"},
                "days_ago": 14,
            },
        ],
    },
    "anxiety_spiral": {
        "project_id": "proj_anxiety",
        "fragments": [
            {
                "raw_input": "Thoughts racing at 3am again, ceiling fan spinning like my mind won't stop",
                "tags": {
                    "emotion": ["anxiety", "fear"],
                    "theme": ["mental-health", "isolation"],
                    "structure_hint": "verse_candidate",
                    "style": ["alternative", "indie"],
                    "potential": "high",
                },
                "days_ago": 20,
            },
            {
                "raw_input": "Breathe in, breathe out, but the walls keep closing and the air gets thin",
                "tags": {
                    "emotion": ["anxiety", "vulnerability"],
                    "theme": ["mental-health"],
                    "structure_hint": "chorus_candidate",
                    "style": ["alternative"],
                    "potential": "high",
                },
                "days_ago": 19,
            },
            {
                "raw_input": "Everyone's moving forward and I'm stuck in this loop, same fears different day",
                "tags": {
                    "emotion": ["anxiety", "sadness"],
                    "theme": ["mental-health", "self-identity"],
                    "structure_hint": "verse_candidate",
                    "style": ["alternative", "indie"],
                    "potential": "medium",
                },
                "days_ago": 18,
            },
            {
                "raw_input": "Phone buzzing, heart pounding, every notification feels like a threat",
                "tags": {
                    "emotion": ["anxiety", "fear"],
                    "theme": ["mental-health", "social-commentary"],
                    "structure_hint": "verse_candidate",
                    "style": ["alternative", "electronic"],
                    "potential": "medium",
                },
                "days_ago": 21,
            },
            {
                "raw_input": "Dissonant synth pad, unstable rhythm, 140bpm but feels like drowning",
                "tags": {
                    "emotion": ["anxiety", "tension"],
                    "theme": ["mental-health"],
                    "structure_hint": "melodic_motif",
                    "style": ["electronic", "alternative"],
                    "potential": "medium",
                },
                "audio_features": {"bpm": 140, "key": "Dm"},
                "days_ago": 22,
            },
            {
                "raw_input": "Maybe if I just keep running the panic can't catch me, feet on pavement at dawn",
                "tags": {
                    "emotion": ["anxiety", "hope"],
                    "theme": ["mental-health", "growth"],
                    "structure_hint": "bridge_candidate",
                    "style": ["alternative", "indie"],
                    "potential": "medium",
                },
                "days_ago": 17,
            },
        ],
    },
}

OUTLIERS = [
    {
        "raw_input": "Mariachi trumpet solo over a reggaeton beat, experimental fusion idea",
        "tags": {
            "emotion": ["excitement", "joy"],
            "theme": ["celebration"],
            "structure_hint": "melodic_motif",
            "style": ["latin", "reggae"],
            "potential": "low",
        },
        "days_ago": 45,
    },
    {
        "raw_input": "Spoken word over jazz piano: the revolution will not be monetized",
        "tags": {
            "emotion": ["defiance", "anger"],
            "theme": ["social-commentary", "rebellion"],
            "structure_hint": "verse_candidate",
            "style": ["jazz", "hip-hop"],
            "potential": "medium",
        },
        "days_ago": 60,
    },
    {
        "raw_input": "Lullaby for my niece, soft humming over music box melody in F major",
        "tags": {
            "emotion": ["tenderness", "serenity"],
            "theme": ["love", "home"],
            "structure_hint": "melodic_motif",
            "style": ["classical", "folk"],
            "potential": "low",
        },
        "audio_features": {"bpm": 60, "key": "F"},
        "days_ago": 90,
    },
    {
        "raw_input": "Metal riff: drop D, palm muted chugging, angry and fast, screaming about corporate greed",
        "tags": {
            "emotion": ["anger", "defiance"],
            "theme": ["rebellion", "social-commentary"],
            "structure_hint": "hook_candidate",
            "style": ["metal", "punk"],
            "potential": "medium",
        },
        "audio_features": {"bpm": 180, "key": "D"},
        "days_ago": 35,
    },
    {
        "raw_input": "K-pop inspired dance break, catchy synth hook, bilingual lyrics idea Korean-English",
        "tags": {
            "emotion": ["excitement", "joy"],
            "theme": ["celebration", "self-identity"],
            "structure_hint": "hook_candidate",
            "style": ["k-pop", "electronic", "pop"],
            "potential": "medium",
        },
        "days_ago": 50,
    },
]


def main():
    mongo = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
    db = mongo["pocketproducer"]
    vc = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

    existing = db.fragments.count_documents({"user_id": USER_ID})
    if existing > 0:
        print(f"Found {existing} existing fragments for user_id={USER_ID}")
        print("Deleting and re-seeding...")
        db.fragments.delete_many({"user_id": USER_ID})

    all_fragments = []

    for cluster_name, cluster in CLUSTERS.items():
        for frag in cluster["fragments"]:
            doc = {
                "user_id": USER_ID,
                "raw_input": frag["raw_input"],
                "input_type": "text",
                "tags": frag["tags"],
                "project_id": cluster["project_id"],
                "created_at": NOW - timedelta(days=frag["days_ago"]),
                "status": "tagged",
            }
            if "audio_features" in frag:
                doc["audio_features"] = frag["audio_features"]
            all_fragments.append((cluster_name, doc))

    for frag in OUTLIERS:
        doc = {
            "user_id": USER_ID,
            "raw_input": frag["raw_input"],
            "input_type": "text",
            "tags": frag["tags"],
            "project_id": None,
            "created_at": NOW - timedelta(days=frag["days_ago"]),
            "status": "tagged",
        }
        if "audio_features" in frag:
            doc["audio_features"] = frag["audio_features"]
        all_fragments.append(("outlier", doc))

    print(f"Generating embeddings for {len(all_fragments)} fragments...")
    texts = [doc["raw_input"] for _, doc in all_fragments]

    import time

    batch_size = 3
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        if i > 0:
            time.sleep(22)
        batch = texts[i : i + batch_size]
        for attempt in range(3):
            try:
                result = vc.embed(batch, model="voyage-3", input_type="document")
                all_embeddings.extend(result.embeddings)
                break
            except Exception:
                if attempt < 2:
                    print("  Rate limited, waiting 30s...")
                    time.sleep(30)
                else:
                    raise
        print(f"  Embedded {min(i + batch_size, len(texts))}/{len(texts)}")

    docs_to_insert = []
    for idx, (cluster_name, doc) in enumerate(all_fragments):
        doc["embedding"] = all_embeddings[idx]
        docs_to_insert.append(doc)

    result = db.fragments.insert_many(docs_to_insert)
    print(f"\nInserted {len(result.inserted_ids)} fragments")

    for cluster_name in CLUSTERS:
        count = sum(1 for c, _ in all_fragments if c == cluster_name)
        print(f"  {cluster_name}: {count} fragments")
    outlier_count = sum(1 for c, _ in all_fragments if c == "outlier")
    print(f"  outliers: {outlier_count} fragments")

    total = db.fragments.count_documents({"user_id": USER_ID})
    print(f"\nTotal fragments for {USER_ID}: {total}")

    mongo.close()


if __name__ == "__main__":
    main()
