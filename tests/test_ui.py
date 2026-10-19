from pathlib import Path
from streamlit.testing.v1 import AppTest
import xrd_workbench.ui


def test_demo_end_to_end(monkeypatch):
    monkeypatch.delenv("NATURE_FIGURE_SKILL", raising=False)
    at=AppTest.from_file(str(Path(xrd_workbench.ui.__file__)),default_timeout=60).run()
    assert not at.exception
    next(t for t in at.text_input if t.label=="化合物 / 物相名称").set_value("User-declared phase")
    next(b for b in at.button if b.label=="运行分析并生成图谱").click().run(timeout=60)
    assert not at.exception
    assert len(at.error)==0
    result=at.session_state["analysis_result"]
    assert result["comparisons"][result["target"]]["ranked"][0]["reference"]=="Synthetic Phase A.csv"
    assert result["bundle"].startswith(b"PK")
    assert result["plots"]["measurement"]["png"].startswith(b"\x89PNG")
    assert {"实测谱图", "对比图", "分析报告"}.issubset({tab.label for tab in at.tabs})
    report=result["meta"]["reports"][result["target"]]
    assert "User-declared phase" in report["markdown"]
    assert report["data"]["api_calls"]==0
