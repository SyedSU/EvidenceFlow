class_name GenesisSaveFiles
extends RefCounted

# Native persistence is mandatory. No buffered-only/platform rename fallback.
var uncertain=false
var last_revision: Dictionary={}

func lease(path: String, acquire: bool) -> bool:
	return native_available() and ClassDB.class_call_static("GenesisDurableFiles","lock_file" if acquire else "unlock_file",ProjectSettings.globalize_path(path)+".lock")==0

func revision(path: String, limit: int) -> Dictionary:
	var result={"active":null,"backup":null}
	for suffix in ["",".backup"]:
		var name=path+suffix
		if not FileAccess.file_exists(name):
			if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(name)):return {}
			continue
		var record=read_bytes(name,limit)
		if not record.ok:return {}
		var hash=HashingContext.new();hash.start(HashingContext.HASH_SHA256);hash.update(record.bytes)
		result["active" if suffix.is_empty() else "backup"]=hash.finish().hex_encode()
	return result

func native_available() -> bool:
	return ClassDB.class_exists("GenesisDurableFiles") and ClassDB.class_has_method("GenesisDurableFiles","lock_file") and ClassDB.class_has_method("GenesisDurableFiles","unlock_file")

func sync_file(path: String) -> Error:
	if not native_available():return ERR_UNAVAILABLE
	return OK if ClassDB.class_call_static("GenesisDurableFiles","sync_file",ProjectSettings.globalize_path(path))==0 else FAILED

func native_replace(source: String, destination: String) -> int:
	return ClassDB.class_call_static("GenesisDurableFiles","replace_file",ProjectSettings.globalize_path(source),ProjectSettings.globalize_path(destination))

func replace(source: String, destination: String) -> Error:
	if not native_available():return ERR_UNAVAILABLE
	var status=native_replace(source,destination)
	if status==2:uncertain=true
	return OK if status==0 else FAILED

func store_checked(path: String, bytes: PackedByteArray) -> String:
	var file=FileAccess.open(path,FileAccess.WRITE)
	if file==null:return "Could not open the save stage. Check folder permissions and free space."
	var stored=file.store_buffer(bytes)
	file.flush()
	var status=file.get_error()
	file.close()
	if not stored or status!=OK:return "The save stage could not be written. Check free space."
	var readback=read_bytes(path,bytes.size())
	if not readback.ok or readback.bytes!=bytes:return "The save stage failed byte verification."
	if sync_file(path)!=OK:return "The save stage could not be synced to disk. Previous files preserved."
	return ""

func read_bytes(path: String, limit: int) -> Dictionary:
	var file=FileAccess.open(path,FileAccess.READ)
	if file==null:return {"ok":false,"bytes":PackedByteArray()}
	var size=file.get_length()
	if size<=0 or size>limit:file.close();return {"ok":false,"bytes":PackedByteArray()}
	var bytes=file.get_buffer(size)
	var status=file.get_error();file.close()
	return {"ok":bytes.size()==size and status==OK,"bytes":bytes}

func valid_utf8(bytes: PackedByteArray) -> bool:
	var offset=0
	while offset<bytes.size():
		var first=bytes[offset]
		if first<0x80:offset+=1;continue
		var width=2 if first>=0xc2 and first<=0xdf else (3 if first>=0xe0 and first<=0xef else (4 if first>=0xf0 and first<=0xf4 else 0))
		if width==0 or offset+width>bytes.size():return false
		for position in range(1,width):
			if bytes[offset+position]<0x80 or bytes[offset+position]>0xbf:return false
		var second=bytes[offset+1]
		if (first==0xe0 and second<0xa0) or (first==0xed and second>0x9f) or (first==0xf0 and second<0x90) or (first==0xf4 and second>0x8f):return false
		offset+=width
	return true

func decode(bytes: PackedByteArray, validator: Callable) -> Dictionary:
	if not valid_utf8(bytes):return {"ok":false}
	var parser=JSON.new()
	if parser.parse(bytes.get_string_from_utf8())!=OK or not parser.data is Dictionary:return {"ok":false}
	if not validator.call(parser.data):return {"ok":false}
	return {"ok":true,"data":parser.data}

func temporary(path: String) -> String:
	return path+".tmp-"+str(Time.get_ticks_usec())+"-"+str(randi())

func cleanup(path: String):
	# Only the newly generated stage created by this operation; never user saves.
	if FileAccess.file_exists(path):DirAccess.remove_absolute(ProjectSettings.globalize_path(path))

func quarantine(path: String, bytes: PackedByteArray) -> String:
	var context=HashingContext.new();context.start(HashingContext.HASH_SHA256);context.update(bytes)
	var copy_path=path+".corrupt-"+context.finish().hex_encode()
	if FileAccess.file_exists(copy_path):
		var existing=read_bytes(copy_path,bytes.size())
		return copy_path if existing.ok and existing.bytes==bytes else ""
	if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(copy_path)):return ""
	var stage=temporary(copy_path);var error=store_checked(stage,bytes)
	if error.is_empty() and replace(stage,copy_path)==OK:return copy_path
	cleanup(stage);return ""

func read_json(path: String, validator: Callable, limit: int) -> Dictionary:
	if not lease(path,true):return {"ok":false,"error":"Save is busy or its transaction lock is unavailable. Close other instances and retry."}
	var snapshot=revision(path,limit)
	var result=read_json_locked(path,validator,limit)
	result["revision"]=snapshot
	if not lease(path,false):
		uncertain=true
		return {"ok":false,"error":"Save transaction could not be released. Reload before saving."}
	return result

func read_json_locked(path: String, validator: Callable, limit: int) -> Dictionary:
	var source=path
	if not FileAccess.file_exists(path):
		if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(path)):return {"ok":false,"error":"Save path is a directory. Original preserved."}
		if not FileAccess.file_exists(path+".backup"):return {"ok":false,"missing":true,"error":""}
		source=path+".backup"
	var bytes=read_bytes(source,limit)
	if not bytes.ok:return {"ok":false,"error":"Save unreadable or too large. Original preserved; restore a known backup."}
	var value=decode(bytes.bytes,validator)
	if not value.ok:
		var copy_path=quarantine(source,bytes.bytes)
		return {"ok":false,"error":"Invalid save. Original preserved; restore a known backup."+(" Quarantine copy: "+copy_path if not copy_path.is_empty() else " Quarantine unavailable; original is untouched.")}
	return {"ok":true,"data":value.data,"source":source,"error":"Recovered the previous save from backup after an interrupted replacement." if source!=path else ""}

func restore_backup(stage: String, backup: String) -> String:
	if stage.is_empty():return ""
	if replace(stage,backup)==OK:return ""
	if uncertain:return " Backup rollback sync failed. Previous backup is at "+backup+"; durability is uncertain. Reload before saving."
	# A failed Windows move may already have removed the destination. The
	# verified stage is now a recovery copy, not disposable operation debris.
	return " Previous backup retained in recovery file: "+stage

func write_json(path: String, text: String, validator: Callable, limit: int, expected: Dictionary={"active":null,"backup":null}) -> String:
	last_revision={}
	if uncertain:return "Save durability is uncertain. Reload the workshop before saving again; recovery files are preserved."
	if not native_available():return "Native save support is unavailable. Reinstall the complete game package before saving."
	if not lease(path,true):return "Save is busy or its transaction lock is unavailable. Close other instances and retry."
	var snapshot=revision(path,limit)
	var error=""
	if snapshot.is_empty():error="Save or backup is unreadable or is a directory. Previous files preserved."
	elif snapshot!=expected:error="Save changed in another instance. Reload before saving; newer files are preserved."
	else:
		error=write_json_locked(path,text,validator,limit)
		if error.is_empty():
			last_revision=revision(path,limit)
			if last_revision.is_empty():uncertain=true;error="Save committed but verification failed. Reload before saving."
		elif not uncertain:
			# A failed first replacement may have created a valid backup of the
			# unchanged primary. Adopt only our verified, non-uncertain outcome;
			# never acknowledge a revision from the stale-writer rejection above.
			var retained=revision(path,limit)
			if not retained.is_empty() and retained.active==snapshot.active:
				var safe=true
				for suffix in ["",".backup"]:
					if FileAccess.file_exists(path+suffix):
						var record=read_bytes(path+suffix,limit)
						if not record.ok or not decode(record.bytes,validator).ok:safe=false
				if safe:last_revision=retained
	if not lease(path,false):uncertain=true;return "Save transaction could not be released. Reload before saving."
	return error

func write_json_locked(path: String, text: String, validator: Callable, limit: int) -> String:
	if uncertain:return "Save durability is uncertain. Reload the workshop before saving again; recovery files are preserved."
	if not native_available():return "Native save support is unavailable. Reinstall the complete game package before saving."
	var bytes=text.to_utf8_buffer()
	if bytes.is_empty() or bytes.size()>limit or not decode(bytes,validator).ok:return "Invalid or oversized save data. Previous files preserved."
	var backup=path+".backup"
	for destination in [path,backup]:
		if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(destination)):return "Save or backup path is a directory. Previous files preserved."
	var previous=PackedByteArray();var prior_backup=PackedByteArray()
	for existing in [path,backup]:
		if FileAccess.file_exists(existing):
			var record=read_bytes(existing,limit)
			if not record.ok or not decode(record.bytes,validator).ok:return "Existing save or backup is unreadable/invalid. Original preserved; restore a known backup."
			if existing==path:previous=record.bytes
			else:prior_backup=record.bytes
	var stage=temporary(path);var backup_stage=temporary(backup)
	var rollback_stage=""
	# Stage the existing backup before any destructive replacement. If the
	# primary was absent, the backup never changes and must not be rolled back.
	if not previous.is_empty() and not prior_backup.is_empty():
		rollback_stage=temporary(backup)
		var rollback_error=store_checked(rollback_stage,prior_backup)
		if not rollback_error.is_empty():cleanup(rollback_stage);return "Backup recovery stage failed. Original files preserved. "+rollback_error
	var error=store_checked(stage,bytes)
	if not error.is_empty():cleanup(stage);cleanup(rollback_stage);return error
	if not previous.is_empty():
		error=store_checked(backup_stage,previous)
		if not error.is_empty():cleanup(stage);cleanup(backup_stage);cleanup(rollback_stage);return "Backup failed. "+error
		if replace(backup_stage,backup)!=OK:
			if uncertain:return "Backup replacement sync failed. Active original preserved at "+path+"; reload before saving. Recovery stage: "+rollback_stage+". Uncommitted candidate: "+stage
			var recovery=restore_backup(rollback_stage,backup)
			cleanup(stage);cleanup(backup_stage);return "Backup replacement failed. Active original preserved."+recovery
	if replace(stage,path)!=OK:
		if uncertain:return "Save replacement sync failed. Disk state may have advanced; reload before saving. Previous generation: "+backup+(". Older recovery stage: "+rollback_stage if not rollback_stage.is_empty() else "")
		var restoration=""
		if not previous.is_empty() and not FileAccess.file_exists(path):restoration=store_checked(path,previous)
		# Keep the verified original in backup if restoring the active path fails.
		var recovery=""
		if restoration.is_empty():recovery=restore_backup(rollback_stage,backup)
		elif not rollback_stage.is_empty():recovery=" Older backup retained in recovery file: "+rollback_stage
		cleanup(stage)
		return ("Save replacement failed. Previous save retained." if restoration.is_empty() else "Save replacement and recovery failed. The verified original is in the backup; restore it before continuing.")+recovery
	cleanup(rollback_stage)
	return ""
