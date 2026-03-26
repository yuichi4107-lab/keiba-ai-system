# 帯広ばんえい競馬 単勝予想システム

## プロジェクト概要
LightGBMを使ったばんえい競馬の単勝予測システム。
地方競馬公式サイト(keiba.go.jp)からデータを収集し、機械学習で予測する。

## コマンド

```bash
# テスト実行
python -m pytest tests/ -v

# サンプルデータ生成（スクレイピングできない環境用）
PYTHONPATH=. python scripts/generate_sample_data.py

# モデル学習
PYTHONPATH=. python main.py train

# 予測（CSVデータから）
PYTHONPATH=. python main.py predict --date 2025-12-30 --from-csv

# 推奨馬券（1R〜12R全レース予想 + 購入レース選定）
PYTHONPATH=. python main.py recommend --date 2025-12-30 --from-csv

# バックテスト（回収率シミュレーション）
PYTHONPATH=. python main.py evaluate
PYTHONPATH=. python main.py evaluate --test-ratio 0.3

# データ収集（要外部接続）
PYTHONPATH=. python main.py scrape --start 2025-01-01 --end 2025-12-31
```

## ディレクトリ構成

- `main.py` - CLIエントリーポイント (scrape / train / predict / recommend / evaluate)
- `config/settings.py` - 全設定値（LightGBMパラメータ、パス、スクレイピング設定）
- `src/scraper/banei_scraper.py` - keiba.go.jpスクレイパー
- `src/features/feature_engineering.py` - 特徴量エンジニアリング（過去成績・騎手・重量）
- `src/model/predictor.py` - LightGBM予測モデル（学習・予測・保存・読込）
- `scripts/generate_sample_data.py` - テスト用サンプルデータ生成
- `tests/test_features.py` - 特徴量テスト
- `tests/test_predictor.py` - 予測モデルテスト

## 開発ルール

- `PYTHONPATH=.` を付けて実行すること
- テストは `python -m pytest tests/ -v` で実行
- 帯広競馬場コード: `36`
- スクレイピング先: `https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/`
- 外部サイトへの接続が不可な環境では `scripts/generate_sample_data.py` でサンプルデータを生成

## アーキテクチャ

### データフロー
1. **収集**: `BaneiScraper` → keiba.go.jp からHTML取得 → `data/raw/race_results.csv`
2. **特徴量生成**: `FeatureEngineer` → 過去走成績・騎手/調教師成績・重量特徴量 → `data/processed/features.csv`
3. **学習**: `BaneiPredictor.train()` → LightGBM (TimeSeriesSplit CV) → `models/banei_model.pkl`
4. **予測**: `BaneiPredictor.predict()` → 勝率 + レース内順位
5. **推奨**: 期待値（勝率×オッズ）> 1.0 の馬を購入対象に選定

### 特徴量一覧 (`FEATURE_COLUMNS` in `src/model/predictor.py`)
- 馬の過去成績: past_runs, past_win_rate, past_top3_rate, past_avg_finish, past_best_finish, past_avg_time, past_best_time, days_since_last_race
- 騎手/調教師: jockey_win_rate, jockey_top3_rate, trainer_win_rate, trainer_top3_rate
- 重量: horse_weight, weight_carry, weight_rank_in_race, weight_diff_from_mean, carry_rank_in_race, carry_to_weight_ratio
- レース条件: distance, num_runners, post_position, post_position_norm, month, age, sex_code

## Claude Code スラッシュコマンド

- `/project:setup` - 開発環境セットアップ
- `/project:train` - サンプルデータ生成 + モデル学習
- `/project:predict` - 日付指定でレース予測
- `/project:recommend` - 推奨馬券表示
- `/project:evaluate` - バックテスト実行
- `/project:test` - テスト実行
