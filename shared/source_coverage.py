"""Shared discovery/harvest coverage policy. Vendored for standalone skills."""
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def normalize_url(url):
    p = urlparse(url)
    return urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/') or '/',
                       '', urlencode([(k, v) for k, v in parse_qsl(p.query)
                                      if not k.startswith('utm_')]), ''))


def coverage_report(sources, questions, mode='full'):
    """Conservative origin groups; keyword fallback is only a discovery hint."""
    if mode not in ('full', 'focused'):
        raise ValueError('mode 必须为 full/focused')
    if not isinstance(questions, list) or not questions or any(
            not isinstance(q, str) or not q.strip() for q in questions):
        raise ValueError('必须显式提供非空覆盖问题清单')
    questions = list(dict.fromkeys(q.strip() for q in questions))
    valid = [s for s in sources if s.get('status', 'ok') == 'ok'
             and not s.get('redundant_with') and s.get('url')]
    # Merge connected identities: same host OR explicitly same original source.
    groups = []
    for source in valid:
        host = (urlparse(source['url']).hostname or '').lower().removeprefix('www.')
        if not host:
            continue
        keys = {'host:' + host}
        if source.get('original_source_id'):
            keys.add('origin:' + source['original_source_id'])
        matches = [g for g in groups if g[0] & keys]
        members = [source]
        for group in matches:
            keys |= group[0]
            members += group[1]
            groups.remove(group)
        groups.append((keys, members))

    def covers(source, question):
        explicit = source.get('覆盖问题', source.get('covers'))
        if explicit is not None:
            if not isinstance(explicit, list) or any(not isinstance(q, str) for q in explicit):
                raise ValueError('覆盖问题/covers 必须是字符串数组')
            return question in explicit
        return question in (source.get('note', '') + source.get('title', ''))

    counts = {q: sum(any(covers(s, q) for s in members) for _, members in groups)
              for q in questions}
    minimum = 2 if mode == 'full' else 1
    gaps = [q for q, count in counts.items() if count < minimum]
    return {'高频问题': questions, '已覆盖来源数': counts, 'gap': '、'.join(gaps) or '无',
            'coverage_gaps': gaps, 'mode': mode, 'min_sources': minimum,
            'note': '同域/同原始出处保守合并；覆盖映射不代替正文支持关系核验'}
