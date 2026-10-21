with orders as (
    select
        order_id,
        store_id,
        status,
        cast(created_at as timestamp) + interval '3 hours'
            as created_at_riyadh
    from {{ source('raw', 'orders') }}
)

select
    order_id,
    store_id,
    cast(created_at_riyadh as date) as order_date,
    cast(strftime(created_at_riyadh, '%V') as integer) as iso_week
from orders
where status = 'delivered'
  and cast(created_at_riyadh as date) >= date '2026-08-31'
