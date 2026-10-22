-- Validate financial and line-count consistency in Gold.

select
    iso_week,
    city,
    category,
    lines,
    revenue_sar,
    costed_revenue_sar,
    cost_sar,
    margin_sar,
    uncosted_lines
from {{ ref('weekly_margin') }}
where
    lines <= 0
    or uncosted_lines is null
    or uncosted_lines < 0
    or uncosted_lines > lines
    or revenue_sar is null
    or costed_revenue_sar is null
    or cost_sar is null
    or margin_sar is null
    or abs(
        margin_sar - (costed_revenue_sar - cost_sar)
    ) > 0.01
