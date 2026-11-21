"""When a fragment's analysis has stopped without reporting a result.

Analysis runs in the background after the request returns. If the instance
is stopped first, nothing marks the fragment as failed, so it would show as
processing forever. An upload can wait up to 15 minutes for a pipeline slot
and the analysis itself takes a few minutes, so 20 minutes without a result
means it is no longer running.
"""

from datetime import UTC, datetime, timedelta

STALLED_AFTER = timedelta(minutes=20)


def analysis_stalled(fragment: dict, now: datetime) -> bool:
    if fragment.get("status") != "processing":
        return False
    if fragment.get("pipeline_step") in ("done", "error"):
        return False
    started = fragment.get("analysis_started_at") or fragment.get("created_at")
    if not isinstance(started, datetime):
        return False
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return now - started > STALLED_AFTER
