import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="wstools", # Replace with your own username
    version="0.0.1",
    author="Inductiveload",
    author_email="inductiveload@gmail.com",
    description="Simple tools for managing works at Wikisource",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/inductiveload/wstools",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)