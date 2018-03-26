from cloudify import ctx
import string
import subprocess
import random


def _get_random_password(length=40):
    return ''.join([
        random.choice(string.letters) for i in range(length)
    ])


def configure():
    ctx.logger.info('Ensuring influx is started for service configuration.')
    subprocess.check_call(['sudo', 'service', 'influxdb', 'start'])
    ctx.logger.info('Influx service started.')

    username = ctx.node.properties.get('influx_user', 'cloudify_manager')
    password = _get_random_password()

    ctx.logger.info('Creating influx admin user.')
    # TODO: Should add a less privileged user for inputting data.
    subprocess.check_call([
        'influx', '--execute', (
            'CREATE USER "{username}" '
            "WITH PASSWORD '{password}' "
            'WITH ALL PRIVILEGES'
        ).format(
            username=username,
            password=password,
        ),
    ])
    ctx.logger.info('Influx admin user created.')

    ctx.instance.runtime_properties['username'] = username
    # TODO: This should be encrypted using the same approach as for the snmp
    # agent plugin (also not implemented yet)
    ctx.instance.runtime_properties['password'] = password


if __name__ == '__main__':
    configure()
