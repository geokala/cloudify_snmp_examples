from cloudify import ctx
import os
import subprocess
import tempfile


BASE_CONF = """[agent]
  interval = "10s"
  round_interval = true
  metric_batch_size = 1000
  metric_buffer_limit = 10000
  collection_jitter = "0s"
  flush_interval = "10s"
  flush_jitter = "0s"
  precision = ""
  debug = false
  quiet = false
  logfile = ""
  hostname = ""
  omit_hostname = true

[[outputs.influxdb]]
  urls = ["http://127.0.0.1:8086"]
  database = "cloudify"
  retention_policy = ""
  write_consistency = "any"
  timeout = "5s"
  username = "{username}"
  password = "{password}"

[[inputs.internal]]"""


def configure():
    username = ctx.node.properties['influx_user']
    # TODO: Provide option between encrypted and unencrypted pass supplied
    password = ctx.node.properties['influx_pass']

    tmp_dir = tempfile.mkdtemp(prefix='cloudify_telegraf')

    tmp_conf_path = os.path.join(tmp_dir, 'base_conf')
    telegraf_conf_path = '/etc/telegraf/telegraf.conf'

    ctx.logger.info('Setting telegraf base configuration.')
    with open(tmp_conf_path, 'w') as conf_handle:
        conf_handle.write(BASE_CONF.format(
            username=username,
            password=password,
        ))
    subprocess.check_call(['sudo', 'cp', tmp_conf_path, telegraf_conf_path])
    subprocess.check_call(['rm', '-rf', tmp_dir])
    ctx.logger.info('Telegraf base config applied.')


if __name__ == '__main__':
    configure()
