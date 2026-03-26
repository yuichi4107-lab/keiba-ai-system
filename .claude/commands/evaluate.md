バックテスト（回収率シミュレーション）を実行してください。

引数: $ARGUMENTS（テスト比率、省略時は 0.2）

以下の手順で実行:
1. サンプルデータが無ければ生成
2. `PYTHONPATH=. python main.py evaluate --test-ratio <比率>` でバックテスト
3. 回収率・的中率・損益を報告
