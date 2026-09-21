WITH hierarchy AS (
    SELECT employee_id, manager_id, employee_name, 0 AS level
    FROM dbo.employees
    WHERE manager_id IS NULL
    UNION ALL
    SELECT e.employee_id, e.manager_id, e.employee_name, h.level + 1
    FROM dbo.employees AS e
    INNER JOIN hierarchy AS h ON e.manager_id = h.employee_id
)
SELECT employee_id, manager_id, employee_name, level
FROM hierarchy;
