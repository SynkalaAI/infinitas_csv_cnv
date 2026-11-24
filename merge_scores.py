import argparse
import csv
import sys
import unicodedata
from pathlib import Path

from convert_csv import detect_format
from convert_scores import INPUT_COLUMNS
from reverse_convert_scores import CHARTS, CHART_FIELDS, normalize_name


KEY_COUNTER_CLEAR_RANKS = {
    "NO PLAY": 0,
    "FAILED": 1,
    "A-CLEAR": 2,
    "ASSIST CLEAR": 2,
    "CLEAR": 3,
    "E-CLEAR": 4,
    "EASY CLEAR": 4,
    "H-CLEAR": 5,
    "HARD CLEAR": 5,
    "EXH-CLEAR": 6,
    "EX HARD CLEAR": 6,
    "F-COMBO": 7,
    "FULLCOMBO CLEAR": 7,
}
OFFICIAL_CLEAR_RANKS = {
    "NO PLAY": 0,
    "FAILED": 1,
    "ASSIST CLEAR": 2,
    "CLEAR": 3,
    "EASY CLEAR": 4,
    "HARD CLEAR": 5,
    "EX HARD CLEAR": 6,
    "FULLCOMBO CLEAR": 7,
}
OFFICIAL_TITLE_ALIASES = {
    "Ignis†Irae": "Ignis†Iræ",
    "BLOSSOM": "BLO§OM",
    "POLKAMANIA": "POLꞰAMAИIA",
    "ATHER": "ÆTHER",
    "火影": "焱影",
    "RINNE": "RINИE",
    "uan": "uən",
    "VOID": "VØID",
    "ACT0": "ACTØ",
    "uen": "uən",
}
KEY_COUNTER_FALLBACK_TITLES = {
    "Ignis†Iræ": "Ignis†Irae",
    "BLO§OM": "BLOSSOM",
    "POLꞰAMAИIA": "POLKAMANIA",
    "ÆTHER": "ATHER",
    "焱影": "火影",
    "RINИE": "RINNE",
    "uən": "uan",
    "VØID": "VOID",
    "ACTØ": "ACT0",
}


def _read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV file is empty: {path}") from exc
        return header, list(reader)


def _validate_score(score, path, row_number, chart):
    if not score.isdigit():
        raise ValueError(
            f"Invalid score on input row {row_number}, {chart}: {score} ({path})"
        )
    return int(score)


def _read_key_counter(path):
    header, rows = _read_csv(path)
    if not INPUT_COLUMNS.issubset(header):
        raise ValueError(f"Unrecognized key-counter CSV columns: {path}")
    if len(set(header)) != len(header):
        raise ValueError(f"Duplicate CSV columns: {path}")

    indexes = {column: header.index(column) for column in INPUT_COLUMNS}
    charts = {}
    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            raise ValueError(f"Invalid column count on input row {row_number}: {path}")
        title = row[indexes["Title"]]
        mode = row[indexes["mode"]]
        lamp = row[indexes["Lamp"]]
        score = row[indexes["Score"]]
        if not title:
            raise ValueError(f"Missing title on input row {row_number}: {path}")
        if mode not in {"SPB", "SPN", "SPH", "SPA", "SPL"}:
            raise ValueError(f"Unsupported mode on input row {row_number}: {mode}")
        if lamp not in KEY_COUNTER_CLEAR_RANKS:
            raise ValueError(f"Unsupported lamp on input row {row_number}: {lamp}")
        _validate_score(score, path, row_number, mode)
        key = (title, mode)
        if key in charts:
            raise ValueError(
                f"Duplicate chart on input row {row_number}: {title} ({mode})"
            )
        charts[key] = row
    return header, charts, indexes


def _official_chart_starts(header, path):
    if len(header) < 33 or header[1] != "タイトル":
        raise ValueError(f"Unrecognized INFINITAS CSV columns: {path}")
    expected_chart_names = {
        "SPB": "BEGINNER",
        "SPN": "NORMAL",
        "SPH": "HYPER",
        "SPA": "ANOTHER",
        "SPL": "LEGGENDARIA",
    }
    starts = {}
    for mode, start in CHARTS:
        expected = [
            f"{expected_chart_names[mode]} {field}" for field in CHART_FIELDS
        ]
        if header[start : start + 6] != expected:
            raise ValueError(f"Unrecognized INFINITAS columns for {mode}: {path}")
        starts[mode] = start
    return starts


def _read_official(path):
    header, rows = _read_csv(path)
    while header and not header[-1]:
        header.pop()
    starts = _official_chart_starts(header, path)
    records = {}
    for row_number, row in enumerate(rows, start=2):
        while len(row) > len(header) and not row[-1]:
            row.pop()
        if len(row) > len(header):
            raise ValueError(f"Invalid column count on input row {row_number}: {path}")
        if len(row) < 33:
            raise ValueError(f"Invalid column count on input row {row_number}: {path}")
        row += [""] * (len(header) - len(row))
        title = row[1]
        if not title:
            raise ValueError(f"Missing title on input row {row_number}: {path}")
        if title in records:
            raise ValueError(f"Duplicate title on input row {row_number}: {title}")
        for mode, start in starts.items():
            clear = row[start + 3]
            if clear not in OFFICIAL_CLEAR_RANKS:
                raise ValueError(
                    f"Unsupported clear type on input row {row_number}, "
                    f"{mode}: {clear}"
                )
            _validate_score(row[start], path, row_number, mode)
        records[title] = row
    return header, records, starts


def _merge_key_counter(header_a, charts_a, indexes_a, header_b, charts_b):
    if header_a != header_b:
        raise ValueError("The key-counter CSV files have different columns.")
    title_index = indexes_a["Title"]
    mode_index = indexes_a["mode"]
    strict_index = {}
    typographic_index = {}
    strict_a_titles = set()
    typographic_a_titles = set()
    a_titles = set()
    merged = {}

    def add_index(index, normalized_title, title):
        if normalized_title:
            candidates = index.setdefault(normalized_title, [])
            if title not in candidates:
                candidates.append(title)

    def merge_rows(row_a, row_b):
        score_index = indexes_a["Score"]
        lamp_index = indexes_a["Lamp"]
        score_row = (
            row_b
            if int(row_b[score_index]) > int(row_a[score_index])
            else row_a
        )
        merged_row = score_row.copy()
        merged_row[title_index] = row_a[title_index]
        merged_row[mode_index] = row_a[mode_index]
        merged_row[lamp_index] = (
            row_b[lamp_index]
            if KEY_COUNTER_CLEAR_RANKS[row_b[lamp_index]]
            > KEY_COUNTER_CLEAR_RANKS[row_a[lamp_index]]
            else row_a[lamp_index]
        )
        return merged_row

    for row_a in charts_a.values():
        title = row_a[title_index]
        mode = row_a[mode_index]
        key = (title, mode)
        normalized = _normalize_title(title)
        typographic = _normalize_typographic_title(title)
        strict_a_titles.add(normalized)
        a_titles.add(title)
        if typographic:
            typographic_a_titles.add(typographic)
        if key in merged:
            merged[key] = merge_rows(merged[key], row_a)
        else:
            merged[key] = row_a.copy()
        add_index(strict_index, normalized, title)
        add_index(typographic_index, typographic, title)

    reported_unmatched_titles = set()
    reported_ambiguous_titles = set()
    for row_b in charts_b.values():
        title = row_b[title_index]
        mode = row_b[mode_index]
        normalized = _normalize_title(title)
        typographic = _normalize_typographic_title(title)

        if title in a_titles:
            matching_titles = [title]
        else:
            matches = strict_index.get(normalized, [])
            matching_titles = _choose_key_counter_titles(matches)
            if not matches:
                matches = typographic_index.get(typographic, [])
                matching_titles = _choose_key_counter_titles(matches)
            if matches and matching_titles is None:
                if title not in reported_ambiguous_titles:
                    print(f"ERROR: 曖昧な曲名のためマージできません: {title}")
                    reported_ambiguous_titles.add(title)
            elif not matches:
                matching_titles = None

        if matching_titles is not None:
            for matching_title in matching_titles:
                matching_key = (matching_title, mode)
                row = row_b.copy()
                row[title_index] = matching_title
                if matching_key in merged:
                    merged[matching_key] = merge_rows(merged[matching_key], row)
                else:
                    merged[matching_key] = row
        else:
            if (
                normalized not in strict_a_titles
                and typographic not in typographic_a_titles
                and title not in reported_unmatched_titles
            ):
                print(f"ERROR: マージ先の曲名が見つかりません: {title}")
                reported_unmatched_titles.add(title)
            row = row_b.copy()
            row[title_index] = KEY_COUNTER_FALLBACK_TITLES.get(title, title)
            key = (row[title_index], mode)
            if key in merged:
                merged[key] = merge_rows(merged[key], row)
            else:
                merged[key] = row

    return header_a, list(merged.values())


def _choose_key_counter_titles(candidates):
    identities = {_canonical_title(title) for title in candidates}
    if not candidates or len(identities) != 1:
        return None

    return candidates


def _merge_official(header_a, records_a, starts_a, header_b, records_b):
    if header_a != header_b:
        raise ValueError("The INFINITAS CSV files have different columns.")
    merged = {title: row.copy() for title, row in records_a.items()}
    titles_by_normalized_name = {}
    titles_by_typographic_name = {}
    for title in records_a:
        normalized = _normalize_title(title)
        titles_by_normalized_name.setdefault(normalized, []).append(title)
        typographic = _normalize_typographic_title(title)
        if typographic:
            titles_by_typographic_name.setdefault(typographic, []).append(title)

    for title, row_b in records_b.items():
        matching_titles = titles_by_normalized_name.get(_normalize_title(title), [])
        if title in merged:
            matching_title = title
        elif len(matching_titles) == 1:
            matching_title = matching_titles[0]
        elif len(matching_titles) > 1:
            raise ValueError(
                f"Ambiguous title match in INFINITAS CSV: {title} "
                f"({', '.join(matching_titles)})"
            )
        else:
            typographic_matches = titles_by_typographic_name.get(
                _normalize_typographic_title(title), []
            )
            if len(typographic_matches) == 1:
                matching_title = typographic_matches[0]
            elif len(typographic_matches) > 1:
                raise ValueError(
                    f"Ambiguous typographic title match in INFINITAS CSV: {title} "
                    f"({', '.join(typographic_matches)})"
                )
            else:
                print(f"ERROR: マージ先の曲名が見つかりません: {title}")
                merged[title] = row_b
                continue
        row_a = merged[matching_title]
        for mode, start in starts_a.items():
            score_a = int(row_a[start])
            score_b = int(row_b[start])
            clear_a = row_a[start + 3]
            clear_b = row_b[start + 3]
            score_row = row_b if score_b > score_a else row_a
            row_a[start : start + 6] = score_row[start : start + 6]
            row_a[start + 3] = (
                clear_b
                if OFFICIAL_CLEAR_RANKS[clear_b] > OFFICIAL_CLEAR_RANKS[clear_a]
                else clear_a
            )

    output_rows = []
    for row in merged.values():
        output_rows.append(row)
    return header_a, output_rows


def _normalize_title(title):
    return normalize_name(_canonical_title(title))


def _normalize_typographic_title(title):
    title = _canonical_title(title)
    normalized = unicodedata.normalize("NFKD", title).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace()
        and unicodedata.category(character)[0] not in {"M", "P", "S"}
    )


def _canonical_title(title):
    return OFFICIAL_TITLE_ALIASES.get(title, title)


def _format_official_field(value):
    if any(character in value for character in ',\r\n') or value.startswith('"'):
        return '"' + value.replace('"', '""') + '"'
    return value


def _write_official_csv(file, header, rows):
    for row in [header] + rows:
        # INFINITAS leaves embedded quotes unescaped when a field needs no quoting.
        file.write(",".join(_format_official_field(value) for value in row) + "\n")


def merge(input_a, input_b):
    format_a = detect_format(input_a)
    format_b = detect_format(input_b)
    if format_a != format_b:
        raise ValueError("Input CSV files must use the same format.")

    if format_a == "key_counter":
        header_a, charts_a, indexes_a = _read_key_counter(input_a)
        header_b, charts_b, _ = _read_key_counter(input_b)
        return _merge_key_counter(
            header_a, charts_a, indexes_a, header_b, charts_b
        )

    header_a, records_a, starts_a = _read_official(input_a)
    header_b, records_b, _ = _read_official(input_b)
    return _merge_official(header_a, records_a, starts_a, header_b, records_b)


def main():
    parser = argparse.ArgumentParser(
        description="Merge two INFINITAS or key-counter score CSV files."
    )
    parser.add_argument("input_a", type=Path)
    parser.add_argument("input_b", type=Path)
    parser.add_argument("output_path", nargs="?", type=Path)
    args = parser.parse_args()

    try:
        if args.output_path is not None:
            output_resolved = args.output_path.resolve()
            if output_resolved in (args.input_a.resolve(), args.input_b.resolve()):
                raise ValueError("Output path must not be either input file.")
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", newline="")
        header, rows = merge(args.input_a, args.input_b)
        if args.output_path is None:
            if len(header) > 1 and header[1] == "タイトル":
                _write_official_csv(sys.stdout, header, rows)
            else:
                writer = csv.writer(sys.stdout, lineterminator="\n")
                writer.writerow(header)
                writer.writerows(rows)
        else:
            args.output_path.parent.mkdir(parents=True, exist_ok=True)
            with args.output_path.open("w", encoding="utf-8-sig", newline="") as file:
                if len(header) > 1 and header[1] == "タイトル":
                    _write_official_csv(file, header, rows)
                else:
                    writer = csv.writer(file, lineterminator="\n")
                    writer.writerow(header)
                    writer.writerows(rows)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
