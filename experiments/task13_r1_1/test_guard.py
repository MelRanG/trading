from pathlib import Path
import hashlib,pytest
from guard import admit,enforce,bound_feedback

def test_fail_closed_essential_contract():
 r=admit('x',['weighted_mean','controls'],{'weighted_mean':True},{})
 with pytest.raises(ValueError,match='QUALITY_GATE_REJECTED'):enforce(r)
 assert r['missing_essential_components']==['controls']

def test_all_pool_not_only_parent():
 r=admit('child',['mechanism'],{'mechanism':True},{'parent':.02,'other_prior':.96})
 assert r['pool_duplicates'][0]['candidate']=='other_prior'
 with pytest.raises(ValueError):enforce(r)

def test_feedback_current_status_and_wrong_binding(tmp_path):
 p=tmp_path/'code.py';p.write_text('original')
 m={'candidate':'Q1','code_hash':hashlib.sha256(p.read_bytes()).hexdigest(),'H':20}
 r=bound_feedback('Q1',p,m,'This factor has not been evaluated.')
 assert r['status']=='EVALUATED' and r['description_at_generation'].endswith('evaluated.')
 assert 'has not been evaluated' not in r['task_description_for_feedback']
 assert 'CURRENT STATUS: EVALUATED candidate=Q1' in r['task_description_for_feedback']
 with pytest.raises(ValueError):bound_feedback('Q0',p,m,'')
 p.write_text('changed')
 with pytest.raises(ValueError):bound_feedback('Q1',p,m,'')
