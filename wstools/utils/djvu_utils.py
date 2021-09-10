
import logging
import os
import subprocess

def create_djvu_from_pages(djvu_files, out_djvu):

    logging.debug("Concatenating {} djvu files to {}".format(len(djvu_files), out_djvu))

    # djvm complains if the file exists
    if os.path.exists(out_djvu):
        os.remove(out_djvu)

    if len(djvu_files) == 0:
        return None

    cmd = ["djvm", "-c", out_djvu]
    cmd.extend(djvu_files)

    rc = subprocess.call(cmd)

    if rc != 0:
        raise ValueError("djvm returned {}".format(rc))