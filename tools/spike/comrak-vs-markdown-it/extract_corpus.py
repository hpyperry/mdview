#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the P0 corpus for comrak-vs-markdown-it.

Sources:
  1. Old Python test suite: every render_markdown() input actually executed.
  2. Real docs fixtures under docs/.
  3. Markdown fixtures embedded in tests/selftest.sh.
  4. corpus/curated.json (hand-written edge cases).
  5. CommonMark spec examples (fetched once, cached).

The old assertions/outputs are NOT the oracle. The oracle is markdown-it 14.3.2
(see oracle.mjs). This script only collects inputs and old outputs for reference.
"""

import hashlib
import inspect
import json
import os
import re
import sys
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CORPUS_DIR = os.path.join(HERE, "corpus")
CACHE_DIR = os.path.join(HERE, ".cache")
OUT_JSONL = os.path.join(CORPUS_DIR, "corpus.jsonl")
OUT_SUMMARY = os.path.join(CORPUS_DIR, "summary.json")

sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tests"))

import mdview  # noqa: E402
import tests_render  # noqa: E402

CLASS_TAGS = {
    "TestInline": ["inline"],
    "TestBlocks": ["blocks"],
    "TestRewrites": ["path", "rewrite"],
    "TestTargetEncoding": ["path", "encoding"],
    "TestReferenceImages": ["reference", "image"],
    "TestDataURIImages": ["data-uri"],
    "TestAutolinkLiteral": ["autolink"],
    "TestImageZoom": ["image", "zoom"],
    "TestAttributeTitles": ["attributes"],
    "TestReviewRegressions": ["regressions"],
    "TestLinkSafety": ["security", "protocol"],
    "TestRoutingHelpers": ["routing"],
}

STRESS_RE = re.compile(r"_is_linear$|_no_crash$")
INTERNAL_RE = re.compile(r"test_.*(placeholder|nul|private)", re.I)
PUA_RE = re.compile(r"[\x00\ue000-\uf8ff]")

DOC_FILES = [
    "docs/index.md",
    "docs/guide/install.md",
    "docs/guide/advanced.md",
    "docs/guide/code-blocks.md",
    "docs/preview/index.md",
    "docs/preview/binary-test.md",
]

SELFTEST_BARE = """正文 https://example.com/a 结束。

带查询串 https://e.com/x?a=1&b=2 结束。

括号 https://en.wikipedia.org/wiki/A_(b) 结束。

全角 https://e.com/a。结束。

中文 https://zh.wikipedia.org/wiki/中文条目 结束。

行内码 `https://e.com/code` 与尖括号 <https://e.com/angle>。

标签里 [见 https://e.com/label 说明](other.md)。

```text
https://e.com/fenced
```
"""

SELFTEST_B10_DOC = """![a](img%20dir/nested%20pic.png)

![b](带%20空格.png)

![c](<img dir/nested pic.png>)

![d](img dir/nested pic.png)

![e][ref]

[x](a%23b.md)

[y](a b.md)

[ref]: img%20dir/nested%20pic.png
"""

SELFTEST_B10_LITERAL = "![b](x%2520y.png)\n"


def entry(name, text, source, tags, policy="semantic", rel="docs/a.md", refs=None):
    return {
        "name": name,
        "input": text,
        "rel": rel,
        "source": source,
        "tags": sorted(set(tags)),
        "policy": policy,
        "refs": refs or [],
    }


def nearest_test_frame(start):
    frame = start
    while frame is not None:
        filename = frame.f_code.co_filename
        func = frame.f_code.co_name
        if os.path.basename(filename) == "tests_render.py" and func.startswith("test_"):
            return frame
        frame = frame.f_back
    return None


def capture_old_tests():
    records = []
    counters = {}
    original = mdview.render_markdown

    def recorder(text, *args, **kwargs):
        out = original(text, *args, **kwargs)
        if isinstance(text, str):
            frame = nearest_test_frame(inspect.currentframe().f_back)
            if frame is not None:
                test_self = frame.f_locals.get("self")
                cls = test_self.__class__.__name__ if test_self is not None else "Unknown"
                method = frame.f_code.co_name
                line = frame.f_lineno
            else:
                caller = inspect.currentframe().f_back
                cls = "Unknown"
                method = caller.f_code.co_name if caller else "Unknown"
                line = caller.f_lineno if caller else 0
            key = (cls, method)
            ordinal = counters.get(key, 0)
            counters[key] = ordinal + 1
            rel = args[0] if args else kwargs.get("rel_path", "")
            policy = "semantic"
            tags = list(CLASS_TAGS.get(cls, ["old-tests"]))
            if STRESS_RE.search(method):
                policy = "stress"
                tags.append("stress")
            elif INTERNAL_RE.search(method) or PUA_RE.search(text):
                policy = "internal"
                tags.append("internal")
            records.append({
                "name": "old:%s.%s#%d" % (cls, method, ordinal),
                "input": text,
                "rel": rel,
                "source": "old_tests",
                "tags": tags,
                "policy": policy,
                "refs": [{"class": cls, "method": method, "line": line, "ordinal": ordinal}],
                "old_output": out,
            })
        return out

    mdview.render_markdown = recorder
    old_cwd = os.getcwd()
    os.chdir(REPO)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(tests_render)
        result = unittest.TextTestRunner(verbosity=0, stream=sys.stderr).run(suite)
    finally:
        os.chdir(old_cwd)
        mdview.render_markdown = original
    if result.failures or result.errors:
        print(
            "[extract] WARNING: old suite had %d failures, %d errors"
            % (len(result.failures), len(result.errors)),
            file=sys.stderr,
        )
    return records


def doc_entries():
    out = []
    for rel in DOC_FILES:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            print("[extract] missing docs fixture: %s" % rel, file=sys.stderr)
            continue
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        out.append(entry("docs:%s" % rel, text, "docs", ["docs"], rel=rel))
    return out


def selftest_entries():
    return [
        entry("selftest:bare.md", SELFTEST_BARE, "selftest", ["selftest", "autolink"], rel="bare.md"),
        entry("selftest:b10-doc.md", SELFTEST_B10_DOC, "selftest", ["selftest", "path", "encoding"], rel="doc.md"),
        entry("selftest:b10-literal.md", SELFTEST_B10_LITERAL, "selftest", ["selftest", "path", "encoding"], rel="literal.md"),
    ]


def curated_entries():
    path = os.path.join(CORPUS_DIR, "curated.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = []
    for item in data:
        out.append(entry(
            "curated:%s" % item["name"],
            item["input"],
            "curated",
            item.get("tags", []),
            policy=item.get("policy", "semantic"),
            rel=item.get("rel", "docs/a.md"),
        ))
    return out


def commonmark_entries():
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, "commonmark-spec-0.31.2.json")
    if not os.path.exists(cache):
        url = "https://spec.commonmark.org/0.31.2/spec.json"
        print("[extract] fetching %s" % url, file=sys.stderr)
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                payload = resp.read()
            with open(cache, "wb") as f:
                f.write(payload)
        except Exception as exc:  # noqa: BLE001 - spike script, network is optional
            print("[extract] WARNING: could not fetch spec: %s" % exc, file=sys.stderr)
            return []
    with open(cache, "r", encoding="utf-8") as f:
        examples = json.load(f)
    out = []
    for ex in examples:
        md = ex.get("markdown")
        if not isinstance(md, str):
            continue
        out.append(entry(
            "spec:%s" % ex.get("example", len(out) + 1),
            md,
            "commonmark-spec",
            ["spec", ex.get("section", "")],
            rel="docs/a.md",
        ))
    return out


def merge_policy(existing, incoming):
    # internal > front_matter > semantic > stress
    order = {"stress": 0, "semantic": 1, "front_matter": 2, "internal": 3}
    return existing if order[existing] >= order[incoming] else incoming


def main():
    os.makedirs(CORPUS_DIR, exist_ok=True)
    all_entries = []
    all_entries.extend(capture_old_tests())
    all_entries.extend(doc_entries())
    all_entries.extend(selftest_entries())
    all_entries.extend(curated_entries())
    all_entries.extend(commonmark_entries())

    merged = {}
    for item in all_entries:
        key = (item["input"], item.get("rel", ""))
        if key not in merged:
            item = dict(item)
            item["tags"] = sorted(set(item.get("tags", [])))
            item["refs"] = list(item.get("refs", []))
            merged[key] = item
        else:
            dst = merged[key]
            dst["tags"] = sorted(set(dst.get("tags", [])) | set(item.get("tags", [])))
            dst["refs"].extend(item.get("refs", []))
            dst["policy"] = merge_policy(dst.get("policy", "semantic"), item.get("policy", "semantic"))
            if "old_output" not in dst and "old_output" in item:
                dst["old_output"] = item["old_output"]

    entries = list(merged.values())
    for item in entries:
        digest = hashlib.sha256((item["input"] + "\0" + item.get("rel", "")).encode("utf-8")).hexdigest()
        item["id"] = digest[:16]
    entries.sort(key=lambda e: (e["source"], e["name"]))

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for item in entries:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    counts = {}
    for item in entries:
        key = "%s/%s" % (item["source"], item["policy"])
        counts[key] = counts.get(key, 0) + 1
    tags = {}
    for item in entries:
        for tag in item.get("tags", []):
            tags[tag] = tags.get(tag, 0) + 1
    summary = {
        "total": len(entries),
        "by_source_policy": counts,
        "top_tags": sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))[:40],
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("[extract] wrote %d entries to %s" % (len(entries), OUT_JSONL))
    for key in sorted(counts):
        print("  %-32s %d" % (key, counts[key]))
    print("[extract] tags:", ", ".join("%s=%d" % kv for kv in summary["top_tags"][:20]))


if __name__ == "__main__":
    main()
