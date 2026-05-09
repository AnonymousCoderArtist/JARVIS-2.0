"""
JARVIS Query Type Classifier - Built from Scratch
==================================================
Custom TF-IDF + Feedforward Neural Network classifier.
No pretrained models used. Trains entirely on synthetic+curated data.

Architecture:
  - TF-IDF Vectorizer (max 12000 features)
  - 4-layer Feedforward NN: input -> 4096 -> 2048 -> 512 -> 6
  - ~10-20M trainable parameters (after vocab pruning)

Classes (6):
  bug_fix, code_review, implementation, refactor, documentation, testing
"""

import json
import math
import random
import re
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_DIR = Path(__file__).resolve().parent / "model_artifacts"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

VECTORIZER_PATH = MODEL_DIR / "vectorizer.json"
WEIGHTS_PATH = MODEL_DIR / "model_weights.npz"
META_PATH = MODEL_DIR / "model_meta.json"

LABELS = ["bug_fix", "code_review", "implementation", "refactor", "documentation", "testing"]
LABEL_TO_ID = {label: idx for idx, label in enumerate(LABELS)}
ID_TO_LABEL = {idx: label for idx, label in enumerate(LABELS)}
NUM_CLASSES = len(LABELS)

# Hyperparameters
MAX_FEATURES = 12000
MIN_DF = 2
MAX_DF = 0.85
NGRAM_RANGE = (1, 2)

HIDDEN_DIMS = [4096, 2048, 512]
DROPOUT_RATE = 0.3

BATCH_SIZE = 32
EPOCHS = 200
LEARNING_RATE = 0.001
WEIGHT_DECAY = 1e-4
PATIENCE = 25
MIN_DELTA = 1e-4


# ---------------------------------------------------------------------------
# Data Augmentation
# ---------------------------------------------------------------------------
def _augment_text(text: str) -> list[str]:
    """Generate augmented versions of a single text sample."""
    variants = [text]

    prefixes = ["please ", "could you ", "can you ", "i need to ", "help me ",
                "would you ", "should i ", "want to ", ""]
    suffixes = ["", " please", " thanks", " if possible", " for me",
                " now", " immediately", " as soon as possible"]
    for p in prefixes:
        for s in suffixes:
            if p or s:
                candidate = f"{p}{text}{s}"
                if candidate != text:
                    variants.append(candidate)

    substitutions = {
        "fix": ["repair", "resolve", "correct", "patch"],
        "implement": ["create", "build", "add", "develop"],
        "review": ["check", "analyze", "audit", "examine"],
        "document": ["describe", "explain", "detail", "write docs for"],
        "test": ["validate", "verify", "check", "assess"],
        "refactor": ["restructure", "reorganize", "improve", "clean up"],
        "code": ["source", "module", "function", "implementation"],
        "error": ["issue", "problem", "bug", "fault", "defect"],
        "add": ["introduce", "incorporate", "include"],
        "create": ["build", "develop", "make", "design"],
    }

    lower = text.lower()
    for original, replacements in substitutions.items():
        if original in lower:
            for rep in replacements:
                new_text = re.sub(r'\b' + re.escape(original) + r'\b', rep, text, flags=re.IGNORECASE)
                if new_text != text:
                    variants.append(new_text)

    variants.append(text.capitalize())

    stripped = text.rstrip(".!?")
    for punct in [".", "!", "?"]:
        candidate = stripped + punct
        if candidate != text:
            variants.append(candidate)

    return variants


def augment_dataset(texts: list[str], labels: list[str], target_per_class: int = 500) -> Tuple[list[str], list[str]]:
    """Augment dataset to reach target_per_class samples per label."""
    from collections import defaultdict

    by_label = defaultdict(list)
    for text, label in zip(texts, labels):
        by_label[label].append(text)

    augmented_texts = []
    augmented_labels = []

    for label in LABELS:
        originals = by_label.get(label, [])
        if not originals:
            continue

        for t in originals:
            augmented_texts.append(t)
            augmented_labels.append(label)

        needed = target_per_class - len(originals)
        if needed <= 0:
            continue

        count = 0
        idx = 0
        while count < needed:
            text = originals[idx % len(originals)]
            variants = _augment_text(text)
            for v in variants[1:]:
                if count >= needed:
                    break
                augmented_texts.append(v)
                augmented_labels.append(label)
                count += 1
            idx += 1

    return augmented_texts, augmented_labels


# ---------------------------------------------------------------------------
# TF-IDF Vectorizer (pure numpy)
# ---------------------------------------------------------------------------
class SimpleTfidfVectorizer:
    """Lightweight TF-IDF vectorizer built from scratch."""

    def __init__(self, max_features=MAX_FEATURES, min_df=MIN_DF,
                 max_df=MAX_DF, ngram_range=NGRAM_RANGE):
        self.max_features = max_features
        self.min_df = min_df
        self.max_df = max_df
        self.ngram_range = ngram_range
        self.vocabulary_: dict[str, int] = {}
        self.idf_: np.ndarray = np.array([])
        self._fitted = False

    def _tokenize(self, text: str) -> list[str]:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return [t for t in text.split() if len(t) >= 2]

    def _get_ngrams(self, tokens: list[str], n: int) -> list[str]:
        return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

    def _extract_features(self, text: str) -> list[str]:
        tokens = self._tokenize(text)
        features = list(tokens)
        if self.ngram_range[1] >= 2:
            features.extend(self._get_ngrams(tokens, 2))
        return features

    def fit(self, documents: list[str]):
        n_docs = len(documents)
        df_counts: dict[str, int] = {}
        for doc in documents:
            for feat in set(self._extract_features(doc)):
                df_counts[feat] = df_counts.get(feat, 0) + 1

        min_count = self.min_df if isinstance(self.min_df, int) else int(self.min_df * n_docs)
        max_count = self.max_df if isinstance(self.max_df, int) else int(self.max_df * n_docs)

        eligible = {f: c for f, c in df_counts.items() if min_count <= c <= max_count}
        sorted_features = sorted(eligible.items(), key=lambda x: x[1], reverse=True)
        selected = sorted_features[:self.max_features]

        self.vocabulary_ = {feat: idx for idx, (feat, _) in enumerate(selected)}
        self.idf_ = np.zeros(len(self.vocabulary_), dtype=np.float32)
        for feat, idx in self.vocabulary_.items():
            df = df_counts.get(feat, 0)
            self.idf_[idx] = math.log((n_docs + 1) / (df + 1)) + 1.0

        self._fitted = True
        return self

    def transform(self, documents: list[str]) -> np.ndarray:
        if not self._fitted:
            raise RuntimeError("Vectorizer not fitted.")
        n_docs = len(documents)
        n_features = len(self.vocabulary_)
        matrix = np.zeros((n_docs, n_features), dtype=np.float32)

        for i, doc in enumerate(documents):
            features = self._extract_features(doc)
            tf: dict[str, float] = {}
            for feat in features:
                if feat in self.vocabulary_:
                    tf[feat] = tf.get(feat, 0.0) + 1.0
            total = sum(tf.values())
            if total > 0:
                for feat in tf:
                    tf[feat] /= total
            for feat, val in tf.items():
                matrix[i, self.vocabulary_[feat]] = val * self.idf_[self.vocabulary_[feat]]
            rn = np.linalg.norm(matrix[i])
            if rn > 0:
                matrix[i] /= rn
        return matrix

    def fit_transform(self, documents: list[str]) -> np.ndarray:
        self.fit(documents)
        return self.transform(documents)

    def save(self, path: Path):
        data = {
            "vocabulary": self.vocabulary_,
            "idf": self.idf_.tolist(),
            "max_features": self.max_features,
            "min_df": self.min_df,
            "max_df": self.max_df,
            "ngram_range": self.ngram_range,
        }
        with open(path, 'w') as f:
            json.dump(data, f)

    def load(self, path: Path):
        with open(path) as f:
            data = json.load(f)
        self.vocabulary_ = data["vocabulary"]
        self.idf_ = np.array(data["idf"], dtype=np.float32)
        self.max_features = data["max_features"]
        self.min_df = data["min_df"]
        self.max_df = data["max_df"]
        self.ngram_range = tuple(data["ngram_range"])
        self._fitted = True


# ---------------------------------------------------------------------------
# Neural Classifier (pure PyTorch)
# ---------------------------------------------------------------------------
class TextClassifier(nn.Module):
    """Feedforward neural network for text classification.

    Architecture: input_dim -> 4096 -> 2048 -> 512 -> num_classes
    """

    def __init__(self, input_dim: int, hidden_dims=None,
                 num_classes=NUM_CLASSES, dropout=DROPOUT_RATE):
        super().__init__()

        if hidden_dims is None:
            hidden_dims = HIDDEN_DIMS

        layers = []
        prev = input_dim
        for h in hidden_dims:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev = h
        layers.append(nn.Linear(prev, num_classes))

        self.net = nn.Sequential(*layers)
        self._device = 'cpu'

    def forward(self, x):
        return self.net(x)

    def to(self, *args, **kwargs):
        super().to(*args, **kwargs)
        device = args[0] if args else kwargs.get('device', 'cpu')
        self.net = self.net.to(device)
        self._device = device
        return self

    @property
    def device(self):
        return self._device

    def train_mode(self):
        self.net.train()

    def eval_mode(self):
        self.net.eval()

    def parameters(self, recurse: bool = True):
        return self.net.parameters(recurse) if recurse else iter([p for m in self.net.modules() for p in m.parameters() if p.requires_grad])

    def save(self, path: Path):
        import torch
        torch.save(self.net.state_dict(), path)

    def load(self, path: Path, input_dim: int):
        import torch
        self.__init__(input_dim=input_dim)
        self.net.load_state_dict(torch.load(path, weights_only=True, map_location='cpu'))
        self.eval_mode()

    def predict_proba(self, x_tensor) -> np.ndarray:
        import torch
        self.net.eval()
        with torch.no_grad():
            logits = self.net(x_tensor)
            probs = torch.softmax(logits, dim=1)
            return probs.numpy()

    def predict(self, x_tensor) -> np.ndarray:
        probs = self.predict_proba(x_tensor)
        return np.argmax(probs, axis=1)

    def count_params(self) -> int:
        return sum(p.numel() for p in self.net.parameters())


# ---------------------------------------------------------------------------
# Training Utilities
# ---------------------------------------------------------------------------
class EarlyStopping:
    def __init__(self, patience=PATIENCE, min_delta=MIN_DELTA):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = float('inf')
        self.early_stop = False

    def __call__(self, val_loss):
        if self.best_loss - val_loss > self.min_delta:
            self.best_loss = val_loss
            self.counter = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.early_stop = True
        return self.early_stop


def train_val_split(texts, labels, val_ratio=0.15, random_seed=42):
    random.seed(random_seed)
    from collections import defaultdict

    by_label = defaultdict(list)
    for text, label in zip(texts, labels):
        by_label[label].append((text, label))

    train_pairs, val_pairs = [], []
    for label in LABELS:
        items = by_label.get(label, [])
        random.shuffle(items)
        split_idx = max(1, int(len(items) * (1 - val_ratio)))
        train_pairs.extend(items[:split_idx])
        val_pairs.extend(items[split_idx:])

    random.shuffle(train_pairs)
    random.shuffle(val_pairs)

    return (
        [p[0] for p in train_pairs], [p[1] for p in train_pairs],
        [p[0] for p in val_pairs], [p[1] for p in val_pairs],
    )


def train_model(texts: list[str], labels: list[str],
                epochs=EPOCHS, lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY) -> Tuple:
    """Train the full classification pipeline.

    Returns:
        (vectorizer, model, metadata_dict)
    """
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    print(f"[Classifier] Starting training on {len(texts)} samples across {NUM_CLASSES} classes...")

    # Vectorize
    vectorizer = SimpleTfidfVectorizer()
    X = vectorizer.fit_transform(texts)
    input_dim = X.shape[1]
    print(f"[Classifier] Vocabulary size (features): {input_dim}")

    # Encode labels
    y = np.array([LABEL_TO_ID[l] for l in labels], dtype=np.int64)

    # Split
    train_X, train_y, val_X, val_y = train_val_split(texts, labels)
    train_X = vectorizer.transform(train_X)
    val_X = vectorizer.transform(val_X)
    train_y = np.array([LABEL_TO_ID[l] for l in train_y], dtype=np.int64)
    val_y = np.array([LABEL_TO_ID[l] for l in val_y], dtype=np.int64)

    # DataLoaders
    train_ds = TensorDataset(torch.FloatTensor(train_X), torch.LongTensor(train_y))
    val_ds = TensorDataset(torch.FloatTensor(val_X), torch.LongTensor(val_y))
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    # Model
    model = TextClassifier(input_dim=input_dim)
    model.to('cpu')
    model.train_mode()
    param_count = model.count_params()
    print(f"[Classifier] Trainable parameters: {param_count:,}")

    # Loss + optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.7)
    early_stopper = EarlyStopping()

    best_val_loss = float('inf')
    best_state = None
    history = {"train_loss": [], "val_loss": [], "val_acc": []}

    for epoch in range(epochs):
        # Train
        model.train_mode()
        t_loss = 0.0
        t_correct = 0
        t_total = 0

        for bx, by in train_loader:
            optimizer.zero_grad()
            out = model(bx)
            loss = criterion(out, by)
            loss.backward()
            optimizer.step()

            t_loss += loss.item() * bx.size(0)
            _, pred = torch.max(out, 1)
            t_total += by.size(0)
            t_correct += (pred == by).sum().item()

        avg_tloss = t_loss / t_total
        train_acc = t_correct / t_total

        # Validate
        model.eval_mode()
        v_loss = 0.0
        v_correct = 0
        v_total = 0

        with torch.no_grad():
            for bx, by in val_loader:
                out = model(bx)
                loss = criterion(out, by)
                v_loss += loss.item() * bx.size(0)
                _, pred = torch.max(out, 1)
                v_total += by.size(0)
                v_correct += (pred == by).sum().item()

        avg_vloss = v_loss / max(v_total, 1)
        val_acc = v_correct / max(v_total, 1)

        history["train_loss"].append(avg_tloss)
        history["val_loss"].append(avg_vloss)
        history["val_acc"].append(val_acc)
        scheduler.step()

        if avg_vloss < best_val_loss:
            best_val_loss = avg_vloss
            best_state = {k: v.cpu().clone() for k, v in model.net.state_dict().items()}
            model.save(WEIGHTS_PATH)

        if early_stopper(avg_vloss):
            print(f"[Classifier] Early stopping at epoch {epoch + 1}")
            break

        if (epoch + 1) % 25 == 0 or epoch == 0:
            print(f"[Epoch {epoch + 1}] train_loss={avg_tloss:.4f}  "
                  f"val_loss={avg_vloss:.4f}  val_acc={val_acc:.2%}")

    # Restore best weights
    if best_state is not None:
        model.net.load_state_dict(best_state)

    # Save artifacts
    vectorizer.save(VECTORIZER_PATH)
    meta = {
        "input_dim": input_dim,
        "labels": LABELS,
        "param_count": param_count,
        "training_history": {
            "final_train_loss": float(history["train_loss"][-1]),
            "final_val_loss": float(history["val_loss"][-1]),
            "final_val_acc": float(history["val_acc"][-1]),
            "best_val_loss": float(best_val_loss),
            "epochs_trained": len(history["train_loss"]),
        },
        "hyperparameters": {
            "max_features": MAX_FEATURES,
            "hidden_dims": HIDDEN_DIMS,
            "dropout": DROPOUT_RATE,
            "learning_rate": lr,
            "batch_size": BATCH_SIZE,
            "epochs_trained": len(history["train_loss"]),
        },
    }
    with open(META_PATH, 'w') as f:
        json.dump(meta, f, indent=2)

    acc = history["val_acc"][-1]
    print(f"\n[Classifier] Training complete. Final val accuracy: {acc:.2%}")
    print(f"[Classifier] Model saved to {WEIGHTS_PATH}")
    print(f"[Classifier] Vectorizer saved to {VECTORIZER_PATH}")

    return vectorizer, model, meta


# ---------------------------------------------------------------------------
# Inference Functions
# ---------------------------------------------------------------------------
_model: Optional[TextClassifier] = None
_vectorizer: Optional[SimpleTfidfVectorizer] = None


def _ensure_loaded():
    global _model, _vectorizer
    if _model is not None and _vectorizer is not None:
        return True

    if not VECTORIZER_PATH.exists() or not WEIGHTS_PATH.exists() or not META_PATH.exists():
        return None

    _vectorizer = SimpleTfidfVectorizer()
    _vectorizer.load(VECTORIZER_PATH)

    with open(META_PATH) as f:
        meta = json.load(f)

    _model = TextClassifier(input_dim=meta["input_dim"])
    _model.load(WEIGHTS_PATH, meta["input_dim"])
    return True


def load_model() -> tuple[TextClassifier | None, SimpleTfidfVectorizer | None] | None:
    """Load trained model and vectorizer. Returns (model, vectorizer) or None."""
    ok = _ensure_loaded()
    if ok is None:
        return None
    return _model, _vectorizer


def predict(model: TextClassifier, vectorizer: SimpleTfidfVectorizer,
            text: str) -> Tuple[str, float]:
    """Predict class label + confidence for input text.

    Returns:
        (label: str, confidence: float 0.0-1.0)
    """
    model.eval_mode()
    X = vectorizer.transform([text])
    import torch
    x_t = torch.FloatTensor(X)
    probs = model.predict_proba(x_t)
    idx = int(np.argmax(probs[0]))
    return ID_TO_LABEL[idx], float(probs[0][idx])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    """Train the classifier from scratch."""
    from .training_data import TRAINING_DATA, augment_training_data, get_training_data

    print("=" * 60)
    print("JARVIS Query Type Classifier - Training from Scratch")
    print("=" * 60)

    base_data = get_training_data()
    texts, labels = zip(*base_data)
    print(f"Base training samples: {len(texts)}")

    aug_texts, aug_labels = zip(*augment_training_data(list(zip(texts, labels))))
    print(f"Augmented training samples: {len(aug_texts)}")

    vectorizer, model, meta = train_model(list(aug_texts), list(aug_labels))

    print("\n" + "=" * 60)
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
        print(f"  '{test_text}'\n   -> {label} ({conf:.1%})")

    print(f"\nModel info: {meta['param_count']:,} params, "
          f"val_acc={meta['training_history']['final_val_acc']:.2%}")


if __name__ == "__main__":
    main()

