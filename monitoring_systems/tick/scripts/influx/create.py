#! /usr/bin/env python
from cloudify import ctx
import subprocess


def create():
    ctx.logger.info('Installing influx.')
    subprocess.check_call(['sudo', 'yum', 'install', '-y', 'influxdb'])
    ctx.logger.info('Influx installed.')


if __name__ == '__main__':
    create()
