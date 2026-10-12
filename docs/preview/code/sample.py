#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文注释：验证 .py 在浏览器里的编码是否正确。"""

import os
from typing import Dict, List


MAX_RETRY = 3
PI = 3.14159


class 中文类名:
    """三引号字符串里的中文也应该正常。"""

    def __init__(self, root: str, depth: int = 0) -> None:
        self.root = root
        self._cache: Dict[str, str] = {}

    def 渲染(self, paths: List[str]) -> str:
        if not paths:
            return "空"
        return "\n".join(f"{p}: {os.path.getsize(p)}" for p in paths)


if __name__ == "__main__":
    print(中文类名(".").渲染(["README.md"]))
