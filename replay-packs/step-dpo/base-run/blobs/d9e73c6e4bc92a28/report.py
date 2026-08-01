from pydantic import BaseModel


class Metric(BaseModel):
    name: str
    value: float


def render_report(metrics):
    return '\n'.join(m.model_dump_json(exclude_unset=True, by_alias=True) for m in metrics)