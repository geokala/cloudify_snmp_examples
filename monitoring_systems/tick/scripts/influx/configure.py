from cloudify import ctx
import os
import string
import subprocess
import tempfile
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
        'certificate': '/etc/influxdb/influxdb-selfsigned.crt',
        'private-key': '/etc/influxdb/influxdb-selfsigned.key',
    }

    ctx.logger.info('Configuring HTTPS for InfluxDB.')
    # A self signed cert is not ideal for production deployments, but this
    # blueprint is intended only as a reference example, so we mainly want the
    # SSL so that we can confirm telegraf and the webui will work with it.
    ctx.logger.info('Generating certificates.')
    csr_config = """[req]
distinguished_name = req_distinguished_name
req_extensions = server_req_extensions
[ server_req_extensions ]
subjectAltName=IP:127.0.0.1,DNS:127.0.0.1,DNS:localhost
[ req_distinguished_name ]
commonName = _common_name # ignored, _default is used instead
commonName_default = 127.0.0.1"""
    csr_conf_temp_dir = tempfile.mkdtemp()
    csr_conf_temp_file = os.path.join(csr_conf_temp_dir, 'csr_conf')
    with open(csr_conf_temp_file, 'w') as csr_conf_handle:
        csr_conf_handle.write(csr_config)
    subprocess.check_output([
        'sudo', 'openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048',
        '-days', '365', '-batch',
        '-keyout', conf_values['private-key'],
        '-out', conf_values['certificate'],
        '-extensions', 'server_req_extensions',
        '-config', csr_conf_temp_file,
    ])
    subprocess.check_call(['sudo', 'rm', '-rf', csr_conf_temp_dir])
    # Make the private key only be accessible to influx (and root)
    subprocess.check_call(['sudo', 'chmod', '440',
                           conf_values['private-key']])
    subprocess.check_call(['sudo', 'chgrp', 'influxdb',
                           conf_values['private-key']])
    with open(conf_values['certificate']) as cert_handle:
        ctx.instance.runtime_properties['ssl_cert'] = cert_handle.read()
    ctx.logger.info('Setting InfluxDB HTTPS configuration.')
    base_subst = "s|# https-{param} =.*|https-{param} = {value}|"
    substitutions = []
    for key, value in conf_values.items():
        if key != 'enabled':
            # The influx configuration requires quoted values or it will fail
            # but not log any helpful reasons. However, if we quote the
            # value of the https-enabled key then it'll also fail without
            # logging the reason.
            value = '"' + value + '"'
        substitutions.append(
            base_subst.format(
                param=key,
                value=value,
            )
        )
    substitutions.append('s|# auth-enabled = false|auth-enabled = true|')
    for substitution in substitutions:
        subprocess.check_output([
            "sudo", "sed", "-i",
            substitution,
            "/etc/influxdb/influxdb.conf"
        ])
    subprocess.check_output([
        'sudo', 'service', 'influxdb', 'restart',
    ])
    ctx.logger.info('HTTPS configured for InfluxDB.')


if __name__ == '__main__':
    configure()
