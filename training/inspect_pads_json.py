from pathlib import Path
import json


MOVEMENT_DIR = Path("training/data/pads/movement")


def main():
    files = sorted(MOVEMENT_DIR.glob("observation_*.json"))

    print("MOVEMENT_DIR:", MOVEMENT_DIR)
    print("Total JSON files:", len(files))

    if not files:
        raise FileNotFoundError(f"Tidak ada observation_*.json di {MOVEMENT_DIR}")

    sample = files[0]

    print("\nSample file:", sample)

    with open(sample, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("\nTop-level type:", type(data))

    if isinstance(data, dict):
        print("Top-level keys:")
        for key in data.keys():
            print("-", key)

        print("\nPreview values:")
        for key, value in list(data.items())[:20]:
            print(f"\nKEY: {key}")
            print("TYPE:", type(value))

            if isinstance(value, (str, int, float, bool)) or value is None:
                print("VALUE:", value)
            elif isinstance(value, list):
                print("LIST LEN:", len(value))
                print("FIRST ITEM:", repr(value[0])[:500] if value else None)
            elif isinstance(value, dict):
                print("DICT KEYS:", list(value.keys())[:30])
            else:
                print("REPR:", repr(value)[:500])

    elif isinstance(data, list):
        print("List length:", len(data))
        print("First item:", repr(data[0])[:1000] if data else None)


if __name__ == "__main__":
    main()
