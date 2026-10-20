//! Ported renderer regression suite.
//!
//! This is the Rust successor to the old Python `tests/tests_render.py` render
//! classes (P4-1). Expectations follow ADR 0005 (VS Code core), ADR 0006
//! (raw HTML + Trust/CSP) and ADR 0007 (linkify / reference definitions /
//! front matter / long-tail use comrak behavior).
//!
//! Expectations that intentionally differ from the old Python suite are marked
//! with `accepted deviation` in the test name or comment.

use mdview::render::render_markdown;

fn r(src: &str) -> String {
    render_markdown(src, "docs/a.md")
}

fn r_at(src: &str, rel: &str) -> String {
    render_markdown(src, rel)
}

/// Attribute names of one start tag, following HTML's quoted-value rules so
/// escaped text like `&quot; onerror=&quot;` is not mistaken for an attribute.
fn attr_names(tag: &str) -> Vec<String> {
    let inner = match tag.split_once(' ') {
        Some((_, rest)) => rest.trim_end_matches('>').trim_end_matches('/'),
        None => return Vec::new(),
    };
    let mut names = Vec::new();
    let mut chars = inner.char_indices().peekable();
    while let Some((start, ch)) = chars.next() {
        if ch.is_whitespace() {
            continue;
        }
        let mut end = start + ch.len_utf8();
        for (i, c) in chars.by_ref() {
            if c.is_whitespace() || c == '=' {
                end = i;
                break;
            }
            end = i + c.len_utf8();
        }
        let name = inner[start..end].trim().to_ascii_lowercase();
        if !name.is_empty() {
            names.push(name);
        }
        // Skip a quoted or bare value if one follows.
        let rest = &inner[end..];
        let rest = rest.trim_start();
        if let Some(rest) = rest.strip_prefix('=') {
            let rest = rest.trim_start();
            let mut quoted = None;
            for (i, c) in rest.char_indices() {
                if c == '"' || c == '\'' {
                    quoted = Some((i, c));
                    break;
                }
                if c.is_whitespace() {
                    break;
                }
            }
            if let Some((open, quote)) = quoted
                && let Some(close) = rest[open + 1..].find(quote)
            {
                let skip = rest[open + 1..].len() - rest[open + 1 + close..].len();
                let consumed = open + 1 + skip + 1;
                // Move the iterator to the end of the quoted value.
                let target = inner.len() - rest[consumed..].len();
                while let Some(&(i, _)) = chars.peek() {
                    if i < target {
                        chars.next();
                    } else {
                        break;
                    }
                }
            }
        }
    }
    names
}

fn start_tag<'a>(html: &'a str, name: &str) -> Option<&'a str> {
    let open = html.find(&format!("<{name}"))?;
    let rest = &html[open..];
    let close = rest.find('>')?;
    Some(&rest[..=close])
}

fn href(html: &str) -> Option<&str> {
    let tag = start_tag(html, "a")?;
    attr_value(tag, "href")
}

fn attr_value<'a>(tag: &'a str, attr: &str) -> Option<&'a str> {
    let needle = format!("{attr}=\"");
    let start = tag.find(&needle)? + needle.len();
    let rest = &tag[start..];
    let end = rest.find('"')?;
    Some(&rest[..end])
}

// ---------------------------------------------------------------------------
// Inline — old TestInline
// ---------------------------------------------------------------------------

#[test]
fn triple_emphasis() {
    assert!(r("***双***").contains("<em><strong>双</strong></em>"));
    assert!(r("***粗斜*** 测试").contains("<em><strong>粗斜</strong></em> 测试"));
    assert!(r("中文***粗斜***中文").contains("中文<em><strong>粗斜</strong></em>中文"));
    assert!(r("___粗斜___").contains("<em><strong>粗斜</strong></em>"));
}

#[test]
fn emphasis_and_strikethrough() {
    assert!(r("**粗体**").contains("<strong>粗体</strong>"));
    assert!(r("*斜体*").contains("<em>斜体</em>"));
    assert!(r("*斜体*。").contains("<em>斜体</em>。"));
    assert!(r("~~删除~~").contains("<s>删除</s>"));
    assert!(!r("~~删除~~").contains("<del>"));
}

#[test]
fn underscore_rules() {
    assert!(r("a__b__c").contains("a__b__c"));
    assert!(!r("a__b__c").contains("<strong>"));
    // accepted deviation vs the old Python implementation: VS Code/markdown-it
    // follow CommonMark and do not emphasise intraword underscores next to CJK.
    assert!(r("中文__粗__中文").contains("中文__粗__中文"));
    assert!(r("__粗__ 与 _斜_ 并存").contains("<strong>粗</strong> 与 <em>斜</em> 并存"));
}

#[test]
fn asterisk_intraword_follows_commonmark() {
    // Old Python treated `a*b` as literal; VS Code/markdown-it pair delimiters
    // the CommonMark way, and comrak matches.
    assert!(r("a*b 和 2*3*4").contains("a<em>b 和 2</em>3*4"));
    assert!(r("2*3*4").contains("2<em>3</em>4"));
    assert!(r("中*插*文").contains("中<em>插</em>文"));
}

#[test]
fn adjacent_and_unmatched_delimiters() {
    assert!(r("**a****b**").contains("<strong>a****b</strong>"));
    let out = r("**a*");
    assert!(out.contains("*<em>a</em>"), "{out}");
    assert!(
        r("见 **粗体 **内** 粗体** 结束")
            .contains("<strong>粗体 <strong>内</strong> 粗体</strong>")
    );
}

#[test]
fn code_span_protects_markdown() {
    assert!(r("`a**b**c`").contains("<code>a**b**c</code>"));
    assert!(r("`a*b*c`").contains("<code>a*b*c</code>"));
}

#[test]
fn backslash_escape() {
    let out = r(r"\*不是斜体\*");
    assert!(out.contains("*不是斜体*"));
    assert!(!out.contains("<em>"));
    let out = r(r"\`不是代码\`");
    assert!(!out.contains("<code>"));
    assert!(out.contains("不是代码"));
}

#[test]
fn escapes_and_code_spans_do_not_corrupt_tokens() {
    let cases = [
        r"`\*转义\*`",
        r"| `\*转义\*` | 反斜杠转义优先 |",
        r"\*裸转义\* 与 `代码`",
        r"`a` 和 \`b\` 和 `c`",
        r"\`不是代码\`",
        r"转义写法：\*不是斜体\*、\`不是代码\`。",
        r"`**粗体**` 与 **真粗体**",
        r"``双反引号`` 与 \`单个\`",
    ];
    for src in cases {
        let out = r(src);
        for junk in ["MK0", "MK1", "\u{e000}", "\u{e010}", "\u{e013}"] {
            assert!(!out.contains(junk), "placeholder leak: {src:?} -> {out:?}");
        }
    }
    // CommonMark keeps the backslash inside code spans.
    assert!(r("`\\*x\\*`").contains("<code>\\*x\\*</code>"));
    assert!(!r("`\\*x\\*`").contains("<em>"));
}

#[test]
fn code_fence_html_is_escaped() {
    let payloads = [
        "```html\n<script>alert(1)</script>\n```",
        "```\n<img src=x onerror=\"alert(1)\">\n```",
        "```javascript\ndocument.write(\"<script>x</script>\")\n```",
        "~~~text\n<svg onload=alert(1)>\n~~~",
    ];
    for src in payloads {
        let out = r(src);
        for tag in ["<script", "<img", "<svg"] {
            assert!(!out.contains(tag), "unescaped {tag} in {src:?}: {out}");
        }
        assert!(
            out.contains("&lt;"),
            "fence content must be escaped: {src:?}"
        );
    }
    let out = r("```python\nif a < b and c > d:\n    pass\n```");
    assert!(out.contains("&lt;"));
    assert!(out.contains("&gt;"));
    assert!(out.contains("class=\"language-python\""));
}

#[test]
fn raw_html_passes_through_outside_code() {
    // ADR 0006: raw HTML is not escaped; the Trust prompt and CSP are the
    // boundary. Content inside code spans/fences stays escaped (test above).
    let out = r("<script>alert(1)</script>");
    assert!(out.contains("<script>alert(1)</script>"));
    let out = r("<div class=x>raw</div>");
    assert!(out.contains("<div class=x>raw</div>"));
    let out = r("a <b>c</b> d");
    assert!(out.contains("a <b>c</b> d"));
    let out = r("`<script>`");
    assert!(out.contains("<code>&lt;script&gt;</code>"));
}

#[test]
fn image_alt_is_plain_text() {
    assert!(r("![**粗**](p.png)").contains("alt=\"粗\""));
    assert!(r("![![i](i.png)](p.png)").contains("alt=\"i\""));
    assert!(r("![a<b>c](p.png)").contains("alt=\"a&lt;b&gt;c\""));
    // accepted deviation: comrak keeps the decoded ampersand, markdown-it
    // drops entity tokens from alt.
    assert!(r("![a&amp;b](p.png)").contains("alt=\"a&amp;b\""));
    assert!(r("![**粗**][r]\n\n[r]: p.png").contains("alt=\"粗\""));
    assert!(r("![**粗**][]\n\n[**粗**]: p.png").contains("alt=\"粗\""));
}

#[test]
fn entities_decode() {
    assert!(r("&copy;").contains("©"));
    assert!(r("&amp;").contains("&amp;"));
    assert!(r("&#65;").contains("A"));
}

#[test]
fn angle_autolink() {
    assert!(
        r("<https://example.com>")
            .contains("<a href=\"https://example.com\">https://example.com</a>")
    );
}

#[test]
fn reference_link() {
    let out = r("[文字][r1]\n\n[r1]: https://example.com \"标题\"");
    assert!(
        out.contains("<a href=\"https://example.com\" title=\"标题\">文字</a>"),
        "{out}"
    );
    let out = r("[r1]\n\n[r1]: https://example.com");
    assert!(out.contains(">r1</a>"));
}

// ---------------------------------------------------------------------------
// Blocks — old TestBlocks
// ---------------------------------------------------------------------------

#[test]
fn headings_have_no_ids() {
    assert_eq!(r("# 标题"), "<h1>标题</h1>\n");
    assert_eq!(r("### 三级"), "<h3>三级</h3>\n");
    let out = r("## 重复\n\n## 重复");
    assert!(!out.contains("id="), "{out}");
    assert_eq!(out.matches("<h2>重复</h2>").count(), 2);
}

#[test]
fn setext_follows_commonmark() {
    assert_eq!(r("一级\n==="), "<h1>一级</h1>\n");
    // VS Code/comrak treat `文字\n---` as a Setext heading, not a rule.
    assert_eq!(r("二级\n---"), "<h2>二级</h2>\n");
}

#[test]
fn horizontal_rules() {
    assert!(r("---").contains("<hr"));
    assert!(r("***").contains("<hr"));
    assert!(r("___").contains("<hr"));
}

#[test]
fn tight_and_loose_lists() {
    let tight = r("- a\n- b");
    assert!(tight.contains("<li>a</li>"));
    assert!(!tight.contains("<p>a</p>"));
    let loose = r("- a\n\n- b");
    assert!(loose.contains("<p>a</p>"), "{loose}");
    assert!(loose.contains("<p>b</p>"), "{loose}");
}

#[test]
fn ordered_list_start() {
    assert!(r("4. a\n5. b").contains("<ol start=\"4\">"));
    assert!(r("1. a").contains("<ol>"));
}

#[test]
fn nested_lists() {
    let out = r("- 外层\n  - 内层\n    1. 有序");
    assert!(out.contains("内层"));
    assert!(out.contains("<ol>"));
    assert!(out.matches("<ul>").count() >= 2, "{out}");
}

#[test]
fn task_list_is_literal() {
    let out = r("- [ ] 待办\n- [x] 完成");
    assert!(!out.contains("<input"));
    assert!(out.contains("[ ] 待办"));
    assert!(out.contains("[x] 完成"));
}

#[test]
fn blockquote_nested() {
    let out = r("> 一层\n> > 二层");
    assert_eq!(out.matches("<blockquote>").count(), 2);
}

#[test]
fn fenced_code_language_class() {
    let out = r("```python\ndef f(x):\n    return \"s\"\n```");
    assert!(out.contains("class=\"language-python\""));
    assert!(out.contains("def f(x):"));
    // Server does not highlight; highlight.js runs in the browser.
    assert!(!out.contains("<span class=\"kw\">"));
    let out = r("```\nx = 1\n```");
    assert!(!out.contains("<span"));
    assert!(out.contains("x = 1"));
    assert!(!out.contains("class=\"language-"));
}

#[test]
fn fence_content_not_parsed() {
    let out = r("```\n# 不是标题\n**不是粗体**\n```");
    assert!(!out.contains("<h1"));
    assert!(!out.contains("<strong>"));
}

#[test]
fn tilde_fence() {
    assert!(r("~~~\nx\n~~~").contains("<pre><code>"));
}

#[test]
fn table_alignment_uses_style() {
    let out = r("| a | b |\n|:--|--:|\n| 1 | 2 |");
    assert!(out.contains("<th style=\"text-align:left\">a</th>"));
    assert!(out.contains("<th style=\"text-align:right\">b</th>"));
    assert!(out.contains("<td"));
    assert!(!out.contains("align=\""));
}

#[test]
fn table_after_rule() {
    let out = r("---\n\n| a |\n| - |\n| 1 |");
    assert!(out.contains("<hr"));
    assert!(out.contains("<table>"));
}

#[test]
fn front_matter_is_consumed() {
    let out = r("---\ntitle: x\n---\n\n# Hi");
    assert!(!out.contains("title: x"), "{out}");
    assert!(out.contains("<h1>Hi</h1>"));
}

#[test]
fn empty_front_matter_is_not_consumed() {
    // comrak's front matter extension needs content between the delimiters.
    let out = r("---\n---\n");
    assert_eq!(out.matches("<hr").count(), 2, "{out}");
}

// ---------------------------------------------------------------------------
// URL rewrites — old TestRewrites
// ---------------------------------------------------------------------------

#[test]
fn md_link_rewritten() {
    assert!(r("[x](sub/b.md)").contains("href=\"/docs/sub/b.md\""));
    assert!(r("[x](sub/b.md#锚)").contains("href=\"/docs/sub/b.md#%E9%94%9A\""));
    assert!(r("![x](img/a.png)").contains("src=\"/docs/img/a.png\""));
}

#[test]
fn image_and_relative_path_rewrite() {
    assert!(r("![x](img/a.png)").contains("src=\"/docs/img/a.png\""));
    assert!(r_at("![x](../img/a.png)", "docs/sub/a.md").contains("src=\"/docs/img/a.png\""));
}

#[test]
fn dotdot_is_clamped() {
    let out = r_at("[x](../../../outside/x.md)", "a.md");
    assert!(out.contains("../../../outside/x.md"));
    assert!(!out.contains("href=\"/outside"));
    assert!(r_at("![x](../img/a.png)", "docs/sub/a.md").contains("src=\"/docs/img/a.png\""));
}

#[test]
fn absolute_and_external_links() {
    assert!(r("[x](https://e.com/x)").contains("href=\"https://e.com/x\""));
    assert!(r("[x](/a/b.md)").contains("href=\"/a/b.md\""));
}

#[test]
fn cjk_path_is_encoded() {
    let out = r("[x](中文目录/说明.md)");
    assert!(out.contains("href=\"/docs/%E4%B8%AD%E6%96%87"));
    assert!(!out.contains("中文目录"));
}

#[test]
fn anchor_only_is_encoded() {
    assert!(r("[x](#锚)").contains("href=\"#%E9%94%9A\""));
}

// ---------------------------------------------------------------------------
// Target encoding — old TestTargetEncoding
// ---------------------------------------------------------------------------

#[test]
fn percent20_is_decoded_and_encoded_once() {
    let out = r("![x](my%20file.png)");
    assert!(out.contains("src=\"/docs/my%20file.png\""), "{out}");
    assert!(!out.contains("%25"));
}

#[test]
fn percent20_in_directory_component() {
    let out = r("![x](img%20dir/my%20file.png)");
    assert!(out.contains("src=\"/docs/img%20dir/my%20file.png\""));
    assert!(!out.contains("%25"));
}

#[test]
fn literal_percent_round_trips() {
    // The Rust server follows VS Code and decodes twice: `%2520` names the
    // literal `%20` file, which is reachable as `/docs/my%20file.png`.
    assert!(r("![x](my%2520file.png)").contains("src=\"/docs/my%20file.png\""));
    assert!(r("[x](a%2523b.md)").contains("href=\"/docs/a%23b.md\""));
    assert!(r("[x](100%25.png)").contains("href=\"/docs/100%25.png\""));
}

#[test]
fn query_and_fragment_are_split_before_decoding() {
    assert!(r("[x](a%23b.md)").contains("href=\"/docs/a%23b.md\""));
    assert!(r("[x](a%3Fb.md)").contains("href=\"/docs/a%3Fb.md\""));
    assert!(r("![x](img/a%23b.png)").contains("src=\"/docs/img/a%23b.png\""));
    assert!(r("![x](img/a%3Fb.png)").contains("src=\"/docs/img/a%3Fb.png\""));
}

#[test]
fn query_and_fragment_kept_verbatim() {
    assert!(r("[x](doc.md?raw=1#L10)").contains("href=\"/docs/doc.md?raw=1#L10\""));
    assert!(r("[x](doc.md?q=a%20b)").contains("href=\"/docs/doc.md?q=a%20b\""));
    assert!(r("[x](doc.md?q=a+b)").contains("href=\"/docs/doc.md?q=a+b\""));
    assert!(r("[x](sub/b.md#锚)").contains("href=\"/docs/sub/b.md#%E9%94%9A\""));
}

#[test]
fn link_and_image_share_one_rule() {
    for target in [
        "my%20file.png",
        "a%23b.png",
        "100%25.png",
        "sub%20dir/x.png",
        "a%2Bb.png",
        "中文.png",
    ] {
        let link_html = r(&format!("[x]({target})"));
        let link = href(&link_html).expect("link href");
        let image_html = r(&format!("![x]({target})"));
        let img_tag = start_tag(&image_html, "img").expect("img");
        let image = attr_value(img_tag, "src").expect("image src");
        assert_eq!(link, image, "{target}");
    }
}

#[test]
fn obfuscated_scheme_never_executes() {
    let out = r("[x](%6aavascript:alert(1))");
    assert!(!out.contains("href=\"javascript:"));
    assert!(out.contains("/docs/javascript%3Aalert(1)"));
    let out = r("![x](%6aavascript:alert(1))");
    assert!(!out.contains("src=\"javascript:"));
    assert!(out.contains("src=\"/docs/javascript%3Aalert(1)\""));
}

#[test]
fn angle_destination_encodes_inner_space() {
    assert!(r("[x](<a b.md>)").contains("href=\"/docs/a%20b.md\""));
    assert!(r("[x](<a b.md> \"t\")").contains("href=\"/docs/a%20b.md\" title=\"t\""));
}

#[test]
fn angle_and_percent_forms_are_identical() {
    assert_eq!(r("![x](img/my%20file.png)"), r("![x](<img/my file.png>)"));
    assert_eq!(r("[x](a%20b.md)"), r("[x](<a b.md>)"));
}

#[test]
fn angle_destination_keeps_inner_paren() {
    assert!(r("[x](<a)b.md>)").contains("href=\"/docs/a)b.md\""));
}

#[test]
fn angle_destination_with_scheme() {
    assert!(r("[x](<https://e.com/a b>)").contains("href=\"https://e.com/a%20b\""));
}

#[test]
fn angle_destination_not_touched_inside_code_span() {
    assert!(r("`![](<a b.png>)`").contains("<code>![](&lt;a b.png&gt;)</code>"));
}

#[test]
fn nested_angle_image_in_link() {
    assert!(
        r("[![i](<a b.png>)](y.md)")
            .contains("<a href=\"/docs/y.md\"><img src=\"/docs/a%20b.png\" alt=\"i\" />")
    );
}

#[test]
fn bare_space_destination_is_not_a_link() {
    let out = r("[x](a b.md)");
    assert!(!out.contains("<a"));
    assert!(out.contains("[x](a b.md)"));
    assert!(!r("![x](img/my file.png)").contains("<img"));
}

#[test]
fn trailing_space_and_title_still_are_links() {
    assert!(r("[x](a  )").contains("href=\"/docs/a\""));
    assert!(r("[x](a \"t\")").contains("href=\"/docs/a\" title=\"t\""));
    assert!(!r("[x](a \"t\" junk)").contains("<a"));
}

// ---------------------------------------------------------------------------
// Reference images — old TestReferenceImages
// ---------------------------------------------------------------------------

#[test]
fn full_reference_image() {
    assert!(
        r("![x][pic]\n\n[pic]: img/my%20file.png")
            .contains("<img src=\"/docs/img/my%20file.png\" alt=\"x\"")
    );
}

#[test]
fn collapsed_reference_image() {
    assert!(
        r("![x][]\n\n[x]: img/my%20file.png")
            .contains("<img src=\"/docs/img/my%20file.png\" alt=\"x\"")
    );
}

#[test]
fn shortcut_reference_image() {
    assert!(r("![x]\n\n[x]: a%20b.png").contains("<img src=\"/docs/a%20b.png\" alt=\"x\""));
}

#[test]
fn reference_image_angle_definition_with_trailing_newline() {
    // A normal file ends with a newline; comrak and markdown-it both parse
    // `[pic]: <a b.png>` there.
    let out = r("![x][pic]\n\n[pic]: <a b.png>\n");
    assert!(
        out.contains("<img src=\"/docs/a%20b.png\" alt=\"x\""),
        "{out}"
    );
}

#[test]
fn reference_image_angle_definition_at_eof_is_a_comrak_quirk() {
    // comrak does not recognise the definition when the file ends immediately
    // after `>`. markdown-it still parses it, so this is a narrow EOF gap.
    let out = r("![x][pic]\n\n[pic]: <a b.png>");
    assert!(!out.contains("<img"), "{out}");
    assert!(out.contains("![x][pic]"), "{out}");
}

#[test]
fn reference_image_title() {
    assert!(
        r("![x][pic]\n\n[pic]: a.png \"t\"")
            .contains("<img src=\"/docs/a.png\" alt=\"x\" title=\"t\"")
    );
}

#[test]
fn reference_attributes_are_not_reparsed_as_markdown() {
    let out = r("[x][r]\n\n[r]: _x_.png");
    assert!(out.contains("href=\"/docs/_x_.png\""));
    assert!(!out.contains("<em>"), "{out}");
    let out = r("![i][r]\n\n[r]: _x_.png");
    assert!(out.contains("src=\"/docs/_x_.png\""));
    assert!(!out.contains("<em>"), "{out}");
    assert!(
        r("[**粗**][r]\n\n[r]: u.md").contains("<a href=\"/docs/u.md\"><strong>粗</strong></a>")
    );
    assert!(r("[_斜_][r]\n\n[r]: u.md").contains("<a href=\"/docs/u.md\"><em>斜</em></a>"));
}

#[test]
fn rejected_reference_protocol_is_removed() {
    // ADR 0007: comrak drops the invalid definition; the reference renders as
    // plain label text. No href and no image.
    for src in [
        "![x][r]\n\n[r]: javascript:alert(1)",
        "![x][r]\n\n[r]: data:text/html,x",
    ] {
        let out = r(src);
        assert!(!out.contains("<img"), "{src}: {out}");
        assert!(!out.contains("href="), "{src}: {out}");
        assert!(out.contains("x"), "{src}: {out}");
    }
}

#[test]
fn reference_image_needs_definition() {
    assert!(!r("![x][nope]").contains("<img"));
}

#[test]
fn repeated_reference_definition_first_wins() {
    assert!(r("[x][r]\n\n[r]: a.md\n[r]: b.md").contains("href=\"/docs/a.md\""));
}

#[test]
fn reference_target_encoding_matches_inline() {
    let target = "https://e.com/a%20b";
    let inline = href(&r(&format!("[x]({target})")))
        .expect("inline href")
        .to_string();
    let reference = href(&r(&format!("[x][r]\n\n[r]: {target}")))
        .expect("reference href")
        .to_string();
    assert_eq!(inline, reference);
    assert_eq!(inline, target);
}

// ---------------------------------------------------------------------------
// data: URI images — old TestDataURIImages (policy updated by VS Code 1.142)
// ---------------------------------------------------------------------------

const PNG: &str = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";

#[test]
fn data_uri_inline_image() {
    assert!(r(&format!("![x]({PNG})")).contains(&format!("<img src=\"{PNG}\" alt=\"x\"")));
}

#[test]
fn data_uri_reference_image() {
    assert!(
        r(&format!("![x][pic]\n\n[pic]: {PNG}")).contains(&format!("<img src=\"{PNG}\" alt=\"x\""))
    );
}

#[test]
fn data_uri_angle_destination() {
    assert!(r(&format!("![x](<{PNG}>)")).contains(&format!("<img src=\"{PNG}\" alt=\"x\"")));
}

#[test]
fn data_uri_registered_types() {
    for uri in [
        "data:image/gif;base64,AAAA",
        "data:image/png;base64,AAAA",
        "data:image/jpeg;base64,AAAA",
        "data:image/webp;base64,AAAA",
    ] {
        assert!(
            r(&format!("![x]({uri})")).contains(&format!("src=\"{uri}\"")),
            "{uri}"
        );
    }
}

#[test]
fn data_uri_any_image_type_with_semicolon_is_allowed() {
    // VS Code 1.142 override: /^data:image\/.*?;/ (links and images).
    for uri in [
        "data:image/svg+xml;base64,AAAA",
        "data:image/bmp;base64,AAAA",
        "data:image/x-icon;base64,AAAA",
        "data:image/avif;base64,AAAA",
    ] {
        assert!(
            r(&format!("![x]({uri})")).contains(&format!("src=\"{uri}\"")),
            "{uri}"
        );
    }
}

#[test]
fn data_uri_base64_flag_is_case_insensitive_for_registered_types() {
    let uri = "DATA:IMAGE/PNG;BASE64,AAAA";
    assert!(r(&format!("![x]({uri})")).contains(&format!("src=\"{uri}\"")));
}

#[test]
fn data_uri_parameters_before_base64_are_allowed() {
    let uri = "data:image/svg+xml;charset=utf-8;base64,PHN2Zy8+";
    assert!(r(&format!("![x]({uri})")).contains(&format!("src=\"{uri}\"")));
}

#[test]
fn data_uri_image_is_allowed_in_link_position() {
    // User decision: match VS Code, which allows data:image/*;... in both
    // links and images.
    assert!(r(&format!("[x]({PNG})")).contains(&format!("href=\"{PNG}\"")));
    assert!(r(&format!("[x][r]\n\n[r]: {PNG}")).contains(&format!("href=\"{PNG}\"")));
}

#[test]
fn data_uri_non_image_is_rejected() {
    for uri in ["data:text/html,x", "data:application/javascript,alert(1)"] {
        let out = r(&format!("![x]({uri})"));
        assert!(!out.contains("<img"), "{uri}: {out}");
        assert!(out.contains("x"), "{uri}: {out}");
        let out = r(&format!("[x]({uri})"));
        assert!(!out.contains("href="), "{uri}: {out}");
    }
}

#[test]
fn data_uri_without_semicolon_is_rejected() {
    // `data:image/png,AAAA` has no `;` after the subtype, so it is neither an
    // image data URI nor a valid media-type prefix. (`data:image/png;base64`
    // without a payload *does* match VS Code's `^data:image\/(gif|png|jpeg|webp);`
    // prefix and is intentionally allowed, degenerate as it is.)
    let out = r("![x](data:image/png,AAAA)");
    assert!(!out.contains("<img"), "{out}");
}

#[test]
fn obfuscated_data_scheme_stays_a_relative_path() {
    let out = r("![x](%64ata:image/png;base64,AAAA)");
    assert!(!out.contains("src=\"data:"));
    assert!(out.contains("src=\"/docs/data%3Aimage/png;base64,AAAA\""));
}

#[test]
fn data_uri_payload_quotes_cannot_break_the_attribute() {
    let out = r("![x](data:image/png;base64,\"onerror=\"alert(1))");
    assert!(!out.contains(" onerror=\""), "{out}");
    assert!(out.contains("%22onerror=%22"), "{out}");
    let img = start_tag(&out, "img").expect("img tag");
    assert_eq!(attr_names(img), ["src", "alt"], "{img}");
}

#[test]
fn raw_html_img_passes_through() {
    let out = r(&format!("<img src=\"{PNG}\">"));
    assert!(out.contains(&format!("<img src=\"{PNG}\">")), "{out}");
}

#[test]
fn zoom_href_is_byte_identical_to_src_for_data_uri() {
    let out = r(&format!("![x]({PNG})"));
    assert!(out.contains(&format!(
        "<a class=\"zoom\" href=\"{PNG}\"><img src=\"{PNG}\""
    )));
}

#[test]
fn badge_image_is_not_wrapped_in_zoom_for_data_uri() {
    let out = r(&format!("[![i]({PNG})](u.md)"));
    assert!(out.contains(&format!(
        "<a href=\"/docs/u.md\"><img src=\"{PNG}\" alt=\"i\" /></a>"
    )));
    assert!(!out.contains("class=\"zoom\""));
}

// ---------------------------------------------------------------------------
// Autolink literals — old TestAutolinkLiteral (comrak behavior, ADR 0007)
// ---------------------------------------------------------------------------

#[test]
fn bare_https_becomes_link() {
    let out = r("访问 https://example.com/a 看看。");
    assert!(out.contains("<a href=\"https://example.com/a\">https://example.com/a</a>"));
    assert!(out.contains("访问 "));
}

#[test]
fn bare_http_with_port_and_trailing_slash() {
    assert!(r("打开 http://127.0.0.1:8000/ 即可。").contains("href=\"http://127.0.0.1:8000/\""));
}

#[test]
fn scheme_case_is_preserved() {
    // accepted deviation: comrak keeps the author's uppercase scheme.
    assert!(
        r("见 HTTPS://EXAMPLE.COM/A 结束")
            .contains("<a href=\"HTTPS://EXAMPLE.COM/A\">HTTPS://EXAMPLE.COM/A</a>")
    );
}

#[test]
fn www_is_linkified_by_comrak() {
    // accepted deviation vs VS Code (which disables fuzzy links).
    assert!(r("见 www.example.com 说明").contains("href=\"http://www.example.com\""));
}

#[test]
fn bare_email_is_linkified_by_comrak() {
    // accepted deviation vs VS Code.
    assert!(r("联系 a@b.com 吧").contains("href=\"mailto:a@b.com\""));
}

#[test]
fn trailing_ascii_punctuation_belongs_to_sentence() {
    for ch in [".", ",", ":", ";", "!", "?"] {
        let out = r(&format!("见 https://example.com/a{ch} 结束"));
        assert!(
            out.contains("href=\"https://example.com/a\""),
            "{ch}: {out}"
        );
        assert!(out.contains(&format!("</a>{ch}")), "{ch}: {out}");
    }
}

#[test]
fn full_width_punctuation_is_swallowed_by_comrak() {
    // accepted deviation: VS Code's linkify-it stops before `。`.
    let out = r("见 https://example.com/a。结束");
    assert!(
        out.contains("href=\"https://example.com/a%E3%80%82%E7%BB%93%E6%9D%9F\""),
        "{out}"
    );
    assert!(out.contains("https://example.com/a。结束</a>"), "{out}");
}

#[test]
fn cjk_inside_url_is_kept() {
    let out = r("见 https://zh.wikipedia.org/wiki/中文条目 结束");
    assert!(
        out.contains("href=\"https://zh.wikipedia.org/wiki/%E4%B8%AD%E6%96%87%E6%9D%A1%E7%9B%AE\"")
    );
    assert!(out.contains(">https://zh.wikipedia.org/wiki/中文条目</a>"));
}

#[test]
fn parentheses_balance_like_gfm() {
    let out = r("见 https://en.wikipedia.org/wiki/A_(b) 结束");
    assert!(out.contains("href=\"https://en.wikipedia.org/wiki/A_(b)\""));
    let out = r("见 https://en.wikipedia.org/wiki/A_(b)) 结束");
    assert!(out.contains("href=\"https://en.wikipedia.org/wiki/A_(b)\""));
    assert!(out.contains("</a>) 结束"));
    let out = r("(见 https://example.com/a)");
    assert!(out.contains("href=\"https://example.com/a\""));
    assert!(out.contains("</a>)"));
}

#[test]
fn trailing_quotes_returned_to_sentence() {
    let out = r("见 \"https://example.com/a\" 结束");
    assert!(out.contains("href=\"https://example.com/a\""));
    assert!(out.contains("</a>&quot; 结束"));
}

#[test]
fn query_string_escaped_once() {
    let out = r("访问 https://e.com/x?a=1&b=2 结束");
    assert!(out.contains("href=\"https://e.com/x?a=1&amp;b=2\""));
    assert!(!out.contains("&amp;amp;"));
}

#[test]
fn entity_stops_the_url_in_comrak() {
    // accepted deviation: VS Code includes `&copy` in the URL.
    let out = r("见 https://e.com/a&copy; 结束");
    assert!(out.contains("href=\"https://e.com/a\""), "{out}");
    assert!(out.contains("</a>© 结束"), "{out}");
}

#[test]
fn bare_url_not_linkified_inside_code() {
    assert!(r("写成 `https://e.com/a` 即可").contains("<code>https://e.com/a</code>"));
    assert!(!r("```\nhttps://e.com/a\n```").contains("<a"));
}

#[test]
fn angle_autolink_still_works() {
    assert!(
        r("<https://example.com>")
            .contains("<a href=\"https://example.com\">https://example.com</a>")
    );
}

#[test]
fn markdown_link_destination_is_not_linkified() {
    let out = r("见 [x](https://e.com/a) 说明");
    assert!(out.contains("<a href=\"https://e.com/a\">x</a>"));
    assert_eq!(out.matches("<a ").count(), 1);
}

#[test]
fn label_url_is_not_nested() {
    let out = r("[见 https://example.com/a 说明](other.md)");
    assert_eq!(out.matches("<a ").count(), 1, "{out}");
    assert!(out.contains("见 https://example.com/a 说明</a>"));
}

#[test]
fn image_alt_is_not_linkified() {
    let out = r("![见 https://e.com/a](p.png)");
    assert_eq!(out.matches("<a ").count(), 1, "{out}");
    assert!(out.contains("<a class=\"zoom\" href=\"/docs/p.png\">"));
    assert!(out.contains("alt=\"见 https://e.com/a\""));
}

#[test]
fn reference_image_source_is_not_corrupted() {
    let out = r("![a][r]\n\n[r]: https://e.com/p.png");
    assert!(out.contains("<img src=\"https://e.com/p.png\" alt=\"a\""));
    assert!(!out.contains("src=\"<a"));
    assert!(out.contains("<a class=\"zoom\" href=\"https://e.com/p.png\">"));
}

#[test]
fn url_after_markdown_link_is_linkified() {
    let out = r("[x](a.md)https://e.com");
    assert!(out.contains("href=\"/docs/a.md\""));
    assert!(out.contains("href=\"https://e.com\""));
}

#[test]
fn linkified_in_heading_and_table() {
    assert!(r("## 见 https://e.com/a").contains("<a href=\"https://e.com/a\""));
    assert!(r("| a |\n|---|\n| https://e.com/x |").contains("<td><a href=\"https://e.com/x\""));
}

#[test]
fn no_link_without_a_scheme() {
    assert!(!r("普通一段没有链接的文字").contains("<a"));
}

// ---------------------------------------------------------------------------
// Image zoom wrapper — old TestImageZoom
// ---------------------------------------------------------------------------

#[test]
fn inline_image_is_wrapped() {
    assert!(r("![x](p.png)").contains(
        "<a class=\"zoom\" href=\"/docs/p.png\"><img src=\"/docs/p.png\" alt=\"x\" /></a>"
    ));
}

#[test]
fn reference_image_is_wrapped() {
    for src in [
        "![x][r]\n\n[r]: p.png",
        "![x][]\n\n[x]: p.png",
        "![x]\n\n[x]: p.png",
    ] {
        let out = r(src);
        assert!(
            out.contains("<a class=\"zoom\" href=\"/docs/p.png\">"),
            "{src}"
        );
        assert!(out.contains("<img src=\"/docs/p.png\" alt=\"x\""), "{src}");
    }
}

#[test]
fn zoom_href_is_byte_identical_to_src() {
    for target in [
        "my%20file.png",
        "a%23b.png",
        "100%25.png",
        "中文.png",
        "img%20dir/x%20y.png",
        "<a b.png>",
    ] {
        let out = r(&format!("![x]({target})"));
        let zoom = href(&out).expect("zoom href");
        let img = start_tag(&out, "img").expect("img");
        let src = attr_value(img, "src").expect("src");
        assert_eq!(zoom, src, "{target}");
    }
}

#[test]
fn badge_image_inside_link_is_not_wrapped() {
    let out = r("[![i](p.png)](u.md)");
    assert!(!out.contains("class=\"zoom\""), "{out}");
    assert_eq!(out.matches("<a ").count(), 1, "{out}");
    assert!(out.contains("<a href=\"/docs/u.md\"><img src=\"/docs/p.png\" alt=\"i\" /></a>"));
}

#[test]
fn image_wrapped_in_every_block_context() {
    for src in [
        "## 图 ![x](p.png)",
        "- 图 ![x](p.png)",
        "> 引用 ![x](p.png)",
        "| a |\n|---|\n| ![x](p.png) |",
    ] {
        assert!(r(src).contains("<a class=\"zoom\""), "{src}");
    }
}

#[test]
fn image_not_wrapped_inside_code() {
    assert_eq!(r("`![x](p.png)`").matches("<a class=\"zoom\"").count(), 0);
    assert_eq!(
        r("```\n![x](p.png)\n```")
            .matches("<a class=\"zoom\"")
            .count(),
        0
    );
}

#[test]
fn rejected_protocol_produces_no_wrapper() {
    let out = r("![x](javascript:alert(1))");
    assert!(!out.contains("<img"), "{out}");
    assert!(!out.contains("class=\"zoom\""), "{out}");
}

#[test]
fn title_stays_on_the_image() {
    let out = r("![x](p.png \"t\")");
    assert!(out.contains(
        "<a class=\"zoom\" href=\"/docs/p.png\"><img src=\"/docs/p.png\" alt=\"x\" title=\"t\" />"
    ));
    let before_img = out.split("<img").next().unwrap();
    assert!(!before_img.contains("title="));
}

#[test]
fn each_image_wrapped_exactly_once() {
    let out = r("![x](p.png) 与 ![y](q.png)");
    assert_eq!(out.matches("<a class=\"zoom\"").count(), 2);
    assert_eq!(out.matches("</a>").count(), 2);
}

// ---------------------------------------------------------------------------
// Titles — old TestAttributeTitles
// ---------------------------------------------------------------------------

#[test]
fn image_title_is_plain_text() {
    let out = r("![a](p.png \"x &amp; y\")");
    assert!(out.contains("title=\"x &amp; y\""));
    assert!(!out.contains('\u{0}'));
    // accepted deviation: comrak does not parse inline markdown in titles.
    let out = r("![a](p.png \"`c`\")");
    assert!(out.contains("title=\"`c`\""), "{out}");
    assert!(!out.contains("<code>"));
    assert!(!out.contains("</a>c"));
}

#[test]
fn link_title_is_plain_text() {
    let out = r("[t](u.md \"`c`\")");
    assert!(out.contains("title=\"`c`\""), "{out}");
    assert!(!out.contains("<code>"));
    assert!(r("[t](u.md \"x &amp; y\")").contains("title=\"x &amp; y\""));
    assert!(r("![a](p.png \"x <b> y\")").contains("title=\"x &lt;b&gt; y\""));
}

#[test]
fn title_quotes_cannot_escape_attributes() {
    let out = r("[t](u.md \"t\\\" onmouseover=\\\"x\")");
    assert!(
        out.contains("title=\"t&quot; onmouseover=&quot;x\""),
        "{out}"
    );
    let out = r("![i](p.png \"t\\\" onerror=\\\"x\")");
    assert!(out.contains("title=\"t&quot; onerror=&quot;x\""), "{out}");
}

// ---------------------------------------------------------------------------
// Link safety — old TestLinkSafety
// ---------------------------------------------------------------------------

#[test]
fn dangerous_protocols_are_rejected() {
    for payload in [
        "[x](javascript:alert(1))",
        "[x](JavaScript:alert(1))",
        "[x](JaVaScRiPt:alert(1))",
        "[x](vbscript:msgbox(1))",
        "[x](data:text/html,<script>alert(1)</script>)",
        "[x](file:///etc/passwd)",
    ] {
        let out = r(payload);
        assert!(!out.contains("href="), "{payload}: {out}");
        assert!(out.contains("x"), "{payload}: {out}");
    }
    assert!(!r("[x](  javascript:alert(1))").contains("href="));
}

#[test]
fn vscode_schemes_are_rejected_on_this_server() {
    // Server deviation from VS Code: there is no `vscode:` handler here.
    for scheme in ["vscode:command:foo", "vscode-insiders:command:foo"] {
        let out = r(&format!("[x]({scheme})"));
        assert!(!out.contains("href="), "{out}");
        assert!(!out.contains("vscode"), "{out}");
    }
}

#[test]
fn dangerous_protocol_in_reference_and_image_rejected() {
    assert!(!r("[x][r]\n\n[r]: javascript:alert(1)").contains("href="));
    assert!(!r("![i](javascript:alert(1))").contains("<img"));
    assert!(!r("![i](vbscript:msgbox(1))").contains("<img"));
}

#[test]
fn safe_schemes_are_preserved() {
    for url in [
        "https://e.com/a",
        "http://e.com/a",
        "mailto:a@b.com",
        "ftp://e.com/f",
        "tel:+123",
        "#anchor",
        "/abs/path.md",
        "rel/path.md",
    ] {
        assert!(
            r(&format!("[x]({url})")).contains("href="),
            "safe link rejected: {url}"
        );
    }
}

#[test]
fn generated_tags_stay_within_the_attribute_whitelist() {
    let allowed = ["href", "title", "src", "alt", "class", "style"];
    let payloads = [
        "[a](b.md \"t\\\" onmouseover=\\\"x\")",
        "![i](p.png \"t\\\" onerror=\\\"x\")",
        "[a](<b\"onmouseover=\"c>)",
        "[x](javascript:alert(1))",
        "![x](javascript:alert(1))",
        "![a\" onerror=\"alert(1)](p.png)",
        "![a\" onerror=\"alert(1)][r]\n\n[r]: p.png",
        "![a\" onerror=\"alert(1)]\n\n[a\" onerror=\"alert(1)]: p.png",
        "[a](x&amp;y.md)",
        "[x](https://e.com/a \"t\\\" onmouseover=\\\"x\")",
    ];
    for payload in payloads {
        let out = r(payload);
        for tag in ["<a ", "<img "] {
            let mut rest = out.as_str();
            while let Some(index) = rest.find(tag) {
                let candidate = &rest[index..];
                let end = candidate.find('>').expect("close tag");
                let names = attr_names(&candidate[..=end]);
                for name in names {
                    assert!(
                        allowed.contains(&name.as_str()),
                        "unexpected attribute {name:?} for {payload:?}: {candidate}"
                    );
                }
                rest = &candidate[end..];
            }
        }
    }
}

#[test]
fn autolink_attribute_injection_is_blocked() {
    let out = r("<foo@bar.com\"onmouseover=\"document.title=1>\n");
    let tag = start_tag(&out, "a").expect("autolink");
    assert_eq!(attr_names(tag), ["href"], "{out}");
    assert!(out.contains("&quot;"), "{out}");
    assert!(!tag.contains("onmouseover"), "{tag}");
}

#[test]
fn http_autolink_escapes_text() {
    let out = r("<http://e.com/x\"y>\n");
    assert!(out.contains("&quot;"), "{out}");
    let tag = start_tag(&out, "a").expect("autolink");
    assert_eq!(attr_names(tag), ["href"], "{out}");
    assert_eq!(attr_value(tag, "href"), Some("http://e.com/x%22y"), "{tag}");
}

#[test]
fn alt_cannot_escape_its_attribute() {
    let payloads = [
        "![a\" onerror=\"alert(1)](p.png)",
        "![a\" onerror=\"alert(1)][r]\n\n[r]: p.png",
        "![a\" onerror=\"alert(1)]\n\n[a\" onerror=\"alert(1)]: p.png",
    ];
    for payload in payloads {
        let out = r(payload);
        assert!(out.contains("<img"), "{payload}: {out}");
        let img = start_tag(&out, "img").expect("img");
        assert_eq!(attr_names(img), ["src", "alt"], "{payload}: {img}");
        let alt = attr_value(img, "alt").expect("alt");
        assert!(!alt.contains('"'), "{payload}: {alt}");
        assert!(alt.contains("&quot;"), "{payload}: {alt}");
    }
}

#[test]
fn raw_html_in_link_label_is_passed_through() {
    // ADR 0006: raw HTML passthrough is intentional. The security boundary is
    // the Trust prompt + CSP at the server layer (covered by server tests).
    let out = r("[a<b>c](u.md)");
    assert!(out.contains("<a href=\"/docs/u.md\">a<b>c</a>"), "{out}");
    let out = r("[<script>alert(1)</script>](u.md)");
    assert!(out.contains("<script>alert(1)</script>"), "{out}");
    let out = r("[**粗**<script>x</script>](u.md)");
    assert!(
        out.contains("<strong>粗</strong><script>x</script>"),
        "{out}"
    );
}

#[test]
fn nul_in_url_never_produces_an_executable_scheme() {
    let out = r("[x](java\u{0}script:alert(1))");
    assert!(!out.contains("href=\"javascript:"), "{out}");
    assert!(
        out.contains("href=\"/docs/java%00script%3Aalert(1)\""),
        "{out}"
    );
}

#[test]
fn url_entities_are_not_double_escaped() {
    for src in ["[a](x&amp;y.md)", "[a](x&y.md)"] {
        let out = r(src);
        assert!(!out.contains("MK0"), "placeholder leak: {out}");
        assert!(!out.contains("&amp;amp;"), "{out}");
        assert!(out.contains("href=\"/docs/x&amp;y.md\""), "{src}: {out}");
    }
}

// ---------------------------------------------------------------------------
// Review regressions — old TestReviewRegressions
// ---------------------------------------------------------------------------

fn assert_linear(src: &str, label: &str, limit_secs: u64) {
    let start = std::time::Instant::now();
    let out = render_markdown(src, "docs/a.md");
    assert!(!out.is_empty());
    assert!(
        start.elapsed() < std::time::Duration::from_secs(limit_secs),
        "{label} took {:?}",
        start.elapsed()
    );
}

#[test]
fn link_bracket_runs_stay_linear() {
    assert_linear(&"[x](".repeat(20_000), "[x]( run", 20);
    assert_linear(&"[".repeat(40_000), "[ run", 20);
}

#[test]
fn delimiter_runs_stay_linear() {
    for ch in ["*", "_"] {
        assert_linear(
            &format!("{}{}", ch.repeat(64_000), "x"),
            "delimiter run",
            20,
        );
    }
}

#[test]
fn mixed_links_and_bare_urls_stay_linear() {
    assert_linear(
        &"[x](u.md) https://e.com/a ".repeat(20_000),
        "mixed links and URLs",
        20,
    );
}

#[test]
fn deep_nesting_does_not_crash() {
    for src in [
        ">".repeat(1000),
        format!("- {}", "- ".repeat(500)) + "x",
        vec!["a"; 200].join("["),
    ] {
        let out = render_markdown(&src, "docs/a.md");
        assert!(!out.is_empty());
    }
}

#[test]
fn nul_is_replaced_not_leaked() {
    let out = r("a\u{0}b\n");
    assert!(!out.contains('\u{0}'), "{out}");
    assert!(out.contains("a\u{fffd}b"), "{out}");
}

#[test]
fn escaped_gt_has_no_marker_leak() {
    let out = r("\\>\n");
    assert!(!out.contains('\u{e000}'), "{out}");
    assert!(!out.contains('\u{e001}'), "{out}");
    assert!(out.contains("&gt;"), "{out}");
}

#[test]
fn code_span_has_no_placeholder_leak() {
    for src in ["`\\*`", "`a\\`b`", "`\\>`"] {
        let out = render_markdown(&(src.to_string() + "\n"), "docs/a.md");
        assert!(!out.contains("MK0"), "{src:?} -> {out}");
        for ch in ['\u{e010}', '\u{e013}', '\u{e000}', '\u{e001}'] {
            assert!(!out.contains(ch), "{src:?} leaked {ch:?}");
        }
    }
}

#[test]
fn heading_ids_are_never_generated() {
    for src in ["## a\n## a-1\n## a", "## 重复\n\n## 重复", "# a\n# a\n# a"] {
        let out = render_markdown(src, "docs/a.md");
        assert!(!out.contains("id="), "{out}");
    }
}

#[test]
fn nested_image_in_link_label_survives() {
    let out = r("[![build](badge.svg)](https://ci.example/run)\n");
    assert!(out.contains("<img"), "{out}");
    assert!(!out.contains("&lt;img"), "{out}");
    assert!(out.contains("href=\"https://ci.example/run\""));
}

#[test]
fn emphasis_inside_inline_link_label() {
    let out = r("[**bold**](x.md)\n");
    assert!(out.contains("<strong>bold</strong>"), "{out}");
    assert!(!out.contains("**bold**"), "{out}");
}

#[test]
fn url_with_balanced_parens() {
    let out = r("[x](https://e.com/wiki/Foo_(bar))\n");
    assert!(out.contains("Foo_(bar)"), "{out}");
    assert!(!out.contains("</a>)"), "{out}");
}

#[test]
fn reference_definitions_inside_fences_are_ignored() {
    let out = r("```\n[r]: https://evil.example\n```\n\n[r]\n");
    assert!(out.contains("[r]: https://evil.example"), "{out}");
    assert!(!out.contains("href=\"https://evil.example\""), "{out}");
}

#[test]
fn bare_dashes_are_setext_not_a_table() {
    // ADR 0007: comrak/VS Code parse `文字 | 文字\n---` as a Setext heading.
    let out = r("文字 | 文字\n---\n");
    assert!(!out.contains("<table>"), "{out}");
    assert!(out.contains("<h2>文字 | 文字</h2>"), "{out}");
}

#[test]
fn crlf_input_is_handled() {
    let out = r("a\r\nb\r\n");
    assert!(out.contains("a\nb"), "{out}");
}
