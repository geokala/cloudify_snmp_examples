from cloudify import ctx
import subprocess


def start():
    ctx.logger.info('Starting telegraf service.')
    # Restart instead of start so that config is applied if the service is
    # already started
    subprocess.check_call(['sudo', 'service', 'telegraf', 'restart'])
    ctx.logger.info('Telegraf service started.')


if __name__ == '__main__':
    start()
