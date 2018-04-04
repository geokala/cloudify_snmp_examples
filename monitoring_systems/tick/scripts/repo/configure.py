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
    try:
        keys_before = subprocess.check_output(['rpm', '-q', 'gpg-pubkey'])
        keys_before = [line.strip() for line in keys_before.splitlines()]
    except subprocess.CalledProcessError:
        # This will cause an error when there are no keys
        keys_before = []
    with open(tmp_key_path, 'w') as key_handle:
        key_handle.write(ctx.node.properties['influx_repo_public_key'])
    subprocess.check_call(['sudo', 'rpm', '--import', tmp_key_path])
    keys_after = subprocess.check_output(['rpm', '-q', 'gpg-pubkey'])
    keys_after = [line.strip() for line in keys_after.splitlines()]
    # This logic will fail if another key is being added at the same time as
    # this install is running, but if someone is messing around with yum
    # during this install then we will run into too many race conditions to
    # consider this to be stable.
    # Simply put: Running this install in parallel with other rpm related
    # activities is not supported.
    for key in keys_after:
        if key not in keys_before:
            ctx.instance.runtime_properties['rpm-gpg-key'] = key.strip()
            break
    ctx.logger.info('Repository key added.')

    ctx.logger.info('Cleaning up tempdir.')
    subprocess.check_call(['rm', '-rf', tmp_conf_dir])


if __name__ == '__main__':
    configure()
