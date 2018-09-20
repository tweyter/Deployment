SERVER CREATION AND DEPLOYMENT

In order to run these programs, Python 3.6 or higher must be installed.
The most recent Python version is 3.7, which will work fine.
To install, go to https://www.python.org/downloads/ and click on the
download link.
You can then follow the instructions given here: https://www.ics.uci.edu/~pattis/common/handouts/pythoneclipsejava/python.html

Once Python is installed and can be run from the command line (Powershell, etc.)
then go to the command line and upgrade Python's package installer. To do so, type:

python -m pip install --upgrade pip

Once that is done, change to the directory where
this package is installed. When you are in the same directory as the
requirements.txt file, type the following:

pip install -r requirements.txt

In order to run these programs, the configuration.json program must be filled out.
The following components are initially blank and must be filled in by you:

Special Note for SSH path: For any path such as SSH_PATH, make sure backslashes are escaped using "\\"
or simply use a forward slash as the directory separator.

Special Note for DIGITAL_OCEAN_KEY: You must use PuTTYGEN to create an OpenSSH compatible public key file.
To do this, open your .ppk key file in Puttygen, and as long as it's a recent verion, it should
display the public key in a window. Copy this and paste it into a new file named for the key
(such as id_rsa.pub)  Also, the program assumes that both DIGITAL_OCEAN_KEY and GITHUB_KEY are in the same
directory so make sure they're stored in the SSH_PATH directory.

Special note for GITHUB_KEY: This is your PRIVATE key. It will be copied onto the server so that the server can
clone the repository. In order to make an OpenSSH compatible private key, open your .ppk key file in Puttygen
and in the Conversions dropdown menu select Export OpenSSH key. Make sure to save this in the same directory
as your DIGITAL_OCEAN_KEY.

  "SSH_PATH": The path to your SSH public key files.
	Example: "C:\\path\\to\\deployment_package_directory"
	
  "DIGITAL_OCEAN_KEY": The name of your SSH public key file used for Digital Ocean
  "DIGITAL_OCEAN_TOKEN": The API token given to you by the Digital Ocean website.
  "GITHUB_KEY" : The name of your SSH private key file used by GitHub.

After that, you can run either the create.py or deploy.py programs by typing either:
python create.py
or
python deploy.py <ip_address> <admin_username>
where <ip_address> is the IP Address of the server and
<admin_username> is the username that you created. Both of these
values should be in the droplet_data.txt file that was created by running
create.py
