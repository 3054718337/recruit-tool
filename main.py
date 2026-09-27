"""协会招新报名表数据处理小工具。

用法：
    python main.py data/sample.csv [--output-dir output]

按「读入与概览 → 校验与清洗 → 统计与导出」三步处理报名表。
当前实现到需求 1（读入与概览），需求 2/3 随后续 PR 加入。
全程只读取原始文件，不修改原 CSV。
"""

import argparse
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["姓名", "学号", "邮箱", "志愿1", "志愿2", "推荐人"]


def load_csv(path: str) -> pd.DataFrame:
    """读入报名表 CSV，并校验表头字段是否齐全。

    - dtype=str：全部字段按字符串读入，保留学号等字段的原始写法
    - encoding="utf-8-sig"：兼容带 BOM 的 UTF-8（Excel 导出常见）
    - keep_default_na=False：只有空单元格视为空，避免正常内容被误判为缺失
    """
    csv_path = Path(path)
    if not csv_path.exists():
        raise SystemExit(f"错误：找不到文件 {csv_path}")
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    except UnicodeDecodeError:
        raise SystemExit(f"错误：{csv_path} 不是 UTF-8 编码（见 README 设计假设第 7 条）")

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise SystemExit(f"错误：表头缺少字段 {'、'.join(missing)}")
    return df


def is_empty(series: pd.Series) -> pd.Series:
    """空值判定：NaN，或去掉首尾空格后为空字符串（README 设计假设第 2 条）。"""
    return series.isna() | (series.astype(str).str.strip() == "")


def print_overview(df: pd.DataFrame) -> None:
    """需求 1：打印总行数、每列空值数、完全重复的行。"""
    print("========== 报名表概览 ==========")
    print(f"总行数：{len(df)}")

    print("每列空值数：")
    for col in REQUIRED_COLUMNS:
        print(f"  {col}: {int(is_empty(df[col]).sum())}")

    dup_mask = df.duplicated(keep="first")
    dup_rows = [i + 1 for i in df.index[dup_mask]]  # +1 转成数据行号（表头不算）
    if dup_rows:
        print(f"完全重复的行：{len(dup_rows)} 行（数据行 {'、'.join(map(str, dup_rows))}）")
    else:
        print("完全重复的行：0 行")


def main() -> None:
    parser = argparse.ArgumentParser(description="协会招新报名表数据处理小工具")
    parser.add_argument("csv", help="报名表 CSV 文件路径")
    parser.add_argument("--output-dir", default="output", help="导出文件目录（默认 output/，需求 2/3 使用）")
    args = parser.parse_args()

    df = load_csv(args.csv)
    print_overview(df)


if __name__ == "__main__":
    main()
