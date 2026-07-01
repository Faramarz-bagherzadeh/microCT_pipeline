#!/bin/bash -l
#SBATCH --account=glaz.glaz
#SBATCH --partition=smp
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 128
#SBATCH --time=47:00:00
#SBATCH --job-name=merging
#SBATCH --output=logs/merging_log.%j.out

module load mesa
module load conda

conda activate faramarz-env

# IMPORTANT: force conda runtime libraries first
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH

JSONS_DIR=""

PROJECT_DIR="/albedo/work/projects/p_ICECTai/microCT_pipeline"

python -u "$PROJECT_DIR/6-merging_data/json_merger.py" \
    --jsons_dir "$JSONS_DIR"
