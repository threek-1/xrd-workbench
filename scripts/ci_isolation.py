"""Install and test source and wheel packages in separate temporary environments."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


def main():
    root = Path(__file__).resolve().parents[1]
    artifacts = root / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    env = os.environ.copy()
    for name in ['PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'NATURE_FIGURE_SKILL']:
        env.pop(name, None)
    env.update(PYTHONNOUSERSITE='1', PIP_NO_CACHE_DIR='1',
               PIP_DISABLE_PIP_VERSION_CHECK='1', MPLBACKEND='Agg',
               STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')
    with tempfile.TemporaryDirectory(prefix='xrd-clean-') as tmp:
        tmp = Path(tmp)
        source = tmp / '项目 XRD'
        shutil.copytree(root, source, ignore=shutil.ignore_patterns(
            '.git', '.venv', '__pycache__', '.pytest_cache', 'artifacts', 'build', '*.egg-info'))
        outside = tmp / 'outside'
        outside.mkdir()
        smoke = outside / 'smoke_installed.py'
        shutil.copy2(source / 'scripts/smoke_installed.py', smoke)

        def run(command):
            subprocess.run([str(p) for p in command], cwd=outside, env=env, check=True)

        def python_at(folder):
            return folder / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

        source_env = tmp / 'source-env'
        run([sys.executable, '-I', source / 'install.py', '--python', sys.executable,
             '--venv', source_env])
        source_python = python_at(source_env)
        run([source_python, '-I', smoke, '--examples', source / 'examples',
             '--output', artifacts / 'source'])
        run([source_python, '-I', '-m', 'pip', 'install', 'pytest>=8,<9', 'build>=1,<2'])
        run([source_python, '-I', '-m', 'pytest', source / 'tests', '-q'])
        run([source_python, '-I', '-m', 'build', source, '--outdir', artifacts / 'dist'])
        wheel = next((artifacts / 'dist').glob('*.whl'))
        wheel_env = tmp / 'wheel-env'
        venv.EnvBuilder(with_pip=True).create(wheel_env)
        wheel_python = python_at(wheel_env)
        run([wheel_python, '-I', '-m', 'pip', 'install', '--upgrade', 'pip'])
        run([wheel_python, '-I', '-m', 'pip', 'install', '--only-binary=:all:', wheel])
        run([wheel_python, '-I', '-m', 'pip', 'check'])
        # Remove the source import path to detect missing files in the wheel.
        examples = outside / 'examples'
        shutil.copytree(source / 'examples', examples)
        shutil.rmtree(source)
        run([wheel_python, '-I', smoke, '--wheel', '--examples', examples,
             '--output', artifacts / 'wheel'])
        freeze = subprocess.check_output([str(wheel_python), '-I', '-m', 'pip', 'freeze'], env=env)
        (artifacts / 'dependencies.txt').write_bytes(freeze)


if __name__ == '__main__':
    main()
