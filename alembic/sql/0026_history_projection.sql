WITH source AS MATERIALIZED (
 SELECT r.id,r.contract_id,r.created_at,r.after::jsonb AS a
 FROM public.revisions r
 WHERE r.created_at<=(SELECT max(point.value) FROM unnest(cutoffs) AS point(value))
   AND r.action IN ('created','updated','archived')
), eligible AS MATERIALIZED (
 -- Parse once, then retain small text projections for the bounded sort.
 SELECT r.id,r.contract_id,r.created_at,r.a->>'department_id' AS dept_text,
  r.a->>'financial_direction' AS direction_text,r.a->>'value_basis' AS basis_text,
  r.a->>'annual_value' AS annual_text,r.a->>'archived_at' AS archived_text
 FROM source r WHERE r.a ? 'department_id' AND r.a ? 'annual_value'
), latest AS (
 SELECT DISTINCT ON(point.value,r.contract_id) point.value AS period,
  r.dept_text,r.direction_text,r.basis_text,r.annual_text,r.archived_text
 FROM unnest(cutoffs) AS point(value) JOIN eligible r ON r.created_at<=point.value
 ORDER BY point.value,r.contract_id,r.created_at DESC,r.id DESC
), scoped AS (
 SELECT l.period,l.dept_text::integer AS dept,
  CASE WHEN l.direction_text IN ('expense','income') THEN l.direction_text ELSE 'unknown' END AS dir,
  CASE WHEN l.basis_text IN ('net','gross') THEN l.basis_text ELSE 'unknown' END AS vb,
  CASE WHEN l.annual_text ~ '^[0-9]{1,10}(\.[0-9]{1,2})?$' THEN l.annual_text::numeric END AS value
 FROM latest l WHERE COALESCE(l.archived_text,'')=''
  AND l.dept_text ~ '^[1-9][0-9]{0,8}$'
  AND (p->>'role' IN ('admin','reviewer') OR (p->>'role'='department' AND l.dept_text=p->>'department_id'))
) SELECT s.period,s.dept,s.dir,s.vb,count(*),count(s.value),sum(s.value)
 FROM scoped s GROUP BY s.period,s.dept,s.dir,s.vb
 ORDER BY s.period,s.dept,s.dir,s.vb
