import spacy
import pandas as pd
import ast
from spacy.tokens import DocBin
from spacy.util import filter_spans
from pathlib import Path
from tqdm import tqdm

# ===== PATH SETUP =====
BASE_DIR = Path(__file__).resolve().parent

train_csv = BASE_DIR / "Datasets" / "Training_Set_1.csv"
test_csv = BASE_DIR / "Datasets" / "Testing_Set_1.csv"

train_output = BASE_DIR / "train.spacy"
dev_output = BASE_DIR / "dev.spacy"

# ===== LOAD TOKENIZER ONLY =====
nlp = spacy.blank("en")


# ===== CONVERSION FUNCTION =====
def convert(csv_path, output_path):
    df = pd.read_csv(csv_path)
    doc_bin = DocBin()

    total_entities = 0
    kept_entities = 0
    skipped_entities = 0

    print(f"\nProcessing: {csv_path}")

    for _, row in tqdm(df.iterrows(), total=len(df)):
        text = row["text"]
        entities = ast.literal_eval(row["True Predictions"])

        doc = nlp.make_doc(text)
        ents = []

        for start, end, label in entities:
            total_entities += 1

            span = doc.char_span(start, end, label=label, alignment_mode="contract")

            if span is None:
                skipped_entities += 1
                print(f"Skipped: '{text[start:end]}' ({label})")
            else:
                ents.append(span)
                kept_entities += 1

        # Remove overlapping entities safely
        doc.ents = filter_spans(ents)

        doc_bin.add(doc)

    doc_bin.to_disk(output_path)

    print(f"\nSaved: {output_path}")
    print(f"Total entities: {total_entities}")
    print(f"Kept entities: {kept_entities}")
    print(f"Skipped entities: {skipped_entities}")
    print(f"Dropped due to alignment: {total_entities - kept_entities}")


# ===== RUN =====
if __name__ == "__main__":
    convert(train_csv, train_output)
    convert(test_csv, dev_output) 