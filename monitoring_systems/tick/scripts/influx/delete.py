#! /usr/bin/env python
from cloudify import ctx
import subprocess


def delete():
    ctx.logger.info('Removing influx.')
    subprocess.check_call(['sudo', 'yum', 'remove', '-y', 'influxdb'])
    ctx.logger.info('Influx removed.')


if __name__ == '__main__':
    delete()
