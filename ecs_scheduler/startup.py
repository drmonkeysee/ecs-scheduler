"""ECS scheduler initialization helper methods."""
import os
import logging
import logging.handlers

import yaml

from . import configuration
from .scheduld import triggers


_logger = logging.getLogger(__name__)


def init():
    """Initialize global application state."""
    init_env()
    init_config()
    triggers.init()


def init_env():
    """Set up runtime environment such as logging."""
    log_level = getattr(logging, os.getenv('LOG_LEVEL', default=''), None)
    log_handlers = [logging.StreamHandler()]
    log_folder = os.getenv('LOG_FOLDER')
    if log_folder:
        unique_folder = os.path.join(log_folder, os.getenv('HOSTNAME', default='local'))
        os.makedirs(unique_folder, exist_ok=True)
        log_file = os.path.join(unique_folder, 'app.log')
        log_handlers.append(logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=1))
    logging.basicConfig(level=log_level, handlers=log_handlers, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')


def init_config():
    """
    Discover and parse environment-specific configuration file.

    Sets global configuration dict at ecs_scheduler.configuration.config.
    """
    c = _load_config()
    configuration.config.update(c)


def _load_config():
    with open('config/config_default.yaml') as config_file:
        config = yaml.safe_load(config_file)

    run_env = os.getenv('RUN_ENV')
    if run_env:
        try:
            with open(f'config/config_{run_env}.yaml') as env_config_file:
                env_config = yaml.safe_load(env_config_file)
        except FileNotFoundError:
            _logger.warning('No config file found for environment "%s"', run_env)
        else:
            config = _merge_config(config, env_config)

    _merge_env_vars(config)

    _logger.debug('ecs scheduler config: %s', config)
    return config


def _merge_env_vars(config):
    # TODO: no env vars at the moment
    pass


def _merge_config(base, ext):
    if isinstance(base, dict) and isinstance(ext, dict):
        for k, v in base.items():
            if k not in ext:
                ext[k] = v
            else:
                ext[k] = _merge_config(v, ext[k])
    return ext
