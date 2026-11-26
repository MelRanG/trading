"""Original specialist components with a shared frozen-source transport adapter.
No market API, broker, subprocess code execution or production credentials.
"""
from pathlib import Path
import json,sys,hashlib,copy
from types import SimpleNamespace
engine=sys.argv[1];root=Path('/work');packet=json.loads((root/'packet.json').read_text());instruction=(root/'common_instruction.txt').read_text()
for case in packet['cases']:
 symbol=case['ticker'];out=root/symbol;out.mkdir(exist_ok=True)
 if (out/'analysis.json').exists():continue
 query=instruction+json.dumps(case,ensure_ascii=False)
 if engine=='tradingagents':
  from langchain_openai import ChatOpenAI
  from tradingagents.agents.researchers.bull_researcher import create_bull_researcher
  from tradingagents.agents.researchers.bear_researcher import create_bear_researcher
  llm=ChatOpenAI(model='gpt-4o',base_url='http://127.0.0.1:18080/v1',api_key='task6-tradingagents',temperature=0,max_retries=0)
  state={'company_of_interest':symbol,'asset_type':'stock','instrument_context':case['company']+' ('+symbol+') source-only research, no orders','market_report':'No separate market analysis; see supplied source packet and frozen close.','sentiment_report':'NOT_AVAILABLE','news_report':'No additional external news; official issuer packet only.','fundamentals_report':query,'investment_debate_state':{'history':'','bull_history':'','bear_history':'','current_response':'','count':0}}
  bull=create_bull_researcher(llm)(copy.deepcopy(state));bear=create_bear_researcher(llm)(copy.deepcopy(state));(out/'native_bull.json').write_text(json.dumps(bull,indent=2));(out/'native_bear.json').write_text(json.dumps(bear,indent=2))
  # Same output contract as other arms; no other arm's results supplied.
  final=llm.invoke(query+'\nIndependently generated ORIGINAL bull and bear nodes below. Synthesize them into the requested JSON.\n'+json.dumps({'bull':bull,'bear':bear}));text=final.content
 elif engine=='finrobot':
  from finrobot.agents.workflow import FinRobot
  agent=FinRobot('Expert_Investor',llm_config={'config_list':[{'model':'gpt-4o','api_key':'task6-finrobot','base_url':'http://127.0.0.1:18080/v1'}],'cache_seed':None,'temperature':0,'timeout':210},human_input_mode='NEVER',code_execution_config=False)
  final=agent.generate_reply(messages=[{'role':'user','content':query}]);text=final.get('content','') if isinstance(final,dict) else str(final)
 else:raise ValueError('unknown engine')
 (out/'raw_response.txt').write_text(text);start=text.find('{');parsed,_=json.JSONDecoder().raw_decode(text[start:]);(out/'analysis.json').write_text(json.dumps(parsed,indent=2,ensure_ascii=False));(out/'receipt.json').write_text(json.dumps({'engine':engine,'case':symbol,'input_sha256':hashlib.sha256(query.encode()).hexdigest(),'native_scope':'Original bull/bear factories + common schema synthesis' if engine=='tradingagents' else 'Original FinRobot Expert_Investor wrapper + AutoGen inference; external toolkits unregistered','network':'none except task-only model relay','actual_model':'gpt-6.1-terra','orders':False},indent=2));print(engine,symbol,'DONE',flush=True)
