
import os
import logging


class Cache():

    def __init__(self, directory):

        if not directory:
            raise ValueError(f'Cache directory error: {directory}')

        os.makedirs(directory, exist_ok=True)
        self.directory = directory

    def get_file(self, name):

        if not self.directory:
            return None

        name_in_cache = os.path.join(self.directory, name)

        logging.debug(f'Looking for {name_in_cache}')

        if (os.path.isfile(name_in_cache) and
                os.path.getsize(name_in_cache) > 0):
            return name_in_cache

        return None

    def cache_file(self, fo, name):

        if not self.directory:
            return None

        pos = fo.tell()
        fo.seek(0)

        name_in_cache = os.path.join(self.directory, name)

        with open(name_in_cache, 'wb') as cache_fo:
            cache_fo.write(fo.read())

        fo.seek(pos)
        return name_in_cache
