import time
import argparse
import tomllib
from datetime import datetime, timedelta

import pandas as pd
import ee

from otter.soils import pt_soil_func

pt_soil = pt_soil_func()

# currently any getinfo call that fails > 5 times will cause failure 
def gi_safe(ee_obj, msg="", try_times=5):
    times = 0
    while times < try_times:
        try:
            obj = ee_obj.getInfo()
            return obj
        except Exception as e:
            err = f"{msg} failed\n"
            print(err)
            print(e)
            with open(f"{out_dir}/errors.txt", "a") as f:
                f.write(err)
                f.write(str(e))
            times += 1
            time.sleep(1)

    with open(f"{out_dir}/errors.txt", "a") as f:
        err = f"{msg} FAILED\n"
        print(err)
        f.write(err)

    # kill the thread job?
    raise Exception("idk")

def soil_from_hist(hist, crop, get_max=False):
    # running fractional aws, cn
    aws_f = 0
    cn_f = 0
    total = 0

    if get_max:
        aws_max_f = 0

    for mukey in hist.keys():
        frac = hist[mukey]

        if get_max:
            aws, aws_max, cn = pt_soil(crop, int(mukey), make_max=True)
            aws_max_f += frac*aws_max
        else:
            aws, cn = pt_soil(crop, int(mukey))

        aws_f += frac*aws
        cn_f += frac*cn
        total += frac

    # return aws, cn weighted by fraction of field
    if get_max:
        return aws_f/total, aws_max_f/total, cn_f/total

    return aws_f/total, cn_f/total

def get_data(ee_fields_path, fid_str, start_yr, end_yr, get_max=False):
    yrs = range(start_yr, end_yr+1)
    fields_ee = ee.FeatureCollection(ee_fields_path)
    num_fields = gi_safe(fields_ee.size(), msg=f"num_fields")
    if num_fields == 0:
        err = f"no fields"
        print(err)
        return
    else:
        #print(f"{h_id} num fields: {num_fields}")
        pass

    gnatsgo = ee.Image("projects/otter-460723/assets/gNATSGO_mukey_202502")
    mukeys = gnatsgo.reduceRegions(
        fields_ee,
        ee.Reducer.frequencyHistogram(),
        30
    )

    crops = ee.ImageCollection("projects/openet/assets/crop_type/v2024a").filterBounds(fields_ee)
    crops_comb = ee.Image()
    for year in yrs:
        crops_yr = crops.filter(ee.Filter.stringContains("system:index", str(year))).mosaic().rename([f"crop_{year}"])
        #soils = soils.addBands(crops_yr.select(f"crop_{year}"))
        crops_comb = crops_comb.addBands(crops_yr)

    vals_crop = crops_comb.reduceRegions(
        fields_ee,
        ee.Reducer.mode(),
        30
    )

    df = pd.DataFrame(columns=[f"crop_{yr}" for yr in yrs])
    floats = 0
    for i in range(0, num_fields, 5000):
        valsi = mukeys.toList(5000, i)
        valsi_loc = gi_safe(valsi, msg=f"get mukeys", try_times=1)

        valsi_crop = vals_crop.toList(5000, i)
        valsi_loc_crop = gi_safe(valsi_crop, msg=f"get vals", try_times=1)
        for res in valsi_loc:
            p = res["properties"]
            pp = [x["properties"] for x in valsi_loc_crop if x["properties"][fid_str]==p[fid_str]][0]

            crop = pp[f"crop_{start_yr}"]
            if type(crop) is float:
                crop = int(round(crop))
                floats += 1


            if get_max:
                aws, aws_max, cn = soil_from_hist(p["histogram"], crop, get_max=True)
                d1 = {"aws_max": aws_max for yr in yrs}
            else:
                aws, cn = soil_from_hist(p["histogram"], crop)

            d2 = {f"aws_{yr}": aws for yr in yrs}
            d3 = {f"cn_{yr}": cn for yr in yrs}
            d4 = {f"crop_{yr}": crop for yr in yrs}

            # hdf seems to require keys to be strings
            fid = p[fid_str]
            if fid == 1146:
                import ipdb
                ipdb.set_trace()

            if type(fid) is int:
                # put an f in front because otherwise it gives a ton of warnings
                fid = "f" + str(fid)

            if get_max:
                row = pd.DataFrame(data= d1 | d2 | d3 | d4, index=[fid])
            else:
                row = pd.DataFrame(data= d2 | d3 | d4, index=[fid])
            df = pd.concat((df, row))

    print(yrs[0], floats)
    return df
    
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

    dt_fmt = "%Y-%m-%d"
    start_dt = datetime.strptime(extract["start_dt"], dt_fmt)
    end_dt = datetime.strptime(extract["end_dt"], dt_fmt)

    get_max = True
    for year in range(start_dt.year, end_dt.year+1):
        df = get_data(extract["fields_ee_asset"], extract["field_identifier"], year, year, get_max=get_max)
        #df.reset_index().rename(columns={"index": "fid"}).to_csv(f"{out_dir}/soils_{year}.csv", index=False)
        df = df.reset_index().rename(columns={"index": "fid"})

        if get_max:
            running = df 
        else:
            running = pd.read_csv(f"{out_dir}/soils.csv")
            running = running.merge(df, on="fid")

        running.to_csv(f"{out_dir}/soils.csv", index=False)

        get_max = False
