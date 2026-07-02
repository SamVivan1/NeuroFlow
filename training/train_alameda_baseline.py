import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit, StratifiedShuffleSplit
from sklearn.pipeline import Pipeline


TARGET_COLUMNS = [
    "Constancy_of_rest",
    "Kinetic_tremor",
    "Postural_tremor",
    "Rest_tremor",
]


def load_dataset(csv_path: Path, target: str):
    """
    Membaca dataset ALAMEDA dan memisahkan fitur, label, dan subject_id.
    subject_id tidak boleh masuk fitur karena bisa menyebabkan data leakage.
    """

    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset tidak ditemukan: {csv_path}")

    df = pd.read_csv(csv_path)

    if target not in df.columns:
        raise ValueError(
            f"Target '{target}' tidak ada di dataset. "
            f"Target tersedia: {[c for c in TARGET_COLUMNS if c in df.columns]}"
        )

    y = df[target].astype(int)

    if y.nunique() < 2:
        raise ValueError(
            f"Target '{target}' hanya memiliki satu kelas: {y.unique().tolist()}. "
            "Model klasifikasi biner tidak bisa dilatih secara valid."
        )

    drop_cols = []

    for col in ["start_timestamp", "end_timestamp"]:
        if col in df.columns:
            drop_cols.append(col)

    for col in TARGET_COLUMNS:
        if col in df.columns:
            drop_cols.append(col)

    if "subject_id" in df.columns:
        groups = df["subject_id"]
        drop_cols.append("subject_id")
    else:
        groups = None

    X = df.drop(columns=drop_cols, errors="ignore")
    X = X.select_dtypes(include=[np.number])

    if X.empty:
        raise ValueError("Tidak ada fitur numerik yang bisa digunakan untuk training.")

    print("\n=== DATASET CHECK ===")
    print(f"Target: {target}")
    print("Total samples:", len(df))
    print("Feature count:", X.shape[1])
    print("Label distribution:")
    print(y.value_counts().sort_index())

    if groups is not None:
        subject_label = pd.DataFrame({"subject_id": groups, "target": y})
        subject_label = subject_label.groupby("subject_id")["target"].max()
        print("\nSubject-level distribution:")
        print(subject_label.value_counts().sort_index())

    return X, y, groups


def split_data(X, y, groups, test_size: float, random_state: int):
    """
    Split utama memakai subject_id agar window dari pasien yang sama tidak bocor
    ke train dan test.

    Karena dataset kecil dan imbalanced, split diulang sampai train dan test
    sama-sama punya kelas 0 dan 1.
    """

    def has_two_classes(labels):
        return len(np.unique(labels)) == 2

    if groups is not None:
        splitter = GroupShuffleSplit(
            n_splits=500,
            test_size=test_size,
            random_state=random_state,
        )

        for train_idx, test_idx in splitter.split(X, y, groups=groups):
            y_train_candidate = y.iloc[train_idx]
            y_test_candidate = y.iloc[test_idx]

            if has_two_classes(y_train_candidate) and has_two_classes(y_test_candidate):
                print("\nSplit mode: GroupShuffleSplit berbasis subject_id")
                return (
                    X.iloc[train_idx],
                    X.iloc[test_idx],
                    y.iloc[train_idx],
                    y.iloc[test_idx],
                )

        print(
            "\nWARNING: Group split gagal menghasilkan train/test dengan dua kelas."
            "\nFallback ke StratifiedShuffleSplit."
            "\nCatatan: ini hanya untuk eksperimen awal karena subject yang sama bisa bocor antar split.\n"
        )

    stratified_splitter = StratifiedShuffleSplit(
        n_splits=1,
        test_size=test_size,
        random_state=random_state,
    )

    train_idx, test_idx = next(stratified_splitter.split(X, y))

    print("\nSplit mode: StratifiedShuffleSplit fallback")

    return (
        X.iloc[train_idx],
        X.iloc[test_idx],
        y.iloc[train_idx],
        y.iloc[test_idx],
    )


def build_model(random_state: int):
    """
    Random Forest dipakai sebagai baseline karena dataset ALAMEDA sudah berbentuk fitur,
    bukan raw time-series.
    """

    model = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=500,
                    max_depth=None,
                    min_samples_leaf=2,
                    class_weight="balanced_subsample",
                    random_state=random_state,
                    n_jobs=-1,
                ),
            ),
        ]
    )

    return model


def evaluate_model(model, X_test, y_test):
    """
    Evaluasi model.
    Confusion matrix dipaksa memakai label [0, 1] agar bentuknya selalu 2x2.
    ROC-AUC hanya dihitung jika y_test punya dua kelas.
    """

    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
        "confusion_matrix": confusion_matrix(
            y_test,
            y_pred,
            labels=[0, 1],
        ).tolist(),
        "classification_report": classification_report(
            y_test,
            y_pred,
            labels=[0, 1],
            output_dict=True,
            zero_division=0,
        ),
    }

    unique_classes = np.unique(y_test)

    if hasattr(model, "predict_proba") and len(unique_classes) == 2:
        y_prob_all = model.predict_proba(X_test)

        # Ambil probabilitas kelas positif yaitu label 1.
        positive_class_index = list(model.classes_).index(1)
        y_prob = y_prob_all[:, positive_class_index]

        metrics["roc_auc"] = float(roc_auc_score(y_test, y_prob))
    else:
        metrics["roc_auc"] = None

    return metrics


def save_outputs(model, metadata, model_path: Path, report_path: Path):
    joblib.dump(model, model_path)

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\nTraining selesai.")
    print(f"Target        : {metadata['target']}")
    print(f"Model saved   : {model_path}")
    print(f"Report saved  : {report_path}")
    print(f"Accuracy      : {metadata['metrics']['accuracy']:.4f}")
    print(f"Balanced Acc. : {metadata['metrics']['balanced_accuracy']:.4f}")
    print(f"F1 Macro      : {metadata['metrics']['f1_macro']:.4f}")
    print(f"ROC-AUC       : {metadata['metrics']['roc_auc']}")
    print("Confusion Mat.:", metadata["metrics"]["confusion_matrix"])


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--csv",
        type=str,
        default="training/data/ALAMEDA_PD_tremor_dataset.csv",
        help="Path ke dataset ALAMEDA CSV.",
    )

    parser.add_argument(
        "--target",
        type=str,
        default="Rest_tremor",
        choices=TARGET_COLUMNS,
        help="Target tremor yang ingin diklasifikasikan.",
    )

    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proporsi data test.",
    )

    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Seed agar hasil eksperimen stabil.",
    )

    args = parser.parse_args()

    csv_path = Path(args.csv)

    model_dir = Path("training/models")
    report_dir = Path("training/reports")

    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    X, y, groups = load_dataset(csv_path, args.target)

    X_train, X_test, y_train, y_test = split_data(
        X,
        y,
        groups,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    print("\n=== SPLIT CHECK ===")
    print("Train samples:", len(X_train))
    print("Test samples :", len(X_test))
    print("Train label distribution:")
    print(y_train.value_counts().sort_index())
    print("Test label distribution:")
    print(y_test.value_counts().sort_index())

    model = build_model(random_state=args.random_state)
    model.fit(X_train, y_train)

    metrics = evaluate_model(model, X_test, y_test)

    model_path = model_dir / f"neuroflow_{args.target}_rf.joblib"
    report_path = report_dir / f"neuroflow_{args.target}_metrics.json"

    metadata = {
        "target": args.target,
        "model_type": "RandomForestClassifier",
        "dataset": str(csv_path),
        "n_features": int(X.shape[1]),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "features": list(X.columns),
        "metrics": metrics,
    }

    save_outputs(model, metadata, model_path, report_path)


if __name__ == "__main__":
    main()