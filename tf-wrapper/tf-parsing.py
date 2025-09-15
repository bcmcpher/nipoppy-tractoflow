import argparse
import os
import shutil
from pathlib import Path
import json
import subprocess
import tempfile
import re

import numpy as np
import nibabel as nib
from bids import BIDSLayout, BIDSLayoutIndexer

def parse_data(bids_dir, participant_id, session_id, outdir, use_bids_filter=True):
    """ Parse and verify the input files to build TractoFlow's simplified input.
    """

    # because why parse subject ID the same as bids ID?
    subj = participant_id.replace('sub-', '')

    # build paths to dataset
    bids_path = f"{bids_dir}/sub-{participant_id}/ses-{session_id}"
    anat_path = f"{bids_path}/anat"
    dwis_path = f"{bids_path}/dwi"

    # build a regex of anything not subject id
    srx = re.compile(f"sub-(?!{subj}.*$)")

    print('Building Single Subject BIDS Layout...')

    # build a BIDSLayoutIndexer to only pull subject ID
    bidx = BIDSLayoutIndexer(ignore=[srx])

    # parse bids directory with subject filter
    layout = BIDSLayout(bids_dir, indexer=bidx)

    # load the bids filter if it's called
    bidf = {}  # make it empty by default
    if use_bids_filter:

        # bad practive, but I don't have time...
        bidf_path = f"./bids_filter_ses-{session_id}.json"

        # if a filter exists
        if os.path.exists(bidf_path):
            print(' -- Expected bids_filter.json is found.')
            f = open(bidf_path)
            bidf = json.load(f)  # load the json as a dictionary
            f.close()

        else:
            print(' -- Expected bids_filter.json is not found.')

    else:
        print(' -- Not using a bids_filter.json')

    print("= "*25)

    # pull every t1w / dwi file name from BIDS layout
    if bidf:
        anat_files = layout.get(extension='.nii.gz', **bidf['t1w'])
        dmri_files = layout.get(extension='.nii.gz', **bidf['dwi'])
    else:
        anat_files = layout.get(suffix='T1w', session=session_id, extension='.nii.gz')
        dmri_files = layout.get(suffix='dwi', session=session_id, extension='.nii.gz')

    # preallocate candidate anatomical files
    canat = []

    #
    # anat parsing
    #

    print("Parsing Anatomical Files...")
    for idx, anat in enumerate(anat_files):

        # pull the data
        tmeta = anat.get_metadata()
        tvol = anat.get_image()

        # because PPMI doesn't have full sidecars

        try:
            tmcmode = tmeta['MatrixCoilMode']
        except:
            tmcmode = 'unknown'

        try:
            torient = tmeta['ImageOrientationText']
        except:
            torient = 'sag'

        try:
            tprotocol = tmeta['ProtocolName']
        except:
            tprotocol = 'unknown'

        # drop flair from getting picked up as anat
        if ("flair" in anat.filename.lower()):
            continue

        print("- "*25)
        print(anat.filename)
        print(f"Scan Type: {tmcmode}")
        print(f"Data Shape: {tvol.shape}")

        # if sense is in the encoded header drop it
        if tmcmode.lower() == 'sense':
            continue

        # look for Neuromelanin type scan in name somewhere
        if ('neuromel' in tprotocol.lower()):
            continue

        # append the data if it passes all the skips
        canat.append(anat)

    print("- "*25)

    # error if nothing passes
    if len(canat) == 0:
        raise ValueError(f'No valid T1 anat file for {participant_id} in ses-{session_id}.')

    # check how many candidates there are
    if len(canat) > 1:
        print('Still have to pick one...')
        npart = [len(x.get_entities()) for x in canat]
        oanat = canat[np.argmin(npart)]
    else:
        oanat = canat[0]

    # verify selection in log
    print(f"Selected anat file: {oanat.filename}")
    shutil.copyfile(Path(anat_path, oanat.filename), Path(outdir, "t1.nii.gz"))
    os.chmod(Path(outdir, "t1.nii.gz"), 0o644)  # set file permissions to +x

    print("= "*25)


    #
    # dmri parsing
    #


    # preallocate candidate dmri inputs
    cdmri = []
    cbv = np.empty(len(dmri_files))
    cnv = np.empty(len(dmri_files))
    cpe = []

    print("Parsing Diffusion Files...")
    for idx, dmri in enumerate(dmri_files):

        tmeta = dmri.get_metadata()
        tvol = dmri.get_image()

        # if no phase encoding present, assume borked
        try:
            tpedir = tmeta['PhaseEncodingDirection']
        except:
            tpedir = tmeta['PhaseEncodingAxis']

        if not tpedir:
            raise ValueError("INCOMPLETE SIDECAR: ['PhaseEncodingDirection'] or ['PhaseEncodingAxis'] is not defined in sidecar. This is required to accurately parse the dMRI data.")

        # print for log
        print("- "*25)
        print(dmri.filename)
        print(f"Encoding Direction: {tpedir}")
        print(f"Data Shape: {tvol.shape}")

        # store phase encoding data
        cpe.append(tpedir)

        # store image dimension
        if len(tvol.shape) == 4:
            cnv[idx] = tvol.shape[-1]
        elif len(tvol.shape) == 3:
            cnv[idx] = 1
        else:
            raise ValueError('dMRI File: {dmri.filename} is not 3D/4D.')

        # build paths to bvec / bval data
        tbvec = Path(bids_dir, "sub-" + participant_id, 'ses-' + session_id, 'dwi', dmri.filename.replace('.nii.gz', '.bvec')).joinpath()
        tbval = Path(bids_dir, "sub-" + participant_id, 'ses-' + session_id, 'dwi', dmri.filename.replace('.nii.gz', '.bval')).joinpath()

        # if bvec / bval data exist
        if os.path.exists(tbvec) & os.path.exists(tbval):
            print('BVEC / BVAL data exists for this file')
            cbv[idx] = 1
        else:
            print('BVEC / BVAL data does not exist for this file')
            cbv[idx] = 0

        # append to output (?)
        cdmri.append(dmri)

    print("- "*25)

    # get unique phase encodings
    ucpe = np.unique(cpe)
    print(f"Phase Encoding Directions are: {ucpe}")

    if ucpe.size == 0:
        raise ValueError("No diffusion files found. Nothing to process.")

    # sanity check - maybe redundant
    if len(ucpe) > 2:
        raise ValueError("More than 2 phase encoding axes found - nothing useful can be done without further filtering.")

    # set the phase encoding direction
    if ('i' in ucpe) | ('i-' in ucpe):
        phase = 'x'
    elif ('j' in ucpe) | ('j-' in ucpe):
        phase = 'y'
    else:
        print('An unlikely (z) or mixed phase encoding has been selected.')
        phase = 'z'

    print(f"Phase Encoding Argument: {phase}")

    # catch all the dmri files
    dmrifs = []

    # pull the full sequences - THIS ONLY GRABS DIRECTED FILES - MISSES B0s TO MERGE
    for idx, x in enumerate(cbv):
        if x == 1:
            print(f"File {idx+1}: {dmri_files[idx].filename}")
            dmrifs.append(dmri_files[idx])

    print(f"dmrifs: {dmrifs}")

    # if there are more than 2, merge by phase encoding directions
    if len(dmri_files) >= 2:

        print("Multiple files found: attempt to merge files by phase encoding direction.")
        print("= "*25)

        # move files into 2 pe lists
        pe1, pe2 = [], []
        for idx, x in enumerate(dmri_files):
            (pe1, pe2)[cpe[idx] in ucpe[0]].append(x)

        # for each file in pe1 list
        pe1dati = []
        pe1data = []
        pe1date = []
        for x in pe1:

            t1dwif = x.get_image()
            t1dwid = t1dwif.get_fdata()
            pe1affine = t1dwif.affine
            pe1readout = x.get_metadata()["TotalReadoutTime"]
            print(f" -- Image file: {x.filename}")
            print(f" -- Image shape: {t1dwid.shape[:3]}")
            print(" -- # of volumes / bvals / bvecs:")

            # load bval / bvec data
            try:
                t1bvals = np.loadtxt(Path(bids_dir, 'sub-' + participant_id, 'ses-' + session_id, 'dwi', x.filename.replace('.nii.gz', '.bval')).joinpath())
            except:
                t1bvals = np.zeros(t1dwif.shape[-1])

            try:
                t1bvecs = np.loadtxt(Path(bids_dir, 'sub-' + participant_id, 'ses-' + session_id, 'dwi', x.filename.replace('.nii.gz', '.bvec')).joinpath())
            except:
                t1bvecs = np.zeros((t1dwif.shape[-1], 3))
            print(f" -- {t1dwid.shape[-1]} / {t1bvals.shape[-1]} / {t1bvecs.shape[-1]}")
            print("- " * 25)

            # merge data
            pe1dati.append(t1dwid)
            pe1data.append(t1bvals)
            pe1date.append(t1bvecs)

            # check dims and merge: .nii.gz, bval, bvec
            try:
                pe1img = np.concatenate(pe1dati, axis=-1)
                pe1bva = np.concatenate(pe1data, axis=-1)
                pe1bve = np.concatenate(pe1date, axis=-1)
            except:
                pe1dati.pop()
                pe1data.pop()
                pe1date.pop()

            print(f"pe1img shape: {pe1img.shape}")

            # # deal w/ an rpe being non-existant
            # if not pe1img:
            #     pe1img = None  # np.zeros([116, 116, 72, 1])
            #     pe1bva = None  # np.zeros([1,0])
            #     pe1bve = None  # np.zeros([3,1])

        # print(f"PE1 {ucpe[0]} Merged Shapes: img: {pe1img.shape} / bval: {pe1bva.shape} / bvec: {pe1bve.shape}")
        print(f"PE1 {ucpe[0]} Merged Files")
        print("= " * 25)

        # for each file in pe2 list
        pe2dati = []
        pe2data = []
        pe2date = []
        for x in pe2:

            t2dwif = x.get_image()
            t2dwid = t2dwif.get_fdata()
            pe2affine = t2dwif.affine
            pe2readout = x.get_metadata()["TotalReadoutTime"]
            print(f" -- Image file: {x.filename}")
            print(f" -- Image shape: {t2dwid.shape[:3]}")
            print(" -- # of volumes / bvals / bvecs:")

            # load bval / bvec data | try and load, if not there can only assume 0s
            try:
                t2bvals = np.loadtxt(Path(bids_dir, 'sub-' + participant_id, 'ses-' + session_id, 'dwi', x.filename.replace('.nii.gz', '.bval')).joinpath())
            except:
                t2bvals = np.zeros(t2dwif.shape[-1])

            try:
                t2bvecs = np.loadtxt(Path(bids_dir, 'sub-' + participant_id, 'ses-' + session_id, 'dwi', x.filename.replace('.nii.gz', '.bvec')).joinpath())
            except:
                t2bvecs = np.zeros((t2dwif.shape[-1], 3))
            print(f" -- {t2dwid.shape[-1]} / {t2bvals.shape[-1]} / {t2bvecs.shape[-1]}")
            print("- " * 25)

            # merge data
            pe2dati.append(t2dwid)
            pe2data.append(t2bvals)
            pe2date.append(t2bvecs)

            # check dims and merge: .nii.gz, bval, bvec
            try:
                pe2img = np.concatenate(pe2dati, axis=-1)
                pe2bva = np.concatenate(pe2data, axis=-1)
                pe2bve = np.concatenate(pe2date, axis=-1)
            except:
                pe2dati.pop()
                pe2data.pop()
                pe2date.pop()
                
            print(f"pe2img shape: {pe2img.shape}")

            # deal w/ an rpe being non-existant
            # if not pe2img:
            #     pe2img = None  # np.zeros([116, 116, 72, 1])
            #     pe2bva = None  # np.zeros([1,0])
            #     pe2bve = None  # np.zeros([3,1])

        # print(f"PE2 {ucpe[1]} Merged Shapes: img: {pe2img.shape} / bval: {pe2bva.shape} / bvec: {pe2bve.shape}")
        print(f"PE2 {ucpe[0]} Merged Files")
        print("= " * 25)

        # deal with one or the other being empty
        # if isempty(pe1img) | isempty(pe2img)
        # # if either is empty, set outs w/ non revb0
        # # else create these files

        # deal w/ these possibly being empty
        try:
            xxx = pe1bve[:, pe1bva > 0].shape[1]
        except:
            xxx = 0

        try:
            yyy = pe2bve[:, pe2bva > 0].shape[1]
        except:
            yyy = 0

        # print(f"xxx: {xxx} | yyy: {yyy}")

        # determine what sequence will be the weighted / revb0
        if  xxx > yyy:
            # print(f" -- Selected PE1 ({ucpe[0]}) as FPE.")
            # print(f" -- -- RPE PE2 ({ucpe[1]}).")
            dwis_out = pe1img
            dwis_aff = pe1affine
            bval_out = pe1bva
            bvec_out = pe1bve
            mf_readout = pe1readout

            try:
                revb_out = np.mean(pe2img, axis=-1)
                revb_aff = pe2affine
            except:
                revb_out = None
                revb_aff = None

        else:
            #print(f" -- Selected PE2 ({ucpe[1]}) as FPE.")
            #print(f" -- -- RPE PE1 ({ucpe[0]}).")

            dwis_out = pe2img
            dwis_aff = pe2affine
            bval_out = pe2bva
            bvec_out = pe2bve
            mf_readout = pe2readout

            try:
                revb_out = np.mean(pe1img, axis=-1)
                revb_aff = pe1affine
            except:
                revb_out = None
                revb_aff = None

        # write the dwi / revb0 to disk
        print("Writing output files...")

        dwi_out = 'dwi.nii.gz'
        dwi_data = nib.nifti1.Nifti1Image(dwis_out, dwis_aff)
        nib.save(dwi_data, Path(outdir, dwi_out).joinpath())

        # write out the mergec bval / bvec files
        np.savetxt(Path(outdir, 'bval'), bval_out, fmt='%1.0f')
        np.savetxt(Path(outdir, 'bvec'), bvec_out, fmt='%1.6f')

        if np.any(revb_out):
            rpe_out = 'rev_b0.nii.gz'
            rpe_data = nib.nifti1.Nifti1Image(revb_out, revb_aff)
            nib.save(rpe_data, Path(outdir, rpe_out).joinpath())
        else:
            print(" -- RPE Image isn't really there - don't write it.")

    else:

        print("Just copy single dwi file to output folder.")
        shutil.copy(dmrifs[0], Path(outdir, 'dwi.nii.gz'))
        shutil.copy(Path(bids_dir, "sub-" + participant_id, 'ses-' + session_id, 'dwi', dmrifs[0].filename.replace('.nii.gz', '.bvec')).joinpath(), Path(outdir, "bvec"))
        shutil.copy(Path(bids_dir, "sub-" + participant_id, 'ses-' + session_id, 'dwi', dmrifs[0].filename.replace('.nii.gz', '.bval')).joinpath(), Path(outdir, "bval"))
        rpe_out = None

    # return the paths to the input files to copy
    # return(dmrifile, bvalfile, bvecfile, anatfile, rpe_file, phase, readout)
    return("Parsing complete.")


if __name__ == '__main__':
    # argparse
    HELPTEXT = """
    Script to run parse bids dMRI data into TractoFlow generic input
    """

    # parse inputs
    parser = argparse.ArgumentParser(description=HELPTEXT)
    parser.add_argument('--bids_dir', type=str, help='BIDS directory', required=True)
    parser.add_argument('--output_dir', type=str, default=None, help='specify custom output dir (if None --> <DATASET_ROOT>/derivatives)')
    parser.add_argument('--participant_id', type=str, help='participant id', required=True)
    parser.add_argument('--session_id', type=str, help='session id for the participant', required=True)
#    parser.add_argument('--use_bids_filter', action='store_true', help='use bids filter or not')
#    parser.add_argument('--dti_shells', type=str, default=None, help='shell value(s) on which a tensor will be fit', required=False)
#    parser.add_argument('--fodf_shells', type=str, default=None, help='shell value(s) on which the CSD will be fit', required=False)
#    parser.add_argument('--sh_order', type=str, default=None, help='The order of the CSD function to fit', required=False)

    # extract arguments
    args = parser.parse_args()
    bids_dir = args.bids_dir
    output_dir = args.output_dir # Needed on BIC (QPN) due to weird permissions issues with mkdir
    participant_id = args.participant_id
    session_id = args.session_id
#    dti_shells=args.dti_shells
#    fodf_shells=args.fodf_shells
#    sh_order=args.sh_order
#    use_bids_filter = args.use_bids_filter

    # test parsing
    parse_data(bids_dir, participant_id, session_id, output_dir, use_bids_filter=True)
    # dmrifile, bvalfile, bvecfile, anatfile, rpe_file, phase, readout = parse_data(bids_dir, participant_id, session_id, use_bids_filter)
