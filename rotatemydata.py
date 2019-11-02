#!/usr/bin/env python3

import argparse
import logging
import os
import subprocess
from myutil import SSH, create_ssh, expanduser, read_config, setup_logging

DEFAULT_SECTION = 'RotateMyData'


class Rotation:

    def __init__(self, location, config, ssh):
        self.location = location
        self.config = config
        self.ssh = ssh
        self.source_root = os.path.join(self.config[DEFAULT_SECTION]['remote_root'], self.config[location]['source'])
        if not self.source_root.endswith('/'):
            self.source_root += '/'
        self.destination_root = os.path.join(self.config[DEFAULT_SECTION]['remote_root'], self.config[location]['destination'])
        self.prefix = self.config[location].get('prefix', 'v')

    def get_rotation_name(self, num):
        return '{}.{}'.format(self.prefix, num)

    def get_rotation_path(self, num):
        return os.path.join(self.destination_root, self.get_rotation_name(num))

    def rotate_numbers(self):
        logging.info("Rotate %s", self.location)
        self.ssh.run(['mkdir', '-p', self.destination_root])
        files = self.ssh.run(['ls', self.destination_root]).strip().split("\n")
        retain = int(self.config[self.location].get('retain', 7))

        def exists(num):
            return self.get_rotation_name(num) in files

        if exists(retain):
            self.ssh.run(['rm', '-rf', self.get_rotation_path(retain)])

        last_found = None
        mvs = []
        for i in range(retain - 1, -1, -1):
            if not exists(i):
                continue
            last_found = i+1
            if mvs:
                mvs.append("&&")
            mvs.extend(['mv', self.get_rotation_path(i), self.get_rotation_path(i+1)])
        if mvs:
            self.ssh.run(mvs)
        return last_found

    def new_rotation(self, last_found):
        old_path = None if last_found is None else self.get_rotation_path(last_found)
        new_path = self.get_rotation_path(0)
        rsync_args = ['-lptgoD', '--dirs', '--delete', '--numeric-ids', '--delete-excluded', '--recursive']
        if old_path:
            rel_path = os.path.relpath(old_path, new_path)
            rsync_args += ['--link-dest=' + rel_path]
        rsync_cmd = ['rsync'] + rsync_args + [self.source_root, new_path]
        try:
            result = self.ssh.run(rsync_cmd)
        except subprocess.CalledProcessError as e:
            logging.error(e)

    def read_file(self, file):
        return self.ssh.run(['touch', file, '&&', 'cat', file])

    def rotate(self):
        logging.info("Process location %s", self.location)
        lastbackup_path = os.path.join(self.source_root, 'sharemydata_lastbackup.txt')
        lastrotation_path = os.path.join(self.source_root, 'sharemydata_lastrotation.txt')
        if self.read_file(lastbackup_path) == self.read_file(lastrotation_path):
            logging.info("No new backup, do not need to rotate")
            return
        last_found = self.rotate_numbers()
        self.new_rotation(last_found)
        self.ssh.run(['cp', lastbackup_path, lastrotation_path])
        logging.info("Finished location %s", self.location)


def main():
    parser = argparse.ArgumentParser(description="Rotate a backup on a remote server using rsync.")
    parser.add_argument('--config', '-c', default='~/.rotatemydata.ini', help="Config file")
    parser.add_argument('--verbose', '-v', action='store_true', help='verbose output')
    parser.add_argument('--quiet', action='store_true', help='output only warnings')
    args = parser.parse_args()

    config = read_config(args)
    if not config:
        print("Could not read config file {}".format(args.config))
        return
    conf = config[DEFAULT_SECTION]
    setup_logging(args.verbose, args.quiet, expanduser(conf['logfile']))
    ssh = create_ssh(conf['remote_ip_script'], conf['remote_username'], conf['remote_port'], conf['identity_file'])
    locations = conf['locations'].split(':')
    for location in locations:
        Rotation(location, config, ssh).rotate()

if __name__ == '__main__':
    main()
