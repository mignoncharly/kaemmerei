-- Owner-only encrypted credentials and policy. Runtime roles receive narrowly
-- scoped functions, never table/column grants. The shared web role remains a
-- trusted application boundary, as for password/session bootstrap.
ALTER TABLE public.mfa_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mfa_credentials FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mfa_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mfa_policy FORCE ROW LEVEL SECURITY;
CREATE POLICY owner_only ON public.mfa_credentials FOR ALL USING
 (current_user=(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='ohvr_security'))
 WITH CHECK (current_user=(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='ohvr_security'));
CREATE POLICY owner_only ON public.mfa_policy FOR ALL USING
 (current_user=(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='ohvr_security'))
 WITH CHECK (current_user=(SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='ohvr_security'));
REVOKE ALL ON public.mfa_credentials,public.mfa_policy FROM PUBLIC;

CREATE FUNCTION ohvr_security.mfa_policy_required() RETURNS boolean
 LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 DECLARE setting boolean;
 BEGIN
  SELECT required INTO setting FROM public.mfa_policy WHERE id=1;
  IF NOT FOUND THEN RAISE EXCEPTION 'MFA policy is missing'; END IF;
  RETURN setting;
 END;
$$;

CREATE FUNCTION ohvr_security.mfa_required_for(target integer) RETURNS boolean
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT ohvr_security.role_kind()='web' AND
 (ohvr_security.mfa_policy_required() OR EXISTS(
  SELECT 1 FROM public.mfa_credentials WHERE user_id=target AND enabled))
$$;

CREATE FUNCTION ohvr_security.mfa_subject(challenge text) RETURNS integer
 LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT s.pending_user_id FROM public.login_sessions s
 JOIN public.users u ON u.id=s.pending_user_id
 LEFT JOIN public.departments d ON d.id=u.department_id
 WHERE ohvr_security.role_kind()='web'
 AND challenge=current_setting('ohvr.session_hash',true)
 AND s.token_hash=challenge AND s.user_id IS NULL AND s.pending_user_id IS NOT NULL
 AND s.expires_at>timezone('UTC',statement_timestamp()) AND s.mfa_attempts<=5
 AND u.is_active AND (u.role<>'department' OR d.is_active)
$$;

CREATE FUNCTION ohvr_security.mfa_material(challenge text,candidate text) RETURNS jsonb
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 DECLARE subject integer; credential public.mfa_credentials%ROWTYPE;
 BEGIN
  subject:=ohvr_security.mfa_subject(challenge);
  IF subject IS NULL THEN RETURN NULL; END IF;
  SELECT * INTO credential FROM public.mfa_credentials WHERE user_id=subject FOR UPDATE;
  IF NOT FOUND THEN RETURN NULL; END IF;
  IF NOT credential.enabled AND (credential.authorization_expires_at IS NULL OR
      credential.authorization_expires_at<=timezone('UTC',statement_timestamp())) THEN RETURN NULL; END IF;
  IF credential.seed_ciphertext IS NULL AND candidate IS NOT NULL AND NOT credential.enabled THEN
   IF length(candidate)<100 OR length(candidate)>512 OR candidate !~ '^[A-Za-z0-9_-]+={0,2}$' THEN
    RAISE EXCEPTION 'invalid encrypted enrollment material';
   END IF;
   UPDATE public.mfa_credentials SET seed_ciphertext=candidate WHERE user_id=subject;
   credential.seed_ciphertext:=candidate;
   INSERT INTO public.security_events(actor_id,principal,action,target,created_at,outcome,correlation_id,details)
    VALUES(subject,'user','MFA_ENROLLMENT_STARTED','user:'||subject,timezone('UTC',statement_timestamp()),'success',
     coalesce(nullif(current_setting('ohvr.correlation_id',true),''),gen_random_uuid()::text),'{}'::jsonb);
  END IF;
  RETURN jsonb_build_object('user_id',subject,'ciphertext',credential.seed_ciphertext,
                           'enabled',credential.enabled,'last_step',credential.last_step);
 END;
$$;

CREATE FUNCTION ohvr_security.mfa_confirm(challenge text,step integer) RETURNS boolean
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 DECLARE subject integer; credential public.mfa_credentials%ROWTYPE;
         current_step integer:=floor(extract(epoch FROM statement_timestamp())/30)::integer;
 BEGIN
  subject:=ohvr_security.mfa_subject(challenge);
  IF subject IS NULL OR step IS NULL OR step<current_step-1 OR step>current_step+1 THEN RETURN false; END IF;
  SELECT * INTO credential FROM public.mfa_credentials WHERE user_id=subject FOR UPDATE;
  IF NOT FOUND OR credential.seed_ciphertext IS NULL OR step<=credential.last_step THEN RETURN false; END IF;
  IF NOT credential.enabled AND (credential.authorization_expires_at IS NULL OR
      credential.authorization_expires_at<=timezone('UTC',statement_timestamp())) THEN RETURN false; END IF;
  UPDATE public.mfa_credentials SET enabled=true,last_step=step,authorization_expires_at=NULL WHERE user_id=subject;
  -- Full and pending sessions, including other browsers, are revoked on first
  -- enrollment. The current challenge is consumed by the route in this transaction.
  IF NOT credential.enabled THEN
   DELETE FROM public.login_sessions WHERE (user_id=subject OR pending_user_id=subject) AND token_hash<>challenge;
  END IF;
  INSERT INTO public.security_events(actor_id,principal,action,target,created_at,outcome,correlation_id,details)
   VALUES(subject,'user',CASE WHEN credential.enabled THEN 'MFA_VERIFIED' ELSE 'MFA_ENROLLED' END,
    'user:'||subject,timezone('UTC',statement_timestamp()),'success',
    coalesce(nullif(current_setting('ohvr.correlation_id',true),''),gen_random_uuid()::text),'{}'::jsonb);
  RETURN true;
 END;
$$;

CREATE FUNCTION ohvr_security.mfa_denied(challenge text) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 DECLARE subject integer;
 BEGIN
  subject:=ohvr_security.mfa_subject(challenge);
  IF subject IS NULL THEN RETURN; END IF;
  INSERT INTO public.security_events(actor_id,principal,action,target,created_at,outcome,correlation_id,details)
   VALUES(subject,'user','MFA_DENIED','user:'||subject,timezone('UTC',statement_timestamp()),'denied',
    coalesce(nullif(current_setting('ohvr.correlation_id',true),''),gen_random_uuid()::text),'{}'::jsonb);
 END;
$$;

REVOKE ALL ON FUNCTION ohvr_security.mfa_policy_required(),ohvr_security.mfa_required_for(integer),
 ohvr_security.mfa_subject(text),ohvr_security.mfa_material(text,text),
 ohvr_security.mfa_confirm(text,integer),ohvr_security.mfa_denied(text) FROM PUBLIC;
