"""Download specific FMA tracks from the remote zip via HTTP range requests.

Instead of downloading the full 7.2 GB zip, this reads the zip's central
directory (~1 MB from the end) and then fetches only the requested mp3 files.

Run: .venv/bin/python tests/download_fma_tracks.py [--count 100] [--out-dir /tmp/fma_audio]
"""

import argparse
import os
import pathlib
import struct
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

FMA_ZIP_URL = "https://os.unil.cloud.switch.ch/fma/fma_small.zip"
DEFAULT_OUT = pathlib.Path("/tmp/fma_audio")


def get_zip_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req) as resp:
        return int(resp.headers["Content-Length"])


def fetch_range(url: str, start: int, end: int) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("Range", f"bytes={start}-{end}")
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def parse_eocd(data: bytes) -> tuple[int, int]:
    """Find End of Central Directory and return (cd_offset, cd_size). Handles ZIP64."""
    zip64_locator_sig = b"\x50\x4b\x06\x07"
    loc_pos = data.rfind(zip64_locator_sig)
    if loc_pos != -1:
        zip64_eocd_offset = struct.unpack_from("<Q", data, loc_pos + 8)[0]
        zip64_sig = b"\x50\x4b\x06\x06"
        eocd64_start = data.find(zip64_sig)
        if eocd64_start != -1:
            cd_size = struct.unpack_from("<Q", data, eocd64_start + 40)[0]
            cd_offset = struct.unpack_from("<Q", data, eocd64_start + 48)[0]
            return cd_offset, cd_size
        raise ValueError(
            f"ZIP64 EOCD locator found but EOCD64 record not in tail. "
            f"EOCD64 at offset {zip64_eocd_offset}"
        )

    sig = b"\x50\x4b\x05\x06"
    pos = data.rfind(sig)
    if pos == -1:
        raise ValueError("EOCD signature not found")
    cd_size = struct.unpack_from("<I", data, pos + 12)[0]
    cd_offset = struct.unpack_from("<I", data, pos + 16)[0]
    return cd_offset, cd_size


def parse_zip64_extra(
    extra_data: bytes, compressed_size: int, local_offset: int,
) -> tuple[int, int]:
    """Parse ZIP64 extra field to get real compressed_size and local_offset."""
    pos = 0
    while pos + 4 <= len(extra_data):
        tag = struct.unpack_from("<H", extra_data, pos)[0]
        size = struct.unpack_from("<H", extra_data, pos + 2)[0]
        if tag == 0x0001:
            field_pos = pos + 4
            if compressed_size == 0xFFFFFFFF and field_pos + 8 <= pos + 4 + size:
                # skip uncompressed size first
                field_pos += 8
            if compressed_size == 0xFFFFFFFF and field_pos + 8 <= pos + 4 + size:
                compressed_size = struct.unpack_from("<Q", extra_data, field_pos)[0]
                field_pos += 8
            if local_offset == 0xFFFFFFFF and field_pos + 8 <= pos + 4 + size:
                local_offset = struct.unpack_from("<Q", extra_data, field_pos)[0]
            return compressed_size, local_offset
        pos += 4 + size
    return compressed_size, local_offset


def parse_central_directory(data: bytes) -> dict[str, tuple[int, int]]:
    """Parse central directory entries. Returns {filename: (offset, size)}."""
    entries = {}
    sig = b"\x50\x4b\x01\x02"
    pos = 0
    while pos < len(data):
        if data[pos : pos + 4] != sig:
            break
        compressed_size = struct.unpack_from("<I", data, pos + 20)[0]
        fname_len = struct.unpack_from("<H", data, pos + 28)[0]
        extra_len = struct.unpack_from("<H", data, pos + 30)[0]
        comment_len = struct.unpack_from("<H", data, pos + 32)[0]
        local_offset = struct.unpack_from("<I", data, pos + 42)[0]
        fname = data[pos + 46 : pos + 46 + fname_len].decode("utf-8", errors="replace")
        extra_data = data[pos + 46 + fname_len : pos + 46 + fname_len + extra_len]
        if compressed_size == 0xFFFFFFFF or local_offset == 0xFFFFFFFF:
            compressed_size, local_offset = parse_zip64_extra(
                extra_data, compressed_size, local_offset,
            )
        entries[fname] = (local_offset, compressed_size)
        pos += 46 + fname_len + extra_len + comment_len
    return entries


def download_track(url: str, local_offset: int, compressed_size: int) -> bytes:
    """Download a single file from the zip by reading its local header + data."""
    header = fetch_range(url, local_offset, local_offset + 29)
    if header[:4] != b"\x50\x4b\x03\x04":
        raise ValueError("Bad local file header")
    fname_len = struct.unpack_from("<H", header, 26)[0]
    extra_len = struct.unpack_from("<H", header, 28)[0]
    data_start = local_offset + 30 + fname_len + extra_len
    data_end = data_start + compressed_size - 1
    return fetch_range(url, data_start, data_end)


def get_seeded_track_ids() -> list[int]:
    """Get track IDs from our seeded FMA fragments in MongoDB."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        import pymongo
        mongo = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"])
        db = mongo["pocketproducer"]
        docs = db.fragments.find(
            {"user_id": "real_audio", "source.dataset": "FMA"},
            {"source.track_id": 1},
        )
        ids = [doc["source"]["track_id"] for doc in docs]
        mongo.close()
        return ids
    except Exception as e:
        print(f"WARNING: Could not read from MongoDB ({e}), using fallback")
        return []


def main():
    parser = argparse.ArgumentParser(description="Download FMA tracks via range requests")
    parser.add_argument("--count", type=int, default=100, help="Max tracks (default 100)")
    parser.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT), help="Output directory")
    parser.add_argument("--dry-run", action="store_true", help="List tracks without downloading")
    args = parser.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    seeded_ids = get_seeded_track_ids()
    print(f"Found {len(seeded_ids)} seeded track IDs in MongoDB")

    print("Getting zip file size...")
    zip_size = get_zip_size(FMA_ZIP_URL)
    print(f"Zip size: {zip_size / 1e9:.1f} GB")

    print("Reading zip tail to find central directory...")
    tail_size = 1 * 1024 * 1024
    tail = fetch_range(FMA_ZIP_URL, zip_size - tail_size, zip_size - 1)

    cd_offset, cd_size = parse_eocd(tail)
    print(f"Central directory: offset={cd_offset}, size={cd_size / 1e6:.1f} MB")

    print(f"Fetching central directory ({cd_size / 1e6:.1f} MB)...")
    cd_data = fetch_range(FMA_ZIP_URL, cd_offset, cd_offset + cd_size - 1)

    entries = parse_central_directory(cd_data)
    mp3_entries = {k: v for k, v in entries.items() if k.endswith(".mp3")}
    print(f"Found {len(mp3_entries)} mp3 files in zip")

    if seeded_ids:
        target_filenames = {}
        for tid in seeded_ids:
            fname = f"fma_small/{tid // 1000:03d}/{tid:06d}.mp3"
            if fname in mp3_entries:
                target_filenames[fname] = mp3_entries[fname]

        print(f"Matched {len(target_filenames)} tracks to seeded IDs")
        tracks_to_download = list(target_filenames.items())[:args.count]
    else:
        tracks_to_download = list(mp3_entries.items())[:args.count]

    print(f"\nWill download {len(tracks_to_download)} tracks")

    total_bytes = sum(v[1] for _, v in tracks_to_download)
    print(f"Estimated download: {total_bytes / 1e6:.0f} MB")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for fname, (offset, size) in tracks_to_download[:10]:
            print(f"  {fname} ({size / 1e3:.0f} KB)")
        if len(tracks_to_download) > 10:
            print(f"  ... and {len(tracks_to_download) - 10} more")
        return

    downloaded = 0
    failed = 0
    for i, (fname, (offset, csize)) in enumerate(tracks_to_download):
        out_path = out_dir / pathlib.Path(fname).name
        if out_path.exists():
            downloaded += 1
            continue

        try:
            audio_data = download_track(FMA_ZIP_URL, offset, csize)
            out_path.write_bytes(audio_data)
            downloaded += 1
        except Exception as e:
            print(f"  FAILED {fname}: {e}")
            failed += 1

        if (i + 1) % 10 == 0 or i + 1 == len(tracks_to_download):
            print(f"  {i + 1}/{len(tracks_to_download)} downloaded")

    print(f"\nDone: {downloaded} downloaded, {failed} failed")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
