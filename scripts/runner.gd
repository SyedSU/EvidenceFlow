extends Node
signal changed
var busy=false
var cancelled=false
var http: HTTPRequest
func cancel():
 if busy:
  cancelled=true
  if is_instance_valid(http):http.cancel_request()
func finish(model, status: String, message: String) -> String:
 model.state.run_status=status
 var saved=model.save_workspace()
 busy=false;changed.emit()
 return message+(" Save failed: "+saved if not saved.is_empty() else "")
func execute(model) -> String:
 if busy:return "A workflow is already running."
 var invalid=model.validate(model.state.graph)
 if not invalid.is_empty():return invalid
 if model.state.document.is_empty():return "Import a document first."
 if model.state.mode=="local" and not model.valid_endpoint(model.state.endpoint):return "Use a literal 127.0.0.1 HTTP endpoint; remote inference is disabled."
 busy=true;cancelled=false
 model.state.outputs={};model.state.run_status="running"
 var saved=model.save_workspace()
 if not saved.is_empty():busy=false;return "Run not started: "+saved
 changed.emit()
 for id in model.order(model.state.graph):
  await get_tree().process_frame
  if cancelled:return finish(model,"cancelled","Run cancelled. Completed intermediate outputs are retained; restart explicitly.")
  var node={}
  for candidate in model.state.graph.nodes:
   if candidate.id==id:node=candidate
  var text=model.state.document
  for edge in model.state.graph.edges:
   if edge[1]==id:text=model.state.outputs[edge[0]].text
  var output=text
  if node.kind!="read":
   if model.state.mode=="template":output=model.template(node.kind,text,node.option)
   else:
    var answer=await infer(model,node.kind,text,node.option)
    if cancelled:return finish(model,"cancelled","Run cancelled; no response was adopted.")
    if answer.has("error"):return finish(model,"failed",answer.error)
    output=answer.text
  if output.to_utf8_buffer().size()>model.MAX_TEXT:return finish(model,"failed","Step output exceeds the 65,536-byte limit.")
  model.state.outputs[id]={"text":output,"mode":model.state.mode}
  saved=model.save_workspace();changed.emit()
  if not saved.is_empty():return finish(model,"failed","Intermediate save failed: "+saved)
 return finish(model,"complete","")
func infer(model,kind: String,text: String,option: String) -> Dictionary:
 http=HTTPRequest.new();add_child(http)
 http.timeout=120;http.body_size_limit=262144;http.max_redirects=0
 var completed=[]
 http.request_completed.connect(func(result,code,headers,body):completed.append([result,code,headers,body]))
 var body=JSON.stringify({"model":model.state.model,"messages":model.prompt(kind,text,option),"temperature":0.2,"max_tokens":2048,"stream":false})
 var error=http.request(model.state.endpoint,["Content-Type: application/json"],HTTPClient.METHOD_POST,body)
 if error!=OK:http.queue_free();return {"error":"Local inference request could not start. Check the local llama-server."}
 while completed.is_empty() and not cancelled:await get_tree().process_frame
 if cancelled:http.cancel_request();http.queue_free();return {"error":"Cancelled."}
 var response=completed[0];http.queue_free()
 if response[0]!=HTTPRequest.RESULT_SUCCESS or response[1]!=200:return {"error":"Local inference failed (transport "+str(response[0])+", HTTP "+str(response[1])+"). Check your local server/model. Template mode was not substituted."}
 if not model.files.valid_utf8(response[3]):return {"error":"Local server returned malformed UTF-8."}
 var parser=JSON.new()
 if parser.parse(response[3].get_string_from_utf8())!=OK:return {"error":"Local server returned malformed JSON."}
 var parsed=parser.data
 if not parsed is Dictionary or not parsed.get("choices") is Array or parsed.choices.is_empty():return {"error":"Local server returned an unsupported response."}
 var choice=parsed.choices[0]
 if not choice is Dictionary or not choice.get("message") is Dictionary or not choice.message.get("content") is String:return {"error":"Local server response has no text content."}
 var result=choice.message.content
 if result.is_empty() or result.to_utf8_buffer().size()>model.MAX_TEXT:return {"error":"Local server output is empty or oversized."}
 return {"text":result}
