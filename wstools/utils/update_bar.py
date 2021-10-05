
import sys

try:
    import tqdm
except ImportError:
    tqdm = None


class DummyUpdateBar():

    def __init__(self, name, total):
        self.name = name
        self.total = total

    def update(size):
        pass


def get_download_bar(name, total):

    if tqdm:
        return tqdm.tqdm(
            desc=name,
            total=total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024)

    return DummyUpdateBar(name, total)


"""
Wrapper for Paramiko callbacks
"""
if tqdm is None:
    class ParamikoTqdmWrapper(object):
        # tqdm not installed - construct and return dummy/basic versions
        def __init__(self, *a, **k):
            pass

        def view_bar(self, name, size, sent):
            # original version
            res = sent / int(size) * 100
            sys.stdout.write(f'\rComplete precent: {res:.2f}%')
            sys.stdout.flush()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
else:
    class ParamikoTqdmWrapper(tqdm.tqdm):
        def view_bar(self, name, size, sent):
            self.total = int(size)
            self.update(int(sent - self.n))  # update pbar with increment
