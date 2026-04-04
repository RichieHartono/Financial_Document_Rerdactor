import spacy
import pandas as pd
import ast
from spacy.training import Example
from spacy.scorer import Scorer
from pathlib import Path

# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent

CSV_TEST = BASE_DIR / "Datasets" / "Testing_Set_1.csv"
MODEL_PATH = BASE_DIR / "models" / "output3" / "model-best"

OUTPUT_FILE = BASE_DIR / "Eval" / "ner_2_model_results.csv"

# =========================
# HELPERS
# =========================

def merge_overlapping_entities(entities):
    if not entities:
        return []

    entities = sorted(entities, key=lambda x: x[0])
    merged = []
    cur_start, cur_end, cur_label = entities[0]

    for start, end, label in entities[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
        else:
            merged.append((cur_start, cur_end, cur_label))
            cur_start, cur_end, cur_label = start, end, label

    merged.append((cur_start, cur_end, cur_label))
    return merged


def clean_entities(nlp, text, entities):
    doc = nlp.make_doc(text)
    clean = []

    for start, end, label in entities:
        span = doc.char_span(start, end, label=label, alignment_mode="contract")
        if span:
            clean.append((span.start_char, span.end_char, label))

    return clean


def load_test_data(csv_path, nlp):
    df = pd.read_csv(csv_path)

    test_data = []
    for _, row in df.iterrows():
        text = row["text"]
        entities = ast.literal_eval(row["True Predictions"])

        entities = merge_overlapping_entities(entities)
        entities = clean_entities(nlp, text, entities)

        test_data.append((text, {"entities": entities}))

    return test_data


def evaluate_model(nlp, test_data):
    scorer = Scorer()
    examples = []

    for text, annotations in test_data:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)

        predicted_doc = nlp(text)
        example.predicted = predicted_doc

        examples.append(example)

    return scorer.score(examples)


# =========================
# MAIN
# =========================

def main():
    print("Loading model...")
    nlp = spacy.load(MODEL_PATH)

    print("Loading test data...")
    test_data = load_test_data(CSV_TEST, nlp)

    print(f"Loaded {len(test_data)} samples\n")

    print("Evaluating model...\n")
    scores = evaluate_model(nlp, test_data)

    # =========================
    # COMBINED
    # =========================
    precision = scores.get("ents_p", 0.0)
    recall = scores.get("ents_r", 0.0)
    f1 = scores.get("ents_f", 0.0)

    print("=== COMBINED PERFORMANCE ===")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")

    results = []

    results.append({
        "Label": "Combined Result",
        "Precision": precision,
        "Recall": recall,
        "F1": f1
    })

    # =========================
    # PER ENTITY
    # =========================
    print("\n=== PER-ENTITY PERFORMANCE ===")

    if "ents_per_type" in scores:
        for label, metrics in scores["ents_per_type"].items():
            p = metrics.get("p", 0.0)
            r = metrics.get("r", 0.0)
            f = metrics.get("f", 0.0)

            print(f"\n[{label}]")
            print(f"  Precision: {p:.4f}")
            print(f"  Recall:    {r:.4f}")
            print(f"  F1 Score:  {f:.4f}")

            results.append({
                "Label": label,
                "Precision": p,
                "Recall": r,
                "F1": f
            })

    # =========================
    # SAVE
    # =========================
    pd.DataFrame(results).to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved results to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()