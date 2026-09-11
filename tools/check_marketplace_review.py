#!/usr/bin/env python3
"""Read-only check that published main matches both marketplace reports."""
import base64
import argparse
import json
import re
import subprocess
import sys

REPOSITORY = "MadMatt341/omarchy-keyboard-settings"
DEFAULT_ISSUE = 6363


def api(path):
    result = subprocess.run(
        ["gh", "api", path], check=True, capture_output=True, text=True, timeout=30
    )
    return json.loads(result.stdout)


def report_refs(comments):
    reports = {}
    for comment in comments:
        if (comment.get("user", {}).get("login") != "github-actions[bot]"
                or (comment.get("performed_via_github_app") or {}).get("slug") != "github-actions"):
            continue
        body = comment.get("body", "")
        for marker in ("marketplace-validation", "marketplace-update-validation", "marketplace-security-baseline"):
            if body.startswith("<!-- " + marker):
                if marker in reports:
                    raise ValueError("Duplicate marketplace reports; inspect the issue manually")
                reports[marker] = body
    validations = [reports[key] for key in ("marketplace-validation", "marketplace-update-validation") if key in reports]
    if len(validations) != 1:
        raise ValueError("Missing or duplicate marketplace validation reports")
    validation = validations[0]
    update = "marketplace-update-validation" in reports
    pattern = (r"Quattro compatibility passed at update commit `([0-9a-f]{7,40})(?:…)?`" if update
               else r"Quattro compatibility passed at commit `([0-9a-f]{7,40})`")
    match = re.search(pattern, validation)
    ready = "**Ready for verified update review.**" if update else "**Ready for listing review.**"
    if not match or ready not in validation:
        raise ValueError("Missing, failed, or unrecognized marketplace validation report")
    baseline = reports.get("marketplace-security-baseline", "")
    payload = re.match(r"<!-- marketplace-security-baseline:v4 ([A-Za-z0-9+/=]+) -->", baseline)
    if not payload:
        raise ValueError("Missing or unrecognized security baseline report")
    data = json.loads(base64.b64decode(payload[1], validate=True))
    sha = data.get("commitSha", "")
    if (data.get("schemaVersion") != 2 or data.get("repository") != REPOSITORY
            or "madmatt.keyboard-settings" not in data.get("pluginIds", [])
            or not re.fullmatch(r"[0-9a-f]{40}", sha)):
        raise ValueError("Unexpected security baseline identity/schema")
    return match[1], sha


def check(read=api, issue=DEFAULT_ISSUE):
    if not isinstance(issue, int) or issue <= 0:
        raise ValueError("Issue number must be positive")
    head = read(f"repos/{REPOSITORY}/commits/main")["sha"]
    comments = []
    for page in range(1, 101):
        batch = read(f"repos/omacom/omarchy-plugin-marketplace/issues/{issue}/comments?per_page=100&page={page}")
        comments.extend(batch)
        if len(batch) < 100:
            break
    else:
        raise ValueError("Too many comments; inspect the issue manually")
    validation_ref, baseline_sha = report_refs(comments)
    # Resolve the bot's abbreviated SHA through GitHub, including ambiguity errors.
    validation_sha = read(f"repos/{REPOSITORY}/commits/{validation_ref}")["sha"]
    if read(f"repos/{REPOSITORY}/commits/main")["sha"] != head:
        raise ValueError("main changed during this check; rerun")
    if head != validation_sha or head != baseline_sha:
        raise ValueError(
            f"Review drift: main={head}, validation={validation_sha}, baseline={baseline_sha}. "
            "Update the existing submission and wait for both reports; keep main frozen."
        )
    return f"Both marketplace reports in #{issue} cover published main {head}. Manual approval and marketplace publication are separate."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", type=int, default=DEFAULT_ISSUE,
                        help="Current submission/update issue number (default: %(default)s)")
    args = parser.parse_args()
    try:
        print(check(issue=args.issue))
    except (ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(f"Marketplace review check failed: {error}", file=sys.stderr)
        sys.exit(1)
