#!/bin/bash -l
#SBATCH --account=glaz.glaz
#SBATCH --partition=gpu
#SBATCH --gpus=a100:1
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

INPUT_DIR="/albedo/work/projects/p_ICECTai/B51/B51_bag99_hxfb101ms_block_0.rek"
OUTPUT_DIR="/albedo/work/projects/p_ICECTai/denoised_B51/"

python -u denoising.py\
    --input_dir "$INPUT_DIR" \
    --output_dir "$OUTPUT_DIR"