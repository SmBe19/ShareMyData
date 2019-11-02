# ShareMyData
Script to backup data to a remote server with rsync. The data is pushed to the backup device. This makes this approach suitable for backing up devices which do not run all the time. The process is split into two parts, one uploading the data and a second one doing the rotations.

## Install
Clone the repository. To find the backup device we need a tool to keep track of its IP address. We use [ShareMyIP](https://github.com/SmBe19/ShareMyIP) for this. Clone this as well and follow its [installation instructions](https://github.com/SmBe19/ShareMyIP). We can now call the `get_ip.sh` script which will print the required IP address. You can also use a script which will print some domain name.

You need to be able to establish an ssh connection to the backup device using an identity file.

Next, we set up the config file for ShareMyData. Copy the file `sharemydata.ini.template` to `~/.sharemydata.ini`. Edit the config file as described below. To do backups just call `./sharemydata.py` or if you want to see what's going on use `./sharemydata.py -v`. If you want to backup system files (such as in `/etc`) you have to run it as root (e.g. `sudo ./sharemydata.py`). This script will only copy the files to the remote server.

Finally, we have to set up the config file for the rotation component called RotateMyData. Copy the file `rotatemydata.ini.template` to `~/.rotatemydata.ini` and edit it accordingly. To do rotations call `./rotatemydata.py`. You can run this script from a different device and this device can do rotations for several clients.

## ShareMyData Config File
The config file configures how to access the backup device as well as what to backup. Its default location is `~/.sharemydata.ini`. It uses the standard ini file format.

A configuration consists of some locations which describe what should be backed up.

### Main Config
The main configuration is done in the section `[ShareMyData]`.

- `logfile`: Name of file to write log to.
- `progressfile`: Name of file to write progress to.
- `remote_username`: Name of ssh user to connect to backup device.
- `remote_ip_script`: Path to script which returns the IP address of the backup device.
- `remote_port`: Port to connect to.
- `remote_root`: Path on backup device in which the backups are stored.
- `identity_file`: Path to private key for ssh connection.

### Location
- `source`: Absolute path of local data to backup.
- `require_root`: `1` if this location requires root permissions. This allows to check the required permissions before starting the backup process.
- `exclude#`: Define paths which should be excluded from the backup. Replace `#` by continuous numbers (e.g. `exclude1`, `exclude2`).
- `progress_depth`: How many levels (of folders) the transfer should be split into. One chunk has to be done in one sitting as only progress across these is tracked. Use `0` for small locations. For larger folders such as the home folder a value like `2` seems reasonable (depends a bit on how you store your data).

## RotateMyData Config File
The config file configures how to access the backup device as well as where the backups are stored that will be rotated. Its default location is `~/.rotatemydata.ini`. It uses the standard ini file format.

### Main Config
The main configuration is done in the section `[RotateMyData]`.

- `logfile`: Name of file to write log to.
- `remote_username`: Name of ssh user to connect to backup device.
- `remote_ip_script`: Path to script which returns the IP address of the backup device.
- `remote_port`: Port to connect to.
- `remote_root`: Path on backup device in which the folders with the backups are stored. This is usually the parent directory of what is configured in the `sharemydata.ini` config.
- `identity_file`: Path to private key for ssh connection.

### Location
- `source`: Relative path to a backup folder
- `destination`: Relative path to destination folder in which the rotations are stored
- `retain`: How many old backups should be kept
- `prefix`: Prefix for rotation folder names. Default is `v`, resulting in folders named `v.0`, `v.1` and so on.

## Arguments
- `-h`: Get help for arguments.
- `-c <config>`: Use the specified config file instead of the default one (`~/.sharemaydata.ini`).
- `-v`: Make output more verbose. Add more to get more output. To get a list of copied files, use `-vvv`.
- `-f`: Force creating a new backup. The system keeps track of backup progress by itself so it nows when to start a new backup.
