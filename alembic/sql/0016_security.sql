CREATE SCHEMA ohvr_security;
REVOKE ALL ON SCHEMA ohvr_security FROM PUBLIC;
CREATE TABLE ohvr_security.runtime_roles (role_name name PRIMARY KEY, kind text NOT NULL CHECK (kind IN ('web','integration','maintenance')));
REVOKE ALL ON ohvr_security.runtime_roles FROM PUBLIC;

CREATE FUNCTION ohvr_security.role_kind() RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
 SELECT kind FROM ohvr_security.runtime_roles WHERE role_name = session_user
$$;

CREATE FUNCTION ohvr_security.resolve_principal() RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp AS $$
DECLARE p record; h text; k text;
BEGIN
 k := ohvr_security.role_kind();
 IF k = 'integration' OR (k = 'web' AND COALESCE(current_setting('ohvr.token_hash',true),'') <> '') THEN
  h := current_setting('ohvr.token_hash',true);
  IF h IS NULL OR h !~ '^[0-9a-f]{64}$' THEN RETURN '{}'::jsonb; END IF;
  SELECT t.* INTO p FROM public.integration_tokens t LEFT JOIN public.departments d ON d.id=t.department_id
   WHERE t.token_hash=h AND t.is_active AND (t.expires_at IS NULL OR t.expires_at > timezone('UTC',statement_timestamp()))
     AND (t.department_id IS NULL OR d.is_active);
  IF FOUND THEN RETURN jsonb_build_object('kind','token','id',p.id,'department_id',p.department_id); END IF;
 ELSIF k = 'web' THEN
  h := current_setting('ohvr.session_hash',true);
  IF h IS NULL OR h !~ '^[0-9a-f]{64}$' THEN RETURN '{}'::jsonb; END IF;
  SELECT s.user_id,u.role,u.department_id,u.must_change_password INTO p
   FROM public.login_sessions s LEFT JOIN public.users u ON u.id=s.user_id LEFT JOIN public.departments d ON d.id=u.department_id
   WHERE s.token_hash=h AND s.expires_at > timezone('UTC',statement_timestamp())
    AND (s.user_id IS NULL OR (u.is_active AND u.role IN ('admin','reviewer','department')
         AND (u.role <> 'department' OR d.is_active)));
  IF FOUND THEN
   IF p.user_id IS NULL THEN RETURN jsonb_build_object('kind','guest'); END IF;
   RETURN jsonb_build_object('kind','user','id',p.user_id,'role',p.role,'department_id',p.department_id,'forced',p.must_change_password);
  END IF;
 END IF;
 RETURN '{}'::jsonb;
END $$;

CREATE FUNCTION ohvr_security.principal() RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE p jsonb; k text;
BEGIN
 p:=COALESCE(NULLIF(current_setting('ohvr.principal',true),''),'{}')::jsonb;
 k:=ohvr_security.role_kind();
 IF p->>'kind'='guest' AND k='web' THEN RETURN p; END IF;
 IF p->>'id' !~ '^[1-9][0-9]*$' OR p->>'id' IS NULL THEN RETURN '{}'::jsonb; END IF;
 PERFORM (p->>'id')::integer;
 IF p->>'department_id' IS NOT NULL AND p->>'department_id' !~ '^[1-9][0-9]*$' THEN RETURN '{}'::jsonb; END IF;
 IF p->>'department_id' IS NOT NULL THEN PERFORM (p->>'department_id')::integer; END IF;
 IF p->>'kind'='user' AND k='web' AND p->>'role' IN ('admin','reviewer','department') AND p->>'forced' IN ('true','false') THEN RETURN p; END IF;
 IF p->>'kind'='token' AND k IN ('web','integration') THEN RETURN p; END IF;
 RETURN '{}'::jsonb;
EXCEPTION WHEN invalid_text_representation OR numeric_value_out_of_range THEN RETURN '{}'::jsonb;
END $$;

CREATE FUNCTION ohvr_security.prepare_context(session_hash text, token_hash text, correlation text) RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 PERFORM set_config('ohvr.principal','{}',true);
 PERFORM set_config('ohvr.session_hash',COALESCE(session_hash,''),true);
 PERFORM set_config('ohvr.token_hash',COALESCE(token_hash,''),true);
 PERFORM set_config('ohvr.correlation_id',CASE WHEN correlation ~ '^[0-9a-f-]{36}$' THEN correlation ELSE gen_random_uuid()::text END,true);
 PERFORM set_config('ohvr.principal',ohvr_security.resolve_principal()::text,true);
END $$;

CREATE FUNCTION ohvr_security.uid() RETURNS integer LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ SELECT CASE WHEN ohvr_security.principal()->>'kind'='user' THEN (ohvr_security.principal()->>'id')::integer END $$;
CREATE FUNCTION ohvr_security.admin() RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ SELECT COALESCE(ohvr_security.principal()->>'role'='admin' AND ohvr_security.principal()->>'forced'='false',false) $$;
CREATE FUNCTION ohvr_security.read_department(dept integer) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
 SELECT COALESCE(CASE WHEN ohvr_security.principal()->>'kind'='token' THEN
   ohvr_security.principal()->>'department_id' IS NULL OR (ohvr_security.principal()->>'department_id')::integer=dept
  WHEN ohvr_security.principal()->>'kind'='user' AND ohvr_security.principal()->>'forced'='false' THEN
   ohvr_security.principal()->>'role' IN ('admin','reviewer') OR (ohvr_security.principal()->>'department_id')::integer=dept
  ELSE false END,false)
$$;
CREATE FUNCTION ohvr_security.write_department(dept integer) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
 SELECT COALESCE(ohvr_security.principal()->>'kind'='user' AND ohvr_security.principal()->>'forced'='false' AND
  (ohvr_security.principal()->>'role'='admin' OR (ohvr_security.principal()->>'role'='department' AND (ohvr_security.principal()->>'department_id')::integer=dept)),false)
$$;
CREATE FUNCTION ohvr_security.read_contract(cid integer) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ SELECT COALESCE((SELECT ohvr_security.read_department(department_id) FROM public.contracts WHERE id=cid),false) $$;
CREATE FUNCTION ohvr_security.write_contract(cid integer) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ SELECT COALESCE((SELECT ohvr_security.write_department(department_id) AND archived_at IS NULL FROM public.contracts WHERE id=cid),false) $$;
-- SELECT FOR UPDATE also applies UPDATE policies. Authorized approvers must
-- lock the aggregate without receiving permission to edit its contract fields.
CREATE FUNCTION ohvr_security.lock_contract(cid integer) RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF ohvr_security.role_kind()<>'web' OR ohvr_security.principal()->>'kind'<>'user' THEN RETURN false; END IF;
 PERFORM id FROM public.contracts WHERE id=cid AND ohvr_security.read_department(department_id) FOR UPDATE;
 RETURN FOUND;
END $$;
CREATE FUNCTION ohvr_security.decide(cid integer, tid integer, assignee integer) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
 SELECT ohvr_security.read_contract(cid) AND EXISTS(SELECT 1 FROM public.contracts c WHERE c.id=cid AND c.archived_at IS NULL)
  AND (ohvr_security.admin() OR (assignee=ohvr_security.uid() AND EXISTS (
    SELECT 1 FROM public.users u JOIN public.recipient_memberships m ON m.user_id=u.id JOIN public.recipient_teams t ON t.id=m.team_id
    WHERE u.id=ohvr_security.uid() AND u.can_approve AND t.id=tid AND t.is_active)))
$$;
CREATE FUNCTION ohvr_security.append_revision(cid integer) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
 SELECT ohvr_security.write_department(c.department_id) OR EXISTS(SELECT 1 FROM public.contract_reviews r WHERE r.contract_id=cid AND ohvr_security.decide(cid,r.team_id,r.assigned_user_id))
 FROM public.contracts c WHERE c.id=cid
$$;
CREATE FUNCTION ohvr_security.member(tid integer) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ SELECT EXISTS(SELECT 1 FROM public.recipient_memberships WHERE team_id=tid AND user_id=ohvr_security.uid()) $$;

-- Targeted credential bootstrap only; no integration execution grant is given.
CREATE FUNCTION ohvr_security.password_hash(target_id integer) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
 SELECT u.password_hash FROM public.users u WHERE u.id=target_id AND ohvr_security.role_kind()='web'
  AND (ohvr_security.principal()->>'kind'='guest' OR u.id=ohvr_security.uid())
$$;
CREATE FUNCTION ohvr_security.resolve_token(prefix text, credential_hash text) RETURNS integer LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
 SELECT id FROM public.integration_tokens WHERE token_prefix=prefix AND token_hash=credential_hash
  AND id=(ohvr_security.principal()->>'id')::integer AND ohvr_security.principal()->>'kind'='token'
$$;

CREATE FUNCTION ohvr_security.protect_user() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF session_user = (SELECT r.rolname FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname='ohvr_security') THEN RETURN NEW; END IF;
 IF ohvr_security.admin() THEN RETURN NEW; END IF;
 IF OLD.id <> ohvr_security.uid() OR (to_jsonb(NEW)-'password_hash'-'must_change_password') IS DISTINCT FROM (to_jsonb(OLD)-'password_hash'-'must_change_password') OR NEW.must_change_password THEN
  RAISE EXCEPTION 'Identity privilege change denied' USING ERRCODE='42501';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_user BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION ohvr_security.protect_user();

CREATE FUNCTION ohvr_security.protect_review() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF session_user = (SELECT r.rolname FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname='ohvr_security') OR ohvr_security.admin() THEN RETURN NEW; END IF;
 IF (to_jsonb(NEW)-'status'-'result_text'-'updated_by_id'-'updated_at') IS DISTINCT FROM (to_jsonb(OLD)-'status'-'result_text'-'updated_by_id'-'updated_at') OR NEW.updated_by_id IS DISTINCT FROM ohvr_security.uid() THEN
  RAISE EXCEPTION 'Review reassignment denied' USING ERRCODE='42501';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER protect_review BEFORE UPDATE ON public.contract_reviews FOR EACH ROW EXECUTE FUNCTION ohvr_security.protect_review();

CREATE FUNCTION ohvr_security.immutable_audit() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,pg_temp AS $$ BEGIN RAISE EXCEPTION 'Append-only audit record' USING ERRCODE='42501'; END $$;

CREATE FUNCTION ohvr_security.audit_identity() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF ohvr_security.role_kind()='web' THEN NEW.actor_id:=ohvr_security.uid(); NEW.principal:='user'; END IF;
 NEW.outcome:=CASE WHEN NEW.action ~ '_denied$' THEN 'denied' ELSE 'success' END;
 NEW.correlation_id:=COALESCE(NULLIF(current_setting('ohvr.correlation_id',true),''),gen_random_uuid()::text);
 RETURN NEW;
END $$;
CREATE TRIGGER audit_identity BEFORE INSERT ON public.identity_audit FOR EACH ROW EXECUTE FUNCTION ohvr_security.audit_identity();

CREATE FUNCTION ohvr_security.capture_event() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$
DECLARE row_data jsonb; p jsonb; cid integer;
BEGIN
 row_data:=CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
 p:=ohvr_security.principal();
 cid:=CASE WHEN TG_TABLE_NAME='contracts' THEN (row_data->>'id')::integer ELSE (row_data->>'contract_id')::integer END;
 INSERT INTO public.security_events(actor_id,token_id,principal,action,target,contract_id,created_at,outcome,correlation_id,details)
 VALUES(ohvr_security.uid(),CASE WHEN p->>'kind'='token' THEN (p->>'id')::integer END,
  COALESCE(p->>'kind','migration'),TG_OP,TG_TABLE_NAME||':'||(row_data->>'id'),cid,timezone('UTC',statement_timestamp()),'success',
  COALESCE(NULLIF(current_setting('ohvr.correlation_id',true),''),gen_random_uuid()::text),
  jsonb_build_object('table',TG_TABLE_NAME,'operation',TG_OP,'department_id',row_data->'department_id','version',row_data->'version'));
 RETURN COALESCE(NEW,OLD);
END $$;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ohvr_security FROM PUBLIC;
