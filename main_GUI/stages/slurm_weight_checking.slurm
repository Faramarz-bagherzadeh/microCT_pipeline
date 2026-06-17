#!/bin/bash -l
#SBATCH --partition=smp
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 128
#SBATCH --time=47:00:00
#SBATCH --job-name=WeightChecking
#SBATCH --output=logs/WeightChecking_log.%j.out

module load mesa
module load conda
source deactivate
conda activate faramarz-env

TIFF_DIR=""
WEIGHTS_FILE=""
OUTPUT_DIR=""
PROJECT_DIR="/albedo/work/projects/p_ICECTai/microCT_pipeline"

python -u "$PROJECT_DIR/3-weight_checking/estimate_weight.py" \
    --tiff_dir "$TIFF_DIR" \
    --weights_file "$WEIGHTS_FILE" \
    --output_dir "$OUTPUT_DIR"