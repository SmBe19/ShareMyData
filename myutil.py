import logging
import subprocess
import configparser
import os

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


def create_ssh(ip_script, username, port, identity):
    logging.debug("Retrieve IP with %s", ip_script)
    ip_raw = subprocess.check_output(ip_script, shell=True)
    ip = ip_raw.decode('utf-8').strip()
    logging.info("Found backup device at %s", ip)
    return SSH(username, ip, port, identity)

def expanduser(path):
    if path.startswith("~/"):
        username = os.environ.get('SUDO_USER', '')
        path = "~" + username + path[1:]
    return os.path.expanduser(path)


def read_config(args):
    config = configparser.ConfigParser()
    config.read(expanduser(args.config))
    return config

def setup_logging(verbose, quiet, logfile):
    streamlevel = logging.INFO
    if verbose:
        streamlevel = logging.DEBUG
    elif quiet:
        streamlevel = logging.WARNING

    logging.basicConfig(format='%(levelname)-10s - %(message)s', level=streamlevel)
    rootlogger = logging.getLogger()

    filelevel = logging.DEBUG
    filehandler = logging.FileHandler(filename=logfile)
    filehandler.setLevel(filelevel)
    filehandler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)-10s - %(message)s'))
    rootlogger.addHandler(filehandler)
