"""コマンドラインインターフェース。

使い方:
    python -m kyotei.cli fetch --days 60      # 過去データ取得 (キャッシュ)
    python -m kyotei.cli build --days 60      # 学習用データセット構築
    python -m kyotei.cli train                # LightGBM LambdaRank 学習
    python -m kyotei.cli backtest             # 検証期間の回収率検証
    python -m kyotei.cli predict              # 当日予測 → 静的JSON出力
    python -m kyotei.cli all --days 60        # 上記を一括実行
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

from .constants import DB_PATH, PREDICT_API_DIR


def _date_range(days: int) -> tuple[date, date]:
    """昨日を終端とする過去 days 日間の範囲を返す (当日は結果未確定のため除外)。"""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start, end


def cmd_fetch(args: argparse.Namespace) -> None:
    from .fetcher import RawDataStore

    start, end = _date_range(args.days)
    print(f"BoatraceOpenAPI からデータ取得: {start} 〜 {end}")
    RawDataStore().fetch_range(start, end)
    print("取得完了。")


def cmd_build(args: argparse.Namespace) -> None:
    from .dataset import build_dataset

    start, end = _date_range(args.days)
    print(f"データセット構築: {start} 〜 {end}")
    entries = build_dataset(start, end)
    races = entries["race_id"].nunique()
    print(f"構築完了: {len(entries)} 行 / {races} レース → {DB_PATH}")


def cmd_train(args: argparse.Namespace) -> None:
    from .dataset import load_entries
    from .model import train_model

    entries = load_entries()
    print(f"学習開始: {len(entries)} 行 / {entries['race_id'].nunique()} レース")
    _, metrics = train_model(entries)
    print("学習完了。検証指標:")
    for key in ("valid_races", "win_hit_rate", "exacta_hit_rate", "trifecta_hit_rate"):
        print(f"  {key}: {metrics.get(key)}")
    print("  feature importance (top 10):")
    for name, gain in list(metrics["feature_importance"].items())[:10]:
        print(f"    {name}: {gain:.0f}")


def cmd_backtest(args: argparse.Namespace) -> None:
    from .backtest import format_report, run_backtest
    from .dataset import load_entries, load_payouts

    summary = run_backtest(load_entries(), load_payouts())
    print(format_report(summary))
    report_path = PREDICT_API_DIR.parent / "backtest.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\nレポート保存: {report_path}")


def cmd_predict(args: argparse.Namespace) -> None:
    from .predict import predict_today

    payload = predict_today()
    print(
        f"予測完了: {payload['race_date']} {payload['race_count']} レース"
        f" → {PREDICT_API_DIR / 'today.json'}"
    )


def cmd_racers(args: argparse.Namespace) -> None:
    from .constants import RACERS_API_DIR
    from .dataset import load_entries
    from .racers import build_racer_analysis, export_racer_data

    payload = build_racer_analysis(load_entries())
    export_racer_data(payload)
    print(
        f"選手分析データ生成完了: {payload['racer_count']} 名"
        f" (期間 {payload['period'][0]} 〜 {payload['period'][1]})"
        f" → {RACERS_API_DIR / 'racers.json'}"
    )


def cmd_all(args: argparse.Namespace) -> None:
    cmd_fetch(args)
    cmd_build(args)
    cmd_train(args)
    cmd_backtest(args)
    cmd_predict(args)
    cmd_racers(args)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kyotei", description="競艇予想AIパイプライン")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="過去データを取得してキャッシュ")
    p_fetch.add_argument("--days", type=int, default=60, help="取得日数 (既定60)")
    p_fetch.set_defaults(func=cmd_fetch)

    p_build = sub.add_parser("build", help="学習用データセットを構築")
    p_build.add_argument("--days", type=int, default=60)
    p_build.set_defaults(func=cmd_build)

    p_train = sub.add_parser("train", help="モデルを学習")
    p_train.set_defaults(func=cmd_train)

    p_bt = sub.add_parser("backtest", help="検証期間の的中率・回収率を検証")
    p_bt.set_defaults(func=cmd_backtest)

    p_pred = sub.add_parser("predict", help="当日予測と静的JSON出力")
    p_pred.set_defaults(func=cmd_predict)

    p_racers = sub.add_parser("racers", help="選手個別分析データを生成")
    p_racers.set_defaults(func=cmd_racers)

    p_all = sub.add_parser("all", help="fetch→build→train→backtest→predict を一括実行")
    p_all.add_argument("--days", type=int, default=60)
    p_all.set_defaults(func=cmd_all)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
