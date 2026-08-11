# Data Credits & Attribution

This project uses the following external datasets and models. 声明与实际使用不符时,以本文件收紧后的口径为准;`manifest.jsonl` 类文件由脚本生成,禁止手改。

## Freesound Loop Dataset (FSLD)

Weak-pretraining audio loops with per-item licenses.

- **Source**: [Zenodo record 3967852](https://zenodo.org/records/3967852) — Ramires et al., *The Freesound Loop Dataset and Annotation Tool*, ISMIR 2020
- **Dataset record license**: CC BY 4.0;**逐条音频各有独立许可**(不把 "Creative Commons" 当统一许可)
- **Per-item manifest**: `research/data/fsld/manifest.jsonl`(9,493 条,由 `research/build_fsld_manifest.py` 生成,可复现)
- **分类结果**: cc-by 4,827 / cc0 3,230 / cc-by-nc 1,215 / sampling-plus 221;unknown 0
- **用途边界**:
  - `research_ok`(全部 9,493):weak 预训练与离线分析;
  - `redistribution_ok`(8,057 = cc0 + cc-by):可进入公开 artifact,cc-by 需署名(manifest 含 `username`);
  - cc-by-nc 与 sampling-plus:**不进入**商业演示、可再分发数据包或产品路径。
- 2,795 条带人工标注(bpm、key/mode、拍号、流派、乐器角色),用作 weak pairs 结构化特征与 hard-negative 池
- FSLD 不作为 continuation utility 的人类测试真值(评估协议)

## Models

- **MS-CLAP 2023** — [microsoft/CLAP](https://github.com/microsoft/CLAP),代码 MIT;权重 revision 以 sha256 锁定并写入每条表示与 `style_scores`。用途:离线 audio/text embedding、zero-shot 风格打分;不在同步排序请求路径调用。权重/训练数据商用条款产品化前需再次人工核验。
- **Voyage voyage-3** — API 文本表示(遗留);既有向量冻结为 `text-only-v1` 基线,新用途仅限 intent query 编码。
- **Gemini (Vertex AI)** — 遗留 ingestion 的 tagging/叙事;输出保留为历史元数据,不作为排序真值,比赛关键路径不依赖。

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
