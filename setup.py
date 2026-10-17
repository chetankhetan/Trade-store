from setuptools import setup, find_packages

setup(
    name="trade_store",
    version="0.0.0",
    description="Trade store service",
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
)