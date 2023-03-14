# Ecolator 	

### Installing:
Steps for installing conda environment from the Anaconda prompt
1. Navigate to the Ecolator directory.
2. Create new environment from .yml file.


	$ conda env create --file Ecolator.yml

If the environment creation doesn't work, make sure Anaconda is up-to-date with

    $ conda update --all

If that doesn't work, you may need to force Anaconda to download and use python 3.11 (it defaults to 3.9) by making another environment

    $ conda create -n py311 python=3.11
    $ conda activate py311
    $ conda env create --file Ecolator.yml

3. Check that the environment was created


	$ conda env list

4. Activate the new environment


	$ conda activate Ecolator

If an environment already exits it can be removed with:

	$ conda remove --name Ecolator --all


All the available environment can be found with:

	$ conda env list

### Testing:
I haven't set up unit testing yet >.<
<!-- From the parent directory in Anaconda prompt and type

	$ python -m pytest -->

### Updating Documentation:
1. If not installed in environment: pip install sphinx and numpydocs
2. Using Anaconda prompt navigate to docs directory and run:


	$ make html

### Contact Information
To get in touch with Ecotope Inc. go here: http://ecotope.com/contact/