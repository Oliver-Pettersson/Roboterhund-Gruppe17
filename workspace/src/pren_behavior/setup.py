"""Paket fuer das Verhalten des PREN-Roboterhunds."""

from setuptools import find_packages, setup

package_name = 'pren_behavior'

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
    description='Zustandsautomat und Bewegungsablaeufe des PREN-Roboterhunds.',
    license='Apache-2.0',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'dog_behavior_node = pren_behavior.dog_behavior_node:main',
        ],
    },
)
