extends SceneTree
var failures=0
func check(ok: bool,label: String):
 if ok:print("PASS: "+label)
 else:failures+=1;push_error("FAIL: "+label)
func _initialize():call_deferred("run")
func run():
 var scene=load("res://main.tscn")
 check(scene!=null,"native main scene exists")
 if scene==null:quit(1);return
 var app=scene.instantiate();app.test_path="user://ui-test-"+str(Time.get_ticks_usec())+".json";root.add_child(app)
 await process_frame;await process_frame
 check(app.graph.get_connection_list().size()==3,"visual DAG connections displayed")
 check(app.graph.get_child_count()>=4,"native step nodes displayed")
 var sample=app.test_path+".txt";var file=FileAccess.open(sample,FileAccess.WRITE);file.store_string("blue\nred");file.close()
 app.import_path(sample)
 check(app.flow.state.document=="blue\nred","UI imports real bounded document")
 await app.run_workflow()
 check(app.flow.state.run_status=="complete" and app.flow.state.outputs.has("report"),"UI executes complete workflow")
 app.save_workspace()
 var saved_document=app.flow.state.document
 app.flow.state.document="unsaved edit";app.reopen()
 check(app.flow.state.document==saved_document and app.flow.state.outputs.has("report"),"UI save and reopen retain completed workflow")
 var exported=app.test_path+".md"
 check(app.flow.export_report(exported).is_empty() and FileAccess.get_file_as_string(exported).contains("blue"),"UI workflow report exports real inspected document")
 var rejected=app.test_path+".pdf";file=FileAccess.open(rejected,FileAccess.WRITE);file.store_string("unsupported");file.close()
 app.import_path(rejected)
 check(app.flow.state.document==saved_document and app.flow.state.outputs.has("report"),"failed UI import preserves document and inspected outputs")
 app.show_step("report")
 check(app.output.text.contains("# Report"),"UI shows inspectable report")
 app.option.text="red";app.show_step("extract");app.option.text="red";app.apply_option()
 check(app.flow.state.graph.nodes[1].option=="red" and app.flow.state.outputs.is_empty(),"editing option invalidates previous outputs")
 app.mode.select(1);app.mode_changed(1)
 check(app.flow.state.mode=="local","UI explicitly selects real local inference")
 app.mode.select(0);app.mode_changed(0)
 app.graph_disconnect("extract",0,"translate",0)
 check(not app.flow.validate(app.flow.state.graph).is_empty(),"visual disconnect changes model")
 app.graph_connect("extract",0,"translate",0)
 check(app.flow.validate(app.flow.state.graph).is_empty(),"visual reconnect restores valid workflow")
 root.size=Vector2i(390,720);await process_frame;await process_frame
 check(app.get_node("Layout").size.x<=390 and app.graph.size.x<=366,"root and graph adapt to narrow viewport")
 check(app.run_button.focus_mode==Control.FOCUS_ALL,"run reachable by keyboard")
 for suffix in ["",".backup",".lock",".txt",".md",".md.lock",".pdf"]:DirAccess.remove_absolute(ProjectSettings.globalize_path(app.test_path+suffix))
 app.queue_free();await process_frame
 quit(1 if failures else 0)
