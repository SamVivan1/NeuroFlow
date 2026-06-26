import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


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


def get_model_score(model, X):
    """
    Mengambil skor continuous untuk threshold tuning dan ROC-AUC.

    Untuk model yang punya predict_proba, skor = probabilitas Parkinson.
    Untuk SVM, skor = decision_function.
    """

    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]

    if hasattr(model, "decision_function"):
        return model.decision_function(X)

    return model.predict(X)


def find_best_threshold(y_true, scores):
    """
    Mencari threshold terbaik berdasarkan Balanced Accuracy pada data training fold.

    Threshold tidak dicari dari test fold agar evaluasi tetap jujur.
    """

    scores = np.asarray(scores)
    y_true = np.asarray(y_true)

    min_score = float(np.min(scores))
    max_score = float(np.max(scores))

    thresholds = np.linspace(min_score, max_score, 300)

    best_threshold = 0.5
    best_balanced_acc = -1.0
    best_f1_macro = -1.0

    for threshold in thresholds:
        y_pred = (scores >= threshold).astype(int)

        balanced_acc = balanced_accuracy_score(y_true, y_pred)
        f1_macro = f1_score(y_true, y_pred, average="macro")

        if balanced_acc > best_balanced_acc:
            best_threshold = float(threshold)
            best_balanced_acc = float(balanced_acc)
            best_f1_macro = float(f1_macro)

    return {
        "threshold": best_threshold,
        "train_balanced_accuracy": best_balanced_acc,
        "train_f1_macro": best_f1_macro,
    }


def evaluate_with_threshold(y_true, scores, threshold):
    y_pred = (scores >= threshold).astype(int)

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro")),
        "confusion_matrix": confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1],
        ).tolist(),
    }

    if len(np.unique(y_true)) == 2:
        metrics["roc_auc"] = float(roc_auc_score(y_true, scores))
    else:
        metrics["roc_auc"] = None

    return metrics


def summarize_fold_metrics(fold_metrics):
    summary = {}

    for metric_name in ["accuracy", "balanced_accuracy", "f1_macro", "roc_auc"]:
        values = [
            item[metric_name]
            for item in fold_metrics
            if item[metric_name] is not None
        ]

        summary[metric_name] = {
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "values": [float(v) for v in values],
        }

    summary["confusion_matrices"] = [
        item["confusion_matrix"]
        for item in fold_metrics
    ]

    return summary


def load_feature_table(csv_path: Path):
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Feature CSV tidak ditemukan: {csv_path}\n"
            "Jalankan dulu: python training/train_pads_motion_features.py"
        )

    df = pd.read_csv(csv_path)

    required_columns = {"subject_id", "condition", "label"}

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(f"Kolom wajib hilang dari CSV: {missing}")

    feature_cols = [
        col for col in df.columns
        if col not in ["subject_id", "condition", "label"]
    ]

    X = df[feature_cols]
    y = df["label"].astype(int)

    return df, X, y, feature_cols


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--features-csv",
        type=str,
        default="training/data/processed/pads_motion_features_pd_vs_healthy.csv",
    )

    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    csv_path = Path(args.features_csv)

    report_dir = Path("training/reports/pads_motion")
    model_dir = Path("training/models")

    report_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    df, X, y, feature_cols = load_feature_table(csv_path)

    print("\n=== DATASET CHECK ===")
    print("Feature CSV:", csv_path)
    print("Subjects   :", len(df))
    print("Features   :", len(feature_cols))

    print("\nCondition distribution:")
    print(df["condition"].value_counts())

    print("\nLabel distribution:")
    print(y.value_counts().sort_index())
    print("0 = Healthy, 1 = Parkinson")

    cv = StratifiedKFold(
        n_splits=args.n_splits,
        shuffle=True,
        random_state=args.random_state,
    )

    models = build_models(args.random_state)
    all_results = {}

    for model_name, model in models.items():
        print(f"\n{'=' * 80}")
        print(f"MODEL: {model_name}")
        print(f"{'=' * 80}")

        fold_metrics = []
        thresholds = []

        for fold_idx, (train_idx, test_idx) in enumerate(cv.split(X, y), start=1):
            X_train = X.iloc[train_idx]
            X_test = X.iloc[test_idx]
            y_train = y.iloc[train_idx]
            y_test = y.iloc[test_idx]

            model.fit(X_train, y_train)

            train_scores = get_model_score(model, X_train)
            test_scores = get_model_score(model, X_test)

            threshold_info = find_best_threshold(y_train, train_scores)
            threshold = threshold_info["threshold"]

            test_metrics = evaluate_with_threshold(
                y_true=y_test,
                scores=test_scores,
                threshold=threshold,
            )

            fold_metrics.append(test_metrics)
            thresholds.append(threshold)

            print(f"\nFold {fold_idx}")
            print("Threshold    :", round(threshold, 6))
            print("Accuracy     :", round(test_metrics["accuracy"], 4))
            print("Balanced Acc.:", round(test_metrics["balanced_accuracy"], 4))
            print("F1 Macro     :", round(test_metrics["f1_macro"], 4))
            print("ROC-AUC      :", round(test_metrics["roc_auc"], 4))
            print("CM           :", test_metrics["confusion_matrix"])

        summary = summarize_fold_metrics(fold_metrics)
        summary["thresholds"] = [float(t) for t in thresholds]
        summary["threshold_mean"] = float(np.mean(thresholds))
        summary["threshold_std"] = float(np.std(thresholds))

        all_results[model_name] = summary

        print(f"\nSUMMARY {model_name}")
        print("Mean Accuracy     :", round(summary["accuracy"]["mean"], 4), "+/-", round(summary["accuracy"]["std"], 4))
        print("Mean Balanced Acc.:", round(summary["balanced_accuracy"]["mean"], 4), "+/-", round(summary["balanced_accuracy"]["std"], 4))
        print("Mean F1 Macro     :", round(summary["f1_macro"]["mean"], 4), "+/-", round(summary["f1_macro"]["std"], 4))
        print("Mean ROC-AUC      :", round(summary["roc_auc"]["mean"], 4), "+/-", round(summary["roc_auc"]["std"], 4))
        print("Mean Threshold    :", round(summary["threshold_mean"], 6))

    best_model_name = max(
        all_results.keys(),
        key=lambda name: all_results[name]["f1_macro"]["mean"],
    )

    best_summary = all_results[best_model_name]

    print("\n" + "=" * 80)
    print("BEST MODEL")
    print("=" * 80)
    print("Best model         :", best_model_name)
    print("Mean F1 Macro      :", round(best_summary["f1_macro"]["mean"], 4))
    print("Mean Balanced Acc. :", round(best_summary["balanced_accuracy"]["mean"], 4))
    print("Mean ROC-AUC       :", round(best_summary["roc_auc"]["mean"], 4))
    print("Mean Threshold     :", round(best_summary["threshold_mean"], 6))

    final_model = build_models(args.random_state)[best_model_name]
    final_model.fit(X, y)

    final_scores = get_model_score(final_model, X)
    final_threshold_info = find_best_threshold(y, final_scores)

    final_threshold = final_threshold_info["threshold"]

    model_path = model_dir / f"neuroflow_pads_pd_vs_healthy_{best_model_name}_cv.joblib"
    config_path = model_dir / f"neuroflow_pads_pd_vs_healthy_{best_model_name}_cv_config.json"
    report_path = report_dir / "pads_pd_vs_healthy_cv_threshold_report.json"

    joblib.dump(final_model, model_path)

    config = {
        "model_path": str(model_path),
        "model_name": best_model_name,
        "label_mapping": {
            "0": "Healthy",
            "1": "Parkinson",
        },
        "decision_rule": "score >= threshold => Parkinson",
        "threshold": float(final_threshold),
        "feature_columns": feature_cols,
        "feature_count": len(feature_cols),
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    report = {
        "task": "PADS Parkinson vs Healthy classification with 5-fold CV and threshold tuning",
        "subjects": int(len(df)),
        "label_distribution": {
            str(k): int(v)
            for k, v in y.value_counts().sort_index().items()
        },
        "best_model": best_model_name,
        "best_summary": best_summary,
        "all_results": all_results,
        "final_model_path": str(model_path),
        "final_config_path": str(config_path),
        "final_threshold_info": final_threshold_info,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nSaved model :", model_path)
    print("Saved config:", config_path)
    print("Saved report:", report_path)


if __name__ == "__main__":
    main()
