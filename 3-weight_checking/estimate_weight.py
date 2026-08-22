
def weight_estimation(img, pixel_length, density):

    if img.max()> 1 :
        return 'Error: file is not binarized'

    pixel_vol = pixel_length**3
    ice_pixel_sum = img.sum()
    weight =  ice_pixel_sum* density * pixel_vol

    return weight


def process_file(f, original_weight_df, density):
    """Process a single TIFF file and return its results.

    This is a standalone function so it can be pickled and distributed
    across worker processes for parallel execution.
    """
    import tifffile
    import numpy as np

    data = tifffile.imread(f)
    name = f.split('/')[-1].split('.')[0]
    pixel_length = float(name.split('_')[-1]) / 10000  # 0.0120 #cm
    name = name[:-4]  # Remove the last 4 characters (resolution)
    print('resolution (pixel_length) = ', pixel_length, 'cm')
    print('*********************************************')
    print('processing file: ', name)
    print('shape = ', data.shape)

    try:
        actual_weight = original_weight_df[original_weight_df['file_name'] == name]['weight'].values[0]
        depth = original_weight_df[original_weight_df['file_name'] == name]['depth'].values[0]
        estimated_weight = weight_estimation(data, pixel_length=pixel_length, density=density)
        return {
            'file_name': name,
            'depth': depth,
            'estimated_weight': estimated_weight,
            'actual_weight': actual_weight,
        }
    except Exception as e:
        print(f"Error processing on :{name}: {e}")
        return None


if __name__ == "__main__":
    import numpy as np
    import tifffile
    import glob
    import pandas as pd
    import argparse
    import matplotlib.pyplot as plt
    import os
    from concurrent.futures import ProcessPoolExecutor, as_completed

    parser = argparse.ArgumentParser()

    parser.add_argument("--weights_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--tiff_dir", type=str, required=True)
    parser.add_argument("--num_workers", type=int, default=10,
                        help="Number of files to process in parallel (default: 10)")

    args = parser.parse_args()

    weights_file = args.weights_file
    output_dir = args.output_dir
    tiff_dir = args.tiff_dir
    num_workers = args.num_workers

    print("Weights file:", weights_file)
    print("Output directory:", output_dir)
    print("TIFF directory:", tiff_dir)
    print("Number of parallel workers:", num_workers)

    density = 0.917  # g/cm3
    print('density = ', density, 'g/cm3')

    paths = glob.glob(tiff_dir + '/*.tif')
    print('number of files =', len(paths))
    original_weight_df = pd.read_excel(weights_file)

    results = []
    # Process files in parallel, up to `num_workers` at a time
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_path = {
            executor.submit(process_file, f, original_weight_df, density): f
            for f in paths
        }
        for future in as_completed(future_to_path):
            f = future_to_path[future]
            try:
                result = future.result()
                if result is not None:
                    results.append(result)
            except Exception as e:
                print(f"Unexpected error processing {f}: {e}")

    df = pd.DataFrame(results, columns=['file_name', 'depth', 'estimated_weight', 'actual_weight'])
    df['error'] = df['estimated_weight'] - df['actual_weight']
    df['error_percent'] = df['error'] / df['actual_weight'] * 100
    df.to_excel(output_dir + '/estimated_weights.xlsx', index=False)
    print('Saved estimated weights to: ', output_dir + '/estimated_weights.xlsx')

    plt.figure()
    plt.scatter(df['actual_weight'], df['estimated_weight'])
    # Add 45-degree dashed line (y = x) for perfect agreement reference
    min_val = min(df['actual_weight'].min(), df['estimated_weight'].min())
    max_val = max(df['actual_weight'].max(), df['estimated_weight'].max())
    plt.plot([min_val, max_val], [min_val, max_val], 'k--')
    plt.xlabel('Actual Weight (g)')
    plt.ylabel('Estimated Weight (g)')
    plt.title('Weight Estimation Comparison')
    plt.savefig(output_dir + '/fig1.png')
    plt.close()

    plt.figure()
    plt.title('Estimtated - Actual Weight vs. Depth')
    plt.scatter(df['depth'], df['error_percent'])
    plt.xlabel('Depth (cm)')
    plt.ylabel('Error (%)')
    plt.title('Weight Estimation Error vs. Depth')
    plt.savefig(output_dir + '/fig2.png')
    plt.close()
    print('Saved figures to: ', output_dir)