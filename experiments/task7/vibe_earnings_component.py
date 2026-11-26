"""Original Vibe earnings skill/provider, shared frozen-source data adapter.
This is distinct from the CLI grounding/fallback experiment, not its replacement.
"""
from pathlib import Path
import json
from src.providers.chat import ChatLLM
packet=json.loads(Path('/work/company_packet.json').read_text());skill=Path('/venv/lib/python3.12/site-packages/src/skills/earnings-forecast/SKILL.md').read_text();common=Path('/work/common_instruction.txt').read_text()
llm=ChatLLM();response=llm.chat([{'role':'system','content':'You are the original Vibe earnings research worker applying the bundled earnings-forecast skill to a frozen-source adapter. Do not call unavailable external tools; source contents are already provided and all derived estimates must be labelled assumptions. Use only relevant reasoning from the skill and return the common JSON contract. Original skill:\n'+skill},{'role':'user','content':common+'\nAnalyze BOTH cases and return {"cases":[caseNVDA,caseCRWV]}:\n'+json.dumps(packet['cases'],ensure_ascii=False)}]);text=response.content
Path('/work/earnings_component.raw.txt').write_text(text);r,_=json.JSONDecoder().raw_decode(text[text.find('{'):]);Path('/work/earnings_component.json').write_text(json.dumps(r,indent=2,ensure_ascii=False));llm.close();print('ORIGINAL_EARNINGS_COMPONENT_DONE')
