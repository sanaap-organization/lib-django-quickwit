import os
import sys

from django.core.management import execute_from_command_line


def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)

    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
