#!/bin/bash -l

#SBATCH --partition=smp
#SBATCH --nodes=1
#SBATCH --tasks-per-node 1
#SBATCH --qos=48h
#SBATCH --cpus-per-task 128
#SBATCH --time=47:00:00
#SBATCH --job-name=Segmentation
#SBATCH --output=Segmentation_log%j.out

module load mesa
module load conda
source deactivate
conda activate env


python my_py.py