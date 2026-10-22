-- Validate SCD2 date boundaries and current-version flags.
-- Every non-final version must end when the next version begins.
-- Only the final version for each SKU may be current.

with ordered_versions as (
    select
        sku,
        valid_from,
        valid_to,
        is_current,
        lead(valid_from) over (
            partition by sku
            order by valid_from
        ) as next_valid_from
    from {{ ref('product_cost_history') }}
)

select *
from ordered_versions
where
    valid_from is null
    or (valid_to is not null and valid_to <= valid_from)
    or valid_to is distinct from next_valid_from
    or is_current is distinct from (next_valid_from is null)
