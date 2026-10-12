-- 中文注释：SQL
SELECT d.id, d.title, COUNT(c.id) AS 评论数
FROM docs AS d
LEFT JOIN comments AS c ON c.doc_id = d.id
WHERE d.status = 'active'
GROUP BY d.id, d.title
ORDER BY 评论数 DESC
LIMIT 10;
