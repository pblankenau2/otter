# Instructions

1. Upload field boundaries to EE
2. Create/modify `ee_extract.toml`
3. Set the EE project ID under `[ee]`
4. Add a new "extraction" with the required entries
5. Run `ee_data_general.py [extraction]` to extract ET, ETo, and precip
6. Run `ee_soils_general.py [extraction]` to extract AWS, CN, and crops
6. Run `combine.py [extraction]` to combine years and soil data

Output is a single `inputs.h5` file with tabular time series data indexed by field ID.

# Todos

1. Handle partial years (currently just getting every day for every year)
2. Handle partitioning on attribute (e.g., HUC8) for larger extractions (see `../ee_data.py` for example)
3. Combine years by default (not a separate step)

# Nice to haves

1. Restart without overwrite for if extraction failed part way through
2. Less janky logging
3. Figure out why threadpool holds onto so much memory (would be able to do full extraction directly rather than by year)
