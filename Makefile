PYTHON = backend/.venv/bin/python
ITEMS_LAION = research/data/fsld/items_laion-clap-music.jsonl
ITEMS_MS = research/data/fsld/items.jsonl
CHROMA = research/data/fsld/chroma.jsonl
ROLE_PROMPTS = research/data/fsld/role_prompts.json

.PHONY: reproduce check test build features fusion fusion-7sig fusion-ms alignment

reproduce: features fusion fusion-7sig fusion-ms alignment check build
	@echo "=== All artifacts reproduced and verified ==="

features: $(CHROMA) $(ROLE_PROMPTS)

$(CHROMA) $(ROLE_PROMPTS): $(ITEMS_LAION)
	$(PYTHON) research/extract_fsld_features.py \
		--items $(ITEMS_LAION) \
		--output-chroma $(CHROMA) \
		--output-role-prompts $(ROLE_PROMPTS)

fusion: $(ITEMS_LAION)
	$(PYTHON) research/run_fusion.py \
		--items $(ITEMS_LAION) \
		--output artifacts/fusion

fusion-7sig: features $(ITEMS_LAION)
	$(PYTHON) research/run_fusion.py \
		--items $(ITEMS_LAION) \
		--chroma $(CHROMA) \
		--role-prompts $(ROLE_PROMPTS) \
		--output artifacts/fusion-7sig

fusion-ms: features $(ITEMS_MS)
	$(PYTHON) research/run_fusion.py \
		--items $(ITEMS_MS) \
		--chroma $(CHROMA) \
		--role-prompts $(ROLE_PROMPTS) \
		--output artifacts/fusion-msclap

alignment:
	$(PYTHON) research/human_signal_alignment.py

check:
	python3 research/check_paper_numbers.py

test:
	$(PYTHON) -m pytest backend/tests/ranking/test_features.py \
		backend/tests/ranking/test_harmonic.py \
		backend/tests/ranking/test_role_probe.py \
		backend/tests/ranking/test_fusion.py -v

build:
	docs/ismir2026/build.sh
