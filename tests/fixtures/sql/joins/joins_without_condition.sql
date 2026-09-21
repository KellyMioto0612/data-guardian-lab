SELECT o.order_id, c.customer_name
FROM dbo.orders AS o
INNER JOIN dbo.customers AS c;
