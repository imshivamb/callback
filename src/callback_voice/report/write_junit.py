import xml.etree.ElementTree as ET
from pathlib import Path

from callback_voice.core.models.baseline_diff import BaselineDiff
from callback_voice.core.models.run_result import RunResult
from callback_voice.core.models.scenario_result import ScenarioResult


def write_junit(result: RunResult, path: Path) -> None:
    """``junit.xml`` for CI test reporters: one testsuite per scenario.

    Each trial is a testcase (``error`` when the call could not run), then one testcase
    per thresholded aggregate and one per baseline comparison. A trial that failed on
    its own inside a scenario that passes on its aggregates (one missed task in five
    against a 0.8 rate) is not a failure; its reasons go to ``system-out``.
    """
    root = ET.Element("testsuites", name="callback", time=f"{result.duration_s:.2f}")
    diffs: dict[str, list[BaselineDiff]] = {}
    for d in result.baseline_diff:
        diffs.setdefault(d.scenario_id, []).append(d)
    for scenario in result.scenarios:
        root.append(_suite(scenario, diffs.get(scenario.scenario_id, [])))
    for key in ("tests", "failures", "errors"):
        root.set(key, str(sum(int(s.get(key, "0")) for s in root)))
    tree = ET.ElementTree(root)
    ET.indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _suite(scenario: ScenarioResult, diffs: list[BaselineDiff]) -> ET.Element:
    sid = scenario.scenario_id
    suite = ET.Element("testsuite", name=sid)
    for t in scenario.trials:
        duration = t.call.duration_s if t.call else 0.0
        case = ET.SubElement(
            suite,
            "testcase",
            classname=sid,
            name=f"trial {t.trial} ({t.call_id})",
            time=f"{duration:.2f}",
        )
        if t.error is not None:
            ET.SubElement(case, "error", message=t.error.splitlines()[0]).text = t.error
        elif not t.passed and not scenario.passed:
            _failure(case, t.failure_reasons)
        elif not t.passed:
            ET.SubElement(case, "system-out").text = (
                "This call failed on its own, but the scenario passes on its aggregates:\n"
                + "\n".join(t.failure_reasons)
            )
    for a in scenario.aggregates:
        if a.passed is None:
            continue
        case = ET.SubElement(suite, "testcase", classname=sid, name=f"aggregate {a.name}")
        if not a.passed:
            ci = f" (95% CI {a.ci_low:g}–{a.ci_high:g})" if a.ci_low is not None else ""
            _failure(case, [f"{a.name} {a.value:g}{ci}, limit {a.comparator} {a.threshold:g}"])
    for d in diffs:
        if d.direction in ("new", "missing"):
            continue
        case = ET.SubElement(suite, "testcase", classname=sid, name=f"baseline {d.metric}")
        if d.regressed:
            _failure(
                case,
                [f"{d.metric} regressed: {d.baseline:g} → {d.current:g} (Δ {d.delta:+g})"],
            )
    cases = suite.findall("testcase")
    suite.set("tests", str(len(cases)))
    suite.set("failures", str(sum(c.find("failure") is not None for c in cases)))
    suite.set("errors", str(sum(c.find("error") is not None for c in cases)))
    return suite


def _failure(case: ET.Element, reasons: list[str]) -> None:
    first = reasons[0] if reasons else "failed"
    ET.SubElement(case, "failure", message=first).text = "\n".join(reasons) or first
