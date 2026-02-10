import numpy as np
from numba import njit, prange

@njit
def etof_interp(et_ts, eto_ts, nodata=-9999., dtype='float32'):
    etof_ts = np.zeros_like(eto_ts, dtype=dtype)

    # fill leading empty values with first EToF
    first_et_ind = np.argmax(et_ts != nodata)
    first_et_val = et_ts[first_et_ind]
    first_etof = first_et_val / eto_ts[first_et_ind]
    etof_ts[:first_et_ind+1] = first_etof

    # handle zero eto values
    eto_ts[eto_ts==0] = eto_ts[eto_ts!=0].min()

    start_ind = first_et_ind
    for i in range(first_et_ind+1, et_ts.size):
        # find next non-missing et value
        if et_ts[i] != nodata:
            start_etof = et_ts[start_ind] / eto_ts[start_ind]
            end_etof = et_ts[i] / eto_ts[i]

            # linear interpolate from start to end
            etof_ts[start_ind:i+1] = np.linspace(start_etof,
                                                 end_etof,
                                                 i+1-start_ind)

            # set current index as start_ind
            start_ind = i
        # Reached missing value
        else:
            # end of et_ts
            if i == et_ts.size-1:
                etof_ts[start_ind:] = et_ts[start_ind] / eto_ts[start_ind]
            # not end of et_ts
            else:
                continue

    # return interpolated ET
    return etof_ts * eto_ts

# all args are arrays with length of ts
# aws and cn vals are just repeated until end of year
@njit
def do_wb_interp(aws_max: float, aws_u_ts: np.ndarray,
                 cn_ts: np.ndarray, pr_ts: np.ndarray,
                 et_ts: np.ndarray, eto_ts: np.ndarray,
                 nodata=-9999., init_dru_frac=1.,
                 init_drl_frac=1., mad_frac=1.):
    if init_dru_frac > mad_frac:
        raise Exception("init_dru_frac is larger than mad_frac (starting more depleted than allowed)")

    num_steps = et_ts.size

    # start empty
    last_dru = aws_u_ts[0]*init_dru_frac
    max_drl = aws_max - aws_u_ts[0]
    last_drl = max_drl*init_drl_frac
    last_aws_u = aws_u_ts[0]

    dru_ts = np.zeros(num_steps, dtype='float32')
    drl_ts = np.zeros(num_steps, dtype='float32')
    perc_ts = np.zeros(num_steps, dtype='float32')
    dperc_ts = np.zeros(num_steps, dtype='float32')
    ro_ts = np.zeros(num_steps, dtype='float32')
    etaw_ts = np.zeros(num_steps, dtype='float32')
    peff_ts = np.zeros(num_steps, dtype='float32')

    # not currently handling locations with no data
    # TODO something less dumb than this
    if sum(et_ts != nodata) == 0:
        return (dru_ts, drl_ts, perc_ts, dperc_ts, ro_ts,
                etaw_ts, peff_ts, et_ts)
    else:
        et_ts = etof_interp(et_ts, eto_ts, nodata=nodata)

    for i in range(num_steps):
        pr = pr_ts[i]
        et = et_ts[i]

        if aws_u_ts[i] != last_aws_u:
            total_dep = last_dru + last_drl
            last_dru = total_dep * aws_u_ts[i] / aws_max
            last_drl = total_dep * (aws_max - aws_u_ts[i]) / aws_max
            last_aws_u = aws_u_ts[i]

            if last_dru / last_aws_u > mad_frac:
                raise Exception("depletion exceed max allowable depletion after crop switch")

        S = (25400-254*cn_ts[i])/cn_ts[i]
        if pr > 0.2*S:
            ro = (pr-0.2*S)**2/(pr+0.8*S)
        else:
            ro = 0

        perc = max(pr - et - ro - last_dru, 0)
        dru = min(max(last_dru - pr + et + ro, 0),
                      mad_frac*aws_u_ts[i])

        dperc = max(perc - last_drl, 0)
        drl = min(max(last_drl - perc, 0),
                  aws_max - aws_u_ts[i])

        pr_eff = pr - dperc - ro
        dr_change = dru - last_dru
        etaw = et + perc - dperc - pr_eff - dr_change
        #if etaw < -1e-4:
        #    import ipdb
        #    ipdb.set_trace()

        last_dru = dru
        last_drl = drl

        dru_ts[i] = dru
        drl_ts[i] = drl
        perc_ts[i] = perc
        dperc_ts[i] = dperc
        ro_ts[i] = ro
        etaw_ts[i] = etaw
        peff_ts[i] = pr_eff

    return (dru_ts, drl_ts, perc_ts, dperc_ts, ro_ts, etaw_ts,
            peff_ts, et_ts)

@njit(parallel=True)
def chunk_inner(chunk_id, aws_max, aws_u, cn, pr, et, eto,
                nodata=-9999., init_dru_frac=1., init_drl_frac=1):
    print(f"allocating arrays chunk {chunk_id}")
    dru = np.ones(eto.shape, dtype='float32')*nodata
    drl = np.ones(eto.shape, dtype='float32')*nodata
    perc = np.ones(eto.shape, dtype='float32')*nodata
    dperc = np.ones(eto.shape, dtype='float32')*nodata
    etaw = np.ones(eto.shape, dtype='float32')*nodata
    ro = np.ones(eto.shape, dtype='float32')*nodata
    peff = np.ones(eto.shape, dtype='float32')*nodata
    et_int = np.ones(eto.shape, dtype='float32')*nodata

    print(f"running chunk {chunk_id}")
    for i in prange(eto.shape[0]):
        res = do_wb_interp(aws_max[i], aws_u[i, :], cn[i, :],
                           pr[i, :], et[i, :], eto[i, :],
                           nodata=nodata,
                           init_dru_frac=init_dru_frac,
                           init_drl_frac=init_drl_frac)
        (dru_ts, drl_ts, perc_ts, dperc_ts, ro_ts, etaw_ts,
        peff_ts, et_ts) = res

        dru[i] = dru_ts
        drl[i] = drl_ts
        perc[i] = perc_ts
        dperc[i] = dperc_ts
        etaw[i] = etaw_ts
        ro[i] = ro_ts
        peff[i] = peff_ts
        et_int[i] = et_ts

    return dru, drl, perc, dperc, etaw, ro, peff, et_int
