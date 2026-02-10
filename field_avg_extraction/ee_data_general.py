from datetime import datetime, timedelta
import geopandas as gpd
import pandas as pd
from numpy import nan
import pickle
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product, chain
import sys
import gc
import json
import os
import tomllib
import argparse
from pathlib import Path

import ee

SCALE = 0.001
BASE_DIR = "projects/openet/assets"

# currently any getinfo call that fails > 5 times will cause failure 
def gi_safe(ee_obj, msg="", try_times=5):
    times = 0
    while times < try_times:
        try:
            obj = ee_obj.getInfo()
            return obj
        except:
            err = f"{msg} failed\n"
            print(err)
            with open(f"errors.txt", "a") as f:
                f.write(err)
            times += 1
            time.sleep(1)

    with open(f"errors.txt", "a") as f:
        err = f"{msg} FAILED\n"
        print(err)
        f.write(err)

    # kill the thread job?
    raise Exception("idk")

def get_data(cur_dt, ee_fields_path, fid_str):
    print(cur_dt)

    fields_ee = ee.FeatureCollection(ee_fields_path)
    num_fields = gi_safe(fields_ee.size(), msg=f"num_fields")
    if num_fields == 0:
        err = f"no fields"
        return
    else:
        #print(f"{h_id} num fields: {num_fields}")
        pass

    ens = ee.ImageCollection(f"{BASE_DIR}/ensemble/conus/gridmet/landsat/v2_1").filterBounds(fields_ee)
    eto = ee.ImageCollection(f"{BASE_DIR}/reference_et/conus/gridmet/daily/v1")
    gm = ee.ImageCollection("IDAHO_EPSCOR/GRIDMET")

    dts_str = cur_dt.strftime("%Y-%m-%d")
    dte_str = (cur_dt+timedelta(days=1)).strftime("%Y-%m-%d")

    eto_img = eto.filterDate(dts_str, dte_str)
    day = eto_img.first().select("eto")

    gm_img = gm.filterDate(dts_str, dte_str).first()
    day = day.addBands(gm_img.select("pr"))

    ens_imgs = ens.filterDate(dts_str, dte_str)

    # would be better to avoid this getinfo
    # but also tried adding null ens band and that was slower so ?
    num_ens = gi_safe(ens_imgs.size(), msg=f"num_ens")
    if num_ens > 0:
        day_ens = ens_imgs\
            .map(lambda x: x.select("et_ensemble_mad"))\
            .mosaic().multiply(SCALE)
        day = day.addBands(day_ens)
    
    vals = day.reduceRegions(fields_ee, ee.Reducer.mean(), 30)
    dfs = {}
    for i in range(0, num_fields, 5000):
        valsi = vals.toList(5000, i)
        valsi_loc = gi_safe(valsi, msg=f"get vals")
        for res in valsi_loc:
            p = res["properties"]
            et = p["et_ensemble_mad"] if "et_ensemble_mad" in p else nan 
            et = nan if et is None else et
            df = pd.DataFrame(data={"pr": p["pr"], "eto": p["eto"], "et": et},
                              index=[cur_dt])
            if p[fid_str] in dfs.keys():
                dfs[p[fid_str]] = pd.concat((dfs[p[fid_str]], df))
            else:
                dfs[p[fid_str]] = df

    #del vals
    #del valsi
    #del valsi_loc
    #gc.collect()

    return dfs
    
def do_get_data(year, out_dir, ee_fields_path, fid_str, out_fn="inputs"):
    dfs = {}
    jobs = []

    jobs = product(pd.date_range(f"{year}-1-1", f"{year}-12-31"), (ee_fields_path,), (fid_str,))

    with ThreadPoolExecutor(max_workers=10) as e:
        futures = [e.submit(get_data, *job) for job in jobs]

        for future in as_completed(futures):
            res = future.result()
            try:
                for fid in res.keys():
                    if fid in dfs.keys():
                        dfs[fid] = pd.concat((dfs[fid], res[fid]))
                    else:
                        dfs[fid] = res[fid]
            except:
                import ipdb
                ipdb.set_trace()

            # need to explicitly remove references for gc?
            futures.remove(future)

    print(f"writing {year}")
    with pd.HDFStore(f"{out_dir}/{out_fn}_{year}.h5", mode="a") as s:
        for fid in dfs:
            # hdf seems to require keys to be strings
            if type(fid) is int:
                # put an f in front because otherwise it gives a ton of warnings
                f_str = "f" + str(fid)
            else:
                f_str = fid

            s.put(f_str, dfs[fid].sort_index())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("extraction")
    args = parser.parse_args()
    extraction = args.extraction

    with open("ee_extract.toml", "rb") as f:
        config = tomllib.load(f)
    
    ee.Authenticate()
    ee.Initialize(project=config["ee"]["project"], opt_url="https://earthengine-highvolume.googleapis.com")

    extract = config[extraction]
    out_dir = extract["out_dir"]
    Path.mkdir(Path(f"./{out_dir}"), exist_ok=True)
    with open(f"{out_dir}/errors.txt", "a") as f:
        f.write(f"starting new extraction {datetime.now()}\n")

    dt_fmt = "%Y-%m-%d"
    start_dt = datetime.strptime(extract["start_dt"], dt_fmt)
    end_dt = datetime.strptime(extract["end_dt"], dt_fmt)

    for year in range(start_dt.year, end_dt.year+1):
        with open(f"{out_dir}/errors.txt", "a") as f:
            f.write(f"starting {year} {datetime.now()}\n")

        do_get_data(year, out_dir, extract["fields_ee_asset"], extract["field_identifier"])
