from setuptools import find_packages, setup

package_name = 'topological_nav'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', [
            'launch/topological_nav.launch.xml',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='todo',
    maintainer_email='todo@todo.todo',
    description='Topological mapping and autonomous tour navigation with TurtleBot 4',
    license='TODO: License declaration',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'reactive_controller = topological_nav.reactive_controller:main',
            'tour_manager        = topological_nav.tour_manager:main',
            'gesture_node        = topological_nav.gesture_node:main',
            'qr_node             = topological_nav.qr_node:main',
            'tts_node            = topological_nav.tts_node:main',
            'person_follow_node  = topological_nav.person_follow_node:main',
        ],
    },
)
