"""Deterministic evidence reports; no model calls, phase database or invented identity."""
from __future__ import annotations
import re
from .core import detect_peaks
from .matching import MatchOptions


def safe_text(value):
    """Keep user/file labels as literal Markdown text, not report instructions."""
    value = str(value or "").replace("\n", " ").replace("\r", " ")
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|])", r"\\\1", value)


def build_report(sample, comparison, options=MatchOptions(), reference_info=None, raw_points=None):
    """Return structured and Markdown evidence for a single processed scan."""
    reference_info = reference_info or {}
    peaks = detect_peaks(sample, options.prominence, options.min_peak_distance_deg)
    main = sorted(peaks, key=lambda p: (-p["prominence"], p["two_theta_deg"]))[:10]
    ranked = comparison.get("ranked", [])
    rejected = comparison.get("rejected", [])
    main_rows = []
    for peak in main:
        assignments = []
        for candidate in ranked:
            for pair in candidate["matched_peaks"]:
                if abs(pair["observed_deg"]-peak["two_theta_deg"]) < 1e-8:
                    identity = reference_info.get(candidate["reference"], {})
                    assignments.append({"reference": candidate["reference"],
                        "phase_name": identity.get("phase_name", ""), "formula": identity.get("formula", ""),
                        "reference_original_deg": pair["reference_original_deg"],
                        "reference_shifted_deg": pair["reference_shifted_deg"], "delta_deg": pair["delta_deg"],
                        "identity_basis": "user_declaration_unverified"})
        main_rows.append({**peak, "candidate_assignments": assignments,
            "assignment_status": "ambiguous_multiple_references" if len(assignments)>1 else
                                 "candidate_only" if assignments else "unassigned"})
    supported = [r for r in ranked if r["matched_count"] > 0]
    best = supported[0] if supported else None
    structure = {"status": "not_determined", "candidate_reference": None,
                 "statement": "当前信息不足以给出具体晶体结构；未执行指标化、结构求解或精修。"}
    if best:
        info = reference_info.get(best["reference"], {})
        enough_peaks = best["matched_count"] >= 3
        structure.update({"candidate_reference": best["reference"], "user_declared_identity": info,
                          "status": "reference_candidate" if enough_peaks else "insufficient_peak_support"})
        if enough_peaks:
            structure["statement"] = (f"在已上传参考库内，{best['reference']} 是有峰位支持的最高排名候选，"
                f"有 {best['matched_count']} 对峰对应。该结果仅支持将其列为参考物相/结构候选，"
                "尚不能认定样品具有相同化学组成、空间群、晶胞或原子连接方式。")
        else:
            structure["statement"] = (f"最高排名的有峰位支持参考为 {best['reference']}，"
                f"但只有 {best['matched_count']} 对峰对应，证据不足以推断结构类型。")
    warnings = list(dict.fromkeys(w for r in ranked for w in r.get("warnings", [])))
    data = {"engine": "local_deterministic_rules", "api_calls": 0,
            "sample": sample.name, "sample_kind": sample.kind,
            "raw_points": raw_points, "processed_points": len(sample.x),
            "range_deg": [float(sample.x[0]), float(sample.x[-1])],
            "wavelength_angstrom": sample.wavelength, "processing": list(sample.history),
            "detected_peak_count": len(peaks), "main_peak_definition": "top_10_by_prominence",
            "main_peaks": main_rows, "reference_info": reference_info,
            "ranked_candidates": ranked, "rejected_references": rejected,
            "structure_hypothesis": structure, "warnings": warnings,
            "boundaries": {"phase_identity_verified": False, "structure_solved": False,
                           "phase_fractions_estimated": False, "hkl_indexing_performed": False}}
    lines = [f"# XRD 分析报告 · {safe_text(sample.name)}", "",
             "本报告依据所选处理参数和参考谱生成。物相名称与结构信息由用户提供，尚未独立核验。", ""]
    if "synthetic" in sample.kind:
        lines += ["**数据性质：合成演示谱线，不代表真实物相。**", ""]
    lines += ["## 数据与处理", "",
              f"- 原始点数：{raw_points if raw_points is not None else '未提供'}；用于分析的点数：{len(sample.x)}。",
              f"- 分析范围：{sample.x[0]:.5f}–{sample.x[-1]:.5f}°（2θ）。",
              f"- 波长：{f'{sample.wavelength:.5f} Å（用户声明）' if sample.wavelength else '未知；无法核实波长可比性，不计算 d 间距'}。",
              "- 实测单图保留原始强度与所有导入点；对比图和本报告使用所选处理参数。", ""]
    if sample.history:
        for step in sample.history:
            operation = step["operation"]
            if operation == "crop":
                description = f"裁剪：{step['rows_before']} → {step['rows_after']} 点"
            elif operation == "normalize":
                description = f"归一化：{step['method']}；除数 {step['divisor']:.8g}；范围为保留区间"
            elif operation == "savitzky_golay":
                description = f"Savitzky–Golay 平滑：{step['window_points']} 点、{step['polynomial_order']} 阶"
            elif operation == "asymmetric_least_squares":
                description = f"AsLS 扣背景：λ={step['lambda']:.5g}，p={step['p']}，{step['iterations']} 次迭代；负值保留"
            else:
                description = "角度升序整理，强度同步排序"
            lines.append(f"- {description}。")
    else:
        lines.append("- 未施加数值处理。")
    lines += ["", "## 主要峰与候选归属", "",
        f"共检出 {len(peaks)} 个峰。以下列出突出度最高的至多 10 个峰；突出度阈值为信号范围的 {options.prominence:.1%}，最小峰间距 {options.min_peak_distance_deg:.3f}°。",
        "表中归属只表示在指定容差内与参考峰对应；一个峰对应多个参考时全部列出。不能把单个衍射峰直接当作某种元素的检测证据。", "",
        "| 2θ / ° | 处理后强度 | d / Å | 半突出度宽度 / ° | 候选对应（用户声明） |",
        "|---:|---:|---:|---:|---|"]
    for peak in main_rows:
        attribution = []
        for a in peak["candidate_assignments"]:
            phase = a["phase_name"] or "物相名未知"
            formula = f"，{a['formula']}" if a["formula"] else ""
            attribution.append(safe_text(f"{phase}{formula} [{a['reference']}]，Δ2θ={a['delta_deg']:+.4f}°"))
        d = f"{peak['d_angstrom']:.5f}" if peak["d_angstrom"] is not None else "—"
        lines.append(f"| {peak['two_theta_deg']:.5f} | {peak['intensity']:.6g} | {d} | {peak['width_half_prominence_deg']:.5f} | {'；'.join(attribution) or '未分配：无已提供参考峰对应'} |")
    if not main_rows:
        lines += ["", "未检出满足当前参数的峰，无法进行主要峰归属。"]
    lines += ["", "## 参考物相与结构线索", ""]
    if not ranked:
        lines += ["没有可比较的参考谱结果，因此不输出具体成分或结构候选。", ""]
    for i, candidate in enumerate(ranked, 1):
        identity = reference_info.get(candidate["reference"], {})
        name = identity.get("phase_name") or "未知"
        formula = identity.get("formula") or "未知"
        origin = {"yes":"用户声明由 CIF 模拟", "no":"用户声明非 CIF 来源", "unknown":"未知"}.get(identity.get("from_cif"), "未知")
        lines += [f"### {i}. {safe_text(candidate['reference'])}", "",
            f"- 用户声明物相：{safe_text(name)}；化学式：{safe_text(formula)}。",
            f"- 用户声明结构信息：{safe_text(identity.get('structure') or '未提供')}。",
            f"- CIF 来源：{origin}；来源/编号：{safe_text(identity.get('source') or '未提供')}。",
            f"- 启发式分数 {candidate['score']:.4f}（不是概率）；匹配 {candidate['matched_count']} 对峰；实验峰覆盖率 {candidate['observed_peak_coverage']:.1%}；参考峰召回率 {candidate['reference_peak_recall']:.1%}。",
            f"- 共同范围覆盖实验角度跨度的 {candidate['overlap_fraction']:.1%}；共同范围内有 {len(candidate['unmatched_observed_deg'])} 个实验峰未匹配，{len(candidate['missing_reference_deg'])} 个参考峰未出现。",
            f"- 探索性参考平移：{candidate['reference_shift_deg']:+.4f}°；图谱未应用该平移。", ""]
        if identity.get("from_cif") == "yes":
            lines += ["仅记录 CIF 来源声明；本程序没有读取该 CIF，因此不能自动验证晶胞、空间群或 hkl。", ""]
    lines += ["### 结构推测结论", "", safe_text(structure["statement"]), "",
              "即使参考物相名称已填写，也不能仅凭当前排名认定样品成分、纯度或同构关系。未匹配峰须进一步解释；当前不提供定量物相比例。", ""]
    if warnings or rejected:
        lines += ["## 可比性与待核实项", ""]
        for warning in warnings:
            lines.append(f"- {safe_text(warning)}")
        for item in rejected:
            lines.append(f"- 参考谱 {safe_text(item['reference'])} 未参与有效比较：{safe_text(item['reason'])}")
        lines.append("")
    lines += ["## 建议下一步", "",
              "- 确认样品与参考谱的辐射波长、扫描坐标和测量/模拟条件。",
              "- 补充参考物相名称、化学式及结构来源；有 CIF 时结合其预测峰与 hkl 核对。",
              "- 检查主要峰、未匹配峰以及背景/平滑参数的影响；不要将噪声峰自动归为杂相。",
              "- 具体结构、空间群、晶胞和混相含量需要相应的晶体学分析或精修进一步验证。", ""]
    return {"data": data, "markdown": "\n".join(lines)}
