from pathlib import Path

import pandas as pd


CSV_PATH = Path("training/data/ALAMEDA_PD_tremor_dataset.csv")

TARGET_COLUMNS = [
    "Constancy_of_rest",
    "Kinetic_tremor",
    "Postural_tremor",
    "Rest_tremor",
]


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Dataset tidak ditemukan: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    print("\n=== DATASET INFO ===")
    print("Shape:", df.shape)
    print("Columns:", list(df.columns))

    print("\n=== TARGET DISTRIBUTION ===")

    for target in TARGET_COLUMNS:
        if target not in df.columns:
            print(f"\n{target}: kolom tidak ditemukan")
            continue

        counts = df[target].value_counts(dropna=False).sort_index()
        ratio = df[target].value_counts(normalize=True, dropna=False).sort_index()

        print(f"\nTarget: {target}")
        print("Counts:")
        print(counts)
        print("Ratio:")
        print(ratio)

    if "subject_id" not in df.columns:
        print("\nKolom subject_id tidak ditemukan. Split berbasis pasien tidak bisa dicek.")
        return

    print("\n=== SUBJECT-LEVEL TARGET DISTRIBUTION ===")

    for target in TARGET_COLUMNS:
        if target not in df.columns:
            continue

        # max() artinya pasien dianggap positif jika minimal punya satu window positif.
        subject_label = df.groupby("subject_id")[target].max()

        print(f"\nTarget: {target}")
        print("Jumlah subject total    :", subject_label.shape[0])
        print("Subject negatif / positif:")
        print(subject_label.value_counts().sort_index())


if __name__ == "__main__":
    main()
