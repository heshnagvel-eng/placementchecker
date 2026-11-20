"""
Placement Eligibility Checker
Python 3.10+
Normal mode: uses an OpenAI-compatible Chat Completions API.
Offline demo mode: set DEMO_MODE=1 to use the clearly-labelled local demo extractor.
Student records are NEVER sent to the LLM.
"""
import csv
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ALLOWED_BRANCHES = {"CSE", "IT", "AIDS", "ECE", "EEE", "MECH", "CIVIL"}
REQUIRED_FIELDS = {"branches", "min_cgpa", "max_backlogs", "batch", "summary"}
BRANCH_NAMES = {
    "CSE": r"\bCSE\b|computer science",
    "IT": r"\bIT\b|information technology",
    "AIDS": r"\bAIDS\b|artificial intelligence and data science",
    "ECE": r"\bECE\b|electronics and communication",
    "EEE": r"\bEEE\b|electrical and electronics",
    "MECH": r"\bMECH\b|mechanical",
    "CIVIL": r"\bCIVIL\b|civil engineering",
}

def read_csv(filename, required_columns):
    path = BASE_DIR / filename
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not set(required_columns).issubset(reader.fieldnames):
                raise ValueError(f"{filename} is missing required columns: {required_columns}")
            rows = list(reader)
            if not rows:
                raise ValueError(f"{filename} contains no data rows")
            return rows
    except (OSError, csv.Error) as exc:
        raise RuntimeError(f"Cannot read {filename}: {exc}") from exc

def system_prompt():
    return (
        "You extract placement eligibility criteria from one job post. Return JSON only, "
        "with exactly these five keys: branches (list containing only CSE, IT, AIDS, ECE, "
        "EEE, MECH, CIVIL, or ['ALL']); min_cgpa (number 0..10 or null); "
        "max_backlogs (whole number or null); batch (year integer or null); "
        "summary (12 words or fewer). Extract only facts explicitly stated. "
        "Do not convert percentages to CGPA. 'No backlogs' means 0. "
        "Do not infer branches. ALL only if the post says any branch or all branches."
    )

def call_llm(job_text):
    """Call an OpenAI-compatible API; only job_text is included in the request."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Use DEMO_MODE=1 for offline demonstration.")
    endpoint = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/chat/completions")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": job_text}
        ]
    }
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        body = json.loads(response.read().decode("utf-8"))
    return json.loads(body["choices"][0]["message"]["content"])

def demo_extract(job_text):
    """
    Offline demonstration extractor for sample data and testing only.
    This is NOT an LLM and must not be presented as one.
    """
    text = job_text.lower()
    branches = []
    for branch, pattern in BRANCH_NAMES.items():
        if re.search(pattern, text, re.I):
            branches.append(branch)
    if re.search(r"\b(any branch|all branches)\b", text):
        branches = ["ALL"]

    cgpa_match = re.search(r"\b(?:cgpa|c\.g\.p\.a\.?)\s*(?:of|:|is)?\s*(\d+(?:\.\d+)?)", text)
    min_cgpa = float(cgpa_match.group(1)) if cgpa_match else None

    max_backlogs = None
    if re.search(r"\bno backlogs?\b", text):
        max_backlogs = 0
    else:
        m = re.search(r"\bmaximum\s+(\d+)\s+backlogs?\b|\bmax(?:imum)?\s+(\d+)\s+backlogs?\b", text)
        if m:
            max_backlogs = int(next(x for x in m.groups() if x is not None))

    batch_match = re.search(r"\bbatch\s*(?:of|:)?\s*(20\d{2})\b", text)
    batch = int(batch_match.group(1)) if batch_match else None
    return {
        "branches": branches,
        "min_cgpa": min_cgpa,
        "max_backlogs": max_backlogs,
        "batch": batch,
        "summary": "Criteria extracted from the job post"
    }

def fact_check(raw, job_text):
    """Reject extracted facts that cannot be verified in the original post."""
    text = job_text.lower()
    result = dict(raw)
    branches = result.get("branches")
    if not isinstance(branches, list):
        result["branches"] = []
    else:
        verified = []
        for b in branches:
            if b == "ALL":
                if re.search(r"\b(any branch|all branches)\b", text):
                    verified.append("ALL")
            elif b in ALLOWED_BRANCHES and re.search(BRANCH_NAMES[b], text, re.I):
                verified.append(b)
        result["branches"] = list(dict.fromkeys(verified))

    # A numeric CGPA must be explicitly written after the CGPA label.
    cgpa_match = re.search(r"\b(?:cgpa|c\.g\.p\.a\.?)\s*(?:of|:|is)?\s*(\d+(?:\.\d+)?)", text)
    if not cgpa_match:
        result["min_cgpa"] = None
    else:
        try:
            stated = float(cgpa_match.group(1))
            if result.get("min_cgpa") is None or float(result["min_cgpa"]) != stated:
                result["min_cgpa"] = None
        except (TypeError, ValueError):
            result["min_cgpa"] = None

    if re.search(r"\bno backlogs?\b", text):
        if result.get("max_backlogs") != 0:
            result["max_backlogs"] = None
    else:
        m = re.search(r"\b(?:maximum|max(?:imum)?)\s+(\d+)\s+backlogs?\b", text)
        if not m or result.get("max_backlogs") != int(m.group(1)):
            result["max_backlogs"] = None

    m = re.search(r"\bbatch\s*(?:of|:)?\s*(20\d{2})\b", text)
    if not m or result.get("batch") != int(m.group(1)):
        result["batch"] = None
    return result

def validate_reply(raw, job_text):
    if not isinstance(raw, dict) or set(raw.keys()) != REQUIRED_FIELDS:
        raise ValueError("JSON must contain exactly the five required fields")
    branches = raw["branches"]
    if not isinstance(branches, list) or any(b not in ALLOWED_BRANCHES | {"ALL"} for b in branches):
        raise ValueError("branches must be a list of allowed branch names")
    if "ALL" in branches and len(branches) != 1:
        raise ValueError("ALL must be the only branch entry")
    cgpa = raw["min_cgpa"]
    if cgpa is not None and (isinstance(cgpa, bool) or not isinstance(cgpa, (int, float)) or not 0 <= cgpa <= 10):
        raise ValueError("min_cgpa must be a number from 0 to 10 or null")
    backlogs = raw["max_backlogs"]
    if backlogs is not None and (isinstance(backlogs, bool) or not isinstance(backlogs, int) or backlogs < 0):
        raise ValueError("max_backlogs must be a non-negative whole number or null")
    batch = raw["batch"]
    if batch is not None and (isinstance(batch, bool) or not isinstance(batch, int) or not 2000 <= batch <= 2100):
        raise ValueError("batch must be a year or null")
    summary = raw["summary"]
    if not isinstance(summary, str) or len(summary.split()) > 12:
        raise ValueError("summary must be text of 12 words or fewer")
    checked = fact_check(raw, job_text)
    return checked

def extract_criteria(job_text):
    last_error = None
    for attempt in range(2):  # initial attempt + exactly one retry
        try:
            raw = demo_extract(job_text) if os.getenv("DEMO_MODE") == "1" else call_llm(job_text)
            return validate_reply(raw, job_text), None
        except Exception as exc:
            last_error = str(exc)
    fallback = {
        "branches": [], "min_cgpa": None, "max_backlogs": None,
        "batch": None, "summary": "Extraction failed; manual review required"
    }
    return fallback, f"Invalid extraction after one retry: {last_error}"

def student_qualifies(student, criteria):
    branches = criteria["branches"]
    if not branches or (branches != ["ALL"] and student["branch"] not in branches):
        return False
    if criteria["min_cgpa"] is None or float(student["cgpa"]) < float(criteria["min_cgpa"]):
        return False
    if criteria["max_backlogs"] is not None and int(student["backlogs"]) > criteria["max_backlogs"]:
        return False
    if criteria["batch"] is not None and int(student["batch"]) != criteria["batch"]:
        return False
    return True

def write_output_csv(filename, headers, rows):
    with (BASE_DIR / filename).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

def main():
    try:
        jobs = read_csv("jobs.csv", ["job_id", "company", "role", "job_post_text"])
        students = read_csv("students.csv", ["student_id", "name", "branch", "cgpa", "backlogs", "batch"])
        for s in students:
            if s["branch"] not in ALLOWED_BRANCHES:
                raise ValueError(f"Invalid branch for student {s['student_id']}")
            if not 0 <= float(s["cgpa"]) <= 10 or int(s["backlogs"]) < 0:
                raise ValueError(f"Invalid academic values for student {s['student_id']}")

        summary_rows, eligible_rows, review_rows = [], [], []
        matched_student_ids = set()
        for job in jobs:
            criteria, error = extract_criteria(job["job_post_text"])
            status = "matched" if criteria["branches"] and criteria["min_cgpa"] is not None else "needs_review"
            matches = []
            if status == "matched":
                matches = [s for s in students if student_qualifies(s, criteria)]
                matched_student_ids.update(s["student_id"] for s in matches)
            reason = error or ("Missing valid branch criteria" if not criteria["branches"] else
                               "No verified CGPA stated" if criteria["min_cgpa"] is None else "")
            summary_rows.append({
                "job_id": job["job_id"], "company": job["company"], "role": job["role"],
                "branches": "|".join(criteria["branches"]), "min_cgpa": criteria["min_cgpa"],
                "max_backlogs": criteria["max_backlogs"], "batch": criteria["batch"],
                "status": status, "eligible_count": len(matches)
            })
            for s in matches:
                eligible_rows.append({
                    "job_id": job["job_id"], "company": job["company"], "role": job["role"],
                    "student_id": s["student_id"], "name": s["name"], "branch": s["branch"],
                    "cgpa": s["cgpa"], "backlogs": s["backlogs"], "batch": s["batch"],
                    "approval_status": "PENDING_OFFICER_REVIEW"
                })
            if status == "needs_review":
                review_rows.append({
                    "job_id": job["job_id"], "company": job["company"], "role": job["role"],
                    "reason": reason or "Criteria require placement officer review"
                })

        write_output_csv("job_summary.csv",
            ["job_id","company","role","branches","min_cgpa","max_backlogs","batch","status","eligible_count"], summary_rows)
        write_output_csv("eligible.csv",
            ["job_id","company","role","student_id","name","branch","cgpa","backlogs","batch","approval_status"], eligible_rows)
        write_output_csv("review.csv", ["job_id","company","role","reason"], review_rows)

        not_yet = [s for s in students if s["student_id"] not in matched_student_ids]
        lines = ["PLACEMENT ELIGIBILITY SUMMARY", "All eligible lists are drafts pending officer approval.", ""]
        for row in summary_rows:
            lines.append(f'{row["job_id"]} | {row["company"]} | eligible: {row["eligible_count"]} | status: {row["status"]}')
        lines += ["", "STUDENTS NOT YET ELIGIBLE FOR ANY MATCHED JOB:"]
        lines += [f'{s["student_id"]} - {s["name"]}' for s in not_yet] or ["None"]
        (BASE_DIR / "summary.txt").write_text("\n".join(lines), encoding="utf-8")
        print("Project completed successfully.")
        print(f"Jobs processed: {len(jobs)} | Students processed: {len(students)}")
        print(f"Eligible student-job rows: {len(eligible_rows)} | Jobs needing review: {len(review_rows)}")
        print("Generated: job_summary.csv, eligible.csv, review.csv, summary.txt")
        print("IMPORTANT: A placement officer must review every list before it is shared.")
    except (RuntimeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
