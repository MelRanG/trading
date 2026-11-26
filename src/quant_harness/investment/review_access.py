"""Restricted project-memory view shared by proposal/Hermes workers."""
import psycopg
from .review import proposal_context


class ProposalView:
    def __init__(self,store):self._store=store

    def process_context(self,identity):
        with psycopg.connect(self._store.url) as conn:
            row=conn.execute('SELECT kind FROM investment_record WHERE record_id=%s',(identity,)).fetchone()
        if not row or row[0]!='review_process':raise PermissionError('proposal worker can only read sealed process reviews')
        return proposal_context(self._store.get(identity))

    def final_results(self,*args,**kwargs):
        raise PermissionError('final evaluation/holdout access is denied to proposal and memory workers')
