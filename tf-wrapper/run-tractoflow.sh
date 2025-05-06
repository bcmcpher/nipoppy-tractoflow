#!/bin/bash

SUBJ=$1
SESS=$2

BIDSDIR=$3
OUTSDIR=$4
WORKDIR=$5
TFINDIR=$6

TFENVFILE=${WORKDIR}/tf_sub-${SUBJ}_ses-${SESS}_env.txt

# add help message when no arguments are provided
if [ "$#" -lt 5 ]; then
	echo " -- Tractoflow Wrapper Script -- "
	echo " Usage: "
	echo "   $0 <subject_id> <session_id> <bids_dir> <work_dir> <tf_input_dir> "
	echo ""
	echo "  <subject_id>   - subject ID - for name in output path"
	echo "  <session_id>   - session ID - for name in output path"
	echo "  <bids_dir>     - BIDS dataset where subject_id / session_id are located"
	echo "  <output>       - path to Tractoflow output directory"
	echo "  <work_dir>     - path to Tractoflow working directory"
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
if [ ! -d ${TFINDIR} ]; then

	# create the input directory
	mkdir -p ${TFINDIR}

	# create simplified data layout from input
	python /opt/tf-wrapper/tf-parsing.py \
		   --bids_dir ${BIDSDIR} --output_dir ${TFINDIR} \
		   --participant_id ${SUBJ} --session_id ${SESS}

else

	echo " -- TF input directory already exists -- "

fi

# if the environment variables are not already determined
if [ -z ${TFINFILE} ]; then

	# create environment variables in a file
	python /opt/tf-wrapper/tf-shells.py \
		   --bval ${TFINDIR}/bval \
		   --bvec ${TFINDIR}/bvec \
		   --outs ${TFENVFILE}

else

		echo " -- Input data bvals / shells already determined -- "

fi

# get the environment variables from the file
source ${TFENVFILE}

# run nextflow
/usr/bin/nextflow /scilus_flows/tractoflow/main.nf \
		  --input ${TFINDIR} \
		  --output_dir ${OUTSDIR} \
		  -w ${WORKDIR} \
		  --dti_shells "${TFBVAL}" \
		  --fodf_shells "${TFBVAL}" \
		  --step 0.5 \
		  --mean_frf false \
		  --set_frf true \
		  --save_seeds false \
		  -profile fully_reproducible \
		  --processes 4 \
		  --processes_brain_extraction_t1 1 \
		  --processes_denoise_dwi 2 \
		  --processes_denoise_t1 2 \
		  --processes_eddy 1 \
		  --processes_fodf 2 \
		  --processes_registration 1 \
		  -resume

# add cleanup from previous pre-boutiques version...
