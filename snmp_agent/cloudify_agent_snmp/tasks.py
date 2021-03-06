import string
import subprocess
from platform import linux_distribution, win32_ver
import random

from cloudify.decorators import operation
from cloudify import exceptions

LINUX = linux_distribution() if linux_distribution()[0] else None
WINDOWS = win32_ver() if win32_ver()[0] else None
SNMPD_ACCEPTED_HASH_TYPES = ('MD5', 'SHA')
SNMPD_ACCEPTED_ENCRYPTION = ('DES', 'AES')


@operation
def add_cloudify_agent_to_snmpd(ctx):
    snmp_props = ctx.node.properties.get('cloudify_snmp', {})
    runtime_props = ctx.instance.runtime_properties

    service = snmp_props.get('snmpd_service_name', 'snmpd')
    username = snmp_props.get('username', 'cloudify_monitoring')
    auth_pass = get_random_password()
    priv_pass = get_random_password()
    encryption = snmp_props.get('encryption', 'AES')
    hash_type = snmp_props.get('hash_type', 'SHA')
    snmpd_user_conf_path = snmp_props.get('snmpd_username_conf_path',
                                          get_snmpd_user_conf_path())
    snmpd_service_conf_path = snmp_props.get('snmpd_service_conf_path',
                                             get_snmpd_service_conf_path())
    allowed_trees = snmp_props.get('allowed_trees', ['.1.3.6.1.4.1.2021'])

    ctx.logger.info(
        'Stopping SNMP service "{service}" for configuration.'.format(
            service=service,
        ),
    )
    stop_service(service)

    ctx.logger.info(
        'Adding user "{username}" to SNMP user management file '
        '"{path}"'.format(
            username=username,
            path=snmpd_user_conf_path,
        )
    )
    add_snmpd_user(
        username=username,
        auth_pass=auth_pass,
        priv_pass=priv_pass,
        hash_type=hash_type,
        encryption=encryption,
        snmpd_user_conf_path=snmpd_user_conf_path,
    )

    for tree in allowed_trees:
        ctx.logger.info(
            'Adding tree "{tree}" to CloudifyMonitoringView in '
            '"{conf_path}"'.format(
                tree=tree,
                conf_path=snmpd_service_conf_path,
            )
        )
        add_snmp_view(tree, snmpd_service_conf_path)

    ctx.logger.info(
        'Configuring user "{username}" to use CLoudifyMonitoringView in '
        '"{conf_path}"'.format(
            username=username,
            conf_path=snmpd_service_conf_path,
        )
    )
    add_user_mapping(username, snmpd_service_conf_path)

    ctx.logger.info(
        'Starting SNMP service "{service}" with new configuration.'.format(
            service=service,
        ),
    )
    start_service(service)

    runtime_props['cloudify_snmp'] = {
        'service': service,
        'username': username,
        'auth_pass': auth_pass,
        'priv_pass': priv_pass,
        'encryption': encryption,
        'hash_type': hash_type,
        'snmpd_user_conf_path': snmpd_user_conf_path,
        'snmpd_service_conf_path': snmpd_service_conf_path,
        'allowed_trees': allowed_trees,
    }


@operation
def remove_cloudify_agent_from_snmpd(ctx):
    runtime_props = ctx.instance.runtime_properties

    if 'cloudify_snmp' not in runtime_props:
        raise exceptions.NonRecoverableError(
            'Cannot remove SNMPD as it was not configured.'
        )
    snmp_props = runtime_props['cloudify_snmp']

    ctx.logger.info(
        'Stopping SNMP service "{service}" to remove configuration.'.format(
            service=snmp_props['service'],
        ),
    )
    stop_service(snmp_props['service'])

    ctx.logger.info(
        'Removing all entries referencing CloudifyMonitoringView from '
        'SNMP config in "{conf_path}"'.format(
            conf_path=snmp_props['snmpd_service_conf_path'],
        )
    )
    remove_entries_from_file('CloudifyMonitoringView',
                             snmp_props['snmpd_service_conf_path'])

    hex_user = convert_username_to_hex_string(snmp_props['username'])
    ctx.logger.info(
        'Removing user "{username}", identified as "{hex_name}" from SNMP '
        'user management file "{user_conf_path}"'.format(
            username=snmp_props['username'],
            hex_name=hex_user,
            user_conf_path=snmp_props['snmpd_user_conf_path'],
        )
    )
    remove_entries_from_file(
        convert_username_to_hex_string(snmp_props['username']),
        snmp_props['snmpd_user_conf_path'],
    )

    ctx.logger.info(
        'Starting SNMP service "{service}" with removed cloudify '
        ' configuration.'.format(
            service=snmp_props['service'],
        ),
    )
    start_service(snmp_props['service'])

    runtime_props.pop('cloudify_snmp')


def stop_service(name):
    if LINUX:
        stop_service_command = ['sudo', 'service', name, 'stop']
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise exceptions.NonRecoverableError(
            'Only linux and windows are supported.'
        )
    _run(stop_service_command)


def start_service(name):
    if LINUX:
        start_service_command = ['sudo', 'service', name, 'start']
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise exceptions.NonRecoverableError(
            'Only linux and windows are supported.'
        )
    _run(start_service_command)


def add_snmpd_user(username, auth_pass, priv_pass, hash_type, encryption,
                   snmpd_user_conf_path):
    hash_type = hash_type.upper()
    encryption = encryption.upper()

    if hash_type not in SNMPD_ACCEPTED_HASH_TYPES:
        raise ValueError(
            'Hash type "{hash_type}" is not valid for SNMPD. Valid types '
            'are: {acceptable}'.format(
                hash_type=hash_type,
                acceptable=', '.join(SNMPD_ACCEPTED_HASH_TYPES),
            )
        )

    if encryption not in SNMPD_ACCEPTED_ENCRYPTION:
        raise ValueError(
            'Encryption type "{encryption}" is not valid for SNMPD. Valid '
            'encryption types are: {acceptable}'.format(
                encryption=encryption,
                acceptable=', '.join(SNMPD_ACCEPTED_ENCRYPTION),
            )
        )

    create_user_string = 'createUser {user} {hash_type} {auth} {enc} {priv}'
    create_user_string = create_user_string.format(
        user=username,
        hash_type=hash_type,
        auth=auth_pass,
        enc=encryption,
        priv=priv_pass,
    )

    append_string_to_file(create_user_string, snmpd_user_conf_path)


def add_snmp_view(tree, snmpd_config_path):
    view_string = 'view CloudifyMonitoringView included {tree}'.format(
        tree=tree,
    )
    append_string_to_file(view_string, snmpd_config_path)


def add_user_mapping(username, snmpd_config_path):
    mapping_string = 'rouser {user} priv -V CloudifyMonitoringView'.format(
        user=username,
    )
    append_string_to_file(mapping_string, snmpd_config_path)


def convert_username_to_hex_string(username):
    hex_name = [hex(ord(char)) for char in username]
    hex_name_string = '0x' + ''.join(part[2:] for part in hex_name)
    return hex_name_string


def remove_entries_from_file(partial_string, path):
    if LINUX:
        # Make any single quotes work with bash
        partial_string = partial_string.replace("'", "'\"'\"'")
        _run(
            "sudo sed -i '/{partial}/d' {path}".format(
                partial=partial_string,
                path=path,
            ),
            shell=True,
        )
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise exceptions.NonRecoverableError(
            'Only linux and windows are supported.'
        )


def append_string_to_file(string, path):
    if LINUX:
        _run(
            'echo {user_string} | sudo tee -a {path}'.format(
                user_string=string,
                path=path,
            ),
            shell=True,
        )
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise exceptions.NonRecoverableError(
            'Only linux and windows are supported.'
        )


def get_random_password(length=40):
    return ''.join([
        random.choice(string.letters) for i in range(length)
    ])


def get_snmpd_user_conf_path():
    if LINUX:
        if LINUX[0] in ('CentOS Linux', 'CentOS'):
            return '/var/lib/net-snmp/snmpd.conf'
        else:
            return '/var/lib/snmp/snmpd.conf'
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise exceptions.NonRecoverableError(
            'Only linux and windows are supported.'
        )


def get_snmpd_service_conf_path():
    if LINUX:
        return '/etc/snmp/snmpd.conf'
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise exceptions.NonRecoverableError(
            'Only linux and windows are supported.'
        )


def _run(command, shell=False):
    # It'd be nicer to use subprocess.check_output and ignore the output, but
    # that won't work on Centos6
    result = subprocess.call(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=shell,
    )
    if result != 0:
        raise subprocess.CalledProcessError(
            'Failed running {command} with shell={shell}'.format(
                command=command,
                shell=shell,
            )
        )
