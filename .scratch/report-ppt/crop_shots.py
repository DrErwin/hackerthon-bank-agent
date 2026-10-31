"""Crop the tall phone screenshots to the part each slide needs."""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SRC = HERE.parent / "report-ux-polish" / "shots"
OUT = HERE / "img"
OUT.mkdir(exist_ok=True)

CROPS = {
    "T05": ("T05-transfer-change-amount", 120, 1090),
    "T02": ("T02-transfer-confirmation", 330, 1470),
    "B01": ("B01-bills-month", 230, 1100),
    "G01": ("G01-birthday-one-sentence", 150, 1200),
    "X04": ("X04-injection-analyze-only", 360, 1080),
    # The full lost-card reply is only visible near the top of the X04 capture.
    "X01": ("X04-injection-analyze-only", 160, 360),
    "X02": ("X02-code-in-chat-blocked", 300, 700),
    "G06": ("G06-birthday-final-receipt", 0, 760),
    "P01": ("P01-pension-plan", 230, 790),
    "P02": ("P02-pension-final-receipt", 110, 660),
    "T03a": ("T03a-transfer-verify-two-steps", 540, 1172),
    "G05": ("G05-birthday-order-confirm", 0, 820),
}
FULL = {
    "S01": "S01-home", "R01b": "R01b-reduce-plan-steps", "X03": "X03-recovery-card",
    "T01": "T01-transfer-one-sentence", "T04": "T04-transfer-receipt",
    "R01": "R01-reduce-overview", "R02": "R02-reduce-unsubscribe-confirm",
    "R03": "R03-reduce-final-receipt", "G03": "G03-birthday-plan",
}

for key, (name, top, bottom) in CROPS.items():
    im = Image.open(SRC / f"{name}.png")
    im.crop((0, top, im.width, min(bottom, im.height))).save(OUT / f"{key}.png")
for key, name in FULL.items():
    Image.open(SRC / f"{name}.png").save(OUT / f"{key}.png")
print("cropped", len(CROPS) + len(FULL))
