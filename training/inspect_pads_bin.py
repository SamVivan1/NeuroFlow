from pathlib import Path
import pickle

import numpy as np


BIN_DIR = Path("training/data/pads/preprocessed/movement")


def try_load_numpy(path: Path):
    try:
        return np.load(path, allow_pickle=True)
    except Exception as e:
        return e


def try_load_pickle(path: Path):
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        return e


def try_load_raw_float32(path: Path):
    try:
        return np.fromfile(path, dtype=np.float32)
    except Exception as e:
        return e


def describe_object(name: str, obj):
    print(f"\n=== {name} ===")

    if isinstance(obj, Exception):
        print("FAILED:", repr(obj))
        return

    print("Type:", type(obj))

    if isinstance(obj, np.ndarray):
        print("Shape:", obj.shape)
        print("Dtype:", obj.dtype)

        if obj.size > 0:
            flat = obj.reshape(-1)
            print("First values:", flat[:20])

            if np.issubdtype(obj.dtype, np.number):
                print("Min:", np.nanmin(flat))
                print("Max:", np.nanmax(flat))
                print("NaN count:", np.isnan(flat).sum())

    elif isinstance(obj, dict):
        print("Dict keys:", list(obj.keys())[:30])

        for key, value in list(obj.items())[:10]:
            print(f"Key: {key} | Type: {type(value)}")

            if isinstance(value, np.ndarray):
                print("  Shape:", value.shape)
                print("  Dtype:", value.dtype)

    elif isinstance(obj, list):
        print("List length:", len(obj))
        print("First item type:", type(obj[0]) if obj else None)
        print("First item repr:", repr(obj[0])[:500] if obj else None)

    else:
        print("Object repr:", repr(obj)[:1000])


def main():
    files = sorted(BIN_DIR.glob("*_ml.bin"))

    print("BIN_DIR:", BIN_DIR)
    print("Total bin files:", len(files))

    if not files:
        print("\nTidak ada file *_ml.bin di folder preprocessed/movement.")
        print("Sekarang dataset yang terlihat paling jelas adalah file JSON di training/data/pads/movement.")
        return

    for path in files[:5]:
        print("\n" + "=" * 80)
        print("FILE:", path.name)
        print("SIZE:", path.stat().st_size, "bytes")
        print("MAGIC:", path.read_bytes()[:16])

        describe_object("np.load", try_load_numpy(path))
        describe_object("pickle.load", try_load_pickle(path))
        describe_object("np.fromfile float32", try_load_raw_float32(path))


if __name__ == "__main__":
    main()
