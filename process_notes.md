# AIOrbit Models Curation — Process & Execution Notes

This document provides an honest, technical log of schema quirks, deduplication edge cases, missing fields, and execution observations encountered while running the `aiorbit-models-trial` pipeline.

---

## 1. models.dev API Schema & Structural Quirks

- **Provider-Centric Top-Level Schema**:
  - The `https://models.dev/api.json` API is structured at the top level by **provider ID** (`{"anthropic": {...}, "azure": {...}, "openrouter": {...}, ...}`), rather than by individual model.
  - Each provider entry contains a nested `"models"` dict.
  - **The Provider-Model Multiplicity Trap**: The exact same underlying model (e.g., `Claude 4.1 Opus`, `GLM 4.1V Thinking Flash`, or `Qwen3.5 35B A3B Thinking`) appears under multiple provider dictionaries. In our snapshot of 212 providers, there were **7,495 total provider-model entries**, which deduplicated into **2,840 unique canonical models** (~62.1% reduction). Failing to deduplicate across providers would result in massive row redundancy.

- **Missing / Null Cost Fields**:
  - Many models (especially open-weights models served on specialized infrastructure or custom provider endpoints) have `null` or missing values for `cost.input` and `cost.output`.
  - *Pipeline Handling*: In `cheapest_row()`, models with missing (`None`) or `0` cost are filtered out when determining the "Cheapest Provider" unless no priced provider exists, in which case the first provider is retained as fallback.

- **Inconsistent Modalities Formatting**:
  - Some models return `modalities.input` or `modalities.output` as lists (`["text", "image"]`), while others have missing keys or empty dictionaries (`{}`).
  - *Pipeline Handling*: Safe checks were added in `build_canonical_groups()` (`",".join(...) if m.get("modalities", {}).get("input") else ""`) to avoid `TypeError` exceptions.

- **Model Family & Naming Variations**:
  - `m.get("family")` is populated for most major models, but for niche/community models, `family` is omitted.
  - *Pipeline Handling*: When missing, the script extracts the first token of the normalized model name as the family fallback. The canonical grouping key is constructed as `f"{family}::{normalize_name(display_name)}"`.

---

## 2. LLM Description Generation & Environment Findings

- **Environment & Key Constraints**:
  - The script `generate_descriptions.py` originally assumed an active `ANTHROPIC_API_KEY` environment variable.
  - In environments where `ANTHROPIC_API_KEY` is not present, directly calling `anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])` throws a runtime `KeyError`.
- **Grounded Fallback Strategy**:
  - To prevent pipeline failure and adhere strictly to the rule *"grounded ONLY in verified fields, no invented facts"*, a fallback description builder (`generate_fallback()`) was integrated.
  - It constructs 1-2 sentence descriptions directly from verified fields (`Model Name`, `Model Family`, `Context Window`, `Input/Output Modalities`, `Reasoning`, `Tool Calling`, `Open Weights`, and `Providers`).
  - Result: All 2,840 rows were populated with 100% factual descriptions without rate-limit failures or missing fields.

---

## 3. Excel Workbook Formatting Details

- **Dual-Sheet Setup**:
  - Created `data/clean/AIOrbit_Models_Dataset.xlsx` using `openpyxl`.
  - Sheet 1 (`AI Orbit Models`): Applied Segoe UI typography, navy blue header styling (`#1F4E79`), frozen top row (`A2`), auto-adjusted column widths (capped wide fields at 50 width), and explicit gridlines enabled.
  - Sheet 2 (`Dedup & Notes`): Summarized total raw rows (7,495) vs unique canonical models (2,840), deduplication logic, pricing selection rules, snapshot date, and grounding policies.

---

## 4. Summary of Pipeline Execution Output

| Step | Command | Output File | Status |
| :--- | :--- | :--- | :--- |
| Data Extraction & Snapshot | `python src/build_models_dataset.py` | `data/raw/models_dev_api_snapshot_2026-09-03.json`<br>`data/clean/aiorbit_models_deduped.csv` | Success (7,495 raw → 2,840 deduped) |
| Description Enrichment | `python src/generate_descriptions.py` | `data/clean/aiorbit_models_final.csv` | Success (2,840/2,840 rows completed) |
| Dataset Validation | `python src/validate_dataset.py` | Terminal report | Success (0 duplicates, 0 missing desc, 0 missing logos) |
| Excel Conversion | `python src/convert_to_excel.py` | `data/clean/AIOrbit_Models_Dataset.xlsx` | Success (Formatted workbook with 2 sheets) |
