import pathlib

from google.adk.skills import load_skill_from_dir
from google.adk.tools import skill_toolset

SKILLS_DIR = pathlib.Path(__file__).parent.parent / "skills"


def get_skill_toolset(skill_names: list[str]):
    """Load multiple skills and wrap them in a SkillToolset."""
    skills = [load_skill_from_dir(SKILLS_DIR / name) for name in skill_names]
    return skill_toolset.SkillToolset(skills=skills)
