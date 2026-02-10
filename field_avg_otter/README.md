# Instructions

Run `run_otter.py [input_fn] [output_fn]` where `input_fn` is the path to an `inputs.h5` file
and `output_fn` is what the output file will be named.

Script assumes `otter` package is installed. If not, you can copy [water_balance.py](https://github.com/watrs-csumb/openet-water-balance/blob/main/src/otter/water_balance.py) into this directory and then remove `otter.` from the import statement (i.e., just import the function from water_balance.py rather than the package).

# Todo

Write functions that produce AWS and CN based on (a) provided crop type from e.g., shapefile,
and/or (b) extract mukey values (and number of instance of each key) from gNATSGO (uploaded to
EE). In the current implementation, extracting and averaging AWS and CN values can lead to small
changes year over year due to a small number of pixels being reclassified. (This shouldn't be case
using the OpenET crop type assets, but either the polygons don't line up exactly or some field boundaries
were not used to create the crop type maps.)
