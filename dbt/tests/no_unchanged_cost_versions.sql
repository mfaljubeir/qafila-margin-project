with cost_versions as (
    select
        sku,
        valid_from,
        unit_cost_sar,
        lag(unit_cost_sar) over (
            partition by sku
            order by valid_from
        ) as previous_cost
    from {{ ref('product_cost_history') }}
)

select *
from cost_versions
where unit_cost_sar = previous_cost
