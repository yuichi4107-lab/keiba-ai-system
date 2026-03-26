開発環境をセットアップしてください。

以下の手順で実行:
1. `pip install -r requirements.txt` で依存パッケージをインストール
2. `pip install pytest flake8` でdev依存をインストール
3. `python -m pytest tests/ -v` でテストが通ることを確認
4. `PYTHONPATH=. python scripts/generate_sample_data.py` でサンプルデータ生成
5. セットアップ完了を報告
