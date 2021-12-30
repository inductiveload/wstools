
import os

def choose_file(filename, default_dirs, case_sensitive=False):

  if os.path.isabs(filename):
    return filename

  candidates = []

  def normalise(fn):
    if not case_sensitive:
      fn = fn.lower()

    fn = fn.replace(' ', '_')
    return fn

  filename = normalise(filename)

  for d in default_dirs:

    # skip nones, e.g. blank envs
    if not d:
      continue

    for path in os.listdir(d):

      full_path = os.path.join(d, path)

      if os.path.isfile(full_path):
        if normalise(path).startswith(filename):
          candidates.append(full_path)

  if not candidates:
    raise ValueError('No candidate files')

  if len(candidates) == 1:
    return candidates[0]

  raise ValueError(f'Too many candidate files: {candidates}')