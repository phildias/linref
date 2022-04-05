# -*- coding: utf-8 -*-
"""
Created on Sat Apr  2 17:09:32 2022

@author: Phil
"""

import pandas as pd
import geopandas as gpd
import linref as lr
from shapely.geometry import LineString

# Setting up fake data for the examples. 
roads_rows = [{'ID':1,
               'ROUTE_ID':'A',
               'FRM_DFO':0,
               'TO_DFO':100,
               'geometry':LineString([(0,0),
                                      (0,10),
                                      (10,10),
                                      (20,0)])},
              {'ID':2,
               'ROUTE_ID':'A',
               'FRM_DFO':100,
               'TO_DFO':150,
               'geometry':LineString([(20,0),
                                      (20,10),
                                      (20,20),
                                      (20,30)])},
              {'ID':3,
               'ROUTE_ID':'A',
               'FRM_DFO':200,
               'TO_DFO':250,
               'geometry':LineString([(30,30),
                                      (30,35),
                                      (35,35),
                                      (40,25)])},
              {'ID':4,
               'ROUTE_ID':'B',
               'FRM_DFO':50,
               'TO_DFO':100,
               'geometry':LineString([(-5,-5),
                                      (-10,10),
                                      (0,-5),
                                      (5,10)])},
              ]

roads_gdf = gpd.GeoDataFrame(data=roads_rows, 
                             geometry='geometry',
                             crs='epsg:4326')


points_rows = [{'ID':10,
                'ROUTE_ID':'A',
                'DFO':25,
                'WKB':'01010000000000000000000000B0C2078031122140'},
               {'ID':11,
                'ROUTE_ID':'A',
                'DFO':55,
                'WKB':'01010000001C7977E66C8E21400000000000002440'},
               {'ID':12,
                'ROUTE_ID':'A',
                'DFO':123,
                'WKB':'010100000000000000000034409E99999999992B40'},
               {'ID':13,
                'ROUTE_ID':'A',
                'DFO':140,
                'WKB':'010100000000000000000034400200000000003840'},
               {'ID':14,
                'ROUTE_ID':'B',
                'DFO':66,
                'WKB':'0101000000E9D9CE7E31EA23C0DD46363E4ADF2340'},
               {'ID':15,
                'ROUTE_ID':'B',
                'DFO':77,
                'WKB':'0101000000503E0F01D42F0FC0E0755B06F81EEB3F'},
               {'ID':16,
                'ROUTE_ID':'B',
                'DFO':88,
                'WKB':'01010000006A8769E568B5F33FC069C34FC5DFF4BF'},
               {'ID':17,
                'ROUTE_ID':'B',
                'DFO':99,
                'WKB':'0101000000D232722F72BE12403A4C2B47AB1D2240'},
               ]

points_df = pd.DataFrame(data=points_rows)



lines_rows = [{'ID':21,
               'ROUTE_ID':'A',
               'FRM_DFO':50,
               'TO_DFO':65,
               'WKB':'010500000001000000010200000003000000C00A1F00C6481C400000'
                     '00000000244000000000000024400000000000002440D65528B3BA19'
                     '27402AAAD74C45E62040'},
              {'ID':22,
               'ROUTE_ID':'A',
               'FRM_DFO':140,
               'TO_DFO':160,
               'WKB':'01050000000100000001020000000200000000000000000034400200'
                     '00000000384000000000000034400000000000003E40'},
              {'ID':23,
               'ROUTE_ID':'B',
               'FRM_DFO':50,
               'TO_DFO':100,
               'WKB':'01050000000100000001020000000400000000000000000014C00000'
                     '0000000014C000000000000024C00000000000002440000000000000'
                     '000000000000000014C000000000000014400000000000002440'},
              ]

lines_df = pd.DataFrame(data=lines_rows)

###########################################
### From milepost/DFO to point geometry ###
###########################################

# Create an "EventsCollection" instance of the roads
roads_ec = lr.EventsCollection(roads_gdf, 
                               keys=['ROUTE_ID'], 
                               beg='FRM_DFO', 
                               end='TO_DFO')

# Actually "builds" the routes. In the background, linref looks at the geometry
# and the values in the "beg" and "end" columns and populates the associated 
# M-values with each road.
roads_ec.build_routes()

# Create an "EventsCollection" instance for the points. 
# Note that in this case, the "end" value is not needed. 
points_ec = lr.EventsCollection(points_df, keys=['ROUTE_ID'], beg='DFO') 

# Merge the two EventsCollection objects. This creates an EventsMerge instance 
# which has various methods for aggregating the merged data.
points_em = points_ec.merge(roads_ec) 

# Generate the new point geometries. 
new_points = points_em.interpolate()

# Store the final result in a GeoDataFrame. 
points_gdf = gpd.GeoDataFrame(data=points_df.copy(),
                              geometry=new_points, 
                              crs=roads_gdf.crs)

###########################################
### From point geometry to milepost/DFO ###
###########################################

# Create an "EventsCollection" instance of the roads
roads_ec = lr.EventsCollection(roads_gdf, 
                               keys=['ROUTE_ID'], 
                               beg='FRM_DFO', 
                               end='TO_DFO')

# Actually "builds" the routes. In the background, linref looks at the geometry
# and the values in the "beg" and "end" columns and populates the associated 
# M-values from each road.
roads_ec.build_routes()

# TODO: when going from point geom to DFO, the user should be able to indicate 
# which column to use as the route identifier. As it currently stands, 
# I think the algorithm forces you to pick the route which is nearest to the 
# point geometry.
# points_gdf must have point geometry
points_gdf_with_dfo = roads_ec.project(points_gdf.drop(columns=['ROUTE_ID',
                                                                'DFO'])) 


##############################################
### From mileposts/DFOs to line geometries ###
##############################################

# Create an "EventsCollection" instance of the roads
roads_ec = lr.EventsCollection(roads_gdf, 
                               keys=['ROUTE_ID'], 
                               beg='FRM_DFO', 
                               end='TO_DFO')

# Actually "builds" the routes. In the background, linref looks at the geometry
# and the values in the "beg" and "end" columns and populates the associated 
# M-values with each road.
roads_ec.build_routes()

# Create an "EventsCollection" instance for the lines
lines_ec = lr.EventsCollection(lines_df, 
                               keys=['ROUTE_ID'], 
                               beg='FRM_DFO', 
                               end='TO_DFO')

# Merge the two EventsCollection. This creates an EventsMerge instance which 
# has various methods for aggregating the merged data
lines_em = lines_ec.merge(roads_ec) 

# Generate the new line geometries
new_lines = lines_em.cut()

# Store the final result in a GeoDataFrame
lines_gdf = gpd.GeoDataFrame(data=lines_df.copy(),
                             geometry=new_lines,
                             crs=roads_gdf.crs)


############################################
### From line geometry to mileposts/DFOs ###
############################################

# Create an "EventsCollection" instance of the roads
roads_ec = lr.EventsCollection(roads_gdf, 
                               keys=['ROUTE_ID'], 
                               beg='FRM_DFO', 
                               end='TO_DFO')

# Actually "builds" the routes. In the background, linref looks at the geometry
# and the values in the "beg" and "end" columns and populates the associated 
# M-values with each road.
roads_ec.build_routes()

# TODO: when going from line geom to DFOs, the user should be able to indicate 
# which column to use as the route identifier. As it currently stands, 
# I think the algorithm forces you to pick the route which is nearest to the 
# point geometry.
# lines_gdf must have line geometry
lines_gdf_with_dfo = roads_ec.project_parallel(lines_gdf.drop(columns=['ROUTE_ID',
                                                                       'FRM_DFO',
                                                                       'TO_DFO',
                                                                       'WKB'])) 


