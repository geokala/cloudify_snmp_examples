from setuptools import setup

setup(
    name='cloudify-managed-monitoring-plugin',
    version='0.1.0',
    packages=['cloudify_managed_monitoring'],
    install_requires=['cloudify-plugins-common>=3.3.1',
                      'Jinja2==2.10'],
)
