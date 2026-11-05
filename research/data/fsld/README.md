# FSLD data directory

Derived files are gitignored; only `role_prompts.json` is tracked. The
embedding files the paper used come from `python research/fetch_embeddings.py`
(see the hash table below). Everything can also be regenerated from the
FSL10K archive plus the scripts in `research/`, but the embedding step picks
its analysis window at random, so regenerated vectors will not be identical.

## Source

Freesound Loop Dataset (FSL10K): https://zenodo.org/record/3967852
Per-item licenses are recorded in `manifest.jsonl` (`license_class`:
cc-by 4,827 / cc0 3,230 / cc-by-nc 1,215 / sampling-plus 221).

## Regenerating the ignored files

```
# manifest (tracked)
python research/build_fsld_manifest.py

# MS-CLAP 2023 embeddings
python research/embed_fsld_subset.py \
  --zip research/data/fsld/FSL10K.zip \
  --out research/data/fsld/items.jsonl

# LAION-CLAP music embeddings
python research/embed_fsld_subset.py \
  --zip research/data/fsld/FSL10K.zip \
  --adapter laion-clap-music \
  --out research/data/fsld/items_laion-clap-music.jsonl
```

## Content hashes (sha256)

These are the files `research/fetch_embeddings.py` installs here from the
`fsld-embeddings-v1` release bundle (72 MB, bundle sha256
`c08ecb191daec0efe3667efb5b79bfca536f1d3bb1289c2bc88709824dd4945c`); the script verifies each one.

| File | sha256 |
|---|---|
| `chroma.jsonl` | `4aaa1bba5bc138523f9aeb248d3286417ee47c1c949c2ecd3bfd4bd0960acd7f` |
| `items_laion-clap-music.jsonl` (2,558 items, 512-d) | `8e8db7335cd053f94752075f5f60d13d1158430cee193ff9314410533181ce3e` |
| `items_laion-clap-music_packonly.jsonl` (1,797 items) | `7995f56371bfda703d9c4045bb52834cb1880a70c19de850e3c3a7e21c0d6b1e` |
| `items_laion-clap-music_packonly_train.jsonl` | `caf253d3a0030cfdc15c990619df1e16233af208670687004530ccd36633cffe` |
| `items_mert_packonly.jsonl` (768-d) | `7f113ef15f2e43739f6c0b31b3efeb62f70ca58f5a288924acf06e136cea9355` |
| `items_msclap_packonly.jsonl` (1024-d) | `5574f40ed5645c45366068bc5a0aedf54bdafb9a0fb8692656d7b3304a201ba3` |
| `items_msclap_packonly_train.jsonl` | `3a78de4f58a01e38f0310013a115d1136ffa1ec25b61eee873f572b9787be6e0` |
| `manifest.jsonl` | `27576a06f8ac8eba3f633e5273f4acb0a0b809a0f51ba11dd8385cf3f9a63818` |
