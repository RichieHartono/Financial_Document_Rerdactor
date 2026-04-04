import pandas as pd
import ast
from collections import defaultdict
from pdf_redactor import get_regex_entities
from pathlib import Path

IOU_THRESHOLD = 0.5
BASE_DIR = Path(__file__).resolve().parent
CSV_TEST = BASE_DIR / "Datasets" / "Testing_Set_1.csv"

def compute_overlap(a, b):
    overlap = max(0, min(a['end'], b['end']) - max(a['start'], b['start']))
    union = max(a['end'], b['end']) - min(a['start'], b['start'])
    return overlap / union if union > 0 else 0

def evaluate(dataset_path):
    result = []
    df = pd.read_csv(dataset_path)

    global_TP = global_FP = global_FN = 0

    # per label stats
    stats = defaultdict(lambda: {"TP": 0, "FP": 0, "FN": 0})

    for _, row in df.iterrows():
        text = row["text"]
        true_entities = ast.literal_eval(row["True Predictions"])

        truths = [
            {"start": t[0], "end": t[1], "label": t[2]}
            for t in true_entities
        ]

        preds = get_regex_entities(text)

        matched_pred = set()
        matched_true = set()

        for i, p in enumerate(preds):
            for j, t in enumerate(truths):
                if compute_overlap(p, t) >= IOU_THRESHOLD and p["label"] == t["label"]:
                    matched_pred.add(i)
                    matched_true.add(j)

                    stats[p["label"]]["TP"] += 1

        # FP
        for i, p in enumerate(preds):
            if i not in matched_pred:
                stats[p["label"]]["FP"] += 1

        # FN
        for j, t in enumerate(truths):
            if j not in matched_true:
                stats[t["label"]]["FN"] += 1

        # global
        global_TP += len(matched_pred)
        global_FP += len(preds) - len(matched_pred)
        global_FN += len(truths) - len(matched_true)

    # =========================
    # GLOBAL METRICS
    # =========================
    precision = global_TP / (global_TP + global_FP) if global_TP + global_FP else 0
    recall = global_TP / (global_TP + global_FN) if global_TP + global_FN else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    accuracy = global_TP / (global_TP + global_FP + global_FN) if (global_TP + global_FP + global_FN) else 0

    result.append({
            "Label": "Combined Result",
            "Precision": precision,
            "Recall": recall,
            "F1": f1
        })
    
    print("\n=== REGEX GLOBAL PERFORMANCE ===")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print(f"Accuracy:  {accuracy:.4f}")

    # =========================
    # PER LABEL METRICS
    # =========================
    print("\n=== PER-ENTITY PERFORMANCE ===")

    for label, s in stats.items():
        TP, FP, FN = s["TP"], s["FP"], s["FN"]

        p = TP / (TP + FP) if TP + FP else 0
        r = TP / (TP + FN) if TP + FN else 0
        f = 2 * p * r / (p + r) if p + r else 0

        print(f"\n[{label}]")
        print(f"  Precision: {p:.4f}")
        print(f"  Recall:    {r:.4f}")
        print(f"  F1 Score:  {f:.4f}")

        result.append({
            "Label": label,
            "Precision": p,
            "Recall": r,
            "F1": f
        })

    return result


if __name__ == "__main__":
    result = evaluate(CSV_TEST)
    pd.DataFrame(result).to_csv(BASE_DIR / "regex_evaluation_results.csv", index=False)
    print("\nEvaluation complete. Results saved to regex_evaluation_results.csv")