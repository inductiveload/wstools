#! /usr/bin/env python3

import argparse
import logging

import subprocess
import os
import sys
import re
import dotenv


class QuickPwbRunner():

    def __init__(self, put_throttle):

        self.put_throttle = put_throttle

    def run(self, file):

        if os.getenv('QUICKPWB_PWB_PATH'):
            pwb = os.path.join(os.getenv('QUICKPWB_PWB_PATH'), 'pwb.py')
        else:
            pwb = 'pwb.py'

        cmd = [pwb]

        script_name = "replace"

        variables = {}

        def interpolate(s):

            for key, value in variables.items():
                s = s.replace("$" + key, value)
                s = s.replace("${" + key + "}", value)
            return s

        pwb_args = []

        for line in file:

            if line.lstrip().startswith("#"):
                continue

            m = re.match(r"^\$([A-Z0-9_-]+)=(.*)$", line)

            if m:
                if m.group(1) == "_SCRIPT":
                    script_name = m.group(2)
                else:
                    variables[m.group(1)] = m.group(2)
                continue

            if line.startswith("-prefixindex"):

                parts = line.strip().split(":", 2)

                if len(parts) > 2:

                    if parts[1] == "Page":
                        basename = re.sub(r"/\d+", "", parts[2])
                    else:
                        basename = parts[2]

                    pwb_args.append("-namespace:" + interpolate(parts[1]))
                    pwb_args.append("-prefixindex:" + interpolate(basename))
                else:
                    pwb_args.append(interpolate(line))
                continue
            # auto-link templates
            if line.startswith("-summary"):
                line = re.sub(r"\{\{([^\[].*?)\}\}", r"{{[[Template:\1|\1]]}}", line)

            line = line.rstrip("\n")

            pwb_args.append(interpolate(line))

        cmd.append(script_name)

        if self.put_throttle is not None:
            cmd += ['-pt:{}'.format(self.put_throttle)]

        cmd += pwb_args
        logging.debug(cmd)

        subprocess.call(cmd)


def get_cmd_file(filename):

    if os.path.isfile(filename):
        return filename

    candidates = [filename]
    if not filename.endswith('.txt'):
        candidates.append(filename + '.txt')

    search = os.getenv('QUICKPWB_FIX_PATH')
    if search:
        search = search.split(':')

        for s in search:
            for c in candidates:
                fn = os.path.join(s, c)
                if os.path.isfile(fn):
                    return fn

    return None

def main():

    dotenv.load_dotenv();

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument("file", metavar="FILE",
                        help='Info file')
    parser.add_argument('-pt', '--put-throttle', type=float,
                        help='')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    runner = QuickPwbRunner(args.put_throttle)

    cmd_fn = get_cmd_file(args.file)

    if not cmd_fn or not os.path.isfile(cmd_fn):
        logging.error(f'{cmd_fn} is not a file')
        sys.exit(1)

    with open(cmd_fn, 'r') as cmd_file:
        runner.run(cmd_file)


if __name__ == "__main__":
    main()
