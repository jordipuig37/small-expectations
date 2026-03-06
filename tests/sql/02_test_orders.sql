-- smallex:test: negative_order
-- smallex:message: total_amount can't be negative
SELECT id, user_id, total_amount
FROM orders
WHERE total_amount < 0;

-- smallex:test: order_user
-- smallex:message: orders should have existing users
SELECT o.id, o.user_id
FROM orders AS o
LEFT JOIN users AS u ON u.id = o.user_id
WHERE u.id IS NULL;

-- smallex:test: valid_order_status
-- smallex:message: order status should be one of {pending, paid, cancelled}
SELECT id, status
FROM orders
WHERE status NOT IN ('pending', 'paid', 'cancelled');
