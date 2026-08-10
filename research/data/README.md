# Research Data Provenance

本目录只存放**元数据、manifest 和 fixture id**,不存放参与者音频或任何未授权音频。

## 规则

1. 每个数据文件必须能回答:来源、许可证、采集时间、处理脚本、`sha256`。
2. 参与者数据:user id 单向 hash(`participant_hash`),不存 email、OAuth token、原始 project title。
3. 公开弱监督数据(如 FSLD):逐条核验许可证,不把 "Creative Commons" 当统一许可;只使用允许研究处理的子集。
4. 同一音频的 time-stretch / pitch-shift / duplicate hash 不得跨 train/val/test split。
5. split 原则:public weak data 按 source track/pack/uploader;human study 按 participant 和 project;personal feedback 按时间。
6. `golden_pairs.jsonl` 只放合成/自有/明确授权的 fixture;见 `research/annotation-schema.md`(Task 8 创建)。

## 目录约定

```text
research/data/
├── README.md            # 本文件
├── pocketbench.jsonl    # PocketBench v1 manifest(含 dataset_hash)
├── weak_pairs.jsonl     # Layer A 弱监督对
├── pairs.jsonl          # Layer B 显式 pairwise 标注
└── heldout.jsonl        # 冻结测试集(解封前不得评估)
```

所有 evaluation artifact 写入 `artifacts/`(git-ignored 大文件),但 `dataset_hash` 与 `metrics.json` 必须可复现。
