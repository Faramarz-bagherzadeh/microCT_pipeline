#!/bin/bash -l
#SBATCH --account=glaz.glaz
#SBATCH --partition=smp
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 16
#SBATCH --time=47:00:00
#SBATCH --job-name=feature_extraction
#SBATCH --output=logs/feature_extraction_log_%A_%a.out
#SBATCH --array=0-%MAX_JOBS%

module load mesa
module load conda
conda activate faramarz-env

# IMPORTANT: force conda runtime libraries first
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$LD_LIBRARY_PATH

OUTPUT_DIR=""
Resolution=""
PROJECT_DIR="/albedo/work/projects/p_ICECTai/microCT_pipeline"
TIFF_LIST=""

# Read the tif file path corresponding to this array task ID
TIFF_FILE=$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" "$TIFF_LIST")

echo "Array task ID: $SLURM_ARRAY_TASK_ID"
echo "Processing file: $TIFF_FILE"
echo "Output directory: $OUTPUT_DIR"
echo "Resolution: $Resolution"

python -u "$PROJECT_DIR/5-microCT_feature_extraction/main_feature_extractor.py" \
    --tiff_file "$TIFF_FILE" \
    --output_dir "$OUTPUT_DIR" \
    --resolution "$Resolution"