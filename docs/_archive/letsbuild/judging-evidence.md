# Let's Build Judging Evidence

每条主张只允许用「可截图或可运行命令」证明。状态只有 `pending` / `verified`,不允许 "should work"。

## Claim ledger

| Claim | Evidence | Status |
|---|---|---|
| Reads an Audiotool project | 15s screen capture + offline fixture test | pending |
| Inserts a fragment | continuous screen capture | pending |
| Reversible (undo exact insertion) | undo test + screen capture | pending |
| Model beats recency baseline | `research/evaluate.py` JSON output | pending |
| Works without model service (rules fallback) | fallback test + capture | pending |

## Frozen environment (2026-07-30)

| Component | Version / command |
|---|---|
| Node | v24.11.1 |
| Next.js | 16.2.6 (App Router; `next lint` 已移除,lint 用 `eslint .`) |
| React | 19.2.4 |
| @audiotool/nexus | **0.0.17 exact pin**(不使用 `^`/`latest`) |
| Vitest | ^4.1.10 + jsdom + Testing Library |
| Python | 3.12.2 (`backend/.venv`) |
| Backend test | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/pytest -q` |
| Frontend check | `npm run check` = `eslint . && tsc --noEmit && vitest run` |

## Baseline verification (2026-07-30)

```text
frontend tsc --noEmit      exit 0
frontend vitest run        exit 0 (no test files yet, passWithNoTests)
backend pytest             21 passed, 1 failed, 1 error (pre-existing, see below)
frontend eslint .          5 errors, 6 warnings (pre-existing, see below)
```

## Pre-existing failures(非本冲刺引入,不计入新功能完成)

1. `backend/tests/test_api_integration.py::TestCrossRoute::test_fix_stuck_fragments` — assert 0 == 1(六月版本遗留)。
2. `backend/tests/test_memory_classification.py::test_classification` — fixture `gemini` not found;该文件是脚本式手动测试,不适配纯 pytest 运行。
3. `frontend` eslint 5 errors:`app/error.tsx` no-html-link-for-pages、`react-you-might-not-need-an-effect` / set-state-in-effect 类错误若干、impure function during render(fragment 相关旧组件)。

处理策略:冲刺期间新代码必须 0 error;上述遗留项在 08-16–08-18 polish 窗口统一清理,若届时未清理则在提交材料中不宣称 "lint clean"。
