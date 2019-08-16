from setuptools import setup, find_packages

version = '0.0.1'

setup(
    name='photoshop-connection',
    version=version,
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
