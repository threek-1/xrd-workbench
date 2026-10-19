import numpy as np
import pytest
from xrd_workbench.core import Pattern, Recipe, parse_bytes, process, detect_peaks


def scan(y=None):
    x = np.linspace(5, 45, 2001)
    return Pattern("sample", x, np.exp(-.5*((x-20)/.15)**2) if y is None else y, 1.5406)


@pytest.mark.parametrize("delimiter", [" ", ",", "\t", ";"])
def test_delimiters_and_header(delimiter):
    raw = ("Angle Intensity\n"+"\n".join(delimiter.join(map(str,(i,i*2))) for i in range(5,15))).encode()
    pat = parse_bytes(raw,"a.xy")
    assert len(pat.x) == 10
    assert pat.y[0] == 10
    assert len(pat.metadata["sha256"]) == 64


def test_sort_preserves_pairs_and_logs():
    p = parse_bytes(b"9 2\n8 4\n7 6\n6 8\n5 10", "x.xy")
    assert p.y.tolist() == [10,8,6,4,2]
    assert p.history[0]["operation"] == "sort_angle_ascending"


@pytest.mark.parametrize("data", [b"5 1\n6 2\n7 nan\n8 4\n9 5", b"5 1\n6 2\n7 3\n7 4\n9 5",
    b"5 1\n6 2\n7 ERROR\n8 4\n9 5", b"5,1\n6,2\n7,\n8,4\n9,5", b"\x00\x01binary"])
def test_bad_data_not_silently_removed(data):
    with pytest.raises(ValueError):
        parse_bytes(data,"bad.txt")


def test_multicolumn_requires_explicit_mapping():
    raw=b"5 1 90\n6 2 80\n7 3 70\n8 4 60\n9 5 50"
    with pytest.raises(ValueError, match="columns"):
        parse_bytes(raw,"x")
    assert parse_bytes(raw,"x",columns=(0,2)).y[0] == 90


def test_original_is_readonly_and_processing_reproducible():
    original = scan()
    y = original.y.copy()
    r = Recipe(lower=10,upper=30,smooth_window=7)
    a, b = process(original,r), process(original,r)
    np.testing.assert_array_equal(original.y,y)
    np.testing.assert_array_equal(a.y,b.y)
    assert a.x[0] == 10 and a.x[-1] == 30
    assert a.y.max() == 1
    with pytest.raises(ValueError):
        original.y[0] = 1


def test_nonuniform_processing_guard():
    p = Pattern("x", [5,6,7,9,10], [1,2,3,2,1])
    with pytest.raises(ValueError,match="uniform"):
        process(p,Recipe(baseline=True))


def test_peak_units_and_width():
    peaks=detect_peaks(scan())
    assert len(peaks)==1
    assert peaks[0]["two_theta_deg"] == pytest.approx(20)
    assert peaks[0]["width_half_prominence_deg"] == pytest.approx(.15*2.35482,abs=.002)
    assert peaks[0]["d_angstrom"] == pytest.approx(1.5406/(2*np.sin(np.deg2rad(10))))


def test_flat_has_no_peaks():
    assert detect_peaks(scan(np.ones(2001))) == []


def test_baseline_removes_background_without_mutating_input():
    p=scan()
    elevated=Pattern("x",p.x,p.y+5+.01*p.x)
    adjusted=process(elevated,Recipe(baseline=True,normalization="none"))
    assert np.median(np.abs(adjusted.y-p.y)) < .02
    assert elevated.y.min()>5


@pytest.mark.parametrize("recipe", [Recipe(lower=30,upper=10),Recipe(smooth_window=6),Recipe(normalization="bogus"),
                                    Recipe(lower=float("nan")),Recipe(baseline_iterations=0)])
def test_recipe_validation(recipe):
    with pytest.raises(ValueError):
        process(scan(),recipe)


def test_provenance_does_not_call_synthetic_data_measured():
    rows=b"5 1\n6 2\n7 3\n8 2\n9 1"
    assert parse_bytes(rows,"scan").kind == "user_supplied"
    assert parse_bytes(b"# SYNTHETIC DEMONSTRATION; not measured\n"+rows,"demo").kind == "synthetic"


@pytest.mark.parametrize("separator", [",", ";"])
def test_instrument_terminal_delimiter_preserves_every_pair(separator):
    lines = ["[Data]", separator.join(["Angle", "PSD", ""])]
    lines += [separator.join([str(5+i*.02), str(10+i), ""]) for i in range(6)]
    data = ("\r\n".join(lines)+"\r\n").encode()
    p = parse_bytes(data, "instrument.txt")
    np.testing.assert_allclose(p.x, 5+np.arange(6)*.02)
    np.testing.assert_array_equal(p.y, np.arange(10,16))
    assert p.metadata["terminal_delimiter_rows"] == list(range(3,9))
    assert len(p.metadata["header_lines"]) == 2


@pytest.mark.parametrize("broken", ["5,", "5,,", ",10,", "5,,10,", "5,10,,"])
def test_terminal_delimiter_does_not_hide_missing_fields(broken):
    with pytest.raises(ValueError):
        parse_bytes((broken+"\n6,10,\n7,11,\n8,12,\n9,13,").encode(),"bad.csv")


def test_terminal_delimiter_retains_multicolumn_selection_rules():
    raw=b"5,1,90,\n6,2,80,\n7,3,70,\n8,4,60,\n9,5,50,"
    with pytest.raises(ValueError, match="columns"):
        parse_bytes(raw,"multi.csv")
    p=parse_bytes(raw,"multi.csv",columns=(0,2))
    np.testing.assert_array_equal(p.y,[90,80,70,60,50])
    with pytest.raises(ValueError, match="Missing selected column"):
        parse_bytes(raw,"multi.csv",columns=(0,3))
