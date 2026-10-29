#!/usr/bin/env python3
"""Agent assignments share the query catalog used for backfills."""
import json
import sys
from query_generator import generate, templates_for


def build_search_terms(topic, expanded_terms, perspective=None, profile='general'):
    catalog = templates_for(profile)
    perspectives = [perspective] if perspective else catalog
    cells = [(p, s) for p in perspectives for s in catalog[p]]
    return [(q['perspective'], q['sub_dimension'], q['query'])
            for q in generate(topic, expanded_terms, cells, max_per_cell=1000, profile=profile)]


def agent_manifest(topic, expanded_terms, profile='general'):
    return {p: build_search_terms(topic, expanded_terms, p, profile)
            for p in templates_for(profile)}


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit('用法: parallel_agents.py 主题 [扩展词JSON] [general|health]')
    print(json.dumps(agent_manifest(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else [],
                                    sys.argv[3] if len(sys.argv) > 3 else 'general'), ensure_ascii=False, indent=2))
