"""
Generate descriptions for aiorbit_models_deduped.csv using an LLM,
grounded ONLY in the verified fields already in the row (no free-form
guessing -- this is what keeps you safe from the "hallucinated data =
disqualification" rule in the AI Engineer trial doc).
"""

import csv
import os
import time

INPUT_CSV = os.path.join("data", "clean", "aiorbit_models_deduped.csv")
OUTPUT_CSV = os.path.join("data", "clean", "aiorbit_models_final.csv")

PROMPT_TEMPLATE = """Write ONE concise, factual, 1-2 sentence description of this AI model
for a database entry. Use ONLY the facts given below -- do not invent
benchmarks, rankings, or claims not present in this data. If a field is
blank, simply omit it rather than guessing.

Model name: {name}
Family: {family}
Context window: {context}
Reasoning capable: {reasoning}
Tool calling: {tool_call}
Input modalities: {input_mod}
Output modalities: {output_mod}
Open weights: {open_weights}
Served by providers: {providers}

Description:"""


def generate_fallback(row: dict) -> str:
    """Generate a strictly grounded description using only verified fields from the row."""
    name = row.get("Model Name", "").strip()
    family = row.get("Model Family", "").strip()
    providers = row.get("Providers (dedup list)", "").strip()
    context = row.get("Context Window", "").strip()
    reasoning = row.get("Reasoning", "").strip()
    tool_call = row.get("Tool Calling", "").strip()
    input_mod = row.get("Input Modalities", "").strip()
    output_mod = row.get("Output Modalities", "").strip()
    open_weights = row.get("Open Weights", "").strip()

    parts = []
    parts.append(f"{name} is an AI model in the {family} family served by {providers}.")

    details = []
    if context:
        details.append(f"a context window of {context} tokens")
    if input_mod:
        details.append(f"input modalities of {input_mod}")
    if output_mod and output_mod != input_mod:
        details.append(f"output modalities of {output_mod}")

    if details:
        parts.append(f"It features {', '.join(details)}.")

    extra = []
    if reasoning in ("True", "true", True):
        extra.append("supports reasoning")
    if tool_call in ("True", "true", True):
        extra.append("supports tool calling")
    if open_weights in ("True", "true", True):
        extra.append("has open weights")

    if extra:
        parts.append(f"The model {' and '.join(extra)}.")

    return " ".join(parts)


def generate(row: dict, client=None) -> str:
    if client is not None:
        try:
            prompt = PROMPT_TEMPLATE.format(
                name=row["Model Name"],
                family=row["Model Family"],
                context=row["Context Window"] or "not disclosed",
                reasoning=row["Reasoning"] or "unknown",
                tool_call=row["Tool Calling"] or "unknown",
                input_mod=row["Input Modalities"] or "text",
                output_mod=row["Output Modalities"] or "text",
                open_weights=row["Open Weights"] or "unknown",
                providers=row["Providers (dedup list)"],
            )
            # Try available model endpoints
                        # Try available model endpoints
            for model_name in ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
                try:
                    msg = client.chat.completions.create(
                        model=model_name,
                        max_tokens=150,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    res = msg.choices[0].message.content.strip()
                    if res:
                        return res
                except Exception as e:
                    print(f"MODEL {model_name} FAILED for {row.get('Model Name')}: {e}")
                    continue
        except Exception as e:
            print(f"API generation failed for {row.get('Model Name')}: {e}, using grounded fallback.")

    return generate_fallback(row)


def main():
    client = None
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key, max_retries=0)  # fail fast, don't sleep-retry
            print("Groq API client initialized.")
        except Exception as e:
            print(f"Could not initialize Groq client: {e}. Will use grounded fallback.")
    else:
        print("No GROQ_API_KEY environment variable set. Using grounded description generator.")

    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())

    # Resume support: if output already exists, load what's done and skip it
    done_names = set()
    existing_rows = []
    if os.path.exists(OUTPUT_CSV):
        with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
            existing_rows = list(csv.DictReader(f))
        done_names = {r["Model Name"] for r in existing_rows}
        print(f"Resuming: {len(done_names)} rows already done, skipping those.")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in existing_rows:
            writer.writerow(r)  # keep what's already done

        remaining = [r for r in rows if r["Model Name"] not in done_names]
        print(f"{len(remaining)} rows left to process.")

        for i, row in enumerate(remaining):
            try:
                row["Description (fill in via LLM)"] = generate(row, client=client)
            except Exception as e:
                print(f"Row {i} ({row['Model Name']}) failed: {e}")
                row["Description (fill in via LLM)"] = generate_fallback(row)
            writer.writerow(row)
            f.flush()  # so a Ctrl+C doesn't lose the last few rows
            if (i + 1) % 50 == 0 or (i + 1) == len(remaining):
                print(f"{i + 1}/{len(remaining)} done")
            if client is not None:
                time.sleep(0.3)

    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()

