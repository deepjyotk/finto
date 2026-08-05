from collections import defaultdict

def group_failure_codes_by_module(logs: list[dict]) -> dict:
    failures_by_module = defaultdict(list)

    for log in logs:
        if log.get("status") == "failed":
            module = log.get("module")
            error_code = log.get("error_code")

            failures_by_module[module].append(error_code)

    return dict(failures_by_module)


logs = [
    {"module": "perception", "error_code": "CAMERA_FAILURE", "status": "failed"},
    {"module": "planning", "error_code": "PATH_NOT_FOUND", "status": "failed"},
    {"module": "perception", "error_code": "LOW_CONFIDENCE", "status": "failed"},
    {"module": "control", "error_code": None, "status": "passed"},
]

print(group_failure_codes_by_module(logs))