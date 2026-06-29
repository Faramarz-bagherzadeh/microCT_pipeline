import numpy as np
from skimage.measure import label, regionprops, euler_number, marching_cubes, mesh_surface_area


def por_den_vol(binary_image, resolution, pixel_density = 0.917):
    """
    Compute the porosity and density of a 3D binary image.
    
    Parameters:
        pixel_density = 0.917 g/cm³ (density of ice)
        binary_image (numpy.ndarray): 3D binary image where solid=1, void=0
        resolution (float): Voxel resolution in meters
    
    Returns:
        tuple: (porosity, density, sample_volume) where porosity is a float 
               between 0 and 1, density , and 
               sample_volume is in cubic centimeters.
"""
    # Calculate the total number of voxels
    total_voxels = binary_image.size
    
    # Calculate the number of solid voxels (where value is 1)
    solid_voxels = np.sum(binary_image)
    
    # Calculate porosity
    porosity = round(1 - (solid_voxels / total_voxels),3)
    
    # Calculate density (assuming density of solid material)
    density = round(solid_voxels * pixel_density / total_voxels,3)
    
    # Calculate sample volume in cubic centimeters
    voxel_volume_cm3 = (resolution * 100) ** 3  # Convert resolution from meters to centimeters
    sample_volume = round(total_voxels * voxel_volume_cm3, 3)

    return porosity, density, sample_volume


def euler_characteristic(binary_image, resolution):
    
    """Compute the Euler density (Euler characteristic per unit volume) of a 
    3D binary image.
    
    Parameters:
        binary_image (numpy.ndarray): 3D binary image where solid=1, void=0
        resolution (float): Voxel resolution in meters
        
    Returns:
        float: Euler density (Euler number per cm³)
    """
    pixel_volume_cm = (resolution*100) **3
    sample_volume_cm = binary_image.shape[0] * binary_image.shape[1] * binary_image.shape[2] * pixel_volume_cm
    euler_density = round(euler_number(binary_image, connectivity=1)/sample_volume_cm ,2)
    return euler_density


def specific_surface_area(binary_img, resolution):
    """
    Compute the specific surface area using marching cubes (skimage).
    
    Specific surface area = surface area of solid / total volume
    
    Parameters:
        binary_img (numpy.ndarray): 3D binary image where solid=1, void=0
        resolution (float): Voxel resolution in meters
        
    Returns:
        float: Specific surface area in m²/m³
    """
    # Use marching cubes to extract the surface of the solid phase
    verts, faces, normals, values = marching_cubes(
        binary_img.astype(float), 
        level=0.5, 
        spacing=(resolution, resolution, resolution)
    )
    
    # Compute surface area from the mesh
    surface_area = mesh_surface_area(verts, faces)
    
    # Total volume of the image
    total_volume = (binary_img.shape[0] * resolution) * \
                   (binary_img.shape[1] * resolution) * \
                   (binary_img.shape[2] * resolution)
    
    # Specific surface area
    specific_area = surface_area / total_volume
    
    return specific_area


def mean_intercept_length(binary_img, resolution):
    """
    Compute the mean intercept length (MIL) in the x, y, z directions 
    without using puma.
    
    MIL measures the mean length of solid-phase segments along lines 
    through the sample. It is computed by:
      1. Scanning along each axis direction
      2. Counting the number of solid intercepts (transitions from void 
         to solid) along each line
      3. MIL = total solid length in that direction / number of intercepts
    
    Parameters:
        binary_img (numpy.ndarray): 3D binary image where solid=1, void=0
        resolution (float): Voxel resolution in meters
        
    Returns:
        tuple: (MIL_x, MIL_y, MIL_z) in mm
    """
    img = binary_img.astype(bool)
    res_mm = resolution * 1000  # convert m to mm
    
    def compute_mil_along_axis(axis):
        """Compute MIL along a given axis (0=z, 1=y, 2=x)."""
        n_lines = np.prod([img.shape[i] for i in range(3) if i != axis])
        total_solid_length = 0.0
        total_intercepts = 0
        
        # Create a view that iterates over all lines along the given axis
        for indices in np.ndindex(*[img.shape[i] for i in range(3) if i != axis]):
            # Extract the line along the axis
            if axis == 0:  # z-axis
                line = img[indices[0], indices[1], :]
            elif axis == 1:  # y-axis
                line = img[indices[0], :, indices[1]]
            else:  # x-axis
                line = img[:, indices[0], indices[1]]
            
            # Find transitions from void (0/False) to solid (1/True)
            # pad with False at start to detect solid at beginning
            padded = np.concatenate([[False], line])
            solid_starts = padded[1:] & ~padded[:-1]
            intercept_count = np.sum(solid_starts)
            
            if intercept_count > 0:
                total_solid_length += np.sum(line)
                total_intercepts += intercept_count
        
        if total_intercepts == 0:
            return 0.0
        
        # MIL = total solid length (in pixels) * resolution / number of intercepts
        return (total_solid_length / total_intercepts) * res_mm
    
    mil_x = compute_mil_along_axis(2)  # axis 2 = x
    mil_y = compute_mil_along_axis(1)  # axis 1 = y
    mil_z = compute_mil_along_axis(0)  # axis 0 = z
    
    return (round(mil_x, 3), round(mil_y, 3), round(mil_z, 3))





def classify_pores(binary_image):
    """
    Classify pores in a 3D binary image into three groups:
    
    Group 1: Pores with a bounding box dimension >= the first dimension of the image.
    Group 2: Pores connected to a face of the image but not in Group 1.
    Group 3: Pores totally isolated.
    
    Parameters:
        binary_image (numpy.ndarray): A 3D binary image where solid is 1 and pore is 0.

    Returns:
        dict: A dictionary with group keys and corresponding pixel sums.
    """
    # Label connected components in the pore space (binary 0)
    inverted_image = np.logical_not(binary_image)  # Invert the binary image (1 -> 0, 0 -> 1)
    labeled_image, num_features = label(inverted_image, connectivity=3, return_num=True)

    group_1_sum = 0
    group_2_sum = 0
    group_3_sum = 0
    volume = binary_image.shape[0] * binary_image.shape[1] * binary_image.shape[2] 
    image_shape = binary_image.shape

    # Identify pores in each group
    for region in regionprops(labeled_image):
        bbox = region.bbox
        bbox_size = [bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2]]  # 3D bounding box sizes

        # Group 1: Bounding box size >= first dimension of the image
        if any(dim >= image_shape[0] for dim in bbox_size):
            group_1_sum += region.area
        
        else:
            # Determine if the region touches any face of the image
            min_z, min_y, min_x, max_z, max_y, max_x = bbox
            touches_face = (
                min_z == 0 or min_y == 0 or min_x == 0 or
                max_z == image_shape[0] or
                max_y == image_shape[1] or
                max_x == image_shape[2]
            )

            if touches_face:
                # Group 2: Touches a face but not in Group 1
                group_2_sum += region.area
            else:
                # Group 3: Completely isolated
                group_3_sum += region.area

    return round(100*group_1_sum/volume ,3), round(100*group_2_sum/volume ,3) , round(100*group_3_sum/volume ,3)


    






