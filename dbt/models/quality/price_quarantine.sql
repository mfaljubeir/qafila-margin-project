with checked as (
    select
        s.supplier_id,
        s.sku,
        s.valid_from,
        s.source_file,
        s.raw_cost,
        case
            when p.product_id is null then 'unknown_sku'
            when s.unit_cost_sar is null
              or s.unit_cost_sar <= 0 then 'invalid_cost'
            else null
        end as reason
    from {{ ref('stg_supplier_prices') }} s
    left join {{ source('raw', 'products') }} p
        on s.sku = trim(p.sku)
)

select
    supplier_id,
    sku,
    valid_from,
    source_file,
    raw_cost,
    reason
from checked
where reason is not null
