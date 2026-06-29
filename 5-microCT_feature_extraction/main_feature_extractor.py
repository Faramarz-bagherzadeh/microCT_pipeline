"""
Main Feature Extractor for microCT binary images.

This script reads binary .tif files from an input directory, extracts
microstructural parameters using functions from params_basic.py and
params_transport.py, and saves the results as a JSON file per image.

Usage:
    python main_feature_extractor.py --input_dir <path_to_tifs> --resolution <voxel_size_m>
    python main_feature_extractor.py --input_dir ./data --resolution 1e-5 --pixel_density 0.917
    python main_feature_extractor.py --input_dir ./data --resolution 1e-5 --output_dir ./results
"""

import os
import sys
import json
import argparse
import glob
import numpy as np
from datetime import datetime
import tifffile


# Import feature extraction modules
from params_basic import (
    por_den_vol,
    euler_characteristic,
    specific_surface_area,
    mean_intercept_length,
    classify_pores,
)
from params_transport import (
    spherical_ice_cluster,
    skeleton_metrics,
    calculate_permeability,
    calculate_tortuosity,
)


def load_binary_tif(filepath):
    """
    Load a binary .tif file and return as a numpy boolean array.

    Parameters:
        filepath (str): Path to the .tif file

    Returns:
        numpy.ndarray: 3D binary image (bool), where True/1 = solid, False/0 = void
    """
    img = tifffile.imread(filepath)

    # Ensure binary: if values are 0 and 255 (common in image formats), normalize to 0/1
    if img.dtype == np.uint8 or img.dtype == np.uint16:
        unique_vals = np.unique(img)
        if set(unique_vals).issubset({0, 255}) or set(unique_vals).issubset({0, 65535}):
            img = (img > 0).astype(np.uint8)

    # Convert to boolean: solid = True/1, void = False/0
    binary_img = img.astype(bool)

    return binary_img


def extract_basic_params(binary_img, resolution, pixel_density=0.917):
    """
    Extract basic microstructural parameters from a binary image.

    Parameters:
        binary_img (numpy.ndarray): 3D binary image (solid=True, void=False)
        resolution (float): Voxel resolution in meters
        pixel_density (float): Density of solid material in g/cm³

    Returns:
        dict: Dictionary of basic parameters
    """
    results = {}

    # Porosity, density, sample volume
    porosity, density, sample_volume = por_den_vol(binary_img, resolution, pixel_density)
    results['porosity'] = porosity
    results['density_g_per_cm3'] = density
    results['sample_volume_cm3'] = sample_volume

    # Euler characteristic (Euler density)
    euler_density = euler_characteristic(binary_img, resolution)
    results['euler_density_per_cm3'] = euler_density

    # Specific surface area
    specific_area = specific_surface_area(binary_img, resolution)
    results['specific_surface_area_m2_per_m3'] = round(specific_area, 3)

    # Mean intercept length
    mil_x, mil_y, mil_z = mean_intercept_length(binary_img, resolution)
    results['mil_x_mm'] = mil_x
    results['mil_y_mm'] = mil_y
    results['mil_z_mm'] = mil_z
    results['mil_mean_mm'] = round(np.mean([mil_x, mil_y, mil_z]), 3)

    # Pore classification
    group1_pct, group2_pct, group3_pct = classify_pores(binary_img)
    results['porosity_open'] = group1_pct
    results['porosity_cuted'] = group2_pct
    results['porosity_isolated'] = group3_pct

    return results


def extract_transport_params(binary_img, resolution):
    """
    Extract transport-related microstructural parameters from a binary image.
    Permeability and tortuosity are computed for all three directions
    (z, y, x) independently.

    Parameters:
        binary_img (numpy.ndarray): 3D binary image (solid=True, void=False)
        resolution (float): Voxel resolution in meters

    Returns:
        dict: Dictionary of transport parameters
    """
    results = {}

    # Spherical ice cluster thickness
    try:
        cluster_thickness = spherical_ice_cluster(binary_img)
        results['spherical_ice_cluster_pix'] = round(cluster_thickness, 3)
    except Exception as e:
        print(f"  Warning: spherical_ice_cluster failed: {e}")
        results['spherical_ice_cluster_pix'] = None

    # Skeleton metrics (pore network)
    try:
        skel = skeleton_metrics(binary_img, resolution)
        for key, value in skel.items():
            if isinstance(value, (np.floating, float)):
                results[key] = round(float(value), 3)
            elif isinstance(value, (np.integer, int)):
                results[key] = int(value)
            else:
                results[key] = value
    except Exception as e:
        print(f"  Warning: skeleton_metrics failed: {e}")
        for key in ['num_pores', 'num_throats', 'coordination_number',
                     'avg_pore_volume', 'avg_pore_diameter', 'avg_throat_diameter',
                     'avg_throat_length', 'max_connections', 'median_connections',
                     'num_cluster', 'max_cluster_size', 'avg_cluster_size',
                     'avg_pore_surface_area', 'avg_throat_area',
                     'std_coordination_number']:
            results[key] = None

    # Permeability and tortuosity for all three directions
    directions = [
        ('zmin', 'zmax', 'z'),
        ('ymin', 'ymax', 'y'),
        ('xmin', 'xmax', 'x'),
    ]

    for p1, p2, label in directions:
        # Permeability
        try:
            k = calculate_permeability(binary_img, resolution, p1, p2)
            results[f'permeability_{label}_m2'] = round(float(k), 10)
        except Exception as e:
            print(f"  Warning: calculate_permeability ({label}) failed: {e}")
            results[f'permeability_{label}_m2'] = None

        # Tortuosity
        try:
            tau = calculate_tortuosity(binary_img, resolution, p1, p2)
            results[f'tortuosity_{label}'] = round(float(tau), 3)
        except Exception as e:
            print(f"  Warning: calculate_tortuosity ({label}) failed: {e}")
            results[f'tortuosity_{label}'] = None

    return results


def process_single_file(filepath, resolution, pixel_density, output_dir):
    """
    Process a single binary .tif file: extract parameters and save JSON.

    Parameters:
        filepath (str): Path to the .tif file
        resolution (float): Voxel resolution in meters
        pixel_density (float): Density of solid material in g/cm³
        output_dir (str): Directory to save JSON output

    Returns:
        dict: Extracted parameters, or None on failure
    """
    filename = os.path.basename(filepath)
    base_name = os.path.splitext(filename)[0]

    print(f"\n{'='*60}")
    print(f"Processing: {filename}")
    print(f"{'='*60}")

    # Load the binary image
    try:
        binary_img = load_binary_tif(filepath)
        print(f"  Image shape: {binary_img.shape}")
        print(f"  Solid fraction: {np.sum(binary_img) / binary_img.size:.4f}")
    except Exception as e:
        print(f"  ERROR: Failed to load {filepath}: {e}")
        return None

    # Initialize results dictionary with metadata
    results = {
        'filename': filename,
        'filepath': filepath,
        'image_shape': list(binary_img.shape),
        'total_voxels': int(binary_img.size),
        'solid_voxels': int(np.sum(binary_img)),
        'solid_fraction': round(float(np.sum(binary_img) / binary_img.size), 4),
        'resolution_m': resolution,
        'pixel_density_g_per_cm3': pixel_density,
        'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    # Extract basic parameters
    print("  Extracting basic parameters...")
    try:
        basic_params = extract_basic_params(binary_img, resolution, pixel_density)
        results.update(basic_params)
        print(f"    Porosity: {basic_params['porosity']}")
        print(f"    Density: {basic_params['density_g_per_cm3']} g/cm³")
    except Exception as e:
        print(f"  ERROR: Basic parameter extraction failed: {e}")
        return None

    # Extract transport parameters
    print("  Extracting transport parameters...")
    transport_params = extract_transport_params(binary_img, resolution)
    results.update(transport_params)

    # Save to JSON
    json_filename = f"{base_name}_features.json"
    json_path = os.path.join(output_dir, json_filename)

    # Convert numpy types to native Python types for JSON serialization
    def convert_to_serializable(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return obj

    serializable_results = {}
    for key, value in results.items():
        serializable_results[key] = convert_to_serializable(value)

    try:
        with open(json_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        print(f"  Results saved to: {json_path}")
    except Exception as e:
        print(f"  ERROR: Failed to save JSON: {e}")
        return None

    return serializable_results


def main():
    parser = argparse.ArgumentParser(
        description='Extract microstructural parameters from binary .tif images.'
    )
    parser.add_argument(
        '--input_dir', type=str, required=True,
        help='Directory containing binary .tif files'
    )
    parser.add_argument(
        '--output_dir', type=str, default=None,
        help='Directory to save JSON results (default: same as input_dir)'
    )
    parser.add_argument(
        '--resolution', type=float, required=True,
        help='Voxel resolution in meters (e.g., 1e-5 for 10 microns)'
    )
    parser.add_argument(
        '--pixel_density', type=float, default=0.917,
        help='Density of solid material in g/cm³ (default: 0.917 for ice)'
    )
    args = parser.parse_args()

    # Validate input directory
    input_dir = args.input_dir
    if not os.path.isdir(input_dir):
        print(f"ERROR: Input directory does not exist: {input_dir}")
        sys.exit(1)

    # Set output directory
    output_dir = args.output_dir if args.output_dir else input_dir
    os.makedirs(output_dir, exist_ok=True)

    # Find all .tif files directly
    tif_pattern = os.path.join(input_dir, '*.tif')
    tif_files = sorted(glob.glob(tif_pattern))

    if not tif_files:
        print(f"ERROR: No .tif files found in {input_dir}")
        sys.exit(1)

    print(f"Found {len(tif_files)} .tif file(s) to process")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Resolution: {args.resolution} m")
    print(f"Pixel density: {args.pixel_density} g/cm³")
    print()

    # Process each file
    successful = 0
    failed = 0
    failed_files = []

    for i, filepath in enumerate(tif_files, 1):
        print(f"\n[{i}/{len(tif_files)}]")
        result = process_single_file(
            filepath, args.resolution, args.pixel_density, output_dir
        )

        if result is not None:
            successful += 1
        else:
            failed += 1
            failed_files.append(os.path.basename(filepath))

    # Print summary
    print(f"\n{'='*60}")
    print(f"PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"  Total files: {len(tif_files)}")
    print(f"  Successful:  {successful}")
    print(f"  Failed:      {failed}")

    if failed_files:
        print(f"\n  Failed files:")
        for fname in failed_files:
            print(f"    - {fname}")

    print(f"\nJSON results saved in: {output_dir}")


if __name__ == '__main__':
    main()