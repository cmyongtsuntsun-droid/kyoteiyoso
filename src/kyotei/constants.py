"""競艇ドメイン定数。"""
from __future__ import annotations

from pathlib import Path

# プロジェクトルート (src/kyotei/constants.py から2階層上)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "kyotei.db"
TRAIN_CSV = DATA_DIR / "train.csv"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "model.txt"
METRICS_PATH = MODEL_DIR / "metrics.json"
STADIUM_STATS_PATH = MODEL_DIR / "stadium_course_stats.csv"
SITE_DIR = PROJECT_ROOT / "site"
PREDICT_API_DIR = SITE_DIR / "api" / "v1" / "predict"
RACERS_API_DIR = SITE_DIR / "api" / "v1" / "racers"

# 全国24競艇場 (場コード → 名称)
STADIUM_NAMES: dict[int, str] = {
    1: "桐生", 2: "戸田", 3: "江戸川", 4: "平和島", 5: "多摩川", 6: "浜名湖",
    7: "蒲郡", 8: "常滑", 9: "津", 10: "三国", 11: "びわこ", 12: "住之江",
    13: "尼崎", 14: "鳴門", 15: "丸亀", 16: "児島", 17: "宮島", 18: "徳山",
    19: "下関", 20: "若松", 21: "芦屋", 22: "福岡", 23: "唐津", 24: "大村",
}

# 級別 (racer_class_number → 表記)
RACER_CLASS_NAMES: dict[int, str] = {1: "A1", 2: "A2", 3: "B1", 4: "B2"}

# 着順 → LambdaRank ラベル (上位ほど高評価。NDCG のゲインは 2^label - 1 で
# 指数関数的に効くため、1着=5 ... 6着/事故=0 の整数ラベルで設計書の意図を満たす)
PLACE_TO_LABEL: dict[int, int] = {1: 5, 2: 4, 3: 3, 4: 2, 5: 1, 6: 0}

# 欠損値の明示的デフォルト (設計書: SQL/前処理段階で安全に変換しておく)
DEFAULT_AVG_ST = 0.20          # 平均ST欠損時 (新人など)
DEFAULT_TILT = 0.0             # チルト角度
STRONG_WIND_MS = 5             # 強風閾値 (m/s): イン逃げ減衰指標に使用
HIGH_WAVE_CM = 5               # 高波閾値 (cm): 安定板装着相当の荒れ水面フラグ

BOATS_PER_RACE = 6
