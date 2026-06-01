"""Test Catcher Agent's tagging ability with real Gemini API calls.

Run: .venv/bin/python tests/test_catcher_tagging.py
"""

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset
from google.genai import types

SKILLS_DIR = pathlib.Path(__file__).parent.parent / "skills"

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
        "input": "🌧️💔",
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


def build_test_catcher() -> LlmAgent:
    skills = [
        load_skill_from_dir(SKILLS_DIR / "music-tagging"),
        load_skill_from_dir(SKILLS_DIR / "refusal-rules"),
    ]
    return LlmAgent(
        name="catcher_test",
        model=os.environ.get("TEST_GEMINI_MODEL", "gemini-2.5-flash"),
        instruction="""\
You are the Catcher Agent (Perception layer) of Pocket Producer.

You receive text fragments and produce structured tag JSON.

Use the music-tagging skill for the tagging schema.
Use the refusal-rules skill to decide when to set needs_user_input: true.

For text-only inputs, apply tagging rules directly (no audio tools needed).

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
""",
        tools=[skill_toolset.SkillToolset(skills=skills)],
    )


async def test_single(agent: LlmAgent, runner: Runner, fragment: dict, index: int) -> bool:
    session = await runner.session_service.create_session(
        app_name="catcher_test", user_id="test_user"
    )

    content = types.Content(
        role="user",
        parts=[types.Part(text=f"Tag this fragment: {fragment['input']}")],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="test_user", session_id=session.id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text

    print(f"\n{'='*60}")
    print(f"Test {index + 1}: {fragment['input'][:50]}...")
    print(f"{'='*60}")

    try:
        clean = response_text.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:-1])
        result = json.loads(clean)
    except json.JSONDecodeError:
        print("FAIL: Invalid JSON output")
        print(f"Raw: {response_text[:200]}")
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


async def main():
    os.environ.setdefault("GOOGLE_API_KEY", "")

    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: Set GOOGLE_API_KEY in .env or environment")
        sys.exit(1)

    agent = build_test_catcher()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="catcher_test", session_service=session_service)

    results = []
    for i, fragment in enumerate(TEST_FRAGMENTS):
        for attempt in range(3):
            try:
                passed = await test_single(agent, runner, fragment, i)
                results.append(passed)
                break
            except Exception as e:
                print(f"\nRetry {attempt + 1}/3 for test {i + 1}: {e.__class__.__name__}")
                if attempt < 2:
                    await asyncio.sleep(15)
                else:
                    print(f"SKIP: Test {i + 1} failed after 3 attempts")
                    results.append(False)
        await asyncio.sleep(5)

    print(f"\n{'='*60}")
    passed_count = sum(results)
    total = len(results)
    print(f"Results: {passed_count}/{total} passed")

    if passed_count >= 4:
        print("VERDICT: Catcher tagging quality is acceptable (≥80%)")
    else:
        print("VERDICT: Needs tuning — check skill loading and prompts")


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    asyncio.run(main())
