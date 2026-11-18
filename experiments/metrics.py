from collections import defaultdict
from statistics import mean


def summarize(rows,config,manifest):
    tasks={}
    for task in ('intent','report','explain','flow'):
        selected=[r for r in rows if r['task']==task]
        scored=[r for r in selected if not r['ambiguous'] and r.get('correct') is not None]
        groups=defaultdict(list)
        for r in selected: groups[r['case_id']].append(r)
        repeated=[v for v in groups.values() if len(v)>=3]
        tasks[task]={'observations':len(selected),'unique_cases':len(groups),'scored':len(scored),
                     'ambiguous_observations':sum(r['ambiguous'] for r in selected),
                     'accuracy':mean(r['correct'] for r in scored) if scored else None,
                     'slot_accuracy':mean(r['slot_accuracy'] for r in scored if 'slot_accuracy' in r) if any('slot_accuracy' in r for r in scored) else None,
                     'mean_seconds':mean(r['elapsed_seconds'] for r in selected) if selected else None,
                     'max_seconds':max((r['elapsed_seconds'] for r in selected),default=None),
                     'repeated_cases':len(repeated),
                     'reproducibility':mean(len({r['output_hash'] for r in group})==1 for group in repeated) if repeated else None}
    calls=[call for row in rows for call in row.get('provider_records',[])]
    uncached=[c for c in calls if not c.get('cache_hit')]
    explanation_rows=[r for r in rows if r['task']=='explain']
    return {'name':config['name'],'config':config,'manifest':manifest,'tasks':tasks,
            'observations':len(rows),'rule_violations':sum(bool(r.get('rule_issues')) for r in rows),
            'failures':sum(bool(r.get('error')) for r in rows),
            'provider_failures':sum(bool(c.get('error')) for c in calls),
            'fallbacks':sum(r.get('fallback',False) for r in rows),
            'explain_fallback_rate':mean(r.get('fallback',False) for r in explanation_rows) if explanation_rows else None,
            'provider_calls':len(calls),'uncached_calls':len(uncached),'cached_calls':len(calls)-len(uncached),
            'uncached_model_mean_seconds':mean(c['elapsed_seconds'] for c in uncached) if uncached else None,
            'input_tokens':sum(c.get('input_tokens') or 0 for c in uncached),
            'output_tokens':sum(c.get('output_tokens') or 0 for c in uncached),
            'thinking_tokens':sum(c.get('thinking_tokens') or 0 for c in uncached),
            'actual_models':sorted({c.get('actual_model',c.get('model','')) for c in calls if c.get('model')}),
            'eliminated':any(r.get('rule_issues') for r in rows)}
