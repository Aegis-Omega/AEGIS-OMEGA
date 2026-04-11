from setuptools import setup, find_packages

setup(
    name             = "hallucination-delta",
    version          = "1.0.0",
    description      = "Portable metacognition measurement for any LLM — HD = |claimed - actual|",
    long_description = open("../README.md", encoding="utf-8").read(),
    long_description_content_type = "text/markdown",
    author           = "Tarik Skalic",
    author_email     = "tarikskalic33@gmail.com",
    url              = "https://github.com/tarikskalic33/myapp",
    packages         = find_packages(),
    python_requires  = ">=3.10",
    install_requires = [],         # zero hard dependencies
    extras_require   = {
        "full": [
            "numpy>=1.26.0",       # calibration curves
            "httpx>=0.27.0",       # live server connection
        ]
    },
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords = "llm metacognition hallucination calibration agi benchmark",
)
