# AIOrbit Models Dataset Curation & Pipeline

An automated data pipeline for fetching, deduplicating, enriching, and exporting the complete AI models catalog from [models.dev](https://models.dev).

## 📊 Dataset Overview & Statistics

- **Source API**: [https://models.dev/api.json](https://models.dev/api.json)
- **Snapshot Date**: September 3, 2026 (`2026-09-03`)
- **Raw Provider-Model Rows**: 7,495 entries across 212 providers
- **Clean Deduplicated Models**: **2,840** unique underlying model records
- **Deduplication Reduction**: ~62.1% row reduction (eliminates duplicate rows across providers serving the exact same model)
- **Zero Incomplete Descriptions**: 2,840 / 2,840 records contain grounded descriptions
- **Zero Missing Logos**: 2,840 / 2,840 records contain official provider logo URLs

---

## 📁 Repository Structure

```
aiorbit-models-trial/
├── data/
│   ├── raw/
│   │   └── models_dev_api_snapshot_2026-09-03.json
│   └── clean/
│       ├── aiorbit_models_deduped.csv
│       ├── aiorbit_models_final.csv
│       └── AIOrbit_Models_Dataset.xlsx
├── src/
│   ├── build_models_dataset.py
│   ├── generate_descriptions.py
│   ├── convert_to_excel.py
│   └── validate_dataset.py
├── process_notes.md
└── README.md
```

---

## 🔄 Reproduction Guide

Follow these steps to reproduce the dataset from scratch:

### 1. Requirements

Ensure Python 3.9+ is installed along with required packages:

```bash
pip install requests openpyxl
```

*(Optional: `pip install anthropic` and `export ANTHROPIC_API_KEY=sk-...` if using Anthropic for description generation).*

### 2. Run Data Ingestion & Deduplication

Fetch the raw catalog snapshot from models.dev and perform provider deduplication:

```bash
python src/build_models_dataset.py
```

- **Output 1**: `data/raw/models_dev_api_snapshot_2026-09-03.json` (raw API response)
- **Output 2**: `data/clean/aiorbit_models_deduped.csv` (deduplicated base dataset)

### 3. Generate Grounded Descriptions

Add grounded, 100% factual descriptions for every deduplicated model row:

```bash
python src/generate_descriptions.py
```

- **Output**: `data/clean/aiorbit_models_final.csv`

### 4. Validate Dataset Integrity

Run the automated integrity and validation suite:

```bash
python src/validate_dataset.py
```

### 5. Export Formatted Excel Workbook

Convert the final CSV into a formatted, dual-sheet Excel file:

```bash
python src/convert_to_excel.py
```

- **Output**: `data/clean/AIOrbit_Models_Dataset.xlsx` (contains `AI Orbit Models` sheet and `Dedup & Notes` sheet).

---

## 🔗 Live Data & Google Sheets

- **Google Sheets Published Dataset**: `[PASTE_GOOGLE_SHEETS_LINK_HERE]` *(Upload `data/clean/AIOrbit_Models_Dataset.xlsx` to Google Sheets and set sharing to "Anyone with the link can view")*
