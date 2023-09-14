# EcosizerEngine

### Requirements:

This software requires a python version greater than or equal to 3.11 to be installed in the environment it is running in.

### Using the package in scripts:

1. Install the package with pip

	$ pip install ecoengine

2. To import and use the tools in this package, add the following import statement to your script:

	from ecoengine import *

You should now be able to use the features of EcosizerEngine in your script

### Running locally in a container:
First, clone the EcosizerEngine repo from github

    $ git clone https://github.com/EcotopeResearch/EcosizerEngine.git

Depending on what type of environment you want to run the code in, please follow the appropriate steps.

Steps for installing in a virtual environment:
1. Navigate to the EcosizerEngine directory. This should be the same directory level as src/, setup.py, and this README document.
2. Run the following command:

	$ pip install -e .

This will install the ecosizer-engine package locally in editable format, such that changes you make in the source code here will be reflected in implementation.
This pip install should also install all dependencies for ecosizer-engine (i.e. numpy, scipy, pytest, and plotly)

Steps for installing using docker container:
1. Navigate to the EcosizerEngine directory.
2. Build container with docker file

	$ docker build -t ecosizerengine:latest .

3. Run docker container

	$  docker run -it ecosizerengine bash

4. When you are done messing about in the docker image, just type the command

	$ exit

or press ctrl+c then ctrl+d

Steps for installing conda environment from the Anaconda prompt:
1. Navigate to the EcosizerEngine directory.
2. Create new environment from .yml file.


	$ conda env create --file EcosizerEngine.yml

If the environment creation doesn't work, make sure Anaconda is up-to-date with

    $ conda update --all

If that doesn't work, you may need to force Anaconda to download and use python 3.11 (it defaults to 3.9) by making another environment

    $ conda create -n py311 python=3.11
    $ conda activate py311
    $ conda env create --file EcosizerEngine.yml

3. Check that the environment was created


	$ conda env list

4. Activate the new environment


	$ conda activate EcosizerEngine

If an environment already exits it can be removed with:

	$ conda remove --name EcosizerEngine --all


All the available environment can be found with:

	$ conda env list

### Testing:
From the parent directory, type

	$ python -m pytest

This will run all unit tests for the package

### Updating Documentation:
1. If not installed in environment: pip install sphinx and numpydoc
2. navigate to docs directory and run:


	$ make html

### Updating version on pypi

1. If you haven't installed them before, pip install build and twine

	$ python -m pip install --upgrade build


	$ python -m pip install --user --upgrade twine

2. Update the version number in setup.cfg
3. Run the following commands from the project root directory:

	$ python -m build

	$ python -m twine upload dist/*

### Contact Information
To get in touch with Ecotope Inc. go here: http://ecotope.com/contact/