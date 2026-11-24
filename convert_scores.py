import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "input" / "sample" / "inf_score.csv"
DEFAULT_OUTPUT = ROOT / "output" / "sample" / "C-2966-8793-6328_sp_score.csv"
DEFAULT_TEMPLATE = ROOT / "input" / "sample" / "template.csv"

CHART_COLUMNS = {
    "SPB": 3,
    "SPN": 9,
    "SPH": 15,
    "SPA": 21,
    "SPL": 27,
}
CLEAR_TYPES = {
    "NO PLAY": "NO PLAY",
    "FAILED": "FAILED",
    "CLEAR": "CLEAR",
    "E-CLEAR": "EASY CLEAR",
    "H-CLEAR": "HARD CLEAR",
    "EXH-CLEAR": "EX HARD CLEAR",
    "F-COMBO": "FULLCOMBO CLEAR",
}
EMPTY_CHART = ["0", "---", "---", "NO PLAY", "0", "---"]
INPUT_COLUMNS = {
    "Title",
    "mode",
    "Lamp",
    "Score",
    "BP",
    "Last Played",
    "Play Count",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV file is empty: {path}") from exc
        return header, list(reader)


def convert(input_path, output_path, template_path=None):
    with input_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or not INPUT_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(
                f"Input CSV must contain these columns: {', '.join(sorted(INPUT_COLUMNS))}"
            )
        input_rows = list(reader)

    template_path = template_path or (
        output_path if output_path.exists() else DEFAULT_TEMPLATE
    )
    template_header, template_rows = read_csv(template_path)
    if len(template_header) < 33 or any(len(row) < 33 for row in template_rows):
        raise ValueError(f"Template CSV does not have the expected score format: {template_path}")

    records = {}
    for row in template_rows:
        title = row[1]
        if title in records:
            raise ValueError(f"Duplicate title in template CSV: {title}")
        records[title] = row

    for row_number, source in enumerate(input_rows, start=2):
        title = source["Title"]
        mode = source["mode"]
        if mode not in CHART_COLUMNS:
            raise ValueError(f"Unsupported mode on input row {row_number}: {mode}")
        if source["Lamp"] not in CLEAR_TYPES:
            raise ValueError(f"Unsupported lamp on input row {row_number}: {source['Lamp']}")
        if not title:
            raise ValueError(f"Missing title on input row {row_number}")

        if title not in records:
            records[title] = ["", title, ""] + EMPTY_CHART.copy() * 5

        start = CHART_COLUMNS[mode]
        miss_count = source["BP"].strip()
        if not miss_count or miss_count == "?":
            miss_count = "---"
        played_at = source["Last Played"].strip() or "---"
        records[title][start : start + 6] = [
            source["Score"],
            played_at,
            miss_count,
            CLEAR_TYPES[source["Lamp"]],
            source["Play Count"],
            played_at,
        ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(template_header)
        writer.writerows(records.values())

    added_titles = set(records) - {row[1] for row in template_rows}
    print(f"Converted {len(input_rows)} scores into {len(records)} song rows.")
    if added_titles:
        print(
            f"Added {len(added_titles)} titles not found in the template; "
            "their version and artist fields are blank.",
            file=sys.stderr,
        )


def main():
    parser = argparse.ArgumentParser(
        description="Convert INFINITAS score CSV data to the SP score CSV format."
    )
    parser.add_argument("input_path", nargs="?", type=Path)
    parser.add_argument("output_path", nargs="?", type=Path)
    parser.add_argument("--input", dest="input_option", type=Path)
    parser.add_argument("--output", dest="output_option", type=Path)
    parser.add_argument(
        "--template",
        type=Path,
        help=(
            "SP score CSV used as the song catalog "
            "(defaults to --output if it exists, otherwise the bundled input catalog)."
        ),
    )
    args = parser.parse_args()
    if args.input_path and args.input_option:
        parser.error("Specify the input path either positionally or with --input, not both.")
    if args.output_path and args.output_option:
        parser.error("Specify the output path either positionally or with --output, not both.")
    input_path = args.input_option or args.input_path or DEFAULT_INPUT
    output_path = args.output_option or args.output_path or DEFAULT_OUTPUT
    try:
        convert(input_path, output_path, args.template)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
