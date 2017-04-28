import ecs_scheduler.main


application = ecs_scheduler.main.create_app()


def main():
    """Production launch entry point."""
    application.run(host='0.0.0.0', use_evalex=False)


# TODO: remove this once it becomes an entry_point script (or invoked by uWSGI?)
if __name__ == '__main__':
    main()
