import os
from setuptools import setup, find_packages


def get_version():
    root = os.path.dirname(__file__)
    filename = os.path.join(root, 'src', 'photoshop', 'version.py')
    with open(filename, 'r') as f:
        return f.read().split('=')[1].strip(" \n'")


setup(
    name='photoshop-connection',
    version=get_version(),
    author='Kota Yamaguchi',
    author_email='KotaYamaguchi1984@gmail.com',
    url='https://github.com/kyamagu/photoshop-connection',
    description='Python package for Photoshop Connection.',
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License (MIT)',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries',
    ],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    install_requires=[
        'cryptography',
        'jinja2',
    ],
    entry_points={
        'console_scripts': ['photoshop-connection = photoshop.__main__:main'],
    },
)
