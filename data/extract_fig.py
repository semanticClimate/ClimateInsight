import os
import shutil
import zipfile
from pathlib import Path

from pdf2docx import Converter

# -----------------------------
# Paths
# -----------------------------
PDF_PATH = Path("data/raw/ipcc_ar6.pdf")
DOCX_PATH = Path("data/raw/ipcc_ar6.docx")
OUTPUT_DIR = Path("data/images")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Step 1: PDF -> Word
# -----------------------------
print("Converting PDF to Word...")

cv = Converter(str(PDF_PATH))
cv.convert(str(DOCX_PATH), start=0, end=None)
cv.close()

print("Word document created!")

# -----------------------------
# Step 2: Extract Images
# -----------------------------
print("Extracting images...")

temp_dir = OUTPUT_DIR / "_temp"

if temp_dir.exists():
    shutil.rmtree(temp_dir)

with zipfile.ZipFile(DOCX_PATH, "r") as zip_ref:
    zip_ref.extractall(temp_dir)

media_dir = temp_dir / "word" / "media"

if not media_dir.exists():
    print("No images found.")
else:
    count = 1

    for image_file in sorted(media_dir.iterdir()):
        if image_file.is_file():

            extension = image_file.suffix.lower()

            new_name = f"image_{count:04d}{extension}"

            shutil.copy2(
                image_file,
                OUTPUT_DIR / new_name
            )

            print(f"Saved: {new_name}")

            count += 1

shutil.rmtree(temp_dir)

print(f"\nDone! Extracted {count-1} images.")