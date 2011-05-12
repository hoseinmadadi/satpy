#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2011.

# SMHI,
# Folkborgsvägen 1,
# Norrköping, 
# Sweden

# Author(s):
 
#   Adam Dybbroe <adam.dybbroe@smhi.se>

# This file is part of mpop.

# mpop is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.

# mpop is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with
# mpop.  If not, see <http://www.gnu.org/licenses/>.

"""Plugin for reading AQUA MODIS level 2 EOS HDF files downloaded from NASA FTP import
"""

import os.path
from ConfigParser import ConfigParser

import datetime
import numpy as np
from pyhdf.SD import SD

from mpop import CONFIG_PATH
from mpop.satin.logger import LOG
import mpop.channel
#from mpop.projector import get_area_def

SCAN_LINE_ATTRS = ['year', 'day', 'msec', 
                   'slat', 'slon', 'clat', 'clon',
                   'elat', 'elon', 'csol_z'
                   ]

GEO_PHYS_PRODUCTS = ['aot_869', 'chlor_a', 
                     'poc', 'cdom_index', 'angstrom', 
                     'pic', 'par', 
                     'nflh', 'ipar', 'Kd_490']

CHANNELS = ['Rrs_412', 
            'Rrs_443', 
            'Rrs_469', 
            'Rrs_488', 
            'Rrs_531', 
            'Rrs_547', 
            'Rrs_555', 
            'Rrs_645', 
            'Rrs_667', 
            'Rrs_678'
            ]

# Flags and quality (the two latter only for SST products):
FLAGS_QUALITY = ['l2_flags', 'qual_sst', 'qual_sst4']

SENSOR_BAND_PARAMS = ['wavelength', 'F0', 'vcal_offset', 'vcal_gain', 
                      'Tau_r', 'k_oz']

# Navigation control points and tilt - no LONLAT:
NAVIGATION_TILT =  ['tilt', 'cntl_pt_cols', 'cntl_pt_rows']
# Geo-location - Longitude,latitude:
LONLAT = ['longitude', 'latitude']


class ModisEosHdfLevel2(mpop.channel.GenericChannel):
    """NASA EOS-HDF Modis data struct"""
    def __init__(self, prodname, resolution = None):
        mpop.channel.GenericChannel.__init__(self, prodname)
        self.filled = False
        self.name = prodname
        self.resolution = resolution

        self.info = {}
        self.shape = None

        self.scanline_attrs = {}
        self.data = {}
        self.starttime = None
        self.endtime = None
        self.satid = ""
        
    def __str__(self):
        return ("'%s: shape %s, resolution %sm'"%
                (self.name, 
                 self.shape, 
                 self.resolution))   

    def is_loaded(self):
        """Tells if the channel contains loaded data.
        """
        return self.filled

    def read(self, filename, **kwargs):
        """Read the data"""
        from pyhdf.SD import SD
        import datetime

        print "*** >>> Read the hdf-eos file!"
        root = SD(filename)
    
        # Get all the Attributes:
        # Common Attributes, Data Time,
        # Data Structure and Scene Coordinates
        for key in root.attributes().keys():
            self.info[key] = root.attributes()[key]

        #try:
        if 1:
            value = root.select(self.name)
            attr = value.attributes()
            data = value.get()

            band = data
            nodata = attr['bad_value_scaled']
            mask = np.equal(band, nodata)
            self.data[self.name] = np.ma.masked_where(mask, band) * \
                attr['slope'] + attr['intercept']
            
            value.endaccess()

        #except:
        #    pass

        root.end()
        self.filled = True


def load(satscene, *args, **kwargs):
    """Read data from file and load it into *satscene*.
    """    
    conf = ConfigParser()
    conf.read(os.path.join(CONFIG_PATH, satscene.fullname + ".cfg"))
    options = {}
    for option, value in conf.items(satscene.instrument_name+"-level3",
                                    raw = True):
        options[option] = value

    for prodname in satscene.channels_to_load:
        if prodname in GEO_PHYS_PRODUCTS:
            # Special loader for products:
            print "Call special product loader!"
            load_modis_lvl2_product(satscene, prodname, options)
                    
    CASES[satscene.instrument_name](satscene, options)


def load_modis_lvl2_product(satscene, prodname, options):
    """Read modis level2 products from file and load it into *satscene*.
    """
    pathname = os.path.join(options["dir"], options['filename'])    
    filename = satscene.time_slot.strftime(pathname)
    
    prod_chan = ModisEosHdfLevel2(prodname)
    prod_chan.read(filename)
    prod_chan.satid = satscene.satname.capitalize()
    prod_chan.resolution = 1000.0
    prod_chan.shape = prod_chan.data[prodname].data.shape

    #lat, lon = get_lat_lon(satscene, None)
    #from pyresample import geometry
    #satscene.area = geometry.SwathDefinition(lons=lon, lats=lat)
    #orbit = 99999

    satscene.channels.append(prod_chan)
            
    LOG.info("Loading modis lvl2 product done.")



def load_modis_lvl2(satscene, options):
    """Read modis level2 data from file and load it into *satscene*.
    """
    pathname = os.path.join(options["dir"], options['filename'])    
    filename = satscene.time_slot.strftime(pathname)
    
    print "FILE: ",filename
    eoshdf = SD(filename)

    # Get all the Attributes:
    # Common Attributes, Data Time,
    # Data Structure and Scene Coordinates
    info = {}
    for key in eoshdf.attributes().keys():
        info[key] = eoshdf.attributes()[key]

    datasets = CHANNELS
    
    scanline_attrs = {}
    data = {}

    dsets = eoshdf.datasets()
    selected_dsets = []
    for bandname in dsets.keys():            
        if datasets and bandname not in datasets and \
                (bandname not in SCAN_LINE_ATTRS and bandname not in LONLAT):
            continue

        if bandname not in satscene.channels_to_load:
            continue

        print "Dataset to load: ", bandname

        value = eoshdf.select(bandname)
        selected_dsets.append(value)

        # Get the Scan-Line Attributes:
        if bandname in SCAN_LINE_ATTRS:
            scanline_attrs[bandname] = {}
            scanline_attrs[bandname]['attr'] = value.attributes()
            scanline_attrs[bandname]['data'] = value.get()
        elif not datasets and bandname not in LONLAT:
            # Get all datasets
            data[bandname] = {}
            data[bandname]['attr'] = value.attributes()
            data[bandname]['data'] = value.get()
        elif bandname in datasets:
            # Get only the selected datasets
            data[bandname] = {}
            data[bandname]['attr'] = value.attributes()
            data[bandname]['data'] = value.get()

        if bandname in satscene.channels_to_load:
            band = data[bandname]['data']
            nodata = data[bandname]['attr']['bad_value_scaled']
            mask = np.equal(band, nodata)
            satscene[bandname] = np.ma.masked_where(mask, band) * \
                data[bandname]['attr']['slope'] + \
                data[bandname]['attr']['intercept']

    # Start Time - datetime object
    starttime = datetime.datetime.strptime(info['Start Time'][0:13], 
                                           "%Y%j%H%M%S")
    msec = float(info['Start Time'][13:16])/1000.
    starttime = starttime + datetime.timedelta(seconds=msec)
    
    # End Time - datetime object
    endtime = datetime.datetime.strptime(info['End Time'][0:13], 
                                         "%Y%j%H%M%S")
    msec = float(info['End Time'][13:16])/1000.
    endtime = endtime + datetime.timedelta(seconds=msec)
        
    #shape = data['longitude']['data'].shape
    #orbit = 99999

    lat, lon = get_lat_lon(satscene, None)

    from pyresample import geometry
    satscene.area = geometry.SwathDefinition(lons=lon, lats=lat)

    for dset in selected_dsets:
        dset.endaccess()
        
    eoshdf.end()

    LOG.info("Loading modis data done.")


def get_lonlat(satscene, row, col):
    """Estimate lon and lat.
    """
    estimate = False
    try:
        latitude, longitude = get_lat_lon(satscene, None)

        lon = longitude[row, col]
        lat = latitude[row, col]
        if longitude.mask[row, col] == False and latitude.mask[row, col] == False:
            estimate = False
    except TypeError:
        pass
    except IndexError:
        pass
    except IOError:
        estimate = True

    if not estimate:
        return lon, lat


def get_lat_lon(satscene, resolution):
    """Read lat and lon.
    """
    del resolution
    
    conf = ConfigParser()
    conf.read(os.path.join(CONFIG_PATH, satscene.fullname + ".cfg"))
    options = {}
    for option, value in conf.items(satscene.instrument_name+"-level3", 
                                    raw = True):
        options[option] = value
        
    return LAT_LON_CASES[satscene.instrument_name](satscene, options)

def get_lat_lon_modis_lvl2(satscene, options):
    """Read lat and lon.
    """
    pathname = os.path.join(options["dir"], options['filename'])    
    filename = satscene.time_slot.strftime(pathname)
    #print "lonlat - FILE: ",filename

    root = SD(filename)
    lon = root.select('longitude')
    longitude = lon.get()
    lat = root.select('latitude')
    latitude = lat.get()

    return latitude, longitude

# -----------------------------------------------------------------------

CASES = {
    "modis": load_modis_lvl2
    }

LAT_LON_CASES = {
    "modis": get_lat_lon_modis_lvl2
    }

