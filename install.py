"""Create a project environment using an available supported Python."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

MIN_PYTHON = (3, 11)
MAX_PYTHON = (3, 15)
PROBE = (
    "import json,sys,struct,sysconfig; "
    "print(json.dumps({'version':list(sys.version_info[:2]),"
    "'bits':struct.calcsize('P')*8,'implementation':sys.implementation.name,"
    "'free_threaded':bool(sysconfig.get_config_var('Py_GIL_DISABLED')),"
    "'executable':sys.executable,'prefix':sys.prefix,'base_prefix':sys.base_prefix}))"
)


def supported(info):
    return (MIN_PYTHON <= tuple(info['version']) < MAX_PYTHON
            and info['bits'] == 64 and info['implementation'] == 'cpython'
            and not info.get('free_threaded', False))


def probe(command):
    try:
        result = subprocess.run(command + ['-I', '-c', PROBE], capture_output=True,
                                text=True, encoding='utf-8', timeout=20)
        return json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def candidates():
    yield [sys.executable]
    if os.name == 'nt' and shutil.which('py'):
        for minor in range(14, 10, -1):
            yield ['py', '-3.' + str(minor)]
    for name in ['python3.14', 'python3.13', 'python3.12', 'python3.11', 'python3', 'python']:
        path = shutil.which(name)
        if path:
            yield [path]


def select_python(explicit=None):
    for command in ([[explicit]] if explicit else candidates()):
        info = probe(command)
        if info and supported(info):
            return info
    raise RuntimeError(
        'No supported Python found. Install standard 64-bit CPython 3.11-3.14 '
        'from https://www.python.org/downloads/ and run this command again. '
        'On Windows, use py --list to inspect installed interpreters. '
        'Python 3.10 and earlier, free-threaded builds and 32-bit Python are not supported.'
    )


def run(command):
    print('Running: ' + subprocess.list2cmdline([str(v) for v in command]), flush=True)
    subprocess.run([str(v) for v in command], check=True)


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', help='Path to a specific Python executable')
    parser.add_argument('--venv', type=Path, help='Environment directory; default: project/.venv')
    parser.add_argument('--check', action='store_true', help='Only detect a compatible Python')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    try:
        info = select_python(args.python)
        print('Selected Python {}: {}'.format('.'.join(map(str, info['version'])), info['executable']))
        if args.check:
            return 0
        if not (root / 'pyproject.toml').is_file():
            raise RuntimeError('Project files are missing. Extract the complete repository before installing.')
        env_dir = args.venv.resolve() if args.venv else root / '.venv'
        executable = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        if env_dir.exists():
            existing = probe([str(executable)])
            config = env_dir / 'pyvenv.cfg'
            if (not existing or not supported(existing)
                    or Path(existing['prefix']).resolve() != env_dir.resolve()
                    or existing['prefix'] == existing['base_prefix']
                    or not config.is_file()
                    or 'include-system-site-packages = false' not in config.read_text(encoding="utf-8").lower()):
                raise RuntimeError('Existing environment is incomplete or incompatible: {}. '
                                   'Use --venv .venv-xrd to create a separate environment.'.format(env_dir))
        else:
            run([info['executable'], '-I', '-m', 'venv', env_dir])
        # Use UTF-8 even when a Windows terminal redirects output in a legacy locale.
        pip = [executable, '-I', '-X', 'utf8', '-m', 'pip']
        run(pip + ['install', '--upgrade', 'pip'])
        run(pip + ['install', '--only-binary=:all:', root])
        run(pip + ['check'])
        print('\nInstallation complete. Start the application with:')
        command = subprocess.list2cmdline([str(executable), '-m', 'xrd_workbench.cli', 'ui'])
        if os.name == 'nt':
            command = '& "{}" -m xrd_workbench.cli ui'.format(executable)
        print(command)
        print('Keep that terminal open; visit the URL printed by the server.')
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print('\nInstallation stopped: {}'.format(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
