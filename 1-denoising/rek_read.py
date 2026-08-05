




import numpy as np
import struct

def read_rek_file(path):
    print ('path : ', path)
    pfile=open(path,"rb")
    header=pfile.read(2048)
    [imagewidth]= struct.unpack('h',header[0:2])  #f8 == d
    print("Image width: "+str(imagewidth))

    [imagehight]= struct.unpack('h',header[2:4])  #f8 == d
    print("Image hight: "+str(imagehight))

    [imagedepth]= struct.unpack('h',header[6:8])  #f8 == d
    print("Image depth: "+str(imagedepth))
    
    [resolution]= struct.unpack('f',header[584:588])  #f8 == d
    print("Pixel resolution: "+str(resolution))


    img = np.fromfile(pfile, dtype=np.uint8, count=imagedepth * imagehight * imagewidth)
    img = img.reshape((int(imagedepth),int(imagehight),int(imagewidth)))
    
    return img, round(resolution)




    
    
    
    
    
    
    
    
    
    
    
