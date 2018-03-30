#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function
from math import sin, radians, degrees, atan2, copysign, sqrt
from colorsys import hsv_to_rgb
from itertools import combinations
from tempfile import TemporaryFile as temp

import numpy as np
from networkx import Graph, connected_components
#from IPython import embed

def calc_sphere(x, y, z):
    """Calculate spherical coordinates for axial data."""
    return np.degrees(np.arctan2(*(np.array((x,y))*np.sign(z)))) % 360, np.degrees(np.arccos(np.abs(z)))

def general_axis(data, order=0):
    """Calculates the Nth eigenvector dataset tensor, first one by default."""
    direction_tensor = np.cov(data.T[:3, :])
    # print direction_tensor
    eigen_values, eigen_vectors = np.linalg.eigh(direction_tensor, UPLO='U')
    eigen_values_order = eigen_values.argsort()[::-1]
    cone_axis = eigen_vectors[:,eigen_values_order[order]]
    return cone_axis/np.linalg.norm(cone_axis)

def calibrate_azimuth(data, target_color, target_azimuth):
    calibrate_data = np.mean(data[target_color], axis=0)
    d_az = target_azimuth - calibrate_data[0]
    # print calibrate_data
    # print d_az
    for color in data.keys():
        data[color] = [((az + d_az) % 360, dip) for az, dip in data[color]]
    return data

# def load_ply(f):
    # f = open(fname, "rb")
    # line = ""
    # while "end_header" not in line:
        # line = f.readline()
        # if line.startswith("element vertex"): vertex_n = int(line.split()[-1])
        # if line.startswith("element face"): face_n = int(line.split()[-1])
    # data = np.fromfile(f, dtype=[("position", np.float32, 3),("normal", np.float32, 3),("color", np.uint8, 4),],count=vertex_n)
    # faces = np.fromfile(f, dtype=[("face_n", np.uint8, 1), ("indices", np.int32, 3),], count=face_n)
    # return data, faces
    
def load_ply(f):
    properties = vertex_properties = []
    face_properties = []
    line = b""
    while b"end_header" not in line:
        line = f.readline()
        if line.startswith(b"element vertex"): vertex_n = int(line.split()[-1])
        if line.startswith(b"element face"):
            face_n = int(line.split()[-1])
            properties = face_properties
        if line.startswith(b"property"): properties.append(line.split()[-1].strip())
    vertex_dtype = [("position", np.float32, 3),]
    vertex_dtype += [("normal", np.float32, 3),] if "nx" in vertex_properties else []
    vertex_dtype += [("color", np.uint8, 4),] if "alpha" in vertex_properties else [("color", np.uint8, 3),]
    faces_dtype = [("face_n", np.uint8, 1), ("indices", np.int32, 3),]
    faces_dtype += [("color", np.uint8, 4),] if "alpha" in face_properties else [("color", np.uint8, 3),] if "red" in face_properties else []
    vertices = np.fromfile(f, dtype=vertex_dtype,count=vertex_n)
    faces = np.fromfile(f, dtype=faces_dtype, count=face_n)
    return vertices, faces
        
def extract_colored_faces(fname, colors):
    output = {color:[] for color in colors}
    vertices, faces = load_ply(fname)
    
    for color in colors:
        colored_vertices_indices = np.nonzero((vertices['color'] == color).all(axis=1))[0]
        colored_faces = np.nonzero(np.all((np.in1d(faces["indices"][:,0], colored_vertices_indices),
                                           np.in1d(faces["indices"][:,1], colored_vertices_indices),
                                           np.in1d(faces["indices"][:,2], colored_vertices_indices)), axis=0))[0]

        colored_faces_graph = Graph()
        colored_faces_graph.add_edges_from(faces['indices'][colored_faces][:,:2])
        colored_faces_graph.add_edges_from(faces['indices'][colored_faces][:,1:])
        colored_faces_graph.add_edges_from(faces['indices'][colored_faces][:,(0,2)])
        
        planes_vertices_indices = list(connected_components(colored_faces_graph))
        print(len(planes_vertices_indices))
        for  plane_vertices_indices in planes_vertices_indices:
                colored_vertices = vertices["position"][list(plane_vertices_indices)]
                dipdir, dip = calc_sphere(*general_axis(colored_vertices, -1))
                X, Y, Z = colored_vertices.mean(axis=0)
                highest_vertex = colored_vertices[np.argmax(colored_vertices[:,2]),:]
                lowest_vertex = colored_vertices[np.argmin(colored_vertices[:,2]),:]
                trace = np.linalg.norm(highest_vertex - lowest_vertex)
                output[color].append((dipdir, dip, X, Y, Z, trace))
    return output
 
def extract_colored_point_clouds(fname, colors):
    output = {color:[] for color in colors}
    vertices, faces = load_ply(fname)
    for color in colors:
        colored_vertices_indices = np.nonzero((vertices['color'] == color).all(axis=1))[0]
        colored_vertices = vertices["position"][list(colored_vertices_indices)]
        dipdir, dip = calc_sphere(*general_axis(colored_vertices, -1))
        X, Y, Z = colored_vertices.mean(axis=0)
        highest_vertex = colored_vertices[np.argmax(colored_vertices[:,2]),:]
        lowest_vertex = colored_vertices[np.argmin(colored_vertices[:,2]),:]
        trace = np.linalg.norm(highest_vertex - lowest_vertex)
        output[color].append((dipdir, dip, X, Y, Z, trace))
    return output
 
def parse_ply(f, colors, eig=False):
    output = {color:[] for color in colors}
    # if not f.readline() == "ply": raise Exception("You must use a .ply (stanford format) file.")
    # if not "ascii" in f.readline(): raise Exception("You must use the ascii .ply specification.")
    header = f.readline()
    print(header)
    while header != "end_header\n": header = f.readline()
    for line in f:
        data = line.split()
        if len(data) < 10:
            break
        x, y, z,\
        nx, ny, nz,\
        r, g, b, alpha = data
        color = (r, g, b, alpha)
        normal = np.array((float(nx), float(ny), float(nz)))
        if color in colors:
            if eig:
                position = np.array((float(x), float(y), float(z)))
                output[color].append(position)
            else:
                normal = normal/np.linalg.norm(normal)
                output[color].append(calc_sphere(*normal))
            # embed()
        # line = f.readline()
    if eig:
        for color in colors:
            output[color] = (calc_sphere(*general_axis(np.array(output[color]), -1)),)
    return output





def color_encode_ply(f, f_out, value=0.7):
    output = {color:[] for color in colors}
    # if not f.readline() == "ply": raise Exception("You must use a .ply (stanford format) file.")
    # if not "ascii" in f.readline(): raise Exception("You must use the ascii .ply specification.")
    header = f.readline()
    #print header,
    f_out.write(header)
    while header != "end_header\n":
        header = f.readline()
        f_out.write(header)
        #print header,
    for line in f:
        data = line.split()
        print(data)
        if len(data) < 10:
            f_out.write(line)
            continue
        x, y, z,\
        nx, ny, nz,\
        r, g, b, alpha = data
        f_nx, f_ny, f_nz = float(nx), float(ny), float(nz)
        norm_n = sqrt(f_nx**2 + f_ny**2 + f_nz**2)
        if norm_n:
            sign_nz = copysign(1, f_nz)
            r, g, b = hsv_to_rgb((degrees(atan2(f_nx*sign_nz, f_ny*sign_nz)) % 360)/360., abs(f_nz/norm_n), value)
            r, g, b = int(r*255), int(g*255), int(b*255)

        f_out.write(" ".join((str(value) for value in (x, y, z,\
                               nx, ny, nz,\
                               r, g, b, alpha))) + "\n")



if __name__ == "__main__":
    from datetime import datetime
    starttime = datetime.now()
    from sys import argv
    from optparse import OptionParser, OptionGroup
    parser = OptionParser(usage="%prog -f input_filename [options] [color1 color2 ... colorN] [-o output_filename]", version="%prog 0.6")
    parser.add_option("-f", "--file", dest="infile", metavar="FILE", help="input painted 3d model")
    parser.add_option("-o", "--outfile", dest="outfile", metavar="FILE", help="output color coded 3d model, for use with --colorencode")
    parser.add_option("-c", "--colorencode", action="store_true", dest="colorencode", help="Process the model and paints it according to the attitude of each face, based on Assali 2013.", default=False)
    parser.add_option("-j", "--join", action="store_true", dest="join", default=False, help="joins all resultant data in a single file, instead of a file for each color as default. Recomended if using --eigen option.")
    parser.add_option("-n", "--network", action="store_true", dest="network", help="Outputs each different colored plane, through graph analysis.", default=False)
    parser.add_option("-p", "--pointcloud", action="store_true", dest="pointcloud", help="output the plane parameters of the point cloud of each color.", default=False)
    # parser.add_option("-v", "--verbose", action="store_true", dest="verbose", help="outputs detailed information on the data", default=False)
    group = OptionGroup(parser, "Calibration Options", "These are small utilities to aid calibration of your data.")
    group.add_option("-e", "--eigen", action="store_true", dest="eig", help="outputs only the third eigenvector of each color points.", default=False)
    group.add_option("-a", "--azimuth", action="store", dest="calibration_data", metavar="COLOR:AZIMUTH", default=None, help="calibrates your output data by turning its azimuth horizontaly until the given color has the given dipdirection")
    group.add_option("-u", "--value", action="store", dest="value", help="Determines the value used for the color encode option. Defaults to 0.90.", default=.9)
    parser.add_option_group(group)
    (options, args) = parser.parse_args()

    colors = []
    if not options.colorencode:
        for color in args:
            components = tuple(color.split(','))
            if len(components) < 4: components += ('255',)
            colors.append(tuple([int(component) for component in components]))
        filename = options.infile.split()[0]
        with open(options.infile, 'rb') as f:
            if options.pointcloud: output = extract_colored_point_clouds(f, colors)
            else: output = extract_colored_faces(f, colors)#, options.eig, options.network)
            if options.calibration_data:
                color, az = options.calibration_data.split(":")
                components = tuple(color.split(','))
                if len(components) < 4: components += ('255',)
                color = components
                az = int(az)
                # embed()
                output = calibrate_azimuth(output, color, az)
            #print output
        if not options.join:
            for color in output.keys():
                with open("{0}_{1}.txt".format(filename, color), 'w') as f, open("{0}_{1}_coords.txt".format(filename, color), 'w') as coordf:
                    coordf.write("X\tY\tZ\tatti\ttrace\n")
                    for dipdir, dip, X, Y, Z, trace in output[color]:
                        f.write("{0}\t{1}\n".format(dipdir, dip))
                        coordf.write("{0}\t{1}\t{2}\t{3}/{4}\t{5}\n".format(X, Y, Z, int(dipdir), int(dip), trace))
                    #np.savetxt(f,  output[color], delimiter="\t",header="dipdir\tdip\tX\tY\tZ")
        else:
            with open("{0}_attitudes.txt".format(filename), 'w') as f:
                for color in output.keys():
                    f.write("#{0}\n".format(color))
                    for dipdir, dip in output[color]:
                        f.write("{0}\t{1}\n".format(dipdir, dip))
    else:
        with open(options.infile, 'r') as f, open(options.outfile, 'wb') as fo:
            color_encode_ply(f, fo, value=float(options.value))
    print("Total time processing ", datetime.now() - starttime,"...")
    print("\a")