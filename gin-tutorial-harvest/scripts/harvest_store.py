"""Provenance records and coverage manifests; never infer success from raw files."""
import hashlib
import json
from pathlib import Path
from source_coverage import coverage_report, normalize_url


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(root):
    path = Path(root) / 'harvest-records.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError('harvest-records.json 必须为对象')
    return data


def record(root, src, **result):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    data = records(root)
    key = normalize_url(src['url'])
    old = data.get(key, {})
    history = old.get('history', []) + [result]
    data[key] = {**old, **src, **result, 'history': history}
    (root / 'harvest-records.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def local_file(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if (root not in path.parents or path.suffix != '.md'
            or path.name.endswith('.raw.md') or not path.is_file()):
        raise ValueError('只接受资料库内的成品 .md，不接受临时 raw 文件或越界路径')
    return path


def acceptance(total, target_words, coverage, mode='full'):
    if mode not in ('full', 'focused') or target_words < 1:
        raise ValueError('mode 须为 full/focused，target_words 须为正数')
    needed = target_words * 3 if mode == 'full' else 1
    gaps = [q for q, n in coverage.items() if n < (2 if mode == 'full' else 1)]
    if not coverage:
        gaps = ['未提供覆盖问题清单']
    return {'material_ok': total >= needed, 'coverage_gaps': gaps,
            'needed_chars': max(0, needed - total), '达标线': needed, 'mode': mode}


def build_manifest(root, topic, sources, target_words=8000, mode='full', sources_path=None):
    root = Path(root).resolve()
    if not isinstance(sources, dict) or not isinstance(sources.get('sources', []), list):
        raise ValueError('sources.json 须为对象，sources 须为数组')
    if any(not isinstance(s, dict) or not isinstance(s.get('url'), str) or not s['url']
           for s in sources.get('sources', [])):
        raise ValueError('每个来源须带非空 URL')
    planned = {normalize_url(s['url']): s for s in sources.get('sources', [])}
    saved = records(root)
    entries, total, seen = [], 0, set()
    for key in sorted(set(planned) | set(saved)):
        original = saved.get(key, {})
        entry = {**planned.get(key, {}), **original}
        # Only explicit descriptive metadata may be updated by the source map.
        for field in ('covers', 'original_source_id', 'redundant_with', '替补自'):
            if field in planned.get(key, {}):
                entry[field] = planned[key][field]
        entry['覆盖问题'] = entry.get('covers', original.get('覆盖问题', []))
        entry['status'] = original.get('status', 'not_collected')
        if entry['status'] == 'ok':
            try:
                path = local_file(root, entry['path'])
                if digest(path) != entry.get('sha256') or path in seen:
                    raise ValueError('资料改变或文件重复，须重新登记')
                if not entry.get('redundant_with'):
                    seen.add(path)
                    total += entry['字数']
            except (OSError, ValueError, KeyError) as exc:
                entry.update(status='invalid', reason=str(exc))
        entries.append(entry)
    questions = sources.get('questions') or sources.get('coverage_check', {}).get('高频问题') or []
    coverage = coverage_report(entries, questions, mode) if questions else None
    dependencies = set(seen)
    registry = root / 'harvest-records.json'
    if registry.is_file():
        dependencies.add(registry)
    if sources_path:
        dependencies.add(Path(sources_path).resolve())
    result = {'schema_version': 2, 'topic': topic, 'target_words': target_words,
              '总字数': total, 'entries': entries,
              '观察哨': [e['url'] for e in entries if e.get('value') == 'unknown'],
              'coverage': coverage,
              '验收': acceptance(total, target_words, coverage['已覆盖来源数'] if coverage else {}, mode),
              'inputs': [{'path': str(p), 'sha256': digest(p)} for p in sorted(dependencies)]}
    (root / 'coverage-manifest.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
