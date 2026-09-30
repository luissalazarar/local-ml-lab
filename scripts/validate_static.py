from pathlib import Path

root = Path(__file__).resolve().parents[1]
required = ["compose.yaml", "backend/Dockerfile", "frontend/Dockerfile", "frontend/package-lock.json", "backend/uv.lock", "AGENTS.md"]
missing = [name for name in required if not (root / name).exists()]
if missing:
    raise SystemExit("Faltan archivos: " + ", ".join(missing))
for path in root.rglob("*.py"):
    if path.name == "validate_static.py" or any(
        part in {".venv", "node_modules", "dist"} for part in path.parts
    ):
        continue
    text = path.read_text(encoding="utf-8")
    if "NotImplementedError" in text:
        raise SystemExit(f"Implementación vacía en {path}")
print("Validación estática correcta")
