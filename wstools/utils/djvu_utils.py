
import logging
import os
import subprocess
import shutil
import tempfile

import tqdm


def create_djvu_from_pages(djvu_files, out_djvu):

    logging.debug(f'Concatenating {len(djvu_files)} djvu files to {out_djvu}')

    # djvm complains if the file exists
    if os.path.exists(out_djvu):
        os.remove(out_djvu)

    if len(djvu_files) == 0:
        return None

    cmd = ["djvm", "-c", out_djvu]
    cmd.extend(djvu_files)

    subprocess.check_call(cmd)


def get_page_count(djvu_filename):
    cmd = ['djvused', '-e', 'n', djvu_filename]
    output = subprocess.check_output(cmd)
    return int(output.strip())


def strip_pages(djvu_filename, include_pages, exclude_pages):

    # nothing to do here
    if not include_pages and not exclude_pages:
        return

    fast_fs = os.getenv('FAST_ACCESS_DIR')

    if fast_fs:
        afhandle, active_file = tempfile.mkstemp(
                prefix=os.path.split(djvu_filename)[1], dir=fast_fs)
        os.close(afhandle)
        shutil.copyfile(djvu_filename, active_file)
    else:
        active_file = djvu_filename

    cnt = get_page_count(djvu_filename)

    all_p = range(1, cnt + 1)

    if include_pages:
        all_p = [x for x in all_p if x in include_pages]

    if exclude_pages:
        all_p = [x for x in all_p if x not in exclude_pages]

    # page that need deleting
    del_p = [x for x in range(1, cnt + 1) if x not in all_p]
    del_p.sort(reverse=True)

    logging.debug(djvu_filename)

    if del_p:
        for p in tqdm.tqdm(del_p, desc='Rm pages'):
            cmd = ['djvm', '-d', active_file, str(p)]
            print(cmd)
            subprocess.check_call(cmd)

    if fast_fs:
        shutil.copyfile(active_file, djvu_filename)
        os.remove(active_file)
