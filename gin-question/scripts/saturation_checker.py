#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""saturation_checker.py — 信息充分性自检：计算新增率并判断是否饱和。"""


def new_rate(prev_total, new_count):
    """计算本轮新增率。"""
    if prev_total == 0:
        return 1.0 if new_count > 0 else 0.0
    return new_count / prev_total


class SaturationTracker:
    """跟踪多轮新增率，判断是否饱和。"""

    def __init__(self, threshold=0.5, consecutive=3):
        self.threshold = threshold
        self.consecutive = consecutive
        self._history = []
        self._low_streak = 0

    def update(self, prev_total, new_count):
        rate = new_rate(prev_total, new_count)
        self._history.append({"prev_total": prev_total, "new_count": new_count, "rate": rate})
        if rate < self.threshold:
            self._low_streak += 1
        else:
            self._low_streak = 0
        return self.saturated

    @property
    def saturated(self):
        return self._low_streak >= self.consecutive

    @property
    def history(self):
        return self._history


def retrieval_state(coverage, rounds, search_calls=0, max_search_calls=100):
    """Evaluate recorded rounds. Never infer search completion from a single batch."""
    if not isinstance(rounds, list) or type(search_calls) is not int or search_calls < 0:
        raise ValueError('rounds 须为数组，search_calls 须为非负整数')
    if type(max_search_calls) is not int or max_search_calls < 1:
        raise ValueError('max_search_calls 须为正整数')
    tracker, streaks = SaturationTracker(), {}
    last_round = 0
    for row in rounds:
        if not isinstance(row, dict) or any(type(row.get(k)) is not int or row[k] < 0
                for k in ('prev_total', 'new_count', 'round')) or row['round'] <= last_round:
            raise ValueError('每轮须有递增 round 和非负 prev_total/new_count')
        last_round = row['round']
        if type(row.get('backfill', False)) is not bool:
            raise ValueError('backfill 须为布尔值')
        if row.get('backfill'):
            targets = row.get('target_cells')
            if not isinstance(targets, list) or not targets or any(not isinstance(c, str) for c in targets):
                raise ValueError('补搜轮须记录非空 target_cells 字符串数组')
            for cell in set(targets):
                streaks[cell] = streaks.get(cell, 0) + 1 if row['new_count'] == 0 else 0
        else:
            tracker.update(row['prev_total'], row['new_count'])
            if row['new_count']:
                streaks.clear()  # conservative: new ordinary results can change cell coverage
    missing = ['/'.join(c) for c in coverage['missing']]
    exhausted = [c for c in missing if streaks.get(c, 0) >= 2]
    pending = [c for c in missing if c not in exhausted]
    if search_calls >= max_search_calls:
        reason = 'budget_exhausted'
    elif pending:
        reason = 'needs_backfill'
    elif tracker.saturated:
        reason = 'saturated'
    else:
        reason = 'needs_more_rounds'
    return {'exit_reason': reason, 'complete': reason == 'saturated',
            'empty_perspectives': exhausted, 'unresolved_cells': pending,
            'rounds': rounds, 'search_calls': search_calls,
            'max_search_calls': max_search_calls}


def main():
    import sys
    if len(sys.argv) < 3:
        print("用法: python3 saturation_checker.py <上轮总数> <本轮新增数>")
        sys.exit(1)
    prev = int(sys.argv[1])
    new = int(sys.argv[2])
    print(f"新增率: {new_rate(prev, new):.2%}")


if __name__ == "__main__":
    main()
