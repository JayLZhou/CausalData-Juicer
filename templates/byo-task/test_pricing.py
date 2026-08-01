from pricing import total_price


def test_total_with_tax():
    items = [{"price": 10.0, "qty": 2}, {"price": 5.0, "qty": 1}]
    assert total_price(items, 0.2) == 30.0
