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
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


N_TASKS = 11
N_WRISTS = 2
N_TIMESTEPS = 976
N_CHANNELS = 6
SAMPLING_RATE = 100

CHANNEL_NAMES = [
    "acc_x",
    "acc_y",
    "acc_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]


def find_pads_dirs(base_dir: Path):
    """
    Mencari folder movement preprocessed dan folder patient metadata.
    Struktur PADS bisa sedikit berbeda tergantung sumber download.
    """

    movement_bin_dir = base_dir / "preprocessed" / "movement"
    patients_dir = base_dir / "patients"

    if not movement_bin_dir.exists():
        raise FileNotFoundError(
            f"Folder bin tidak ditemukan: {movement_bin_dir}\n"
            "Pastikan file *_ml.bin ada di training/data/pads/preprocessed/movement."
        )

    if not patients_dir.exists():
        raise FileNotFoundError(
            f"Folder patients tidak ditemukan: {patients_dir}\n"
            "Cek dengan command: find training/data/pads -maxdepth 3 -type d | sort"
        )

    return movement_bin_dir, patients_dir


def load_patient_condition(patients_dir: Path, subject_id: str):
    """
    Membaca label diagnosis dari patients/patient_xxx.json.
    Field utama yang dipakai adalah 'condition'.
    """

    patient_path = patients_dir / f"patient_{subject_id}.json"

    if not patient_path.exists():
        return None

    with open(patient_path, "r", encoding="utf-8") as f:
        patient = json.load(f)

    condition = patient.get("condition")

    if condition is None:
        return None

    return str(condition)


def condition_to_label(condition: str):
    """
    Target awal dibuat ketat:
    1 = Parkinson's Disease
    0 = Healthy

    Atypical Parkinsonism dan diagnosis lain dibuang dulu agar baseline bersih.
    """

    c = condition.lower().strip()

    if c in ["parkinson's", "parkinsons", "parkinson"]:
        return 1

    if c in ["healthy", "healthy control", "control"]:
        return 0

    return None

def load_bin_as_tensor(path: Path):
    """
    Membaca file *_ml.bin sebagai raw float32.
    Berdasarkan inspeksi lokal:
    total float = 128832 = 11 * 2 * 976 * 6.
    """

    arr = np.fromfile(path, dtype=np.float32)

    expected_size = N_TASKS * N_WRISTS * N_TIMESTEPS * N_CHANNELS

    if arr.size != expected_size:
        raise ValueError(
            f"Ukuran file tidak sesuai untuk {path.name}. "
            f"Dapat {arr.size}, expected {expected_size}."
        )

    return arr.reshape(N_TASKS, N_WRISTS, N_TIMESTEPS, N_CHANNELS)


def safe_power_ratio(numerator: float, denominator: float):
    """
    Menghindari division-by-zero pada rasio energi frekuensi.
    """

    eps = 1e-8
    return float(numerator / (denominator + eps))


def band_power(signal: np.ndarray, fs: int, low: float, high: float):
    """
    Menghitung energi sinyal pada rentang frekuensi tertentu menggunakan FFT.
    Ini berguna untuk membedakan gerakan lambat, tremor Parkinson, dan noise tinggi.
    """

    signal = np.asarray(signal, dtype=np.float32)

    # Kurangi komponen DC agar frekuensi 0 Hz tidak mendominasi.
    signal = signal - np.mean(signal)

    spectrum = np.fft.rfft(signal)

    power = np.abs(spectrum) ** 2

    freqs = np.fft.rfftfreq(signal.size, d=1.0 / fs)

    mask = (freqs >= low) & (freqs <= high)

    if not np.any(mask):
        return 0.0

    return float(np.sum(power[mask]))


def dominant_frequency(signal: np.ndarray, fs: int, low: float = 0.5, high: float = 15.0):
    """
    Mengambil frekuensi dominan pada rentang 0.5–15 Hz.
    Rentang ini relevan untuk gerakan tangan dan tremor.
    """

    signal = np.asarray(signal, dtype=np.float32)
    signal = signal - np.mean(signal)

    spectrum = np.fft.rfft(signal)
    power = np.abs(spectrum) ** 2
    freqs = np.fft.rfftfreq(signal.size, d=1.0 / fs)

    mask = (freqs >= low) & (freqs <= high)

    if not np.any(mask):
        return 0.0

    masked_power = power[mask]
    masked_freqs = freqs[mask]

    return float(masked_freqs[np.argmax(masked_power)])


def extract_signal_features(signal: np.ndarray, prefix: str):
    """
    Mengekstrak fitur statistik dan frekuensi dari satu sinyal 1D.
    """

    signal = np.asarray(signal, dtype=np.float32)

    q75, q25 = np.percentile(signal, [75, 25])

    total_energy = band_power(signal, SAMPLING_RATE, 0.5, 15.0)
    slow_energy = band_power(signal, SAMPLING_RATE, 0.5, 3.0)
    parkinson_energy = band_power(signal, SAMPLING_RATE, 4.0, 6.0)
    motion_tremor_energy = band_power(signal, SAMPLING_RATE, 3.0, 8.0)
    high_tremor_energy = band_power(signal, SAMPLING_RATE, 8.0, 12.0)

    features = {
        f"{prefix}_mean": float(np.mean(signal)),
        f"{prefix}_std": float(np.std(signal)),
        f"{prefix}_rms": float(np.sqrt(np.mean(signal ** 2))),
        f"{prefix}_min": float(np.min(signal)),
        f"{prefix}_max": float(np.max(signal)),
        f"{prefix}_ptp": float(np.ptp(signal)),
        f"{prefix}_median": float(np.median(signal)),
        f"{prefix}_iqr": float(q75 - q25),
        f"{prefix}_dom_freq": dominant_frequency(signal, SAMPLING_RATE),
        f"{prefix}_energy_0p5_3hz": slow_energy,
        f"{prefix}_energy_3_8hz": motion_tremor_energy,
        f"{prefix}_energy_4_6hz": parkinson_energy,
        f"{prefix}_energy_8_12hz": high_tremor_energy,
        f"{prefix}_ratio_4_6_to_total": safe_power_ratio(parkinson_energy, total_energy),
        f"{prefix}_ratio_3_8_to_total": safe_power_ratio(motion_tremor_energy, total_energy),
        f"{prefix}_ratio_4_6_to_0p5_3": safe_power_ratio(parkinson_energy, slow_energy),
    }

    return features


def extract_features_from_tensor(tensor: np.ndarray):
    """
    Ekstraksi fitur dari satu subject.

    Input shape:
    (11 task, 2 wrist, 976 timestep, 6 channel)

    Output:
    dict fitur tabular untuk model classical ML.
    """

    features = {}

    for task_idx in range(N_TASKS):
        for wrist_idx in range(N_WRISTS):
            segment = tensor[task_idx, wrist_idx, :, :]

            wrist_name = "left" if wrist_idx == 0 else "right"
            base_prefix = f"task{task_idx:02d}_{wrist_name}"

            acc = segment[:, 0:3]
            gyro = segment[:, 3:6]

            acc_mag = np.sqrt(np.sum(acc ** 2, axis=1))
            gyro_mag = np.sqrt(np.sum(gyro ** 2, axis=1))

            features.update(
                extract_signal_features(
                    acc_mag,
                    f"{base_prefix}_acc_mag",
                )
            )

            features.update(
                extract_signal_features(
                    gyro_mag,
                    f"{base_prefix}_gyro_mag",
                )
            )

            for ch_idx, ch_name in enumerate(CHANNEL_NAMES):
                features.update(
                    extract_signal_features(
                        segment[:, ch_idx],
                        f"{base_prefix}_{ch_name}",
                    )
                )

    return features


def build_feature_table(base_dir: Path):
    movement_bin_dir, patients_dir = find_pads_dirs(base_dir)

    rows = []
    skipped = []

    bin_files = sorted(movement_bin_dir.glob("*_ml.bin"))

    if not bin_files:
        raise FileNotFoundError(f"Tidak ada *_ml.bin di {movement_bin_dir}")

    for bin_path in bin_files:
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
            tensor = load_bin_as_tensor(bin_path)
            features = extract_features_from_tensor(tensor)
        except Exception as e:
            skipped.append((subject_id, f"load_or_feature_error={repr(e)}"))
            continue

        features["subject_id"] = subject_id
        features["condition"] = condition
        features["label"] = label

        rows.append(features)

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "Feature table kosong. Kemungkinan folder patients tidak cocok "
            "atau field condition tidak terbaca."
        )

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
    }


def evaluate_model(model, X_train, X_test, y_train, y_test):
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, y_pred)),
        "f1_macro": float(f1_score(y_test, y_pred, average="macro")),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist(),
        "classification_report": classification_report(
            y_test,
            y_pred,
            labels=[0, 1],
            target_names=["Healthy", "Parkinson"],
            output_dict=True,
            zero_division=0,
        ),
    }

    if hasattr(model, "predict_proba") and len(np.unique(y_test)) == 2:
        y_prob = model.predict_proba(X_test)[:, 1]
        metrics["roc_auc"] = float(roc_auc_score(y_test, y_prob))
    else:
        metrics["roc_auc"] = None

    return metrics


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--base-dir",
        type=str,
        default="training/data/pads",
        help="Folder root dataset PADS.",
    )

    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Proporsi test set subject-level.",
    )

    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
    )

    args = parser.parse_args()

    base_dir = Path(args.base_dir)

    processed_dir = Path("training/data/processed")
    model_dir = Path("training/models")
    report_dir = Path("training/reports/pads_motion")

    processed_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    print("\n=== BUILD FEATURE TABLE ===")
    df, skipped = build_feature_table(base_dir)

    feature_csv_path = processed_dir / "pads_motion_features_pd_vs_healthy.csv"
    df.to_csv(feature_csv_path, index=False)

    print("Feature table saved:", feature_csv_path)
    print("Total usable subjects:", len(df))
    print("Skipped subjects:", len(skipped))

    print("\nCondition distribution:")
    print(df["condition"].value_counts())

    print("\nLabel distribution:")
    print(df["label"].value_counts().sort_index())
    print("0 = Healthy, 1 = Parkinson")

    feature_cols = [
        c for c in df.columns
        if c not in ["subject_id", "condition", "label"]
    ]

    X = df[feature_cols]
    y = df["label"].astype(int)

    splitter = StratifiedShuffleSplit(
        n_splits=1,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    train_idx, test_idx = next(splitter.split(X, y))

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    print("\n=== SPLIT CHECK ===")
    print("Train subjects:", len(X_train))
    print("Test subjects :", len(X_test))
    print("Train labels:")
    print(y_train.value_counts().sort_index())
    print("Test labels:")
    print(y_test.value_counts().sort_index())

    models = build_models(args.random_state)

    all_results = {}

    for model_name, model in models.items():
        print(f"\n=== TRAINING {model_name} ===")

        metrics = evaluate_model(model, X_train, X_test, y_train, y_test)

        all_results[model_name] = metrics

        print("Accuracy      :", round(metrics["accuracy"], 4))
        print("Balanced Acc. :", round(metrics["balanced_accuracy"], 4))
        print("F1 Macro      :", round(metrics["f1_macro"], 4))
        print("ROC-AUC       :", metrics["roc_auc"])
        print("Confusion Mat.:", metrics["confusion_matrix"])

    best_model_name = max(
        all_results.keys(),
        key=lambda name: all_results[name]["f1_macro"],
    )

    print("\n=== BEST MODEL ===")
    print("Best model:", best_model_name)
    print("Best F1   :", all_results[best_model_name]["f1_macro"])
    print("Best BAcc :", all_results[best_model_name]["balanced_accuracy"])

    final_model = build_models(args.random_state)[best_model_name]
    final_model.fit(X, y)

    final_model_path = model_dir / f"neuroflow_pads_pd_vs_healthy_{best_model_name}.joblib"
    joblib.dump(final_model, final_model_path)

    report = {
        "task": "PADS Parkinson vs Healthy classification",
        "input_shape_assumption": [N_TASKS, N_WRISTS, N_TIMESTEPS, N_CHANNELS],
        "sampling_rate": SAMPLING_RATE,
        "label_mapping": {
            "0": "Healthy Control",
            "1": "Parkinson's",
        },
        "total_subjects_used": int(len(df)),
        "skipped_subjects": skipped[:100],
        "feature_count": int(len(feature_cols)),
        "feature_csv": str(feature_csv_path),
        "best_model": best_model_name,
        "results": all_results,
        "final_model_path": str(final_model_path),
    }

    report_path = report_dir / "pads_pd_vs_healthy_report.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nModel saved :", final_model_path)
    print("Report saved:", report_path)


if __name__ == "__main__":
    main()
