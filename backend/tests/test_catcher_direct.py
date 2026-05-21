"""Direct Gemini API test for Catcher tagging — bypasses ADK to save quota.

Run: .venv/bin/python tests/test_catcher_direct.py
"""

import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import google.genai as genai  # noqa: E402

SKILLS_DIR = pathlib.Path(__file__).parent.parent / "skills"

SYSTEM_INSTRUCTION = """\
You are the Catcher Agent (Perception layer) of Pocket Producer.

You receive text fragments and produce structured tag JSON.

Use the tagging schema below to assign tags.

## Emotion Taxonomy
Primary emotions: joy, sadness, anger, fear, surprise, disgust, trust, anticipation
Musical emotions: melancholy, euphoria, tension, nostalgia, tenderness, defiance,
  longing, serenity, vulnerability, excitement, acceptance, freedom, loss, anxiety

## Theme Taxonomy
Categories: love, heartbreak, self-identity, mental-health, hometown, celebration,
  freedom, rebellion, growth, loss-grief, friendship, nature, time, memory,
  spirituality, social-commentary, isolation, youth, home, introspection

## Structure Hints
verse, chorus, bridge, pre-chorus, hook, intro, outro, spoken-word, ad-lib

## Style Vocabulary
Genres: pop, rock, hip-hop, r-and-b, country, electronic, jazz, classical, folk,
  indie, alternative, latin, afrobeats, k-pop, metal, punk, blues, soul, reggae, funk

Output ONLY a valid JSON object matching this schema, no other text:
{
  "tags": {
    "emotion": ["string"],
    "theme": ["string"],
    "structure_hint": "string | null",
    "style": ["string"],
    "potential": "high | medium | low",
    "needs_user_input": false,
    "user_prompt": null
  },
  "reasoning": "string"
}
"""

TEST_FRAGMENTS = [
    {
        "input": "I keep waiting for the rain to stop, but the rain is me.",
        "expected_emotions": ["melancholy", "acceptance", "sadness", "longing"],
        "expected_themes": ["self-identity", "mental-health", "introspection"],
    },
    {
        "input": "We're dancing on the rooftop, city lights below, nothing can touch us tonight",
        "expected_emotions": ["joy", "excitement", "euphoria", "freedom"],
        "expected_themes": ["celebration", "love", "freedom", "youth"],
    },
    {
        "input": "\U0001f327️\U0001f494",
        "expected_emotions": ["melancholy", "sadness", "loss", "tenderness"],
        "expected_themes": [],
    },
    {
        "input": "I keep pretending I'm fine but the walls are closing in",
        "expected_emotions": ["tension", "anxiety", "melancholy", "vulnerability"],
        "expected_themes": ["mental-health", "self-identity", "isolation"],
    },
    {
        "input": "Coming home after ten years, the old oak tree is still there",
        "expected_emotions": ["nostalgia", "tenderness", "acceptance", "melancholy"],
        "expected_themes": ["hometown", "home", "memory", "time"],
    },
]

MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]


def test_single(client: genai.Client, model: str, fragment: dict, index: int) -> bool:
    prompt = f"Tag this fragment: {fragment['input']}"

    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.3,
        ),
    )
    response_text = resp.text

    print(f"\n{'='*60}")
    print(f"Test {index + 1} [{model}]: {fragment['input'][:50]}...")
    print(f"{'='*60}")

    try:
        clean = response_text.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:-1])
        result = json.loads(clean)
    except json.JSONDecodeError:
        print("FAIL: Invalid JSON output")
        print(f"Raw: {response_text[:300]}")
        return False

    tags = result.get("tags", {})
    emotions = tags.get("emotion", [])
    themes = tags.get("theme", [])
    potential = tags.get("potential", "")
    reasoning = result.get("reasoning", "")

    print(f"Emotions:  {emotions}")
    print(f"Themes:    {themes}")
    print(f"Structure: {tags.get('structure_hint')}")
    print(f"Style:     {tags.get('style', [])}")
    print(f"Potential:  {potential}")
    print(f"Reasoning: {reasoning}")

    passed = True

    if not emotions and not tags.get("needs_user_input"):
        print("FAIL: No emotions and not requesting user input")
        passed = False

    if emotions:
        overlap = set(emotions) & set(fragment["expected_emotions"])
        if not overlap:
            print(f"WARN: No emotion overlap. Expected any of {fragment['expected_emotions']}")
        else:
            print(f"OK: Emotion match: {overlap}")

    if potential not in ("high", "medium", "low"):
        print(f"FAIL: Invalid potential value: {potential}")
        passed = False

    if not reasoning:
        print("FAIL: Missing reasoning")
        passed = False

    return passed


def main():
    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: Set GOOGLE_API_KEY in .env or environment")
        sys.exit(1)

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    results = []
    for i, fragment in enumerate(TEST_FRAGMENTS):
        model = MODELS[i % len(MODELS)]
        for attempt in range(2):
            try:
                passed = test_single(client, model, fragment, i)
                results.append(passed)
                break
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:80]}"
                print(f"\nRetry {attempt + 1}/2 for test {i + 1}: {err}")
                if attempt < 1:
                    time.sleep(65)
                else:
                    print(f"SKIP: Test {i + 1} failed after 2 attempts")
                    results.append(False)
        if i < len(TEST_FRAGMENTS) - 1:
            time.sleep(3)

    print(f"\n{'='*60}")
    passed_count = sum(results)
    total = len(results)
    print(f"Results: {passed_count}/{total} passed")

    if passed_count >= 4:
        print("VERDICT: Catcher tagging quality is acceptable (>=80%)")
    else:
        print("VERDICT: Needs tuning")


if __name__ == "__main__":
    main()
