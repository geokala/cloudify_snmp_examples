#! /usr/bin/env python
from cloudify import ctx
import subprocess


def delete():
    repo = '/etc/yum.repos.d/influxdata.repo'
    ctx.logger.info('Removing Influx yum repository.')
    subprocess.check_call(['sudo', 'rm', '-f', repo])
    ctx.logger.info('Influx yum repository removed.')

    rpmkey = ctx.instance.runtime_properties.get('rpm-gpg-key')
    if rpmkey:
        ctx.logger.info('Removing Influx GPG key.')
        subprocess.check_call(['sudo', 'rpm', '-e', rpmkey])
        ctx.logger.info('Influx GPG key removed.')
    else:
        ctx.logger.warn(
            'Could not remove influx GPG key from RPM as its ID was not '
            'known.'
        )


if __name__ == '__main__':
    delete()
