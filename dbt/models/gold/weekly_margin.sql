with order_lines as (
    select
        o.iso_week,
        o.order_date,
        s.city,
        p.category,
        p.sku,
        i.quantity,
        round(i.quantity * i.unit_price - i.discount, 2)
            as line_revenue
    from {{ ref('stg_orders') }} o
    join {{ source('raw', 'order_items') }} i
        on o.order_id = i.order_id
    join {{ source('raw', 'products') }} p
        on i.product_id = p.product_id
    join {{ source('raw', 'stores') }} s
        on o.store_id = s.store_id
    where i.quantity > 0
),

costed_lines as (
    select
        l.*,
        h.unit_cost_sar,
        l.quantity * h.unit_cost_sar as line_cost
    from order_lines l
    left join {{ ref('product_cost_history') }} h
        on trim(l.sku) = h.sku
       and l.order_date >= h.valid_from
       and (
           l.order_date < h.valid_to
           or h.valid_to is null
       )
)

select
    iso_week,
    city,
    category,
    count(*) as lines,
    round(sum(line_revenue), 2) as revenue_sar,
    round(sum(case
        when unit_cost_sar is not null then line_revenue
        else 0
    end), 2) as costed_revenue_sar,
    round(sum(coalesce(line_cost, 0)), 2) as cost_sar,
    round(
        sum(case
            when unit_cost_sar is not null then line_revenue
            else 0
        end) - sum(coalesce(line_cost, 0)),
        2
    ) as margin_sar,
    sum(case
        when unit_cost_sar is null then 1
        else 0
    end) as uncosted_lines
from costed_lines
group by iso_week, city, category
