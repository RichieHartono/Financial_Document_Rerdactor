import spacy
import pandas as pd
import ast
from spacy.training import Example, offsets_to_biluo_tags
from spacy.util import minibatch, compounding
from tqdm import tqdm
from pathlib import Path
import warnings

# ===== PATH SETUP =====
BASE_DIR = Path(__file__).resolve().parent
csv_path = BASE_DIR / "Datasets" / "Training_Set_1.csv"
output_dir = BASE_DIR / "models" / "test"

"""# Training Model"""

# Load the dataset
dataset = pd.read_csv(csv_path)
print(dataset.head())

# Convert the dataset into the required format
training_data = []  
for index, row in dataset.iterrows():
    text = row['text']
    # Assuming 'True Predictions' is the column containing the annotations
    entities = ast.literal_eval(row['True Predictions'])
    training_data.append((text, {"entities": entities}))

# Display a sample of the training data
print(training_data[:2])

warnings.filterwarnings("ignore", category=UserWarning, module="spacy.training.iob_utils")

# Define the function to merge overlapping entities
def merge_overlapping_entities(entities):
    if not entities:
        return []
    # Sort entities by their start positions
    entities = sorted(entities, key=lambda x: x[0])
    merged_entities = []
    current_start, current_end, current_label = entities[0]

    for start, end, label in entities[1:]:
        if start <= current_end:  # Overlapping
            current_end = max(current_end, end)
        else:
            merged_entities.append((current_start, current_end, current_label))
            current_start, current_end, current_label = start, end, label
    merged_entities.append((current_start, current_end, current_label))
    return merged_entities

# Initialize the Custom Spacy model
nlp = spacy.blank("en")

# Create an NER component and add it to the pipeline
ner = nlp.add_pipe("ner")

# Prepare the training data with merged entities
training_data = []
for index, row in dataset.iterrows():
    text = row['text']
    entities = ast.literal_eval(row['True Predictions'])
    entities = merge_overlapping_entities(entities)

    # Check alignment
    try:
        tags = offsets_to_biluo_tags(nlp.make_doc(text), entities)
        training_data.append((text, {"entities": entities}))
    except Exception as e:
        print(f"Skipping misaligned entity in record {index}: {e}")

# Add the labels to the NER component
for _, annotations in training_data:
    for ent in annotations.get("entities"):
        ner.add_label(ent[2])

# Convert training data to Spacy's format
examples = []
for text, annotations in training_data:
    doc = nlp.make_doc(text)
    example = Example.from_dict(doc, annotations)
    examples.append(example)

# Initialize the optimizer
optimizer = nlp.begin_training()

# Parameters
iterations = 20  # Number of iterations
dropout = 0.5  # Dropout rate
batch_size_start = 4  # Start of the batch size range
batch_size_end = 32  # End of the batch size range

# Training loop
for i in range(iterations):
    losses = {}
    batches = minibatch(examples, size=compounding(batch_size_start, batch_size_end, 1.001))
    for batch in tqdm(batches, desc=f"Epoch {i+1}"):
        nlp.update(batch, losses=losses, drop=dropout, sgd=optimizer)
    print(f"Iteration {i + 1}, Losses: {losses}")

    # Save model
    epoch_dir = output_dir / f"epoch_{i+1}"
    nlp.to_disk(epoch_dir)
    print(f"Saved to {epoch_dir}")

