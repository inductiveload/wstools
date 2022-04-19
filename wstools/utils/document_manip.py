

import os
import subprocess
import logging

def remove_pages(filename, pages, ext=None):

    # dion't guess if given
    if ext is None:
        _, ext = os.path.splitext(filename)

    pages.sort(reverse=True)

    if not pages:
        return

    logging.info("Deleting pages {}".format(', '.join(p)))

    for p in pages:
        if ext == ".djvu":
            cmd = ["djvm", "-d", filename, str(p)]
            logging.debug("Deleting page {}".format(p))
            subprocess.call(cmd)
        else:
            raise NotImplementedError('File type {ext} cannot have pages removed')