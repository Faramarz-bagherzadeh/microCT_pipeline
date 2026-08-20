def get_ice_volume(image,thresh1,pixel_length):
    import cv2
    import numpy as np
    final_mask = np.zeros_like(image)
    for i in range(image.shape[0]):
        img = image[i]
        if img.sum()<100: # passing to next image if it is mostly black
            continue
        # Apply a binary threshold to create a binary image
        _, binary = cv2.threshold(img, thresh1, 1, cv2.THRESH_BINARY )
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)
        mask = np.zeros_like(binary) # contains ice

        for cnt in contours[:]:
            area = cv2.contourArea(cnt)
            if area > 100:  # Adjust this threshold based on the size of the ice pieces
                cv2.drawContours(mask, [cnt], -1, 1, thickness=-1)

        final_mask[i] = mask

    print ('final_mask.sum()',final_mask.sum())
    ice_volume = final_mask.sum()*(pixel_length**3)

    return ice_volume


def weight_estimation(img, pixel_length, density):

    if img.max()> 1 :
        return 'Error: file is not binarized'

    pixel_vol = pixel_length**3
    ice_pixel_sum = img.sum()
    weight =  ice_pixel_sum* density * pixel_vol

    return weight



if __name__ == "__main__":
    import numpy as np
    import tifffile
    import glob
    import pandas as pd
    import argparse
    import matplotlib.pyplot as plt
    import os

    parser = argparse.ArgumentParser()

    parser.add_argument("--weights_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--tiff_dir", type=str, required=True)

    args = parser.parse_args()

    weights_file = args.weights_file
    output_dir = args.output_dir
    tiff_dir = args.tiff_dir

    print("Weights file:", weights_file)
    print("Output directory:", output_dir)
    print("TIFF directory:", tiff_dir)
     
    density = 0.917 #g/cm3
    print ('density = ', density, 'g/cm3')

    df = pd.DataFrame(columns=['file_name', 'depth', 'estimated_weight', 'actual_weight'])
    estimated_weights = []
    actual_weights = []
    names = []
    depths = []
    paths = glob.glob(tiff_dir + '/*.tif')
    print ('number of files =' ,len(paths))
    original_weight_df = pd.read_excel(weights_file)

    for f in paths:

        data = tifffile.imread(f)
        name = f.split('/')[-1].split('.')[0]
        pixel_length= float(name.split('_')[-1])/10000 #0.0120 #cm
        name = name [:-4]  # Remove the last 4 characters (resolution)
        print ('resolution (pixel_length) = ', pixel_length, 'cm')
        print ('*********************************************')
        print ('processing file: ', name)
        print ('shape = ',data.shape)
        try :
            actual_weights.append(original_weight_df[original_weight_df['file_name'] == name]['weight'].values[0])
            depths.append(original_weight_df[original_weight_df['file_name'] == name]['depth'].values[0] )
            estimated_weights.append(weight_estimation(data, pixel_length=pixel_length, density =density ))
            names.append(name)
        except Exception as e:
            print(f"Error processing on :{name}: {e}")


    df['estimated_weight'] = estimated_weights
    df['file_name'] = names
    df['depth'] = depths
    df['actual_weight'] = actual_weights
    df['error'] = df['estimated_weight'] - df['actual_weight']
    df['error_percent'] = df['error'] / df['actual_weight'] * 100
    df.to_excel(output_dir + '/estimated_weights.xlsx', index=False)
    print ('Saved estimated weights to: ', output_dir + '/estimated_weights.xlsx')

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
    print ('Saved figures to: ', output_dir)