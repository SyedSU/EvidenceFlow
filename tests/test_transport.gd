# Synthetic HTTP protocol fixture, NOT a model or inference acceptance.
extends SceneTree
class Fixture:
 extends Node
 var server=TCPServer.new()
 var peer: StreamPeerTCP
 var received=PackedByteArray()
 var requests=[]
 var response=""
 var code="200 OK"
 var port=0
 func start() -> bool:
  for candidate in range(18880,18980):
   if server.listen(candidate,"127.0.0.1")==OK:port=candidate;return true
  return false
 func _process(_delta):
  if peer==null and server.is_connection_available():peer=server.take_connection();received=PackedByteArray()
  if peer==null:return
  peer.poll()
  var available=peer.get_available_bytes()
  if available>0:received.append_array(peer.get_data(available)[1])
  var text=received.get_string_from_utf8();var split=text.find("\r\n\r\n")
  if split<0:return
  var length=0
  for line in text.substr(0,split).split("\r\n"):
   if line.to_lower().begins_with("content-length:"):length=int(line.split(":",true,1)[1].strip_edges())
  if received.size()<split+4+length:return
  requests.append(JSON.parse_string(text.substr(split+4)))
  var body=response.to_utf8_buffer()
  peer.put_data(("HTTP/1.1 "+code+"\r\nConnection: close\r\nLocation: http://192.0.2.1/forbidden\r\nContent-Type: application/json\r\nContent-Length: "+str(body.size())+"\r\n\r\n").to_utf8_buffer()+body)
  peer.disconnect_from_host();peer=null
 func _exit_tree():server.stop()
var failures=0
func check(ok: bool,label: String):
 if ok:print("PASS: "+label)
 else:failures+=1;push_error("FAIL: "+label)
func _initialize():call_deferred("run")
func run():
 var fixture=Fixture.new();root.add_child(fixture)
 check(fixture.start(),"synthetic loopback server starts")
 var flow=load("res://scripts/workflow.gd").new();flow.state.endpoint="http://127.0.0.1:"+str(fixture.port)+"/v1/chat/completions"
 var runner=load("res://scripts/runner.gd").new();root.add_child(runner)
 fixture.response=JSON.stringify({"choices":[{"message":{"content":"SYNTHETIC protocol fixture"}}]})
 var answer=await runner.infer(flow,"translate","Café untrusted document","English")
 check(answer.get("text")=="SYNTHETIC protocol fixture","OpenAI-compatible protocol decoded (synthetic)")
 check(fixture.requests.size()==1 and fixture.requests[0].messages[1].content.contains("Café"),"UTF8 document sent as user data")
 check(fixture.requests[0].messages[0].content.contains("untrusted data") and fixture.requests[0].stream==false,"bounded nonstreaming instruction/data contract")
 fixture.response="not json"
 answer=await runner.infer(flow,"extract","x","")
 check(answer.has("error"),"malformed HTTP response refused")
 fixture.response=JSON.stringify({"choices":[{"message":{"content":123}}]})
 answer=await runner.infer(flow,"report","x","")
 check(answer.has("error"),"nontext response refused")
 fixture.code="302 Found";fixture.response=""
 answer=await runner.infer(flow,"report","x","")
 check(answer.has("error"),"redirect refused without following remote Location")
 fixture.queue_free();runner.queue_free();await process_frame
 quit(1 if failures else 0)
