-- No direct table privileges for integration callers. Fixed budgets and UTC,
-- fixed search_path, no dynamic SQL; scope keys are digests, never credentials.
CREATE FUNCTION ohvr_security.consume_api_rate(principal_key text, address_key text, global_key text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE keys text[] := ARRAY[principal_key,address_key,global_key];
        limits integer[] := ARRAY[120,240,1200];
        instant timestamp := timezone('UTC',statement_timestamp());
        i integer;
BEGIN
 IF ohvr_security.role_kind() <> 'integration' THEN
   RAISE EXCEPTION 'integration role required';
 END IF;
 FOR i IN 1..3 LOOP
   IF keys[i] IS NULL OR keys[i] !~ '^[0-9a-f]{64}$' THEN
     RAISE EXCEPTION 'invalid admission key';
   END IF;
 END LOOP;
 -- One short transaction serializes check+reservation across all processes.
 PERFORM pg_advisory_xact_lock(724931821);
 FOR i IN 1..3 LOOP
   IF (SELECT count(*) FROM public.login_attempts
       WHERE key_hash=keys[i] AND created_at>=instant-interval '1 minute') >= limits[i] THEN
     RETURN false;
   END IF;
 END LOOP;
 INSERT INTO public.login_attempts(key_hash,created_at)
 SELECT k,instant FROM unnest(keys) k;
 RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION ohvr_security.consume_api_rate(text,text,text) FROM PUBLIC;
