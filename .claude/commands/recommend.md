指定された日付の全レース推奨馬券を表示してください。

引数: $ARGUMENTS（日付 YYYY-MM-DD形式、省略時は 2025-12-30）

以下の手順で実行:
1. モデルが未学習なら先に `/train` を実行
2. `PYTHONPATH=. python main.py recommend --date <日付> --from-csv` で推奨馬券を出力
3. 購入推奨レースと見送りレースをまとめて報告
