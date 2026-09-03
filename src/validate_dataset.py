"""
Validate data/clean/aiorbit_models_final.csv and produce validation metrics.
"""

import csv
import os
import random
from collections import Counter

FINAL_CSV = os.path.join("data", "clean", "aiorbit_models_final.csv")


def main():
    if not os.path.exists(FINAL_CSV):
        print(f"Error: {FINAL_CSV} does not exist.")
        return

    with open(FINAL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_rows = len(rows)
    print(f"Total row count: {total_rows}")

    # Check for duplicate Model Name + Model Family combinations
    combos = Counter()
    combo_map = {}
    for i, row in enumerate(rows):
        key = (row.get("Model Name", "").strip(), row.get("Model Family", "").strip())
        combos[key] += 1
        if key not in combo_map:
            combo_map[key] = []
        combo_map[key].append(i + 1)

    duplicates = {k: v for k, v in combos.items() if v > 1}
    print(f"\nDuplicate (Model Name, Model Family) count: {len(duplicates)}")
    if duplicates:
        print("Duplicate details:")
        for (name, family), count in duplicates.items():
            print(f"  - '{name}' (Family: '{family}') appears {count} times (rows: {combo_map[(name, family)]})")
    else:
        print("0 duplicate Model Name + Model Family combinations found.")

    # Check for missing/blank Description
    missing_desc = []
    for i, row in enumerate(rows):
        desc = row.get("Description (fill in via LLM)", "").strip()
        if not desc:
            missing_desc.append((i + 1, row.get("Model Name")))

    print(f"\nRows with missing/blank Description: {len(missing_desc)}")
    if missing_desc:
        print("Missing description rows (first 10):", missing_desc[:10])

    # Check for missing Official Provider Logo URL
    missing_logo = []
    for i, row in enumerate(rows):
        logo = row.get("Official Provider Logo URL", "").strip()
        if not logo:
            missing_logo.append((i + 1, row.get("Model Name")))

    print(f"\nRows with missing Official Provider Logo URL: {len(missing_logo)}")
    if missing_logo:
        print("Missing logo rows (first 10):", missing_logo[:10])

    # Random sample of 10 rows
    random.seed(42)
    sample_indices = sorted(random.sample(range(len(rows)), min(10, len(rows))))
    print("\nRandom sample of 10 rows:")
    for idx in sample_indices:
        r = rows[idx]
        print("-" * 60)
        print(f"Row #{idx+1}:")
        print(f"  Model Name: {r.get('Model Name')}")
        print(f"  Model Family: {r.get('Model Family')}")
        print(f"  Providers: {r.get('Providers (dedup list)')}")
        print(f"  Cheapest Provider: {r.get('Cheapest Provider')}")
        print(f"  Input Cost per 1M ($): {r.get('Input Cost per 1M ($)')}")
        print(f"  Output Cost per 1M ($): {r.get('Output Cost per 1M ($)')}")
        print(f"  Context Window: {r.get('Context Window')}")
        print(f"  Logo URL: {r.get('Official Provider Logo URL')}")
        print(f"  Description: {r.get('Description (fill in via LLM)')}")


if __name__ == "__main__":
    main()
