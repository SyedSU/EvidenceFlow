extends SceneTree
func valid(value):return value is Dictionary and value.get("package_smoke")==true
func failed(message):push_error(message);quit(1)
func _initialize():call_deferred("run")
func run():
 var files=load("res://scripts/durable_files.gd").new()
 if not files.native_available():failed("Packaged native persistence missing");return
 var path="user://package-smoke.json"
 var error=files.write_json(path,'{"package_smoke":true}',valid,4096)
 if not error.is_empty():failed("Packaged native write failed: "+error);return
 var loaded=files.read_json(path,valid,4096)
 if not loaded.ok or not loaded.data.package_smoke:failed("Packaged native read failed");return
 var scene=load("res://main.tscn").instantiate();root.add_child(scene)
 await process_frame;await process_frame
 print("PACKAGED_NATIVE_SAVE_AND_UI_PASS")
 quit()
