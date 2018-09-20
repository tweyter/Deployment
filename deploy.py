# coding=utf-8
"""
Script for installing PHP 7.2 and deploying the server repo.
"""
import sys
import os
import json
import re
import fileinput

from fabric import Connection
from invoke import UnexpectedExit


with open('configuration2.json') as file:
    configuration = json.load(file)

SSH_PATH: str = configuration['SSH_PATH']
DIGITAL_OCEAN_PRIVATE_KEY: str = configuration['DIGITAL_OCEAN_PRIVATE_KEY']

SERVER_REPO: str = configuration['SERVER_REPO']
REPO_URL = f'git@github.com:FCView/{SERVER_REPO}.git'
SITE_FOLDER: str = configuration['SITE_FOLDER']
GITHUB_PRIVATE_KEY: str = configuration['GITHUB_PRIVATE_KEY']


STAGES = {
    'thor_server': {
        'hosts': ['test_username@104.248.55.167'],
        'code_branch': 'master',
        # ...
    },
}


def is_installed(pkg_name: str, connection: Connection) -> bool:
    """
    Check if a package is installed.
    """
    try:
        res = connection.run(f"dpkg -s {pkg_name}", warn=False)
    except UnexpectedExit as e:
        print(e.result)
        print(e.reason)
        return False
    for line in res.stdout.splitlines():
        if line.startswith("Status: "):
            status = line[8:]
            if "installed" in status.split(' '):
                return True
    return False


def install(package: str, connection: Connection) -> bool:
    """
    Install a single package.

    :return True on success, else False.
    """
    options = "--quiet --assume-yes"
    cmd = f"apt-get install {options} {package}"
    res = connection.run(cmd)
    for line in res.stdout.splitlines():
        if line.startswith("The following additional"):
            return True
        elif line.startswith(package):
            if "is already the newest version" in line:
                return True
    return False


def deploy(
        host: str='104.248.126.50',
        username: str = 'admin',
        password: str = ''
):
    """
    Main deployment function.
    """
    key = os.path.join(SSH_PATH, DIGITAL_OCEAN_PRIVATE_KEY)
    connection = Connection(
        host=host,
        user='root',
        connect_kwargs={'key_filename': key}
    )
    connection.open()
    connection.run('export DEBIAN_FRONTEND="noninteractive"')
    _install_php(connection)
    _install_packages(connection)
    _update_php_version(connection)
    _install_composer(connection)
    user_connection = _switch_to_user(username, password, connection)
    _upload_github_ssh_key(GITHUB_PRIVATE_KEY, user_connection)
    _get_latest_source(user_connection)
    _install_dependencies_via_composer(user_connection)
    _wrap_it_up(connection, user_connection)


def rexists(sftp, path):
    """os.path.exists for paramiko's SCP object
    """
    try:
        sftp.stat(path)
    except IOError as e:
        if 'No such file' in str(e):
            return False
        raise
    else:
        return True


def _upload_github_ssh_key(github_key, connection):
    """
    Place the SSH key for GitHub on the server.
    """
    sftp = connection.sftp()
    key_path = os.path.join(SSH_PATH, f"{github_key}")
    if not os.path.exists(key_path):
        msg = f'{github_key} ssh file not found on local system.'
        raise FileNotFoundError(msg)
    if rexists(sftp, f'.ssh/{github_key}'):
        return
    try:
        connection.run('mkdir .ssh')
    except UnexpectedExit:
        pass
    connection.put(key_path, '.ssh/')
    if not rexists(sftp, '.ssh/config'):
        connection.run(
            'echo "IdentityFile ~/.ssh/{}" >> ~/.ssh/config'.format(github_key)
        )


def _install_php(connection):
    """
    Install PHP 7.2 and dependencies.

    """
    connection.run("rm /boot/grub/menu.lst")
    connection.run("apt-get -y update")
    connection.run("apt-get -y upgrade")
    connection.run("apt-get -y install python-software-properties")
    connection.run("add-apt-repository -y ppa:ondrej/php")
    connection.run("add-apt-repository -y ppa:ondrej/apache2")
    connection.run("apt-get -y update")
    connection.run("apt-get -y install php7.2")


def _install_packages(connection):
    packages = [
        "php-pear",
        "php7.2-curl",
        "php7.2-dev",
        "php7.2-gd",
        "php7.2-mbstring",
        "php7.2-zip",
        "php7.2-mysql",
        "php7.2-xml",
        "php7.2-json",
        "php7.2-cli",
        "apache2",
        "libapache2-mod-php7.2",
        "git",
        "unzip",
        "curl",
    ]
    for package in packages:
        if not is_installed(package, connection):
            install(package, connection)


def _update_php_version(connection):
    """
    Switch to using the latest version of PHP.

    """
    connection.run("update-alternatives --set php /usr/bin/php7.2")
    connection.run("a2enmod php7.2")
    connection.run("systemctl restart apache2")


def _install_composer(connection):
    """
    Install composer dependency manager.
    """
    connection.run("curl -sS https://getcomposer.org/installer -o composer-setup.php")
    connection.run(
        "php composer-setup.php --install-dir="
        "/usr/local/bin --filename=composer"
    )


def _switch_to_user(
        username: str,
        password: str,
        connection: Connection,
) -> Connection:
    connection.run('sed -i "s/PasswordAuthentication no/PasswordAuthentication yes/g" /etc/ssh/sshd_config')
    connection.run('systemctl restart sshd')
    connect_kwargs = {'password': password}
    user_connection = Connection(
        host=connection.host,
        user=username,
        connect_kwargs=connect_kwargs,
    )
    user_connection.open()
    print('Admin user connection established.')
    print(f'Switched to user: {username}...')
    return user_connection


def _get_latest_source(connection):
    """
    Pull latest source from GitHub onto the server.

    """
    try:
        connection.run('ssh -T git@github.com')
    except UnexpectedExit:
        connection.run('ssh-keyscan -H github.com >> ~/.ssh/known_hosts')
    if rexists(connection.sftp(), '.git/'):
        connection.run('git fetch')
    else:
        r = connection.run('git clone {}'.format(REPO_URL))
        repo = re.search("\'(.+)\'", r.stdout)
        if repo.group() != SERVER_REPO:
            print(f'Repo name {repo.group()} does not match {SERVER_REPO}')


def _install_dependencies_via_composer(connection):
    """
    Use composer to install the PHP dependencies for the package.
    """
    connection.run(f'cd {SERVER_REPO} && composer install')


def _wrap_it_up(connection: Connection, user_connection: Connection):
    connection.run(
        f'ln -s /var/www/{SERVER_REPO} '
        f'/home/{user_connection.user}/{SERVER_REPO}'
    )
    connection.get('/etc/apache2/apache2.conf')
    edit_apache_conf(user_connection.user)
    connection.put('apache2.conf', '/etc/apache2/apache2.conf')
    connection.close()
    user_connection.close()


def edit_apache_conf(user):
    server_location = f'</Directory>\n' \
                      f'\n' \
                      f'<Directory /home/{user}/{SERVER_REPO}/>\n' \
                      f'    Options Indexes FollowSymLinks\n' \
                      f'    AllowOverride None\n' \
                      f'    Require all granted\n' \
                      f'</Directory>\n'
    with fileinput.FileInput('apache2.conf', inplace=True) as f:
        found_it = False
        replaced = False
        for line in f:
            if found_it is False and '<Directory /var/www/>' in line:
                print(line, end='')
                found_it = True
            elif found_it is True and replaced is True and '</Directory>' in line:
                print(server_location, end='')
                found_it = False
                replaced = False
            elif found_it is True and '-Indexes' in line:
                print(line.replace('Options -Indexes +FollowSymLinks', 'Options Indexes FollowSymLinks'), end='')
                replaced = True
            else:
                print(line, end='')


def main():
    args = sys.argv[1:]
    if args and len(args) == 3:
        host = args[0]
        user = args[1]
        password = args[2]
    elif args:
        raise RuntimeError('deploy.py must be run with either no arguments, or three arguments: <ip_address> <username> <password>')
    else:
        host = '104.248.123.12'
        user = 'george'
        password = 'abc123xyz'
    deploy(host, user, password)


if __name__ == '__main__':
    main()
