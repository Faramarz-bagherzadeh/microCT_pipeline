

def get_ice_part(data,depth):
    """
    data is a binary 3d image
    kernel_size_dilute = 2 for bubble ice
    kernel_size_dilute = 20 for compressed snow
    """
    if depth < 80:
        kernel_size_dilute=80
    else:
        kernel_size_dilute=50

    mask = np.zeros_like(data)
    kernel_dilute = np.ones((kernel_size_dilute,kernel_size_dilute),np.uint8)

    for i in range(data.shape[0]):
        an_img = data[i]
        a_mask = np.zeros_like(an_img)
        diluted = cv2.dilate(an_img,kernel_dilute,iterations = 1)
        contours, _ = cv2.findContours(diluted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 10:  # Adjust this threshold based on the size of the ice pieces
                cv2.drawContours(a_mask, [cnt], -1, 1, thickness=-1)

        mask[i] = a_mask
    return mask


def set_sample_volume(data, ice_mask):
    #cropping x and y assuming z is already cropped by the sample maker

    if ice_mask.shape != data.shape:
        raise ValueError("The shape of the ice mask does not match the shape of the data.")

    half_edge = int(data.shape[0] / 2)

    try:
        rg = regionprops (ice_mask.astype('uint8'))
        center = rg[0].centroid
    except:
        center = tuple((np.array(data.shape) // 2).astype(int))

    x_start = int( center[2] - half_edge)
    x_end = int(center[2] + half_edge )

    y_start = int(center[1] - half_edge)
    y_end = int(center[1] + half_edge )

    print ('center = ',center)
    print ('bounds = ',x_start,x_end,y_start,y_end)

    sample = data[:, y_start:y_end, x_start:x_end] 

    return sample
    

def sample_maker(data, depth, step, sample_size, output_dir, name):
    sample_size = int(sample_size)
    step = int(step)
    d_step = 1/data.shape[0] # assuming sample are one meter each
    skip = 100 # to avoid the black layers at the beginning and end of the data

    for i in range(skip,data.shape[0]-skip,step):
        starting_layer = i
        ending_layer = i+sample_size

        if i+sample_size >= data.shape[0]:
           # ending_layer = -1
           break
        sample = data[starting_layer:ending_layer] # grabing the sample along the depth dimension
        ice_mask = get_ice_part(sample, depth)  # getting the ice mask for the sample
        sample_volume = set_sample_volume(sample,ice_mask)  # setting the sample volume (croping x and y) based on the ice mask
        tifffile.imwrite(output_dir+'/'+name+ '_' + str(depth + round(d_step*i,3)) + '_'+ '.tif', sample_volume.astype('uint8'))
    
    return None

if __name__ == "__main__":
    import numpy as np
    import tifffile
    import glob
    import pandas as pd
    import argparse
    import os
    from skimage.measure import label, regionprops
    import cv2

    parser = argparse.ArgumentParser()

    parser.add_argument("--weights_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--tiff_dir", type=str, required=True)
    parser.add_argument("--sample_size", type=str, required=True)
    parser.add_argument("--overlap_size", type=str, required=True)

    args = parser.parse_args()

    weights_file = args.weights_file
    output_dir = args.output_dir
    tiff_dir = args.tiff_dir
    sample_size = args.sample_size
    overlap_size = args.overlap_size
    step = int(sample_size) - int(overlap_size)

    print("Weights file:", weights_file)
    print("Output directory:", output_dir)
    print("TIFF directory:", tiff_dir)
    print("Sample size:", sample_size)
    print("Step size:", step)
    print("Overlap size:", overlap_size)


    paths = glob.glob(tiff_dir + '/*.tif')
    print ('number of files =' ,len(paths))
    original_weight_df = pd.read_excel(weights_file)

    for f in paths:
        data = tifffile.imread(f)
        name = f.split('/')[-1].split('.')[0]
        print ('*********************************************')
        print ('processing file: ', name)
        print ('shape = ',data.shape)
        try :
            depth = original_weight_df[original_weight_df['file_name'] == name]['depth'].values[0]
            depth = depth - 1 # to make it count from beginning of a bag
            sample_maker(data, depth, step, sample_size, output_dir, name)

        except Exception as e:
            print(f"Error processing on :{name}: {e}")

