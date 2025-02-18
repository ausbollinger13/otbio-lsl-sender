# otbio_lsl_sender

A small Python application that is intended to read data from an OTBioelettronica Quattrocento device and then send that data to lab-streaming-layer.

## Installation (for developers)
To get set up for working on this repository, you should do the following:
1. Sync the repository to a location of your choosing
2. Navigate on your computer to the folder where you placed the repository
3. If you so desire, create a Python virtual environment.
4. Run the following command: `pip install --editable .`

If you don't plan on doing any development, you can just install the app by running the command: `pip install .`

## Building the documentation

To build the _documentation_, you must have __sphinx__ installed. To install __sphinx__, use the following command:

`pip install sphinx`

Once it has been installed, you can then build the documentation using the following command _from the repository's root folder_:

`sphinx-build -M html docs/source docs/build`

## Project structure

The structure of this library follows the following guide: https://github.com/yngvem/python-project-structure

