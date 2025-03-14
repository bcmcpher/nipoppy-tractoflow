#!/bin/bash

SUBJ=$1
SESS=$2

BIDSDIR=$3
WORKDIR=$4
TFINDIR=$5

TFENVFILE=${WORKDIR}/tf_sub-${SUBJ}_ses-${SESS}_env.txt

# if the input directory is empty
if [ -z "$( ls -A ${TFINDIR} )" ]; then

	# create simplified data layout from input
	python /opt/tf-wrapper/bin/tf-parsing.py \
		   --bids_dir $BIDSDIR --output_dir ${TFINDIR} \
		   --participant_id $SUBJ --session_id $SESS

else

	echo " -- TF input already exists -- "

fi

# if the environment variables are not already determined
if [ -z ${TFINFILE} ]; then

	# create environment variables in a file, because TF is that stupid
	python /opt/tf-wrapper/bin/tf-shells.py \
		   --bval /input/sub-${SUBJ}/bval \
		   --bvec /input/sub-${SUBJ}/bvec \
		   --outs $TFENVFILE

else

		echo " -- Input data bvals / shells already determined -- "

fi

# get the environment variables from the file
source $TFENVFILE

# just run the goddamn thing
/usr/bin/nextflow /scilus_flows/tractoflow/main.nf \
		  --input ${TFINDIR} \
		  --output_dir /tractoflow_results \
		  -w ${WORKDIR} \
		  --dti_shells "$TFBVAL" \
		  --fodf_shells "$TFBVAL" \
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
