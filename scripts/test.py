"""Developer-only suite runner. Players use the exported native application."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--godot',required=True)
    args=parser.parse_args()
    failures=[]
    commands=[('import',[args.godot,'--headless','--path',str(ROOT),'--editor','--import','--quit'])]
    commands += [(name.stem,[args.godot,'--headless','--path',str(ROOT),'--script','res://tests/'+name.name]) for name in sorted((ROOT/'tests').glob('test_*.gd'))]
    for name,command in commands:
        result=subprocess.run(command,capture_output=True,text=True,timeout=180)
        output=result.stdout+result.stderr
        (ROOT/'docs/evidence'/f'{name}.log').write_text(output,encoding='utf-8')
        bad=result.returncode!=0 or any(marker in output for marker in ('SCRIPT ERROR:','ERROR:','FAIL:','WARNING:'))
        print(name, 'FAIL' if bad else 'PASS',f'({output.count("PASS:")} assertions)')
        if bad:failures.append(name);print(output)
    return bool(failures)
if __name__=='__main__':sys.exit(main())
