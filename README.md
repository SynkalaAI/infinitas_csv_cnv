# INFINITAS CSV Converter

打鍵カウンタ形式のCSVと、INFINITAS公式スコア形式のCSVを相互変換するPythonスクリプトです。外部ライブラリは必要ありません。コマンドはプロジェクトのルートディレクトリで実行してください。

## 形式判定して変換

`convert_csv.py` は入力CSVのヘッダーから形式を判定し、対応する変換処理を呼び出します。

```powershell
python convert_csv.py <入力CSV> <出力CSV>
```

例:

```powershell
python convert_csv.py input\inf_score.csv output\sample\C-2966-8793-6328_sp_score.csv
python convert_csv.py input\C-2966-8793-6328_sp_score.csv output\sample\inf_score.csv
```

`--input` / `--output` オプションでも指定できます。

```powershell
python convert_csv.py --input input\inf_score.csv --output output\sample\C-2966-8793-6328_sp_score.csv
```

## 変換スクリプトを直接実行

### 打鍵カウンタ形式から公式形式へ

`convert_scores.py` は打鍵カウンタ形式のCSVをSPスコア形式へ変換します。入力・出力パスは位置引数または `--input` / `--output` で指定できます。

```powershell
python convert_scores.py input\inf_score.csv output\sample\C-2966-8793-6328_sp_score.csv
python convert_scores.py --input input\inf_score.csv --output output\sample\C-2966-8793-6328_sp_score.csv
```

省略時は `input\inf_score.csv` を読み、`output\sample\C-2966-8793-6328_sp_score.csv` に出力します。曲情報のカタログには、出力先が既にある場合は出力先CSVを、ない場合は `input\C-2966-8793-6328_sp_score.csv` を使います。別のカタログを使う場合は `--template` で指定してください。

```powershell
python convert_scores.py input\inf_score.csv output\custom\sp_score.csv --template input\C-2966-8793-6328_sp_score.csv
```

### 公式形式から打鍵カウンタ形式へ

`reverse_convert_scores.py` は公式形式のCSVを打鍵カウンタ形式へ変換します。入力・出力パスは位置引数または `--input` / `--output` で指定できます。

```powershell
python reverse_convert_scores.py input\C-2966-8793-6328_sp_score.csv output\sample\inf_score.csv
python reverse_convert_scores.py --input input\C-2966-8793-6328_sp_score.csv --output output\sample\inf_score.csv
```

省略時は `input\C-2966-8793-6328_sp_score.csv` を読み、`output\sample\inf_score.csv` に出力します。譜面レベルは `data\song_levels.json` から読み込みます。レベルDBに一致する曲がない場合、その譜面の `LV` は空欄になります。未プレー譜面（`NO PLAY`）は出力されません。

## 楽曲レベルDBの更新

`data\update_song_levels.py` は `data\source\bemaniwiki.com.html` の `content_1_5` 表からレベルを読み取り、`data\song_levels.json` を更新します。

```powershell
python data\update_song_levels.py
```

既存DBにない曲を追加し、表と値が異なる曲だけを更新します。HTMLにない既存曲や別名などの追加データは保持されます。差分がなければDBファイルを書き換えません。HTMLまたはDBのパスを変更する場合は、次のように指定できます。

```powershell
python data\update_song_levels.py --source data\source\bemaniwiki.com.html --database data\song_levels.json
```
