-- No caller-supplied principal, department or raw historical state output.
CREATE FUNCTION ohvr_security.financial_history_series(cutoffs timestamp[])
RETURNS TABLE(observed_at timestamp, department_id integer, direction text,
 basis text, record_count bigint, known_count bigint, annual numeric)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE p jsonb;
BEGIN
 p:=ohvr_security.resolve_principal();
 IF ohvr_security.role_kind() IS DISTINCT FROM 'web' OR p->>'kind' IS DISTINCT FROM 'user'
 OR p->>'forced' IS DISTINCT FROM 'false' OR cutoffs IS NULL
 OR cardinality(cutoffs) NOT BETWEEN 1 AND 5
 OR EXISTS(SELECT 1 FROM unnest(cutoffs) AS point(value)
           WHERE point.value IS NULL OR point.value>timezone('UTC',statement_timestamp())) THEN
  RAISE EXCEPTION 'Historical series denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY WITH source AS MATERIALIZED (
  -- Parse each qualifying historical state once for all bounded cutoffs.
  SELECT r.id,r.contract_id,r.created_at,r.after::jsonb AS a
  FROM public.revisions r
  WHERE r.created_at<=(SELECT max(point.value) FROM unnest(cutoffs) AS point(value))
    AND r.action IN ('created','updated','archived')
 ), latest AS (
  -- Sort only IDs/timestamps. Historical scope MUST follow latest selection.
  SELECT DISTINCT ON(point.value,r.contract_id) point.value AS period,r.id
  FROM unnest(cutoffs) AS point(value) JOIN source r ON r.created_at<=point.value
  WHERE r.a ? 'department_id' AND r.a ? 'annual_value'
  ORDER BY point.value,r.contract_id,r.created_at DESC,r.id DESC
 ), scoped AS (
  SELECT l.period,(r.a->>'department_id')::integer AS dept,
   CASE WHEN r.a->>'financial_direction' IN ('expense','income') THEN r.a->>'financial_direction' ELSE 'unknown' END AS dir,
   CASE WHEN r.a->>'value_basis' IN ('net','gross') THEN r.a->>'value_basis' ELSE 'unknown' END AS vb,
   CASE WHEN r.a->>'annual_value' ~ '^[0-9]{1,10}(\.[0-9]{1,2})?$' THEN (r.a->>'annual_value')::numeric END AS value
  FROM latest l JOIN source r ON r.id=l.id
  WHERE COALESCE(r.a->>'archived_at','')=''
    AND r.a->>'department_id' ~ '^[1-9][0-9]{0,8}$'
    AND (p->>'role' IN ('admin','reviewer') OR (p->>'role'='department' AND r.a->>'department_id'=p->>'department_id'))
 ) SELECT s.period,s.dept,s.dir,s.vb,count(*),count(s.value),sum(s.value)
   FROM scoped s GROUP BY s.period,s.dept,s.dir,s.vb
   ORDER BY s.period,s.dept,s.dir,s.vb;
END $$;
REVOKE ALL ON FUNCTION ohvr_security.financial_history_series(timestamp[]) FROM PUBLIC;
