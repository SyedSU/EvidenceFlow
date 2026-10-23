extends Control
const Workflow=preload("res://scripts/workflow.gd")
const Runner=preload("res://scripts/runner.gd")
var flow=Workflow.new()
var runner=Runner.new()
var test_path=""
var graph: GraphEdit
var output: TextEdit
var option: LineEdit
var endpoint: LineEdit
var model_name: LineEdit
var mode: OptionButton
var status: Label
var source_label: Label
var inspector: Label
var run_button: Button
var steps: OptionButton
var kinds: OptionButton
var from_step: OptionButton
var to_step: OptionButton
var selected="read"
var chooser: FileDialog
var confirm: ConfirmationDialog
var editing_controls=[]
var refreshing=false
func button(text: String, callback: Callable, parent: Node) -> Button:
 var item=Button.new();item.text=text;item.custom_minimum_size.y=44;item.pressed.connect(callback);parent.add_child(item)
 return item
func label(text: String,parent: Node) -> Label:
 var item=Label.new();item.text=text;item.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;parent.add_child(item);return item
func field(hint: String,parent: Node) -> LineEdit:
 var item=LineEdit.new();item.placeholder_text=hint;item.custom_minimum_size.y=44;item.size_flags_horizontal=Control.SIZE_EXPAND_FILL;parent.add_child(item);return item
func row(parent: Node) -> HFlowContainer:
 var item=HFlowContainer.new();parent.add_child(item);return item
func _ready():
 add_child(runner);runner.changed.connect(update_status)
 var margin=MarginContainer.new();margin.name="Layout";add_child(margin);margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 for side in ["left","top","right","bottom"]:margin.add_theme_constant_override("margin_"+side,12)
 var scroll=ScrollContainer.new();scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED;margin.add_child(scroll)
 var content=VBoxContainer.new();content.size_flags_horizontal=Control.SIZE_EXPAND_FILL;content.add_theme_constant_override("separation",10);scroll.add_child(content)
 label("Evidence Flow · Development build",content).add_theme_font_size_override("font_size",24)
 label("Connect document → extraction → translation → report. Inputs are local TXT/MD (maximum 64 KiB). Review outputs before use.",content)
 var toolbar=row(content)
 editing_controls.append(button("Import document…",func():choose("import"),toolbar))
 editing_controls.append(button("Save workspace",save_workspace,toolbar))
 editing_controls.append(button("Reopen saved",request_reopen,toolbar))
 editing_controls.append(button("Open / recover copy…",func():choose("open"),toolbar))
 editing_controls.append(button("Save copy…",func():choose("copy"),toolbar))
 editing_controls.append(button("Export report…",func():choose("export"),toolbar))
 source_label=label("No document loaded.",content)
 mode=OptionButton.new();mode.add_item("Template mode · no AI");mode.add_item("Local AI · requires your loopback server");mode.custom_minimum_size.y=44;mode.item_selected.connect(mode_changed);content.add_child(mode);editing_controls.append(mode)
 label("Local AI endpoint (literal 127.0.0.1 only) / model alias",content)
 endpoint=field("http://127.0.0.1:8080/v1/chat/completions",content);editing_controls.append(endpoint)
 model_name=field("Model alias served locally",content);editing_controls.append(model_name)
 graph=GraphEdit.new();graph.custom_minimum_size=Vector2(0,290);graph.size_flags_horizontal=Control.SIZE_EXPAND_FILL;graph.minimap_enabled=false;graph.right_disconnects=true;content.add_child(graph)
 graph.connection_request.connect(graph_connect);graph.disconnection_request.connect(graph_disconnect)
 var editbar=row(content)
 steps=OptionButton.new();steps.custom_minimum_size.y=44;steps.item_selected.connect(func(index):show_step(steps.get_item_text(index)));editbar.add_child(steps);editing_controls.append(steps)
 kinds=OptionButton.new();kinds.custom_minimum_size.y=44
 for kind in ["read","extract","translate","report"]:kinds.add_item(kind)
 editbar.add_child(kinds);editing_controls.append(kinds)
 editing_controls.append(button("Add step",add_step,editbar));editing_controls.append(button("Remove selected",remove_step,editbar))
 label("Keyboard / touch connections: select source and destination, then Connect or Disconnect. Nodes can also be dragged and ports connected directly.",content)
 var connectionbar=row(content)
 from_step=OptionButton.new();to_step=OptionButton.new()
 for menu in [from_step,to_step]:menu.custom_minimum_size.y=44;connectionbar.add_child(menu);editing_controls.append(menu)
 editing_controls.append(button("Connect",func():graph_connect(from_step.get_item_text(from_step.selected),0,to_step.get_item_text(to_step.selected),0),connectionbar))
 editing_controls.append(button("Disconnect",func():graph_disconnect(from_step.get_item_text(from_step.selected),0,to_step.get_item_text(to_step.selected),0),connectionbar))
 inspector=label("",content)
 option=field("Extraction: matching text / Translation: target language / Report: focus",content);editing_controls.append(option)
 editing_controls.append(button("Apply step option",apply_option,content))
 output=TextEdit.new();output.editable=false;output.custom_minimum_size.y=180;output.wrap_mode=TextEdit.LINE_WRAPPING_BOUNDARY;content.add_child(output)
 var execution=row(content)
 run_button=button("Run workflow",run_workflow,execution)
 button("Cancel run",runner.cancel,execution)
 status=label("",content)
 chooser=FileDialog.new();chooser.access=FileDialog.ACCESS_FILESYSTEM;chooser.use_native_dialog=false;chooser.size=Vector2i(700,500);add_child(chooser)
 confirm=ConfirmationDialog.new();confirm.dialog_text="Reopen the saved workspace and discard edits since the last save?";confirm.confirmed.connect(reopen);add_child(confirm)
 if not test_path.is_empty():flow.path=test_path
 var error=flow.open_workspace();refresh();tell(error if not error.is_empty() else "Ready. Workspace: "+flow.path)
func tell(message: String):
 status.text=message
func invalidate():
 flow.state.outputs={};flow.state.run_status="idle"
func refresh():
 refreshing=true
 mode.select(1 if flow.state.mode=="local" else 0);endpoint.text=flow.state.endpoint;model_name.text=flow.state.model
 source_label.text="Document: "+(flow.state.source_name if not flow.state.source_name.is_empty() else "none")+" · "+str(flow.state.document.to_utf8_buffer().size())+" bytes"
 graph.clear_connections()
 for child in graph.get_children():
  if child is GraphNode:graph.remove_child(child);child.queue_free()
 for menu in [steps,from_step,to_step]:menu.clear()
 var index=0
 for node in flow.state.graph.nodes:
  var item=GraphNode.new();item.name=node.id;item.title=node.id+" · "+node.kind;item.position_offset=Vector2(35+(index%4)*240,35+floori(index/4.0)*140);item.custom_minimum_size=Vector2(210,100)
  var text=Label.new();text.text="Document input" if node.kind=="read" else "Select to inspect";item.add_child(text)
  item.set_slot(0,node.kind!="read",0,Color(0.4,0.8,0.65),true,0,Color(0.4,0.8,0.65));graph.add_child(item)
  item.gui_input.connect(func(event):
   if event is InputEventMouseButton and event.pressed:show_step(str(item.name)))
  for menu in [steps,from_step,to_step]:menu.add_item(node.id)
  index+=1
 for edge in flow.state.graph.edges:graph.connect_node(edge[0],0,edge[1],0)
 if not flow.state.graph.nodes.any(func(node):return node.id==selected):selected=flow.state.graph.nodes[0].id
 refreshing=false;show_step(selected);update_status()
func show_step(id: String):
 selected=id
 for index in steps.item_count:
  if steps.get_item_text(index)==id:steps.select(index)
 for node in flow.state.graph.nodes:
  if node.id==id:
   option.text=node.option;inspector.text="Inspect "+id+" · "+node.kind+". Extraction option matches lines in template mode; local AI follows the focus."
 var result=flow.state.outputs.get(id)
 output.text=("Mode: "+("Template mode · no AI" if result.mode=="template" else "Local AI · review required")+"\n\n"+result.text) if result!=null else (flow.state.document if id=="read" else "No output for this step. Run the workflow.")
func update_status():
 for item in editing_controls:
  if item is BaseButton:item.disabled=runner.busy
  else:item.editable=not runner.busy
 # Graph mutation callbacks also refuse changes while a run is active.
 graph.mouse_filter=Control.MOUSE_FILTER_IGNORE if runner.busy else Control.MOUSE_FILTER_STOP
 run_button.disabled=runner.busy
 if not refreshing and is_instance_valid(output):show_step(selected)
 if is_instance_valid(status):status.text="Run status: "+flow.state.run_status+" · "+("Template mode (no AI)" if flow.state.mode=="template" else "Local AI only")+" · "+flow.path
func mode_changed(index: int):
 if runner.busy:return
 flow.state.mode="local" if index==1 else "template";invalidate();update_status()
func apply_option():
 if runner.busy:return
 if option.text.to_utf8_buffer().size()>2048:tell("Step option exceeds 2,048 bytes.");return
 for node in flow.state.graph.nodes:
  if node.id==selected:node.option=option.text
 invalidate();show_step(selected);tell("Option applied. Run again to generate current outputs.")
func add_step():
 if runner.busy:return
 if flow.state.graph.nodes.size()>=16:tell("Maximum 16 steps.");return
 var kind=kinds.get_item_text(kinds.selected);var id=kind+str(Time.get_ticks_usec())
 flow.state.graph.nodes.append({"id":id,"kind":kind,"option":"English" if kind=="translate" else ""});selected=id;invalidate();refresh()
func remove_step():
 if runner.busy:return
 if flow.state.graph.nodes.size()==1:tell("Keep at least one step.");return
 flow.state.graph.nodes=flow.state.graph.nodes.filter(func(node):return node.id!=selected)
 flow.state.graph.edges=flow.state.graph.edges.filter(func(edge):return not edge.has(selected))
 invalidate();refresh()
func graph_connect(source: String,_port: int,target: String,_target_port: int):
 if runner.busy:return
 var candidate=flow.state.graph.duplicate(true)
 if candidate.edges.has([source,target]):tell("Connection already exists.");return
 candidate.edges.append([source,target])
 # Partial drafts may contain disconnected steps; enforce local safety then
 # use full validation before saving or executing.
 if source==target:tell("A step cannot connect to itself.");return
 for node in candidate.nodes:
  if node.id==target and node.kind=="read":tell("Read steps have no input.");return
 for edge in flow.state.graph.edges:
  if edge[1]==target:tell("Disconnect the destination's previous input first.");return
 if flow.order(candidate).is_empty():tell("Connection would create a cycle.");return
 flow.state.graph=candidate;invalidate();refresh()
func graph_disconnect(source: String,_port: int,target: String,_target_port: int):
 if runner.busy:return
 flow.state.graph.edges.erase([source,target]);invalidate();refresh()
func configure() -> String:
 if not flow.valid_endpoint(endpoint.text):return "Only http://127.0.0.1:PORT/v1/chat/completions is allowed."
 if model_name.text.is_empty() or model_name.text.length()>128:return "Use a model alias between 1 and 128 characters."
 if flow.state.endpoint!=endpoint.text or flow.state.model!=model_name.text:invalidate()
 flow.state.endpoint=endpoint.text;flow.state.model=model_name.text;return ""
func run_workflow():
 var error=configure()
 if not error.is_empty():tell(error);return
 error=await runner.execute(flow)
 tell(error if not error.is_empty() else "Workflow complete. Inspect every output, then export the report explicitly.")
func save_workspace():
 var error=configure()
 if error.is_empty():error=flow.save_workspace()
 tell(error if not error.is_empty() else "Workspace saved with previous-generation backup.")
func request_reopen():confirm.popup_centered()
func reopen():
 if runner.busy:return
 var error=flow.open_workspace();refresh();tell(error if not error.is_empty() else "Saved workspace reopened.")
func import_path(path: String):
 if runner.busy:return
 var error=flow.import_document(path);refresh();tell(error if not error.is_empty() else "Document imported locally. Save or run to retain it.")
func choose(action: String):
 if runner.busy:return
 for callback in chooser.file_selected.get_connections():chooser.file_selected.disconnect(callback.callable)
 chooser.file_mode=FileDialog.FILE_MODE_SAVE_FILE if action in ["export","copy"] else FileDialog.FILE_MODE_OPEN_FILE
 chooser.filters=PackedStringArray(["*.txt, *.md ; UTF-8 text documents"]) if action=="import" else (PackedStringArray(["*.md, *.txt ; Report text"]) if action=="export" else PackedStringArray(["*.json, *.backup ; Flow workspace or backup"]))
 chooser.title={"import":"Import local document","export":"Export report to a new filename","open":"Open workspace / recover backup (edits will be replaced)","copy":"Save workspace copy to a new filename"}[action]
 chooser.file_selected.connect(func(path):
  match action:
   "import":import_path(path)
   "export":
    var error=flow.export_report(path);tell(error if not error.is_empty() else "Report exported: "+path)
   "open":
    var candidate=Workflow.new();candidate.path=path
    var error=candidate.open_workspace()
    if not candidate.writable:tell(error);return
    # A backup opens read-only until Save copy creates a separate workspace.
    if path.ends_with(".backup"):candidate.writable=false
    flow=candidate;refresh();tell(error if not error.is_empty() else "Opened "+path+". For a backup, use Save copy before editing.")
   "copy":
    if FileAccess.file_exists(path):tell("Choose a new filename; copies never overwrite.");return
    var candidate=Workflow.new();candidate.path=path
    var error=candidate.open_workspace()
    if not error.is_empty():tell(error);return
    candidate.state=flow.state.duplicate(true);error=candidate.save_workspace()
    if error.is_empty():flow=candidate;refresh()
    tell(error if not error.is_empty() else "Workspace copy saved: "+path)
 )
 chooser.popup_centered_ratio(0.85)
