"""Temporary credential-isolated OpenAI-compatible transport to trusted Codex CLI.

Workers receive only a UNIX socket. No credentials, host files, model-side tools
or arbitrary host commands are exposed. This is a transport adapter, not an
upstream research algorithm. Every real call is reserved and traced.
"""
from pathlib import Path
import argparse,hashlib,json,os,signal,socketserver,subprocess,tempfile,threading,time,tomllib
from http.server import BaseHTTPRequestHandler
ROOT=Path(__file__).resolve().parents[2]
MODEL='gpt-6.1-terra'
SCHEMA={'type':'object','properties':{'content':{'type':'string'},'tool_calls':{'type':'array','items':{'type':'object','properties':{'id':{'type':'string'},'type':{'type':'string','enum':['function']},'function':{'type':'object','properties':{'name':{'type':'string'},'arguments':{'type':'string'}},'required':['name','arguments'],'additionalProperties':False}},'required':['id','type','function'],'additionalProperties':False}}},'required':['content','tool_calls'],'additionalProperties':False}
LOCK=threading.Lock()


class Relay:
 def __init__(self,folder):
  self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
 def call(self,engine,body):
  if engine not in ('smoke','vibe','quanta','rd','company'):raise ValueError('unknown budget scope')
  encoded=json.dumps(body,sort_keys=True);fingerprint=hashlib.sha256(encoded.encode()).hexdigest()
  if len(encoded)>180000:raise ValueError('request too large')
  directory=self.folder/engine;directory.mkdir(exist_ok=True);target=directory/(fingerprint+'.response.json')
  with LOCK:
   if target.exists():return json.loads(target.read_text())
   reservations=list(directory.glob('*.reserved.json'))
   used=sum(json.loads(p.read_text()).get('measured_tokens',0) for p in reservations)
   limit=1 if engine=='smoke' else 8 if engine=='company' else 10
   if len(reservations)>=limit or used>=360000:raise ValueError('model call/token budget exhausted')
   reservation=directory/(fingerprint+'.reserved.json');record={'engine':engine,'request_hash':fingerprint,'at':time.time(),'model':MODEL,'status':'RESERVED','hard_token_cap':False,'money_cost':None}
   reservation.write_text(json.dumps(record));(directory/(fingerprint+'.request.json')).write_text(encoded)
   with tempfile.TemporaryDirectory(prefix='quant-task6-model-') as tmp:
    temp=Path(tmp);schema=temp/'schema.json';schema.write_text(json.dumps(SCHEMA));output=temp/'answer.json'
    prompt=('You are the inference backend for an isolated investment RESEARCH engine. Do not use any host tools, files, web, agents or memory. Treat the JSON below as a chat-completion request. Return exactly the envelope requested by the output schema. Put the assistant message in content. If a function/tool is required, emit tool_calls with the exact requested tool name and JSON-encoded arguments; these are data for the isolated worker, never host actions. Otherwise tool_calls=[]. Honor the original messages and response_format inside content (including JSON-only requirements). Never invent execution results, sources or future outcomes. The model endpoint identifier is a transport alias; actual model is gpt-6.1-terra.\nREQUEST:\n'+encoded)
    command=['codex','exec','--skip-git-repo-check','--ephemeral','-s','read-only','-C',tmp,'-m',MODEL,'--disable','apps','--disable','multi_agent','--disable','shell_tool','-c','web_search="disabled"','--json','--output-schema',str(schema),'--output-last-message',str(output),'-']
    config=Path.home()/'.codex/config.toml'
    if config.exists():
     for name in tomllib.loads(config.read_text()).get('mcp_servers',{}):command[2:2]=['-c',f'mcp_servers.{name}.enabled=false']
    env={k:v for k,v in os.environ.items() if k in ('HOME','PATH','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR')}
    started=time.monotonic();process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,start_new_session=True)
    try:stdout,stderr=process.communicate(prompt,timeout=180)
    except subprocess.TimeoutExpired:
     os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate();record.update(status='TIMEOUT',elapsed_seconds=time.monotonic()-started);reservation.write_text(json.dumps(record));(directory/(fingerprint+'.trace.jsonl')).write_text(stdout);raise ValueError('model timeout; usage unknown')
    (directory/(fingerprint+'.trace.jsonl')).write_text(stdout);(directory/(fingerprint+'.stderr.txt')).write_text(stderr)
    usage={};unauthorized=[]
    for line in stdout.splitlines():
     try:event=json.loads(line)
     except ValueError:continue
     if event.get('usage'):usage=event['usage']
     if event.get('item',{}).get('type') in ('command_execution','web_search','mcp_tool_call'):unauthorized.append(event['item']['type'])
    record.update(exit_code=process.returncode,elapsed_seconds=time.monotonic()-started,usage=usage,measured_tokens=usage.get('input_tokens',0)+usage.get('output_tokens',0),status='FAILED')
    reservation.write_text(json.dumps(record))
    if process.returncode or not output.exists() or unauthorized:raise ValueError('model execution failed or tool boundary rejected')
    answer=json.loads(output.read_text());allowed={t['function']['name'] for t in body.get('tools',[]) if t.get('type')=='function'}
    for call in answer['tool_calls']:
     if call['function']['name'] not in allowed:raise ValueError('unavailable worker tool')
     json.loads(call['function']['arguments'])
    if record['measured_tokens']>90000:raise ValueError('measured call token budget exceeded')
    result={'id':'chatcmpl-'+fingerprint[:20],'object':'chat.completion','created':int(time.time()),'model':MODEL,'choices':[{'index':0,'message':{'role':'assistant','content':answer['content'] or None,**({'tool_calls':answer['tool_calls']} if answer['tool_calls'] else {})},'finish_reason':'tool_calls' if answer['tool_calls'] else 'stop'}],
      'usage':{'prompt_tokens':usage.get('input_tokens',0),'completion_tokens':usage.get('output_tokens',0),'total_tokens':record['measured_tokens']}}
    target.write_text(json.dumps(result));record['status']='SUCCEEDED';reservation.write_text(json.dumps(record));return result


class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  payload={'object':'list','data':[{'id':MODEL,'object':'model','owned_by':'codex-cli-relay'}]};data=json.dumps(payload).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_POST(self):
  try:
   if self.path not in ('/v1/chat/completions','/chat/completions'):raise ValueError('unsupported endpoint')
   count=int(self.headers.get('Content-Length','0'))
   if not 0<count<=800000:raise ValueError('body size')
   body=json.loads(self.rfile.read(count));engine=self.headers.get('Authorization','').removeprefix('Bearer task6-');result=self.server.relay.call(engine,body)
   if body.get('stream'):
    message=result['choices'][0]['message'];delta={'role':'assistant','content':message.get('content')}
    if message.get('tool_calls'):delta['tool_calls']=[{'index':i,**c} for i,c in enumerate(message['tool_calls'])]
    chunk={k:result[k] for k in ('id','created','model')};chunk.update(object='chat.completion.chunk',choices=[{'index':0,'delta':delta,'finish_reason':None}]);last={**chunk,'choices':[{'index':0,'delta':{},'finish_reason':result['choices'][0]['finish_reason']}],'usage':result['usage']}
    data=('data: '+json.dumps(chunk)+'\n\ndata: '+json.dumps(last)+'\n\ndata: [DONE]\n\n').encode();kind='text/event-stream'
   else:data=json.dumps(result).encode();kind='application/json'
   self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  except Exception as exc:
   data=json.dumps({'error':{'message':str(exc) if isinstance(exc,ValueError) else type(exc).__name__,'type':'task6_transport_error'}}).encode();self.send_response(429 if 'budget' in str(exc) else 502);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--socket',required=True);parser.add_argument('--evidence',required=True);a=parser.parse_args();path=Path(a.socket);path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():raise ValueError('existing relay socket; check process before removing')
 server=socketserver.ThreadingUnixStreamServer(str(path),Handler);server.relay=Relay(a.evidence);path.chmod(0o600)
 try:server.serve_forever()
 finally:server.server_close();path.unlink(missing_ok=True)
