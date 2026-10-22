-- Reconcile weekly margin against eligible source order lines.
-- Compare both line counts and revenue at the final reporting grain.

with expected as (
    select
        o.iso_week,
        s.city,
        p.category,
        count(*) as expected_lines,
        round(
            sum(round(i.quantity * i.unit_price - i.discount, 2)),
            2
        ) as expected_revenue
    from {{ ref('stg_orders') }} o
    join {{ source('raw', 'order_items') }} i
        on o.order_id = i.order_id
    join {{ source('raw', 'products') }} p
        on i.product_id = p.product_id
    join {{ source('raw', 'stores') }} s
        on o.store_id = s.store_id
    where i.quantity > 0
    group by o.iso_week, s.city, p.category
),

actual as (
    select
        iso_week,
        city,
        category,
        sum(lines) as actual_lines,
        round(sum(revenue_sar), 2) as actual_revenue
    from {{ ref('weekly_margin') }}
    group by iso_week, city, category
)

select
    coalesce(e.iso_week, a.iso_week) as iso_week,
    coalesce(e.city, a.city) as city,
    coalesce(e.category, a.category) as category,
    e.expected_lines,
    a.actual_lines,
    e.expected_revenue,
    a.actual_revenue
from expected e
full outer join actual a
    on e.iso_week = a.iso_week
   and e.city = a.city
   and e.category = a.category
where e.expected_lines is distinct from a.actual_lines
   or e.expected_revenue is distinct from a.actual_revenue
