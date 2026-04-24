#%% Imports
import sys
import h5py
import gdxpds
import argparse
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import reeds


#%% Functions
def read_inputs(case):
    ## Allow either a ReEDS case or a .h5 path to be provided
    if Path(case).suffix == '.h5':
        h5path = case
    else:
        h5path = Path(case, 'inputs_case', 'inputs.h5')
    dictin = {}
    gamstypes = {}
    comments = {}
    with h5py.File(h5path, 'r') as f:
        keys = list(f)
        for key in keys:
            gamstypes[key] = f[key].attrs['gamstype']
            comments[key] = f[key].attrs['comment']
            if isinstance(comments[key], np.float64):
                comments[key] = ''
            columns = [i.decode() for i in list(f[key]['columns'])]
            df = pd.DataFrame({col: f[key][col] for col in columns})
            for col in df:
                if df[col].dtype == 'O':
                    df[col] = df[col].str.decode('utf-8')
            dictin[key] = df
    return dictin, gamstypes, comments


def main(case, overwrite=True, verbose=1):
    dictin, gamstypes, comments = read_inputs(case)
    gdxpath = Path(reeds.io.standardize_case(case), 'inputs_case', 'inputs_0.gdx')
    if gdxpath.is_file():
        if overwrite:
            gdxpath.unlink()
        else:
            raise FileExistsError(gdxpath)
    with gdxpds.gdx.GdxFile() as gdx:
        for key, df in dictin.items():
            if gamstypes[key] == 'set':
                gdxpds.gdx.append_set(
                    gdx_file=gdx,
                    set_name=key,
                    df=df,
                    description=comments.get(key, ''),
                )
            elif gamstypes[key] == 'parameter':
                gdxpds.gdx.append_parameter(
                    gdx_file=gdx,
                    param_name=key,
                    df=df,
                    description=comments.get(key, ''),
                )
            else:
                raise NotImplementedError(gamstypes[key])
            # if verbose:
            #     print(f'{gdxpath.name}: added {key}')
        gdx.write(gdxpath)
        print(f'Wrote inputs.h5 to {gdxpath}')


#%% Procedure
if __name__ == '__main__':
    #%% Time the operation of this script
    tic = datetime.datetime.now()

    #%% Parse arguments
    parser = argparse.ArgumentParser(
        description='Convert a ReEDS-formatted .h5 file to .gdx',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('reeds_path', help='ReEDS directory')
    parser.add_argument('inputs_case', help='ReEDS/runs/{case}/inputs_case directory')

    args = parser.parse_args()
    case = reeds.io.standardize_case(Path(args.inputs_case))

    # #%% Inputs for testing
    # case = Path(reeds.io.reeds_path, 'runs', 'v20260422_inputsM0_Pacific')

    #%% Set up logger
    log = reeds.log.makelog(
        scriptname=__file__,
        logpath=Path(case, 'gamslog.txt'),
    )

    #%% Run it
    main(case)

    #%% Record the runtime
    reeds.log.toc(tic=tic, year=0, process='input_processing/h5_to_gdx.py', path=case)
