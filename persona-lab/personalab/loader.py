"""Load personas and materials from disk."""

from __future__ import annotations

import base64
import random
from pathlib import Path
from typing import Any

import yaml

from .models import MaterialConfig, Persona, PersonasConfig

MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def load_personas(cfg: PersonasConfig) -> list[Persona]:
    """Load personas from a YAML file or a directory of YAML files.

    Each file may be a top-level list of personas or a mapping with a
    `personas:` key holding the list.
    """
    root = Path(cfg.path)
    files = sorted(root.glob("*.yaml")) + sorted(root.glob("*.yml")) if root.is_dir() else [root]
    if not files:
        raise FileNotFoundError(f"no persona YAML files found at {root}")

    personas: list[Persona] = []
    seen: set[str] = set()
    for f in files:
        with open(f) as fh:
            data = yaml.safe_load(fh)
        entries = data.get("personas", []) if isinstance(data, dict) else data
        for entry in entries or []:
            p = Persona.model_validate(entry)
            if p.id in seen:
                raise ValueError(f"duplicate persona id '{p.id}' (in {f})")
            seen.add(p.id)
            personas.append(p)

    if cfg.include:
        missing = set(cfg.include) - seen
        if missing:
            raise ValueError(f"unknown persona ids in include: {sorted(missing)}")
        personas = [p for p in personas if p.id in set(cfg.include)]
    if cfg.exclude:
        personas = [p for p in personas if p.id not in set(cfg.exclude)]
    if cfg.sample is not None and cfg.sample < len(personas):
        rng = random.Random(cfg.seed)
        personas = rng.sample(personas, cfg.sample)
        personas.sort(key=lambda p: p.id)
    if not personas:
        raise ValueError("persona selection produced an empty population")
    return personas


def load_material_blocks(materials: list[MaterialConfig]) -> list[dict[str, Any]]:
    """Convert material files into Claude content blocks.

    PDFs become document blocks (text + page vision), images become image
    blocks, and .txt/.md become labeled text blocks. PPTX is not ingested
    directly — export it to PDF first (e.g. LibreOffice) so slide design
    is preserved.
    """
    blocks: list[dict[str, Any]] = []
    for m in materials:
        path = Path(m.path)
        if not path.exists():
            raise FileNotFoundError(f"material not found: {path}")
        label = m.label or path.name
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            data = base64.standard_b64encode(path.read_bytes()).decode()
            blocks.append({"type": "text", "text": f"MATERIAL — {label} (PDF follows):"})
            blocks.append(
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": "application/pdf", "data": data},
                }
            )
        elif suffix in MEDIA_TYPES:
            data = base64.standard_b64encode(path.read_bytes()).decode()
            blocks.append({"type": "text", "text": f"MATERIAL — {label} (image follows):"})
            blocks.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": MEDIA_TYPES[suffix], "data": data},
                }
            )
        elif suffix in {".txt", ".md", ".markdown"}:
            text = path.read_text()
            blocks.append({"type": "text", "text": f"MATERIAL — {label}:\n\n{text}"})
        elif suffix == ".pptx":
            raise ValueError(
                f"{path}: PPTX is not ingested directly in Phase 0 — export it to PDF "
                "(e.g. `libreoffice --headless --convert-to pdf deck.pptx`) and reference the PDF."
            )
        else:
            raise ValueError(f"{path}: unsupported material type '{suffix}'")
    return blocks
