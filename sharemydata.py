#!/usr/bin/env python3

import argparse
import configparser
import logging
import os
import subprocess
from myutil import SSH, create_ssh, expanduser, read_config, setup_logging

DEFAULT_SECTION = 'ShareMyData'


class Progress:

    def __init__(self, filename):
        self.filename = filename
        self.finished = set()
        if os.path.exists(filename):
            with open(filename, "r") as f:
                self.finished = set(x.strip() for x in f.readlines() if x.strip())
        logging.debug('Already processed locations: %s', ", ".join(self.finished))

    def is_done(self):
        return self.is_finished(':sharemydata:done:')

    def set_done(self):
        self.add_finished(':sharemydata:done:')

    def is_finished(self, path):
        return path in self.finished

    def add_finished(self, path):
        self.finished.add(path)
        with open(self.filename, "w") as f:
            print("\n".join(self.finished), file=f)

    def reset(self):
        logging.info('Reset progress')
        self.finished.clear()
        os.remove(self.filename)


class BackupLocation:

    def __init__(self, location, config, ssh, progress, verbose):
        self.location = location
        self.config = config
        self.ssh = ssh
        self.progress = progress
        self.verbose = verbose
        self.remote_root = self.config[DEFAULT_SECTION]['remote_root']
        self.progress_depth = int(self.config[location].get('progress_depth', 2))
        self.excluded_list = []
        for key in self.config[location]:
            if key.startswith('exclude'):
                self.excluded_list.append(self.config[location][key])

    def handle_directory(self, directory, depth=0):
        if not self.progress.is_finished(directory):
            logging.info('Start directory %s', directory)
            excluded = ['--exclude=' + x for x in self.excluded_list]
            if any(directory.startswith(x) for x in self.excluded_list):
                return
            destination = self.ssh.connection_str() + ':' + self.remote_root
            ssh_cmd = 'ssh -p {} -i "{}"'.format(self.ssh.port, self.ssh.identity_file)
            rsync_args = ['-e', ssh_cmd, '-lptgoD', '--dirs', '--delete', '--numeric-ids', '--relative', '--delete-excluded']
            if depth >= self.progress_depth:
                rsync_args += ['--recursive']
            rsync_args += excluded
            if self.verbose:
                rsync_args += ['-v']
            rsync_cmd = ['rsync'] + rsync_args + [directory, destination]
            logging.debug("Run rsync command %s", " ".join(rsync_cmd))
            try:
                result = subprocess.run(rsync_cmd, check=True)
                self.progress.add_finished(directory)
                logging.info('Finished directory %s', directory)
            except subprocess.CalledProcessError as e:
                logging.error(e)
                logging.info('Error for directory %s', directory)
        if depth < self.progress_depth:
            for f in os.listdir(directory):
                if os.path.isdir(os.path.join(directory, f)):
                    self.handle_directory(os.path.join(directory, f) + '/', depth+1)

    def backup(self):
        self.ssh.run(['mkdir', '-p', self.remote_root])
        source = self.config[self.location]['source']
        if not source.endswith('/'):
            source += '/'
        self.handle_directory(source)


def require_root(config, locations):
    root = False
    for location in locations:
        root = root or config[location].get('require_root', '0') != '0'
    return root


def main():
    parser = argparse.ArgumentParser(description="Backup data to remote server via rsync.")
    parser.add_argument('--config', '-c', default='~/.sharemydata.ini', help="Config file")
    parser.add_argument('--verbose', '-v', action='store_true', help='verbose output')
    parser.add_argument('--quiet', action='store_true', help='output only warnings')
    parser.add_argument('--force-new', '-f', action='store_true', help='force starting a new backup process')
    args = parser.parse_args()

    config = read_config(args)
    if not config:
        print("Could not read config file {}".format(args.config))
        return
    conf = config[DEFAULT_SECTION]
    setup_logging(args.verbose, args.quiet, expanduser(conf['logfile']))
    locations = config[DEFAULT_SECTION]['locations'].split(':')
    if require_root(config, locations):
        if os.getuid() != 0:
            print("This config requires root permissions.")
            exit(0)
    ssh = create_ssh(conf['remote_ip_script'], conf['remote_username'], conf['remote_port'], conf['identity_file'])
    progress = Progress(expanduser(conf['progressfile']))
    for location in locations:
        BackupLocation(location, config, ssh, progress, args.verbose).backup()
    progress.reset()
    ssh.run('date > ' + os.path.join(conf['remote_root'], 'sharemydata_lastbackup.txt'))

if __name__ == '__main__':
    main()
