#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retry_agent.py — 带重试和补搜策略的执行器。"""

import time


class RetryExecutor:
    """对某个检索动作进行重试和补搜。"""

    def __init__(self, max_retries=3, backoff=1.0):
        self.max_retries = max_retries
        self.backoff = backoff

    def execute(self, fn, *args, **kwargs):
        """执行 fn，失败时按指数退避重试。

        fn 应返回 (success: bool, result, error_msg: str)
        """
        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                success, result, error = fn(*args, **kwargs)
                if success:
                    return True, result, None
                last_error = error or "unknown"
            except Exception as e:
                last_error = str(e)
            if attempt < self.max_retries:
                time.sleep(self.backoff * (2 ** (attempt - 1)))
        return False, None, last_error


def main():
    print("retry_agent 是模块，不直接作为 CLI 使用。")


if __name__ == "__main__":
    main()
