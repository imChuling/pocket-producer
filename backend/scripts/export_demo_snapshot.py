"""Write the demo account's list views as static JSON for the frontend.

The demo pages read these files first, so browsing the demo (by people or
crawlers) does not start a backend instance. Re-run after reseeding:

  cd backend && .venv/bin/python -m scripts.export_demo_snapshot

Output: ../frontend/public/demo-data/{fragments,projects,dna}.json and
projects/<id>.json, one per demo project.
"""

import argparse
import json
import pathlib
import sys
from datetime import datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

DEFAULT_OUT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo-data"


def _encode(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _write(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, default=_encode, ensure_ascii=False, indent=1))


def export(db, out: pathlib.Path) -> list[pathlib.Path]:
    from api.routes import demo

    written = []
    fragments = demo.fragments_payload(db, demo.MAX_FRAGMENTS)
    projects = demo.projects_payload(db)
    for name, payload in (
        ("fragments", fragments),
        ("projects", projects),
        ("dna", demo.dna_payload(db)),
    ):
        _write(out / f"{name}.json", payload)
        written.append(out / f"{name}.json")
    for project in projects["projects"]:
        from bson import ObjectId

        detail = demo.project_detail_payload(db, ObjectId(project["_id"]))
        if detail is not None:
            path = out / "projects" / f"{project['_id']}.json"
            _write(path, detail)
            written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    from api.deps import get_db

    for path in export(get_db(), args.out):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
