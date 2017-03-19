from setuptools import setup, find_packages


install_requires = [
    'PyYAML',
    'Flask-RESTful',
    'marshmallow',
    'python-dateutil',
    'APScheduler',
    'boto3',
    'elasticsearch',
    'flask-swagger',
    'Flask-Cors'
]
setup_requires = [
    'setuptools_scm',
    'wheel'
]
with open('README.md') as f:
    long_description = f.read()

setup(
    name='ecs-scheduler',
    use_scm_version=True,
    description='Scheduler for ECS Docker tasks',
    long_description=long_description,
    url='https://github.com/drmonkeysee/ecs-scheduler',
    author='Brandon Stansbury',
    author_email='brandonrstansbury@gmail.com',
    license='MIT',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Utilities',

        'Framework :: Flask',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3.6',
    ],
    keywords='aws ecs docker scheduler scheduling rest',
    
    packages=find_packages(exclude=['test']),
    install_requires=install_requires,
    setup_requires=setup_requires,
    test_suite='test'
)
