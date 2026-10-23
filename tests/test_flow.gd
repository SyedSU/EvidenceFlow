extends SceneTree
var failures=0
func check(condition: bool, label: String):
 if not condition: failures+=1;push_error("FAIL: "+label)
 else: print("PASS: "+label)
func _initialize():
 call_deferred("run")
func run():
 var script=load("res://scripts/workflow.gd")
 check(script!=null,"workflow implementation exists")
 if script==null:quit(1);return
 var flow=script.new()
 var graph=flow.example()
 check(flow.validate(graph).is_empty(),"default read/extract/translate/report DAG valid")
 for identity in ["bad/name", "bad.name", "bad:name", "GraphEdit", "_connection_layer"]:
  var unsafe=graph.duplicate(true);unsafe.nodes[0].id=identity;unsafe.edges[0][0]=identity
  check(not flow.validate(unsafe).is_empty(),"unsafe visual node identity refused: "+identity)
 var cyclic=graph.duplicate(true);cyclic.edges.append(["report","read"])
 check(not flow.validate(cyclic).is_empty(),"cycle refused")
 var unknown=graph.duplicate(true);unknown.nodes[1].kind="shell"
 check(not flow.validate(unknown).is_empty(),"untrusted action kind refused")
 var dangling=graph.duplicate(true);dangling.edges.append(["missing","report"])
 check(not flow.validate(dangling).is_empty(),"dangling connection refused")
 var join=graph.duplicate(true);join.edges.append(["read","report"])
 check(not flow.validate(join).is_empty(),"ambiguous multiple inputs refused")
 check(flow.document("bad.pdf","hello".to_utf8_buffer()).has("error"),"unsupported document refused")
 check(flow.document("x.txt",PackedByteArray([0xff])).has("error"),"malformed UTF8 refused")
 check(flow.document("x.md",("x".repeat(65537)).to_utf8_buffer()).has("error"),"oversized input refused")
 check(flow.document("x.md","Café\nresult".to_utf8_buffer()).text=="Café\nresult","Unicode markdown retained")
 for url in ["https://example.com/v1/chat/completions","http://localhost.evil:8080/v1/chat/completions","http://127.0.0.1:8080@evil/v1/chat/completions","http://192.168.1.3:8080/v1/chat/completions"]:
  check(not flow.valid_endpoint(url),"remote endpoint refused "+url)
 check(flow.valid_endpoint("http://127.0.0.1:8080/v1/chat/completions"),"literal loopback endpoint allowed")
 check(not flow.valid_endpoint("http://localhost:8080/v1/chat/completions"),"DNS endpoint refused")
 check(flow.template("extract","one\ntwo","two")=="two","template extracts matching lines")
 check(flow.template("translate","bonjour","English").begins_with("[Template mode"),"template translation explicitly non-AI")
 check(flow.template("report","facts","").contains("facts"),"report contains inspected input")
 await persistence(script)
 quit(1 if failures else 0)
func persistence(script):
 var path="user://flow-test-"+str(Time.get_ticks_usec())+".json"
 var a=script.new();a.path=path
 check(a.open_workspace().is_empty(),"new workspace starts safely")
 a.state.document="first"
 check(a.save_workspace().is_empty(),"native durable first save")
 var b=script.new();b.path=path
 check(b.open_workspace().is_empty() and b.state.document=="first","saved state reopens")
 a.state.document="second";check(a.save_workspace().is_empty(),"second save creates previous generation")
 b.state.document="stale";check(not b.save_workspace().is_empty(),"stale writer refused")
 check(b.open_workspace().is_empty() and b.state.document=="second","reload recovers latest state")
 var exported=path+".md"
 b.state.outputs={"report":{"text":"Approved report","mode":"template"}}
 check(b.export_report(exported).is_empty(),"explicit report export")
 check(FileAccess.get_file_as_string(exported).contains("Template mode") and FileAccess.get_file_as_string(exported).contains("Approved report"),"export records mode and report")
 check(not b.export_report(exported).is_empty(),"export refuses existing files")
 var file=FileAccess.open(path,FileAccess.WRITE);file.store_string("broken");file.close()
 check(not b.open_workspace().is_empty(),"corruption reported")
 check(FileAccess.get_file_as_string(path)=="broken","corrupt original preserved")
 check(not b.save_workspace().is_empty(),"corrupt workspace never overwritten")
 var recovered=script.new();recovered.path=path+".backup"
 check(recovered.open_workspace().is_empty() and recovered.state.document=="first","previous generation opens separately")
 for suffix in ["",".backup",".lock",".backup.lock",".md"]:
  DirAccess.remove_absolute(ProjectSettings.globalize_path(path+suffix))
 var directory=DirAccess.open("user://")
 for name in directory.get_files():
  if name.begins_with(path.get_file()+".corrupt-"):DirAccess.remove_absolute(ProjectSettings.globalize_path("user://"+name))
