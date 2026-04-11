"""
sovereign_hd — pip-installable package setup
"""
from setuptools import setup, find_packages

setup(
    name             = "sovereign-hd",
    version          = "1.0.0",
    description      = "Hallucination Delta Middleware — mathematically grounded HD scoring for any LLM output",
    long_description = open("README.md", encoding="utf-8").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type = "text/markdown",
    author           = "Tarik Skalic",
    author_email     = "tarikskalic33@gmail.com",
    url              = "https://github.com/tarikskalic/sovereign-agi-os",
    packages         = find_packages(),
    python_requires  = ">=3.10",
    install_requires = ["numpy>=1.24"],
    extras_require   = {
        "full": ["streamlit", "plotly"],
    },
    classifiers      = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords = (
        "hallucination detection llm quality metacognition "
        "biophotonic resonance knowledge-graph"
    ),
    entry_points = {
        "console_scripts": [
            "sovereign-hd = sovereign_hd.__main__:main",
        ]
    },
)
