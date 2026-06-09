#!/bin/bash -l

#SBATCH --partition=gpu
#SBATCH --gpus=a100:1
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 128
#SBATCH --time=47:00:00
#SBATCH --job-name=Denoising
#SBATCH --output=Denoising_log.%j.out


module load mesa
module load conda
source deactivate
conda activate my_env

python my_py