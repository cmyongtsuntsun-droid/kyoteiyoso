"""競艇予想AIパッケージ。

競艇予想システム設計調査.pdf に基づく構成:
データ取得 (BoatraceOpenAPI) → DB化 (SQLite/CSV) → 特徴量作成 →
LightGBM LambdaRank 学習 → 期待値計算 → 静的JSON配信。
"""

__version__ = "0.1.0"
