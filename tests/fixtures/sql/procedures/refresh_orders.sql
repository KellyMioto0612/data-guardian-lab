CREATE PROCEDURE dbo.refresh_orders
AS
BEGIN
    UPDATE dbo.orders
    SET refreshed_at = GETUTCDATE()
    WHERE status = 'pending';
END;
