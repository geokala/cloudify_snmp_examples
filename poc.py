import string
import subprocess
from platform import linux_distribution, win32_ver
import random

LINUX = linux_distribution() if linux_distribution[0] else None
WINDOWS = win32_ver() if win32_ver()[0] else None
SNMPD_ACCEPTED_HASH_TYPES = ('MD5', 'SHA')
SNMPD_ACCEPTED_ENCRYPTION = ('DES', 'AES')


class NotSupportedError(Exception):
    pass


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

    stop_service(service)

    add_snmpd_user(
        username=username,
        auth_pass=auth_pass,
        priv_pass=priv_pass,
        hash_type=hash_type,
        encryption=encryption,
        snmpd_user_conf_pass=snmpd_user_conf_path,
    )

    for tree in allowed_trees:
        add_snmp_view(tree, snmpd_service_conf_path)

    add_user_mapping(username, snmpd_service_conf_path)

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


def remove_cloudify_agent_from_snmpd(ctx):
    runtime_props = ctx.instance.runtime_properties

    if 'cloudify_snmp' not in runtime_props:
        # TODO: NonRecoverable
        raise RuntimeError('Cannot remove SNMPD as it was not configured.')
    snmp_props = runtime_props['cloudify_snmp']

    stop_service(snmp_props['service'])

    remove_entries_from_file('CloudifyMonitoringView',
                             snmp_props['snmpd_service_conf_path'])

    remove_entries_from_file(
        convert_username_to_hex_string(snmp_props['username']),
        snmp_props['snmpd_user_conf_pass'],
    )

    start_service(snmp_props['service'])


def stop_service(name):
    if LINUX:
        stop_service_command = ['sudo', 'service', name, 'stop']
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise NotSupportedError(
            'Only linux and windows are supported.'
        )
    subprocess.check_call(stop_service_command)


def start_service(name):
    if LINUX:
        start_service_command = ['sudo', 'service', name, 'start']
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise NotSupportedError(
            'Only linux and windows are supported.'
        )
    subprocess.check_call(start_service_command)


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
    view_string = 'view CloudifyMonitoringView {tree}'.format(
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
        subprocess.check_call(
            "sudo sed -i '/{partial}/d' {path}".format(
                partial=partial_string,
                path=path,
            ),
            shell=True,
        )
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise NotSupportedError(
            'Only linux and windows are supported.'
        )


def append_string_to_file(string, path):
    if LINUX:
        subprocess.check_call(
            'sudo echo {user_string} | tee -a {path}'.format(
                user_string=string,
                path=path,
            ),
            shell=True,
        )
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise NotSupportedError(
            'Only linux and windows are supported.'
        )


def get_random_password(length=40):
    return ''.join([
        random.choice(string.letters) for i in range(length)
    ])


def get_snmpd_user_conf_path():
    if LINUX:
        if LINUX[0] == 'CentOS Linux':
            return '/var/lib/net-snmp/snmpd.conf'
        else:
            return '/var/lib/snmp/snmpd.conf'
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise NotSupportedError(
            'Only linux and windows are supported.'
        )


def get_snmpd_service_conf_path():
    if LINUX:
        return '/etc/snmp/snmpd.conf'
    elif WINDOWS:
        raise NotImplementedError('Not implemented until later alpha')
    else:
        raise NotSupportedError(
            'Only linux and windows are supported.'
        )
