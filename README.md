# ShareMyData
Script to backup data to a remote server with rsync. The data is pushed to the backup device. This makes this approach suitable for backing up devices which do not run all the time.

## Install
Clone the repository. To find the backup device we need a tool to keep track of its IP address. We use [ShareMyIP](https://github.com/SmBe19/ShareMyIP) for this. Clone this as well and follow its [installation instructions](https://github.com/SmBe19/ShareMyIP). We can now call the `get_ip.sh` script which will print the required IP address. You can also use a script which will print some domain name.

You need to be able to establish an ssh connection to the backup device using an identity file.

Next, we set up the config file for ShareMyData. Copy the file `sharemydata.ini.template` to `~/sharemydata.ini`. Edit the config file as described below. To do backups just call `./sharemydata.py` or if you want to see what's going on use `./sharemydata.py -vvv`. If you want to backup system files (such as in `/etc`) you have to run it as root (e.g. `sudo ./sharemydata.py`).

## Config File
The config file configures how to access the backup device as well as what to backup. Its default location is `~/.sharemydata.ini`. It uses the standard ini file format.

A configuration consists of some locations and some rotations. Locations describe what should be copied. Rotations specify how long the data should be kept. For each config item a default value can be specified in a higher section (main provides defaults for rotation, rotation for location). For example in the main section a default `retain` value of `7` could be defined and then in some rotations it is overridden to be `4`.

### Main Config
The main configuration is done in the section `[ShareMyData]`.

- `default_rotation`: Name of rotation to use if no rotation is specified as command line option.
- `logfile`: Name of file to write log to.
- `progressfile`: Name of file to write progress to. Use `{rotation}` as a placeholder for the name of the rotation.
- `remote_username`: Name of ssh user to connect to backup device.
- `remote_ip_script`: Path to script which returns the IP address of the backup device.
- `remote_port`: Port to connect to.
- `remote_root`: Path on backup device in which the backups are stored.
- `identity_file`: Path to private key for ssh connection.

### Rotation
- `name`: Name of the rotation. Should be the same as the section name.
- `locations`: Name of locations to backup separated by `:`.
- `retain`: How many versions of the data should be kept. For example, a weekly with `retain` of `3` will create `weekly.0`, `weekly.1` and `weekly.2`.

### Location
- `source`: Absolute path of local data to backup.
- `destination`: Relative path of destination on backup device. The resulting path will be `<remote_root>/<rotation>.<num>/<destination>/`.
- `require_root`: `1` if this location requires root permissions. This allows to check the required permissions before starting the backup process.
- `exclude#`: Define paths which should be excluded from the backup. Replace `#` by continuous numbers (e.g. `exclude1`, `exclude2`).
- `progress_depth`: How many levels (of folders) the transfer should be split into. One chunk has to be done in one sitting as only progress across these is tracked. Use `0` for small locations. For larger folders such as the home folder a value like `2` seems reasonable (depends a bit on how you store your data).

## Arguments
- `-h`: Get help for arguments.
- `-c <config>`: Use the specified config file instead of the default one (`~/.sharemaydata.ini`).
- `-v`: Make output more verbose. Add more to get more output. To get a list of copied files, use `-vvv`.
- `-f`: Force creating a new backup. The system keeps track of backup progress by itself so it nows when to start a new backup.
- `rotation`: Name of the rotation to synchronize. If not given the default rotation as specified in the config file is used.
