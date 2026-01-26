# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "eida-consistency>=0.3.7",
# ]
# ///

from eida_consistency.runner import run_consistency_check

# Run check for a specific node and get the report path
report_path = run_consistency_check(
    node="RESIF",
    epochs="5%",
)
print(f"Report generated at: {report_path}")
