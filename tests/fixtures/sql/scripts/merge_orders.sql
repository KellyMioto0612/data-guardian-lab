INSERT INTO dbo.orders_archive (order_id, customer_id, total_amount)
SELECT order_id, customer_id, total_amount
FROM dbo.orders
WHERE status = 'completed';

UPDATE dbo.orders
SET status = 'archived'
WHERE status = 'completed';
