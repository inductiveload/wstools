
import os


def get_dir_list_with_exts(d, want_exts):

    def want(f):
        _, ext = os.path.splitext(f)
        return os.path.isfile(f) and ext.lower() in want_exts

    files = [os.path.join(d, f) for f in os.listdir(d) if want(os.path.join(d, f))]

    files.sort()

    return files
