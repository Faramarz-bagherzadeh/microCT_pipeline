import os
import json
import argparse
import glob
import pandas as pd


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument("--jsons_dir", type=str, required=True,
                        help="Path to a directory containing JSON files to merge")

    args = parser.parse_args()

    jsons_dir = args.jsons_dir

    print(f"JSON directory: {jsons_dir}")

    # Find all JSON files in the directory
    json_files = glob.glob(os.path.join(jsons_dir, "*.json"))
    print(f"Found {len(json_files)} JSON file(s)")

    if not json_files:
        print("No JSON files found. Exiting.")
        return

    # Read each JSON file and collect the data
    all_data = []
    for json_path in sorted(json_files):
        with open(json_path, 'r') as f:
            data = json.load(f)
        all_data.append(data)
        print(f"  Loaded: {os.path.basename(json_path)}")

    # Convert to DataFrame (each JSON dict becomes one row)
    df = pd.DataFrame(all_data)

    # Convert the 'depth' column from string to float if it exists
    if "depth" in df.columns:
        df["depth"] = pd.to_numeric(df["depth"], errors="coerce")

    # Save to Excel in the same directory
    output_path = os.path.join(jsons_dir, "merged_features.xlsx")
    df.to_excel(output_path, index=False)
    print(f"\nMerged data saved to: {output_path}")
    print(f"Total rows: {len(df)}, Total columns: {len(df.columns)}")


if __name__ == '__main__':
    main()