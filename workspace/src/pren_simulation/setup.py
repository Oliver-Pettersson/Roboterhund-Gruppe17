"""Paket fuer die Webots-Anbindung und das Bedienfenster der Simulation."""

from setuptools import find_packages, setup

package_name = 'pren_simulation'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='liano',
    maintainer_email='liano@gmx.ch',
    description='Webots-Bridge und Bedienfenster fuer die PREN-Simulation.',
    license='Apache-2.0',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'control_panel = pren_simulation.control_panel:main',
            'simulation_check = pren_simulation.simulation_check:main',
        ],
    },
)
