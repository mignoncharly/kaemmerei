-- No raw metadata or arbitrary principal/department arguments are exposed.
-- Select the latest state BEFORE filtering historical department ownership.
CREATE FUNCTION ohvr_security.financial_history(cutoff timestamp)
RETURNS TABLE(department_id integer, direction text, basis text, record_count bigint,
              known_count bigint, annual numeric)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE p jsonb;
BEGIN
 p:=ohvr_security.resolve_principal();
 IF ohvr_security.role_kind() IS DISTINCT FROM 'web' OR p->>'kind' IS DISTINCT FROM 'user'
 OR p->>'forced' IS DISTINCT FROM 'false' OR cutoff IS NULL
 OR cutoff>timezone('UTC',statement_timestamp()) THEN
  RAISE EXCEPTION 'Historical report denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY WITH latest AS (
  SELECT DISTINCT ON (r.contract_id) r.after::jsonb AS a
  FROM public.revisions r WHERE r.created_at<=cutoff
   AND r.action IN ('created','updated','archived')
   AND r.after::jsonb ? 'department_id' AND r.after::jsonb ? 'annual_value'
  ORDER BY r.contract_id,r.created_at DESC,r.id DESC
 ), scoped AS (
  SELECT (a->>'department_id')::integer AS dept,
   CASE WHEN a->>'financial_direction' IN ('expense','income') THEN a->>'financial_direction' ELSE 'unknown' END AS dir,
   CASE WHEN a->>'value_basis' IN ('net','gross') THEN a->>'value_basis' ELSE 'unknown' END AS vb,
   CASE WHEN a->>'annual_value' ~ '^[0-9]{1,10}(\.[0-9]{1,2})?$' THEN (a->>'annual_value')::numeric END AS value
  FROM latest WHERE COALESCE(a->>'archived_at','')=''
   AND a->>'department_id' ~ '^[1-9][0-9]{0,8}$'
   AND (p->>'role' IN ('admin','reviewer') OR (p->>'role'='department' AND a->>'department_id'=p->>'department_id'))
 ) SELECT dept,dir,vb,count(*),count(value),sum(value) FROM scoped GROUP BY dept,dir,vb;
END $$;
REVOKE ALL ON FUNCTION ohvr_security.financial_history(timestamp) FROM PUBLIC;
