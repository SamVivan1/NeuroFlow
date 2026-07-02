import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

from ml_service.app.signal_features import extract_mpu_window_features  # noqa: E402


N_TASKS = 11
N_WRISTS = 2
N_TIMESTEPS = 976
N_CHANNELS = 6
SAMPLING_RATE_HZ = 100.0


def condition_to_label(condition: str):
    c = condition.lower().strip()

    if c in ["parkinson's", "parkinsons", "parkinson"]:
        return 1

    if c in ["healthy", "healthy control", "control"]:
        return 0

    return None


def load_patient_condition(patients_dir: Path, subject_id: str):
    patient_path = patients_dir / f"patient_{subject_id}.json"

    if not patient_path.exists():
        return None

    with open(patient_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    condition = data.get("condition")

    if condition is None:
        return None

    return str(condition)


def load_subject_tensor(bin_path: Path):
    arr = np.fromfile(bin_path, dtype=np.float32)

    expected = N_TASKS * N_WRISTS * N_TIMESTEPS * N_CHANNELS

    if arr.size != expected:
        raise ValueError(f"Invalid size for {bin_path.name}: got {arr.size}, expected {expected}")

    return arr.reshape(N_TASKS, N_WRISTS, N_TIMESTEPS, N_CHANNELS)


def build_window_dataset(base_dir: Path):
    movement_dir = base_dir / "preprocessed" / "movement"
    patients_dir = base_dir / "patients"

    if not movement_dir.exists():
        raise FileNotFoundError(f"Folder tidak ditemukan: {movement_dir}")

    if not patients_dir.exists():
        raise FileNotFoundError(f"Folder tidak ditemukan: {patients_dir}")

    rows = []
    skipped = []

    for bin_path in sorted(movement_dir.glob("*_ml.bin")):
        subject_id = bin_path.name.replace("_ml.bin", "")

        condition = load_patient_condition(patients_dir, subject_id)

        if condition is None:
            skipped.append((subject_id, "missing_condition"))
            continue

        label = condition_to_label(condition)

        if label is None:
            skipped.append((subject_id, f"excluded_condition={condition}"))
            continue

        try:
            tensor = load_subject_tensor(bin_path)
        except Exception as exc:
            skipped.append((subject_id, f"load_error={exc}"))
            continue

        for task_idx in range(N_TASKS):
            for wrist_idx in range(N_WRISTS):
                window = tensor[task_idx, wrist_idx, :, :]

                features = extract_mpu_window_features(
                    ax=window[:, 0],
                    ay=window[:, 1],
                    az=window[:, 2],
                    gx=window[:, 3],
                    gy=window[:, 4],
                    gz=window[:, 5],
                    sampling_rate_hz=SAMPLING_RATE_HZ,
                )

                features["subject_id"] = subject_id
                features["condition"] = condition
                features["label"] = label
                features["task_idx"] = task_idx
                features["wrist_idx"] = wrist_idx

                rows.append(features)

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError("Dataset window kosong. Cek path PADS.")

    return df, skipped


def build_models(random_state: int):
    return {
        "logreg": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=5000,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        "svm_rbf": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    SVC(
                        kernel="rbf",
                        C=1.0,
                        gamma="scale",
                        class_weight="balanced",
                        probability=False,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
        "random_forest": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=700,
                        min_samples_leaf=2,
                        class_weight="balanced_subsample",
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "extra_trees": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "classifier",
                    ExtraTreesClassifier(
                        n_estimators=700,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }


def get_scores(model, X):
    if hasattr(model, "decision_function"):
        return model.decision_function(X)

    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]

    return model.predict(X)


def find_best_threshold(y_true, scores):
    scores = np.asarray(scores)
    y_true = np.asarray(y_true)

    thresholds = np.linspace(float(scores.min()), float(scores.max()), 300)

    best = {
        "threshold": 0.0,
        "balanced_accuracy": -1.0,
        "f1_macro": -1.0,
    }

    for threshold in thresholds:
        y_pred = (scores >= threshold).astype(int)

        bacc = balanced_accuracy_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred, average="macro")

        if bacc > best["balanced_accuracy"]:
            best = {
                "threshold": float(threshold),
                "balanced_accuracy": float(bacc),
                "f1_macro": float(f1),
            }

    return best


def evaluate_with_threshold(y_true, scores, threshold):
    y_pred = (scores >= threshold).astype(int)

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "roc_auc": float(roc_auc_score(y_true, scores)),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist(),
    }


def summarize(metrics):
    output = {}

    for key in ["accuracy", "balanced_accuracy", "f1_macro", "roc_auc"]:
        values = [m[key] for m in metrics]

        output[key] = {
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "values": [float(v) for v in values],
        }

    output["confusion_matrices"] = [m["confusion_matrix"] for m in metrics]

    return output


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--base-dir",
        default="training/data/pads",
        help="Root folder dataset PADS.",
    )

    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
    )

    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    base_dir = Path(args.base_dir)

    processed_dir = Path("training/data/processed")
    model_dir = Path("ml_service/models")
    report_dir = Path("training/reports/pads_window_model")

    processed_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== BUILD WINDOW DATASET ===")
    df, skipped = build_window_dataset(base_dir)

    feature_csv = processed_dir / "pads_window_features_pd_vs_healthy.csv"
    df.to_csv(feature_csv, index=False)

    print("Saved feature CSV:", feature_csv)
    print("Rows:", len(df))
    print("Subjects:", df["subject_id"].nunique())
    print("Skipped subjects:", len(skipped))

    print("\nCondition distribution:")
    print(df[["subject_id", "condition"]].drop_duplicates()["condition"].value_counts())

    print("\nWindow label distribution:")
    print(df["label"].value_counts().sort_index())

    drop_cols = ["subject_id", "condition", "label", "task_idx", "wrist_idx"]

    feature_cols = [c for c in df.columns if c not in drop_cols]

    X = df[feature_cols]
    y = df["label"].astype(int)
    groups = df["subject_id"]

    cv = StratifiedGroupKFold(
        n_splits=args.n_splits,
        shuffle=True,
        random_state=args.random_state,
    )

    models = build_models(args.random_state)

    all_results = {}

    for model_name, base_model in models.items():
        print("\n" + "=" * 80)
        print("MODEL:", model_name)
        print("=" * 80)

        fold_metrics = []
        thresholds = []

        for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X, y, groups), start=1):
            model = clone(base_model)

            X_train = X.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_train = y.iloc[train_idx]
            y_test = y.iloc[test_idx]

            model.fit(X_train, y_train)

            train_scores = get_scores(model, X_train)
            test_scores = get_scores(model, X_test)

            threshold_info = find_best_threshold(y_train, train_scores)
            threshold = threshold_info["threshold"]

            metrics = evaluate_with_threshold(y_test, test_scores, threshold)

            fold_metrics.append(metrics)
            thresholds.append(threshold)

            print(f"\nFold {fold_idx}")
            print("Threshold    :", round(threshold, 6))
            print("Accuracy     :", round(metrics["accuracy"], 4))
            print("Balanced Acc.:", round(metrics["balanced_accuracy"], 4))
            print("F1 Macro     :", round(metrics["f1_macro"], 4))
            print("ROC-AUC      :", round(metrics["roc_auc"], 4))
            print("CM           :", metrics["confusion_matrix"])

        summary = summarize(fold_metrics)
        summary["thresholds"] = thresholds
        summary["threshold_mean"] = float(np.mean(thresholds))
        summary["threshold_std"] = float(np.std(thresholds))

        all_results[model_name] = summary

        print("\nSUMMARY", model_name)
        print("Mean Balanced Acc.:", round(summary["balanced_accuracy"]["mean"], 4))
        print("Mean F1 Macro     :", round(summary["f1_macro"]["mean"], 4))
        print("Mean ROC-AUC      :", round(summary["roc_auc"]["mean"], 4))
        print("Mean Threshold    :", round(summary["threshold_mean"], 6))

    best_model_name = max(
        all_results.keys(),
        key=lambda name: all_results[name]["f1_macro"]["mean"],
    )

    print("\n" + "=" * 80)
    print("BEST MODEL")
    print("=" * 80)
    print("Best model:", best_model_name)
    print("F1 Macro :", all_results[best_model_name]["f1_macro"]["mean"])
    print("BAcc     :", all_results[best_model_name]["balanced_accuracy"]["mean"])
    print("ROC-AUC  :", all_results[best_model_name]["roc_auc"]["mean"])

    final_model = build_models(args.random_state)[best_model_name]
    final_model.fit(X, y)

    final_scores = get_scores(final_model, X)
    final_threshold_info = find_best_threshold(y, final_scores)

    final_threshold = final_threshold_info["threshold"]

    model_path = model_dir / f"neuroflow_raw_mpu_window_{best_model_name}.joblib"
    config_path = model_dir / f"neuroflow_raw_mpu_window_{best_model_name}_config.json"
    report_path = report_dir / "raw_mpu_window_model_report.json"

    joblib.dump(final_model, model_path)

    config = {
        "model_name": best_model_name,
        "model_path": str(model_path),
        "threshold": float(final_threshold),
        "feature_columns": feature_cols,
        "feature_count": len(feature_cols),
        "sampling_rate_hz": SAMPLING_RATE_HZ,
        "label_mapping": {
            "0": "Healthy / Non-Parkinson-like",
            "1": "Parkinson Motor Pattern",
        },
        "decision_rule": "score >= threshold => Parkinson Motor Pattern",
        "stress_note": "This model does not classify stress tremor. Stress requires HR/HRV or a stress-labeled dataset.",
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    report = {
        "task": "Raw MPU window-level Parkinson motor-pattern model",
        "dataset": "PADS",
        "rows": int(len(df)),
        "subjects": int(df["subject_id"].nunique()),
        "feature_csv": str(feature_csv),
        "best_model": best_model_name,
        "best_summary": all_results[best_model_name],
        "all_results": all_results,
        "final_threshold_info": final_threshold_info,
        "model_path": str(model_path),
        "config_path": str(config_path),
        "skipped_subjects_sample": skipped[:50],
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nSaved model :", model_path)
    print("Saved config:", config_path)
    print("Saved report:", report_path)


if __name__ == "__main__":
    main()
