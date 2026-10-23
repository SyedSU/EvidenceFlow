extends RefCounted
func valid(value):return value is Dictionary and value.get("package_smoke")==true
func run(tree):
 var files=load("res://scripts/durable_files.gd").new()
 if not files.native_available():push_error("Packaged native persistence missing");tree.quit(1);return
 var path="user://package-smoke.json"
 var error=files.write_json(path,'{"package_smoke":true}',valid,4096)
 if not error.is_empty():push_error("Packaged native write failed: "+error);tree.quit(1);return
 var loaded=files.read_json(path,valid,4096)
 if not loaded.ok or not loaded.data.package_smoke:push_error("Packaged native read failed");tree.quit(1);return
 await tree.process_frame;await tree.process_frame
 print("PACKAGED_NATIVE_SAVE_AND_UI_PASS")
 tree.quit()
