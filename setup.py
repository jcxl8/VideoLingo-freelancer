from setuptools import find_packages, setup

NAME = 'VideoLingo-Freelancer'
VERSION = '3.0.0'

with open("requirements.txt", encoding="utf-8") as file:
    requirements = [
        line
        for raw_line in file
        if (line := raw_line.strip()) and not line.startswith('#')
    ]

setup(
    name=NAME,
    version=VERSION,
    packages=find_packages(),
    python_requires=">=3.12,<3.13",
    install_requires=requirements,
)
