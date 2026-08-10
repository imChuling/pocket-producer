# FSLD data directory

Large derived files are gitignored; only `manifest.jsonl` (item metadata,
licenses, pack grouping) is tracked. Everything below is reproducible from
the FSL10K archive plus the scripts in `research/`.

## Source

Freesound Loop Dataset (FSL10K): https://zenodo.org/record/3967852
Per-item licenses are recorded in `manifest.jsonl` (`license_class`:
cc-by 4,827 / cc0 3,230 / cc-by-nc 1,215 / sampling-plus 221).

## Regenerating the ignored files

```
# manifest (tracked)
backend/.venv/bin/python research/build_fsld_manifest.py

# MS-CLAP 2023 embeddings
backend/.venv/bin/python research/embed_fsld_subset.py \
  --zip research/data/fsld/FSL10K.zip \
  --out research/data/fsld/items.jsonl

# LAION-CLAP music embeddings
backend/.venv/bin/python research/embed_fsld_subset.py \
  --zip research/data/fsld/FSL10K.zip \
  --adapter laion-clap-music \
  --out research/data/fsld/items_laion-clap-music.jsonl
```

## Content hashes (sha256)

| File | sha256 |
|---|---|
| `items.jsonl` (2,558 items, MS-CLAP 1024-d) | `fc0f5bc0a7776d09917d3aec319c66a84aabdf020e1abbd7ea778599ca211543` |
| `items_laion-clap-music.jsonl` (512-d) | `8e8db7335cd053f94752075f5f60d13d1158430cee193ff9314410533181ce3e` |
| `../weak_pairs_fsld.jsonl` (1,755 pairs) | `5422993b3b48ec275d3d20b32ef219cfd84d33ebf031b263920ddee60acf5ff6` |
