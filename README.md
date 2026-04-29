# Robot Framework Summary Report Action

A GitHub Action that parses Robot Framework `output.xml` and posts a **beautiful summary report** as a comment on your Pull Request or Commit — **zero config needed**.

## What You Get

- **Project status table** — overall numbers
- **Owner stats** — per-tag breakdown (who owns failing tests?)
- **Failed modules** — which suites are broken?
- **Failure details** — common errors, grouped by module or globally
- **Failed keywords** — which Robot keywords fail most?
- **Failed/Passed test lists** — expandable details
- **Collapsible sections** — expanded by default, click to collapse

Every section can be **toggled on/off** via action inputs.

---

## Quick Start (3 lines!)

Add this to your workflow — that's it:

```yaml
- name: RF Summary Report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}
```

The action handles Python setup, dependency installation, and comment posting automatically.

### Full Minimal Workflow

```yaml
name: Tests
on: [push, pull_request]

permissions:
  contents: read
  pull-requests: write

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Robot Framework
        run: |
          pip install robotframework
          robot --outputdir results tests/
        continue-on-error: true

      - name: Summary Report
        if: always()
        uses: adiralashiva8/robotframework-summary-report-action@v1
        with:
          output_xml_path: 'results/output.xml'
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

---

## Inputs

### Required

| Input | Description |
|---|---|
| `output_xml_path` | Path to `output.xml`. Supports globs: `results/**/*.xml` |
| `github_token` | GitHub token. Use `${{ secrets.GITHUB_TOKEN }}` |

### Display Options

| Input | Default | Description |
|---|---|---|
| `project_name` | `Robot Framework Summary Report` | Project name in report header |
| `top_n` | `5` | Items per section (top failures, modules, keywords) |
| `comment_on` | `pr` | Where to post: `pr`, `commit`, or `both` |
| `sha` | auto | Commit SHA (auto-detected from workflow context) |

### Tag Filtering

| Input | Default | Description |
|---|---|---|
| `owner_name_tags` | `""` | Comma-separated list of tags that represent owners (e.g., `"alice,bob,charlie"`). Shown in Owner Stats |
| `exclude_tags` | `""` | Comma-separated list of tags to exclude from module stats (e.g., `"smoke,regression"`). Tags not in `owner_name_tags` or `exclude_tags` are treated as modules |

### Section Toggles

Show or hide any section of the report:

| Input | Default | Description |
|---|---|---|
| `show_project_status` | `true` | Overall status table |
| `show_owner_stats` | `true` | Tag stats by owner |
| `show_failed_modules` | `true` | Top failed modules |
| `show_failures_by_module` | `true` | Failures grouped by module |
| `show_common_failures` | `true` | Most common error messages |
| `show_failed_keywords` | `true` | Most failing keywords |
| `show_failed_tests` | `true` | List of failed tests with errors |
| `show_passed_tests` | `false` | List of passed tests |
| `collapsible_sections` | `true` | Wrap detail sections in collapsible blocks |

## Outputs

| Output | Description |
|---|---|
| `report_markdown` | Generated Markdown report content |
| `total_tests` | Total number of tests |
| `passed_tests` | Number of passed tests |
| `failed_tests` | Number of failed tests |
| `skipped_tests` | Number of skipped tests |
| `pass_percentage` | Pass percentage |

---

## Usage Examples

### Comment on Commit Instead of PR

```yaml
- name: Summary Report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}
    comment_on: 'commit'
```

### Minimal Report (Status Only)

```yaml
- name: Summary Report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}
    show_owner_stats: 'false'
    show_failed_modules: 'false'
    show_failures_by_module: 'false'
    show_common_failures: 'false'
    show_failed_keywords: 'false'
```

### Full Report with Everything

```yaml
- name: Summary Report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'My Project'
    show_passed_tests: 'true'
    collapsible_sections: 'true'
    top_n: '10'
```

### With Specific Owners

Only show stats for specific team members:

```yaml
- name: Summary Report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}
    owner_name_tags: 'alice,bob,charlie'
```

### With Exclude Tags

Exclude certain tags (e.g., test types) from module stats:

```yaml
- name: Summary Report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}
    owner_name_tags: 'alice,bob,charlie'
    exclude_tags: 'smoke,regression,sanity'
```

### Use Outputs in Next Steps

```yaml
- name: Summary Report
  id: report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}

- name: Fail if tests failed
  if: steps.report.outputs.failed_tests != '0'
  run: exit 1
```

---

## Tag Conventions

### Owner Tags

Tag tests with owner names to get per-person stats:

```robotframework
*** Test Cases ***
Verify Login
    [Tags]    alice    smoke    accounts
    Log    Test
```

Then specify which tags are owners: `owner_name_tags: 'alice,bob,charlie'`.

### Module Tags

Any tag that is **not** in `owner_name_tags` and **not** in `exclude_tags` is treated as a module:

```robotframework
Verify Account
    [Tags]    accounts    bob    smoke
```

With `owner_name_tags: 'bob'` and `exclude_tags: 'smoke'`, the tag `accounts` becomes a module.

### Exclude Tags

Use `exclude_tags` to filter out tags you don't want in module stats (e.g., test types):

```yaml
exclude_tags: 'smoke,regression,sanity'
```

---

## How It Works

1. User adds the action to their workflow (just `uses:` + 2 inputs)
2. Action automatically installs Python + dependencies
3. Parses Robot Framework `output.xml` using the `robot.api` library
4. Generates a styled Markdown report with configurable sections
5. Posts as a GitHub comment on the PR or commit
6. On re-runs, **updates** the existing comment (no duplicates)

---

## Permissions

```yaml
permissions:
  contents: read          # Always needed
  pull-requests: write    # For PR comments
```

For commit comments, also add `contents: write`.

---

## License

MIT — see [LICENSE](LICENSE).
