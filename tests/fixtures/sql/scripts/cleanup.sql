DELETE FROM dbo.orders
WHERE created_at < DATEADD(day, -90, GETUTCDATE());
