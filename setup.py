from setuptools import setup, find_packages
from setuptools.command.develop import develop
from setuptools.command.install import install
import shutil
import os
import subprocess

def install_service(command_subclass):
    command_subclass.user_options.append(('install-service=', None, 'by default installs keplerserver as a service'))
    _initialize_options = command_subclass.initialize_options
    def init_wrapper(self):
        _initialize_options(self)
        self.install_service = 'True'
    command_subclass.initialize_options = init_wrapper

    _run = command_subclass.run
    def run_wrapper(self):
        _run(self)
        if self.install_service in ['True', 'true']:
            this_path = os.path.dirname(os.path.realpath(__file__))
            unit_file_path = os.path.join(this_path, 'keplerserver.service')
            shutil.copy(unit_file_path, '/etc/systemd/system/')
            subprocess.check_output('systemctl daemon-reload', shell=True)
    command_subclass.run = run_wrapper
    return command_subclass


@install_service
class CustomDevelopCommand(develop):
    pass


@install_service
class CustomInstallCommand(install):
    pass

setup(
    name='kepler-server',
    version='0.1.0',
    description='Kepler API Server / Web GUI',
    author='Kumu',
    author_email='@kumunetworks.com',
    license='',
    install_requires=[
        'msgpack',
        'msgpack_numpy',
        'pyserial',
        'flask',
        'RPi.GPIO',
        'waitress'
    ],
    packages=find_packages(),
    entry_points={'console_scripts': ['keplerserver=keplerserver:main']},
    python_requires='>=3',
    package_data={'keplerserver': ['static/*', 'templates/*']},
    cmdclass={
        'develop': CustomDevelopCommand,
        'install': CustomInstallCommand,
    },
)
