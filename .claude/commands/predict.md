指定された日付のレースを予測してください。

引数: $ARGUMENTS（日付 YYYY-MM-DD形式、省略時は 2025-12-30）

以下の手順で実行:
1. モデルが未学習なら先に `/train` を実行
2. `PYTHONPATH=. python main.py predict --date <日付> --from-csv` で予測
3. 予測結果を表示
