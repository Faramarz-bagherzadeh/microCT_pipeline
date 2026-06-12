
def contrast_stretching_full(input_image):
                # Contrast stretching
                        # Dropping extreems (artifacts)
    p2, p98 = np.percentile(input_image, (2, 98))
    stretched_image = skimage.exposure.rescale_intensity(input_image, in_range=(p2, p98))
    return stretched_image.astype('uint8')
                                                
def reshape_to_10240_1024_1024(data):
    """Center-crop or pad the volume to shape (10240, 1024, 1024)."""
    if not isinstance(data, np.ndarray):
        raise ValueError("Input must be a NumPy array")
    if data.ndim != 3:
        raise ValueError("Input data must have shape (n, height, width)")

    depth_target = 10240
    height_target = 1024
    width_target = 1024

    depth, height, width = data.shape

    depth_start = 0
    height_start = 0
    width_start = 0
    depth_end = depth
    height_end = height
    width_end = width

    if depth > depth_target:
        depth_start = (depth - depth_target) // 2
        depth_end = depth_start + depth_target
    if height > height_target:
        height_start = (height - height_target) // 2
        height_end = height_start + height_target
    if width > width_target:
        width_start = (width - width_target) // 2
        width_end = width_start + width_target

    cropped = data[depth_start:depth_end, height_start:height_end, width_start:width_end]

    pad_front = max((depth_target - cropped.shape[0]) // 2, 0)
    pad_back = depth_target - cropped.shape[0] - pad_front
    pad_top = max((height_target - cropped.shape[1]) // 2, 0)
    pad_bottom = height_target - cropped.shape[1] - pad_top
    pad_left = max((width_target - cropped.shape[2]) // 2, 0)
    pad_right = width_target - cropped.shape[2] - pad_left

    if pad_front > 0 or pad_back > 0 or pad_top > 0 or pad_bottom > 0 or pad_left > 0 or pad_right > 0:
        cropped = np.pad(
            cropped,
            ((pad_front, pad_back), (pad_top, pad_bottom), (pad_left, pad_right)),
            mode="constant",
            constant_values=0,
        )

    return cropped,pad_front


def patching_volume_with_half_overlap(volume, patch_size):
    """
    Taking a volume and patch it with overlap in such way that
    it is reversable to original volume.
    """
    original_vol_shape = volume.shape
    step = patch_size // 2
    patches = patchify(
        volume,
        (patch_size, patch_size, patch_size),
        step=step,
    )
    original_patch_shape = patches.shape
    patches = patches.reshape(-1,patch_size,patch_size,patch_size)
    return patches ,original_patch_shape ,original_vol_shape


def unpatchify_volume_center_croped(patches,
                                    original_patch_shape,
                                    original_vol_shape):
    """
    Taking the processed patches and reconstructing the original volume
    """
    cp = patches.shape[-1] # new length of each patch after ML model
    op = original_patch_shape[0] # original patching dimenssions   
    o = original_vol_shape[0] # original image dimenssions
    #back to original patched spacing but with smaller croped patch size
    patches = patches.reshape(op,op,op,cp,cp,cp)
    #back to original volume size
    volume = unpatchify(patches,(o-cp,o-cp,o-cp))
    return volume



def load_checkpoint(checkpoint, model):
    print("=> Loading checkpoint")
    model.load_state_dict(checkpoint["state_dict"])


def predict(model,data,patch_size, batch_size=128):
    prediction = np.zeros((data.shape[0],patch_size//2,patch_size//2,patch_size//2), dtype='uint8')
    torch.set_num_threads(120)
    #drop zero patches to save time
    non_zero_indices = np.where(np.sum(data, axis=(1,2,3)) != 0)[0]

    loop_len = len (non_zero_indices)//batch_size
    for i in range(0,loop_len+1):
        
        if i+1 > loop_len:
            r = [i*batch_size, None] # make sure we read all patches
        else:
            r = [i*batch_size, (i+1)*batch_size]
                
        input_= torch.from_numpy(data[non_zero_indices[r[0]:r[1]]]).unsqueeze(1).float()
        input_ = input_/255 #normalization
        input_ = input_.to(device)
        output_= model(input_).cpu().detach().numpy()
        output_ = output_[:,0,:,:,:]*255 # back to real scale
        output_ = output_.astype('uint8')
        prediction[non_zero_indices[r[0]:r[1]]]=output_

    return prediction



def get_ice_part(image, thresh1, thresh2, thickness):
    final_mask = np.zeros_like(image)
    for i in range(image.shape[0]):
        img = image[i]
        # Apply a binary threshold to create a binary image
        _, binary = cv2.threshold(img, thresh1, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)

        mask_1 = np.zeros_like(binary) # for removing tube
        mask_2 = np.zeros_like(binary) # contains ice
        mask_3 = np.zeros_like(binary) # for removing middle part
        #print ('number of contours in first mask',len(contours))
        for cnt in contours[:]:
            area = cv2.contourArea(cnt)
            if area > 100:  # Adjust this threshold based on the size of the ice pieces
                cv2.drawContours(mask_1, [cnt], -1, 1, thickness=thickness)
                cv2.drawContours(mask_2, [cnt], -1, 1, thickness=-1)
        mask_2[mask_1 == 1] =0
        img = mask_2*img
        _, binary = cv2.threshold(img, thresh2, 1, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary = cv2.dilate(binary, kernel=None, iterations=3)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        #print ('number of contours in second mask',len(contours))
        contours = sorted(contours, key=lambda x: cv2.contourArea(x), reverse=True)

        for cnt in contours[:2]:
            area = cv2.contourArea(cnt)
            if area > 100:  # Adjust this threshold based on the size of the ice pieces
                cv2.drawContours(mask_3, [cnt], -1, 1, thickness=-1)
        final_mask[i] = mask_3
    
    #Compute the mean value of each mask
    mask_means = np.mean(final_mask, axis=(1, 2))

    #Identify outliers (small masks)
    # You can define an outlier threshold, e.g., mean value less than a certain percentage of the global mean
    global_mean = np.mean(mask_means)
    outlier_threshold = 0.99 * global_mean  #  threshold
    outlier_indices = np.where(mask_means < outlier_threshold)[0]

    # Identify good masks
    good_indices = np.where(mask_means >= outlier_threshold)[0]

    # Helper function to find the closest good index
    def find_closest_good_index(bad_index, good_indices):
        return good_indices[np.abs(good_indices - bad_index).argmin()]

    # Replace outlier masks with the closest good mask
    for outlier_index in outlier_indices:
        closest_good_index = find_closest_good_index(outlier_index, good_indices)
        final_mask[outlier_index] = final_mask[closest_good_index]
    
    
    return final_mask
    
   
    

    
if __name__ == "__main__":
    import numpy as np
    import tifffile
    import torch
    import skimage
    from patchify import patchify, unpatchify
    import glob
    from scipy import ndimage
    import torch.nn as nn
    import time
    import cv2 
    from rek_read import read_rek_file
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--input_dir", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)

    args = parser.parse_args()

    input_dir = args.input_dir
    output_dir = args.output_dir

    print("Input directory:", input_dir)
    print("Output directory:", output_dir)


    
    if torch.cuda.is_available():
        device_count = torch.cuda.device_count()
        print(f"Number of CUDA devices available: {device_count}")
        for i in range(device_count):
            device = torch.cuda.get_device_name(i)
            print(f"Device {i}: {device}")
    else:
        print("CUDA is not available on this machine.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    

    import SRResnet
    n_chanels = 16
    num_residual_blocks = 8
    model = SRResnet.SRResNet(num_blocks = num_residual_blocks, n_chanels = n_chanels)
    model.to(device)
    if torch.cuda.device_count() > 1:
        print(f"Using {torch.cuda.device_count()} GPUs")
        model = nn.DataParallel(model)
        
    load_checkpoint(torch.load("my_SRResnet_RS8_NC16_checkpoint_NoAugmentation.pth.tar",map_location=torch.device(device) ), model)
    print ("Model loaded successfully")
    t1= time.time()

    name = input_dir.split('/')[-1].split('.')[0]
    print ('*********************************************')
    print ('file name = ', name)

    data = read_rek_file(input_dir)
    print ('original data shape = ', data.shape)
    data = contrast_stretching_full(data)
    print ('contrast stretching done!')
    mask = get_ice_part(data, 10, 20, 26) #Thickness = 26 is a proper number 
    # use this mask if needed to filter ice parts before SR operation
    data = data *mask
    del mask

    
    patch_size = 64
    data, pad_front = reshape_to_10240_1024_1024(data)
    print ('reshaping done! ', data.shape)
    patches ,original_patch_shape ,original_vol_shape = patching_volume_with_half_overlap(data, patch_size=patch_size)
    print ('patching done! ', patches.shape)
    output = predict(model,patches,patch_size=patch_size, batch_size=32)
    print ('prediction done! ', output.shape)
    output = unpatchify_volume_center_croped(output, original_patch_shape, original_vol_shape)
    output = output.astype('uint8')
    print ('unpatching done! ', output.shape)
    output = output[pad_front:pad_front+data.shape[0],:,:] # remove the padding part if there is any
    metadata = {
        'axes': 'ZYX',  # Adjust according to your image axes, could be 'XY', 'XYZ', 'ZYX', etc.
        'spacing': 1.0,  # Pixel size along Z-axis (modify as needed)
        'unit': 'um',    # Units, e.g., 'micrometer' or 'nm'
        'description': '3D image data with proper metadata for ImageJ'}
    print ('saving image...')
    tifffile.imwrite(output_dir + name + '_.tif', output,photometric='minisblack',metadata=metadata,imagej=True)
        
    
    t2= time.time()
    print ('Time (h) =', round((t2-t1)/3600,1))
        
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
