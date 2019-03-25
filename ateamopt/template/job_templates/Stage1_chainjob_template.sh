#!/bin/bash

#SBATCH -p prod
#SBATCH -t 30:00
#SBATCH -n 1
#SBATCH -C cpu|nvme
#SBATCH -A proj36
#SBATCH -J launch_Stage_1


set -ex

source activate ateam_opt

JOBID_0=$(<Job_0.txt)
PARENT_DIR=$(<pwd.txt)
export STAGE_DIR=$PARENT_DIR/Stage1
export SCRIPT_REPO=$PARENT_DIR/Script_Repo

mkdir $STAGE_DIR
cp pwd.txt $STAGE_DIR/

STATUS_0=$(sacct -j ${JOBID_0} -o State| sed -n '3 p'| xargs) # get the status of the job
if [[ $STATUS_0 = "COMPLETED" ]]; then
    echo "Stage 0 finished successfully" > Stage0_status.txt
else
    echo "Stage 0 did NOT finish successfully" > Stage0_status.txt
fi
python analysis_stage0.py

echo "Saving the Optimized parameters for the next stage"
rm -rf preprocessed/
rm -rf .ipython/

# Launch the passive+Ih optimization (Stage 1)

cp -r cell_types/ $STAGE_DIR/
cp cell_id.txt $STAGE_DIR/
mv fit_opt.json $STAGE_DIR/cell_types/
if [ -d "peri_model" ]; then mv peri_model/ $STAGE_DIR/; fi
cp -r $PASS_IH_REPO/* $STAGE_DIR/
if [ -f qos.txt ]; then cp qos.txt $STAGE_DIR/ ; fi
cp $SCRIPT_REPO/prepare_stage1_run.py $STAGE_DIR/
cp -r $SCRIPT_REPO/modfiles/ $STAGE_DIR/


cd $STAGE_DIR

python prepare_stage1_run.py
nrnivmodl modfiles/
STAGE="_STAGE1"
STAGE_NEXT="_STAGE2"
CELL_ID=$(<cell_id.txt)
JOBNAME=$CELL_ID$STAGE
LAUNCH_JOBNAME=$CELL_ID$STAGE_NEXT
sed -i -e "s/Stage1/$JOBNAME/g" batch_job.sh
if [ -f qos.txt ]; then
    queue=$(<qos.txt)
    sed -i -e "s/regular/$queue/g" batch_job.sh # Specific to Cori
fi
sed -i -e "s/Stage_2/$LAUNCH_JOBNAME/g" chain_job.sh
echo "Launching Stage 1 Opimization"
RES_1=$(sbatch start_haswell.sh)  # sbatch command goes here
echo ${RES_1##* } > Job_1.txt

