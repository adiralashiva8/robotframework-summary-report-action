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
| `owners` | `""` | Comma-separated list of owner tags (e.g., `"alice,bob,charlie"`). Empty = show all tags |
| `module_tag_prefix` | `""` | Filter module tags by prefix. Empty = use suite names |

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
    owners: 'alice,bob,charlie'
```

### With Module Tag Prefix

If your tests use tags like `module:accounts`:

```yaml
- name: Summary Report
  if: always()
  uses: adiralashiva8/robotframework-summary-report-action@v1
  with:
    output_xml_path: 'results/output.xml'
    github_token: ${{ secrets.GITHUB_TOKEN }}
    module_tag_prefix: 'module:'
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
    [Tags]    alice    smoke
    Log    Test
```

Then specify which tags are owners: `owners: 'alice,bob,charlie'`.
Leave `owners` empty to show stats for **all** tags.

### Module Tags

By default, **suite names** are used as modules. To use tags instead:

```robotframework
Verify Account
    [Tags]    module:accounts    bob
```

Then set `module_tag_prefix: 'module:'`.

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
