# Copyright 2014-2015 Boxkite Inc.

# This file is part of the DataCats package and is released under
# the terms of the GNU Affero General Public License version 3.0.
# See LICENSE.txt or http://www.fsf.org/licensing/licenses/agpl-3.0.html

from datacats.docker import container_logs

from datacats.cli import manage
from datacats.error import DatacatsError
from datacats.environment import Environment
import datacats.task


def install(environment, opts):
    """Install or reinstall Python packages within this environment

Usage:
  datacats install [-cq] [--address=IP] [ENVIRONMENT]

Options:
  --address=IP          The address to bind to when reloading after install [default: 127.0.0.1]
  -c --clean            Reinstall packages into a clean virtualenv
  -q --quiet            Do not show output from installing packages and requirements.

ENVIRONMENT may be an environment name or a path to an environment directory.
Default: '.'
"""
    environment.require_data()
    datacats.task.install_all(environment, opts['--clean'], verbose=not opts['--quiet'])

    for site in environment.sites:
        environment = Environment.load(environment.name, site)
        if 'web' in environment.containers_running():
            # FIXME: reload without changing debug setting?
            manage.reload_(environment, {
                '--address': opts['--address'],
                '--background': False,
                '--no-watch': False,
                '--production': False,
                'PORT': None,
                '--syslog': False,
                '--site-url': None
                })


def _print_logs(c_id):
    for item in container_logs(c_id, "all", True, None):
        print item
