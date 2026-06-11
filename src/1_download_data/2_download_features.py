import ee
import requests
import numpy as np
import geopandas as gpd

from time import sleep
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ee.Authenticate()
ee.Initialize(project="ee-tiagogoncalves")

def get_download_url(xmin, ymin, xmax, ymax, year):
    geometry = ee.Geometry.Rectangle([[xmin, ymin], [xmax, ymax]], proj='EPSG:3857')

    s_date = ee.Date.fromYMD(year, 1, 1)
    e_date = s_date.advance(1, 'year')
                
    collection = ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL")
    
    image = collection.filterBounds(geometry).filterDate(s_date, e_date).first()
    
    return image.getDownloadURL({
        'scale': 10,
        'region': geometry,
        'format': 'GEO_TIFF'
    })

def download_tile(output_dir, url):
    response = requests.get(url)

    if response.status_code == 200:
        with open(output_dir, "wb") as f:
            f.write(response.content)
    else:
        raise Exception(f'status_code {response.status_code}')


def batch_process(file_batch: list[str]):
    for gpkg_file in file_batch:
        gdf = gpd.read_file(gpkg_file)

        xmin, ymin, xmax, ymax = gdf.total_bounds

        for source in ['google', 'bing']:
            year = gdf.iloc[0][f'{source}_year']

            if np.isnan(year):
                continue
            else:
                year = int(year)

            if year < 2017 or year > 2024:
                continue

            for attempt in range(3):
                try:
                    url = get_download_url(xmin, ymin, xmax, ymax, year)

                    download_tile(output_dir / source / f'{gpkg_file.stem}.tif', url)

                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"    ❌ Erro ao baixar a imagem: {e}. Unable to complete successfully")

                    print(f"    ❌ Erro ao baixar a imagem: {e}. Tentando novamente...")
                    sleep(2**attempt)


input_dir = Path("../../data/raw")
output_dir = Path("../../data/feature")

output_dir.mkdir(exist_ok=True)
(output_dir / 'bing').mkdir(exist_ok=True)
(output_dir / 'google').mkdir(exist_ok=True)

gpkg_files = list(input_dir.glob("*.gpkg"))

MAX_WORKERS = 10

k, m = divmod(len(gpkg_files), MAX_WORKERS)
file_batches = [gpkg_files[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(MAX_WORKERS)]

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = [executor.submit(batch_process, file_batch) for file_batch in file_batches]
    for _ in as_completed(futures):
        pass