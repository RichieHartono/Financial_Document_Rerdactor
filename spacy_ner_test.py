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
# CSV_TEST = BASE_DIR / "Datasets" / "Testing_Set_2.csv"
MODEL_DIR = BASE_DIR / "models" / "test"
N_EPOCHS = 20  # number of epochs to evaluate

# =========================
# UTILITY FUNCTIONS
# =========================

def merge_overlapping_entities(entities):
    """Merge overlapping spans"""
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
    """Ensure spans align with tokenizer"""
    doc = nlp.make_doc(text)
    clean = []
    for start, end, label in entities:
        span = doc.char_span(start, end, label=label, alignment_mode="contract")
        if span:
            clean.append((span.start_char, span.end_char, label))
    return clean

def load_csv_to_test_data(csv_path, nlp):
    """Load single CSV into spaCy TEST_DATA format"""
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path.name}")
    print(df.head(5))

    test_data = []
    for _, row in df.iterrows():
        text = row["text"]
        entities = ast.literal_eval(row["True Predictions"])
        entities = merge_overlapping_entities(entities)
        entities = clean_entities(nlp, text, entities)

        test_data.append((text, {"entities": entities}))

    print(f"Total test samples: {len(test_data)}")
    return test_data

def evaluate_model(nlp, test_data):
    """Evaluate NER model on test data using spaCy Scorer"""
    scorer = Scorer()
    examples = []
    for text, annotations in test_data:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)

        predicted_doc = nlp(text)
        example.predicted = predicted_doc
        
        examples.append(example)
    scores = scorer.score(examples)
    return scores

# =========================
# MAIN EVALUATION LOOP
# =========================

if __name__ == "__main__":
    # Load dummy model to get tokenizer for cleaning
    nlp_dummy = spacy.load(MODEL_DIR / "epoch_1")
    TEST_DATA = load_csv_to_test_data(CSV_TEST, nlp_dummy)

    for i, (text, ann) in enumerate(TEST_DATA[:5]):
        print(f"Sample {i+1}:")
        print("Text:", text[:100], "...")
        print("Entities:", ann["entities"])

    results = []

    print("\n===================================")
    print("EPOCH-BY-EPOCH EVALUATION")
    print("===================================\n")

    for epoch in range(1, N_EPOCHS + 1):
        model_path = MODEL_DIR / f"epoch_{epoch}"
        print(f"Evaluating Epoch {epoch} ...")

        nlp = spacy.load(model_path)
        scores = evaluate_model(nlp, TEST_DATA)

        precision = scores.get("ents_p", 0.0)
        recall = scores.get("ents_r", 0.0)
        f1 = scores.get("ents_f", 0.0)

        results.append({
            "Epoch": epoch,
            "Precision": precision,
            "Recall": recall,
            "F1": f1
        })

        print(f"  Precision: {precision:.4f}")
        print(f"  Recall:    {recall:.4f}")
        print(f"  F1 Score:  {f1:.4f}")
        print("  Per-label scores:")
        if "ents_per_type" in scores:
            for label, metrics in scores["ents_per_type"].items():
                print(f"    {label}: P={metrics['p']:.4f} R={metrics['r']:.4f} F1={metrics['f']:.4f}")
        print("-" * 40)

    # Save results to CSV
    pd.DataFrame(results).to_csv(BASE_DIR / "ner_evaluation_results.csv", index=False)
    print("\nEvaluation complete. Results saved to ner_evaluation_results.csv")