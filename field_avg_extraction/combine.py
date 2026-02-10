import pandas as pd
import argparse
import tomllib
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("extraction")
args = parser.parse_args()
extraction = args.extraction

with open("ee_extract.toml", "rb") as f:
    config = tomllib.load(f)
extract = config[extraction]
out_dir = extract["out_dir"]

dt_fmt = "%Y-%m-%d"
start_dt = datetime.strptime(extract["start_dt"], dt_fmt)
end_dt = datetime.strptime(extract["end_dt"], dt_fmt)

soils = pd.read_csv(f"{out_dir}/soils.csv")
dfs = {}
for yr in range(start_dt.year, end_dt.year+1):
    with pd.HDFStore(f"{out_dir}/inputs_{yr}.h5", mode="r") as in_data:
        for fid in in_data.keys():
            # drop leading /
            fid = fid[1:]
            fdf = in_data.get(fid)
            fdf["aws_max"] = soils.loc[soils.fid==fid, "aws_max"].iloc[0]
            fdf["aws_u"] = soils.loc[soils.fid==fid, f"aws_{yr}"].iloc[0]
            fdf["cn"] = soils.loc[soils.fid==fid, f"cn_{yr}"].iloc[0]
            fdf["crop"] = soils.loc[soils.fid==fid, f"crop_{yr}"].iloc[0]

            if fid in dfs:
                dfs[fid] = pd.concat((dfs[fid], fdf))
            else:
                dfs[fid] = fdf

with pd.HDFStore(f"{out_dir}/inputs.h5", mode="w") as out_data:
    for fid in dfs:
        out_data.put(fid, dfs[fid])
