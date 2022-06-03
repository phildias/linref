# -*- coding: utf-8 -*-
"""
Created on Tue Apr  5 18:21:26 2022

@author: DIASF

TODO: Need to make sure the expected order of the coordinates is respected when 
creating the shapely geometries
"""



import os
import sys
import pathlib
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
import fiona
import pyproj

from osgeo import ogr, osr

ogr.UseExceptions()
osr.UseExceptions()

ls_no_m_wkt = 'LINESTRING (0 0, 0 10, 10 10, 20 0)'
ls_no_m_ogr = ogr.CreateGeometryFromWkt(ls_no_m_wkt)

mls_m_wkt = "MULTILINESTRING M((0 0 100, 1 0 200, 2 0 300),(3 0 400, 4 0 500))"
mls_m_ogr = ogr.CreateGeometryFromWkt(mls_m_wkt)

mls_zm_wkt = "MULTILINESTRING ZM((0 0 0 100, 1 0 0 200, 2 0 0 300),(3 0 0 400, 4 0 0 500))"
mls_zm_ogr = ogr.CreateGeometryFromWkt(mls_zm_wkt)

def extract_segment_m_values_from_ogr_geom(input_ogr_geom):
    segments = []
    is_3d = input_ogr_geom.Is3D()
    for j in range(input_ogr_geom.GetGeometryCount()):
        geom = input_ogr_geom.GetGeometryRef(j)
        geom_coords = []
        geom_m_values = []
        for i, point in enumerate(geom.GetPoints()):
            geom_coords.append(point)
            geom_m_values.append(geom.GetM(i))
        for start_c, end_c,start_m, end_m in zip(geom_coords[:-1],geom_coords[1:],
                                                 geom_m_values[:-1],geom_m_values[1:]):
            this_line = ogr.Geometry(ogr.wkbLineString)
            this_dict = {#'start_x':start_c[0],
                         #'start_y':start_c[1],
                         #'end_x':end_c[0],
                         #'end_y':end_c[1],
                         'start_m':start_m,
                         'end_m':end_m}
            if is_3d:
                this_line.AddPoint(*start_c)
                this_line.AddPoint(*end_c)
                #this_dict['start_z'] = start_c[2]
                #this_dict['end_z'] = end_c[2]
            else:
                this_line.AddPoint_2D(*start_c)
                this_line.AddPoint_2D(*end_c)
            this_dict['geom_wkb'] = this_line.ExportToWkb()
            segments.append(this_dict)
    
    segments_df = pd.DataFrame(segments)
    
    return segments_df

def extract_m_values_from_gdb_layer(gdb_path, layer_name):
    driver_name = "OpenFileGDB"

    driver = ogr.GetDriverByName(driver_name)
    data_source = driver.Open(gdb_path, 0)
    layer = data_source.GetLayerByName(layer_name)
    layer_definition = layer.GetLayerDefn()
    fid_colname = layer.GetFIDColumn()
    epsg_code = pyproj.CRS(layer.GetSpatialRef().ExportToWkt()).to_epsg()
    
    # Making sure the feature reader is reset
    layer.ResetReading()

    layer_rows = []
    # Iterating over every feature in the input layer
    for feature in layer:
        # Extracting the input feature's FID, geometry and WKT
        geom_fid = feature.GetFID()
        geom_ogr = feature.GetGeometryRef()
        #geom_wkt = geom_ogr.ExportToIsoWkt()
        
        feature_segments_df = extract_segment_m_values_from_ogr_geom(geom_ogr)
        
        feature_segments_df[fid_colname] = geom_fid
        
        # Iterating over the feature's columns
        for i in range(layer_definition.GetFieldCount()):
            field = layer_definition.GetFieldDefn(i)
            field_name =  field.GetName()
            #field_type_code = field.GetType()
            #field_type = field.GetFieldTypeName(field_type_code)
            #field_width = field.GetWidth()
            #field_precision = field.GetPrecision()
            
            field_value = feature.GetField(field_name)
            feature_segments_df[field_name] = field_value
            
            # Clearing the field
            field = None
        
        layer_rows.append(feature_segments_df.copy())
        
        # Clearing the input Feature
        feature = None
    
    # Releasing the input and output files
    data_source = None
    layer = None
    layer_definition = None

    final_layer_df = pd.concat(layer_rows, ignore_index=True)
    final_geoms = final_layer_df['geom_wkb'].apply(lambda x: shapely.wkb.loads(x))
    
    final_layer_gdf = gpd.GeoDataFrame(data=final_layer_df.copy(), 
                                       geometry=final_geoms,
                                       crs=f'epsg:{epsg_code}')
    
    return final_layer_gdf

segments_df = extract_segment_m_values_from_ogr_geom(mls_zm_ogr)

segments_df['geom_wkb'].apply(lambda x: shapely.wkb.loads(x))

gdb_path = (r"C:\Users\diasf\Jacobs\Austin Transportation Planning - General\D"
            r"ata\TxDOT_Roadway_Inventories\2020\2020_Roadway_Inventory.gdb")
layer_name = 'TxDOT_Roadway_Linework'

full_gdf = extract_m_values_from_gdb_layer(gdb_path, layer_name)

out_gpkg = ('c:/temp/m_values.gpkg')

full_gdf.drop(columns=['geom_wkb']).to_file(out_gpkg, layer='m_values', driver='GPKG')
full_gdf.to_pickle('c:/temp/m_values.pkl')

#full_gdf = pd.read_pickle("C:\Temp\m_values.pkl")
