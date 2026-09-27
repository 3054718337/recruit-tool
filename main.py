"""协会招新报名表数据处理小工具。

用法：
    python main.py data/sample.csv [--output-dir output]

按「读入与概览 → 校验与清洗 → 统计与导出」三步处理报名表。
三个需求（读入概览、校验与问题清单、统计与导出）全部实现。
全程只读取原始文件，不修改原 CSV。
"""

import argparse
import re
from collections import Counter
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["姓名", "学号", "邮箱", "志愿1", "志愿2", "推荐人"]

# 学号共 10 位：11202 + 入学年份末位（3-6，对应 2023-2026 级）+ 4 位序号
STUDENT_ID_PATTERN = re.compile(r"11202[3-6][0-9]{4}")
EMAIL_SUFFIX = "@smbu.edu.cn"


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


def find_exact_duplicates(df: pd.DataFrame) -> dict[int, int]:
    """找出完全重复的行，返回 {重复行的位置: 首次出现行的位置}（0 起）。"""
    first_seen: dict[tuple, int] = {}
    duplicates: dict[int, int] = {}
    for pos, row in enumerate(df.itertuples(index=False)):
        key = tuple(str(v).strip() for v in row)
        if key in first_seen:
            duplicates[pos] = first_seen[key]
        else:
            first_seen[key] = pos
    return duplicates


def validate_row(row: dict, id_counts: Counter) -> list[str]:
    """对单行做格式校验（学号、邮箱、重复报名），返回该行的问题原因列表。

    各项校验独立执行：学号非法时邮箱仍与原学号值比对，原因由调用方合并。
    """
    sid = str(row["学号"]).strip()
    email = str(row["邮箱"]).strip()
    reasons: list[str] = []

    if sid == "":
        reasons.append("学号为空")
    elif not re.fullmatch(r"[0-9]+", sid):
        reasons.append("学号应为纯数字")
    elif not STUDENT_ID_PATTERN.fullmatch(sid):
        reasons.append("学号格式不符（应为 11202+入学年份末位 3-6+4 位序号，共 10 位）")

    expected_email = f"{sid}{EMAIL_SUFFIX}".lower()
    if email == "":
        reasons.append("邮箱为空")
    elif email.lower() != expected_email:
        reasons.append(f"邮箱与学号不匹配（应为 {expected_email}）")

    if sid != "" and id_counts[sid] > 1:
        reasons.append(f"学号 {sid} 出现 {id_counts[sid]} 次，重复报名")
    return reasons


def run_validation(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """需求 2：校验全部行，返回 (问题清单, 干净数据)。

    问题清单 = 原始数据 + 数据行号 + 问题原因，一行有多个原因时用「；」
    合并在同一格（README 设计假设第 3 条）。干净数据 = 未违反任何校验的行。
    """
    ids = df["学号"].astype(str).str.strip()
    id_counts = Counter(x for x in ids if x != "")

    all_reasons = [validate_row(row, id_counts) for row in df.to_dict("records")]

    for dup_pos, first_pos in find_exact_duplicates(df).items():
        all_reasons[dup_pos].append(f"与数据行 {first_pos + 1} 完全重复")

    problem_positions = [i for i, reasons in enumerate(all_reasons) if reasons]
    problems = df.iloc[problem_positions].copy()
    problems.insert(0, "数据行号", [pos + 1 for pos in problem_positions])
    problems["问题原因"] = ["；".join(all_reasons[pos]) for pos in problem_positions]

    clean = df.iloc[[i for i, reasons in enumerate(all_reasons) if not reasons]].copy()
    # 清洗：去首尾空格后导出；问题清单保留原始写法（README 设计假设第 9 条）
    clean = clean.apply(lambda col: col.str.strip())
    return problems, clean


def export_problems(problems: pd.DataFrame, output_dir: Path) -> Path:
    """问题清单导出到 output_dir（UTF-8 带 BOM，Excel 可直接打开）。不动原文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "问题清单.csv"
    problems.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def print_validation_summary(problems: pd.DataFrame, out_path: Path) -> None:
    print()
    print("========== 校验结果 ==========")
    if problems.empty:
        print("未发现问题行，全部数据通过校验")
        return
    print(f"发现 {len(problems)} 个问题行，问题清单已导出：{out_path}")
    for _, row in problems.iterrows():
        print(f"  数据行 {row['数据行号']}（{row['姓名']}）：{row['问题原因']}")


def export_stats(clean: pd.DataFrame, output_dir: Path) -> None:
    """需求 3：按第一志愿分组统计人数，统计单/双志愿人数，导出汇总表与干净数据。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 按第一志愿分组统计（人数降序，同数按出现先后）
    group_counts = clean["志愿1"].str.strip().value_counts()
    summary = pd.DataFrame({"志愿1": group_counts.index, "人数": group_counts.values})
    summary_path = output_dir / "志愿汇总表.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    # 志愿填写情况：志愿 2 非空 = 两个志愿都填
    choice2_empty = is_empty(clean["志愿2"])
    both = int((~choice2_empty).sum())
    only_one = int(choice2_empty.sum())

    clean_path = output_dir / "清洗后报名表.csv"
    clean.to_csv(clean_path, index=False, encoding="utf-8-sig")

    print()
    print("========== 志愿统计 ==========")
    print(f"按第一志愿分组（干净数据 {len(clean)} 人）：")
    for _, row in summary.iterrows():
        print(f"  {row['志愿1']}: {row['人数']}")
    print("志愿填写情况：")
    print(f"  两个志愿都填：{both} 人")
    print(f"  只填一个志愿：{only_one} 人")
    print(f"干净数据已导出：{clean_path}（{len(clean)} 行）")
    print(f"志愿汇总表已导出：{summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="协会招新报名表数据处理小工具")
    parser.add_argument("csv", help="报名表 CSV 文件路径")
    parser.add_argument("--output-dir", default="output", help="导出文件目录（默认 output/）")
    args = parser.parse_args()

    df = load_csv(args.csv)
    print_overview(df)

    problems, clean = run_validation(df)
    out_path = export_problems(problems, Path(args.output_dir))
    print_validation_summary(problems, out_path)
    export_stats(clean, Path(args.output_dir))


if __name__ == "__main__":
    main()
