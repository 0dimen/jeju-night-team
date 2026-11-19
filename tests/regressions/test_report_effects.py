"""문서의 합성 100m 직선 손계산·불변조건. 실제 제보/안전 정답이 아님."""
from copy import deepcopy
import json
import subprocess
import sys

import pytest
from agent.data.report_effects import ReportEffectPolicy, compare_report_effects

GRAPH = {'center': [126, 33], 'scale': [100000, 100000]}
NOW = '2026-11-20T07:45:00+09:00'
POLICY = ReportEffectPolicy(10, 2)
REPORT = dict(id='SYNTHETIC-1', status='APPROVED', resolved=False, kind='light_failure',
    approved_by='검토자 예시', evidence_ref='합성 검사', approved_at='2026-11-20T07:00:00+09:00',
    valid_from='2026-11-20T07:00:00+09:00', valid_until='2026-11-21T07:00:00+09:00',
    coordinates=[126.0005, 33])


def baseline():
    rows = []
    for rid, lat, cost in [('A', 33, 100), ('B', 33.001, 130)]:
        rows.append(dict(id=rid, coordinates=[[126, lat], [126.001, lat]], comparison_cost=cost,
            duration_minutes=1 if rid == 'A' else 2, distance_m=100,
            cctv_percent=20, light_percent=30, eligible_for_recommendation=True))
    return dict(routes=rows, recommended_route_id='A', preference='both')


def calculate(reports=None, data=None, policy=POLICY, now=NOW):
    return compare_report_effects(baseline() if data is None else data,
        [deepcopy(REPORT)] if reports is None else reports, policy, as_of=now, graph=GRAPH)


def test_union_length_hand_calculation_changes_candidate_not_operational_recommendation():
    data = baseline(); original = deepcopy(data)
    result = calculate(data=data)
    effect = result['routes'][0]['report_effect']
    assert effect['affected_length_m'] == pytest.approx(20, abs=1e-4)
    assert effect['adjusted_cost'] == pytest.approx(140, abs=1e-4)
    assert result['report_comparison']['recommended_route_id'] == 'B'
    assert result['recommended_route_id'] == 'A' and data == original
    assert result['routes'][0]['cctv_percent'] == 20


def test_overlap_does_not_double_count_and_nonoverlap_adds():
    second = {**REPORT, 'id': 'SYNTHETIC-2'}
    assert calculate([REPORT, second])['routes'][0]['report_effect']['adjusted_cost'] == 140
    second['coordinates'] = [126.0008, 33]
    assert calculate([REPORT, second])['routes'][0]['report_effect']['adjusted_cost'] == 180


@pytest.mark.parametrize('change', [dict(status='UNDER_REVIEW'), dict(resolved=True),
    dict(kind='unspecified'), dict(approved_at='2026-11-20T08:00:00+09:00'),
    dict(valid_from='2026-11-20T08:00:00+09:00'),
    dict(valid_until=NOW), dict(coordinates=[127, 33])])
def test_inactive_or_distant_report_does_not_change_cost(change):
    result = calculate([{**REPORT, **change}])
    assert result['routes'][0]['report_effect']['adjusted_cost'] == 100
    assert result['report_comparison']['recommended_route_id'] == 'A'


def test_no_reports_and_zero_weight_preserve_cost():
    for result in (calculate([]), calculate(policy=ReportEffectPolicy(10, 0))):
        assert result['routes'][0]['report_effect']['adjusted_cost'] == 100


def test_detour_eligibility_and_fastest_are_preserved():
    data = baseline(); data['routes'][1]['eligible_for_recommendation'] = False
    assert calculate(data=data)['report_comparison']['recommended_route_id'] == 'A'
    data = baseline(); data['preference'] = 'fastest'
    assert calculate(data=data)['report_comparison']['recommended_route_id'] == 'A'


@pytest.mark.parametrize('change', [dict(approved_by=''), dict(evidence_ref=''),
    dict(approved_at='2026-11-20T07:00:00'), dict(coordinates=[True, 33]),
    dict(coordinates=[float('nan'), 33]), dict(valid_until='2020-01-01T00:00:00Z')])
def test_invalid_approved_record_fails_instead_of_assuming_zero(change):
    with pytest.raises(ValueError):
        calculate([{**REPORT, **change}])


@pytest.mark.parametrize('policy', [ReportEffectPolicy(0, 1), ReportEffectPolicy(10, -1),
    ReportEffectPolicy(float('nan'), 1), ReportEffectPolicy(10, True)])
def test_invalid_policy_fails(policy):
    with pytest.raises(ValueError):
        calculate(policy=policy)


def test_duplicate_ids_and_missing_route_metrics_fail():
    with pytest.raises(ValueError):
        calculate([REPORT, REPORT])
    data = baseline(); data['routes'][0]['comparison_cost'] = None
    with pytest.raises(ValueError):
        calculate(data=data)
    data = baseline(); data['routes'][0]['coordinates'] *= 0
    with pytest.raises(ValueError):
        calculate(data=data)


def test_route_order_does_not_break_ties():
    data = baseline(); data['routes'][1]['comparison_cost'] = 100
    forward = calculate([], data=data)
    data['routes'].reverse()
    assert calculate([], data=data)['report_comparison'] == forward['report_comparison']


def test_cli_local_file_and_exclusive_private_output(tmp_path):
    source = tmp_path / 'input.json'; output = tmp_path / 'output.json'
    source.write_text(json.dumps(dict(result=baseline(), reports=[REPORT], graph=GRAPH)))
    command = [sys.executable, 'scripts/compare_reviewed_reports.py', '--input', str(source),
        '--output', str(output), '--radius-m', '10', '--weight', '2', '--as-of', NOW]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0
    assert json.loads(output.read_text())['report_comparison']['recommended_route_id'] == 'B'
    assert output.stat().st_mode & 0o777 == 0o600
    assert subprocess.run(command, capture_output=True).returncode == 2


def test_selected_route_internal_hook_with_stub_api(monkeypatch):
    from types import SimpleNamespace
    import agent.data.selected_routes as selected
    context = SimpleNamespace(graph=GRAPH)
    monkeypatch.setattr(selected, 'selected_context', lambda *args: context)
    monkeypatch.setattr(selected, 'compare', lambda *args: {**baseline(), 'limitations': []})
    monkeypatch.setattr(selected, 'public_points', lambda *args: [])
    result = selected.selected_compare([126, 33], [126.001, 33], '2026-11-20T22:00',
        reviewed_reports=[REPORT], report_policy=POLICY, report_as_of=NOW)
    assert result['report_comparison']['recommended_route_id'] == 'B'
    normal = selected.selected_compare([126, 33], [126.001, 33], '2026-11-20T22:00')
    assert 'report_comparison' not in normal


def test_invalid_projection_is_not_a_zero_effect():
    with pytest.raises(ValueError):
        compare_report_effects(baseline(), [REPORT], POLICY, as_of=NOW,
            graph={"center": [126, 33], "scale": [float("nan"), 100000]})
