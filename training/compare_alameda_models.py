import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


TARGET_COLUMNS = [
    "Constancy_of_rest",
    "Kinetic_tremor",
    "Postural_tremor",
    "Rest_tremor",
]


def load_dataset(csv_path: Path, target: str):
    df = pd.read_csv(csv_path)

    if target not in df.columns:
        raise ValueError(f"Target {target} tidak ditemukan.")

    if "subject_id" not in df.columns:
        raise ValueError("Dataset wajib punya subject_id untuk evaluasi yang jujur.")

    y = df[target].astype(int)
    groups = df["subject_id"]

    drop_cols = ["subject_id", "start_timestamp", "end_timestamp"]

    for col in TARGET_COLUMNS:
        if col in df.columns:
            drop_cols.append(col)

    X = df.drop(columns=drop_cols, errors="ignore")
    X = X.select_dtypes(include=[np.number])

    return X, y, groups


def get_subject_level_counts(y, groups):
    subject_label = pd.DataFrame({"subject_id": groups, "target": y})
    subject_label = subject_label.groupby("subject_id")["target"].max()
    return subject_label.value_counts().sort_index()


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
                        max_iter=3000,
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
                        probability=True,
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
        "hist_gradient_boosting": Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "classifier",
                    HistGradientBoostingClassifier(
                        learning_rate=0.05,
                        max_iter=300,
                        random_state=random_state,
                    ),
                ),
            ]
        ),
    }


def evaluate_fold(model, X_train, X_test, y_train, y_test):
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    result = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist(),
    }

    if len(np.unique(y_test)) == 2 and hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
        result["roc_auc"] = float(roc_auc_score(y_test, y_prob))
    else:
        result["roc_auc"] = None

    return result


def summarize_results(fold_results):
    summary = {}

    for metric in ["accuracy", "balanced_accuracy", "f1_macro", "roc_auc"]:
        values = [
            r[metric]
            for r in fold_results
            if r[metric] is not None and not np.isnan(r[metric])
        ]

        if len(values) == 0:
            summary[metric] = None
        else:
            summary[metric] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "values": [float(v) for v in values],
            }

    summary["confusion_matrices"] = [r["confusion_matrix"] for r in fold_results]

    return summary


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--csv",
        type=str,
        default="training/data/ALAMEDA_PD_tremor_dataset.csv",
    )

    parser.add_argument(
        "--target",
        type=str,
        default="Rest_tremor",
        choices=TARGET_COLUMNS,
    )

    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    csv_path = Path(args.csv)

    output_dir = Path("training/reports/model_comparison")
    model_dir = Path("training/models")

    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    X, y, groups = load_dataset(csv_path, args.target)

    subject_counts = get_subject_level_counts(y, groups)

    print("\n=== DATASET CHECK ===")
    print("Target:", args.target)
    print("Samples:", len(X))
    print("Features:", X.shape[1])
    print("\nWindow-level label distribution:")
    print(y.value_counts().sort_index())
    print("\nSubject-level label distribution:")
    print(subject_counts)

    if 0 not in subject_counts.index or 1 not in subject_counts.index:
        raise ValueError("Subject-level hanya punya satu kelas. Evaluasi valid tidak mungkin.")

    n_negative_subjects = int(subject_counts.loc[0])
    n_positive_subjects = int(subject_counts.loc[1])

    n_splits = min(5, n_negative_subjects, n_positive_subjects)

    if n_splits < 2:
        raise ValueError("Jumlah subject positif/negatif terlalu sedikit untuk cross-validation.")

    print(f"\nCV mode: StratifiedGroupKFold")
    print(f"n_splits: {n_splits}")

    cv = StratifiedGroupKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=args.random_state,
    )

    models = build_models(args.random_state)
    all_results = {}

    for model_name, model in models.items():
        print(f"\n=== Training model: {model_name} ===")

        fold_results = []

        for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X, y, groups=groups), start=1):
            X_train = X.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_train = y.iloc[train_idx]
            y_test = y.iloc[test_idx]

            print(f"\nFold {fold_idx}")
            print("Train labels:")
            print(y_train.value_counts().sort_index())
            print("Test labels:")
            print(y_test.value_counts().sort_index())

            if y_train.nunique() < 2 or y_test.nunique() < 2:
                print("Skip fold karena train/test hanya punya satu kelas.")
                continue

            fold_result = evaluate_fold(model, X_train, X_test, y_train, y_test)
            fold_results.append(fold_result)

            print("Balanced Acc:", round(fold_result["balanced_accuracy"], 4))
            print("F1 Macro    :", round(fold_result["f1_macro"], 4))
            print("ROC-AUC     :", fold_result["roc_auc"])
            print("CM          :", fold_result["confusion_matrix"])

        if len(fold_results) == 0:
            print(f"Model {model_name} tidak punya fold valid.")
            continue

        summary = summarize_results(fold_results)

        all_results[model_name] = summary

        mean_bal_acc = summary["balanced_accuracy"]["mean"]
        mean_f1 = summary["f1_macro"]["mean"]

        print(f"\nSummary {model_name}")
        print("Mean Balanced Acc:", round(mean_bal_acc, 4))
        print("Mean F1 Macro    :", round(mean_f1, 4))

    if not all_results:
        raise RuntimeError("Tidak ada model yang berhasil dievaluasi.")

    best_model_name = max(
        all_results.keys(),
        key=lambda name: all_results[name]["f1_macro"]["mean"],
    )

    print("\n=== BEST MODEL ===")
    print("Best:", best_model_name)
    print("F1 Macro Mean:", all_results[best_model_name]["f1_macro"]["mean"])
    print("Balanced Acc :", all_results[best_model_name]["balanced_accuracy"]["mean"])

    report = {
        "target": args.target,
        "cv": "StratifiedGroupKFold",
        "n_splits": n_splits,
        "results": all_results,
        "best_model": best_model_name,
    }

    report_path = output_dir / f"{args.target}_model_comparison.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nReport saved:", report_path)

    final_model = build_models(args.random_state)[best_model_name]
    final_model.fit(X, y)

    final_model_path = model_dir / f"neuroflow_{args.target}_{best_model_name}_final.joblib"
    joblib.dump(final_model, final_model_path)

    print("Final model trained on all data:", final_model_path)


if __name__ == "__main__":
    main()