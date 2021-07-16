import pathlib
from setuptools import setup, find_packages


__dir__ = pathlib.Path(__file__).resolve().parent


def get_file(file: pathlib.Path) -> str:
    """Extract all lines from a file."""
    with open(file, "r") as f:
        return f.read()


setup(
    name="sepaq_crawler",
    author="Antoine Prouvost",
    description="Utility to crawl the SEPAQ API.",
    long_description=get_file(__dir__ / "README.md"),
    license="MIT",
    url="https://github.com/AntoinePrv/Sepaq-Crawler",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=["requests", "click", "geopy", "notify-py"],
)
