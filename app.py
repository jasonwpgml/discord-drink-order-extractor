from __future__ import annotations

import csv
import io
import json
from typing import Any


# Streamlit Community Cloud에서는 기본 파일 시스템 쓰기가 가능하지만,
# 앱 재실행 시 설정값이 초기화되지 않도록 세션 상태를 사용합니다.

import streamlit as st

from discord_drink_order_extractor import (
    MENU_ALIASES,
    extract_orders,
    is_unconfirmed_order,
    load_menu_aliases,
    make_summary,
    parse_discord_text,
    reload_menu_aliases,
    save_menu_aliases,
)

st.set_page_config(page_title="DrinkLister", layout="wide")

DEFAULT_SAMPLE = """[오후 3:20] 제이슨: 아아 라지 2잔, 하나는 샷추가
민수 — 오후 3:21
딸기라떼 M 얼음 적게 한잔
수진: 제이슨이랑 똑같이 1잔
영희: 바닐라라떼 톨 1잔, 아메리카노 핫 2잔 디카페인"""

if "input_text" not in st.session_state:
    st.session_state.input_text = DEFAULT_SAMPLE
if "orders" not in st.session_state:
    st.session_state.orders = []
if "summary" not in st.session_state:
    st.session_state.summary = "추출된 주문이 없습니다."
if "menu_editor_rows" not in st.session_state:
    alias_data = load_menu_aliases()
    st.session_state.menu_editor_rows = [
        {"menu": canonical, "aliases": ", ".join(aliases)}
        for canonical, aliases in alias_data.items()
    ]


def analyze_text(raw_text: str) -> tuple[int, list[Any]]:
    if not raw_text.strip():
        st.session_state.orders = []
        st.session_state.summary = "추출된 주문이 없습니다."
        return 0, []

    messages = parse_discord_text(raw_text)
    orders = extract_orders(messages)
    st.session_state.orders = orders
    st.session_state.summary = make_summary(orders)
    return len(messages), orders


def to_rows(orders: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "주문자": order.user,
            "메뉴": order.menu,
            "온도": order.temperature,
            "사이즈": order.size,
            "수량": order.quantity,
            "디카페인": order.decaf_count,
            "옵션": order.options,
            "확인/비고": order.note,
            "원문": order.source,
        }
        for order in orders
    ]


def build_csv_bytes(orders: list[Any]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "주문자",
            "메뉴",
            "온도",
            "사이즈",
            "수량",
            "디카페인",
            "옵션",
            "확인/비고",
            "원문",
        ]
    )
    for order in orders:
        writer.writerow(
            [
                order.user,
                order.menu,
                order.temperature,
                order.size,
                order.quantity,
                order.decaf_count,
                order.options,
                order.note,
                order.source,
            ]
        )
    return output.getvalue().encode("utf-8-sig")


st.title("DrinkLister")
st.caption("Discord 메시지를 붙여넣으면 주문자·메뉴·옵션을 웹에서 바로 분석합니다.")

st.subheader("1. 입력")
input_text = st.text_area(
    "Discord 메시지", value=st.session_state.input_text, height=320
)

button_cols = st.columns(2)
with button_cols[0]:
    if st.button("주문 분석", use_container_width=True):
        st.session_state.input_text = input_text
        analyze_text(input_text)
        st.success("주문 분석이 완료되었습니다.")
with button_cols[1]:
    if st.button("입력 지우기", use_container_width=True):
        st.session_state.input_text = ""
        st.session_state.orders = []
        st.session_state.summary = "추출된 주문이 없습니다."
        st.rerun()

st.divider()
with st.expander("2. 메뉴 별칭 설정", expanded=False):
    st.caption("메뉴 이름은 왼쪽, 별칭은 오른쪽에서 따로 관리할 수 있습니다.")

    if st.button("메뉴 추가", use_container_width=True):
        st.session_state.menu_editor_rows.append({"menu": "", "aliases": ""})
        st.rerun()

    rows = st.session_state.menu_editor_rows
    for index, row in enumerate(rows):
        menu_col, alias_col = st.columns([1.2, 2.2])
        with menu_col:
            menu_name = st.text_input(
                "메뉴",
                value=row["menu"],
                key=f"menu_input_{index}",
                label_visibility="collapsed",
                help="메뉴 이름을 수정하세요.",
            )
        with alias_col:
            alias_text = st.text_input(
                "별칭",
                value=row["aliases"],
                key=f"alias_input_{index}",
                label_visibility="collapsed",
                help="여러 별칭은 쉼표로 구분하세요.",
            )
        rows[index] = {"menu": menu_name, "aliases": alias_text}

    st.session_state.menu_editor_rows = rows

    if st.button("별칭 저장", use_container_width=True):
        try:
            edited_aliases: dict[str, list[str]] = {}
            for row in rows:
                menu_name = row.get("menu", "").strip()
                if not menu_name:
                    continue
                aliases = [
                    item.strip()
                    for item in str(row.get("aliases", "")).split(",")
                    if item.strip()
                ]
                if aliases:
                    edited_aliases[menu_name] = aliases
            save_menu_aliases(edited_aliases)
            reload_menu_aliases()
            st.session_state.menu_editor_rows = [
                {"menu": menu, "aliases": ", ".join(aliases)}
                for menu, aliases in load_menu_aliases().items()
            ]
            st.success("메뉴 별칭 설정을 저장했습니다.")
        except Exception as exc:  # pragma: no cover - UI feedback path
            st.error(f"설정 저장 실패: {exc}")

st.divider()

if st.session_state.orders:
    confirmed_orders = [
        order for order in st.session_state.orders if not is_unconfirmed_order(order)
    ]
    unconfirmed_orders = [
        order for order in st.session_state.orders if is_unconfirmed_order(order)
    ]
    st.subheader("3. 결과")
    metric_cols = st.columns(4)
    with metric_cols[0]:
        st.metric("분석된 메시지", len(parse_discord_text(st.session_state.input_text)))
    with metric_cols[1]:
        st.metric("주문 건수", len(st.session_state.orders))
    with metric_cols[2]:
        st.metric("확인된 주문", len(confirmed_orders))
    with metric_cols[3]:
        st.metric("미확인 주문", len(unconfirmed_orders))
    st.dataframe(
        to_rows(st.session_state.orders), use_container_width=True, hide_index=True
    )
    st.subheader("집계 요약")
    st.text_area("요약 결과", value=st.session_state.summary, height=220)
    st.download_button(
        label="CSV 다운로드",
        data=build_csv_bytes(st.session_state.orders),
        file_name="drink_orders.csv",
        mime="text/csv",
        use_container_width=True,
    )
else:
    st.info("Discord 메시지를 붙여넣고 ‘주문 분석’을 눌러주세요.")
    st.code(DEFAULT_SAMPLE, language="text")
