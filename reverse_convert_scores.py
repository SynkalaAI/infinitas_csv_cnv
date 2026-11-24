import argparse
import csv
import json
import sys
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "input" / "sample" / "C-2966-8793-6328_sp_score.csv"
DEFAULT_OUTPUT = ROOT / "output" / "sample" / "inf_score.csv"
LEVEL_DATABASE = ROOT / "data" / "song_levels.json"

CHARTS = (
    ("SPB", 3),
    ("SPN", 9),
    ("SPH", 15),
    ("SPA", 21),
    ("SPL", 27),
)
CLEAR_TYPES = {
    "FAILED": "FAILED",
    "CLEAR": "CLEAR",
    "ASSIST CLEAR": "A-CLEAR",
    "EASY CLEAR": "E-CLEAR",
    "HARD CLEAR": "H-CLEAR",
    "EX HARD CLEAR": "EXH-CLEAR",
    "FULLCOMBO CLEAR": "F-COMBO",
}
OUTPUT_HEADER = [
    "LV",
    "Title",
    "mode",
    "Lamp",
    "Score",
    "(rate)",
    "BP",
    "Opt(best score)",
    "Opt(min bp)",
    "Last Played",
    "Play Count",
]
CHART_FIELDS = (
    "スコア",
    "最終スコア更新時刻",
    "ミスカウント",
    "クリアタイプ",
    "プレー回数",
    "最終プレー日時",
)
ARTIST_COLUMN = 2


def normalize_name(value):
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace()
        and unicodedata.category(character)[0] != "P"
    )


def load_level_database(path):
    with path.open(encoding="utf-8") as file:
        database = json.load(file)

    if not isinstance(database, dict):
        raise ValueError(f"Invalid song-level database: {path}")
    songs = database.get("songs")
    aliases = database.get("aliases")
    if not isinstance(songs, list) or not isinstance(aliases, dict):
        raise ValueError(f"Invalid song-level database: {path}")

    by_title = {}
    for song in songs:
        if not isinstance(song, dict):
            raise ValueError(f"Invalid song entry in level database: {path}")
        title = song.get("title")
        artist = song.get("artist")
        levels = song.get("levels")
        if not isinstance(title, str) or not isinstance(artist, str):
            raise ValueError(f"Invalid song title or artist in level database: {path}")
        if not isinstance(levels, dict):
            raise ValueError(f"Invalid levels for {title} in level database: {path}")
        by_title.setdefault(normalize_name(title), []).append(song)

    if not all(
        isinstance(alias, str) and isinstance(target, str)
        for alias, target in aliases.items()
    ):
        raise ValueError(f"Invalid title aliases in level database: {path}")
    return by_title, aliases


def find_song_level(title, artist, mode, by_title, aliases):
    title = aliases.get(title, title)
    candidates = by_title.get(normalize_name(title), [])
    if len(candidates) > 1:
        normalized_artist = normalize_name(artist)
        candidates = [
            song
            for song in candidates
            if normalize_name(song["artist"]) == normalized_artist
        ]
    if len(candidates) != 1:
        return None

    level = candidates[0]["levels"].get(mode)
    if level is not None and (not isinstance(level, int) or level < 1):
        raise ValueError(f"Invalid {mode} level for {title}: {level}")
    return level


def convert(input_path, output_path):
    level_index, title_aliases = load_level_database(LEVEL_DATABASE)
    with input_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV file is empty: {input_path}") from exc
        rows = list(reader)

    if len(header) < 33 or any(len(row) < 33 for row in rows):
        raise ValueError(f"Input CSV does not have the expected SP score format: {input_path}")
    if header[1] != "タイトル":
        raise ValueError(f"Input CSV has an unexpected title column: {header[1]}")
    for mode, start in CHARTS:
        chart_name = {
            "SPB": "BEGINNER",
            "SPN": "NORMAL",
            "SPH": "HYPER",
            "SPA": "ANOTHER",
            "SPL": "LEGGENDARIA",
        }[mode]
        expected = [f"{chart_name} {field}" for field in CHART_FIELDS]
        if header[start : start + 6] != expected:
            raise ValueError(f"Input CSV has unexpected columns for {mode}: {input_path}")

    titles = set()
    output_rows = []
    skipped_charts = 0
    missing_levels = []
    for row_number, row in enumerate(rows, start=2):
        title = row[1]
        if not title:
            raise ValueError(f"Missing title on input row {row_number}")
        if title in titles:
            raise ValueError(f"Duplicate title on input row {row_number}: {title}")
        titles.add(title)

        for mode, start in CHARTS:
            score, _, miss_count, clear_type, play_count, last_played = row[
                start : start + 6
            ]
            if clear_type == "NO PLAY":
                skipped_charts += 1
                continue
            if clear_type not in CLEAR_TYPES:
                raise ValueError(
                    f"Unsupported clear type on input row {row_number}, "
                    f"{mode}: {clear_type}"
                )
            if not score.isdigit():
                raise ValueError(
                    f"Invalid score on input row {row_number}, {mode}: {score}"
                )
            if not play_count.isdigit():
                raise ValueError(
                    f"Invalid play count on input row {row_number}, {mode}: {play_count}"
                )

            level = find_song_level(
                title, row[ARTIST_COLUMN], mode, level_index, title_aliases
            )
            if level is None:
                missing_levels.append((title, mode))
            output_rows.append(
                [
                    str(level) if level is not None else "",
                    title,
                    mode,
                    CLEAR_TYPES[clear_type],
                    score,
                    "",
                    "" if miss_count == "---" else miss_count,
                    "?",
                    "?",
                    last_played,
                    play_count,
                ]
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(OUTPUT_HEADER)
        writer.writerows(output_rows)

    print(f"Converted {len(output_rows)} played charts.")
    if skipped_charts:
        print(f"Skipped {skipped_charts} charts marked NO PLAY.")
    if missing_levels:
        print(
            f"Could not find a level for {len(missing_levels)} played charts "
            "in the song-level database; their LV fields are blank.",
            file=sys.stderr,
        )
        for title, mode in missing_levels[:10]:
            print(f"  {mode}: {title}", file=sys.stderr)
    print(
        "Rate and option details are not present in the input format "
        "and remain blank or unknown."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Convert an SP score CSV to the INFINITAS score CSV format."
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
    input_path = args.input_option or args.input_path or DEFAULT_INPUT
    output_path = args.output_option or args.output_path or DEFAULT_OUTPUT
    try:
        convert(input_path, output_path)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
