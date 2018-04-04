from cloudify import ctx
import subprocess


def delete():
    ctx.logger.info('Removing telegraf.')
    subprocess.check_call(['sudo', 'yum', 'remove', '-y', 'telegraf'])
    ctx.logger.info('Telegraf removed.')


if __name__ == '__main__':
    delete()
