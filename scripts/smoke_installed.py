"""Exercise an installed package from outside its source directory."""
import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--wheel', action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    assert not os.environ.get('NATURE_FIGURE_SKILL')
    assert sys.prefix != sys.base_prefix
    import xrd_workbench
    package_file = Path(xrd_workbench.__file__).resolve()
    if args.wheel:
        assert Path(sys.prefix).resolve() in package_file.parents, package_file
    import numpy as np
    from streamlit.testing.v1 import AppTest
    import xrd_workbench.ui
    from xrd_workbench.figures import audit_pdf

    # Renamed public examples exercise Unicode and spaces without private inputs.
    names = [('Synthetic sample.csv', '样品 sample.csv'),
             ('Synthetic Phase A.csv', '参考 A.csv'), ('Synthetic Phase B.csv', '参考 B.csv')]
    paths = []
    for source, name in names:
        path = out / name
        path.write_bytes((args.examples / source).read_bytes())
        paths.append(path)
    archive = out / 'analysis.zip'
    subprocess.run([sys.executable, '-I', '-m', 'xrd_workbench.cli', 'analyze', str(paths[0]),
                    '--reference', str(paths[1]), '--reference', str(paths[2]),
                    '--wavelength', '1.5406', '--output', str(archive)], check=True)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for line in z.read('checksums.sha256').decode().splitlines():
            digest, name = line.split('  ', 1)
            assert sha256(z.read(name)).hexdigest() == digest
        m = json.loads(z.read('manifest.json'))
        assert m['nature_qa']['status'] == 'not_run'
        for prefix in ['', 'measurement/']:
            for ext in ['pdf', 'svg', 'png', 'tiff']:
                assert len(z.read(prefix + 'figure.' + ext)) > 1000
            assert audit_pdf(z.read(prefix + 'figure.pdf'))['status'] == 'pass'
        saved = np.loadtxt(BytesIO(z.read('measurement/source.csv')), delimiter=',', skiprows=1)
        original = np.loadtxt(paths[0], delimiter=',', skiprows=2)
        np.testing.assert_allclose(saved, original, rtol=1e-10, atol=1e-10)
        assert m['reports'][paths[0].name]['data']['raw_points'] == 3001
        # Extraction is limited to an archive produced in this test.
        z.extractall(out / 'replay')
    subprocess.run([sys.executable, '-I', str(out / 'replay/reproduce_analysis.py')], check=True)
    subprocess.run([sys.executable, '-I', str(out / 'replay/reproduce.py')], check=True)
    replayed = json.loads((out / 'replay/reproduced-comparisons.json').read_text(encoding='utf-8'))
    stored = json.loads((out / 'replay/comparisons.json').read_text(encoding='utf-8'))
    assert replayed == stored

    app = AppTest.from_file(str(Path(xrd_workbench.ui.__file__)), default_timeout=120).run()
    assert not app.exception
    next(b for b in app.button if b.label == '运行分析并生成图谱').click().run(timeout=120)
    assert not app.exception and not app.error
    result = app.session_state['analysis_result']
    assert {'实测谱图', '对比图', '分析报告'} <= {t.label for t in app.tabs}
    assert result['plots']['measurement']['png'].startswith(b'\x89PNG')
    assert result['comparisons'][result['target']]['ranked'][0]['reference'] == 'Synthetic Phase A.csv'

    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    process_options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
                       if os.name == 'nt' else {'start_new_session': True})
    with (out / 'server.log').open('w', encoding='utf-8') as log:
        server = subprocess.Popen([sys.executable, '-I', '-m', 'xrd_workbench.cli', 'ui',
                                   '--port', str(port)], stdout=log, stderr=log, **process_options)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError('Server exited; inspect server.log')
                try:
                    with opener.open('http://127.0.0.1:{}/_stcore/health'.format(port), timeout=2) as response:
                        if response.read().strip() == b'ok':
                            break
                except OSError:
                    time.sleep(.5)
            else:
                raise RuntimeError('Server health check timed out')
            with opener.open('http://127.0.0.1:{}/'.format(port), timeout=5) as response:
                assert response.status == 200 and b'<html' in response.read().lower()
        finally:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(server.pid), '/T', '/F'], check=False)
            else:
                try:
                    os.killpg(server.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            server.wait(timeout=20)
    evidence = dict(status='passed', python=sys.version, platform=platform.platform(),
                    machine=platform.machine(), package=str(package_file), wheel=args.wheel,
                    private_skills=False, checks=['cli', 'four_export_formats', 'raw_values',
                    'checksums', 'raw_replay', 'redraw', 'ui_analysis', 'http_server'])
    (out / 'result.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
