#! /usr/bin/env python
from cloudify import ctx
import os
import subprocess
import tempfile


def configure():
    tmp_conf_dir = tempfile.mkdtemp(prefix='cloudify_influx_repo_install')

    tmp_repo_path = os.path.join(tmp_conf_dir, 'repo')
    tmp_key_path = os.path.join(tmp_conf_dir, 'key')

    repo_dest = '/etc/yum.repos.d/influxdata.repo'

    ctx.logger.info('Adding influx repository.')
    with open(tmp_repo_path, 'w') as repo_handle:
        repo_handle.write("""[influxdb]
name = InfluxData Repository - RHEL $releasever
baseurl = https://repos.influxdata.com/rhel/$releasever/$basearch/stable
enabled = 1
gpgcheck = 1
gpgkey = https://repos.influxdata.com/influxdb.key""")
    subprocess.check_call(['sudo', 'chown', 'root.',
                           tmp_repo_path])
    subprocess.check_call(['sudo', 'mv',
                           tmp_repo_path,
                           repo_dest])
    ctx.logger.info('Repository added in {path}'.format(path=repo_dest))

    ctx.logger.info('Adding repository key.')
    with open(tmp_key_path, 'w') as key_handle:
        key_handle.write(ctx.node.properties['influx_repo_public_key'])
    subprocess.check_call(['sudo', 'rpm', '--import', tmp_key_path])
    ctx.logger.info('Repository key added.')

    ctx.logger.info('Cleaning up tempdir.')
    subprocess.check_call(['rm', '-rf', tmp_conf_dir])


if __name__ == '__main__':
    configure()
