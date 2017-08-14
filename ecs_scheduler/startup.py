"""ECS scheduler initialization helper methods."""
import os
import logging
import logging.handlers

from .scheduld import triggers


_logger = logging.getLogger(__name__)


def init():
    """Initialize global application state."""
    init_env()
    triggers.init()


def init_env():
    """Set up runtime environment such as logging."""
    log_level = getattr(logging, os.getenv('LOG_LEVEL', default=''), None)
    log_handlers = [logging.StreamHandler()]
    log_folder = os.getenv('LOG_FOLDER')
    if log_folder:
        # TODO: allow addition of hostname without forcing it
        unique_folder = os.path.join(log_folder, os.getenv('HOSTNAME', default='local'))
        os.makedirs(unique_folder, exist_ok=True)
        log_file = os.path.join(unique_folder, 'app.log')
        log_handlers.append(logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=1))
    logging.basicConfig(level=log_level, handlers=log_handlers, format='%(levelname)s:%(name)s:%(asctime)s %(message)s')
