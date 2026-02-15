from setuptools import setup, find_packages

setup(
    name="push2reaper",
    version="0.1.0",
    description="Push 2 hardware controller for Reaper DAW on Linux",
    author="mseibert",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "push2-python",
        "python-osc>=1.8.0",
        "python-rtmidi>=1.5.0",
        "Pillow>=10.0.0",
        "PyYAML>=6.0",
        "python-dotenv>=1.0.0",
        "numpy",
    ],
    entry_points={
        "console_scripts": [
            "push2reaper=main:main",
        ],
    },
)
