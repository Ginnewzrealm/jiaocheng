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
