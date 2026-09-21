CREATE VIEW dbo.active_orders
AS
SELECT order_id, customer_id, status
FROM dbo.orders
WHERE status = 'active';
