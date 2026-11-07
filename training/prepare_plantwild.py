"""Convert the extracted PlantWild v2 folder into the layout train_disease.py expects.

PlantWild folders look like:   "tomato late blight", "bell pepper bacterial spot"
train_disease.py expects:      "Tomato___Late_blight",  "Pepper,_bell___Bacterial_spot"

Run it ONCE on your extracted folder (not the zip), pointing --dst at your PlantVillage folder to MERGE both
datasets (diseases with the same name end up in one class and PlantVillage's "healthy" classes stay):

  python prepare_plantwild.py --src C:\\Users\\you\\Downloads\\plantwild_v2 --dst .\\data\\combined \\
        --holdout 0.15 --field-dst .\\data\\field_test
  (copy your PlantVillage class folders into .\\data\\combined too, or use --dst .\\data\\plantvillage)

It only COPIES images (originals are untouched) and prefixes copied files with "pw_".
Licence of PlantWild: CC BY-NC-ND 4.0 (non-commercial). Check the terms before any commercial use.
"""
import argparse
import shutil
from pathlib import Path

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
# Crops whose names have more than one word (everything else: the first word is the crop).
MULTI_WORD_CROPS = ["bell pepper", "sweet potato", "sweet corn", "green onion", "bitter gourd", "bottle gourd",
                    "ridge gourd", "snake gourd", "passion fruit", "dragon fruit", "chili pepper", "hot pepper"]
# Same disease, different spelling in PlantVillage: use PlantVillage's folder name so both datasets share ONE class.
ALIASES = {
    "tomato bacterial leaf spot": "Tomato___Bacterial_spot",
    "tomato early blight": "Tomato___Early_blight",
    "tomato late blight": "Tomato___Late_blight",
    "tomato leaf mold": "Tomato___Leaf_Mold",
    "tomato septoria leaf spot": "Tomato___Septoria_leaf_spot",
    "tomato mosaic virus": "Tomato___Tomato_mosaic_virus",
    "tomato yellow leaf curl virus": "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "potato early blight": "Potato___Early_blight",
    "potato late blight": "Potato___Late_blight",
    "apple scab": "Apple___Apple_scab",
    "apple black rot": "Apple___Black_rot",
    "apple rust": "Apple___Cedar_apple_rust",
    "grape black rot": "Grape___Black_rot",
    "bell pepper bacterial spot": "Pepper,_bell___Bacterial_spot",
    "citrus greening disease": "Orange___Haunglongbing_(Citrus_greening)",
    "corn common rust": "Corn_(maize)___Common_rust_",
    "corn rust": "Corn_(maize)___Common_rust_",
    "corn gray leaf spot": "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "corn northern leaf blight": "Corn_(maize)___Northern_Leaf_Blight",
    "cherry powdery mildew": "Cherry_(including_sour)___Powdery_mildew",
    "peach bacterial spot": "Peach___Bacterial_spot",
    "strawberry leaf scorch": "Strawberry___Leaf_scorch",
    "squash powdery mildew": "Squash___Powdery_mildew",
}
# PlantWild crop word -> the crop name PlantVillage uses, so one crop is never split across two prefixes.
CROP_NAMES = {"corn": "Corn_(maize)", "bell pepper": "Pepper,_bell", "cherry": "Cherry_(including_sour)"}
# Not fruits or vegetables. Skipped unless you pass --keep-all.
DEFAULT_SKIP = {"maple", "tobacco"}


def split_name(folder: str) -> tuple[str, str]:
    name = " ".join(folder.lower().split())
    for crop in MULTI_WORD_CROPS:
        if name.startswith(crop + " "):
            return crop, name[len(crop) + 1:]
    crop, _, disease = name.partition(" ")
    return crop, disease


def new_label(folder: str) -> tuple[str, str]:
    key = " ".join(folder.lower().split())
    crop, disease = split_name(folder)
    if key in ALIASES:
        return crop, ALIASES[key]
    crop_label = CROP_NAMES.get(crop) or crop.replace(" ", "_").capitalize()
    return crop, f"{crop_label}___{disease.replace(' ', '_').capitalize()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="extracted plantwild_v2 folder (contains the 115 class folders)")
    ap.add_argument("--dst", required=True, help="output folder (use your PlantVillage folder to merge)")
    ap.add_argument("--skip", nargs="*", default=[], help="extra crop names to leave out, e.g. wheat")
    ap.add_argument("--keep-all", action="store_true", help="also keep non-food crops such as maple and tobacco")
    ap.add_argument("--dry-run", action="store_true", help="only print what would be copied")
    ap.add_argument("--holdout", type=float, default=0.0,
                    help="fraction of PlantWild images kept OUT of training as a real-photo test set, e.g. 0.15")
    ap.add_argument("--field-dst", help="folder for the held-out test images (required with --holdout)")
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    if args.holdout and not args.field_dst:
        raise SystemExit("--holdout needs --field-dst, e.g. --field-dst data\\field_test")
    every = round(1 / args.holdout) if args.holdout else 0  # every Nth image goes to the test set
    field = Path(args.field_dst) if args.field_dst else None
    skip = set(args.skip) | (set() if args.keep_all else DEFAULT_SKIP)
    folders = sorted(p for p in src.iterdir() if p.is_dir())
    if not folders:
        raise SystemExit(f"No class folders found in {src}. Extract the zip first and point --src at the folder "
                         "that contains folders like 'apple scab'.")
    totals, crops, held, counter = {}, set(), {}, {}
    for f in folders:
        crop, label = new_label(f.name)[0], new_label(f.name)[1]
        if crop in skip:
            continue
        images = [p for p in f.rglob("*") if p.suffix.lower() in IMG_EXT]
        totals[label] = totals.get(label, 0) + len(images)
        crops.add(label.split("___")[0])
        if args.dry_run:
            continue
        for i, img in enumerate(sorted(images)):
            n = counter[label] = counter.get(label, -1) + 1  # unique name even if two folders share a label
            to_test = bool(every) and i % every == 0
            out = (field if to_test else dst) / label
            out.mkdir(parents=True, exist_ok=True)
            shutil.copy2(img, out / f"pw_{n:05d}{img.suffix.lower()}")
            held[label] = held.get(label, 0) + int(to_test)
    print(f"{len(totals)} classes, {sum(totals.values())} images, {len(crops)} crops "
          f"{'(dry run, nothing copied)' if args.dry_run else 'copied to ' + str(dst)}")
    if every and not args.dry_run:
        print(f"{sum(held.values())} images held out as a test set in {field}")
    for label, n in sorted(totals.items()):
        flag = "  <-- only %d images" % n if n < 30 else ""
        print(f"  {label}: {n}{flag}")


if __name__ == "__main__":
    main()