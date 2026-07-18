"""Setup script for ib_paper."""

from setuptools import find_packages, setup

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="ib_paper",
    version="0.1.0",
    description="Interactive Brokers Paper Trading CLI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Ricky",
    url="https://github.com/riggy420/ne-library",
    packages=["ib_paper"],
    package_dir={"ib_paper": "."},
    install_requires=[
        "ib_insync>=0.9.86",
        "click>=8.0",
        "flask>=3.0",
        "flask-socketio>=5.0",
        "eventlet>=0.30",
    ],
    entry_points={
        "console_scripts": [
            "ibpaper=ib_paper.cli:main",
            "ibpaper-server=ib_paper.server:main",
        ],
    },
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
)
