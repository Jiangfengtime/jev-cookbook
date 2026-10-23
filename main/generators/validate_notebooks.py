"""逐本在新内核验证课程 Notebook；默认仅编译，--execute 才请求真实服务。

main/.venv/bin/python main/generators/validate_notebooks.py --scope all --execute --output /tmp/jev-validation
"""
import argparse, concurrent.futures, hashlib, json, os, sys, tempfile, time
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
OUT=None
STALE_ENV=False
CFG=dotenv_values(ROOT/'main/.env');KEY=CFG.get('TYPESAFE_API_KEY') or ''
BOOT='''import json as _vj, os as _vo
from dotenv import dotenv_values as _vvalues
from typesafe_sdk import TypeSafeClient as _VC
_vcfg = _vvalues(%r)
_vbase = _vcfg.get('TYPESAFE_BASE_URL') or _vo.getenv('TYPESAFE_BASE_URL') or 'https://api.typesafe.ai'
_vkey = _vcfg.get('TYPESAFE_API_KEY') or _vo.getenv('TYPESAFE_API_KEY', '')
_vrequests = []
_voriginal = _VC._request
def _vrequest(self, request, **kwargs):
    assert request.url.startswith(_vbase.rstrip('/') + '/'), 'Wrong endpoint'
    assert request.headers.get('Authorization') == 'Bearer ' + _vkey, 'Wrong credential source'
    _vrow = {'status': 'started'}
    _vrequests.append(_vrow)
    try:
        result = _voriginal(self, request, **kwargs)
        _vrow.update(status='ok', model=getattr(result, 'model', None))
        return result
    except Exception as error:
        _vrow.update(status='error', error=type(error).__name__)
        raise
_VC._request = _vrequest
''' % str(ROOT/'main/.env')
END='''assert _vrequests, 'No real API calls were made'
assert all(r['status'] == 'ok' for r in _vrequests), 'Some API calls failed or fell back'
if 'TS' in globals():
    assert not getattr(TS, 'offline', False), 'Notebook fell back to fake answers'
print('__VALIDATION__' + _vj.dumps({'requests': len(_vrequests), 'models': sorted(set(r['model'] for r in _vrequests if r.get('model')))}))
'''
BENCHMARK_AUDIT = '''from collections import Counter
_expected = {json.loads(line)['id'] for line in (PROJ / 'tasks/public_all.jsonl').read_text().splitlines() if line.strip()}
_checked = list((PROJ / 'runs/notebook-demo/real').rglob('results.jsonl'))
assert _checked, 'Missing real benchmark results'
for _file in _checked:
    _rows = [json.loads(line) for line in _file.read_text().splitlines() if line.strip()]
    _counts = Counter(row['status'] for row in _rows)
    assert {row['task_id'] for row in _rows} == _expected, 'Incomplete benchmark task coverage'
    assert len(_rows) == len(_expected) and _counts == {'ok': len(_expected)}, dict(_counts)
    print('BENCHMARK_COVERAGE', _file.parent.name, dict(_counts))
'''
def run(path):
    started=time.time();rel=path.relative_to(ROOT)
    print('START',str(rel),flush=True)
    core=rel.parts[1].startswith(('01_', '02_', '03_', '04_'))
    nb=nbformat.read(path,as_version=4);installs=0
    source_hash=hashlib.sha256(json.dumps([c.source for c in nb.cells],ensure_ascii=False).encode()).hexdigest()
    for cell in nb.cells:
        if cell.cell_type=='code':
            cell.outputs=[];cell.execution_count=None
            if '%pip' in cell.source:
                cell.source='import typesafe_sdk, dotenv  # Dependencies already installed; no environment mutation during validation'
                installs+=1
    if core:
        nb.cells.insert(0,nbformat.v4.new_code_cell(BOOT));nb.cells.append(nbformat.v4.new_code_cell(END))
    elif rel.parts[1] == '06_模型评测':
        nb.cells.append(nbformat.v4.new_code_cell(BENCHMARK_AUDIT))
    env=os.environ.copy();env['JEV_RUN_MODE']='live'
    if STALE_ENV:
        env.update(TYPESAFE_API_KEY='stale-validation-key',TYPESAFE_BASE_URL='http://127.0.0.1:8811',TYPESAFE_DEFAULT_MODEL='laya-multilingual')
    km=KernelManager(kernel_name='python3');km.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
    rec={'path':str(rel),'status':'failed','dependency_install_cells_skipped':installs,'source_sha256':source_hash}
    try:
        NotebookClient(nb,km=km,timeout=120,resources={'metadata':{'path':str(path.parent)}}).execute(env=env)
        for output in nb.cells[-1].get('outputs', []):
            for line in output.get('text','').splitlines():
                if line.startswith('__VALIDATION__'):rec.update(json.loads(line.removeprefix('__VALIDATION__')))
        rec['status']='passed'
    except Exception as e:
        detail=str(e)
        if KEY:detail=detail.replace(KEY,'[redacted]')
        rec.update(error_type=type(e).__name__,error=detail[-6500:])
    finally:
        if km.has_kernel:km.shutdown_kernel(now=True)
        km.cleanup_resources()
    if rec['status']=='failed' and any(word in rec.get('error','') for word in ['需要 NVIDIA CUDA GPU', '缩放对比需要聊天模型 Key', '缺少 Jev-Mem 外部项目', '找不到 Pi CLI']):
        rec['status']='blocked_prerequisite'
    rec['seconds']=round(time.time()-started,1)
    nb.metadata['jev_validation']=rec.copy()
    raw=nbformat.writes(nb)
    if KEY and KEY in raw:
        raw=raw.replace(KEY,'[redacted]');rec.update(status='failed',error='Secret found in notebook output')
    destination=OUT/rel;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(raw)
    print(rec['status'].upper(),str(rel),'seconds=',rec['seconds'],'requests=',rec.get('requests'), 'error=',rec.get('error_type',''),flush=True)
    return rec
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scope',choices=['core','all'],default='core')
    ap.add_argument('--pattern',action='append',default=[])
    ap.add_argument('--execute',action='store_true',help='启用真实执行；可能产生服务用量')
    ap.add_argument('--test-stale-env',action='store_true',help='注入旧 Key/本机地址，验证 .env 优先级')
    ap.add_argument('--output',type=Path)
    ap.add_argument('--workers',type=int,choices=[1,2],default=2)
    args=ap.parse_args()
    paths=sorted(p for p in (ROOT/'main').rglob('*.ipynb')
                 if not any(x in p.parts for x in ['11_知识库','validation','.venv','.ipynb_checkpoints','templates']))
    if args.scope=='core':
        paths=[p for p in paths if p.relative_to(ROOT).parts[1].startswith(('01_','02_','03_','04_'))]
    if args.pattern:paths=[p for p in paths if any(s in str(p) for s in args.pattern)]
    if not paths:ap.error('没有匹配的 Notebook')
    if not args.execute:
        from IPython.core.inputtransformer2 import TransformerManager
        transform=TransformerManager()
        for p in paths:
            nb=nbformat.read(p,as_version=4)
            for i,c in enumerate(nb.cells):
                if c.cell_type=='code':compile(transform.transform_cell(c.source),f'{p}:{i}','exec')
        print('Syntax/format passed:',len(paths),'notebooks. Use --execute for runtime validation.')
        sys.exit(0)
    OUT=(args.output or Path(tempfile.mkdtemp(prefix='jev-validation-'))).resolve()
    OUT.mkdir(parents=True,exist_ok=True)
    STALE_ENV=args.test_stale_env
    records=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,p) for p in paths]):
            records.append(future.result())
            (OUT/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print('SUMMARY',len(records),'passed',sum(r['status']=='passed' for r in records),'report',OUT/'results.json')
    sys.exit(1 if any(r['status']=='failed' for r in records) else 0)
