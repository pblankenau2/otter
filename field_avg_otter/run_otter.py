from datetime import datetime
import pandas as pd
from otter.water_balance import do_wb_interp
import h5py
import os
import argparse
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("input_fn")
parser.add_argument("out_fn")
args = parser.parse_args()
input_fn = args.input_fn
out_fn = args.out_fn

with pd.HDFStore(input_fn, mode="r") as in_data:
    with pd.HDFStore(out_fn, mode="a") as out_data:
        for fid in in_data.keys():
            f = in_data.get(fid)
            f.loc[f.et.isna(), "et"] = -9999
            #f.aws_u = np.minimum(f.aws_max, f.aws_u)
            if (f.aws_max < f.aws_u).sum() > 0:
                raise Exception(f"aws_u > aws_max field {fid}")

            if f.aws_u.isna().sum() > 0:
                import ipdb
                ipdb.set_trace()

            if (f.aws_u == 0).sum() > 0 or f.aws_u.isna().sum() > 0:
                print(f"skipping {fid}")
                continue

            def n(attr):
                return f[attr].to_numpy()
        
            try:
                dru, drl, perc, dperc, ro, etaw, peff, et\
                    = do_wb_interp(n("aws_max")[0], n("aws_u"), n("cn"), n("pr"),
                                   n("et"), n("eto"),
                                   init_dru_frac=1., init_drl_frac=1., mad_frac=1.0)
            except Exception as e:
                print(e)
                import ipdb
                ipdb.set_trace()
        
            f["dru"] = dru
            f["drl"] = drl
            f["perc"] = perc
            f["dperc"] = dperc
            f["ro"] = ro
            f["etaw"] = etaw
            f["peff"] = peff
            f["et_interp"] = et
        
            out_data.put(fid, f)
