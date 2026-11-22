import pytest
from fastapi import HTTPException
from app.models import LineItemCreate
from app.service import calculate_totals

def test_single_item_calculation():
    items = [LineItemCreate(item_name="Ergonomic Chair", quantity=2, unit_price=1500000.0)]
    calc, grand_total = calculate_totals(items)
    assert len(calc) == 1
    assert calc[0]["line_total"] == 3000000.0
    assert grand_total == 3000000.0

def test_multiple_items_and_rounding():
    items = [
        LineItemCreate(item_name="SSD NVMe 1TB", quantity=3, unit_price=1250500.50),
        LineItemCreate(item_name="RAM DDR5 32GB", quantity=2, unit_price=1800200.25),
    ]
    calc, grand_total = calculate_totals(items)
    assert calc[0]["line_total"] == 3751501.50
    assert calc[1]["line_total"] == 3600400.50
    assert grand_total == 7351902.00

def test_zero_quantity_rejection():
    with pytest.raises(Exception):
        LineItemCreate(item_name="Invalid Item", quantity=0, unit_price=50000.0)

def test_negative_price_rejection():
    with pytest.raises(Exception):
        LineItemCreate(item_name="Invalid Item", quantity=1, unit_price=-1000.0)
