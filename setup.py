from setuptools import (
    setup,
    find_packages,
)

setup(
    name='pysteon',
    author='Julien Kauffmann',
    author_email='julien.kauffmann@freelan.org',
    maintainer='Julien Kauffmann',
    maintainer_email='julien.kauffmann@freelan.org',
    version=open('VERSION').read().strip(),
    url='http://ereOn.github.io/pysteon',
    description="Insteon devices control library.",
    long_description="""\
pysteon is a library and a set of CLI that controls Insteon devices.
""",
    packages=find_packages(exclude=[
        'tests',
    ]),
    install_requires=[
        'chromalog>=1.0.5,<2',
        'click>=6.6,<7',
        'pyserial>=3.1.1,<4',
        'pyslot>=2.0.1,<3',
        'pyyaml>=3.12,<4',
    ],
    test_suite='tests',
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Development Status :: 5 - Production/Stable',
    ],
    entry_points={
        'console_scripts': [
            'pysteon = pysteon.entry_points:pysteon',
        ],
    },
)
