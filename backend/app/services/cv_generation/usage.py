from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.llm_run import LlmRun
from app.schemas.usage import UsageBreakdownItem, UsageDayItem, UsageSummary


def compute_usage_summary(db: Session) -> UsageSummary:
    """Aggregates the full llm_runs audit log -- every stage of every real
    generation ever run, success or failure -- into overall totals plus
    breakdowns by stage, model, and day. Grouping is done in Python rather
    than SQL date functions, since the row volume for a personal app is small
    and this keeps the query portable across SQLite/Postgres.
    """
    runs = list(db.scalars(select(LlmRun)).all())

    total_cost = 0.0
    total_in = 0
    total_out = 0
    failed_calls = 0

    by_stage: dict[str, list[float | int]] = defaultdict(lambda: [0.0, 0, 0, 0])
    by_model: dict[str, list[float | int]] = defaultdict(lambda: [0.0, 0, 0, 0])
    by_day: dict[str, list[float | int]] = defaultdict(lambda: [0.0, 0])

    for run in runs:
        cost = run.estimated_cost_usd or 0.0
        in_tok = run.input_tokens or 0
        out_tok = run.output_tokens or 0

        total_cost += cost
        total_in += in_tok
        total_out += out_tok
        if run.status != "success":
            failed_calls += 1

        stage_bucket = by_stage[run.stage]
        stage_bucket[0] += cost
        stage_bucket[1] += in_tok
        stage_bucket[2] += out_tok
        stage_bucket[3] += 1

        model_bucket = by_model[run.model]
        model_bucket[0] += cost
        model_bucket[1] += in_tok
        model_bucket[2] += out_tok
        model_bucket[3] += 1

        day_key = run.created_at.date().isoformat()
        day_bucket = by_day[day_key]
        day_bucket[0] += cost
        day_bucket[1] += 1

    return UsageSummary(
        total_cost_usd=round(total_cost, 6),
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_calls=len(runs),
        failed_calls=failed_calls,
        by_stage=[
            UsageBreakdownItem(key=k, cost_usd=round(v[0], 6), input_tokens=v[1], output_tokens=v[2], calls=v[3])
            for k, v in sorted(by_stage.items(), key=lambda kv: -kv[1][0])
        ],
        by_model=[
            UsageBreakdownItem(key=k, cost_usd=round(v[0], 6), input_tokens=v[1], output_tokens=v[2], calls=v[3])
            for k, v in sorted(by_model.items(), key=lambda kv: -kv[1][0])
        ],
        by_day=[
            UsageDayItem(date=k, cost_usd=round(v[0], 6), calls=v[1])
            for k, v in sorted(by_day.items())
        ],
    )
