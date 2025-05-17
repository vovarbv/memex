from setuptools import setup, find_packages

# Read requirements files
with open('requirements.txt') as f:
    core_requirements = [line for line in f.read().splitlines() 
                        if line and not line.startswith('#') and not line.startswith('-r')]

with open('requirements-agents.txt') as f:
    agents_requirements = [line for line in f.read().splitlines() 
                          if line and not line.startswith('#') and not line.startswith('-r')]

setup(
    name="cursor-memory",
    version="0.1.0",
    description="Task management and context memory for Cursor AI",
    author="Cursor Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=core_requirements,
    extras_require={
        "agents": agents_requirements,
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
) 