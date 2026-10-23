extends SceneTree
var failures=0
func check(value: bool,label: String):
 if value:print("PASS: "+label)
 else:failures+=1;push_error("FAIL: "+label)
func _initialize():call_deferred("run")
func run():
 var model=load("res://scripts/workflow.gd").new()
 model.path="user://runner-"+str(Time.get_ticks_usec())+".json";model.open_workspace();model.state.document="red\nblue";model.state.graph.nodes[1].option="blue"
 var code=load("res://scripts/runner.gd")
 check(code!=null,"runner implementation exists")
 if code==null:quit(1);return
 var runner=code.new();root.add_child(runner)
 var message=await runner.execute(model)
 check(message.is_empty() and model.state.run_status=="complete","template DAG completes")
 check(model.state.outputs.extract.text=="blue" and model.state.outputs.report.text.contains("blue"),"connected intermediate results retained")
 check(model.state.outputs.translate.mode=="template" and model.state.outputs.translate.text.contains("translation unavailable"),"translation fallback honest")
 model.state.mode="local";model.state.endpoint="http://127.0.0.1:1/v1/chat/completions"
 message=await runner.execute(model)
 check(not message.is_empty() and model.state.run_status=="failed","unavailable local model fails visibly")
 check(not model.state.outputs.has("extract"),"model failure never produces template AI result")
 model.state.mode="template"
 runner.call_deferred("cancel")
 message=await runner.execute(model)
 check(model.state.run_status=="cancelled" and not message.is_empty(),"cancellation persists explicit state")
 model.state.run_status="running";check(model.save_workspace().is_empty(),"running checkpoint durable")
 var interrupted=load("res://scripts/workflow.gd").new();interrupted.path=model.path
 check(interrupted.open_workspace().is_empty() and interrupted.state.run_status=="interrupted","interrupted run never auto resumes")
 model.state.run_status="cancelled";model.save_workspace()
 var recovered=load("res://scripts/workflow.gd").new();recovered.path=model.path
 check(recovered.open_workspace().is_empty() and recovered.state.run_status=="cancelled","cancelled run reopens without auto retry")
 for suffix in ["",".backup",".lock"]:DirAccess.remove_absolute(ProjectSettings.globalize_path(model.path+suffix))
 runner.queue_free();await process_frame
 quit(1 if failures else 0)
