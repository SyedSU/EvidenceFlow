"""First-party Windows version resources for builder-owned unsigned templates.

Patch the template BEFORE Godot embeds the PCK. Never modify a released/signed
artifact or run UpdateResource on a game with an embedded pack.
"""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import struct


def version_tuple(version):
 if not isinstance(version,str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?',version):
  raise ValueError('Expected three or four decimal version components')
 parts=tuple(int(part) for part in version.split('.'))
 if any(part>65535 for part in parts):raise ValueError('Version component exceeds WORD')
 return parts+(0,)*(4-len(parts))


def version_resource(version):
 parts=version_tuple(version);text='.'.join(map(str,parts))
 def align(data):return data+b'\0'*((-len(data))%4)
 def block(key,value=b'',children=b'',kind=0,value_length=None):
  body=align(b'\0'*6+(key+'\0').encode('utf-16le'))+value
  if children:body=align(body)+children
  return struct.pack('<HHH',len(body),len(value) if value_length is None else value_length,kind)+body[6:]
 def string(key,value):
  data=(value+'\0').encode('utf-16le')
  return block(key,data,kind=1,value_length=len(data)//2)
 strings=[('CompanyName','Evidence'),('FileDescription','EvidenceFlow Review Application'),
          ('FileVersion',text),('InternalName','EvidenceFlow'),('OriginalFilename','EvidenceFlow.exe'),
          ('ProductName','EvidenceFlow'),('ProductVersion',text)]
 table=block('040904b0',children=b''.join(align(string(key,value)) for key,value in strings),kind=1)
 info=block('StringFileInfo',children=table,kind=1)
 translation=block('VarFileInfo',children=block('Translation',struct.pack('<HH',0x409,1200)),kind=1)
 ms=(parts[0]<<16)|parts[1];ls=(parts[2]<<16)|parts[3]
 fixed=struct.pack('<13I',0xfeef04bd,0x10000,ms,ls,ms,ls,0x3f,0,0x40004,1,0,0,0)
 return block('VS_VERSION_INFO',fixed,align(info)+translation)


def _windows():
 if os.name!='nt':raise OSError('Windows resource APIs are required')
 return ctypes.WinDLL('kernel32',use_last_error=True)


def read_version(path):
 _windows();api=ctypes.WinDLL('version',use_last_error=True)
 api.GetFileVersionInfoSizeW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(wintypes.DWORD)];api.GetFileVersionInfoSizeW.restype=wintypes.DWORD
 api.GetFileVersionInfoW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p];api.GetFileVersionInfoW.restype=wintypes.BOOL
 api.VerQueryValueW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.UINT)];api.VerQueryValueW.restype=wintypes.BOOL
 name=str(Path(path).resolve());unused=wintypes.DWORD();size=api.GetFileVersionInfoSizeW(name,ctypes.byref(unused))
 if not size:raise ctypes.WinError(ctypes.get_last_error())
 data=ctypes.create_string_buffer(size)
 if not api.GetFileVersionInfoW(name,0,size,data):raise ctypes.WinError(ctypes.get_last_error())
 pointer=ctypes.c_void_p();length=wintypes.UINT()
 if not api.VerQueryValueW(data,'\\',ctypes.byref(pointer),ctypes.byref(length)) or length.value<52:
  raise RuntimeError('Version fixed info missing')
 values=struct.unpack('<13I',ctypes.string_at(pointer,52))
 if values[0]!=0xfeef04bd or values[2:4]!=values[4:6]:raise RuntimeError('File/product fixed version mismatch')
 return (values[2]>>16,values[2]&65535,values[3]>>16,values[3]&65535)


def write_version(path,version):
 """Replace all existing version languages on an owned template, preserving other resources."""
 data=version_resource(version);api=_windows();name=str(Path(path).resolve())
 api.LoadLibraryExW.argtypes=[wintypes.LPCWSTR,wintypes.HANDLE,wintypes.DWORD];api.LoadLibraryExW.restype=wintypes.HMODULE
 api.FreeLibrary.argtypes=[wintypes.HMODULE];api.FreeLibrary.restype=wintypes.BOOL
 names_callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMODULE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ssize_t)
 languages_callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMODULE,ctypes.c_void_p,ctypes.c_void_p,wintypes.WORD,ctypes.c_ssize_t)
 api.EnumResourceNamesW.argtypes=[wintypes.HMODULE,ctypes.c_void_p,names_callback,ctypes.c_ssize_t];api.EnumResourceNamesW.restype=wintypes.BOOL
 api.EnumResourceLanguagesW.argtypes=[wintypes.HMODULE,ctypes.c_void_p,ctypes.c_void_p,languages_callback,ctypes.c_ssize_t];api.EnumResourceLanguagesW.restype=wintypes.BOOL
 api.BeginUpdateResourceW.argtypes=[wintypes.LPCWSTR,wintypes.BOOL];api.BeginUpdateResourceW.restype=wintypes.HANDLE
 api.UpdateResourceW.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,wintypes.WORD,ctypes.c_void_p,wintypes.DWORD];api.UpdateResourceW.restype=wintypes.BOOL
 api.EndUpdateResourceW.argtypes=[wintypes.HANDLE,wintypes.BOOL];api.EndUpdateResourceW.restype=wintypes.BOOL
 entries=[];errors=[]
 @languages_callback
 def language_callback(_module,_type,resource,language,_parameter):
  entries.append((resource if resource<=65535 else ctypes.wstring_at(resource),language));return True
 @names_callback
 def name_callback(module,_type,resource,_parameter):
  if not api.EnumResourceLanguagesW(module,16,resource,language_callback,0):errors.append(ctypes.get_last_error())
  return not errors
 module=api.LoadLibraryExW(name,None,0x2|0x20)
 if not module:raise ctypes.WinError(ctypes.get_last_error())
 try:
  if not api.EnumResourceNamesW(module,16,name_callback,0):
   error=ctypes.get_last_error()
   if error not in (1813,1814,1815):raise ctypes.WinError(error)
  if errors:raise ctypes.WinError(errors[0])
 finally:api.FreeLibrary(module)
 handle=api.BeginUpdateResourceW(name,False)
 if not handle:raise ctypes.WinError(ctypes.get_last_error())
 try:
  for resource,language in entries:
   resource_pointer=resource if isinstance(resource,int) else ctypes.cast(ctypes.c_wchar_p(resource),ctypes.c_void_p)
   if not api.UpdateResourceW(handle,16,resource_pointer,language,None,0):raise ctypes.WinError(ctypes.get_last_error())
  buffer=ctypes.create_string_buffer(data)
  if not api.UpdateResourceW(handle,16,1,0,buffer,len(data)):raise ctypes.WinError(ctypes.get_last_error())
 except BaseException:
  api.EndUpdateResourceW(handle,True);raise
 if not api.EndUpdateResourceW(handle,False):raise ctypes.WinError(ctypes.get_last_error())
 if read_version(path)!=version_tuple(version):raise RuntimeError('Written Windows version did not round-trip')
