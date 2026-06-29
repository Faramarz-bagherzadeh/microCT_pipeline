import numpy as np
import openpnm as op
import porespy as ps
from collections import Counter
from scipy import ndimage as ndi
from tqdm import tqdm

np.set_printoptions(precision=4)
np.random.seed(10)

def determine_inlet_outlet(img,pn,resolution , p1,p2):
        # Get pore coordinates
    pore_coords = pn["pore.coords"]
    l = img.shape[0] * resolution
    es = 0.1*img.shape[0] * resolution # estimated distance from surface to the pore
    if p1 == 'zmin' or p2 == 'zmin':
        inlet_pores = np.where(pore_coords[:, 2] < es)  # Pores at zmin
        outlet_pores = np.where(pore_coords[:, 2] > l - es) # Pores at zmax
    elif p1== 'ymin' or p2== 'ymin':
        inlet_pores = np.where(pore_coords[:, 1] < es)  # Pores at ymin
        outlet_pores = np.where(pore_coords[:, 1] > l - es) # Pores at ymax
    elif p1 == 'xmin' or p2 == 'xmin' :
        inlet_pores = np.where(pore_coords[:, 0] < es)  # Pores at xmin
        outlet_pores = np.where(pore_coords[:, 0] > l - es) # Pores at xmax
    else:
        print ('P1 and P2 Error!!!!')

    #print('inlet= ',inlet_pores,'outlet = ', outlet_pores)
    return inlet_pores, outlet_pores


def complementbin(binimg):
    complement=binimg.astype(int)
    complement[complement==0]=2
    complement[complement==1]=0
    complement[complement==2]=1
    return complement



def spherical_ice_cluster(img):
    '''spherical ice cluster size is a volume-weighted mean of
    the maximum sphere that can be placed into the structure.'''
    volumepix = img.shape[0]*img.shape[1]*img.shape[2]
    img = img.astype(bool)
    D = ndi.distance_transform_edt(img)
    distancelist =  np.arange(0, 20, 0.5).tolist()

    icefractionlist=[]
    iceerosionlist=[]
    for distance in tqdm(distancelist, desc="Processing Distances", unit="step"):
        D3=D>distance
        n3 = (len(D3 [D3>0]))/volumepix
        iceerosionlist.append(n3)
        #print("Ice fraction before dilation: "+str(n3)+" for distance: "+str(distance))
        D3comp=complementbin(D3)
        Ddistance = ndi.distance_transform_edt(D3comp)
        D4=Ddistance>distance
        n4 = (volumepix -len(D4 [D4>0]))/volumepix
        icefractionlist.append(n4)
        #print("Ice fraction after dilation: "+str(n4)+" for distance: "+str(distance))

    meanthickness=0
    for i in range(0,len(distancelist)-1):
        if iceerosionlist[i+1]!=0:
            #print(distancelist[i+1])
            meanthickness+=(icefractionlist[i]-icefractionlist[i+1])/(icefractionlist[0])*2*distancelist[i+1]
    print("Cluster thickness diameter in PIX: "+str(meanthickness))

    return meanthickness




def skeleton_metrics(img, resolution):
    '''Properties of the skeleton created by Porespy'''
    results = {}

    snow = ps.networks.snow2(img, voxel_size= resolution)
    pn = op.io.network_from_porespy(snow.network)
    pn.add_model(propname='pore.cluster_number',
                 model=op.models.network.cluster_number)
    pn.add_model(propname='pore.cluster_size',
                 model=op.models.network.cluster_size)

    results['num_pores'] = snow.network['pore.all'].shape[0]
    results['num_throats'] = snow.network['throat.all'].shape[0]
    results['coordination_number'] = round( (2 * results['num_throats']) / (results['num_pores']) , 2)
    results['avg_pore_volume']= snow.network['pore.region_volume'].mean()
    results['avg_pore_diameter'] = snow.network['pore.equivalent_diameter'].mean()
    results['avg_throat_diameter'] = snow.network['throat.inscribed_diameter'].mean()
    results['avg_throat_length'] = snow.network['throat.total_length'].mean()

    connection_counts = list(Counter(snow.network['throat.conns'].flatten()).values())
    results['max_connections'] = max(connection_counts)
    results['median_connections'] = np.median(connection_counts)


    results['num_cluster'] = len(np.unique(pn['pore.cluster_number']))
    results['max_cluster_size'] = pn['pore.cluster_size'].max()
    results['avg_cluster_size'] = round(np.unique(pn['pore.cluster_size']).mean())
    
    results['avg_pore_surface_area'] = snow.network['pore.surface_area'].mean()
    results['avg_throat_area'] = snow.network['throat.cross_sectional_area'].mean()
    results['std_coordination_number'] = round(np.std(connection_counts),2)

    return results



def calculate_permeability(img, resolution,p1,p2):
    filled =ps.filters.fill_closed_pores(img,surface=False)
    thickness = 2
    if p1 == 'zmin':
        filled [:, :, :thickness] = True  # Front face
    elif p1== 'ymin':
        filled [:, :thickness, :] = True  # Front face
    elif p1 == 'xmin' :
        filled [:thickness, :, :] = True  # Front face
    else:
        print ('Cluster Connector plance not found ERROR!!!!')

    snow = ps.networks.snow2(filled, voxel_size= resolution)
    pn = op.io.network_from_porespy(snow.network)

    # Something related to the recent update of the library (ignore it)
    pn['pore.diameter'] = pn['pore.equivalent_diameter']
    pn['throat.diameter'] = pn['throat.inscribed_diameter']
    pn['throat.spacing'] = pn['throat.total_length']

    # Adding model
    pn.add_model(propname='throat.hydraulic_size_factors',
                 model=op.models.geometry.hydraulic_size_factors.pyramids_and_cuboids)
    pn.add_model(propname='throat.diffusive_size_factors',
                 model=op.models.geometry.diffusive_size_factors.pyramids_and_cuboids)
    pn.regenerate_models()

    #Health check
    h = op.utils.check_network_health(pn)
    op.topotools.trim(network=pn, pores=h['disconnected_pores'])
    h = op.utils.check_network_health(pn)

    # p1 , p2 should be from pn labels, use print(pn) to check labels
    phase = op.phase.Phase(network=pn)
    phase['pore.viscosity']=1.0
    phase.add_model_collection(op.models.collections.physics.basic)
    phase.regenerate_models()

    def compute_k(pn, p1,p2):
        inlet, outlet = determine_inlet_outlet(img,pn,resolution,p1,p2)
        flow = op.algorithms.StokesFlow(network=pn, phase=phase)
        flow.set_value_BC(pores=inlet, values=1)
        flow.set_value_BC(pores=outlet, values=0)
        flow.run()
        phase.update(flow.soln)
        Q = flow.rate(pores=inlet, mode='group')[0]
        A = (img.shape[1] * img.shape[2])*(resolution**2) #A = op.topotools.get_domain_area(pn, inlets=inlet, outlets=outlet)
        L = img.shape[0]*resolution #L = op.topotools.get_domain_length(pn, inlets=inlet, outlets=outlet)
        k = Q * L / A # K = Q * L * mu / (A * Delta_P) # mu and Delta_P were assumed to be 1.
        return k

    #compute permeability on different directions
    k = compute_k(pn,p1,p2)

    return k


def calculate_tortuosity(img, resolution,p1,p2):
    filled =ps.filters.fill_closed_pores(img,surface=False)
    thickness = 2
    if p1 == 'zmin':
        filled [:, :, :thickness] = True  # Front face
    elif p1== 'ymin':
        filled [:, :thickness, :] = True  # Front face
    elif p1 == 'xmin' :
        filled [:thickness, :, :] = True  # Front face
    else:
        print ('Cluster Connector plance not found ERROR!!!!')

    snow = ps.networks.snow2(filled, voxel_size= resolution, r_max=8, sigma=0)

    pn = op.io.network_from_porespy(snow.network)

    # Something related to the recent update of the library (ignore it)
    pn['pore.diameter'] = pn['pore.equivalent_diameter']
    pn['throat.diameter'] = pn['throat.inscribed_diameter']
    pn['throat.spacing'] = pn['throat.total_length']


    #Health check
    h = op.utils.check_network_health(pn)
    op.topotools.trim(network=pn, pores=h['disconnected_pores'])
    h = op.utils.check_network_health(pn)


    air = op.phase.Air(network=pn)

    def simple_diffusive_conductance(phase):
        ''' This function generates diffusivity values
        used for Ficks Simuation '''

        net = phase.network
        A = net['throat.cross_sectional_area']
        L = net['throat.total_length']
        conns = net['throat.conns']
        D = phase['pore.diffusivity'][conns].mean(axis=1)
        return D * A / L

    # Add model to phase
    air.add_model(
        propname='throat.diffusive_conductance',
        model=simple_diffusive_conductance
    )
    air.regenerate_models()

    phys = op.models.collections.physics.basic
    #del phys['throat.entry_pressure']
    air.add_model_collection(phys)
    air.regenerate_models()

    fd = op.algorithms.FickianDiffusion(network=pn, phase=air)


    def compute_tau(img,pn, p1,p2):

        inlet, outlet = determine_inlet_outlet(img,pn,resolution,p1,p2)
        C_in, C_out = [10, 5]
        fd.set_value_BC(pores=inlet, values=C_in)
        fd.set_value_BC(pores=outlet, values=C_out)

        fd.run()
        rate_inlet = fd.rate(pores=inlet)[0]
        #print(f'Molar flow rate: {rate_inlet:.5e} mol/s')

        A = (img.shape[1] * img.shape[2])*(resolution**2)
        L = img.shape[0]*resolution
        D_eff = rate_inlet * L / (A * (C_in - C_out))
        #print("{0:.6E}".format(D_eff))

        e = len(img[img == True])/np.prod(img.shape)
        #print('The porosity is: ',e)

        D_AB = air['pore.diffusivity'][0]
        tau = e * D_AB / D_eff
        print('The tortuosity is:', tau)

        #plot_network(img, pn, p1, p2, inlet, outlet)


        return tau

    #compute permeability on different directions
    tau = compute_tau(img,pn,p1,p2)
    
    return tau
