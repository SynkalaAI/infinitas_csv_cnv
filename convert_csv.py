import argparse
import csv
from pathlib import Path

from convert_scores import DEFAULT_TEMPLATE, INPUT_COLUMNS, convert as convert_scores
from reverse_convert_scores import CHART_FIELDS, CHARTS, convert as reverse_convert_scores


ROOT = Path(__file__).resolve().parent


def detect_format(input_path):
    with input_path.open(encoding="utf-8-sig", newline="") as file:
        try:
            header = next(csv.reader(file))
        except StopIteration as exc:
            raise ValueError(f"CSV file is empty: {input_path}") from exc

    if INPUT_COLUMNS.issubset(header):
        return "key_counter"

    expected_chart_names = {
        "SPB": "BEGINNER",
        "SPN": "NORMAL",
        "SPH": "HYPER",
        "SPA": "ANOTHER",
        "SPL": "LEGGENDARIA",
    }
    if len(header) >= 33 and header[1] == "タイトル":
        for mode, start in CHARTS:
            chart_name = expected_chart_names[mode]
            expected = [f"{chart_name} {field}" for field in CHART_FIELDS]
            if header[start : start + 6] != expected:
                break
        else:
            return "infinitas_official"

    raise ValueError(f"Unrecognized CSV format: {input_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert between INFINITAS score CSV formats."
    )
    parser.add_argument("input_path", nargs="?", type=Path)
    parser.add_argument("output_path", nargs="?", type=Path)
    parser.add_argument("--input", dest="input_option", type=Path)
    parser.add_argument("--output", dest="output_option", type=Path)
    args = parser.parse_args()
    if args.input_path and args.input_option:
        parser.error("Specify the input path either positionally or with --input, not both.")
    if args.output_path and args.output_option:
        parser.error("Specify the output path either positionally or with --output, not both.")
    input_path = args.input_option or args.input_path
    output_path = args.output_option or args.output_path
    if input_path is None or output_path is None:
        parser.error("Both input and output paths are required.")

    try:
        source_format = detect_format(input_path)
        if source_format == "key_counter":
            convert_scores(input_path, output_path, DEFAULT_TEMPLATE)
        else:
            reverse_convert_scores(input_path, output_path)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
