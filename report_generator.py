#!/usr/bin/env python3
"""
Robot Framework Summary Report Generator for GitHub Actions.

Parses Robot Framework output.xml file(s) and generates a Markdown
summary report, then posts it as a comment on a Pull Request or Commit.
"""

import glob
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests
from robot.api import ExecutionResult

# ─── Constants ────────────────────────────────────────────────────────────────

COMMENT_MARKER = "<!-- rf-summary-report-action -->"

# ─── Parsing ──────────────────────────────────────────────────────────────────


def resolve_output_paths(pattern):
    """Resolve output.xml path(s) from a glob pattern or explicit path."""
    paths = sorted(glob.glob(pattern, recursive=True))
    if not paths:
        if os.path.isfile(pattern):
            return [pattern]
        print(f"::error::No files matched pattern: {pattern}")
        sys.exit(1)
    return paths


def parse_output_xml(paths):
    """Parse one or more output.xml files and extract all statistics."""
    if len(paths) == 1:
        result = ExecutionResult(paths[0])
    else:
        result = ExecutionResult(*paths, merge=True)

    all_tests = list(result.suite.all_tests)

    # ── Overall stats
    total = len(all_tests)
    passed = sum(1 for t in all_tests if t.status == "PASS")
    failed = total - passed
    pass_pct = round((passed / total) * 100, 2) if total > 0 else 0.0

    overall = {"total": total, "pass": passed, "fail": failed, "pass_pct": pass_pct}

    # ── Per-tag stats
    tag_data = defaultdict(lambda: {"total": 0, "pass": 0, "fail": 0})
    for test in all_tests:
        for tag in test.tags:
            tag_data[tag]["total"] += 1
            if test.status == "PASS":
                tag_data[tag]["pass"] += 1
            else:
                tag_data[tag]["fail"] += 1

    # ── Per-suite (module) stats
    suite_data = defaultdict(lambda: {"total": 0, "pass": 0, "fail": 0})
    for test in all_tests:
        suite_name = test.parent.name
        suite_data[suite_name]["total"] += 1
        if test.status == "PASS":
            suite_data[suite_name]["pass"] += 1
        else:
            suite_data[suite_name]["fail"] += 1

    # ── Failed test details
    failed_tests_info = []
    for test in all_tests:
        if test.status == "FAIL":
            failed_tests_info.append({
                "name": test.name,
                "message": (test.message or "").strip() or "Unknown error",
                "tags": list(test.tags),
                "module": test.parent.name,
            })

    # ── Passed test details
    passed_tests_info = []
    for test in all_tests:
        if test.status == "PASS":
            passed_tests_info.append({
                "name": test.name,
                "tags": list(test.tags),
                "module": test.parent.name,
            })

    # ── Error messages by module and globally
    error_module_list = []
    error_global = Counter()
    for ft in failed_tests_info:
        msg = ft["message"]
        error_module_list.append({"message": msg, "module": ft["module"]})
        error_global[msg] += 1

    # ── Failed keywords
    failed_kw_counter = Counter()
    for test in all_tests:
        if test.status == "FAIL":
            for kw_display in _collect_leaf_failed_keywords(test):
                failed_kw_counter[kw_display] += 1

    return {
        "overall": overall,
        "tag_data": dict(tag_data),
        "suite_data": dict(suite_data),
        "failed_tests": failed_tests_info,
        "passed_tests": passed_tests_info,
        "error_module_list": error_module_list,
        "error_global": error_global,
        "failed_keywords": failed_kw_counter,
    }


def _collect_leaf_failed_keywords(item):
    """Recursively collect the deepest (leaf-level) failing keywords."""
    keywords = []
    body = getattr(item, "body", None) or getattr(item, "keywords", [])
    for child in body:
        status = getattr(child, "status", None)
        if status == "FAIL":
            child_failures = _collect_leaf_failed_keywords(child)
            if child_failures:
                keywords.extend(child_failures)
            else:
                name = getattr(child, "name", "") or ""
                args = getattr(child, "args", [])
                display = name
                if args:
                    display += " " + " ".join(str(a) for a in args)
                keywords.append(display.strip())
    return keywords


# ─── Markdown Helpers ─────────────────────────────────────────────────────────


def _md_esc(text):
    """Escape characters that have special meaning in Markdown tables."""
    return str(text).replace("\\", "\\\\").replace("|", "\\|")


def _section_start(title, emoji, collapsible):
    """Open a section — collapsible details block (open by default) or plain header."""
    if collapsible:
        return f'\n<details open>\n<summary><b>{emoji} {title}</b></summary>\n'
    return f"\n### {emoji} {title}\n"


def _section_end(collapsible):
    if collapsible:
        return "\n</details>\n"
    return "\n"


# ─── Markdown Report Generation ──────────────────────────────────────────────


def generate_markdown_report(data, config):
    """Generate the full Markdown summary report."""
    overall = data["overall"]
    project = config["project_name"]
    top_n = config["top_n"]
    owner_list = config["owner_list"]
    module_prefix = config["module_prefix"]
    collapsible = config["collapsible"]

    lines = [COMMENT_MARKER, ""]

    # ── Header with status badge ──────────────────────────────────────────
    pct = overall["pass_pct"]
    if overall["fail"] == 0:
        status_emoji = "✅"
    else:
        status_emoji = "❌"

    lines.append(f"## {status_emoji} {_md_esc(project)} Test Report")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 1. Project Status Table ───────────────────────────────────────────
    if config["show_project_status"]:
        lines.append("### 📊 Project Status")
        lines.append("")
        lines.append("| Total | ✅ Passed | ❌ Failed | Pass % |")
        lines.append("|:---:|:---:|:---:|:---:|")
        lines.append(
            f"| **{overall['total']}** "
            f"| **{overall['pass']}** "
            f"| **{overall['fail']}** "
            f"| **{pct}%** |"
        )
        lines.append("")

    # ── 2. Tag Stats By Owner ─────────────────────────────────────────────
    if config["show_owner_stats"]:
        owner_tags = _filter_owner_tags(data["tag_data"], owner_list)
        if owner_tags:
            lines.append(_section_start("Tag Stats By Owner", "👥", collapsible))
            lines.append("")
            lines.append("| Tag | Total | Passed | Failed | Pass % |")
            lines.append("|:---|:---:|:---:|:---:|:---:|")
            for tag_name, stats in sorted(owner_tags.items(), key=lambda x: x[0].lower()):
                p = stats["pass"]
                f = stats["fail"]
                t = stats["total"]
                tag_pct = round((p / t) * 100, 2) if t > 0 else 0.0
                lines.append(f"| {_md_esc(tag_name)} | {t} | {p} | {f} | {tag_pct}% |")
            lines.append("")
            lines.append(_section_end(collapsible))

    # ── 3. Top N Failed Modules ───────────────────────────────────────────
    if config["show_failed_modules"]:
        if module_prefix:
            module_tags = _filter_tags_by_prefix(data["tag_data"], module_prefix)
            module_items = [(n, s) for n, s in module_tags.items() if s["fail"] > 0]
        else:
            module_items = [(n, s) for n, s in data["suite_data"].items() if s["fail"] > 0]

        if module_items:
            module_items.sort(key=lambda x: x[1]["fail"], reverse=True)
            module_items = module_items[:top_n]
            lines.append(_section_start(f"Top {top_n} Failed Modules", "📦", collapsible))
            lines.append("")
            lines.append("| Module | Total | Passed | Failed | Pass % |")
            lines.append("|:---|:---:|:---:|:---:|:---:|")
            for name, stats in module_items:
                p = stats["pass"]
                f = stats["fail"]
                t = stats["total"]
                mod_pct = round((p / t) * 100, 2) if t > 0 else 0.0
                lines.append(f"| {_md_esc(name)} | {t} | {p} | {f} | {mod_pct}% |")
            lines.append("")
            lines.append(_section_end(collapsible))

    # ── 4. Top N Common Failures In Module ────────────────────────────────
    if config["show_failures_by_module"] and data["error_module_list"]:
        pair_counter = Counter()
        for entry in data["error_module_list"]:
            pair_counter[(entry["message"], entry["module"])] += 1
        top_pairs = pair_counter.most_common(top_n)

        lines.append(_section_start(f"Top {top_n} Failures By Module", "🔍", collapsible))
        lines.append("")
        lines.append("| Error Message | Module | Count |")
        lines.append("|:---|:---:|:---:|")
        for (msg, mod), count in top_pairs:
            lines.append(f"| {_md_esc(msg)} | {_md_esc(mod)} | {count} |")
        lines.append("")
        lines.append(_section_end(collapsible))

    # ── 5. Top N Common Failures ──────────────────────────────────────────
    if config["show_common_failures"] and data["error_global"]:
        top_errors = data["error_global"].most_common(top_n)
        lines.append(_section_start(f"Top {top_n} Common Failures", "⚠️", collapsible))
        lines.append("")
        lines.append("| Error Message | Count |")
        lines.append("|:---|:---:|")
        for msg, count in top_errors:
            lines.append(f"| {_md_esc(msg)} | {count} |")
        lines.append("")
        lines.append(_section_end(collapsible))

    # ── 6. Top N Failed Keywords ──────────────────────────────────────────
    if config["show_failed_keywords"] and data["failed_keywords"]:
        top_kws = data["failed_keywords"].most_common(top_n)
        lines.append(_section_start(f"Top {top_n} Failed Keywords", "🔑", collapsible))
        lines.append("")
        lines.append("| Keyword | Count |")
        lines.append("|:---|:---:|")
        for kw, count in top_kws:
            lines.append(f"| `{_md_esc(kw)}` | {count} |")
        lines.append("")
        lines.append(_section_end(collapsible))

    # ── 7. Failed Tests List ──────────────────────────────────────────────
    if config["show_failed_tests"] and data["failed_tests"]:
        lines.append(_section_start("Failed Tests", "🚨", collapsible))
        lines.append("")
        lines.append("| # | Test Name | Module | Error |")
        lines.append("|:---:|:---|:---|:---|")
        for i, ft in enumerate(data["failed_tests"], 1):
            lines.append(
                f"| {i} | {_md_esc(ft['name'])} | {_md_esc(ft['module'])} | {_md_esc(ft['message'])} |"
            )
        lines.append("")
        lines.append(_section_end(collapsible))

    # ── 8. Passed Tests List ──────────────────────────────────────────────
    if config["show_passed_tests"] and data["passed_tests"]:
        lines.append(_section_start("Passed Tests", "✅", collapsible))
        lines.append("")
        lines.append("| # | Test Name | Module |")
        lines.append("|:---:|:---|:---|")
        for i, pt in enumerate(data["passed_tests"], 1):
            lines.append(f"| {i} | {_md_esc(pt['name'])} | {_md_esc(pt['module'])} |")
        lines.append("")
        lines.append(_section_end(collapsible))

    # ── Footer ────────────────────────────────────────────────────────────
    lines.append("---")
    lines.append(
        '_🤖 Generated by **Robot Framework Summary Report Action**_'
    )

    return "\n".join(lines)


def _filter_owner_tags(tag_data, owner_list):
    """Filter tags to only those in the owner list. If list is empty, return all."""
    if not owner_list:
        return dict(tag_data)
    normalized = {name.strip().lower() for name in owner_list}
    return {
        tag_name: stats
        for tag_name, stats in tag_data.items()
        if tag_name.lower() in normalized
    }


def _filter_tags_by_prefix(tag_data, prefix):
    """Filter and rename tag entries by prefix. If prefix is empty, return all."""
    if not prefix:
        return dict(tag_data)
    filtered = {}
    for tag_name, stats in tag_data.items():
        if tag_name.lower().startswith(prefix.lower()):
            display_name = tag_name[len(prefix):]
            if display_name:
                filtered[display_name] = stats
    return filtered


# ─── GitHub API Helpers ───────────────────────────────────────────────────────

API_BASE = "https://api.github.com"


def _headers(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _find_existing_comment(url, token):
    """Find an existing comment with our marker."""
    page = 1
    while True:
        resp = requests.get(
            url, headers=_headers(token), params={"per_page": 100, "page": page}
        )
        resp.raise_for_status()
        comments = resp.json()
        if not comments:
            break
        for comment in comments:
            if COMMENT_MARKER in (comment.get("body") or ""):
                return comment["id"]
        page += 1
    return None


def post_pr_comment(html, token, repo, pr_number):
    """Post or update a comment on a Pull Request."""
    list_url = f"{API_BASE}/repos/{repo}/issues/{pr_number}/comments"
    existing_id = _find_existing_comment(list_url, token)

    if existing_id:
        url = f"{API_BASE}/repos/{repo}/issues/comments/{existing_id}"
        resp = requests.patch(url, headers=_headers(token), json={"body": html})
        print(f"Updated existing PR comment #{existing_id}")
    else:
        resp = requests.post(list_url, headers=_headers(token), json={"body": html})
        print(f"Created new PR comment")

    resp.raise_for_status()
    return resp.json()


def post_commit_comment(html, token, repo, sha):
    """Post or update a comment on a Commit."""
    list_url = f"{API_BASE}/repos/{repo}/commits/{sha}/comments"
    existing_id = _find_existing_comment(list_url, token)

    if existing_id:
        url = f"{API_BASE}/repos/{repo}/comments/{existing_id}"
        resp = requests.patch(url, headers=_headers(token), json={"body": html})
        print(f"Updated existing commit comment #{existing_id}")
    else:
        resp = requests.post(list_url, headers=_headers(token), json={"body": html})
        print(f"Created new commit comment")

    resp.raise_for_status()
    return resp.json()


# ─── GitHub Actions Helpers ───────────────────────────────────────────────────


def get_pr_number():
    """Extract PR number from the GitHub event payload."""
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or not os.path.isfile(event_path):
        return None
    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)
    # pull_request event
    pr = event.get("pull_request")
    if pr:
        return pr.get("number")
    # issue_comment event on a PR
    issue = event.get("issue", {})
    if issue.get("pull_request"):
        return issue.get("number")
    return None


def set_output(name, value):
    """Set a GitHub Actions output variable."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            # Handle multiline values
            if "\n" in str(value):
                import uuid

                delimiter = uuid.uuid4().hex
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
            else:
                f.write(f"{name}={value}\n")


# ─── Main ─────────────────────────────────────────────────────────────────────


def _is_true(val):
    """Check if an env var string is truthy."""
    return str(val).strip().lower() in ("true", "1", "yes")


def main():
    # Read inputs from environment
    output_xml_path = os.environ.get("INPUT_OUTPUT_XML_PATH", "output.xml")
    github_token = os.environ.get("INPUT_GITHUB_TOKEN", "")
    project_name = os.environ.get("INPUT_PROJECT_NAME", "Robot Framework")
    owners_raw = os.environ.get("INPUT_OWNERS", "")
    owner_list = [o.strip() for o in owners_raw.split(",") if o.strip()]
    module_prefix = os.environ.get("INPUT_MODULE_TAG_PREFIX", "")
    top_n = int(os.environ.get("INPUT_TOP_N", "5"))
    input_sha = os.environ.get("INPUT_SHA", "")
    comment_on = os.environ.get("INPUT_COMMENT_ON", "pr").lower().strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    # Section toggles
    config = {
        "project_name": project_name,
        "top_n": top_n,
        "owner_list": owner_list,
        "module_prefix": module_prefix,
        "show_project_status": _is_true(os.environ.get("INPUT_SHOW_PROJECT_STATUS", "true")),
        "show_owner_stats": _is_true(os.environ.get("INPUT_SHOW_OWNER_STATS", "true")),
        "show_failed_modules": _is_true(os.environ.get("INPUT_SHOW_FAILED_MODULES", "true")),
        "show_failures_by_module": _is_true(os.environ.get("INPUT_SHOW_FAILURES_BY_MODULE", "true")),
        "show_common_failures": _is_true(os.environ.get("INPUT_SHOW_COMMON_FAILURES", "true")),
        "show_failed_keywords": _is_true(os.environ.get("INPUT_SHOW_FAILED_KEYWORDS", "true")),
        "show_passed_tests": _is_true(os.environ.get("INPUT_SHOW_PASSED_TESTS", "false")),
        "show_failed_tests": _is_true(os.environ.get("INPUT_SHOW_FAILED_TESTS", "true")),
        "collapsible": _is_true(os.environ.get("INPUT_COLLAPSIBLE_SECTIONS", "true")),
    }

    # Resolve SHA
    sha = input_sha or os.environ.get("GITHUB_SHA", "")

    # Resolve output.xml path(s)
    paths = resolve_output_paths(output_xml_path)
    print(f"Parsing output file(s): {paths}")

    # Parse and generate
    data = parse_output_xml(paths)
    report = generate_markdown_report(data, config)

    # Set outputs
    overall = data["overall"]
    set_output("total_tests", overall["total"])
    set_output("passed_tests", overall["pass"])
    set_output("failed_tests", overall["fail"])
    set_output("pass_percentage", overall["pass_pct"])
    set_output("report_markdown", report)

    # Print summary to workflow log
    print(f"\n{'='*60}")
    print(f"  {project_name} Summary")
    print(f"  Total: {overall['total']}  Pass: {overall['pass']}  "
          f"Fail: {overall['fail']}  Pass%: {overall['pass_pct']}")
    print(f"{'='*60}\n")

    # Post comment
    if not github_token:
        print("::warning::No GitHub token provided. Skipping comment posting.")
        print("Report HTML written to outputs only.")
        return

    if not repo:
        print("::warning::GITHUB_REPOSITORY not set. Skipping comment posting.")
        return

    pr_number = get_pr_number()

    if comment_on in ("pr", "both") and pr_number:
        post_pr_comment(report, github_token, repo, pr_number)
    elif comment_on == "pr" and not pr_number:
        print("::warning::Not a PR context. Falling back to commit comment.")
        if sha:
            post_commit_comment(report, github_token, repo, sha)
        else:
            print("::error::No SHA available for commit comment.")
            sys.exit(1)

    if comment_on in ("commit", "both") and sha:
        post_commit_comment(report, github_token, repo, sha)
    elif comment_on == "commit" and not sha:
        print("::error::No commit SHA available.")
        sys.exit(1)

    print("Report posted successfully!")


if __name__ == "__main__":
    main()
