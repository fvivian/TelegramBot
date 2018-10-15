

import numpy as np
from pyproj import Proj, transform
import matplotlib
from mpl_toolkits.basemap import Basemap
import matplotlib.pyplot as plt
import io
import json
import requests
from rasterio.io import MemoryFile
import logging

matplotlib.use('Agg')
logger = logging.getLogger(__name__)

# import all the necessary tokens/IDs:
with open('configFips.cfg') as f:
    tokens = json.loads(f.read())


def generate_browser_url(sat, date, lon, lat, no2=False):
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
        date = ''

    url = f'http://apps.sentinel-hub.com/eo-browser/#lat={lat}&' \
          f'lng={lon}&zoom=10&datasource={instrument}&' \
          f'time={date}&preset={layer}'

    return url


def get_bounding_box(lon, lat, reso):
    inProj = Proj(init='epsg:4326')
    outProj = Proj(init='epsg:3857')

    xC, yC = transform(inProj, outProj, lon, lat)
    width = 980
    height = 540
    xmin = xC - width * reso / 2
    xmax = xC + width * reso / 2
    ymin = yC - height * reso / 2
    ymax = yC + height * reso / 2

    return(xmin, ymin, xmax, ymax)


def get_current_wms_image(sat, lon, lat):
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=60)

    params = {'service': 'WMS',
              'request': 'GetMap',
              'layers': '',
              'styles': '',
              'format': 'image/tiff',
              'version': '1.1.1',
              'showlogo': 'false',
              'height': 720,
              'width': 1280,
              'srs': 'EPSG%3A3857',
              'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}
    if sat == 'S1':
        ID = tokens['wms_token']['sentinel1']
        params['layers'] = 'S1_VV_ORTHORECTIFIED'
    if sat == 'S2':
        ID = tokens['wms_token']['sentinel2']
        params['layers'] = 'S2_TRUE_COLOR'
    if sat == 'S3':
        ID = tokens['wms_token']['sentinel3']
        params['layers'] = 'S3_TRUE_COLOR'

    URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/' + ID

    r = requests.get(URL, {**params}, timeout=10)
    with MemoryFile(r.content) as memfile:
        with memfile.open() as dataset:
            imgData = dataset.read(1)
    return(imgData)


def request_S5P_image(lon, lat, gas):
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=2e3)

    ID = tokens['wms_token']['sentinel5p']
    URL = 'http://services.eocloud.sentinel-hub.com/v1/wms/' + ID
    params = {'service': 'WMS',
              'request': 'GetMap',
              'layers': f'S5P_{gas}',
              'styles': '',
              'format': 'image/tiff',
              'version': '1.1.1',
              'showlogo': 'false',
              'height': 540,
              'width': 980,
              'srs': 'EPSG%3A3857',
              'bbox': f'{xmin}, {ymin}, {xmax}, {ymax}'}

    r = requests.get(URL, {**params}, timeout=10)
    with MemoryFile(r.content) as memfile:
        with memfile.open() as dataset:
            imgData = dataset.read(1)

    imgTiff = generate_s5p_image_from_data(imgData, lon, lat, params['layers'])
    return imgTiff


def generate_s5p_image_from_data(data, lon, lat, layer):
    imgTiff = data * 1e4
    xmin, ymin, xmax, ymax = get_bounding_box(lon, lat, reso=2e3)
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

    return photo
