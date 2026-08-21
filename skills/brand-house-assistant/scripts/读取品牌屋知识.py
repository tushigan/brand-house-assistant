#!/usr/bin/env python3
"""按模式、字段和深度确定性读取品牌屋橙皮书章节。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


MODES = (
    "从零构建",
    "品牌共创",
    "策略启发",
    "方法带教",
    "审查评审",
    "执行落地",
    "版本重审",
)
DEPTHS = ("快速", "标准", "深度")

# 每个字段映射为（主章节，直接上下游章节）。
FIELD_MAP = {
    "边界与版本": (("01", "03"), ("02", "16", "18")),
    "MVV": (("05", "06"), ("04", "12", "15")),
    "品类定位": (("07",), ("08", "09", "10")),
    "核心客群与场景": (("08",), ("07", "09", "10")),
    "差异化价值": (("09",), ("07", "08", "10", "11")),
    "品牌定位": (("10",), ("07", "08", "09", "11")),
    "RTB": (("11",), ("09", "10", "12", "17")),
    "品牌主张": (("12",), ("05", "10", "11", "13")),
    "品牌人格": (("13",), ("12", "14", "15")),
    "口号与表达": (("14",), ("12", "13", "15")),
    "执行落地": (("15",), ("13", "14", "17", "18")),
    "工作坊与评审": (("17",), ("02", "16", "18")),
    "全部": (tuple(f"{number:02d}" for number in range(1, 19)), ()),
}

PHASES = {
    "1": tuple(f"{number:02d}" for number in range(1, 4)),
    "2": tuple(f"{number:02d}" for number in range(4, 7)),
    "3": tuple(f"{number:02d}" for number in range(7, 12)),
    "4": tuple(f"{number:02d}" for number in range(12, 16)),
    "5": tuple(f"{number:02d}" for number in range(16, 19)),
    "全部": tuple(f"{number:02d}" for number in range(1, 19)),
}

CHAPTER_HEADING = re.compile(r"(?m)^# §(\d{2})(?:\s|$)")
EXPECTED_CHAPTERS = tuple(f"{number:02d}" for number in range(1, 19))
SKILL_ROOT = Path(__file__).resolve().parents[1]
BOOK_PATH = SKILL_ROOT / "references" / "品牌屋构建橙皮书.md"


class ReaderError(Exception):
    """可直接呈现给使用者的中文错误。"""


class ChineseArgumentParser(argparse.ArgumentParser):
    """将 argparse 默认的英文错误改为可读的中文错误。"""

    def error(self, message: str) -> None:
        if "expected one argument" in message:
            option_match = re.search(r"argument ([^:]+):", message)
            option = option_match.group(1) if option_match else "该选项"
            raise ReaderError(f"参数缺值：{option} 后面必须提供一个值。")
        if message.startswith("unrecognized arguments:"):
            supplied = message.partition(":")[2].strip()
            if any(part.startswith("-") for part in supplied.split()):
                raise ReaderError(f"未知参数：{supplied}。请检查参数名。")
            raise ReaderError(f"多余参数：{supplied}。请删除不需要的内容。")
        raise ReaderError("参数格式错误：请检查参数名和参数值。")


def _chapter_matches_outside_fences(book_text: str) -> list[re.Match[str]]:
    """识别 Markdown 代码围栏之外的正式章节标题。"""
    matches: list[re.Match[str]] = []
    fence_char: str | None = None
    fence_length = 0
    offset = 0

    for line in book_text.splitlines(keepends=True):
        line_without_ending = line.rstrip("\r\n")
        if fence_char is not None:
            closing_fence = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*",
                line_without_ending,
            )
            if closing_fence:
                fence_char = None
                fence_length = 0
            offset += len(line)
            continue

        opening_fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line_without_ending)
        if opening_fence:
            marker, info = opening_fence.groups()
            if marker[0] == "~" or "`" not in info:
                fence_char = marker[0]
                fence_length = len(marker)
                offset += len(line)
                continue

        chapter_match = CHAPTER_HEADING.match(book_text, offset)
        if chapter_match:
            matches.append(chapter_match)
        offset += len(line)

    return matches


def parse_chapters(book_text: str) -> dict[str, str]:
    """按一级标题动态切分原典，并严格校验 §01—§18。"""
    matches = _chapter_matches_outside_fences(book_text)
    found = tuple(match.group(1) for match in matches)
    if found != EXPECTED_CHAPTERS:
        found_text = "、".join(f"§{number}" for number in found) if found else "未识别到任何章节"
        raise ReaderError(
            "原典章节异常：必须恰好识别§01—§18且顺序唯一；"
            f"当前识别结果为 {found_text}。"
        )

    chapters: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(book_text)
        chapters[match.group(1)] = book_text[match.start() : end].rstrip("\r\n") + "\n"
    return chapters


def selected_chapters(field: str, depth: str, phase: str | None = None) -> tuple[str, ...]:
    """根据字段、深度和可选阶段返回已排序、去重的章号。"""
    if depth == "快速":
        return ()
    if depth == "深度" and field == "全部" and phase is not None:
        return PHASES[phase]

    primary, neighbors = FIELD_MAP[field]
    return tuple(sorted(set(primary + neighbors), key=int))


def _chapter_range(numbers: tuple[str, ...]) -> str:
    """将连续章号转为简洁的预计范围文本。"""
    if numbers == EXPECTED_CHAPTERS:
        return "§01—§18"
    return "、".join(f"§{number}" for number in numbers)


def print_catalog() -> None:
    """只输出可选路由与映射，不读取原典正文。"""
    print("可用模式：" + "、".join(MODES))
    print("可用深度：" + "、".join(DEPTHS))
    print("可用阶段：1、2、3、4、5、全部（仅用于深度＋字段“全部”）")
    print("字段与预计章节：")
    for field, (primary, neighbors) in FIELD_MAP.items():
        numbers = tuple(sorted(set(primary + neighbors), key=int))
        print(f"- {field}：预计章节 {_chapter_range(numbers)}")
    print("阶段与预计章节：")
    for phase, numbers in PHASES.items():
        print(f"- 阶段{phase}：预计章节 {_chapter_range(numbers)}")


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器，值合法性由 main 统一给出中文错误。"""
    parser = ChineseArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--列出", action="store_true", help="列出模式、字段、深度和阶段")
    parser.add_argument("--模式")
    parser.add_argument("--字段")
    parser.add_argument("--深度")
    parser.add_argument("--阶段")
    parser.add_argument("-h", "--帮助", action="help", help="显示帮助")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    """完成值、缺失参数和组合冲突校验。"""
    if args.列出:
        if any((args.模式, args.字段, args.深度, args.阶段)):
            raise ReaderError("参数冲突：--列出 不能与模式、字段、深度或阶段同时使用。")
        return

    missing = [name for name in ("模式", "字段", "深度") if getattr(args, name) is None]
    if missing:
        raise ReaderError("缺少必需参数：" + "、".join(f"--{name}" for name in missing))
    if args.模式 not in MODES:
        raise ReaderError(f"未知模式：{args.模式}。请先用 --列出 查看可用模式。")
    if args.字段 not in FIELD_MAP:
        raise ReaderError(f"未知字段：{args.字段}。请先用 --列出 查看可用字段。")
    if args.深度 not in DEPTHS:
        raise ReaderError(f"未知深度：{args.深度}。可用深度为快速、标准、深度。")
    if args.阶段 is not None and args.阶段 not in PHASES:
        raise ReaderError(f"未知阶段：{args.阶段}。可用阶段为1、2、3、4、5、全部。")
    if args.阶段 is not None and (args.深度 != "深度" or args.字段 != "全部"):
        raise ReaderError("参数冲突：--阶段 只能用于深度“深度”且字段“全部”。")


def main(argv: list[str] | None = None) -> int:
    """运行命令行读取器。"""
    try:
        args = build_parser().parse_args(argv)
        _validate_args(args)

        if args.列出:
            print_catalog()
            return 0

        mode_card = f"references/模式-{args.模式}.md"
        print(f"模式卡：{mode_card}")
        print(f"字段：{args.字段}")
        print(f"深度：{args.深度}")

        if args.深度 == "快速":
            print("本次不读取橙皮书正文；如需字段定义、上下游关系或裁决方法，建议升级到标准深度。")
            return 0

        try:
            book_text = BOOK_PATH.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ReaderError(f"无法读取品牌屋橙皮书原典：{exc}") from exc
        chapters = parse_chapters(book_text)
        numbers = selected_chapters(args.字段, args.深度, args.阶段)
        if args.阶段 is not None:
            print(f"阶段：{args.阶段}")
        print("本次读取章节：" + "、".join(f"§{number}" for number in numbers))
        print()
        for number in numbers:
            print(chapters[number], end="\n")
        return 0
    except ReaderError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
