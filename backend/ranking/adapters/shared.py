"""The one MS-CLAP instance the process shares.

The ranking service, the session-embed route, ingest, and the role probe all
need the same 658 MB model; constructing it per call site would load it
several times into a 4 GiB container and leave all but one copy cold after
warmup. Everything goes through get_msclap(); inference is serialized with
infer_lock because the model is not safe to call from several threads.
"""

import os
import threading

from ranking.adapters.msclap import MsClapAdapter

_adapter: MsClapAdapter | None = None
_lock = threading.Lock()
infer_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("POCKET_ENABLE_CLAP") == "1"


def get_msclap() -> MsClapAdapter | None:
    """Return the shared adapter, or None when CLAP is disabled.

    The adapter itself is cheap; the model weights load on its first encode
    call (see MsClapAdapter._load), so creating it here never blocks startup.
    """
    global _adapter
    if _adapter is not None:
        return _adapter
    if not enabled():
        return None
    with _lock:
        if _adapter is None:
            import torch

            torch.set_num_threads(2)
            _adapter = MsClapAdapter()
    return _adapter


def status() -> str:
    if not enabled():
        return "disabled"
    adapter = _adapter
    if adapter is None or getattr(adapter, "_model", None) is None:
        return "loading"
    return "ready"


def encode_audio(waveform, sample_rate: int):
    adapter = get_msclap()
    if adapter is None:
        raise RuntimeError("CLAP is disabled on this server")
    with infer_lock:
        return adapter.encode_audio(waveform, sample_rate)


def encode_text(texts: list[str]):
    adapter = get_msclap()
    if adapter is None:
        raise RuntimeError("CLAP is disabled on this server")
    with infer_lock:
        return adapter.encode_text(texts)


def reset_for_tests(adapter: MsClapAdapter | None) -> None:
    global _adapter
    _adapter = adapter
