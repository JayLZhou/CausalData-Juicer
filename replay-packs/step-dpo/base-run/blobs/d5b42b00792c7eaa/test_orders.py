import pytest
from pydantic import ValidationError

from orders import Order


def test_total_computed():
    order = Order(price=2.5, qty=4)
    assert order.total == 10.0


def test_qty_must_be_positive():
    with pytest.raises(ValidationError):
        Order(price=1.0, qty=0)
