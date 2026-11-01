from pathlib import Path
import re

from setuptools import find_packages, setup


version_file = Path(__file__).parent / "cc1101_transceiver" / "_version.py"
match = re.fullmatch(r'__version__\s*=\s*["\']([^"\']+)["\']\s*\n?', version_file.read_text())
if not match:
    raise RuntimeError("invalid cc1101_transceiver/_version.py")

setup(
    name="rpi-cc1101-transciever",
    version=match.group(1),
    packages=find_packages(),
    python_requires=">=3.10",
)
