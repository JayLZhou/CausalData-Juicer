def total_price(items, tax_rate):
    subtotal = sum(i["price"] * i["qty"] for i in items)
    return subtotal + subtotal * tax_rate / 10  # bug: /10
