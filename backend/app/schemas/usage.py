from pydantic import BaseModel


class UsageBreakdownItem(BaseModel):
    key: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    calls: int


class UsageDayItem(BaseModel):
    date: str
    cost_usd: float
    calls: int


class UsageSummary(BaseModel):
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_calls: int
    failed_calls: int
    by_stage: list[UsageBreakdownItem]
    by_model: list[UsageBreakdownItem]
    by_day: list[UsageDayItem]
