from hashlib import sha256
from io import BytesIO
import json
import zipfile
import numpy as np
import matplotlib.pyplot as plt
from xrd_workbench.core import Pattern
from xrd_workbench.figures import make_figure, export_figure, audit_pdf
from xrd_workbench.bundle import make_bundle


def pattern():
    x=np.linspace(5,60,551)
    return Pattern("Reference A",x,np.exp(-((x-20)/.3)**2),1.5406)


def test_export_source_integrity_and_checksums(monkeypatch):
    monkeypatch.delenv("NATURE_FIGURE_SKILL", raising=False)
    raw=b"an original source preserved byte for byte\n"
    z,meta,plots=make_bundle([pattern()],[("../unsafe.csv",raw)],recipe={},comparisons={},peaks=[])
    with zipfile.ZipFile(BytesIO(z)) as archive:
        assert archive.testzip() is None
        assert archive.read("raw/01_unsafe.csv")==raw
        assert not any(".." in n for n in archive.namelist())
        for line in archive.read("checksums.sha256").decode().splitlines():
            digest,name=line.split("  ",1)
            assert sha256(archive.read(name)).hexdigest()==digest
        manifest=json.loads(archive.read("manifest.json"))
        assert manifest["claims"]["score_is_probability"] is False
    assert audit_pdf(plots["pdf"])["status"] == "pass"
    assert b"<text" in plots["svg"]


def test_stacked_data_not_rescaled():
    p=pattern()
    fig,meta=make_figure([p,p])
    for line,trace in zip(fig.axes[0].lines,meta["traces"]):
        np.testing.assert_allclose(line.get_ydata()-trace["offset"],p.y,atol=1e-15)
    plt.close(fig)


def test_overlay_text_qa():
    fig,_=make_figure([pattern(),pattern()],mode="overlay",width_mm=88)
    files=export_figure(fig)
    assert audit_pdf(files["pdf"])["status"] == "pass"
    plt.close(fig)
