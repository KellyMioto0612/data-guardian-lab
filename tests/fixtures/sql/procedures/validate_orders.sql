CREATE PROCEDURE dbo.validate_orders
AS
BEGIN
    SELECT order_id, customer_id
    FROM dbo.orders
    WHERE total_amount >= 0;

    EXEC dbo.refresh_orders;
END;
