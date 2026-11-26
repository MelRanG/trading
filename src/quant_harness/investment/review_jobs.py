"""Restart-safe research queue in a dedicated review DB, not the trade ledger."""
import json
from datetime import datetime,timezone,timedelta
import psycopg
from psycopg.rows import dict_row
from .research import digest

DDL='''
CREATE TABLE IF NOT EXISTS review_job (
 job_id text PRIMARY KEY,kind text NOT NULL,payload jsonb NOT NULL,status text NOT NULL,
 owner text,lease_until timestamptz,attempts integer NOT NULL DEFAULT 0,result_id text,
 next_observation_at timestamptz,last_error text,updated_at timestamptz NOT NULL DEFAULT now());
'''


class Queue:
    def __init__(self,store):
        self.store=store
        with psycopg.connect(store.url) as conn:conn.execute(DDL)

    def enqueue(self,kind,payload,next_observation_at=None):
        identity=digest({'kind':kind,'payload':payload})
        with psycopg.connect(self.store.url) as conn:
            conn.execute("INSERT INTO review_job(job_id,kind,payload,status,next_observation_at) VALUES (%s,%s,%s::jsonb,'READY',%s) ON CONFLICT DO NOTHING",(identity,kind,json.dumps(payload),next_observation_at))
        return identity

    def claim(self,owner,lease_seconds=120,identity=None):
        with psycopg.connect(self.store.url,row_factory=dict_row) as conn:
            conn.execute("UPDATE review_job SET status='FAILED',last_error='LEASE_EXPIRED_RETRY_LIMIT' WHERE status='RUNNING' AND lease_until<now() AND attempts>=3")
            row=conn.execute("""SELECT * FROM review_job WHERE
                (status IN ('READY','RETRY') OR (status='RUNNING' AND lease_until<now()))
                AND attempts<3 AND (next_observation_at IS NULL OR next_observation_at<=now())
                AND (%s::text IS NULL OR job_id=%s) ORDER BY updated_at,job_id FOR UPDATE SKIP LOCKED LIMIT 1""",(identity,identity)).fetchone()
            if not row:return None
            conn.execute("UPDATE review_job SET status='RUNNING',owner=%s,lease_until=now()+(%s*interval '1 second'),attempts=attempts+1,updated_at=now() WHERE job_id=%s",(owner,lease_seconds,row['job_id']))
            return dict(row)

    def finish(self,identity,owner,result_id,status='DONE',next_observation_at=None):
        if status not in ('DONE','PENDING_LABELS','PENDING_EVIDENCE','NO_CHANGE'):raise ValueError('invalid job completion')
        with psycopg.connect(self.store.url) as conn:
            row=conn.execute("UPDATE review_job SET status=%s,result_id=%s,next_observation_at=%s,lease_until=NULL,updated_at=now() WHERE job_id=%s AND owner=%s AND status='RUNNING' AND lease_until>=now() RETURNING job_id",(status,result_id,next_observation_at,identity,owner)).fetchone()
            if not row:raise ValueError('lost research lease')

    def fail(self,identity,owner,error):
        with psycopg.connect(self.store.url) as conn:
            conn.execute("UPDATE review_job SET status=CASE WHEN attempts>=3 THEN 'FAILED' ELSE 'RETRY' END,last_error=%s,lease_until=NULL,updated_at=now() WHERE job_id=%s AND owner=%s AND status='RUNNING'",(error,identity,owner))

    def observe(self,identity,evidence_hash):
        """New labels/events explicitly wake a waiting task once per evidence version."""
        return self.enqueue('FOLLOWUP',{'previous_job':identity,'evidence_hash':evidence_hash})
