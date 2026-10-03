"""Read the approved eight-field matrix; executable plans are separate from prose."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STANDARD_IDS = (
    [f"TF-PAY-{n:02}" for n in [1, 2, 3, 4, 5, 6, 7, 8, 16]]
    + [f"TF-INP-{n:02}" for n in [1, 2, 3, 6, 7, 10]]
    + ["TF-CNF-01", "TF-BNK-03", "TF-BNK-07", "TF-BNK-08", "TF-VFY-01", "TF-VFY-14"]
)


def load_cases():
    rows = []
    for line in (ROOT / "cases.md").read_text(encoding="utf-8").splitlines():
        fields = [part.strip() for part in line.strip("|").split("|")]
        if not line.startswith("| TF-") or len(fields) != 8:
            continue
        ident, dimension, basis, setup, inputs, interaction, expected, mapping = fields
        samples = ["嗯", "好", "行"] if ident == "TF-CNF-03" else [None]
        for sample in samples:
            rows.append(dict(id=ident if sample is None else f"{ident}[{sample}]",
                             scenario_id=ident, dimension=dimension, basis=basis,
                             setup=setup, inputs=inputs, interaction=interaction,
                             expected=expected, mapping=mapping, sample=sample,
                             standard=ident in STANDARD_IDS))
    return rows


def data_version():
    digest = hashlib.sha256()
    for name in ("cases.md", "fixtures.md", "plans.py"):
        digest.update((ROOT / name).read_bytes())
    return digest.hexdigest()
