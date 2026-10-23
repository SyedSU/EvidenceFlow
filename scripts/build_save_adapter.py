"""Build first-party x64 save GDExtension. A C compiler is build-time only."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
HEADER_SHA='640b48188708ba0016f8d7ace9e0e1d3279a41fa1226c59ff3193b15538bd254'
ANDROID_NDK_VERSION='28.2.13676358'

def android_compiler(ndk):
    ndk=Path(ndk).resolve()
    properties=ndk/'source.properties'
    if not properties.is_file() or 'Pkg.Revision = '+ANDROID_NDK_VERSION not in properties.read_text(encoding='utf-8').splitlines():
        raise RuntimeError('Reviewed Android NDK '+ANDROID_NDK_VERSION+' required')
    if platform.machine().lower() not in ('x86_64','amd64') or sys.platform not in ('linux','win32'):
        raise RuntimeError('Reviewed Android build hosts are Linux/Windows x64')
    host='windows-x86_64' if os.name=='nt' else 'linux-x86_64'
    toolchain=ndk/'toolchains/llvm/prebuilt'/host
    compiler=toolchain/'bin'/('clang.exe' if os.name=='nt' else 'clang')
    if not compiler.is_file():raise RuntimeError('NDK clang toolchain unavailable')
    return str(compiler),['--target=aarch64-linux-android26','--sysroot='+str(toolchain/'sysroot')]

def windows_compiler(temp):
    environment=os.environ.copy()
    compiler=shutil.which('cl')
    if compiler:return compiler,environment
    # Existing windows-latest toolchain; setup path is installer-derived.
    finder=Path(environment.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    if not finder.exists():raise RuntimeError('Visual Studio C compiler required to build the save adapter')
    install=subprocess.check_output([str(finder),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    setup=Path(install)/'VC/Auxiliary/Build/vcvars64.bat'
    if not install or not setup.is_file():raise RuntimeError('Visual Studio x64 C toolchain unavailable')
    if any(c in str(setup) for c in ('"','%','\n','\r')):raise RuntimeError('Unsupported toolchain setup path')
    batch=Path(temp)/'toolchain.cmd'
    # Only fixed toolchain setup is batch code. Checkout/output paths and C
    # arguments are passed directly to cl, preserving Unicode and literal %.
    batch.write_text('@echo off\nchcp 65001 >nul\ncall "'+str(setup)+'" >nul\nif errorlevel 1 exit /b %errorlevel%\n'+''.join('set '+name+'\n' for name in ('PATH','INCLUDE','LIB','LIBPATH')),encoding='utf-8')
    output=subprocess.check_output(['cmd','/d','/c',str(batch)],cwd=temp,encoding='utf-8')
    for line in output.splitlines():
        name,_,value=line.partition('=');name=name.upper()
        if name in ('PATH','INCLUDE','LIB','LIBPATH'):environment[name]=value
    compiler=shutil.which('cl',path=environment.get('PATH'))
    if not compiler or not environment.get('INCLUDE') or not environment.get('LIB'):raise RuntimeError('Visual Studio environment was not initialized')
    return compiler,environment

def build_adapter(project=ROOT/'native',android_ndk=None):
    project=Path(project).resolve()
    source=project/'durability'
    if hashlib.sha256((source/'gdextension_interface.h').read_bytes()).hexdigest()!=HEADER_SHA:
        raise RuntimeError('Pinned Godot4.7.2 ABI header changed; review/rebuild required')
    if platform.machine().lower() not in ('x86_64','amd64'):raise RuntimeError('Save adapter supports x64 Windows/Linux only')
    output=project/('genesis_save.android.arm64.so' if android_ndk else ('genesis_save.dll' if os.name=='nt' else 'genesis_save.so'))
    with tempfile.TemporaryDirectory(prefix='genesis-save-build-') as temp:
        temp=Path(temp)
        files=[source/'save_platform.c',source/'save_extension.c']
        if android_ndk:
            compiler,target=android_compiler(android_ndk)
            print('GENESIS_ANDROID_NDK:',ANDROID_NDK_VERSION,'API:26 ABI:arm64-v8a')
            subprocess.run([compiler,*target,'-std=c11','-Wall','-Wextra','-Werror','-O2','-pthread','-fPIC','-fvisibility=hidden','-shared','-Wl,--no-undefined',*[str(x) for x in files],'-o',str(output)],cwd=temp,check=True)
        elif os.name=='nt':
            compiler,environment=windows_compiler(temp)
            subprocess.run([compiler,'/Bv','/nologo','/std:c11','/W4','/WX','/O2','/MT','/LD',*[str(x) for x in files],'/link','/OUT:'+str(output)],cwd=temp,env=environment,check=True)
        else:
            compiler=shutil.which('cc')
            if not compiler:raise RuntimeError('C compiler required to build the save adapter')
            print('GENESIS_SAVE_COMPILER:',subprocess.check_output([compiler,'--version'],text=True).splitlines()[0])
            subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-O2','-pthread','-fPIC','-fvisibility=hidden','-shared',*[str(x) for x in files],'-o',str(output)],cwd=temp,check=True)
    print('GENESIS_SAVE_ADAPTER_BUILT:',output.name,'SHA256:',hashlib.sha256(output.read_bytes()).hexdigest())
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--project',type=Path,default=ROOT/'native')
    parser.add_argument('--android-ndk',type=Path,help='Reviewed NDK28.2.13676358; compile arm64-v8a API26 adapter')
    args=parser.parse_args();build_adapter(args.project,args.android_ndk)
