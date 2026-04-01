import fitz
import re
import spacy
from pathlib import Path

# =========================
# PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent
ner_spacy_1 = spacy.load(BASE_DIR / "models" / "spacy" / "epoch_20")
ner_spacy_2 = spacy.load(BASE_DIR / "models" / "spacy_cfg" / "model-best")

pdf_input = BASE_DIR / "pdf_files" / "input" / "CPB Software Vendor Invoice.pdf"
pdf_output_debug = BASE_DIR / "pdf_files" / "output" / "output_debug_3.pdf"
pdf_redacted = BASE_DIR / "pdf_files" / "output" / "output_redacted_3.pdf" # FINAL PDF

# =========================
# CONFIG
# =========================
REGEX_WEIGHT = 0.5
NER_1_WEIGHT = 0.5
NER_2_WEIGHT = 0.5  
THRESHOLD = 1
MAX_ENTITY_LENGTH = 60

BLACKLIST = {
    "Invoice", "Amount", "Tax", "Total",
    "Shipping", "Order", "Date", "Description",
    "Charges", "Number"
}

# =========================
# REGEX
# =========================
def get_regex_entities(text):
    patterns = {
        # "name": r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)+\b", // Not good, make noises
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "url": r"\bhttps?://[^\s]+\b",
        "phone": r"\b(?:\+?\d{1,3})?[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b",
        "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "company": r"\b[A-Z][A-Za-z0-9&.,\s]+(?:Inc|Ltd|LLC|Group|Corp|Company)\b",
        # "address": r"\d+\s[A-Za-z0-9\s,.-]+" // Not good, make noises
    }

    entities = []
    for label, pattern in patterns.items():
        for match in re.finditer(pattern, text):
            entities.append({
                "start": match.start(),
                "end": match.end(),
                "label": label,
                "weight": REGEX_WEIGHT,
                "source": "REGEX",
                "text": match.group()
            })
    return entities

# =========================
# NER
# =========================
def get_ner_entities(nlp, text, weight, source):
    doc = nlp(text)
    entities = []

    for ent in doc.ents:
        entities.append({
            "start": ent.start_char,
            "end": ent.end_char,
            "text": ent.text,
            "label": ent.label_,
            "weight": weight,
            "source": source
        })

    return entities

# =========================
# OVERLAP
# =========================
def overlap_ratio(a, b):
    overlap = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    min_len = min(a["end"] - a["start"], b["end"] - b["start"])
    return overlap / min_len if min_len > 0 else 0

# =========================
# FILTER
# =========================
def is_valid(text):
    if len(text) > MAX_ENTITY_LENGTH:
        return False
    if any(word in text for word in BLACKLIST):
        return False
    return True

# =========================
# MERGE
# =========================
def merge_entities(entities):
    entities = sorted(entities, key=lambda x: x["start"])
    merged = []

    for ent in entities:
        if not is_valid(ent["text"]):
            continue

        found = False

        for m in merged:
            if overlap_ratio(ent, m) > 0.6:
                m["start"] = min(m["start"], ent["start"])
                m["end"] = max(m["end"], ent["end"])
                m["weight"] += ent["weight"]
                m["sources"].add(ent["source"])
                m["labels"].add(ent["label"])
                found = True
                break

        if not found:
            merged.append({
                "start": ent["start"],
                "end": ent["end"],
                "text": ent["text"],
                "weight": ent["weight"],
                "sources": {ent["source"]},
                "labels": {ent["label"]}
            })

    return [m for m in merged if m["weight"] >= THRESHOLD]

# =========================
# DEBUG PRINT
# =========================
def print_debug(regex_ents, ner_1_ents, ner_2_ents):
    # print("\n=== REGEX DETECTIONS ===")
    # for e in regex_ents:
    #     print(f"{e['text']} -> {e['label']}")

    print("\n=== NERz DETECTIONS ===")
    for e in ner_1_ents:
        print(f"{e['text']} -> {e['label']}")

    print("\n=== NER BEST MODEL DETECTIONS ===")
    for e in ner_2_ents:
        print(f"{e['text']} -> {e['label']}")

def print_final_entities(text, final_ents):
    print("\n=== FINAL ENTITIES ===")
    for ent in final_ents:
        span = text[ent["start"]:ent["end"]]
        print(f"[FINAL] '{span}' | weight={ent['weight']} | labels={ent['labels']}")

# =========================
# ANNOTATE PDF (DEBUG)
# =========================
def annotate_pdf(input_pdf, output_pdf, regex_ents_all, ner_1_ents_all, ner_2_ents_all,final_ents_all):
    doc = fitz.open(input_pdf)

    for page_index, page in enumerate(doc):
        text = page.get_text()

         # REGEX (RED BOX)
        for ent in regex_ents_all[page_index]:
            rects = page.search_for(ent["text"])
            for r in rects:
                annot = page.add_rect_annot(r)
                annot.set_colors(stroke=(1, 0, 0))  # red
                annot.set_info(content=f"REGEX: {ent['label']}")
                annot.update()

        # NER1 (BLUE BOX)
        for ent in ner_1_ents_all[page_index]:
            rects = page.search_for(ent["text"])
            for r in rects:
                annot = page.add_rect_annot(r)
                annot.set_colors(stroke=(0, 0, 1))
                annot.set_info(content=f"NER1: {ent['label']}")
                annot.update()

        # NER2 (GREEN BOX)
        for ent in ner_2_ents_all[page_index]:
            rects = page.search_for(ent["text"])
            for r in rects:
                annot = page.add_rect_annot(r)
                annot.set_colors(stroke=(0, 1, 0))
                annot.set_info(content=f"NER2: {ent['label']}")
                annot.update()

        # FINAL (BLACK BOX)
        # for ent in final_ents_all[page_index]:
        #     span_text = text[ent["start"]:ent["end"]]
        #     rects = page.search_for(span_text)
        #     for r in rects:
        #         annot = page.add_rect_annot(r)
        #         annot.set_colors(stroke=(0, 0, 0))
        #         annot.set_info(content=f"FINAL: {','.join(ent['labels'])}")
        #         annot.update()

    doc.save(output_pdf)
    print(f"\n✅ Saved DEBUG PDF: {output_pdf}")

# =========================
# REDACT + CONSOLE PREVIEW
# =========================
def redact_pdf(input_pdf, output_pdf, final_ents_all):
    doc = fitz.open(input_pdf)

    for page_index, page in enumerate(doc):
        text = page.get_text()
        redacted_text = list(text)

        print(f"\n===== PAGE {page_index+1} =====")

        for ent in final_ents_all[page_index]:
            span_text = text[ent["start"]:ent["end"]]

            print(f"[REDACTING] {span_text}")

            # mask console preview
            for i in range(ent["start"], ent["end"]):
                redacted_text[i] = "'\'"

            # apply to PDF
            rects = page.search_for(span_text)
            for r in rects:
                page.add_redact_annot(r, fill=(0, 0, 0))

        page.apply_redactions()

        print("\n--- REDACTED TEXT PREVIEW ---")
        print("".join(redacted_text))

    doc.save(output_pdf)
    print(f"\nSaved REDACTED PDF: {output_pdf}")

# =========================
# MAIN
# =========================
def process_pdf():
    doc = fitz.open(pdf_input)

    regex_all = []
    ner_1_all = []
    ner_2_all = []
    final_all = []

    for page_num, page in enumerate(doc):
        print(f"\n=> Processing page {page_num+1}")
        text = page.get_text()

        # 1. Detect Entities 
        regex_ents = get_regex_entities(text)
        ner_1_ents = get_ner_entities(ner_spacy_1, text, NER_1_WEIGHT, "NER1")
        ner_2_ents = get_ner_entities(ner_spacy_2, text, NER_2_WEIGHT, "NER2")

        # DEBUG
        print_debug(regex_ents, ner_1_ents, ner_2_ents)

        # 2. Merge Overlapping Entities
        final_ents = merge_entities(regex_ents + ner_1_ents + ner_2_ents)

        # print_final_entities(text, final_ents)

        regex_all.append(regex_ents)
        ner_1_all.append(ner_1_ents)
        ner_2_all.append(ner_2_ents)
        final_all.append(final_ents)

    # DEBUG PDF
    annotate_pdf(pdf_input, pdf_output_debug, regex_all, ner_1_all, ner_2_all, final_all)

    # REDACTED PDF + CONSOLE DEBUG
    redact_pdf(pdf_input, pdf_redacted, final_all)


if __name__ == "__main__":
    process_pdf()