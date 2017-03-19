"""Demo app for testing with ECS"""
import logging
import time
import os


def run():
    """Run the demo and do useless work for ~20 seconds"""
    logging.info('Starting taskdemo...')
    logging.info('ENV: %s', os.environ)
    time.sleep(2)

    logging.info('[=>                  ] - 10% complete')
    time.sleep(5)

    logging.info('[====>               ] - 25% complete')
    time.sleep(1)

    logging.info('[=============>      ] - 70% complete')
    time.sleep(7)

    logging.info('[==================> ] - 95% complete')
    time.sleep(5)

    logging.info('[====================] - 100% complete')
    logging.info('[✔︎] taskdemo complete!')
