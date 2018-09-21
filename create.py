# coding=utf-8
"""
Script for creating a new Digital Ocean droplet.
"""
import os
import json
import string
import secrets
from typing import List, Tuple

from fabric import Connection
from invoke import UnexpectedExit
from paramiko.ssh_exception import NoValidConnectionsError
import digitalocean

from deploy import deploy


with open('configuration.json') as file:
    configuration = json.load(file)

SSH_PATH: str = configuration['SSH_PATH']
DIGITAL_OCEAN_PUBLIC_KEY: str = configuration['DIGITAL_OCEAN_PUBLIC_KEY']
DIGITAL_OCEAN_PRIVATE_KEY: str = configuration['DIGITAL_OCEAN_PRIVATE_KEY']
DIGITAL_OCEAN_TOKEN: str = configuration['DIGITAL_OCEAN_TOKEN']


def create():
    """
    Create a new Digital Ocean droplet and then deploy the php server code.

    For example: Typing "fab create BobServer nyc1 s-1vcpu-1gb" on the command
    line will create a new Digital Ocean Droplet named "BobServer" in
    the NYC1 region, with a size of 512mb. It will automatically pull
    your ssh keys and store the public keys on the new server so that
    you can access it as root right away.


    """
    manager = digitalocean.Manager(token=DIGITAL_OCEAN_TOKEN)
    current_names = _get_current_droplets(manager)
    username, name, region, size_slug = _get_parameters(current_names)

    ssh_keys = _create_ssh_keys(manager)
    droplet = digitalocean.Droplet(
        token=DIGITAL_OCEAN_TOKEN,
        name=name,
        region=region,
        image='ubuntu-16-04-x64',
        size_slug=size_slug,
        ssh_keys=ssh_keys,
        backups=False,
    )
    print('Creating droplet...')
    droplet.create()
    print('Verifying...')
    actions = droplet.get_actions()
    for action in actions:
        status = ''
        while status != 'completed':
            action.load()
            status = action.status
            # Once it shows completed, droplet is up and running
            print(action.status)
    droplet.load()
    if not droplet.id:
        raise ValueError('Droplet creation failed. No ID.')
    info = f'{droplet.name} ip_address: {droplet.ip_address}'
    print(f'Droplet created: {info}')
    with open('droplet_data.txt', 'w') as file:
        file.write(info + '\n')
    if not droplet.ip_address:
        raise ValueError('Droplet creation failed. No ip address registered.')
    key_path = os.path.join(SSH_PATH, DIGITAL_OCEAN_PRIVATE_KEY)
    connection = Connection(
        host=droplet.ip_address,
        user='root',
        connect_kwargs={'key_filename': key_path}
    )
    try:
        connection.open()
    except (TimeoutError, NoValidConnectionsError):
        connection.open()
    username, password = new_user(username, connection)
    with open('droplet_data.txt', 'a') as f:
        f.writelines([
            f'username: {username}  group: admin  password: {password}',
            'sudo privileges granted.',
        ])
    return droplet.ip_address, username, password


def _get_current_droplets(manager: digitalocean.Manager) -> List[str]:
    """
    Get a list of the current droplets to make sure the same name will not
    be used twice.

    :return: List of current droplet names.
    """
    droplets = manager.get_all_droplets()
    names = [x.name for x in droplets]
    return names


def _get_parameters(current_names: List[str]):
    """
    Get parameters from the user and verify that they are of the correct
    format.

    :return: user name, server name, server region, and size slug.
    """
    while True:
        username = input("Administrator username:")
        if not username:
            print("You must enter a name for the admin user.")
            print("There are some installations that can not be done as root.")
        else:
            break

    while True:
        name = input("New server name:")
        if not name:
            print('You must enter a name for the new server.')
        elif name in current_names:
            print(f'The name {name} is already in use. Please select another.')
        else:
            break
    available_regions = (
        'AMS2',
        'AMS3',
        'BLR1',
        'FRA1',
        'LON1',
        'NYC1',
        'NYC2',
        'NYC3',
        'SFO1',
        'SFO2',
        'SGP1',
        'TOR1',
    )
    default = "nyc1"
    region = input("Region: [{}]".format(default))
    if region == '':
        region = "nyc1"
    if region.upper() not in available_regions:
        msg = 'Region must be one of the following list: {}'.format(
            ', '.join(available_regions)
        )
        raise ValueError(msg)
    default = "s-1vcpu-1gb"
    size_slug = input("Size slug: [{}]".format(default))
    if size_slug == '':
        size_slug = default
    if not size_slug:
        msg = 'You must enter an appropriate size slug.'
        raise ValueError(msg)
    return username, name, region, size_slug


def _create_ssh_keys(manager: digitalocean.Manager) -> List[digitalocean.SSHKey]:
    """
    Upload a ssh public key to Digital Ocean, if not already loaded.

    If it is already loaded, then just get the id.

    :return: List of SSHkey objects.
    """
    registered_keys = manager.get_all_sshkeys()
    ssh_keys = []
    print('Registering SSH keys...')
    print('Known keys:')
    print('\n'.join([key.name for key in registered_keys]))
    key = DIGITAL_OCEAN_PUBLIC_KEY
    print(f'Checking key: {key}')
    with open(os.path.join(SSH_PATH, f"{key}")) as file:
        public_key = file.read().rstrip('\n')
    registered = [rkey for rkey in registered_keys if rkey.public_key == public_key]
    for rkey in registered_keys:
        if rkey.public_key == public_key:
            ssh_keys.append(registered[0])
            print(
                f'SSH key {key} verified already registered as '
                f'{registered[0].name}.')
            break
    else:
        key = digitalocean.SSHKey(
            name=key,
            public_key=public_key,
            token=DIGITAL_OCEAN_TOKEN,
        )
        key.create()
        ssh_keys.append(key)
        print(f'SSH key {key} has now been registered with name {key.name}')
    return ssh_keys


def new_user(admin_username, connection) -> Tuple[str, str]:
    """
    Create a new user.

    :param admin_username: The username to be created.
    :param connection: The Fabric Connection object.
    """

    # Create the admin group and add it to the sudoers file
    admin_group = 'admin'
    try:
        connection.run('addgroup {group}'.format(group=admin_group), warn=True)
    except UnexpectedExit:
        pass

    connection.run('echo "%{group} ALL=(ALL) ALL" >> /etc/sudoers'.format(
        group=admin_group))

    # Create the new admin user (default group=username); add to admin group
    connection.run('adduser {username} --disabled-password --gecos ""'.format(
        username=admin_username))
    connection.run('adduser {username} {group}'.format(
        username=admin_username,
        group=admin_group))

    # Generate a 40 character alphanumeric password
    alphabet = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(alphabet) for i in range(40))
    # Set the password for the new admin user
    connection.run('echo "{password}\n{password}" | passwd {username}'.format(
        password=password,
        username=admin_username
    ))
    # Grant sudo privileges
    connection.run('usermod -aG sudo {username}'.format(
        username=admin_username,
    ))
    return admin_username, password


def main():
    ip_address, username, password = create()
    deploy(ip_address, username, password)


if __name__ == '__main__':
    main()
