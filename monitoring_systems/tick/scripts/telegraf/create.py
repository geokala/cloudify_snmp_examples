from cloudify import ctx
import subprocess


def create():
    ctx.logger.info('Installing telegraf.')
    subprocess.check_call(['sudo', 'yum', 'install', '-y', 'telegraf'])
    ctx.logger.info('Telegraf installed.')


if __name__ == '__main__':
    create()
