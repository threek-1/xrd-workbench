"""Streamlit interface for XRD processing and comparison."""
from dataclasses import asdict, replace
from io import BytesIO
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from xrd_workbench.core import parse_bytes, process, Recipe, detect_peaks
from xrd_workbench.matching import MatchOptions, rank_references
from xrd_workbench.bundle import make_bundle, json_bytes
from xrd_workbench.demo import demo_inputs


CSS = """
<style>
[data-testid="stAppViewContainer"] {background:#f7f9fa;}
.block-container {max-width:1260px;padding-top:2.2rem;padding-bottom:3rem;}
h1 {letter-spacing:-.055em;font-weight:750!important;color:#163542;}
h2,h3 {color:#234955;}
[data-testid="stSidebar"] {background:#edf2f3;}
[data-testid="stMetric"] {background:white;border:1px solid #dfe7e9;border-radius:12px;padding:18px;}
[data-testid="stForm"] {background:white;border:1px solid #dfe7e9;border-radius:14px;}
.stButton>button[kind="primary"] {background:#246b81;border:none;}
.eyebrow {font-size:12px;letter-spacing:.16em;color:#527c89;font-weight:700;}
.lead {font-size:17px;line-height:1.8;color:#5b6f76;margin-bottom:24px;}
</style>
"""


def main():
    st.set_page_config(page_title="XRD Workbench", page_icon="◫", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown('<div class="eyebrow">POWDER X-RAY DIFFRACTION</div>', unsafe_allow_html=True)
    st.title("XRD Workbench")
    st.markdown('<div class="lead">导入 XRD 数据，对比参考谱，导出图谱与分析报告。</div>', unsafe_allow_html=True)
    with st.sidebar:
        st.header("工作区")
        demo = st.toggle("使用合成示例", value=True)
        st.caption("示例为固定随机种子生成的虚构谱线，用于演示，不是实测或真实物相数据。")
        st.divider()
        st.markdown("**工作流程**\n\n① 导入样品与参考库\n\n② 设置处理与匹配\n\n③ 检查候选及逐峰证据\n\n④ 导出图谱和可复现记录")
        st.divider()
        st.caption("本地运行\n\n支持一维连续谱；物相信息由用户填写。")
    if demo:
        entries = demo_inputs()
        samples, refs = entries[:1], entries[1:]
    else:
        col1, col2 = st.columns(2)
        with col1:
            su = st.file_uploader("实验样品 · 可多选", type=["txt", "csv", "xy", "dat", "tsv"], accept_multiple_files=True)
        with col2:
            ru = st.file_uploader("标准 / 参考谱 · 可多选", type=["txt", "csv", "xy", "dat", "tsv"], accept_multiple_files=True)
        samples = [(f.name, f.getvalue()) for f in su]
        refs = [(f.name, f.getvalue()) for f in ru]
    if not samples:
        st.info("先上传至少一个样品。没有参考谱时也可以处理、寻峰和导出。")
        return
    if len(samples) > 20 or len(refs) > 40:
        st.error("单次最多 20 个样品、40 个参考谱。请分批运行。")
        return
    all_names = [name for name, _ in samples+refs]
    if len(set(all_names)) != len(all_names):
        st.error("文件名有重复。请为不同样品和参考谱使用唯一名称，以保证报告对应准确。")
        return
    with st.form("analysis"):
        st.subheader("01 / 分析设置")
        a, b, c = st.columns(3)
        with a:
            lower = st.number_input("2θ 下限 / °", value=5., min_value=0., max_value=179., step=1.)
            upper = st.number_input("2θ 上限 / °", value=80., min_value=1., max_value=180., step=1.)
            norm = st.selectbox("强度归一化", ["max", "none", "area"],
                                format_func=lambda v: {"max":"保留范围最大值 = 1", "none":"保留输入强度", "area":"保留范围积分 = 1"}[v])
        with b:
            baseline = st.checkbox("扣除背景（AsLS，仅样品）", value=False)
            smooth = st.checkbox("Savitzky–Golay 平滑（仅样品）", value=False)
            window = st.number_input("平滑窗口 / 点数（奇数）", value=11, min_value=5, max_value=301, step=2)
        with c:
            tol = st.number_input("峰位匹配容差 / °", value=.20, min_value=.01, max_value=2., step=.01)
            prom = st.slider("最低峰突出度 / 信号范围", .01, .50, .04, .01)
            spacing = st.number_input("最小峰间距 / °", value=.15, min_value=.01, max_value=5., step=.01)
        with st.expander("解析、波长与高级参数"):
            st.caption("默认读取两列：2θ（度）与强度。多列文件必须显式选择列；不支持 θ、q 或 d 轴自动猜测。")
            d, e, f = st.columns(3)
            with d:
                choose_columns = st.checkbox("手动指定列", value=False)
                xcol = st.number_input("角度列（从 1 开始）", value=1, min_value=1, max_value=20)
                ycol = st.number_input("强度列（从 1 开始）", value=2, min_value=1, max_value=20)
                skip = st.number_input("跳过样品开头行数", value=0, min_value=0, max_value=1000)
                rskip = st.number_input("跳过参考开头行数", value=0, min_value=0, max_value=1000)
            with e:
                known = st.checkbox("已确认波长（未知时请勿勾选）", value=demo)
                sw = st.number_input("样品波长 / Å", value=1.5406, min_value=.1, max_value=5., format="%.5f")
                rw = st.number_input("参考波长 / Å", value=1.5406, min_value=.1, max_value=5., format="%.5f")
                shift = st.number_input("探索性参考平移范围 ± / °", value=0., min_value=0., max_value=1., step=.05)
            with f:
                lam = st.number_input("AsLS λ", value=1e6, min_value=100., max_value=1e10, format="%.1e")
                p = st.number_input("AsLS p", value=.01, min_value=.001, max_value=.499, format="%.3f")
                overlap = st.slider("最少样品扫描范围覆盖", .1, 1., .5, .05)
            st.caption("平移仅用于探索性匹配，图中保留原始峰位；它不是零点校准。参考谱只裁剪和归一化，不扣背景或平滑。")
        st.subheader("02 / 出图")
        a, b, c = st.columns(3)
        with a:
            chosen = st.selectbox("本次出图样品（所有样品均参与分析）", [n for n, _ in samples])
            sample_label = st.text_input("样品图例（建议短英文）", value="Synthetic sample" if demo else "Sample")
        with b:
            plot_refs = st.multiselect("叠加参考谱（最多 7 个）", [n for n, _ in refs], default=[n for n, _ in refs[:3]])
            mode = st.selectbox("排列方式", ["stacked", "overlay"], format_func=lambda s:"上下错位排列" if s=="stacked" else "同轴叠加")
        with c:
            width = st.selectbox("成图宽度 / mm", [180, 88, 120])
            st.caption("PDF / SVG 保留矢量与可编辑文字；PNG / TIFF 为 600 dpi。")
        reference_labels = {}
        reference_info = {}
        if refs:
            with st.expander("参考谱英文图例（与原文件对应保存在导出包）"):
                for index, (name, _) in enumerate(refs, 1):
                    stem = Path(name).stem
                    # Use an ASCII figure label when the source filename needs other fonts.
                    default_label = stem if stem.isascii() else f"Reference {index}"
                    reference_labels[name] = st.text_input(name, value=default_label, key="label_"+name)
            with st.expander("参考物相与结构信息（用于分析报告）", expanded=not demo):
                st.caption("填写已知信息即可，未知项留空。CIF 来源声明不会触发结构解析，也不等于已验证结构。")
                for index, (name, _) in enumerate(refs, 1):
                    st.markdown(f"**参考 {index}：{name}**")
                    left, right = st.columns(2)
                    with left:
                        phase = st.text_input("化合物 / 物相名称", value=f"Synthetic Phase {chr(64+index)}" if demo else "", key="phase_"+name)
                        formula = st.text_input("化学式（未知留空）", key="formula_"+name)
                        structure = st.text_input("结构说明 / 晶型 / 空间群（已知时填写）", key="structure_"+name)
                    with right:
                        from_cif = st.selectbox("是否由 CIF 模拟得到", ["unknown", "yes", "no"],
                            format_func=lambda x:{"unknown":"未知", "yes":"是", "no":"否"}[x], key="cif_"+name)
                        source = st.text_input("来源 / CIF 编号 / 文献或数据库编号", key="source_"+name)
                    reference_info[name] = dict(phase_name=phase.strip(), formula=formula.strip(),
                                               structure=structure.strip(), from_cif=from_cif, source=source.strip(),
                                               identity_basis="user_declaration_unverified")
        run = st.form_submit_button("运行分析并生成图谱", type="primary", width="stretch")
    if run:
        st.session_state.pop("analysis_result", None)
        try:
            if len(plot_refs) > 7:
                raise ValueError("每张图最多选择 7 个参考谱。")
            with st.spinner("解析、处理、匹配与检查导出图谱…"):
                cols = (xcol-1, ycol-1) if choose_columns else None
                sample_raw = [parse_bytes(data, name, sw if known else None, cols, skip) for name, data in samples]
                ref_raw = [parse_bytes(data, name, rw if known else None, cols, rskip) for name, data in refs]
                if demo:
                    sample_raw = [replace(p, kind="synthetic") for p in sample_raw]
                    ref_raw = [replace(p, kind="synthetic_reference") for p in ref_raw]
                else:
                    ref_raw = [replace(p, kind="user_reference") for p in ref_raw]
                recipe = Recipe(lower, upper, baseline, lam, p, 10, window if smooth else 0, 3, norm)
                ref_recipe = Recipe(lower=lower, upper=upper, normalization=norm)
                processed = [process(p, recipe) for p in sample_raw]
                processed_refs = [process(p, ref_recipe) for p in ref_raw]
                options = MatchOptions(tol, prom, spacing, shift, overlap)
                comparisons = {}
                for pat in processed:
                    ranked, rejected = rank_references(pat, processed_refs, options)
                    comparisons[pat.name] = {"ranked":ranked, "rejected":rejected}
                target = next(p for p in processed if p.name == chosen)
                plot_patterns = [target]+[p for name in plot_refs for p in processed_refs if p.name == name]
                labels = [sample_label]+[reference_labels[p.name] for p in plot_patterns[1:]]
                peaks = detect_peaks(target, prom, spacing)
                recipe_record = {"sample":asdict(recipe), "reference":asdict(ref_recipe), "matching":asdict(options),
                                 "all_sample_records":[p.info() for p in processed],
                                 "all_reference_records":[p.info() for p in processed_refs]}
                bundle, meta, plots = make_bundle(plot_patterns, samples+refs, recipe=recipe_record,
                            comparisons=comparisons, peaks=peaks, mode=mode, width_mm=width, labels=labels, analysis_patterns=processed+processed_refs,
                            measurement_pattern=next(p for p in sample_raw if p.name == chosen), reference_info=reference_info)
                st.session_state.analysis_result = dict(bundle=bundle, meta=meta, plots=plots,
                      comparisons=comparisons, peaks=peaks, target=target.name, rows=len(target.x),
                      sample_count=len(samples), reference_count=len(refs), demo=demo)
        except (ValueError, OSError, RuntimeError) as exc:
            st.error(str(exc))
    result = st.session_state.get("analysis_result")
    if not result:
        return
    st.divider()
    st.subheader("03 / 上次运行结果")
    st.caption(f"样品：{result['target']} · 修改上方设置后，点击运行以更新结果。")
    if result["demo"]:
        st.info("当前结果来自合成示例，不代表真实样品、晶体结构或物相鉴定能力验证。")
    a,b,c,d = st.columns(4)
    a.metric("批量样品", result["sample_count"])
    b.metric("参考谱", result["reference_count"])
    c.metric("当前图谱点数", f"{result['rows']:,}")
    d.metric("选出的衍射峰", len(result["peaks"]))
    t_measure, t1, t_report, t2, t3, t4 = st.tabs(["实测谱图", "对比图", "分析报告", "候选与逐峰证据", "峰表", "处理与质量记录"])
    with t_measure:
        st.image(result["plots"]["measurement"]["png"], width="stretch")
        st.caption("实测单图：保留全部导入点和原始强度，不应用裁剪、扣背景、平滑或归一化。")
        buttons = st.columns(4)
        for col, ext in zip(buttons, ["pdf", "svg", "png", "tiff"]):
            col.download_button("实测 " + ext.upper(), result["plots"]["measurement"][ext], f"xrd-measurement.{ext}", key="measurement_"+ext)
    with t_report:
        report_name = st.selectbox("查看样品报告", list(result["meta"]["reports"]), key="report_sample")
        report = result["meta"]["reports"][report_name]
        st.markdown(report["markdown"])
        st.download_button("下载分析报告 Markdown", report["markdown"], "xrd-report.md", "text/markdown")
        st.download_button("下载报告数据 JSON", json_bytes(report["data"]), "xrd-report.json", "application/json")
    with t1:
        st.image(result["plots"]["png"], width="stretch")
        st.caption("自动检查不替代最终尺寸下的人工检查。比较中优化的平移不会自动应用到图谱。")
        st.download_button("下载完整可复现包 ZIP", result["bundle"], "xrd-analysis.zip", "application/zip", type="primary")
        buttons = st.columns(4)
        for col, ext in zip(buttons, ["pdf","svg","png","tiff"]):
            col.download_button(ext.upper(), result["plots"][ext], f"xrd-comparison.{ext}")
    with t2:
        st.warning("排名仅在已上传的参考库内成立。分数不是概率；高分不能证明纯相，未匹配峰也不能单独证明杂相。")
        for name, comp in result["comparisons"].items():
            st.markdown(f"**{name}**")
            if comp["ranked"]:
                table = [{"候选参考谱":r["reference"], "分数（0–1）":round(r["score"],4),
                          "峰位 F1":round(r["peak_f1"],3), "轮廓余弦":round(r["profile_cosine"],3),
                          "匹配峰数":r["matched_count"], "证据状态":"候选" if r["status"]=="candidate_only" else "无峰位支持", "范围覆盖":round(r["overlap_fraction"],3),
                          "探索平移 / °":round(r["reference_shift_deg"],4)} for r in comp["ranked"]]
                st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
                for r in comp["ranked"]:
                    with st.expander(f"逐峰证据 · {r['reference']}"):
                        for warning in r["warnings"]:
                            st.warning(warning)
                        st.dataframe(pd.DataFrame(r["matched_peaks"]), hide_index=True)
                        st.write("未匹配实验峰 / °", r["unmatched_observed_deg"])
                        st.write("缺失参考峰 / °", r["missing_reference_deg"])
                        st.write("共同范围外的实验峰 / °", r["outside_overlap_observed_deg"])
                        st.write("未经平移的分数", r["unshifted_score"])
            else:
                st.info("没有可比较的参考结果。")
            for rejected in comp["rejected"]:
                st.error(f"{rejected['reference']}：{rejected['reason']}")
    with t3:
        st.dataframe(pd.DataFrame(result["peaks"]), hide_index=True, width="stretch")
        st.caption("宽度为半突出度宽度，未经仪器展宽校正，不直接作为晶粒尺寸计算的 FWHM。d 间距仅在波长已声明时计算。")
    with t4:
        st.json(result["meta"])
        st.download_button("下载处理与来源记录", json_bytes(result["meta"]), "manifest.json", "application/json")


if __name__ == "__main__":
    main()
