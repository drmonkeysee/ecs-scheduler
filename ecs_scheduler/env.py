"""ECS scheduler initialization helper methods."""
import os
import logging
import logging.handlers

from . import triggers


_logger = logging.getLogger(__name__)


def init():
    """Initialize global application state."""
    _init_logging()
    triggers.init()


def get_var(name, required=False, default=None):
    """
    Get environment variable value.

    :param name: Name of the env variable (sans ECSS_ prefix)
    :required: Raise KeyError if env variable not found
    :default: Default value if env variable not found
    """
    name = f'ECSS_{name}'
    val = os.environ[name] if required else os.getenv(name, default)
    return val.format(**os.environ) if val else val


def _init_logging():
    log_level = getattr(logging, get_var('LOG_LEVEL', default=''), None)
    log_handlers = [logging.StreamHandler()]
    log_folder = get_var('LOG_FOLDER')
    if log_folder:
        os.makedirs(log_folder, exist_ok=True)
        log_file = os.path.join(log_folder, 'app.log')
        log_handlers.append(logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=1))
    logging.basicConfig(level=log_level, handlers=log_handlers, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')
