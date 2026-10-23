/* Godot4.7.2 C ABI bridge. Only static persistence operations are exposed. */
#include "gdextension_interface.h"
#include "save_platform.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

_Static_assert(sizeof(void *)==8,"Genesis save adapter requires a 64-bit target");
/* String/StringName are 8-byte opaque types in the pinned float_64 ABI. */
static void *class_name;
static GDExtensionClassLibraryPtr library;
static GDExtensionInterfaceVariantGetType variant_type;
static GDExtensionTypeFromVariantConstructorFunc to_string;
static GDExtensionVariantFromTypeConstructorFunc from_int;
static GDExtensionInterfaceStringToUtf8Chars string_utf8;
static GDExtensionInterfaceStringNameNewWithUtf8Chars name_new;
static GDExtensionInterfaceStringNewWithUtf8Chars string_new;
static GDExtensionPtrDestructor string_destroy, name_destroy;
static GDExtensionInterfaceClassdbRegisterExtensionClass6 register_class;
static GDExtensionInterfaceClassdbRegisterExtensionClassMethod register_method;
static GDExtensionInterfaceClassdbUnregisterExtensionClass unregister_class;

static char *path_string(GDExtensionConstStringPtr value) {
    GDExtensionInt size=string_utf8(value,NULL,0);
    if (size<=0 || size>32768) return NULL;
    char *path=malloc((size_t)size+1);
    if (!path) return NULL;
    GDExtensionInt written=string_utf8(value,path,size);
    path[size]=0;
    if (written!=size || strlen(path)!=(size_t)size) {free(path);return NULL;}
    return path;
}
static int64_t operate(int operation, const char *source, const char *destination) {
    if (!source || (operation==2 && !destination)) return 1;
    if (operation==1) return genesis_sync_file(source);
    if (operation==2) return genesis_replace_file(source,destination);
    if (operation==3) return genesis_lock_file(source);
    if (operation==4) return genesis_unlock_file(source);
    return 1;
}
static void method_call(void *userdata, GDExtensionClassInstancePtr instance,
        const GDExtensionConstVariantPtr *args, GDExtensionInt argc,
        GDExtensionVariantPtr result, GDExtensionCallError *error) {
    (void)instance;
    int operation=(int)(intptr_t)userdata;
    int count=operation==2?2:1;
    int64_t status=1;
    error->error=GDEXTENSION_CALL_OK;
    if (argc!=count) {
        error->error=argc<count?GDEXTENSION_CALL_ERROR_TOO_FEW_ARGUMENTS:GDEXTENSION_CALL_ERROR_TOO_MANY_ARGUMENTS;
        error->expected=count;
    } else {
        char *paths[2]={NULL,NULL};
        for (int i=0;i<count;i++) {
            if (variant_type(args[i])!=GDEXTENSION_VARIANT_TYPE_STRING) {
                error->error=GDEXTENSION_CALL_ERROR_INVALID_ARGUMENT;
                error->argument=i;error->expected=GDEXTENSION_VARIANT_TYPE_STRING;break;
            }
            void *string=NULL;
            to_string(&string,(GDExtensionVariantPtr)args[i]);
            paths[i]=path_string(&string);
            string_destroy(&string);
        }
        if (error->error==GDEXTENSION_CALL_OK) status=operate(operation,paths[0],paths[1]);
        free(paths[0]);free(paths[1]);
    }
    from_int(result,&status);
}
static void method_ptrcall(void *userdata, GDExtensionClassInstancePtr instance,
        const GDExtensionConstTypePtr *args, GDExtensionTypePtr result) {
    (void)instance;
    int operation=(int)(intptr_t)userdata;
    char *source=path_string(args[0]);
    char *destination=operation==2?path_string(args[1]):NULL;
    *(int64_t *)result=operate(operation,source,destination);
    free(source);free(destination);
}
static void free_instance(void *userdata, GDExtensionClassInstancePtr instance) {
    (void)userdata;(void)instance; /* Abstract class has no instances. */
}
static void add_method(const char *label, int operation) {
    int count=operation==2?2:1;
    void *name=NULL,*empty_name=NULL,*empty_string=NULL,*arg_names[2]={NULL,NULL};
    name_new(&name,label);name_new(&empty_name,"");string_new(&empty_string,"");
    GDExtensionPropertyInfo return_info={0},args[2]={{0},{0}};
    GDExtensionClassMethodArgumentMetadata metadata[2]={0,0};
    return_info.type=GDEXTENSION_VARIANT_TYPE_INT;
    return_info.name=&empty_name;return_info.class_name=&empty_name;return_info.hint_string=&empty_string;return_info.usage=6;
    for (int i=0;i<count;i++) {
        name_new(&arg_names[i],i==0?"source":"destination");
        args[i]=return_info;args[i].type=GDEXTENSION_VARIANT_TYPE_STRING;args[i].name=&arg_names[i];
    }
    GDExtensionClassMethodInfo method={0};
    method.name=&name;method.method_userdata=(void *)(intptr_t)operation;
    method.call_func=method_call;method.ptrcall_func=method_ptrcall;
    method.method_flags=GDEXTENSION_METHOD_FLAG_NORMAL|GDEXTENSION_METHOD_FLAG_STATIC;
    method.has_return_value=1;method.return_value_info=&return_info;
    method.argument_count=(uint32_t)count;method.arguments_info=args;method.arguments_metadata=metadata;
    register_method(library,&class_name,&method);
    for (int i=0;i<count;i++) name_destroy(&arg_names[i]);
    name_destroy(&name);name_destroy(&empty_name);string_destroy(&empty_string);
}
static void initialize(void *userdata, GDExtensionInitializationLevel level) {
    (void)userdata;
    if (level!=GDEXTENSION_INITIALIZATION_SCENE) return;
    void *parent=NULL;name_new(&class_name,"GenesisDurableFiles");name_new(&parent,"RefCounted");
    GDExtensionClassCreationInfo6 info={0};
    /* Internal static API: not an editor-creatable resource/class. */
    info.is_abstract=1;info.is_exposed=0;info.free_instance_func=free_instance;
    register_class(library,&class_name,&parent,&info);
    add_method("sync_file",1);add_method("replace_file",2);
    add_method("lock_file",3);add_method("unlock_file",4);
    name_destroy(&parent);
}
static void deinitialize(void *userdata, GDExtensionInitializationLevel level) {
    (void)userdata;
    if (level!=GDEXTENSION_INITIALIZATION_SCENE) return;
    unregister_class(library,&class_name);name_destroy(&class_name);
}
GENESIS_EXPORT GDExtensionBool genesis_save_init(GDExtensionInterfaceGetProcAddress get,
        GDExtensionClassLibraryPtr lib, GDExtensionInitialization *init) {
#define LOAD(variable,type,label) do { GDExtensionInterfaceFunctionPtr raw=get(label); \
    _Static_assert(sizeof(variable)==sizeof(raw),"Godot function pointer ABI"); \
    memcpy(&variable,&raw,sizeof(variable));if (!variable) return 0; } while (0)
    LOAD(variant_type,GDExtensionInterfaceVariantGetType,"variant_get_type");
    LOAD(string_utf8,GDExtensionInterfaceStringToUtf8Chars,"string_to_utf8_chars");
    LOAD(name_new,GDExtensionInterfaceStringNameNewWithUtf8Chars,"string_name_new_with_utf8_chars");
    LOAD(string_new,GDExtensionInterfaceStringNewWithUtf8Chars,"string_new_with_utf8_chars");
    LOAD(register_class,GDExtensionInterfaceClassdbRegisterExtensionClass6,"classdb_register_extension_class6");
    LOAD(register_method,GDExtensionInterfaceClassdbRegisterExtensionClassMethod,"classdb_register_extension_class_method");
    LOAD(unregister_class,GDExtensionInterfaceClassdbUnregisterExtensionClass,"classdb_unregister_extension_class");
    GDExtensionInterfaceGetVariantToTypeConstructor to_type;
    GDExtensionInterfaceGetVariantFromTypeConstructor from_type;
    GDExtensionInterfaceVariantGetPtrDestructor destructor;
    LOAD(to_type,GDExtensionInterfaceGetVariantToTypeConstructor,"get_variant_to_type_constructor");
    LOAD(from_type,GDExtensionInterfaceGetVariantFromTypeConstructor,"get_variant_from_type_constructor");
    LOAD(destructor,GDExtensionInterfaceVariantGetPtrDestructor,"variant_get_ptr_destructor");
#undef LOAD
    to_string=to_type(GDEXTENSION_VARIANT_TYPE_STRING);from_int=from_type(GDEXTENSION_VARIANT_TYPE_INT);
    string_destroy=destructor(GDEXTENSION_VARIANT_TYPE_STRING);name_destroy=destructor(GDEXTENSION_VARIANT_TYPE_STRING_NAME);
    if (!to_string || !from_int || !string_destroy || !name_destroy) return 0;
    library=lib;init->minimum_initialization_level=GDEXTENSION_INITIALIZATION_SCENE;
    init->userdata=NULL;init->initialize=initialize;init->deinitialize=deinitialize;return 1;
}
