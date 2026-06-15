#!/bin/bash -l
#SBATCH --account=glaz.glaz
#SBATCH --partition=gpu
#SBATCH --gpus=a100:4
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 128
#SBATCH --time=47:00:00
#SBATCH --job-name=Denoising
#SBATCH --output=logs\Denoising_log.%j.out


module load mesa
module load conda
source deactivate
conda activate faramarz-env

INPUT_DIR=""
OUTPUT_DIR=""
PROJECT_DIR="/albedo/work/projects/p_ICECTai/microCT_pipeline"

python -u "$PROJECT_DIR/1-denoising/DL_denoiser.py" \
    --input_dir "$INPUT_DIR" \
    --output_dir "$OUTPUT_DIR"