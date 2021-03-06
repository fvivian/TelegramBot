

import numpy as np
from pyproj import Proj, transform
import matplotlib
matplotlib.use('Agg')
from mpl_toolkits.basemap import Basemap
import matplotlib.pyplot as plt
import io
import json
import requests
from urllib.parse import urlencode
from rasterio.io import MemoryFile
import logging

logger = logging.getLogger(__name__)

# import all the necessary tokens/IDs:
with open('configFips.cfg') as f:
    tokens = json.loads(f.read())


def generate_browser_url(sat, lon, lat, date, no2=False):
    if sat == 'S1':
        instrument = 'Sentinel-1%20GRD%20IW'
        layer = '1_VV_ORTHORECTIFIED'
    elif sat == 'S2':
        instrument = 'Sentinel-2%20L1C'
        layer = '1_TRUE_COLOR'
    elif sat == 'S3':
        instrument = 'Sentinel-3%20OLCI'
        layer = '1_TRUE_COLOR'
    elif sat == 'S5P':
        instrument = 'Sentinel-5P%20NO2' if no2 else 'Sentinel-5P%20CO'
        layer = 'NO2_VISUALIZED' if no2 else 'CO_VISUALIZED'

    url = f'http://apps.sentinel-hub.com/eo-browser/?lat={lat}&' \
          f'lng={lon}&zoom=9&time={date}&' \
          f'preset={layer}&datasource={instrument}'

    return url


def get_bounding_box(lon, lat, xdim, ydim, reso):
    inProj = Proj(init='epsg:4326')
    outProj = Proj(init='epsg:3857')

    xC, yC = transform(inProj, outProj, lon, lat)
    width = xdim
    height = ydim
    xmin = xC - width * reso / 2
    xmax = xC + width * reso / 2
    ymin = yC - height * reso / 2
    ymax = yC + height * reso / 2

    return(xmin, ymin, xmax, ymax)

def create_wms_image_url(sat, lon, lat, time, gas=None):
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, 1280, 720, reso=60)

    params = {'service': 'WMS',
              'request': 'GetMap',
              'layers': '',
              'styles': '',
              'format': 'image/jpeg',
              'version': '1.1.1',
              'showlogo': 'false',
              'height': 720,
              'width': 1280,
              'srs': 'EPSG%3A3857',
              'time': f'{time}/{time}',
              'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}
    if sat == 'S1':
        ID = tokens['wms_token']['sentinel1']
        URL = 'http://services.sentinel-hub.com/ogc/wms/' + ID
        params['layers'] = 'S1-VV-ORTHORECTIFIED'
    if sat == 'S2':
        ID = tokens['wms_token']['sentinel2']
        URL = 'http://services.sentinel-hub.com/ogc/wms/' + ID
        params['layers'] = 'S2-TRUE-COLOR'
        params['maxcc'] = 5
    if sat == 'S3':
        ID = tokens['wms_token']['sentinel3']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/' + ID
        params['layers'] = 'S3_TRUE_COLOR'
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, 1280, 720, reso=5e2)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
    if sat == 'S5P':
        ID = tokens['wms_token']['sentinel5p']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/'+ ID
        params['layers'] = f'S5P_{gas}'
        params['format'] = 'image/tiff'
        params['time'] = ''
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, 1280, 720, reso=2e3)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
        
    url = f'{URL}?{urlencode(params)}'
    
    return(url)
"""
def get_current_wms_image(sat, lon, lat):

    URL, params = create_parameters_getmap(sat, lon, lat)

    try:
        #with MemoryFile(r.content) as memfile:
        #    with memfile.open() as dataset:
        #        imgData = dataset.read(1)
        #return(imgData)
        r = requests.get(URL, {**params}, timeout=10)
        return(r.url)
    except requests.exceptions.RequestException as e:
        logger.exception(f'WMS server did not respond to GetMap request in time.')
        raise requests.exceptions.RequestsException('WMS server timed out')
    except Exception as e:
        logger.exception(f'Exception in get_current_wms_image')
        logger.info(f'URL that caused exception: {r.url}')
        raise
"""

def create_parameters_wfs(sat, lon, lat, gas=None):
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, 10, 10, reso=60)

    params = {'service': 'WFS',
              'request': 'GetFeature',
              'outputformat': 'application/json',
              'srs': 'EPSG%3A3857',
              'maxfeatures': '100',
              'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}
    if sat == 'S1':
        ID = tokens['wms_token']['sentinel1']
        URL = 'http://services.sentinel-hub.com/ogc/wfs/' + ID
        params['typenames'] = 'DSS3'
    if sat == 'S2':
        ID = tokens['wms_token']['sentinel2']
        URL = 'http://services.sentinel-hub.com/ogc/wfs/' + ID
        params['typenames'] = 'S2.TILE'
        params['maxcc'] = 5
    if sat == 'S3':
        ID = tokens['wms_token']['sentinel3']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wfs/' + ID
        params['typenames'] = 'S3.TILE'
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, 10, 10, reso=5e2)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
    if sat == 'S5P':
        ID = tokens['wms_token']['sentinel5p']
        URL = 'http://services.eocloud.sentinel-hub.com/v1/wfs/' + ID
        params['typenames'] = f'S5P_{gas}'
        xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, 10, 10, reso=2e3)
        params['bbox'] = f'{xmin}, {ymin}, {xmax}, {ymax}'
    return(URL, params)

def get_image_date(sat, lon, lat, gas=None):
    url, params = create_parameters_wfs(sat, lon, lat)
    URL = f'{url}?{urlencode(params)}'

    try:
        r = requests.get(URL, timeout=20)
        js = json.loads(r.content)
        date = js['features'][0]['properties']['date']
        time = js['features'][0]['properties']['time']
        timeshort = f'{time.split(":")[0]}{time.split(":")[1]}{time.split(":")[2]}'
        return(date, timeshort)
    except requests.exceptions.RequestException as e:
        logger.exception(f'WFS server did not respond to GetFeature request in time. URL: {URL}')
        raise 
    except Exception as e:
        logger.exception(f'Exception in get_image_date, url that caused exception: {r.url}')
        raise

def get_current_S5P_image(lon, lat, gas):

    URL = create_wms_image_url('S5P', lon, lat, '', gas=gas)

    r = requests.get(URL, timeout=20)
    try:
        with MemoryFile(r.content) as memfile:
            with memfile.open() as dataset:
                imgData = dataset.read(1)
    except requests.exceptions.RequestException as e:
        logger.exception(f'S5P WMS server did not respond to GetMap in time.')
        raise requests.exceptions.RequestsException('WMS server timed out')
    except Exception as e:
        logger.exception(f'Exception in get_current_S5P_image')
        logger.info(f'URL that caused exception: {r.url}')
        raise

    imgTiff = generate_s5p_image_from_data(imgData, lon, lat, gas)
    return imgTiff


def generate_s5p_image_from_data(data, lon, lat, layer):
    imgTiff = data * 1e4
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, 1280, 720, reso=2e3)
    inProj = Proj(init='epsg:4326')
    outProj = Proj(init='epsg:3857')

    photo = io.BytesIO()
    photo.name = 'image.png'
    lonmin, latmin = transform(outProj, inProj, xmin, ymin)
    lonmax, latmax = transform(outProj, inProj, xmax, ymax)
    m = Basemap(projection='merc',
                llcrnrlat=latmin,
                urcrnrlat=latmax,
                llcrnrlon=lonmin,
                urcrnrlon=lonmax,
                resolution='i')
    m.drawcoastlines()
    m.drawcountries()
    ny = imgTiff.shape[0]
    nx = imgTiff.shape[1]
    ma1 = np.ma.masked_values(imgTiff, 0, copy=False)
    ma = np.ma.masked_where(ma1 < 0, ma1, copy=False)
    lons, lats = m.makegrid(nx, ny)  # get lat/lons of ny by nx evenly space grid.
    x, y = m(lons, lats)  # compute map proj coordinates.
    cs = m.contourf(x, y, np.flip(ma, 0), cmap=plt.cm.jet)
    cbar = m.colorbar(cs, location='bottom', pad="5%")
    cbar.set_label(f'{layer}' + r' in $mol / cm^2$ ' + f'at lon = {"%.1f" % lon}, lat = {"%.1f" % lat}')
    plt.savefig(photo)
    photo.seek(0)
    plt.clf()
    return photo
