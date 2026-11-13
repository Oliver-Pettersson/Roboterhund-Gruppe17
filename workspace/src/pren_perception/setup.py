"""Paket fuer die Wahrnehmung des PREN-Roboterhunds."""

from setuptools import find_packages, setup

package_name = 'pren_perception'

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
    description='Kamera, Sprach-, Gesten- und Knochenerkennung des PREN-Roboterhunds.',
    license='Apache-2.0',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'camera_node = pren_perception.camera_node:main',
            'gesture_command_node = pren_perception.gesture_command_node:main',
            'voice_command_node = pren_perception.voice_command_node:main',
        ],
    },
)
