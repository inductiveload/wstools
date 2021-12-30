import urllib.request
import tqdm

URL = "https://archive.org/download/clevelandart-1916.1044-gardener-s-house-at/1916.1044_full.tif"


req = urllib.request.Request(URL, method='HEAD')

f = urllib.request.urlopen(req)

size = int(f.headers['Content-Length'])
print(size)

chunk_size = 25 * 1024 * 1024

file = open('foo.tif', 'wb')

written = 0

with tqdm.tqdm(
        desc="IA ↓",
        total=size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024) as progress:

    while written < size:

        start = written
        end = min(written + chunk_size, size)

        req = urllib.request.Request(
            URL,
            headers={'Range': f'bytes={start}-{end - 1}'}
        )

        print(req.headers)

        g = urllib.request.urlopen(req)
        file.write(g.read())

        transferred = end - start
        progress.update(transferred)
        written += transferred

file.close()
