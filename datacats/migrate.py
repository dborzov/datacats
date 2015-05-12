# Copyright 2014-2015 Boxkite Inc.
# This file is part of the DataCats package and is released under
# the terms of the GNU Affero General Public License version 3.0.
# See LICENSE.txt or http://www.fsf.org/licensing/licenses/agpl-3.0.html

from os import makedirs, remove
from os.path import isdir, exists, join as path_join, split as path_split
from ConfigParser import SafeConfigParser
import shutil
import sys

from datacats.docker import (is_boot2docker, remove_container,
                             rename_container, web_command)
from datacats.scripts import PURGE, MIGRATE_BACKUP, MIGRATE
from datacats.password import generate_password


def needs_format_conversion(datadir):
    """
    Returns True if `datadir` requires conversion to the child env format.
    """
    return (isdir(datadir) and isdir(path_join(datadir, 'run')) and
            exists(path_join(datadir, 'passwords.ini')) and
            exists(path_join(datadir, 'search')) and
            exists(path_join(datadir, 'solr')) and
            exists(path_join(datadir, 'project-dir')))


def get_migration_lock(datadir):
    lock_location = path_join(datadir, '.migration_lock')
    # Just 'touch' the file to make sure it exists.
    open(lock_location, 'wb').close()


def release_migration_lock(datadir):
    lock_location = path_join(datadir, '.migration_lock')
    remove(lock_location)


def convert_environment(datadir):
    get_migration_lock(datadir)
    new_child_name = 'primary'
    inp = None

    while inp != 'y' and inp != 'n':
        inp = raw_input('You are using a file in the old DataCats format. '
                        'Would you like to convert it (y/n) [n]: ')

    if inp == 'n':
        sys.exit(1)

    # Get around a quirk in path_split where a / at the end will make the
    # dirname (split[0]) the entire path
    datadir = datadir[:-1] if datadir[-1] == '/' else datadir
    split = path_split(datadir)

    print 'Making sure that containers are stopped...'
    env_name = split[1]
    # Old-style names on purpose! We need to stop old containers!
    remove_container('datacats_web_' + env_name)
    remove_container('datacats_solr_' + env_name)
    remove_container('datacats_postgres_' + env_name)

    backup_name = split[1] + '.bak'
    backup_loc = path_join(split[0], backup_name)

    print 'Making a backup at {}...'.format(backup_loc)

    if exists(backup_loc):
        # Remove any old backups
        web_command(
                command=['/scripts/purge.sh'] +
                        ['/project/.datacats/' + split[1] + '.bak'],
                ro={PURGE: '/scripts/purge.sh'},
                rw={split[0]: '/project/.datacats'},
                clean_up=True)

    # Make a backup of the current version
    web_command(
            command=['/scripts/migrate_backup.sh',
                     '/project/.datacats/' + env_name,
                     '/project/.datacats/' + backup_name],
            ro={MIGRATE_BACKUP: '/scripts/migrate_backup.sh'},
            rw={split[0]: '/project/.datacats'},
            clean_up=True)

    # Begin the actual conversion
    to_move = (['files', 'passwords.ini', 'run', 'solr', 'search'] +
               (['postgres', 'data'] if not is_boot2docker() else []))
    # Make a primary child
    child_path = path_join(datadir, 'children', new_child_name)
    makedirs(child_path)

    print 'Doing conversion...'
    web_command(
            command=['/scripts/migrate.sh',
                     '/project/data',
                     '/project/data/children/' + new_child_name] +
            to_move,
            ro={MIGRATE: '/scripts/migrate.sh'},
            rw={datadir: '/project/data'},
            clean_up=True
            )

    if is_boot2docker():
        # Stick the child name in the file
        rename_container('datacats_pgdata_' + env_name,
                         'datacats_pgdata_' + env_name + '_' + new_child_name)

    with open(path_join(datadir, '.version'), 'w') as f:
        # Version 2
        f.write('2')

    # Lastly, grab the project directory and update the ini file
    with open(path_join(datadir, 'project-dir')) as pd:
        project = pd.read()

    cp = SafeConfigParser()
    config_loc = path_join(project, '.datacats-environment')
    cp.read([config_loc])

    new_section = 'child_' + new_child_name
    cp.add_section('child_' + new_child_name)

    # Ports need to be moved into the new section
    port = cp.get('datacats', 'port')
    cp.remove_option('datacats', 'port')

    cp.set(new_section, 'port', port)

    with open(config_loc, 'w') as config:
        cp.write(config)

    # Make a session secret for it (make it per-child)
    cp = SafeConfigParser()
    config_loc = path_join(child_path, 'passwords.ini')
    cp.read([config_loc])

    # Grab the secret from config
    # Find the project-dir
    with open(datadir + '/project-dir') as pd:
        dev_ini_loc = path_join(pd.read(), 'development.ini')
    dev_ini_cp = SafeConfigParser()
    dev_ini_cp.read(dev_ini_loc)
    secret = dev_ini_cp.get('app:main', 'beaker.session.secret')

    cp.set('passwords', 'beaker_session_secret', generate_password())

    with open(config_loc, 'w') as config:
        cp.write(config)

    release_migration_lock(datadir)
