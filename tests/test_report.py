from dataclasses import asdict
from io import BytesIO
import json
import zipfile
import numpy as np

from xrd_workbench.core import Pattern, process, Recipe, detect_peaks
from xrd_workbench.matching import compare, MatchOptions
from xrd_workbench.report import build_report
from xrd_workbench.bundle import make_bundle


def scan(name="Sample"):
    x=np.linspace(5,45,2001)
    return Pattern(name,x,100+800*sum(np.exp(-.5*((x-p)/.12)**2) for p in [12,20,32]))


def test_unknown_identity_stays_unknown_without_api():
    p,ref=scan(),scan("ref")
    comparison={"ranked":[compare(p,ref)],"rejected":[]}
    report=build_report(p,comparison)
    assert report["data"]["api_calls"]==0
    assert report["data"]["structure_hypothesis"]["status"]=="reference_candidate"
    assert "物相名未知" in report["markdown"]
    assert report["data"]["boundaries"]["structure_solved"] is False
    assert report["data"]["main_peaks"][0]["d_angstrom"] is None


def test_user_structure_metadata_is_not_verified_structure():
    p,ref=scan(),scan("ref")
    info={"ref":{"phase_name":"Candidate A","formula":"AB2","structure":"P1","from_cif":"yes","source":"USER-001"}}
    report=build_report(p,{"ranked":[compare(p,ref)]},reference_info=info)
    row=report["data"]["main_peaks"][0]["candidate_assignments"][0]
    assert row["phase_name"]=="Candidate A"
    assert row["identity_basis"]=="user_declaration_unverified"
    assert "没有读取该 CIF" in report["markdown"]
    assert "AB2" in report["markdown"] and "USER-001" in report["markdown"]


def test_ambiguous_peak_keeps_all_references():
    p,a,b=scan(),scan("A"),scan("B")
    report=build_report(p,{"ranked":[compare(p,a),compare(p,b)]})
    assert all(len(r["candidate_assignments"])==2 for r in report["data"]["main_peaks"])
    assert all(r["assignment_status"]=="ambiguous_multiple_references" for r in report["data"]["main_peaks"])


def test_no_reference_or_flat_data_cannot_invent_identity():
    p=scan()
    flat=Pattern("flat",p.x,np.ones_like(p.x))
    report=build_report(flat,{"ranked":[]})
    assert report["data"]["main_peaks"]==[]
    assert report["data"]["structure_hypothesis"]["status"]=="not_determined"


def test_export_has_distinct_raw_and_comparison_data_and_reports(monkeypatch):
    monkeypatch.delenv("NATURE_FIGURE_SKILL",raising=False)
    raw=scan()
    processed=process(raw,Recipe(lower=10,upper=40))
    z,meta,plots=make_bundle([processed],[],recipe={"matching":asdict(MatchOptions())},
          comparisons={},peaks=detect_peaks(processed),measurement_pattern=raw)
    assert meta["measurement"]["pattern"]["points"]==2001
    assert meta["patterns"][0]["points"]==1501
    assert meta["measurement"]["pattern"]["history"]==[]
    assert plots["png"] != plots["measurement"]["png"]
    with zipfile.ZipFile(BytesIO(z)) as archive:
        source=np.loadtxt(BytesIO(archive.read("measurement/source.csv")),delimiter=",",skiprows=1)
        np.testing.assert_allclose(source[:,1],raw.y,rtol=1e-10)
        assert {"measurement/figure.pdf","figure.pdf","report.md","report.json","reports/01.md"}.issubset(archive.namelist())
        report=json.loads(archive.read("report.json"))
        assert report["raw_points"]==2001 and report["processed_points"]==1501
