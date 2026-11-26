"""Container-local HTTP forwarder to the task-only host UNIX model relay."""
import http.client,socket
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Connection(http.client.HTTPConnection):
 def connect(self):self.sock=socket.socket(socket.AF_UNIX);self.sock.settimeout(210);self.sock.connect('/relay/model.sock')
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def request(self):
  body=self.rfile.read(int(self.headers.get('Content-Length','0')));conn=Connection('localhost',timeout=210);conn.request(self.command,self.path,body,{k:v for k,v in self.headers.items() if k.lower() not in ('host','connection')});r=conn.getresponse();data=r.read();self.send_response(r.status)
  for k,v in r.getheaders():
   if k.lower() not in ('transfer-encoding','connection','content-length','server','date'):self.send_header(k,v)
  self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);conn.close()
 do_GET=request
 do_POST=request
ThreadingHTTPServer(('127.0.0.1',18080),Handler).serve_forever()
