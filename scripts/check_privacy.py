import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
patterns = {
    "posible clave OpenAI": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "clave OpenAI asignada": re.compile(r"OPENAI_API_KEY\s*=\s*[^\s#]+"),
}
bad = []
for path in root.rglob("*"):
    if not path.is_file() or any(
        part == "node_modules" or part.startswith(".git") for part in path.parts
    ):
        continue
    if path.suffix.lower() not in {".py", ".ts", ".tsx", ".md", ".yaml", ".yml", ".json", ".example"}:
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    for label, pattern in patterns.items():
        if pattern.search(text) and path.name != "check_privacy.py":
            bad.append((path, label))
if bad:
    raise SystemExit("Posibles secretos: " + repr(bad))
print("No se encontraron patrones de secretos conocidos")
