"""Behavioral regressions for discovery, collection and simplified v3 authoring."""
import importlib.util
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pipeline_fixture import ROOT, build, draft, flow, outline_module
from tutorial_contract import read_json, contains_display_text


def load(name, skill, script):
    path = ROOT / skill / 'scripts' / script
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pipeline = load('research_pipeline', 'gin-question', 'pipeline.py')
harvest = load('research_harvest', 'gin-tutorial-harvest', 'harvest.py')
scan = load('research_scan', 'gin-tutorial-source-scan', 'source_scan.py')
from saturation_checker import retrieval_state
from query_generator import generate
from parallel_agents import agent_manifest
from source_coverage import coverage_report
from harvest_store import records, build_manifest


def rounds():
    return [{'round': i, 'prev_total': 10, 'new_count': 1} for i in range(1, 4)]


def test_empty_retrieval_is_not_saturated(tmp_path):
    result = pipeline.run({'topic': '配置工具', 'search_results': []}, str(tmp_path))
    assert result['exit_reason'] == 'needs_backfill'
    assert not result['complete'] and len(result['unresolved_cells']) == 16
    assert not read_json(tmp_path / 'problem_list.json')['complete']


def test_saturation_requires_coverage_rounds_and_budget():
    assert retrieval_state({'missing': []}, [])['exit_reason'] == 'needs_more_rounds'
    assert retrieval_state({'missing': []}, rounds())['complete']
    assert not retrieval_state({'missing': [('基础', 'Why')]}, rounds())['complete']
    assert retrieval_state({'missing': []}, rounds(), 100)['exit_reason'] == 'budget_exhausted'


def test_backfill_does_not_count_as_saturation_and_needs_two_attempts():
    missing = {'missing': [('基础', 'Why')]}
    history = rounds() + [{'round': 4, 'prev_total': 13, 'new_count': 0,
                           'backfill': True, 'target_cells': ['基础/Why']}]
    assert not retrieval_state(missing, history)['complete']
    history.append({**history[-1], 'round': 5})
    assert retrieval_state(missing, history)['complete']
    assert not retrieval_state(missing, history[3:])['complete']


def test_duplicate_search_hits_do_not_promote_single_source():
    candidate = {'text': '工具如何配置？', 'source_url': 'https://example.org/q',
                 'retrieval_perspective': '基础', 'sub_dimension': 'How'}
    items = pipeline.aggregate_sources([candidate] * 5)
    confirmed, pending = pipeline.apply_frequency_gate(items)
    assert not confirmed and pending[0]['source_count'] == 1
    assert pending[0]['total_frequency'] == 1


def test_incomplete_cli_preserves_results_and_cannot_count_as_stage1(tmp_path):
    manifest = tmp_path / 'input.json'
    manifest.write_text(json.dumps({'topic': '配置工具', 'search_results': []}))
    result = subprocess.run([sys.executable, str(ROOT / 'gin-question/scripts/pipeline.py'),
                             '--manifest', str(manifest), '--output-dir', str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert (tmp_path / 'audit_report.json').exists()
    problem = read_json(tmp_path / 'problem_list.json')
    problem['problems'] = [{'text': '明确问题'}]
    (tmp_path / 'problem_list.json').write_text(json.dumps(problem))
    assert not flow.stage_status(tmp_path)['stage1']['satisfied']


def test_generic_queries_are_domain_neutral_and_health_is_available():
    queries = generate('代理配置', [], [('人群场景', '人群差异')])
    assert all('孕妇' not in q['query'] and '女性' not in q['query'] for q in queries)
    health = agent_manifest('减脂', [], 'health')
    assert any('孕妇' in q[2] for q in health['人群场景'])
    assert scan.grade_source('配置 HTTP 代理', 'https://docs.example.org/proxy')[0] != 'reject'
    assert scan.grade_source('代理加盟月入过万', 'https://example.org')[0] == 'reject'


def test_coverage_threshold_and_independent_origins():
    sources = [{'url': 'https://a.org/1', 'covers': ['问题']},
               {'url': 'https://a.org/2', 'covers': ['问题']}]
    report = coverage_report(sources, ['问题'])
    assert report['已覆盖来源数']['问题'] == 1 and report['gap'] == '问题'
    sources[1].update(url='https://b.org/2', original_source_id='same')
    sources[0]['original_source_id'] = 'same'
    assert coverage_report(sources, ['问题'])['gap'] == '问题'
    sources[1]['original_source_id'] = 'independent'
    assert coverage_report(sources, ['问题'])['gap'] == '无'
    assert coverage_report(sources[:1], ['问题'], 'focused')['gap'] == '无'


def source():
    return {'url': 'https://a.org/guide', 'title': '配置指南', 'layer': 'L1',
            'value': 'high', 'action': '单页采集', 'covers': ['问题']}


def test_manifest_preserves_provenance_ignores_raw_and_rejects_stale_content(tmp_path):
    text = tmp_path / 'guide.md'
    text.write_text('正文内容 ' * 200)
    (tmp_path / 'failed.raw.md').write_text('错误 ' * 10000)
    harvest.register_source(tmp_path, source(), text, 'collector')
    spec = {'questions': ['问题'], 'sources': [source()]}
    result = build_manifest(tmp_path, '测试', spec, mode='focused')
    assert result['验收']['material_ok'] and not result['验收']['coverage_gaps']
    assert len(result['entries']) == 1 and result['总字数'] == 800
    assert result['entries'][0]['url'] == source()['url']
    assert result['entries'][0]['channel'] == 'collector'
    assert result['entries'][0]['覆盖问题'] == ['问题']
    assert build_manifest(tmp_path, '测试', {}, mode='focused')['验收']['coverage_gaps']
    text.write_text('正文改变 ' * 200)
    result = build_manifest(tmp_path, '测试', spec, mode='focused')
    assert result['entries'][0]['status'] == 'invalid' and result['总字数'] == 0


def test_raw_and_path_traversal_cannot_be_registered(tmp_path):
    raw = tmp_path / 'x.raw.md'
    raw.write_text('正文 ' * 1000)
    with pytest.raises(ValueError):
        harvest.register_source(tmp_path, source(), raw, 'collector')
    with pytest.raises(ValueError):
        harvest.organize_path(str(tmp_path), '../outside', 'title')


def test_collector_is_delegated_and_cli_errors_do_not_reuse_old_content(tmp_path, monkeypatch):
    monkeypatch.setattr(harvest, 'load_config', lambda: {})
    monkeypatch.setattr(harvest.subprocess, 'run', lambda *a, **k: pytest.fail('collector should not call firecrawl'))
    with pytest.raises(harvest.HarvestError, match='collector'):
        harvest.harvest_one(tmp_path, {**source(), 'action': 'collector 采集'})
    monkeypatch.setattr(harvest.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=1, stderr='rate limit', stdout=''))
    with pytest.raises(harvest.HarvestError, match='quota'):
        harvest.harvest_one(tmp_path, source())
    assert list(records(tmp_path).values())[0]['status'] == 'quota'


def test_actual_cli_blocked_source_reaches_mirror_after_definitions(tmp_path, monkeypatch):
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[cmd.index('-o') + 1]).write_text('403 blocked' if len(calls) == 1 else '正文 ' * 600)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(subprocess, 'run', run)
    monkeypatch.setattr(sys, 'argv', ['harvest.py', 'harvest-one', '--dir', str(tmp_path),
                                    '--url', 'https://pubmed.ncbi.nlm.nih.gov/37248144/', '--title', '测试'])
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / 'gin-tutorial-harvest/scripts/harvest.py'), run_name='__main__')
    assert exc.value.code == 0 and len(calls) == 2
    assert 'europepmc.org' in ' '.join(calls[1])


def test_whole_site_uses_crawl_and_keeps_page_urls(tmp_path, monkeypatch):
    commands = []
    def run(cmd, **kwargs):
        commands.append(cmd)
        pages = [{'markdown': '正文 ' * 600, 'metadata': {'sourceURL': f'https://a.org/page{i}', 'title': '同名'}}
                 for i in range(2)]
        Path(cmd[cmd.index('-o') + 1]).write_text(json.dumps({'status': 'completed', 'data': pages}))
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(harvest.subprocess, 'run', run)
    monkeypatch.setattr(harvest, 'load_config', lambda: {'firecrawl_api_key': 'synthetic-fixture'})
    harvest.harvest_one(tmp_path, {**source(), 'action': '整站扒取'}, limit=2)
    assert commands[0][3] == 'crawl' and '--limit' in commands[0]
    pages = [e for e in records(tmp_path).values() if e['status'] == 'ok']
    assert len(pages) == 2 and len({e['path'] for e in pages}) == 2
    assert all(e['covers'] == [] for e in pages)  # No fabricated per-page coverage.


def test_outline_review_copy_and_modern_intro_are_not_position_locked(tmp_path):
    build(tmp_path, through='stage5')
    contract = read_json(tmp_path / 'outlines/大纲_Q1.json')
    manifest = read_json(tmp_path / 'answers/answers-manifest.json')
    review = outline_module.render_outline(contract)
    assert '准备终端' in review and 'C-1' not in review and 'L1/print.md' not in review
    text = (tmp_path / 'chapters/ch1.md').read_text()
    text = text.replace('写给：', '\n导语。\n\n阅读说明。\n\n写给：')
    result = draft.check_chapter(text, outline=contract, manifest=manifest, library=str(tmp_path / 'library'))
    assert not result['errors']
    text = text.replace('终端输出记录', '无关的东西')
    result = draft.check_chapter(text, outline=contract, manifest=manifest, library=str(tmp_path / 'library'))
    assert any('交付物' in e for e in result['errors'])


def test_formatting_tolerance_preserves_changed_values_detection():
    assert contains_display_text('检查**标准**输出', '检查标准输出')
    assert not contains_display_text('设置 100 秒', '设置 10 秒')
    assert not contains_display_text('<!-- 设置 10 秒 -->', '设置 10 秒')
    assert contains_display_text('使用 `__name__` 和 `2**3`', '__name__')
    assert not contains_display_text('使用 `name` 和 `23`', '__name__')
    assert contains_display_text('使用 `2**3`', '2**3')
    assert not contains_display_text('使用 `23`', '2**3')


def test_modern_style_warnings_do_not_accumulate_into_failure():
    from qc import check_humanity
    text = '# 示例\n\n' + '说明文字' * 100 + '\n\n让我们看看。这非常重要。十分重要。极其重要。一定成功。\n\n' + '**提示** ' * 20
    report = check_humanity(text, tutorial_type='概念型')
    assert report['score'] < 70 and report['status'] == 'minor'
    broken = check_humanity('# 标题\n\n#### 跳级', tutorial_type='概念型')
    assert broken['status'] == 'fail'


def test_relative_output_directory_and_postprocessed_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(harvest, 'load_config', lambda: {})
    def run(cmd, **kwargs):
        Path(cmd[cmd.index('-o') + 1]).write_text('正文 ' * 600)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(harvest.subprocess, 'run', run)
    output = harvest.harvest_one('library', source())
    assert Path(output).is_absolute() and Path(output).is_file()
    assert list(records('library').values())[0]['status'] == 'ok'


def test_crawl_incomplete_does_not_pass(tmp_path, monkeypatch):
    def run(cmd, **kwargs):
        Path(cmd[cmd.index('-o') + 1]).write_text(json.dumps({'status': 'scraping', 'data': []}))
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(harvest.subprocess, 'run', run)
    monkeypatch.setattr(harvest, 'load_config', lambda: {'firecrawl_api_key': 'synthetic'})
    with pytest.raises(harvest.HarvestError, match='incomplete'):
        harvest.harvest_one(tmp_path, {**source(), 'action': '整站扒取'})
    result = build_manifest(tmp_path, '测试', {'questions': ['问题']}, mode='focused')
    assert not result['验收']['material_ok']
    assert result['entries'][0]['status'] == 'incomplete'


def test_manifest_metadata_change_invalidates_stage0(tmp_path):
    library = tmp_path / 'library'
    library.mkdir()
    text = library / 'guide.md'
    text.write_text('正文内容 ' * 200)
    harvest.register_source(library, source(), text, 'collector')
    spec = {'questions': ['问题'], 'sources': [source()]}
    spec_path = tmp_path / 'sources.json'
    spec_path.write_text(json.dumps(spec))
    build_manifest(library, '测试', spec, mode='focused', sources_path=spec_path)
    assert flow.stage_status(tmp_path)['stage0']['satisfied']
    spec_path.write_text(json.dumps({**spec, 'questions': ['另一个问题']}))
    assert not flow.stage_status(tmp_path)['stage0']['satisfied']


def test_batch_discovery_and_standalone_collection_cli(tmp_path):
    scan_scripts = tmp_path / 'scan'
    harvest_scripts = tmp_path / 'harvest'
    shutil.copytree(ROOT / 'gin-tutorial-source-scan/scripts', scan_scripts)
    shutil.copytree(ROOT / 'gin-tutorial-harvest/scripts', harvest_scripts)
    candidates = tmp_path / 'candidates.json'
    good = {**source(), 'title': '配置 HTTP 代理', 'url': 'https://docs.example.org/guide'}
    candidates.write_text(json.dumps([good, {'title': '代理加盟月入过万', 'url': 'https://spam.example.org'}]))
    sources = tmp_path / 'sources.json'
    sources.write_text(json.dumps({'topic': '工具', 'sources': [], 'rejected': []}))
    def cli(script, *args):
        result = subprocess.run([sys.executable, str(script), *map(str, args)], cwd=tmp_path,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    cli(scan_scripts / 'source_scan.py', 'ingest', '--file', sources, '--input', candidates)
    assert len(read_json(sources)['sources']) == 1 and len(read_json(sources)['rejected']) == 1
    cli(scan_scripts / 'source_scan.py', 'coverage', '--file', sources, '--questions', '问题', '--mode', 'focused', '--save')
    assert read_json(sources)['coverage_check']['gap'] == '无'
    library = tmp_path / 'library'
    library.mkdir()
    (library / 'doc.md').write_text('正文内容 ' * 200)
    single = tmp_path / 'source.json'
    single.write_text(json.dumps(good))
    cli(harvest_scripts / 'harvest.py', 'register', '--dir', library, '--file', 'doc.md', '--source-json', single, '--channel', 'collector')
    cli(harvest_scripts / 'harvest.py', 'manifest', '--dir', library, '--topic', '工具', '--sources', sources, '--mode', 'focused')
    assert flow.stage_status(tmp_path)['stage0']['satisfied']


def test_generated_outline_cli_report_binds_review_copy(tmp_path):
    from tutorial_contract import current_report
    build(tmp_path, through='stage4')
    markdown = tmp_path / 'outlines/review.md'
    report = tmp_path / 'checks/ch1.outline.json'
    result = subprocess.run([sys.executable, str(ROOT / 'gin-outline/scripts/outline.py'), 'check',
                             '--outline', str(tmp_path / 'outlines/大纲_Q1.json'),
                             '--manifest', str(tmp_path / 'answers/answers-manifest.json'),
                             '--library', str(tmp_path / 'library'), '--output', str(report),
                             '--markdown', str(markdown)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert current_report(read_json(report), [markdown], 'outline')
    markdown.write_text('不再是审核过的目录')
    assert not current_report(read_json(report), [markdown], 'outline')
