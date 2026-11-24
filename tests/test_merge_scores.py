import csv
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from merge_scores import main, merge
from reverse_convert_scores import CHARTS, CHART_FIELDS


KEY_COUNTER_HEADER = [
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


def official_header():
    header = ["バージョン", "タイトル", "アーティスト"]
    chart_names = {
        "SPB": "BEGINNER",
        "SPN": "NORMAL",
        "SPH": "HYPER",
        "SPA": "ANOTHER",
        "SPL": "LEGGENDARIA",
    }
    for mode, _ in CHARTS:
        header.extend(f"{chart_names[mode]} {field}" for field in CHART_FIELDS)
    return header


def official_row(title, score, clear):
    row = ["1st&substream", title, "Artist"]
    for mode, _ in CHARTS:
        if mode == "SPH":
            row.extend([score, "---", "---", clear, "1", "---"])
        else:
            row.extend(["0", "---", "---", "NO PLAY", "0", "---"])
    return row


class MergeScoresTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)

    def write_csv(self, name, header, rows):
        path = self.directory / name
        with path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def test_key_counter_merges_score_and_clear_independently(self):
        row_a = ["10", "Song", "SPA", "CLEAR", "100", "", "20", "?", "?", "", "1"]
        row_b = ["10", "Song", "SPA", "FAILED", "200", "", "30", "?", "?", "", "2"]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, [row_a])
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, [row_b])

        header, rows = merge(path_a, path_b)

        self.assertEqual(header, KEY_COUNTER_HEADER)
        self.assertEqual(rows[0][3:5], ["CLEAR", "200"])

    def test_key_counter_merges_normalized_title_variants(self):
        row_a = ["10", "Metagame Matador\u00a0", "SPA", "CLEAR", "100", "", "20", "?", "?", "", "1"]
        row_b = ["10", "metagame   matador", "SPA", "FAILED", "200", "", "30", "?", "?", "", "2"]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, [row_a])
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, [row_b])
        output = io.StringIO()

        with redirect_stdout(output):
            _, rows = merge(path_a, path_b)

        self.assertEqual(output.getvalue(), "")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Metagame Matador\u00a0")
        self.assertEqual(rows[0][3:5], ["CLEAR", "200"])

    def test_key_counter_keeps_input_a_title_for_typographic_matches(self):
        rows_a = [
            ["10", "Love km", "SPA", "CLEAR", "1817", "", "20", "?", "?", "", "1"],
            ["10", "LOVE SHINE", "SPH", "H-CLEAR", "1747", "", "20", "?", "?", "", "1"],
            ["10", "LOVE SHINE", "SPA", "EXH-CLEAR", "1957", "", "20", "?", "?", "", "1"],
        ]
        rows_b = [
            ["10", "Love\u2661km", "SPN", "E-CLEAR", "166", "", "20", "?", "?", "", "1"],
            ["10", "Love\u2661km", "SPA", "H-CLEAR", "1817", "", "20", "?", "?", "", "1"],
            ["10", "LOVE\u2661SHINE", "SPB", "E-CLEAR", "196", "", "20", "?", "?", "", "1"],
            ["10", "LOVE\u2661SHINE", "SPH", "H-CLEAR", "1747", "", "20", "?", "?", "", "1"],
            ["10", "LOVE\u2661SHINE", "SPA", "EXH-CLEAR", "1957", "", "20", "?", "?", "", "1"],
        ]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, rows_a)
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, rows_b)

        _, rows = merge(path_a, path_b)

        keyed_rows = {(row[1], row[2]): row for row in rows}
        self.assertIn(("Love km", "SPN"), keyed_rows)
        self.assertIn(("LOVE SHINE", "SPB"), keyed_rows)
        self.assertNotIn(("Love\u2661km", "SPN"), keyed_rows)
        self.assertNotIn(("LOVE\u2661SHINE", "SPB"), keyed_rows)
        self.assertEqual(len(rows), 5)

    def test_key_counter_merges_shared_alias_to_each_left_title(self):
        row_a = ["10", "uan", "SPH", "CLEAR", "100", "", "20", "?", "?", "", "1"]
        row_a2 = ["10", "uen", "SPH", "H-CLEAR", "150", "", "10", "?", "?", "", "2"]
        row_b = ["10", "uən", "SPH", "FAILED", "200", "", "30", "?", "?", "", "3"]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, [row_a, row_a2])
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, [row_b])
        output = io.StringIO()

        with redirect_stdout(output):
            _, rows = merge(path_a, path_b)

        self.assertEqual(output.getvalue(), "")
        self.assertEqual(len(rows), 2)
        keyed_rows = {row[1]: row for row in rows}
        self.assertEqual(keyed_rows["uan"][3:5], ["CLEAR", "200"])
        self.assertEqual(keyed_rows["uen"][3:5], ["H-CLEAR", "200"])

    def test_key_counter_preserves_single_input_alias_title(self):
        row_a = ["10", "uen", "SPA", "CLEAR", "100", "", "20", "?", "?", "", "1"]
        row_b = ["10", "uən", "SPA", "H-CLEAR", "200", "", "10", "?", "?", "", "2"]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, [row_a])
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, [row_b])

        _, rows = merge(path_a, path_b)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "uen")
        self.assertEqual(rows[0][4], "200")

    def test_key_counter_keeps_left_titles_for_registered_aliases(self):
        aliases = [
            ("Ignis†Irae", "Ignis†Iræ"),
            ("BLOSSOM", "BLO§OM"),
            ("POLKAMANIA", "POLꞰAMAИIA"),
            ("ATHER", "ÆTHER"),
            ("火影", "焱影"),
            ("RINNE", "RINИE"),
            ("uan", "uən"),
            ("VOID", "VØID"),
            ("ACT0", "ACTØ"),
            ("uen", "uən"),
        ]
        rows_a = [
            ["10", left, "SPA", "CLEAR", "100", "", "20", "?", "?", "", "1"]
            for left, _ in aliases
        ]
        rows_b = [
            ["10", right, "SPA", "H-CLEAR", "200", "", "10", "?", "?", "", "2"]
            for right in dict.fromkeys(right for _, right in aliases)
        ]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, rows_a)
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, rows_b)
        output = io.StringIO()

        with redirect_stdout(output):
            _, rows = merge(path_a, path_b)

        self.assertEqual(output.getvalue(), "")
        expected_titles = {left for left, _ in aliases}
        self.assertEqual({row[1] for row in rows}, expected_titles)
        self.assertEqual(len(rows), len(expected_titles))
        merged = {row[1]: row for row in rows}
        for left, _ in aliases:
            self.assertEqual(merged[left][4], "200")

    def test_key_counter_reports_unmatched_title_to_stdout(self):
        row_a = ["10", "Known song", "SPA", "CLEAR", "100", "", "20", "?", "?", "", "1"]
        row_b = ["10", "Unknown song", "SPA", "CLEAR", "200", "", "30", "?", "?", "", "2"]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, [row_a])
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, [row_b])
        output = io.StringIO()

        with redirect_stdout(output):
            _, rows = merge(path_a, path_b)

        self.assertIn("ERROR", output.getvalue())
        self.assertIn("Unknown song", output.getvalue())
        self.assertEqual(rows[-1][1], "Unknown song")

    def test_official_merges_score_and_clear_independently(self):
        path_a = self.write_csv(
            "a.csv", official_header(), [official_row("Song", "100", "HARD CLEAR")]
        )
        path_b = self.write_csv(
            "b.csv", official_header(), [official_row("Song", "200", "EASY CLEAR")]
        )

        header, rows = merge(path_a, path_b)

        self.assertEqual(header, official_header())
        self.assertEqual(rows[0][15], "200")
        self.assertEqual(rows[0][18], "HARD CLEAR")

    def test_official_merge_drops_empty_trailing_header_column(self):
        header = official_header() + [""]
        path_a = self.write_csv("a.csv", header, [official_row("Song", "100", "CLEAR")])
        path_b = self.write_csv("b.csv", header, [official_row("Song", "200", "CLEAR")])

        merged_header, rows = merge(path_a, path_b)

        self.assertEqual(len(merged_header), 33)
        self.assertEqual(len(rows[0]), 33)

    def test_official_cli_preserves_artist_quote_style(self):
        row_a = official_row("SIGMA", "100", "CLEAR")
        row_b = official_row("SIGMA", "200", "CLEAR")
        row_a[2] = row_b[2] = 'BEMANI Sound Team "Mutsuhiko Izumi"'
        comma_row_a = official_row("Comma Song", "100", "CLEAR")
        comma_row_b = official_row("Comma Song", "200", "CLEAR")
        comma_row_a[2] = comma_row_b[2] = 'Artist, "quoted"'
        path_a = self.write_csv(
            "a.csv", official_header(), [row_a, comma_row_a]
        )
        path_b = self.write_csv(
            "b.csv", official_header(), [row_b, comma_row_b]
        )
        output_path = self.directory / "merged.csv"

        with patch(
            "sys.argv",
            ["merge_scores.py", str(path_a), str(path_b), str(output_path)],
        ):
            main()

        text = output_path.read_text(encoding="utf-8-sig")
        self.assertIn(',BEMANI Sound Team "Mutsuhiko Izumi",', text)
        self.assertIn(',"Artist, ""quoted""",', text)
        with output_path.open(encoding="utf-8-sig", newline="") as file:
            output_rows = list(csv.reader(file))
        self.assertEqual(output_rows[1][2], row_a[2])
        self.assertEqual(output_rows[2][2], comma_row_a[2])

    def test_official_merge_matches_normalized_titles(self):
        row_a = official_row("Metagame Matador\u00a0", "100", "HARD CLEAR")
        row_a[2] = "Catalog Artist"
        row_b = official_row("metagame   matador", "200", "EASY CLEAR")
        path_a = self.write_csv("a.csv", official_header(), [row_a])
        path_b = self.write_csv("b.csv", official_header(), [row_b])

        _, rows = merge(path_a, path_b)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Metagame Matador\u00a0")
        self.assertEqual(rows[0][2], "Catalog Artist")
        self.assertEqual(rows[0][15], "200")
        self.assertEqual(rows[0][18], "HARD CLEAR")

    def test_official_merge_matches_punctuation_variants(self):
        row_a = official_row('"You\'ll say Now!"', "100", "CLEAR")
        row_a[2] = "Catalog Artist"
        row_b = official_row('You\'ll say "Now!"', "200", "CLEAR")
        path_a = self.write_csv("a.csv", official_header(), [row_a])
        path_b = self.write_csv("b.csv", official_header(), [row_b])

        _, rows = merge(path_a, path_b)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], '"You\'ll say Now!"')
        self.assertEqual(rows[0][2], "Catalog Artist")
        self.assertEqual(rows[0][15], "200")

    def test_official_merge_matches_symbol_and_diacritic_variants(self):
        row_a = official_row("Love\u2661km", "100", "HARD CLEAR")
        row_a[2] = "Catalog Artist"
        row_b = official_row("Love km", "200", "EASY CLEAR")
        path_a = self.write_csv("a.csv", official_header(), [row_a])
        path_b = self.write_csv("b.csv", official_header(), [row_b])

        _, rows = merge(path_a, path_b)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Love\u2661km")
        self.assertEqual(rows[0][2], "Catalog Artist")
        self.assertEqual(rows[0][15], "200")
        self.assertEqual(rows[0][18], "HARD CLEAR")

    def test_official_merge_applies_registered_title_aliases(self):
        aliases = [
            ("Ignis†Irae", "Ignis†Iræ"),
            ("BLOSSOM", "BLO§OM"),
            ("POLKAMANIA", "POLꞰAMAИIA"),
            ("ATHER", "ÆTHER"),
            ("火影", "焱影"),
            ("RINNE", "RINИE"),
            ("uan", "uən"),
            ("VOID", "VØID"),
            ("ACT0", "ACTØ"),
            ("uen", "uən"),
        ]
        canonical_titles = list(dict.fromkeys(canonical for _, canonical in aliases))
        rows_a = [
            official_row(title, "100", "CLEAR") for title in canonical_titles
        ]
        rows_b = [
            official_row(alias, "200", "HARD CLEAR") for alias, _ in aliases
        ]
        path_a = self.write_csv("a.csv", official_header(), rows_a)
        path_b = self.write_csv("b.csv", official_header(), rows_b)
        output = io.StringIO()

        with redirect_stdout(output):
            _, rows = merge(path_a, path_b)

        self.assertEqual(output.getvalue(), "")
        self.assertEqual(len(rows), len(canonical_titles))
        merged = {row[1]: row for row in rows}
        for title in canonical_titles:
            self.assertEqual(merged[title][15], "200")
            self.assertEqual(merged[title][18], "HARD CLEAR")

    def test_official_merge_reports_unmatched_title_to_stdout(self):
        path_a = self.write_csv(
            "a.csv", official_header(), [official_row("Known song", "100", "CLEAR")]
        )
        path_b = self.write_csv(
            "b.csv",
            official_header(),
            [official_row("Unknown song", "200", "HARD CLEAR")],
        )
        output = io.StringIO()

        with redirect_stdout(output):
            _, rows = merge(path_a, path_b)

        self.assertIn("ERROR", output.getvalue())
        self.assertIn("Unknown song", output.getvalue())
        self.assertEqual(rows[-1][1], "Unknown song")

    def test_official_merge_rejects_ambiguous_normalized_titles(self):
        rows_a = [
            official_row("Song", "100", "CLEAR"),
            official_row("Ｓｏｎｇ", "200", "CLEAR"),
        ]
        path_a = self.write_csv("a.csv", official_header(), rows_a)
        path_b = self.write_csv(
            "b.csv", official_header(), [official_row("song", "300", "CLEAR")]
        )

        with self.assertRaisesRegex(ValueError, "Ambiguous title match"):
            merge(path_a, path_b)

    def test_official_merge_rejects_ambiguous_typographic_titles(self):
        rows_a = [
            official_row("Café", "100", "CLEAR"),
            official_row("Cafè", "200", "CLEAR"),
        ]
        path_a = self.write_csv("a.csv", official_header(), rows_a)
        path_b = self.write_csv(
            "b.csv", official_header(), [official_row("Cafe", "300", "CLEAR")]
        )

        with self.assertRaisesRegex(ValueError, "Ambiguous typographic title match"):
            merge(path_a, path_b)

    def test_rejects_mixed_formats(self):
        key_counter = self.write_csv("key.csv", KEY_COUNTER_HEADER, [])
        official = self.write_csv("official.csv", official_header(), [])

        with self.assertRaisesRegex(ValueError, "same format"):
            merge(key_counter, official)

    def test_cli_writes_csv_to_stdout_when_output_is_omitted(self):
        row = ["10", "Song", "SPA", "CLEAR", "100", "", "20", "?", "?", "", "1"]
        path_a = self.write_csv("a.csv", KEY_COUNTER_HEADER, [row])
        path_b = self.write_csv("b.csv", KEY_COUNTER_HEADER, [row])
        output = io.StringIO()

        with patch("sys.argv", ["merge_scores.py", str(path_a), str(path_b)]):
            with patch("sys.stdout", output):
                main()

        result = list(csv.reader(output.getvalue().splitlines()))
        self.assertEqual(result, [KEY_COUNTER_HEADER, row])


if __name__ == "__main__":
    unittest.main()
