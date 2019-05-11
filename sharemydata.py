#!/usr/bin/env python3

import argparse
import configparser
import logging
import os
import subprocess

DEFAULT_SECTION = 'ShareMyData'
verbose = 0

class SSH:

    def __init__(self, username, ip, port, identity_file):
        self.username = username
        self.ip = ip
        self.port = port
        self.identity_file = identity_file

    def connection_str(self):
        return '{}@{}'.format(self.username, self.ip)

    def run(self, command):
        if isinstance(command, str):
            command = [command]
        logging.debug("Connect to %s:%s and run %s", self.connection_str(), self.port, " ".join(command))
        raw = subprocess.check_output(['ssh', self.connection_str(), '-p', self.port, '-i', self.identity_file] + command)
        return raw.decode('utf-8')

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

    def __init__(self, config_dict, ssh, root_path, old_rotation, rotation, location, progress):
        self.config_dict = config_dict
        self.ssh = ssh
        self.root_path = root_path
        self.old_rotation = old_rotation
        self.rotation = rotation
        self.location = location
        self.progress = progress
        self.progress_depth = int(self.config('progress_depth'))

    def config(self, key):
        return get_config(self.config_dict, key, self.location, self.rotation)

    def get_config_list(self, key):
        return get_config_list(self.config_dict, key, self.location, self.rotation)

    def handle_directory(self, directory, depth=0):
        if not self.progress.is_finished(directory):
            logging.info('Start directory %s', directory)
            excluded_list = self.get_config_list('exclude')
            excluded = list(map(lambda x: '--exclude=' + x, excluded_list))
            if any(directory.startswith(x) for x in excluded_list):
                return
            remote_path = os.path.join(self.root_path, self.config('destination'))
            destination = self.ssh.connection_str() + ':' + remote_path
            ssh_cmd = 'ssh -p {} -i "{}"'.format(self.ssh.port, self.ssh.identity_file)
            rsync_args = ['-e', ssh_cmd, '-lptgoD', '--dirs', '--delete', '--numeric-ids', '--relative', '--delete-excluded']
            if depth >= self.progress_depth:
                rsync_args += ['--recursive']
            if self.old_rotation:
                rel_path = os.path.relpath(os.path.join(self.old_rotation, self.config('destination')), remote_path)
                rsync_args += ['--link-dest=' + rel_path]
            rsync_args += excluded
            if verbose > 2:
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
        remote_path = os.path.join(self.root_path, self.config('destination'))
        self.ssh.run(['mkdir', '-p', remote_path])
        source = self.config('source')
        if not source.endswith('/'):
            source += '/'
        self.handle_directory(source)

class Rotation:

    def __init__(self, config_dict, rotation):
        self.config_dict = config_dict
        self.rotation = rotation
        self.ssh = self.get_ssh()
        self.progress = Progress(expanduser(self.config('progressfile').format(rotation=rotation)))

    def config(self, key):
        return get_config(self.config_dict, key, self.rotation)

    def get_ssh(self):
        ip_script = self.config('remote_ip_script')
        logging.debug("Retrieve IP with %s", ip_script)
        ip_raw = subprocess.check_output(ip_script, shell=True)
        ip = ip_raw.decode('utf-8').strip()
        logging.info("Found backup device at %s", ip)
        return SSH(self.config('remote_username'), ip, self.config('remote_port'), self.config('identity_file'))

    def rotate(self):
        logging.info("Rotate %s", self.rotation)
        files = self.ssh.run(['ls', self.config('remote_root')]).strip().split("\n")
        name = self.config('name')
        retain = int(self.config('retain'))

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
            #self.ssh.run(['mv', self.get_rotation_path(i), self.get_rotation_path(i+1)])
        if mvs:
            self.ssh.run(mvs)
        return last_found

    def get_last_found(self):
        logging.info('Resume %s without rotation', self.rotation)
        files = self.ssh.run(['ls', self.config('remote_root')]).strip().split("\n")
        retain = int(self.config('retain'))

        def exists(num):
            return self.get_rotation_name(num) in files

        for i in range(1, retain):
            if exists(i):
                return i
        return None

    def get_rotation_name(self, num):
        return '{}.{}'.format(self.config('name'), num)

    def get_rotation_path(self, num):
        return os.path.join(self.config('remote_root'), self.get_rotation_name(num))

    def do_everything(self, force_new):
        if force_new or self.progress.is_done():
            logging.info('Start new rotation for %s', self.rotation)
            last_found = self.rotate()
            self.progress.reset()
        else:
            last_found = self.get_last_found()
        locations = self.config('locations').split(':')
        root_path = self.get_rotation_path(0)
        old_rotation = None if last_found is None else self.get_rotation_path(last_found)
        for location in locations:
            logging.info("Process location %s", location)
            loc = BackupLocation(self.config_dict, self.ssh, root_path, old_rotation, self.rotation, location, self.progress)
            loc.backup()
        self.progress.set_done()
        logging.info("Finished backup")


def require_root(config, rotation):
    locations = get_config(config, 'locations', rotation).split(':')
    root = False
    for location in locations:
        root = root or get_config(config, 'require_root', rotation, location, default='0') != '0'
    return root


def get_config(config, key, *sections, default=None):
    try:
        for section in sections:
            if section in config:
                if key in config[section]:
                    return config[section][key]
        return config[DEFAULT_SECTION][key]
    except KeyError:
        return default


def get_config_list(config, key, *sections, default=None):
    try:
        sol = []
        for section in sections + (DEFAULT_SECTION,):
            if section in config:
                for sectionkey in config[section]:
                    if sectionkey.startswith(key):
                        sol.append(config[section][sectionkey])
        return sol
    except KeyError:
        return default


def expanduser(path):
    if path.startswith("~/"):
        username = os.environ.get('SUDO_USER', '')
        path = "~" + username + path[1:]
    return os.path.expanduser(path)


def read_config(args):
    config = configparser.ConfigParser()
    config.read(expanduser(args.config))
    return config


def setup_logging(args, config):
    global verbose
    if args.verbose is not None:
        verbose = args.verbose
    streamlevel = ([logging.WARNING, logging.INFO][verbose:] + [logging.DEBUG])[0]

    logging.basicConfig(format='%(levelname)-10s - %(message)s', level=streamlevel)
    rootlogger = logging.getLogger()

    logfile = expanduser(get_config(config, 'logfile'))
    filelevel = logging.DEBUG
    filehandler = logging.FileHandler(filename=logfile)
    filehandler.setLevel(filelevel)
    filehandler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)-10s - %(message)s'))
    rootlogger.addHandler(filehandler)


def main():
    parser = argparse.ArgumentParser(description="Backup data to remote server via rsync.")
    parser.add_argument('--config', '-c', default='~/.sharemydata.ini', help="Config file")
    parser.add_argument('--verbose', '-v', action='count', help='verbose output')
    parser.add_argument('--force-new', '-f', action='store_true', help='force starting a new backup process')
    parser.add_argument('rotation', nargs='?', default='', help='Name of rotation to perform')
    args = parser.parse_args()

    config = read_config(args)
    if not config:
        print("Could not read config file {}".format(args.config))
        return
    setup_logging(args, config)
    rotation = args.rotation or config['ShareMyData']['default_rotation']
    if require_root(config, rotation):
        if os.getuid() != 0:
            print("This config requires root permissions.")
            exit(0)
    Rotation(config, rotation).do_everything(args.force_new)

if __name__ == '__main__':
    main()
