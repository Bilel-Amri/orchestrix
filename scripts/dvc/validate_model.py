import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

with open(ROOT / "params.yaml", encoding="utf-8") as f:
    params = json.load(f)

model = params["model"]

bundle = ROOT / model["bundle"]
config_file = ROOT / model["config"]
embeddings = ROOT / model["embeddings"]

# Vérifier les artefacts
for path in (bundle, config_file, embeddings):
    if not path.exists():
        raise FileNotFoundError(f"Artefact manquant : {path}")

if not bundle.is_file():
    raise ValueError("Le bundle du modèle n'est pas un fichier.")

if not embeddings.is_dir():
    raise ValueError("Le dossier des embeddings est invalide.")

# Lire la configuration
with open(config_file, encoding="utf-8") as f:
    config = json.load(f)

classes = config.get("class_names", {})
metrics = config.get("test_metrics", {})

if len(classes) != model["expected_classes"]:
    raise ValueError(
        f"Nombre de classes incorrect : {len(classes)}"
    )

required_metrics = [
    "accuracy",
    "macro_f1",
    "balanced_accuracy"
]

for name in required_metrics:
    if name not in metrics:
        raise ValueError(f"Métrique absente : {name}")

# Calculer les empreintes SHA256
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

embedding_files = sorted(
    p for p in embeddings.rglob("*") if p.is_file()
)

if not embedding_files:
    raise ValueError("Le dossier embedding_model est vide.")

embedding_hashes = {
    str(p.relative_to(ROOT)): sha256_file(p)
    for p in embedding_files
}

# Rapport de validation et métriques
report = {
    "model": {
        "bundle": str(bundle.relative_to(ROOT)),
        "bundle_sha256": sha256_file(bundle),
        "config": str(config_file.relative_to(ROOT)),
        "embedding_files_count": len(embedding_files),
        "embedding_sha256": embedding_hashes
    },
    "classes": classes,
    "versions": config.get("versions", {}),
    "test_metrics": metrics
}

output = ROOT / "reports/dvc/model_metrics.json"
output.parent.mkdir(parents=True, exist_ok=True)

with open(output, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("Validation DVC réussie.")
print(f"Bundle : {bundle.name}")
print(f"Fichiers embeddings : {len(embedding_files)}")
print(f"Macro-F1 : {metrics['macro_f1']:.4f}")
print(f"Rapport : {output}")
