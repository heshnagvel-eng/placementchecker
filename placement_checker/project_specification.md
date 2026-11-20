# Project Specification: Placement Eligibility Checker

**Purpose:** Build a console-based Python application for a college placement cell. It reads job posts and student records from CSV files, extracts eligibility criteria from each post, validates those criteria, and creates draft eligibility reports.

**Inputs:** `jobs.csv` (minimum 8 posts) and `students.csv` (minimum 20 fictional student records).

**LLM output:** Exactly five JSON fields: `branches`, `min_cgpa`, `max_backlogs`, `batch`, and `summary`. Only facts explicitly stated in the job post may be extracted. A summary must contain no more than 12 words.

**Validation:** Validate keys, types and allowed values. Retry invalid output once. If it remains invalid, use a safe fallback and flag the post for review. Verify every branch against the text. Accept `ALL` only for “any branch” or “all branches”. Never convert percentage to CGPA.

**Job status:** `matched` only when at least one valid branch and a verified CGPA are available; otherwise `needs_review`.

**Eligibility:** A student must satisfy branch, minimum CGPA, maximum backlog (if stated) and batch (if stated).

**Outputs:** `job_summary.csv`, `eligible.csv`, `review.csv` and `summary.txt`.

**Privacy and human oversight:** Student records remain inside Python and are never sent to the LLM. All generated eligible lists are drafts and must be checked by the placement officer before sharing.

**Error handling:** Handle missing or malformed input files and invalid data safely. Use fictional sample student data only.
