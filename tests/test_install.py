import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('installer', Path(__file__).resolve().parents[1] / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def info(version=(3, 13), bits=64, implementation='cpython', free_threaded=False):
    return dict(version=version, bits=bits, implementation=implementation, free_threaded=free_threaded,
                executable='/a path/python')


def test_supported_interpreters():
    for minor in range(11, 15):
        assert installer.supported(info((3, minor)))
    for value in [info((3, 10)), info((3, 15)), info(bits=32),
                  info(implementation='pypy'), info(free_threaded=True)]:
        assert not installer.supported(value)


def test_discovery_skips_incompatible_python(monkeypatch):
    monkeypatch.setattr(installer, 'candidates', lambda: iter([['old'], ['missing'], ['compatible']]))
    monkeypatch.setattr(installer, 'probe', lambda command: {
        'old': info((3, 9)), 'missing': None, 'compatible': info((3, 13))}[command[0]])
    assert installer.select_python()['version'] == (3, 13)


def test_explicit_python_does_not_silently_fall_back(monkeypatch):
    monkeypatch.setattr(installer, 'probe', lambda command: info((3, 9)))
    import pytest
    with pytest.raises(RuntimeError, match='No supported Python'):
        installer.select_python('/old/python')
