def get_ice_volume(image,thresh1,pixel_length):
    import cv2
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

def uncertainity_function (img_seg, pixel_volume, density):
    from skimage.segmentation import find_boundaries
    uncertainity = 0
    step = 100
    for s in range (0,img_seg.shape[0],step):
        print ('steps = ',s,s+step)
        if s+step > data.shape[0]:
            img = img_seg[s:,:,:]
        else:
            img = img_seg[s:s+step,:,:]

        boundary = find_boundaries(img, connectivity=1, mode='outer', background=0)
        boundary_pixel_count = np.sum(boundary)
        uncertainity += boundary_pixel_count * (pixel_volume *0.5) * density
    return uncertainity

def get_real_porousity (img_seg, pixel_volume, density):
    from skimage.segmentation import find_boundaries
    uncertainity = 0
    step = 100
    for s in range (0,img_seg.shape[0],step):
        print ('steps = ',s,s+step)
        if s+step > data.shape[0]:
            img = img_seg[s:,:,:]
        else:
            img = img_seg[s:s+step,:,:]

        boundary = find_boundaries(img, connectivity=1, mode='outer', background=0)
        boundary_pixel_count = np.sum(boundary)
        uncertainity += boundary_pixel_count * (pixel_volume *0.5) * density
    return uncertainity

if __name__ == "__main__":
    import numpy as np
    import tifffile
    import glob
    import pandas as pd
    df = pd.DataFrame(columns=['name','weight'])
    weights = []
    names = []
    
    pixel_length=0.00601035
    density = 0.917
    paths = glob.glob('../B40_SR_seg/*.tif')
    print(paths)
    print ('number of files =' ,len(paths))

    for f in paths:

        data = tifffile.imread(f)
        name = f.split('/')[-1].split('.')[0]
        print ('*********************************************')

        print ('shape = ',data.shape)
        weight = weight_estimation(data, pixel_length=pixel_length, density =density )
        print (name, ', weight =  ', weight)
        #unc = uncertainity_function(data, pixel_volume=pixel_length**3, density=density)
        #print (name, ', uncertainity =  ', unc)
        #ice_volume = get_ice_volume(data,0.5, pixel_length)
        #print (name, ', ice volume = ', ice_volume)
        weights.append(weight)
        names.append(name)

    df.weight = weights
    df.name = names
    df.to_excel('estimated_weights.xlsx', index=False)
        
