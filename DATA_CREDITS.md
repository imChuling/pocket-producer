# Data Credits & Attribution

This project uses the following external datasets and models. When in doubt, the per-item manifest is authoritative; manifest files are script-generated and must not be hand-edited.

## Freesound Loop Dataset (FSLD)

Weak-pretraining audio loops with per-item licenses.

- **Source**: [Zenodo record 3967852](https://zenodo.org/records/3967852) — Ramires et al., *The Freesound Loop Dataset and Annotation Tool*, ISMIR 2020
- **Dataset record license**: CC BY 4.0. Each audio file carries its own license (the dataset-level CC BY does not override individual track licenses).
- **Per-item manifest**: `research/data/fsld/manifest.jsonl` (9,493 items). Not tracked in git (`research/data/fsld/.gitignore`); regenerated locally by `research/build_fsld_manifest.py` from the FSL10K metadata.
- **License breakdown**: CC-BY 4,827 / CC0 3,230 / CC-BY-NC 1,215 / Sampling+ 221 / Unknown 0
- **Usage scope**:
  - All 9,493 items: research, weak pretraining, offline analysis
  - 8,057 items (CC0 + CC-BY): eligible for redistribution; CC-BY items require attribution (manifest includes `username`)
  - CC-BY-NC and Sampling+: marked `research_ok` by `research/build_fsld_manifest.py` and used in research and training; not redistributed (no FSLD audio, embeddings or derived per-item files are in this repository)
- **Training set behind the served weights**: `artifacts/fusion-deploy/weights.json` was fitted on the pack-only train split (1,389 loops): CC-BY 635, CC0 547, CC-BY-NC 129, Sampling+ 78. The full pack-only set (1,797 loops, train plus held-out) has 263 CC-BY-NC or Sampling+ loops. The served file contains five weights, not audio or embeddings.
- 2,795 items carry human annotations (BPM, key/mode, time signature, genre, instrument role), used for weak-pair structured features and hard-negative sampling. 2,559 of them are marked well-cut (all `research_ok`); 2,558 of those are in the embedding files (`items.jsonl`, `items_laion-clap-music.jsonl`), and that is the "2,558 annotated items" count used elsewhere.
- FSLD is not used as ground truth for continuation-utility human evaluation

## Pretrained models, code and services

Licences as stated at each primary source, checked 2026-11-17. Where a
source states no licence, or two sources disagree, that is recorded as
found.

- **MS-CLAP 2023** ([microsoft/CLAP](https://github.com/microsoft/CLAP)). Code: MIT ([LICENSE](https://github.com/microsoft/CLAP/blob/main/LICENSE)). Weights `CLAP_weights_2023.pth`: MS-PL on the [Hugging Face card](https://huggingface.co/microsoft/msclap); the same file on [Zenodo record 8378278](https://zenodo.org/record/8378278) is listed as CC BY 3.0 US. The weight revision is SHA-256-locked and recorded in every stored representation. Used at ingest, by `/session-embed`, to encode typed intent for `audio-cosine-v1`, and in research.
- **LAION-CLAP** ([LAION-AI/CLAP](https://github.com/LAION-AI/CLAP)). Code: CC0-1.0 ([LICENSE](https://github.com/LAION-AI/CLAP/blob/main/LICENSE)). Checkpoint `music_audioset_epoch_15_esc_90.14.pt`: CC0-1.0 per the [Hugging Face card](https://huggingface.co/lukewys/laion_clap). Research only.
- **MERT-v1-95M** ([m-a-p/MERT-v1-95M](https://huggingface.co/m-a-p/MERT-v1-95M)). CC BY-NC 4.0 per the model card. Research only.
- **COCOLA** ([gladia-research-group/cocola](https://github.com/gladia-research-group/cocola)). Code: MIT ([LICENSE](https://github.com/gladia-research-group/cocola/blob/main/LICENSE)). `COCOLA_HP_v1` checkpoint: licence not confirmed (linked from the repository README on Google Drive with no licence statement). Evaluation only, loaded from a separate checkout.
- **Voyage `voyage-3`**: hosted API, governed by the provider's [terms of service](https://www.voyageai.com/tos). Text embeddings for fragments (used by grouping vector search) and typed intent, and the frozen `text-only-v1` baseline.
- **Gemini on Vertex AI**: hosted API, governed by the [Google Cloud terms](https://cloud.google.com/terms) and [service-specific terms](https://cloud.google.com/terms/service-terms). Ingest tagging, intent parsing, the grouping agents, and project titles, narratives and next actions. Outputs are not used as ranking ground truth.
- **`@audiotool/nexus`** (npm). The [registry metadata](https://registry.npmjs.org/@audiotool/nexus) and the package's `package.json` say MIT; the repository's [LICENSE file](https://github.com/audiotool/nexus/blob/HEAD/LICENSE) is Apache-2.0. `frontend/patches/` applies a local patch to the installed package.
- **Freesound previews** (downloaded through the Freesound API for the MERT embeddings): governed by the [Freesound API terms of use](https://freesound.org/help/tos_api/); each sound keeps the Creative Commons licence its uploader chose, recorded per item in the manifest.

## Multitrack datasets (behavioural tests and retrieval)

Used for evaluation only. No audio, stems or features from these datasets
are distributed in this repository; it holds aggregate results and, for
MUSDB18-HQ, the track names and file hashes that identify the evaluated set.

- **MUSDB18-HQ** (Rafii, Liutkus, Stöter, Mimilakis and Bittner, 2019),
  Zenodo record 3338373. Released for educational and non-commercial use;
  see the record for the terms of the individual tracks.
- **BabySlakh**, a 20-track subset of **Slakh2100** (Manilow, Wichern,
  Seetharaman and Le Roux, 2019), Zenodo record 4603870, CC BY 4.0. Used as
  the development set.
- **COCOLA** (Ciranni et al., 2025): the released `COCOLA_HP_v1` checkpoint
  is loaded from a separate checkout of the authors' repository and is not
  included here.

## Demo account audio

The read-only demo account plays royalty-free loops from Looperman, named by
their original titles. The audio is not part of this repository. The lyrics,
tags, suggestions, project groupings and next actions shown with them are
sample text written for the demo.

## Free Music Archive (FMA)

Audio metadata (track titles, genres, BPM, key, energy, danceability, etc.)

- **Repository**: https://github.com/mdeff/fma
- **Paper**: Defferrard, M., Benzi, K., Vandergheynst, P., & Bresson, X. (2017). FMA: A Dataset for Music Analysis. *ISMIR 2017*.
- **arXiv**: https://arxiv.org/abs/1612.01840
- **License**: Audio tracks are individually licensed by their artists (Creative Commons). Metadata is provided for research purposes.
- **Usage in this project**: We use only the metadata (tracks.csv, echonest.csv) — no audio files are downloaded or distributed.

## LabROSA Lyric Database (LYRICAL)

Lyrics with structural annotations (verse, chorus, bridge, etc.)

- **Repository**: https://github.com/mattmcvicar/lyric_database
- **Authors**: Matt McVicar, LabROSA (Columbia University)
- **Paper**: McVicar, M., et al. (2014). Automatic Retrieval of Music Lyrics. *Foundations and Trends in Information Retrieval*.
- **Usage in this project**: We parse structure-annotated lyrics to create text-type fragment entries. No audio is used.

## Citation

If you use or reference the seed data in this project, please cite the original authors:

```bibtex
@inproceedings{fma_dataset,
  title  = {FMA: A Dataset for Music Analysis},
  author = {Defferrard, Micha{\"e}l and Benzi, Kirell and Vandergheynst, Pierre and Bresson, Xavier},
  year   = {2017},
  booktitle = {18th International Society for Music Information Retrieval Conference (ISMIR)},
}

@article{mcvicar2014lyrics,
  title   = {Automatic Retrieval of Music Lyrics},
  author  = {McVicar, Matt and others},
  journal = {Foundations and Trends in Information Retrieval},
  year    = {2014},
}
```
