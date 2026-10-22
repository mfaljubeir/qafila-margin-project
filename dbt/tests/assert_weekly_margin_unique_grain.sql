-- Each ISO week, city, and category must appear only once.
select
    iso_week,
    city,
    category,
    count(*) as duplicate_count
from {{ ref('weekly_margin') }}
group by iso_week, city, category
having count(*) > 1
