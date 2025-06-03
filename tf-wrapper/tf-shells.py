import argparse
import os

import numpy as np


def checkData(bvalfile, bvecfile):

    # load the bval / bvec data
    bval = np.loadtxt(bvalfile)
    bvec = np.loadtxt(bvecfile)

    # pull the number of shells
    bunq = np.unique(bval)

    # convert to integer w/ , separated list
    sh_use = ' '.join([str(int(x)) for x in bunq])

    # logical index of b0 values
    b0idx = bval == 0

    # check that vectors are unique
    tvec = bvec[:, ~b0idx]
    tdir = np.unique(tvec, axis=0)

    # compute and print the maximum shell
    dlmax = int(np.floor((-3 + np.sqrt(1 + 8 * tdir.shape[1]) / 2.0)))
    if dlmax <= 6:
        sh_order = str(dlmax)
    else:
        sh_order = "8"

    print('-'*80)
    print(f'The largest supported lmax using the whole dMRI sequence is: {dlmax}')
    print(f' -- Fitting lmax: {sh_order}')

    # export necessary values as environment variables
    os.environ["TFBVAL"] = sh_use
    os.environ["TFORDR"] = sh_order

    # return the values
    return(sh_use, sh_order)


if __name__ == '__main__':
    # argparse
    HELPTEXT = """
    Script to run create environment variables to run Tractoflow
    """

    # parse inputs
    parser = argparse.ArgumentParser(description=HELPTEXT)
    parser.add_argument('--bval', type=str, help='bval data to evaluate', required=True)
    parser.add_argument('--bvec', type=str, help='bvec data to evaluate', required=True)
    parser.add_argument('--outs', type=str, help='output file to source environment values', required=True)

    # extract arguments
    args = parser.parse_args()
    bval = args.bval
    bvec = args.bvec
    out_file = args.outs

    # just run the fxn
    tfbval, tfshod = checkData(bval, bvec)

    # print vars from environment for sanity
    print(f"Shells   : {os.environ['TFBVAL']}")
    print(f"SH Order : {os.environ['TFORDR']}")
    print('-'*80)

    with open(out_file, 'a') as env_file:
        env_file.write(f'export TFBVAL="{tfbval}"\n')
        env_file.write(f'export TFSHOD="{tfshod}"\n')
        env_file.close()
