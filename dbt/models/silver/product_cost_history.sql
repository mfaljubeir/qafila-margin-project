with valid_prices as (
    select s.*
    from {{ ref('stg_supplier_prices') }} s
    left join {{ source('raw', 'products') }} p
        on s.sku = trim(p.sku)
    where p.product_id is not null
      and s.unit_cost_sar > 0
),

latest_files as (
    select *
    from valid_prices
    qualify row_number() over (
        partition by sku, valid_from
        order by source_file desc
    ) = 1
),

cost_changes as (
    select
        sku,
        unit_cost_sar,
        valid_from,
        lag(unit_cost_sar) over (
            partition by sku
            order by valid_from
        ) as previous_cost
    from latest_files
),

versions as (
    select sku, unit_cost_sar, valid_from
    from cost_changes
    where previous_cost is null
       or unit_cost_sar <> previous_cost
)

select
    sku,
    cast(unit_cost_sar as double) as unit_cost_sar,
    valid_from,
    lead(valid_from) over (
        partition by sku
        order by valid_from
    ) as valid_to,
    lead(valid_from) over (
        partition by sku
        order by valid_from
    ) is null as is_current
from versions
