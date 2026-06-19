from setuptools import find_packages, setup

setup(
    name="school-route-planner",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.0.0",
        "openpyxl>=3.1.0",
        "numpy>=1.24.0",
        "ortools>=9.8.0",
        "requests>=2.31.0",
        "folium>=0.15.0",
    ],
    entry_points={
        "console_scripts": [
            "school-route-planner=run:main",
        ],
    },
)
