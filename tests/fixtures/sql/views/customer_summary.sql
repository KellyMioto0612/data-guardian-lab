CREATE VIEW dbo.customer_summary
AS
SELECT c.customer_id, c.customer_name, COUNT(o.order_id) AS order_count
FROM dbo.customers AS c
LEFT JOIN dbo.orders AS o ON o.customer_id = c.customer_id
GROUP BY c.customer_id, c.customer_name;
