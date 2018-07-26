#!/usr/bin/env python3

import argparse
import configparser
import os
import subprocess

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
        print("Connect to {}:{} and run {}".format(self.connection_str(), self.port, " ".join(command)))
        raw = subprocess.check_output(['ssh', self.connection_str(), '-p', self.port, '-i', self.identity_file] + command)
        return raw.decode('utf-8')

class BackupLocation:

    def __init__(self, config_dict, ssh, root_path, old_rotation, rotation, location):
        self.config_dict = config_dict
        self.ssh = ssh
        self.root_path = root_path
        self.old_rotation = old_rotation
        self.rotation = rotation
        self.location = location

    def config(self, key):
        return get_config(self.config_dict, key, self.location, self.rotation)

    def get_config_list(self, key):
        return get_config_list(self.config_dict, key, self.location, self.rotation)

    def backup(self):
        excluded = list(map(lambda x: '--exclude=' + x, self.get_config_list('exclude')))
        remote_path = os.path.join(self.root_path, self.config('destination'))
        destination = self.ssh.connection_str() + ':' + remote_path
        self.ssh.run(['mkdir', '-p', remote_path])
        ssh_cmd = 'ssh -p {} -i "{}"'.format(self.ssh.port, self.ssh.identity_file)
        rsync_args = ['-e', ssh_cmd, '-a', '--delete', '--numeric-ids', '--relative', '--delete-excluded']
        if self.old_rotation:
            rel_path = os.path.relpath(os.path.join(self.old_rotation, self.config('destination')), remote_path)
            rsync_args += ['--link-dest=' + rel_path]
        rsync_args += excluded
        rsync_cmd = ['rsync'] + rsync_args + [self.config('source'), destination]
        print("Run rsync command {}".format(" ".join(rsync_cmd)))
        try:
            raw = subprocess.check_output(rsync_cmd)
        except subprocess.CalledProcessError as e:
            print(e)

class Rotation:

    def __init__(self, config_dict, rotation):
        self.config_dict = config_dict
        self.rotation = rotation
        self.ssh = self.get_ssh()

    def config(self, key):
        return get_config(self.config_dict, key, self.rotation)

    def get_ssh(self):
        ip_script = self.config('remote_ip_script')
        print("Retrieve IP with {}".format(ip_script))
        ip_raw = subprocess.check_output(ip_script, shell=True)
        ip = ip_raw.decode('utf-8').strip()
        print("Found IP {}".format(ip))
        return SSH(self.config('remote_username'), ip, self.config('remote_port'), self.config('identity_file'))

    def rotate(self):
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
        self.ssh.run(mvs)
        return last_found

    def get_rotation_name(self, num):
        return '{}.{}'.format(self.config('name'), num)

    def get_rotation_path(self, num):
        return os.path.join(self.config('remote_root'), self.get_rotation_name(num))

    def do_everything(self):
        last_found = self.rotate()
        locations = self.config('locations').split(':')
        for location in locations:
            print("Process location {}".format(location))
            root_path = self.get_rotation_path(0)
            old_rotation = None if last_found is None else self.get_rotation_path(last_found)
            loc = BackupLocation(self.config_dict, self.ssh, root_path, old_rotation, self.rotation, location)
            loc.backup()


def get_config(config, key, *sections):
    for section in sections:
        if section in config:
            if key in config[section]:
                return config[section][key]
    return config['ShareMyData'][key]


def get_config_list(config, key, *sections):
    sol = []
    for section in sections + ('ShareMyData',):
        if section in config:
            for sectionkey in config[section]:
                if sectionkey.startswith(key):
                    sol.append(config[section][sectionkey])
    return sol


def read_config(args):
    config = configparser.ConfigParser()
    config.read(args.config)
    return config


def main():
    parser = argparse.ArgumentParser(description="Backup data to remote server via rsync.")
    parser.add_argument('--config', '-c', default='~/.sharemydata.ini', help="Config file")
    parser.add_argument('rotation', nargs='?', default='', help='Name of rotation to perform')
    args = parser.parse_args()

    config = read_config(args)
    if not config:
        print("Could not read config file {}".format(args.config))
        return
    Rotation(config, args.rotation or config['ShareMyData']['default_rotation']).do_everything()

if __name__ == '__main__':
    main()