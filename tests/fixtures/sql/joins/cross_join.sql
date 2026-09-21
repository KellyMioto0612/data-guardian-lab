SELECT c.customer_name, s.segment_name
FROM dbo.customers AS c
CROSS JOIN dbo.customer_segments AS s;
