"""Check the GitLab CI files like GitLab does for scripts: every script line must be a string."""
import glob
import sys

import yaml

bad = 0
jobs = {}
for f in [".gitlab-ci.yml", *sorted(glob.glob(".gitlab/ci/*.yml"))]:
    for name, job in yaml.safe_load(open(f)).items():
        if not isinstance(job, dict):
            continue
        jobs[name] = job
        for key in ("script", "before_script", "after_script"):
            for i, line in enumerate(job.get(key, [])):
                if not isinstance(line, str):
                    print(f"{f}: {name}.{key}[{i}] is a {type(line).__name__}: {line!r}")
                    bad += 1
for name, job in jobs.items():
    for need in job.get("needs", []):
        assert need["job"] in jobs, (name, need)
    if "extends" in job:
        assert job["extends"] in jobs, (name, job["extends"])
print("errors:", bad)
sys.exit(1 if bad else 0)
