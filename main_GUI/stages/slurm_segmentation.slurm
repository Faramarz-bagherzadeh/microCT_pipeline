#!/bin/bash -l
#SBATCH --account=glaz.glaz
#SBATCH --partition=smp
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 128
#SBATCH --time=47:00:00
#SBATCH --job-name=SegmentKmean
#SBATCH --output=/albedo/work/projects/p_ICECTai/microCT_pipeline/logs/segmentation_log_%A_%a.out
#SBATCH --array=0-%MAX_JOBS%%50

module load mesa
module load conda
source deactivate
conda activate faramarz-env

FILES=(  )
INPUT_DIR="${FILES[$SLURM_ARRAY_TASK_ID]}"
OUTPUT_DIR=""
PROJECT_DIR="/albedo/work/projects/p_ICECTai/microCT_pipeline"

python -u "$PROJECT_DIR/2-segmentation/segmenter.py" \
    --input_dir "$INPUT_DIR" \
    --output_dir "$OUTPUT_DIR"