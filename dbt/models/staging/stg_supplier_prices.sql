with source as (
    select
        supplier_id,
        trim(sku) as sku,
        valid_from,
        parse_filename(filename) as source_file,
        coalesce(
            cast(unit_cost as varchar),
            cast(cost_sar as varchar)
        ) as raw_cost
    from {{ source('raw', 'supplier_prices') }}
),

cleaned as (
    select
        *,
        translate(
            replace(replace(trim(raw_cost), '٫', '.'), ',', '.'),
            '٠١٢٣٤٥٦٧٨٩',
            '0123456789'
        ) as normalized_cost
    from source
)

select
    supplier_id,
    sku,
    valid_from,
    source_file,
    raw_cost,
    round(try_cast(normalized_cost as double), 2) as unit_cost_sar
from cleaned
