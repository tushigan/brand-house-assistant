#!/usr/bin/env python3
"""检查结构化品牌屋Markdown的基本方法门禁。"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = (
    "品牌边界",
    "使命",
    "愿景",
    "价值观",
    "品类定位",
    "核心客群与场景",
    "差异化价值",
    "品牌定位",
    "RTB",
    "品牌主张",
    "品牌人格",
    "品牌口号",
    "裁决结论",
)

STATE_SECTION_HEADINGS = (
    "四维状态台账",
    "当前事实、策略假设与能力缺口",
)

FORMAL_DECISIONS = ("待裁决", "保留", "退回", "淘汰")

STATE_VALUES = {
    "内容性质": ("当前事实", "策略假设"),
    "证据状态": ("已证实", "待验证"),
    "能力状态": ("已具备", "待建设"),
    "裁决状态": FORMAL_DECISIONS + ("通过",),
}

TABLE_HEADER_WORDS = {
    "证据项目",
    "证据",
    "项目",
    "内容",
    "说明",
    "类型",
    "状态",
}


def section(text: str, heading: str) -> str:
    pattern = rf"(?ms)^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def meaningful_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        value = raw.strip().lstrip("-* ").strip()
        if not value or value.startswith(("#", "|", "---")):
            continue
        lines.append(value)
    return lines


def markdown_cells(line: str) -> list[str]:
    """拆分一行简单Markdown表格；不处理单元格内的转义竖线。"""
    value = line.strip()
    if "|" not in value:
        return []
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [cell.strip() for cell in value.split("|")]


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def state_table(states: str) -> tuple[list[str], list[list[str]]] | None:
    """按表头定位四维状态表，返回表头和数据行。"""
    lines = states.splitlines()
    dimensions = tuple(STATE_VALUES)
    for index, line in enumerate(lines):
        header = markdown_cells(line)
        if not header or not all(dimension in header for dimension in dimensions):
            continue
        rows: list[list[str]] = []
        for row_line in lines[index + 1 :]:
            cells = markdown_cells(row_line)
            if not cells:
                if rows:
                    break
                continue
            if is_separator_row(cells):
                continue
            rows.append(cells)
        return header, rows
    return None


def rtb_items(rtb: str) -> list[str]:
    """提取RTB中的逐条证据，兼容项目符号和简单Markdown表格。"""
    items: list[str] = []
    for raw in rtb.splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        cells = markdown_cells(value)
        if cells:
            if is_separator_row(cells):
                continue
            if cells and all(cell in TABLE_HEADER_WORDS for cell in cells):
                continue
            item = " ".join(cell for cell in cells if cell)
        else:
            item = value.lstrip("-* ").strip()
        if item and item != "---":
            items.append(item)
    return items


def first_section(text: str, headings: tuple[str, ...]) -> tuple[str, str]:
    """返回第一个已存在的兼容章节标题及正文。"""
    for heading in headings:
        content = section(text, heading)
        if content:
            return heading, content
        if re.search(rf"(?m)^## {re.escape(heading)}\s*$", text):
            return heading, ""
    return "", ""


def selected_decision(conclusion: str) -> str | None:
    """提取单一裁决值；“通过”只作为“保留”的展示别名。"""
    match = re.search(
        r"(?m)^\s*(?:[-*]\s*)?结论\s*[：:]\s*(待裁决|保留|退回|淘汰|通过)\s*$",
        conclusion,
    )
    if not match:
        return None
    return "保留" if match.group(1) == "通过" else match.group(1)


def validate(text: str) -> list[str]:
    errors: list[str] = []

    for heading in REQUIRED_SECTIONS:
        if not re.search(rf"(?m)^## {re.escape(heading)}\s*$", text):
            errors.append(f"缺少必填章节：{heading}")

    for heading in ("使命", "愿景", "价值观"):
        content = section(text, heading)
        if re.search(r"沿用(?:集团|企业|母品牌)|复制(?:集团|企业|母品牌)", content):
            errors.append(f"{heading}不能直接沿用集团、企业或母品牌答案")

    difference = meaningful_lines(section(text, "差异化价值"))
    if not difference or not re.match(r"^更[^\s，。；：:]{1,}", difference[0]):
        errors.append("差异化价值必须使用“更XX”句式")

    for gate in ("对手明确", "用户重要", "影响选择", "RTB成立", "相对持续"):
        if not re.search(rf"(?m)^### {gate}\s*$", section(text, "差异化价值")):
            errors.append(f"差异化价值缺少实质门：{gate}")

    rtb = section(text, "RTB")
    for evidence in ("产品证据", "体验证据", "背书证据"):
        if not re.search(rf"(?m)^### {evidence}\s*$", rtb):
            errors.append(f"RTB缺少证据分类：{evidence}")

    rtb_lines = rtb_items(rtb)
    future_terms = r"计划|拟建设|待建设|申请中|明年|未来|准备建设|尚未"
    future_rtb_lines = [line for line in rtb_lines if re.search(future_terms, line)]
    if rtb_lines and len(future_rtb_lines) == len(rtb_lines):
        errors.append("RTB不能只写未来计划或待建设能力")
    elif not rtb_lines:
        errors.append("RTB不能只写未来计划或待建设能力")
    elif future_rtb_lines:
        errors.append("RTB不能混入未来计划或待建设能力；请逐条移入能力建设或未知项栏")

    state_heading, states = first_section(text, STATE_SECTION_HEADINGS)
    state_rows: list[dict[str, str]] = []
    if not state_heading:
        errors.append("缺少必填章节：四维状态台账（兼容旧标题“当前事实、策略假设与能力缺口”）")
    else:
        for dimension in ("内容性质", "证据状态", "能力状态", "裁决状态"):
            if dimension not in states:
                errors.append(f"状态台账缺少四维字段：{dimension}")
        parsed_state_table = state_table(states)
        if parsed_state_table is None:
            if all(dimension in states for dimension in STATE_VALUES):
                errors.append("四维状态台账必须使用包含四个状态列的Markdown表格")
        else:
            header, rows = parsed_state_table
            indices = {dimension: header.index(dimension) for dimension in STATE_VALUES}
            identity_indices = [
                header.index(column)
                for column in ("字段", "内容")
                if column in header
            ]
            if not identity_indices:
                identity_indices = [
                    index
                    for index, column in enumerate(header)
                    if column not in STATE_VALUES
                ]
            effective_rows = [
                (row_number, row)
                for row_number, row in enumerate(rows, start=1)
                if len(row) >= len(header)
                and any(row[index].strip() for index in identity_indices)
            ]
            if not effective_rows:
                errors.append("四维状态台账至少需要一条有效数据记录")
            for row_number, row in effective_rows:
                row_states: dict[str, str] = {}
                for dimension, allowed in STATE_VALUES.items():
                    cell_index = indices[dimension]
                    value = row[cell_index].strip() if cell_index < len(row) else ""
                    row_states[dimension] = value
                    if value and value not in allowed:
                        allowed_text = "／".join(allowed)
                        errors.append(
                            f"状态台账第{row_number}行“{dimension}”状态格必须留空或填写单一规定值：{allowed_text}"
                        )
                state_rows.append(row_states)

    conclusion = section(text, "裁决结论")
    decision = selected_decision(conclusion)
    if decision is None:
        if re.search(r"(?m)^\s*(?:[-*]\s*)?结论\s*[：:]\s*待验证\s*$", conclusion):
            errors.append("裁决结论不能填写“待验证”；它只属于证据状态。请选择待裁决、保留、退回或淘汰")
        elif re.search(r"(?m)^\s*(?:[-*]\s*)?结论\s*[：:]\s*待建设\s*$", conclusion):
            errors.append("裁决结论不能填写“待建设”；它只属于能力状态。请选择待裁决、保留、退回或淘汰")
        elif any(mark in conclusion for mark in ("／", "/")):
            errors.append("裁决结论仍是模板多选项，请只选择待裁决、保留、退回或淘汰中的一项")
        else:
            errors.append("裁决结论必须明确选择待裁决、保留、退回或淘汰；“通过”只作为“保留”的展示别名")
    elif decision == "保留" and any(
        row.get("证据状态") == "待验证" or row.get("能力状态") == "待建设"
        for row in state_rows
    ):
        errors.append("存在待验证证据或待建设能力时，裁决不能选择保留或通过")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python3 检查品牌屋.py /绝对路径/品牌屋.md")
        return 2

    path = Path(sys.argv[1]).expanduser()
    if not path.is_file():
        print(f"❌ 文件不存在：{path}")
        return 2

    errors = validate(path.read_text(encoding="utf-8"))
    if errors:
        for error in errors:
            print(f"❌ {error}")
        print(f"共发现{len(errors)}项结构或方法门禁问题。")
        return 1

    print("✅ 品牌屋结构、状态与基础方法门禁通过。")
    print("提示：仍需人工完成事实核查、用户验证、食品合规审查和最终裁决。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
