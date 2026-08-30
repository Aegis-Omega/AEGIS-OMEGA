from setuptools import setup, find_packages

setup(
    name="aegis-omega",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["httpx>=0.27.0"],
    python_requires=">=3.10",
    description="AEGIS-Ω Agent Platform — 39 Mythos-level governed agents",
    long_description="Constitutional AI governance platform. 39 autonomous agents. Replay-certifiable.",
    author="Aegis Omega",
    url="https://aegisomega.com",
)
