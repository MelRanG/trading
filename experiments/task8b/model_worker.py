"""Pinned original Vibe inference component; input/output only, no worker tools."""
from pathlib import Path
import json,sys
from src.providers.chat import ChatLLM
stage=sys.argv[1];w=Path('/work');request=json.loads((w/(stage+'.request.json')).read_text());raw=ChatLLM().chat(request['messages']).content;(w/(stage+'.raw.txt')).write_text(raw);parsed=json.loads(raw);(w/(stage+'.json')).write_text(json.dumps(parsed,indent=2,ensure_ascii=False));print('ORIGINAL_VIBE_COMPONENT_DONE',stage)
