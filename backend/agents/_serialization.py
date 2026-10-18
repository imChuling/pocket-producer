"""Shared JSON serialization for agent tool return values."""

import json
from datetime import datetime
from typing import Any

from bson import ObjectId


class MongoJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def to_json(value: Any) -> str:
    return json.dumps(value, cls=MongoJSONEncoder, ensure_ascii=False)
