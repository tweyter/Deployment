import os
import json

from fabric import task, Connection
import create


with open('configuration.json') as file:
    configuration = json.load(file)

SSH_PATH: str = configuration['SSH_PATH']
DIGITAL_OCEAN_PRIVATE_KEY: str = configuration['DIGITAL_OCEAN_PRIVATE_KEY']


@task
def new_user():
    ip_address = input('Please enter the ip address of the server:')
    admin_username = input('Please enter a username for the new admin:')
    key_path = os.path.join(SSH_PATH, DIGITAL_OCEAN_PRIVATE_KEY)

    connection = Connection(
        host=ip_address,
        user='root',
        connect_kwargs={'key_filename': key_path}
    )
    create.new_user(admin_username, connection)
    return
