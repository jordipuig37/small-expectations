-- smallex:test: null_emails
-- smallex:message: users.email should never be NULL
SELECT id, name, email
FROM users
WHERE email IS NULL;

-- smallex:test: empty_emails
-- smallex:message: users.email should never be empty
SELECT id, name, email
FROM users
WHERE email = '';

-- smallex:test: duplicate_ids
-- smallex:message: user ids must be unique
SELECT email, COUNT(*) AS duplicates
FROM users
WHERE email IS NOT NULL
GROUP BY email
HAVING COUNT(*) > 1;
