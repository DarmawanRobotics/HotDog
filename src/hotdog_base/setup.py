from __future__ import annotations

from glob import glob

from setuptools import find_packages, setup

package_name = 'hotdog_base'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test', 'test.*']),
    data_files=[
        ('share/ament_index/resource_index/packages', [f'resource/{package_name}']),
        (f'share/{package_name}', ['package.xml', 'README.md']),
        (f'share/{package_name}/launch', glob('launch/*.launch.py')),
        (f'share/{package_name}/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    extras_require={'test': ['pytest']},
    zip_safe=True,
    maintainer='Agus Darmawan',
    maintainer_email='darmawandeveloper@gmail.com',
    description='The Lynx M20 under HotDog: both Airy LiDARs as one leveled cloud.',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'cloud_merger_node = hotdog_base.cloud_merger_node:main',
        ],
    },
)
