from pydantic import BaseModel, field_validator, model_validator


class Order(BaseModel):
    price: float
    qty: int
    total: float = 0.0

    @field_validator('qty')
    def qty_positive(cls, v):
        if v <= 0:
            raise ValueError('qty must be positive')
        return v

    @model_validator(
        mode='before',
        skip_on_failure=True
    )
    def compute_total(cls, values):
        values['total'] = values.get('price', 0.0) * values.get('qty', 0)
        return values


if __name__ == '__main__':
    import pytest
    pytest.main()