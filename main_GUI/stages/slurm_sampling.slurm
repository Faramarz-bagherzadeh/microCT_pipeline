#!/bin/bash -l
#SBATCH --account=glaz.glaz
#SBATCH --partition=smp
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 128
#SBATCH --time=47:00:00
#SBATCH --job-name=Sampling
#SBATCH --output=/albedo/work/projects/p_ICECTai/microCT_pipeline/logs/sampling_log_%A_%a.out
#SBATCH --array=0-%MAX_JOBS%%50

module load mesa
module load conda
conda activate faramarz-env
# IMPORTANT: force conda runtime libraries first
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH

FILES=(  )
TIFF_FILE="${FILES[$SLURM_ARRAY_TASK_ID]}"
WEIGHTS_FILE=""
OUTPUT_DIR=""
SAMPLE_SIZE=""
OVERLAP_SIZE=""
PROJECT_DIR="/albedo/work/projects/p_ICECTai/microCT_pipeline"

python -u "$PROJECT_DIR/4-sampling/sample_maker.py" \
    --tiff_file "$TIFF_FILE" \
    --weights_file "$WEIGHTS_FILE" \
    --output_dir "$OUTPUT_DIR"\
    --sample_size "$SAMPLE_SIZE"\
    --overlap_size "$OVERLAP_SIZE"