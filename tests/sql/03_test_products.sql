-- smallex:name: product_positive_price
-- smallex:message: all products should have positive price
SELECT id, sku, price
FROM products
WHERE price <= 0;
