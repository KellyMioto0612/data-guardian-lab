WITH recent_orders AS (
    SELECT order_id, customer_id, total_amount
    FROM dbo.orders
    WHERE created_at >= DATEADD(day, -30, GETUTCDATE())
), customer_totals AS (
    SELECT customer_id, SUM(total_amount) AS total_amount
    FROM recent_orders
    GROUP BY customer_id
)
SELECT customer_id, total_amount
FROM customer_totals;
