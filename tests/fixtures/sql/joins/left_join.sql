SELECT c.customer_name, o.order_id
FROM dbo.customers AS c
LEFT JOIN dbo.orders AS o ON o.customer_id = c.customer_id;
