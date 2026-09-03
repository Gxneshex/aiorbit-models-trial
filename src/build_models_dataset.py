"""
AIOrbit Models Module — models.dev pipeline (v2)
--------------------------------------------------
Fixes over v1:
 1. Dedup now keys off a NORMALIZED CORE MODEL ID (strips vendor prefixes,
    version/date suffixes, quantization tags) instead of raw display name,
    so "Claude Haiku 4.5 (Anthropic)" and "Claude Haiku 4.5" collapse into
    ONE row instead of two.
 2. Adds a quality filter: drops rows that are ONLY served by marketplace
    resellers under a rebranded/prefixed name (e.g. "Azure gpt-4-turbo" via
    nano-gpt, "SpaceXAI: Grok 4.20" via kilo) and drops obvious community
    fine-tune spam (name contains "unslop", "abliterated", "uncensored",
    etc.) and router/meta-models (family == "auto").
 3. Reports real before/after numbers so you can see what got removed
    and why, per the guideline requirement to document curation decisions.

Run: python src/build_models_dataset.py
"""

import json
import csv
import re
import datetime
from collections import defaultdict

import requests

API_URL = "https://models.dev/api.json"
LOGO_URL = "https://models.dev/logos/{provider}.svg"

RAW_SNAPSHOT_PATH = f"data/raw/models_dev_api_snapshot_{datetime.date.today()}.json"
OUTPUT_CSV = "data/clean/aiorbit_models_deduped.csv"
REJECTED_LOG = "data/clean/rejected_rows_log.csv"

JUNK_NAME_PATTERNS = [
    r"\bunslop\b", r"\babliterated\b", r"\buncensored\b", r"\bnsfw\b",
    r"\brp[- ]?v\d", r"\bwaifu\b", r"\berotic\b",
]

RESELLER_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9]+:\s|\(NovitaAI\)|\(Anthropic\)$")

META_FAMILIES = {"auto", "model-router"}


def normalize_display(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\(latest\)", "", n)
    n = re.sub(r"\((anthropic|novitaai|openai|google)\)", "", n)
    n = re.sub(r"[^a-z0-9]+", " ", n).strip()
    return n


def normalize_core_id(model_id: str) -> str:
    n = model_id.lower()
    n = n.split("/")[-1]
    n = re.sub(r"^(anthropic|openai|google|meta|mistral|cohere|deepseek|qwen)\.", "", n)
    n = re.sub(r"[-:]v?\d+:\d+$", "", n)
    n = re.sub(r"-\d{8}$", "", n)
    n = re.sub(r"-latest$", "", n)
    n = re.sub(r"-(fp16|fp8|int8|int4|awq|gptq|bf16)$", "", n)
    return n


def is_junk_name(name: str) -> bool:
    lname = name.lower()
    return any(re.search(pat, lname) for pat in JUNK_NAME_PATTERNS)


def fetch_catalog() -> dict:
    resp = requests.get(API_URL, timeout=30, headers={"User-Agent": "AIOrbit-trial-script/2.0"})
    resp.raise_for_status()
    return resp.json()


def build_canonical_groups(catalog: dict):
    groups = defaultdict(lambda: {"providers": set(), "rows": [], "names_seen": set()})
    rejected = []

    for provider_id, provider_data in catalog.items():
        for model_id, m in provider_data.get("models", {}).items():
            display_name = m.get("name") or model_id
            family = (m.get("family") or normalize_display(display_name).split()[0]).lower()

            if family in META_FAMILIES:
                rejected.append((display_name, provider_id, "meta/router pseudo-model"))
                continue
            if is_junk_name(display_name):
                rejected.append((display_name, provider_id, "junk/spam name pattern"))
                continue

            core_id = normalize_core_id(model_id)
            key = f"{family}::{core_id}"

            groups[key]["providers"].add(provider_id)
            groups[key]["names_seen"].add(display_name)
            groups[key]["family"] = family
            groups[key]["rows"].append({
                "provider": provider_id,
                "model_id": model_id,
                "display_name": display_name,
                "input_cost": m.get("cost", {}).get("input"),
                "output_cost": m.get("cost", {}).get("output"),
                "context_limit": m.get("limit", {}).get("context"),
                "output_limit": m.get("limit", {}).get("output"),
                "reasoning": m.get("reasoning"),
                "tool_call": m.get("tool_call"),
                "modalities_input": ",".join(m.get("modalities", {}).get("input", [])),
                "modalities_output": ",".join(m.get("modalities", {}).get("output", [])),
                "open_weights": m.get("open_weights"),
                "release_date": m.get("release_date"),
                "last_updated": m.get("last_updated"),
            })

    final_groups = {}
    for key, g in groups.items():
        clean_name_exists = any(not RESELLER_PREFIX_PATTERN.search(n) for n in g["names_seen"])
        if not clean_name_exists:
            for r in g["rows"]:
                rejected.append((r["display_name"], r["provider"], "reseller-only rebrand, no clean source name in group"))
            continue
        final_groups[key] = g

    return final_groups, rejected


def best_display_name(g):
    clean = [n for n in g["names_seen"] if not RESELLER_PREFIX_PATTERN.search(n)]
    pool = clean if clean else list(g["names_seen"])
    return min(pool, key=len)


def cheapest_row(rows):
    priced = [r for r in rows if r["input_cost"] not in (None, 0)]
    if not priced:
        return rows[0]
    return min(priced, key=lambda r: r["input_cost"])


def main():
    print("Fetching models.dev catalog...")
    catalog = fetch_catalog()
    total_raw = sum(len(p.get("models", {})) for p in catalog.values())
    print(f"Providers found: {len(catalog)}")
    print(f"Total raw provider-model entries: {total_raw}")

    with open(RAW_SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f)
    print(f"Saved raw untouched API snapshot to {RAW_SNAPSHOT_PATH}")

    groups, rejected = build_canonical_groups(catalog)

    # --- Final merge pass: collapse groups that share the same clean
    # display name, since different providers format model IDs
    # inconsistently enough that the core-ID key alone under-merges. ---
    merged = {}
    for key, g in groups.items():
        name_key = normalize_display(best_display_name(g))
        if name_key in merged:
            merged[name_key]["providers"] |= g["providers"]
            merged[name_key]["rows"].extend(g["rows"])
            merged[name_key]["names_seen"] |= g["names_seen"]
        else:
            merged[name_key] = g
    groups = merged
    print(f"Unique canonical models after dedup + quality filter: {len(groups)}")
    print(f"Rows rejected (junk/meta/reseller-only): {len(rejected)}")

    fieldnames = [
        "Model Name", "Model Family", "Providers (dedup list)", "Num Providers",
        "Cheapest Provider", "Input Cost per 1M ($)", "Output Cost per 1M ($)",
        "Context Window", "Max Output", "Reasoning", "Tool Calling",
        "Input Modalities", "Output Modalities", "Open Weights",
        "Release Date", "Last Updated", "Official Provider Logo URL",
        "Description (fill in via LLM)"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for key, g in groups.items():
            best = cheapest_row(g["rows"])
            unique_providers = sorted(g["providers"])
            writer.writerow({
                "Model Name": best_display_name(g),
                "Model Family": g["family"],
                "Providers (dedup list)": "; ".join(unique_providers),
                "Num Providers": len(unique_providers),
                "Cheapest Provider": best["provider"],
                "Input Cost per 1M ($)": best["input_cost"],
                "Output Cost per 1M ($)": best["output_cost"],
                "Context Window": best["context_limit"],
                "Max Output": best["output_limit"],
                "Reasoning": best["reasoning"],
                "Tool Calling": best["tool_call"],
                "Input Modalities": best["modalities_input"],
                "Output Modalities": best["modalities_output"],
                "Open Weights": best["open_weights"],
                "Release Date": best["release_date"],
                "Last Updated": best["last_updated"],
                "Official Provider Logo URL": LOGO_URL.format(provider=best["provider"]),
                "Description (fill in via LLM)": "",
            })

    with open(REJECTED_LOG, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Display Name", "Provider", "Rejection Reason"])
        writer.writerows(rejected)

    print(f"Wrote {len(groups)} rows to {OUTPUT_CSV}")
    print(f"Wrote rejection log ({len(rejected)} rows) to {REJECTED_LOG}")
    print("Review rejected_rows_log.csv before final submission -- spot check")
    print("a sample to make sure the filter isn't dropping anything legitimate.")


if __name__ == "__main__":
    main()