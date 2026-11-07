"""Train the leaf-disease classifier (transfer learning) and export ONNX for ml_service.

Run on your laptop/Colab/SageMaker (GPU helps, CPU works but is slow). See docs/MODEL_TRAINING.md.

  python train_disease.py --data ./data/plantvillage --out ../models \
        --crops Tomato Potato "Corn_(maize)" "Pepper,_bell" \
        [--field-dir ./data/plantdoc_test] [--epochs 8]

--data       folder of class sub-folders (e.g. Tomato___Late_blight/*.jpg) = PlantVillage layout
--crops      crop prefixes to keep, or the single word  all  to use every class folder
--field-dir  OPTIONAL real-field test set in the same layout (e.g. PlantDoc). Reporting accuracy
             on it next to the PlantVillage number is the honest measure of real-world quality.
Outputs in --out: disease.onnx, labels.json, disease_metrics.json
"""
import argparse
import json
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms

IMG = 224
MEAN, STD = [0.485, 0.456, 0.406], [0.229, 0.224, 0.225]  # must match ml_service/app.py


class CropFolder(datasets.ImageFolder):
    """ImageFolder that keeps only classes whose folder name starts with one of the prefixes."""

    def __init__(self, root, prefixes, transform=None, classes=None):
        self._prefixes, self._fixed = prefixes, classes
        super().__init__(root, transform=transform)

    def find_classes(self, directory):
        names = sorted(d.name for d in Path(directory).iterdir() if d.is_dir())
        if self._fixed is not None:
            names = [n for n in names if n in self._fixed]
            names = sorted(names, key=self._fixed.index)
        else:
            if "all" not in self._prefixes:  # --crops all keeps every class folder
                names = [n for n in names if any(n.startswith(p) for p in self._prefixes)]
        return names, {n: i for i, n in enumerate(names)}


def evaluate(model, loader, device):
    model.eval()
    correct = total = 0
    with torch.no_grad():
        for x, y in loader:
            pred = model(x.to(device)).argmax(1).cpu()
            correct += (pred == y).sum().item()
            total += len(y)
    return correct / max(total, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="../models")
    ap.add_argument("--crops", nargs="+", default=["Tomato", "Potato", "Corn_(maize)", "Pepper,_bell"])
    ap.add_argument("--field-dir")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--val-split", type=float, default=0.15)
    ap.add_argument("--no-pretrained", action="store_true", help="skip ImageNet weights (tests only)")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    torch.manual_seed(0)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # Strong augmentation helps the model survive messy real-field photos.
    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(IMG, scale=(0.5, 1.0)), transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(25), transforms.ColorJitter(0.3, 0.3, 0.3, 0.05),
        transforms.ToTensor(), transforms.Normalize(MEAN, STD)])
    eval_tf = transforms.Compose([transforms.Resize((IMG, IMG)), transforms.ToTensor(),
                                  transforms.Normalize(MEAN, STD)])

    full_train = CropFolder(args.data, args.crops, transform=train_tf)
    full_eval = CropFolder(args.data, args.crops, transform=eval_tf)
    classes = full_train.classes
    print(f"{len(classes)} classes, {len(full_train)} images, device={device}")

    g = torch.Generator().manual_seed(0)
    perm = torch.randperm(len(full_train), generator=g).tolist()
    n_val = int(len(perm) * args.val_split)
    train_ds, val_ds = Subset(full_train, perm[n_val:]), Subset(full_eval, perm[:n_val])
    train_dl = DataLoader(train_ds, args.batch, shuffle=True, num_workers=args.workers)
    val_dl = DataLoader(val_ds, args.batch, num_workers=args.workers)

    weights = None if args.no_pretrained else models.MobileNet_V3_Small_Weights.DEFAULT
    model = models.mobilenet_v3_small(weights=weights)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(classes))
    model.to(device)

    # Stage 1: train only the new head. Stage 2: fine-tune everything at a lower LR.
    for p in model.features.parameters():
        p.requires_grad = False
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.1)
    best_acc, best_state = 0.0, None
    for epoch in range(args.epochs):
        if epoch == max(1, args.epochs // 3):
            for p in model.features.parameters():
                p.requires_grad = True
        lr = args.lr if epoch < max(1, args.epochs // 3) else args.lr / 10
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
        model.train()
        for x, y in train_dl:
            opt.zero_grad()
            loss = loss_fn(model(x.to(device)), y.to(device))
            loss.backward()
            opt.step()
        acc = evaluate(model, val_dl, device)
        print(f"epoch {epoch + 1}/{args.epochs}  val_acc={acc:.4f}")
        if acc >= best_acc:
            best_acc, best_state = acc, {k: v.cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)

    metrics = {"val_accuracy_plantvillage": round(best_acc, 4), "classes": len(classes)}
    if args.field_dir:
        field = CropFolder(args.field_dir, args.crops, transform=eval_tf, classes=classes)
        if len(field):
            metrics["field_accuracy"] = round(
                evaluate(model, DataLoader(field, args.batch, num_workers=args.workers), device), 4)
            metrics["field_images"] = len(field)
    print(json.dumps(metrics, indent=2))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.eval().cpu()
    torch.onnx.export(model, torch.randn(1, 3, IMG, IMG), str(out / "disease.onnx"),
                      input_names=["input"], output_names=["logits"],
                      dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17,
                      dynamo=False)
    (out / "labels.json").write_text(json.dumps(classes, indent=2))
    (out / "disease_metrics.json").write_text(json.dumps(metrics, indent=2))
    print("Saved disease.onnx, labels.json, disease_metrics.json to", out)


if __name__ == "__main__":
    main()