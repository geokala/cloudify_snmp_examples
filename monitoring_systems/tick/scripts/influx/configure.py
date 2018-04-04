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

    username = ctx.node.properties.get('influx_user', 'cloudify')
    password = _get_random_password()
    unpriv_username = '{user}_unprivileged'.format(user=username)
    unpriv_password = _get_random_password()

    database_name = 'cloudify'

    ctx.logger.info('Creating influx users and databases.')
    try:
        if 'admin_username' not in ctx.instance.runtime_properties:
            ctx.logger.info('Creating admin user')
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
            ctx.instance.runtime_properties['admin_username'] = username
            # TODO: These should be encrypted using the same approach as for
            # the snmp agent plugin (encryption not implemented yet in either
            # plugin)
            ctx.instance.runtime_properties['admin_password'] = password
            ctx.logger.info('Admin user created.')
        if 'unprivileged_username' not in ctx.instance.runtime_properties:
            ctx.logger.info('Creating unprivileged user')
            subprocess.check_call([
                'influx', '--username', username, '--password', password,
                '--execute', (
                    'CREATE USER "{username}" '
                    "WITH PASSWORD '{password}'"
                ).format(
                    username=unpriv_username,
                    password=unpriv_password,
                ),
            ])
            ctx.instance.runtime_properties['unprivileged_username'] = (
                unpriv_username
            )
            ctx.instance.runtime_properties['unprivileged_password'] = (
                unpriv_password
            )
            ctx.logger.info('Unprivileged user created.')
        if 'database' not in ctx.instance.runtime_properties:
            ctx.logger.info('Creating database')
            subprocess.check_call([
                'influx', '--username', username, '--password', password,
                '--execute', (
                    'CREATE DATABASE {database}'
                ).format(
                    database=database_name,
                ),
            ])
            ctx.instance.runtime_properties['database'] = (
                database_name
            )
            ctx.logger.info('Database created.')
        if 'database_permissions' not in ctx.instance.runtime_properties:
            ctx.logger.info('Granting unprivileged user DB write access.')
            subprocess.check_call([
                'influx', '--username', username, '--password', password,
                '--execute', (
                    'GRANT WRITE ON {database} TO {user}'
                ).format(
                    database=database_name,
                    user=unpriv_username,
                ),
            ])
            ctx.instance.runtime_properties['database_permissions'] = {
                database_name: {
                    'WRITE': [
                        unpriv_username,
                    ],
                },
            }
            ctx.logger.info('Unprivileged user permissions granted.')
    except subprocess.CalledProcessError:
        # Avoid spitting the password into the logs
        raise subprocess.CalledProcessError(
            'Failed preparing influx. Database may not have started...'
        )
    ctx.logger.info('Influx users and databases created.')
    configure_https()


def configure_https():
    conf_values = {
        # Don't change these names unless influxdb conf does, please.
        'enabled': 'true',
        'certificate': '/etc/ssl/influxdb-selfsigned.key',
        'private-key': '/etc/ssl/influxdb-selfsigned.crt',
    }

    ctx.logger.info('Configuring HTTPS for InfluxDB.')
    # A self signed cert is not ideal for production deployments, but this
    # blueprint is intended only as a reference example, so we mainly want the
    # SSL so that we can confirm telegraf and the webui will work with it.
    ctx.logger.info('Generating certificates.')
    subprocess.check_output([
        'sudo', 'openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048',
        '-days', '365', '-batch',
        '-keyout', conf_values['private-key'],
        '-out', conf_values['certificate'],
    ])
    with open('/etc/ssl/influxdb-selfsigned.crt') as cert_handle:
        ctx.instance.runtime_properties['ssl_cert'] = cert_handle.read()
    ctx.logger.info('Setting InfluxDB HTTPS configuration.')
    base_subst = "s|# https-{param} =.*|https-{param} = {value}|"
    for key, value in conf_values.items():
        subprocess.check_output([
            "sudo", "sed", "-i",
            base_subst.format(
                param=key,
                value=value,
            ),
            "/etc/influxdb/influxdb.conf"
        ])
    subprocess.check_output([
        'sudo', 'service', 'influxdb', 'restart',
    ])
    ctx.logger.info('HTTPS configured for InfluxDB.')


if __name__ == '__main__':
    configure()
