-- Every aggregate writer meets the snapshot barrier before changing any row.
CREATE FUNCTION ohvr_security.sync_writer() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ BEGIN
 PERFORM 1 FROM public.sync_state WHERE id=1 FOR UPDATE;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
END $$;
CREATE FUNCTION ohvr_security.sync_capture() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ DECLARE cid integer; olddept integer; newdept integer; category text; BEGIN
 IF TG_TABLE_NAME='contracts' THEN
  IF TG_OP<>'INSERT' THEN olddept:=OLD.department_id; END IF;
  IF TG_OP<>'DELETE' THEN newdept:=NEW.department_id;cid:=NEW.id; ELSE cid:=OLD.id; END IF;
  category:='contract';
 ELSE
  IF TG_OP='DELETE' THEN cid:=OLD.contract_id; ELSE cid:=NEW.contract_id; END IF;
  SELECT department_id INTO newdept FROM public.contracts WHERE id=cid;olddept:=newdept;
  UPDATE public.contracts SET updated_at=timezone('UTC',statement_timestamp()) WHERE id=cid AND archived_at IS NULL;
  category:=CASE TG_TABLE_NAME WHEN 'contract_documents' THEN 'document' WHEN 'contract_tasks' THEN 'task'
    WHEN 'contract_reviews' THEN 'review' WHEN 'review_decisions' THEN 'decision' ELSE 'history' END;
 END IF;
 INSERT INTO public.sync_outbox(event_key,contract_id,old_department_id,new_department_id,kind)
 VALUES(gen_random_uuid()::text,cid,olddept,newdept,category);
 RETURN NULL;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['contracts','contract_documents','contract_tasks','contract_reviews','review_decisions','revisions'] LOOP
  EXECUTE format('CREATE TRIGGER sync_writer BEFORE INSERT OR UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION ohvr_security.sync_writer()',t);
  EXECUTE format('CREATE TRIGGER sync_capture AFTER INSERT OR UPDATE OR DELETE ON public.%I FOR EACH ROW EXECUTE FUNCTION ohvr_security.sync_capture()',t);
 END LOOP;
END $$;

-- This is publication of committed outbox entries, never a source sequence watermark.
CREATE FUNCTION ohvr_security.sync_barrier() RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ DECLARE r record; n integer; f integer; BEGIN
 IF ohvr_security.resolve_principal()->>'kind'<>'token' OR ohvr_security.resolve_principal()->>'kind' IS NULL THEN
  RETURN NULL; END IF;
 SELECT next_seq,floor INTO n,f FROM public.sync_state WHERE id=1 FOR UPDATE;
 FOR r IN SELECT * FROM public.sync_outbox WHERE published_seq IS NULL ORDER BY id LOOP
  n:=n+1;
  INSERT INTO public.sync_events(seq,event_key,contract_id,old_department_id,new_department_id,kind)
   VALUES(n,r.event_key,r.contract_id,r.old_department_id,r.new_department_id,r.kind);
  UPDATE public.sync_outbox SET published_seq=n WHERE id=r.id;
 END LOOP;
 UPDATE public.sync_state SET next_seq=n WHERE id=1;
 RETURN jsonb_build_object('boundary',n,'floor',f);
END $$;
CREATE FUNCTION ohvr_security.token_grant_change() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ BEGIN
 IF (NEW.api_scopes,NEW.department_id,NEW.owner_user_id,NEW.service_owner,NEW.is_active,NEW.expires_at)
 IS DISTINCT FROM (OLD.api_scopes,OLD.department_id,OLD.owner_user_id,OLD.service_owner,OLD.is_active,OLD.expires_at)
 THEN PERFORM 1 FROM public.sync_state WHERE id=1 FOR UPDATE;
 NEW.grant_version:=OLD.grant_version+1; END IF;RETURN NEW;
END $$;
CREATE TRIGGER token_grant_change BEFORE UPDATE ON public.integration_tokens FOR EACH ROW EXECUTE FUNCTION ohvr_security.token_grant_change();
DO $$ DECLARE t text; trusted text; access text; BEGIN
 trusted:='current_user=(SELECT r.rolname FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname=''ohvr_security'')';
 FOREACH t IN ARRAY ARRAY['sync_state','sync_outbox','sync_events','sync_cursors','sync_snapshot_items'] LOOP
  EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY trusted_owner ON public.%I FOR ALL USING (%s) WITH CHECK (%s)',t,trusted,trusted);
  IF t IN ('sync_cursors','sync_snapshot_items') THEN
   access:='ohvr_security.role_kind()=''integration'' AND ohvr_security.principal()->>''kind''=''token'' AND token_id=(ohvr_security.principal()->>''id'')::integer';
   EXECUTE format('CREATE POLICY token_read ON public.%I FOR SELECT USING (%s)',t,access);
   EXECUTE format('CREATE POLICY token_create ON public.%I FOR INSERT WITH CHECK (%s)',t,access);
  ELSIF t='sync_events' THEN
   access:='ohvr_security.principal()->>''kind''=''token'' AND (ohvr_security.principal()->>''department_id'' IS NULL OR old_department_id=(ohvr_security.principal()->>''department_id'')::integer OR new_department_id=(ohvr_security.principal()->>''department_id'')::integer)';
   EXECUTE format('CREATE POLICY token_read ON public.%I FOR SELECT USING (%s)',t,access);
  END IF;
 END LOOP;
END $$;
REVOKE ALL ON FUNCTION ohvr_security.sync_barrier(),ohvr_security.sync_capture(),ohvr_security.sync_writer(),ohvr_security.token_grant_change() FROM PUBLIC;

-- Runtime readers never receive the raw old/new scope columns.
CREATE FUNCTION ohvr_security.sync_events_page(after_seq integer, page_size integer)
RETURNS TABLE(seq integer,event_key text,contract_id integer,kind text,removed boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$ DECLARE p jsonb; dept integer; BEGIN
 p:=ohvr_security.resolve_principal();
 IF p->>'kind' IS DISTINCT FROM 'token' OR page_size NOT BETWEEN 1 AND 501 OR after_seq<0 THEN
  RAISE EXCEPTION 'Invalid synchronization request' USING ERRCODE='42501'; END IF;
 dept:=(p->>'department_id')::integer;
 RETURN QUERY SELECT e.seq,e.event_key::text,e.contract_id,
  CASE WHEN NOT EXISTS(SELECT 1 FROM public.contracts c WHERE c.id=e.contract_id AND (dept IS NULL OR c.department_id=dept))
    OR (dept IS NOT NULL AND e.new_department_id IS DISTINCT FROM dept) THEN NULL ELSE e.kind::text END,
  NOT EXISTS(SELECT 1 FROM public.contracts c WHERE c.id=e.contract_id AND (dept IS NULL OR c.department_id=dept))
    OR (dept IS NOT NULL AND e.new_department_id IS DISTINCT FROM dept)
 FROM public.sync_events e WHERE e.seq>after_seq AND (dept IS NULL OR e.old_department_id=dept OR e.new_department_id=dept)
 ORDER BY e.seq LIMIT page_size;
END $$;
REVOKE ALL ON FUNCTION ohvr_security.sync_events_page(integer,integer) FROM PUBLIC;

CREATE FUNCTION ohvr_security.sync_owner_change() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $$ BEGIN
 PERFORM 1 FROM public.sync_state WHERE id=1 FOR UPDATE;
 IF TG_TABLE_NAME='users' THEN
  UPDATE public.integration_tokens SET grant_version=grant_version+1 WHERE owner_user_id=NEW.id;
 ELSE
  UPDATE public.integration_tokens SET grant_version=grant_version+1 WHERE department_id=NEW.id
   OR owner_user_id IN (SELECT id FROM public.users WHERE department_id=NEW.id);
 END IF;RETURN NULL;
END $$;
CREATE TRIGGER sync_owner_change AFTER UPDATE OF is_active,role,department_id ON public.users FOR EACH ROW EXECUTE FUNCTION ohvr_security.sync_owner_change();
CREATE TRIGGER sync_department_change AFTER UPDATE OF is_active ON public.departments FOR EACH ROW EXECUTE FUNCTION ohvr_security.sync_owner_change();
REVOKE ALL ON FUNCTION ohvr_security.sync_owner_change() FROM PUBLIC;
