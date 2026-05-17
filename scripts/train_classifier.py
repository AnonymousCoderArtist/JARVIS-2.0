"""
Standalone script to train the JARVIS classifier from scratch.
"""
import importlib.util
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT)

# Bypass circular imports: load training_data directly
td_path = os.path.join(ROOT, "core", "learn", "Classification", "training_data.py")
spec = importlib.util.spec_from_file_location("core.learn.Classification.training_data", td_path)
if spec is None or spec.loader is None:
    raise RuntimeError("Failed to load training_data module")
td_module = importlib.util.module_from_spec(spec)
sys.modules["core.learn.Classification.training_data"] = td_module
spec.loader.exec_module(td_module)

# Now import the training pipeline
from jarvis.core.learn.Classification.train_classifier import predict, train_model

print("=" * 60)
print("JARVIS Query Type Classifier - Training from Scratch")
print("=" * 60)

base_data = td_module.get_training_data()
print(f"Base training samples: {len(base_data)}")

aug_data = td_module.augment_training_data(base_data)
aug_texts = [d[0] for d in aug_data]
aug_labels = [d[1] for d in aug_data]
print(f"Augmented training samples: {len(aug_texts)}")

vectorizer, model, meta = train_model(aug_texts, aug_labels)

print("")
print("=" * 60)
print("Verification test:")
for test_text in [
    "fix the null pointer exception in the parser",
    "review my code for potential bugs",
    "implement a new feature request",
    "refactor this code for clarity",
    "write comprehensive tests for the API",
    "document the api endpoints thoroughly",
]:
    label, conf = predict(model, vectorizer, test_text)
    print(f"  {test_text!r}")
    print(f"   -> {label} ({conf:.1%})")

print(f"\nModel: {meta['param_count']:,} params")
print(f"Final val accuracy: {meta['training_history']['final_val_acc']:.2%}")
print(f"Trained for {meta['training_history']['epochs_trained']} epochs")
print("Done!")
