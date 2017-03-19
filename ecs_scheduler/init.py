"""ECS scheduler initialization helper methods"""
import os
import logging
import logging.handlers
import yaml


def _merge_config(base, ext):
    if isinstance(base, dict) and isinstance(ext, dict):
        for k, v in base.items():
            if k not in ext:
                ext[k] = v
            else:
                ext[k] = _merge_config(v, ext[k])
    return ext


def env():
    """Set up runtime environment such as logging"""
    log_level = getattr(logging, os.getenv('LOG_LEVEL', default=''), None)
    log_handlers = [logging.StreamHandler()]
    log_folder = os.getenv('LOG_FOLDER')
    if log_folder:
        unique_folder = os.path.join(log_folder, os.getenv('HOSTNAME', default='local'))
        os.makedirs(unique_folder, exist_ok=True)
        log_file = os.path.join(unique_folder, 'app.log')
        log_handlers.append(logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=1))
    logging.basicConfig(level=log_level, handlers=log_handlers, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')


def config():
    """Discover and parse environment-specific configuration file

    :returns: a union of default and environment-specific configuration as a dictionary
    """
    with open('config/config_default.yaml') as config_file:
        config = yaml.load(config_file)

    run_env = os.getenv('RUN_ENV')
    if run_env:
        try:
            with open('config/config_{}.yaml'.format(run_env)) as env_config_file:
                env_config = yaml.load(env_config_file)
        except FileNotFoundError:
            logging.warning('No config file found for environment "%s"', run_env)
        else:
            config = _merge_config(config, env_config)

    _merge_env_vars(config)

    logging.debug('ecs scheduler config: %s', config)
    return config

def _merge_env_vars(config):
    service_name = os.getenv('SERVICE')
    if service_name:
        config['service_name'] = service_name

    sleep_time = os.getenv('SLEEP_IN_SECONDS')
    if sleep_time:
        try:
            config['scheduld']['sleep_in_seconds'] = int(sleep_time)
        except ValueError:
            logging.warning('SLEEP_IN_SECONDS env variable could not be converted to an integer: "%s"; using configured value of %s seconds instead',
                sleep_time, config['scheduld']['sleep_in_seconds'])
