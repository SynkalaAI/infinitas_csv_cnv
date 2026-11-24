import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT / "source" / "bemaniwiki.com.html"
DEFAULT_DATABASE = ROOT / "song_levels.json"
SECTION_ID = "content_1_5"
SOURCE_REFERENCE = "source/bemaniwiki.com.html#content_1_5"
MODES = ("SPB", "SPN", "SPH", "SPA", "SPL")


class LevelTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.section_found = False
        self.target_table_found = False
        self.table_depth = 0
        self.rows = []
        self.current_row = None
        self.current_cell = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "h3" and attributes.get("id") == SECTION_ID:
            self.section_found = True
        elif tag == "table" and self.section_found and not self.target_table_found:
            self.target_table_found = True
            self.table_depth += 1
        elif tag == "table" and self.target_table_found and self.table_depth:
            self.table_depth += 1

        if self.table_depth != 1:
            return
        if tag == "tr":
            self.current_row = []
        elif tag in ("td", "th") and self.current_row is not None:
            self.current_cell = []
        elif tag == "br" and self.current_cell is not None:
            self.current_cell.append("\n")
        elif tag in ("p", "div") and self.current_cell is not None:
            self.current_cell.append(" ")

    def handle_endtag(self, tag):
        if self.table_depth == 1 and tag in ("td", "th") and self.current_cell is not None:
            lines = [
                " ".join(line.split())
                for line in "".join(self.current_cell).splitlines()
            ]
            self.current_row.append("\n".join(line for line in lines if line))
            self.current_cell = None
        elif self.table_depth == 1 and tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None

        if tag == "table" and self.table_depth:
            self.table_depth -= 1

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell.append(data)


def parse_level(value, row_number, mode):
    if value == "-":
        return None
    match = re.search(r"\d+", value)
    if match is None:
        raise ValueError(
            f"Could not parse {mode} level {value!r} in source table row {row_number}"
        )
    return int(match.group())


def parse_source(path):
    parser = LevelTableParser()
    with path.open(encoding="utf-8") as file:
        parser.feed(file.read())
    parser.close()

    if not parser.section_found:
        raise ValueError(f"Could not find section #{SECTION_ID} in {path}")
    if not parser.rows:
        raise ValueError(f"Could not find a table after section #{SECTION_ID} in {path}")

    songs = []
    seen_titles = set()
    for row_number, row in enumerate(parser.rows, start=1):
        if len(row) != 14:
            continue
        title, artist = row[12].split("\n", 1)[0], row[13].split("\n", 1)[0]
        if not title:
            raise ValueError(f"Missing title in source table row {row_number}")
        if title in seen_titles:
            raise ValueError(f"Duplicate title in source table row {row_number}: {title}")
        seen_titles.add(title)

        songs.append(
            {
                "title": title,
                "artist": artist,
                "levels": {
                    mode: parse_level(value, row_number, mode)
                    for mode, value in zip(MODES, row[1:6])
                },
            }
        )

    if not songs:
        raise ValueError(f"No song entries found in section #{SECTION_ID} in {path}")
    return songs


def load_database(path):
    if not path.exists():
        return {
            "source": SOURCE_REFERENCE,
            "modes": list(MODES),
            "aliases": {},
            "songs": [],
        }

    with path.open(encoding="utf-8") as file:
        database = json.load(file)
    if not isinstance(database, dict):
        raise ValueError(f"Invalid song-level database: {path}")
    if not isinstance(database.get("songs"), list):
        raise ValueError(f"Song-level database must contain a songs list: {path}")
    if not isinstance(database.get("aliases", {}), dict):
        raise ValueError(f"Song-level database aliases must be an object: {path}")

    seen_titles = set()
    for song in database["songs"]:
        if not isinstance(song, dict) or not isinstance(song.get("title"), str):
            raise ValueError(f"Invalid song entry in song-level database: {path}")
        if song["title"] in seen_titles:
            raise ValueError(f"Duplicate title in song-level database: {song['title']}")
        seen_titles.add(song["title"])
    return database


def merge_songs(database, source_songs):
    existing = {song["title"]: song for song in database["songs"]}
    added = 0
    updated = 0
    for source_song in source_songs:
        current = existing.get(source_song["title"])
        if current is None:
            current = dict(source_song)
            database["songs"].append(current)
            existing[source_song["title"]] = current
            added += 1
            continue

        changed = False
        if current.get("artist") != source_song["artist"]:
            current["artist"] = source_song["artist"]
            changed = True

        levels = current.get("levels")
        if not isinstance(levels, dict):
            current["levels"] = dict(source_song["levels"])
            changed = True
        else:
            for mode, level in source_song["levels"].items():
                if levels.get(mode) != level:
                    levels[mode] = level
                    changed = True
        if changed:
            updated += 1
    return added, updated


def update_database(source_path, database_path):
    source_songs = parse_source(source_path)
    database = load_database(database_path)
    added, updated = merge_songs(database, source_songs)

    metadata_changed = False
    for field, value in (
        ("source", SOURCE_REFERENCE),
        ("modes", list(MODES)),
    ):
        if database.get(field) != value:
            database[field] = value
            metadata_changed = True

    if added or updated or metadata_changed:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = database_path.with_suffix(database_path.suffix + ".tmp")
        try:
            with temporary_path.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(database, file, ensure_ascii=False, indent=2)
                file.write("\n")
            temporary_path.replace(database_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        print(
            f"Updated {database_path}: added {added} songs, "
            f"updated {updated} songs"
            f"{' and metadata' if metadata_changed else ''}."
        )
    else:
        print(f"No differences found; left {database_path} unchanged.")


def main():
    parser = argparse.ArgumentParser(
        description="Incrementally update the song-level database from the BemaniWiki HTML table."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    try:
        update_database(args.source, args.database)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
