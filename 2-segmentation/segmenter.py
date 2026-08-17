

def get_ice_part(image,skip,thresh1, kernel_size):
    final_mask = np.zeros_like(image)
    for i in range(0,image.shape[0]-skip,skip):
        img = image[i]
        if img.sum()<5e3: # passing to next image if it is mostly black
            continue

        # Apply a binary threshold to create a binary image
        _, binary = cv2.threshold(img, thresh1, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)

        mask = np.zeros_like(binary) # contains ice

        for cnt in contours[:]:
            area = cv2.contourArea(cnt)
            if area > 100:  # Adjust this threshold based on the size of the ice pieces
                cv2.drawContours(mask, [cnt], -1, 1, thickness=-1)

        kernel = np.ones((kernel_size,kernel_size),np.uint8)
        erosion_mask = cv2.erode(mask,kernel,iterations = 1)
        if erosion_mask.sum()<1e3:
            continue
        final_mask[i] = erosion_mask
    return final_mask




def contrast_stretching(input_image):
    import skimage
    #Contrast stretching
    #Dropping extreems (artifacts)
    p2, p98 = np.percentile(input_image, (1, 99))
    stretched_image = skimage.exposure.rescale_intensity(input_image, in_range=(p2, p98))
    return stretched_image.astype('uint8')

'''
def GMM_seg(img):
    from sklearn.mixture import GaussianMixture as GMM
    binary_img = np.zeros_like(img)
    mask = get_ice_part(img, skip= 50   ,thresh1=15,kernel_size=100)
    pixels = img[mask==1].reshape((-1, 1))

    if len(pixels) < 1e3:
        return binary_img

    gmm_model = GMM(n_components=2, random_state=20, covariance_type='full', init_params='kmeans').fit(pixels)
    ice_class = gmm_model.means_.round(3).tolist()
    ice_class_index = ice_class.index(max(ice_class))

    gmm_labels = img.reshape((-1, 1))
    gmm_labels = gmm_model.predict(gmm_labels)
    gmm_labels = gmm_labels.reshape(img.shape)
    binary_img[gmm_labels == ice_class_index] = 1
    return binary_img

'''
def binary_seg_kMeans(img):
    from sklearn.cluster import KMeans
    print ('K-Mean started !')
    constant = 0

    binary = np.zeros_like(img)
    mask = get_ice_part(img, skip=200,thresh1=15,kernel_size=100)
    pixels = img[mask==1].reshape(-1, 1)

    if len(pixels) < 1e3:
        return binary

    kmeans = KMeans(n_init=4, n_clusters=2,)
    kmeans.fit(pixels)

    centers = kmeans.cluster_centers_
    thresh = (centers[0] + centers[1])/2
    thresh = round(thresh[0])+ constant
    print (thresh)
    binary[img > thresh] = 1

    return binary
'''
def Otsu(img):
    import skimage.filters as skf
    #binary = np.zeros_like(img)
    mask = get_ice_part(img, skip=200,thresh1=15,kernel_size=200)
    pixels = img[mask==1].reshape(-1, 1)
    if len(pixels) < 1e3:
        print ('No ice detected in Otsu!')
        return None
    thresh = skf.threshold_otsu(pixels)
    print('Otsu Threshold = ',thresh)
    #binary[img > thresh] = 1
    return thresh
'''
def segmentation_function(image, batch):
    import numpy as np
    segmented_img = np.zeros_like(image)
    for s in range (0,image.shape[0],batch):
        print ('steps = ',s,s+batch)
        if s+batch > image.shape[0]:
            img = image[s:,:,:]
        else:
            img = image[s:s+batch,:,:]

        img = contrast_stretching(img)
        binary = binary_seg_kMeans(img)
        #binary = GMM_seg(img)
        #binary = Otsu(img)
        if s+batch > image.shape[0]:
            segmented_img[s:,:,:] = binary
        else:
            segmented_img[s:s+batch,:,:]= binary

    return segmented_img.astype('uint8')
'''

def segmentation_by_weight_3(image, name):
    """Segmentation based on adaptive core weights (optimized binary search)."""
    import numpy as np
    import pandas as pd
    import cv2

    resolution = 0.00601  # cm
    density_ice = 0.917  # g/cm³

    # --- Load true weights ---
    core_name = name.split('_')[0]
    weight_dfs = {'B40': 'B40_weights.csv', 'T4MP00': 'T4MP00_weights.csv', 'B45': 'B45_weights.csv'}
    df = pd.read_csv(weight_dfs[core_name])

    left_core = int(name.split('Bag')[1].split('_')[0])
    left_core_weight = df.loc[df['Bag'] == left_core, 'Weight'].iloc[0]

    right_core_weight = 0
    if core_name not in ['T4MP00', 'B45'] and left_core not in [7]:
        right_core = int(name.split('Bag')[1].split('_')[1])
        right_core_weight = df.loc[df['Bag'] == right_core, 'Weight'].iloc[0]

    total_weight = left_core_weight + right_core_weight 
    total_weight -= total_weight * 0.02

    # --- Precompute histogram of pixel intensities ---
    mask_nonzero = image > 0
    pixels = image[mask_nonzero].ravel()
    hist, bin_edges = np.histogram(pixels, bins=256, range=(0, 256))
    pixel_mass = (resolution ** 3) * density_ice

    # --- Compute cumulative weights from brightest to darkest ---
    cum_mass = np.cumsum(hist[::-1])[::-1] * pixel_mass
    errors = np.abs(cum_mass - total_weight)
    best_idx = np.argmin(errors)
    best_thresh = bin_edges[best_idx]
    best_est_weight = cum_mass[best_idx]
    print (f"Best estimated weight at threshold {best_thresh:.3f}: {best_est_weight:.2f} g")

    binary = (image >= best_thresh).astype(np.uint8)
    image_weight = binary.sum() * (resolution ** 3) * density_ice
    best_error = abs(image_weight - total_weight)


    print(f"Optimal threshold: {best_thresh:.3f}, Error: {best_error:.2f} g, , Real Weight: {total_weight:.2f} g, Weight: {image_weight:.2f} g")
    if best_error > 100:
        print("Warning: High error in estimated weight!")
        del binary
        binary = segmentation_function(image, batch=4000)
        image_weight = binary.sum() * (resolution ** 3) * density_ice
        best_error = abs(image_weight - total_weight)
        print(f"Error: {best_error:.2f} g, Real Weight: {total_weight:.2f} g, Estimated Weight: {image_weight:.2f} g")

    return binary , errors
'''
if __name__ == "__main__":
    

    import cv2
    import numpy as np
    import tifffile
    import glob
    import time
    import os
    import argparse
    os.environ["OPENBLAS_NUM_THREADS"] = str(os.cpu_count()-10)
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    parser = argparse.ArgumentParser()

    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)


    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir

    print("Input directory:", input_dir)
    print("Output directory:", output_dir)


    batch = 5000
    print ('batch size = ', batch)

    t1 = time.time()
    data = tifffile.imread(input_dir)
    print ('Data shape = ',data.shape)
    name = os.path.basename(input_dir).split('.ti')[0]
    print ('*********************************************')
    print ('file name = ', name)
    print ('shape = ',data.shape)
    segmented_data = segmentation_function(data, batch)
        #segmented_data, err_array = segmentation_by_weight_3(data,name)
        #np.save(f'weight_errors/{name}_errors.npy', err_array)
    del data
    t2= time.time()
    print ('Time (min) =', round((t2-t1)/60 , 1))
    tifffile.imwrite(output_dir+'/'+name+'.tif', segmented_data)
