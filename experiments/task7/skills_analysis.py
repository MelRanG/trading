from pathlib import Path
import json,http.client,socket
ROOT=Path(__file__).resolve().parents[2];b=ROOT/'runtime/task7';packet=json.loads((b/'company/packet.json').read_text());common=(b/'company/common_instruction.txt').read_text();skills='\n\n'.join((b/'skills'/n).read_text() for n in ['investor-harness.md','financial-services.md','equity-research-skill.md'])
class Conn(http.client.HTTPConnection):
 def connect(self):self.sock=socket.socket(socket.AF_UNIX);self.sock.settimeout(210);self.sock.connect('/tmp/quant-task7.sock')
for case in packet['cases']:
 out=b/'comparison/skills'/case['ticker'];out.mkdir(parents=True,exist_ok=True)
 if (out/'analysis.json').exists():continue
 body={'model':'gpt-4o','messages':[{'role':'system','content':'Use only the catalyst/causal, earnings-scenario and expectation/reverse-DCF reasoning from these original pinned investment skill instructions. User explicitly requests a bounded source-only A/B, not full skill deployment/PDF/report workflow. No iFind, paid tools or unprovided data. Do not fabricate missing source/consensus; obey common JSON output and uncertainty contract. Original instructions:\n'+skills},{'role':'user','content':common+json.dumps(case,ensure_ascii=False)}],'response_format':{'type':'json_object'}}
 (out/'request.json').write_text(json.dumps(body,indent=2,ensure_ascii=False));c=Conn('localhost');c.request('POST','/v1/chat/completions',json.dumps(body),{'Authorization':'Bearer task6-skills','Content-Type':'application/json'});r=c.getresponse();data=r.read();(out/'response.json').write_bytes(data)
 if r.status!=200:raise RuntimeError(data.decode())
 text=json.loads(data)['choices'][0]['message']['content'];parsed,_=json.JSONDecoder().raw_decode(text[text.find('{'):]);(out/'analysis.json').write_text(json.dumps(parsed,indent=2,ensure_ascii=False));print(case['ticker'],'DONE',flush=True)
