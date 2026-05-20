from setuptools import find_packages, setup


setup(
    name="rpi-cc1101-transciever",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["cc1101==3.0.0", "spidev"],
)
