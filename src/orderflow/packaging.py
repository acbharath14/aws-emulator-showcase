"""Build the Lambda deployment zip from processor.py.

The zip contains one file, lambda_function.py, whose content is this
package's processor module. Tests exercise the same code the function runs,
not a copy.
"""

import io
import zipfile
from pathlib import Path

PROCESSOR_PATH = Path(__file__).with_name("processor.py")


def build_lambda_zip():
    """Return the deployment package bytes for the order processor."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(PROCESSOR_PATH, "lambda_function.py")
    buf.seek(0)
    return buf.read()
