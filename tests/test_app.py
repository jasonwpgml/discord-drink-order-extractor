from app import extract_orders, parse_discord_text


def test_extract_orders_from_sample_message() -> None:
    text = """[오후 3:20] 제이슨: 아아 라지 2잔, 하나는 샷추가
민수 — 오후 3:21
딸기라떼 M 얼음 적게 한잔
수진: 제이슨이랑 똑같이 1잔
영희: 바닐라라떼 톨 1잔, 아메리카노 핫 2잔 디카페인"""

    messages = parse_discord_text(text)
    orders = extract_orders(messages)

    assert len(orders) >= 5
    assert any(order.menu == "아이스 아메리카노" for order in orders)
    assert any(order.menu == "딸기라떼(only iced)" for order in orders)
