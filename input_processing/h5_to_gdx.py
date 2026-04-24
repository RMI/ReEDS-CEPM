#%% Imports
import sys
import h5py
import gdxpds
import argparse
import datetime
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Literal
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
            if 'comment' in f[key].attrs:
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


def get_declaration(df):
    """
    For everything except primary sets, return the domain as "(dim1,dim2,...)"
    """
    if (len(df.columns) == 1) and (df.columns[0] == '*'):
        out = ''
    else:
        out = '(' + ','.join(df.columns) + ')'
    return out


def sort_primary_first(declarations:list):
    """Put primary sets before subsetes"""
    writelist = (
        [i for i in declarations if '(' not in i]
        + [i for i in declarations if '(' in i]
    )
    return writelist


def write_declaration(
    case:str|Path,
    declarations:list,
    gamstype:Literal['set','parameter'],
):
    """
    Write GAMS code to declare sets/parameters before loading them from a .gdx file
    """
    ## Get aliases so we can define them after the parent is defined
    aliases = pd.read_csv(
        Path(reeds.io.reeds_path, 'inputs', 'sets', '_aliases.csv'),
        header=0, index_col=0,
    ).squeeze()
    ## Need to write primary sets before subsets
    if gamstype == 'set':
        writelist = sort_primary_first(declarations)
    else:
        writelist = declarations
    fpath = Path(case, f'b_declare_{gamstype}s.gms')
    with open(fpath, 'w') as f:
        if len(writelist):
            for line in writelist:
                f.write(f'{gamstype} {line} ;\n')
                # if line in aliases:
                for alias in aliases.get([line], []):
                    f.write(f'alias({line},{alias}) ;\n')
    print(f'Wrote {fpath}')


def write_load(
    case:str|Path,
    declarations:list,
    gamstype:Literal['set','parameter'],
):
    """
    Write GAMS code to load sets/parameters from .gdx file
    """
    ## Need to write primary sets before subsets
    if gamstype == 'set':
        writelist = sort_primary_first(declarations)
    else:
        writelist = declarations
    fpath = Path(case, f'b_load_{gamstype}s.gms')
    with open(fpath, 'w') as f:
        for line in writelist:
            key = line.split('(')[0]
            f.write(f'$loadDCR {key} = {key}\n')
    print(f'Wrote {fpath}')


def main(case, overwrite=True, verbose=1):
    dictin, gamstypes, comments = read_inputs(case)
    gdxpath = Path(reeds.io.standardize_case(case), 'inputs_case', 'inputs_0.gdx')
    declare_sets = []
    declare_parameters = []
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
                    description=comments.get(key, None),
                )
                declare_sets.append(f'{key}{get_declaration(df)}')
            elif gamstypes[key] == 'parameter':
                gdxpds.gdx.append_parameter(
                    gdx_file=gdx,
                    param_name=key,
                    df=df,
                    description=comments.get(key, None),
                )
                declare_parameters.append(f'{key}{get_declaration(df)}')
            else:
                raise NotImplementedError(gamstypes[key])
        gdx.write(gdxpath)
        print(f'Wrote inputs.h5 to {gdxpath}')
    write_declaration(case, declare_sets, 'set')
    write_declaration(case, declare_parameters, 'parameter')
    write_load(case, declare_sets, 'set')
    write_load(case, declare_parameters, 'parameter')


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
    # case = Path(reeds.io.reeds_path, 'runs', 'v20260424_inputsM3_Pacific')

    #%% Set up logger
    log = reeds.log.makelog(
        scriptname=__file__,
        logpath=Path(case, 'gamslog.txt'),
    )

    #%% Run it
    main(case)

    #%% Record the runtime
    reeds.log.toc(tic=tic, year=0, process='input_processing/h5_to_gdx.py', path=case)
