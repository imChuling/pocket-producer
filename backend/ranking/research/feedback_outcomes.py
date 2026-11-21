"""Replay feedback for candidates in one served list."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class ProposalOutcome:
    chosen: bool = False
    rejected: bool = False
    previewed: bool = False
    rejected_after_preview: bool = False
    inserts: int = 0
    undos: int = 0

    @property
    def retained(self) -> bool:
        return self.inserts > self.undos


def matches_participant(event, participant_hash):
    """Legacy rows may lack verification metadata or a pseudonymous participant."""
    if event.get("exposure_verified") is False:
        return False
    actor = event.get("participant_hash")
    return actor is None or participant_hash is None or actor == participant_hash


def _event_time(event: dict) -> datetime:
    stamp = event["created_at"]
    if isinstance(stamp, str):
        stamp = datetime.fromisoformat(stamp)
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)


def proposal_outcomes(fragment_ids, events) -> dict[str, ProposalOutcome]:
    """Replay server timestamps, using file order for ties or undated legacy sequences.

    Each new region ID identifies one insert and at most one undo, including retries.
    Historical anonymous rows have only a running count of unmatched insertions.
    """
    served = set(fragment_ids)
    grouped = defaultdict(list)
    for event in events:
        fid = event.get("fragment_id")
        if fid in served:
            grouped[fid].append(event)

    outcomes = {}
    for fid, history in grouped.items():
        if all(event.get("created_at") is not None for event in history):
            history.sort(key=_event_time)
        outcome = ProposalOutcome()
        inserted_ids, undone_ids = set(), set()
        for event in history:
            kind = event.get("event")
            region = event.get("insertion_id")
            if kind == "preview":
                outcome.previewed = True
            elif kind == "reject":
                outcome.rejected = True
                outcome.rejected_after_preview |= outcome.previewed
            elif kind == "accept":
                outcome.chosen = True
            elif kind == "insert":
                outcome.chosen = True
                if region is None:
                    outcome.inserts += 1
                else:
                    inserted_ids.add(region)
            elif kind == "undo":
                if region is not None:
                    undone_ids.add(region)
                elif outcome.undos < outcome.inserts:
                    outcome.undos += 1
        outcome.inserts += len(inserted_ids)
        outcome.undos += len(inserted_ids & undone_ids)
        outcomes[fid] = outcome
    return outcomes
