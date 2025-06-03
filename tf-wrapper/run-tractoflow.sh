#!/bin/bash

# parse inputs
SUBJ=$1
SESS=$2

BIDSDIR=$3
WORKDIR=$4
OUTSDIR=$5
TFINDIR=$6

# build paths to input files
TFRUNDIR=${TFINDIR}/sub-${SUBJ}_ses-${SESS}
INPUTDIR=${TFINDIR}/sub-${SUBJ}_ses-${SESS}/input
TFINRUN=${INPUTDIR}/${SUBJ}
TFENVFILE=${TFINDIR}/sub-${SUBJ}_ses-${SESS}_env.txt
TFWORKDIR=${WORKDIR}/sub-${SUBJ}_ses-${SESS}

# add help message when no arguments are provided
if [ "$#" -lt 6 ]; then
	echo " -- Tractoflow Wrapper Script -- "
	echo " Usage: "
	echo "   $0 <subject_id> <session_id> <bids_dir> <work_dir> <tf_input_dir> "
	echo ""
	echo "  <subject_id>   - subject ID - for name in output path"
	echo "  <session_id>   - session ID - for name in output path"
	echo "  <bids_dir>     - BIDS dataset where subject_id / session_id are located"
	echo "  <work_dir>     - path to Tractoflow working directory"
	echo "  <output>       - path to Tractoflow output directory"
	echo "  <tf_input_dir> - path to created Tractoflow input directory"
	echo ""
	exit 1
fi

#
# check if inputs exist
#

if [ -z $SUBJ ]; then
	echo " -- No subject ID provided -- "
	exit 1
fi

if [ -z $SESS ]; then
	echo " -- No session ID provided -- "
	exit 1
fi

if [ ! -d $BIDSDIR ]; then
	echo " -- BIDS directory does not exist -- "
	exit 1
fi

if [ ! -d $OUTSDIR ]; then
	echo " -- Output directory does not exist -- "
	exit 1
fi

if [ ! -d $WORKDIR ]; then
	echo " -- Working directory does not exist -- "
	exit 1
fi

# if the input directory is functionally empty
if [ ! -d ${TFINRUN} ]; then

	# create the input directory
	mkdir -p ${TFINRUN}

	# create simplified data layout from input
	python /opt/tf-wrapper/tf-parsing.py \
		   --bids_dir ${BIDSDIR} --output_dir ${TFINRUN} \
		   --participant_id ${SUBJ} --session_id ${SESS}

else

	echo " -- TF input directory already exists -- "

fi

# if the environment variables are not already determined
if [ -z ${TFENVFILE} ]; then

	# create environment variables in a file
	python /opt/tf-wrapper/tf-shells.py \
		   --bval ${TFINRUN}/bval \
		   --bvec ${TFINRUN}/bvec \
		   --outs ${TFENVFILE}  # this isn't getting made...?

else

		echo " -- Input data bvals / shells already determined -- "

fi

# deal with working directory being present or not
if [ -d ${TFWORKDIR} ]; then
	echo " -- Working directory already exists. Process should resume."
else
	mkdir -p ${TFWORKDIR}
fi

# get the environment variables from the file
source ${TFENVFILE}

# change into input directory to manage nextflow logs
cd ${TFRUNDIR}

echo ${TFBVAL}

# run nextflow
{  # try
/usr/bin/nextflow /scilus_flows/tractoflow/main.nf \
		  --input ${INPUTDIR} \
		  --output_dir ${OUTSDIR} \
		  -w ${TFWORKDIR} \
		  --run-gibbs-correction true \
		  --dti_shells "${TFBVAL}" \
		  --fodf_shells "${TFBVAL}" \
		  --set_frf true \
		  --mean_frf false \
		  --step 0.5 \
		  --save_seeds false \
		  -profile fully_reproducible \
		  --processes 4 \
		  -resume
} || {  # catch
	echo "Nextflow run failed."
	exit 1
}

# find and convert all symlinks to absolute paths
if [ -f ${OUTSDIR}/${SUBJ}/PTF_Tracking/sub-${SUBJ}__pft_tracking_prob_wm_seed_0.trk ]; then
	find ${OUTSDIR}/${SUBJ} -type l -execdir bash -c 'cp --remove-destination "$(readlink "${0}")" "${0}"' {} \;
fi

# # remove working directories if key output exists
# if [ -f ${RESULTS}/${SUBJ}/DTI_Metrics/sub-${SUBJ}__tensor.nii.gz ]; then
#	rm -rf ${TFWORKDIR}
#	rm -rf ${TFRUNDIR}  # ?
# fi
