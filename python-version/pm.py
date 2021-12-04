import sys
import getpass
import os.path
import pyperclip
import copy

from pathlib import Path
from hasher import Hasher
from aes import AESCipher

# Context keys.

# Operation to do.
COMMAND = 'command'
# OS user's username used to perform the operation on storage.
USERNAME = 'username'
# Password of the storage.
STORAGE_PASSWORD = 'storage_password'
# Name of the site for which the password is requested.
SITE_NAME = 'site'
# Username on the site for which the password is requested
SITE_LOGIN = 'login'
# System parameter which sets the mode of printing data to the console.
# Default mode is printing to clipboard.
SYS_PRINT_TO_CONSOLE = 'sys_ptc'

# All possible commands for the tool.
INIT = '-i'
ADD = '-a'
READ = '-r'
DELETE = '-d'
HELP = '-h'
COMMANDS = {INIT, ADD, READ, DELETE, HELP}

# User's parameters representing named arguments. These are just keys
# for some values which should be used when performing an operation.
USER_PARAMETERS = {
    '-u': USERNAME,
    '-s': SITE_NAME,
    '-l': SITE_LOGIN
}

# Optional system parameters which can be used when performing an operation.
SYS_PARAMETERS = {'-ptc'}


# Parses all information supported with the call into the context dictionary.
def parse_ctx_from_command_line(args):
    context_dict = {}
    it = iter(args)
    for arg in it:
        if arg in COMMANDS or arg in SYS_PARAMETERS:
            context_dict[COMMAND] = arg
        elif arg in USER_PARAMETERS:
            context_dict[USER_PARAMETERS[arg]] = next(it)
        else:
            print(f'Command line args parsing error: unexpected token: {arg}')
    return context_dict


# Checks if context has all necessary information for performing operation.
def ensure_ctx(ctx, *args):
    # We are functional programmers after all...
    newctx = copy.deepcopy(ctx)
    for arg in args:
        if arg not in ctx and arg == USERNAME:
            # If no username was supplied, use unix user's one.
            newctx[USERNAME] = getpass.getuser()
        elif arg not in ctx:
            # All other missing information must be provided from the input.
            newctx[arg] = input(f'{arg}: ')
    return newctx


# The absolute UNIX path to the storage of the user.
def get_storage_path(username: str) -> str:
    return os.path.join(os.environ['HOME'],
                        '.pmp',
                        Hasher.sha256(username + '_storage') + '.pst')


# Checks if there is a storage for the user with given password.
# Checks if user can access this storage.
def has_access(ctx):
    username = ctx[USERNAME]
    storage_password = ctx[STORAGE_PASSWORD]
    storage_path = get_storage_path(username)
    if Path(storage_path).exists() and Path(storage_path).is_file():
        with open(storage_path, 'r') as storage:
            written_storage_password = storage.readline().rstrip()
            return written_storage_password == Hasher.sha256(storage_password)
    else:
        print('no storage file found, aborting')
        return False


# appends newline to the end of the given string
def append_newline(s: str) -> str:
    return s + '\n'


# creates and initializes storage file
def create_storage_file(absolute_storage_path: str, storage_password: str):
    root_dir = os.path.dirname(absolute_storage_path)
    if not Path(root_dir).exists():
        Path(root_dir).mkdir()
    Path(absolute_storage_path).touch()
    with open(absolute_storage_path, 'a') as storage_file:
        storage_file.write(append_newline(Hasher.sha256(storage_password)))
        print('done')


def init_storage(ctx):
    username = ctx[USERNAME]
    storage_password = ctx[STORAGE_PASSWORD]
    absolute_storage_path = get_storage_path(username)
    if Path(absolute_storage_path).exists():
        print('storage already exists, are you sure you want to overwrite it? (y/N)', end=' ')
        overwrite = input()
        if overwrite != 'y':
            print('aborting')
            return
    create_storage_file(absolute_storage_path, storage_password)
    print('storage initialized for user ' + username)


# Prompts user's password hiding echo to unix console.
def prompt_password():
    site_password = getpass.getpass('site password: ')
    confirm_site_password = getpass.getpass('confirm site password: ')
    return site_password, confirm_site_password


def add_password(ctx):
    username = ctx[USERNAME]
    storage_password = ctx[STORAGE_PASSWORD]
    site = ctx[SITE_NAME]
    # Here getting input from context is not possible as it must be double-checked.
    # Because of this, regular input prompt is used.
    site_password, confirm_site_password = prompt_password()
    if site_password == confirm_site_password:
        storage_path = get_storage_path(username)
        with open(storage_path, 'a+') as storage_file:
            cipher = AESCipher(storage_password)
            # both site name and site password are encrypted
            storage_file.write(append_newline(cipher.encrypt(site)))
            storage_file.write(append_newline(cipher.encrypt(site_password)))
            print('done')
    else:
        print('passwords don\'t match')


def read_password(ctx):
    username = ctx[USERNAME]
    storage_password = ctx[STORAGE_PASSWORD]
    site = ctx[SITE_NAME]
    cipher = AESCipher(storage_password)
    absolute_storage_path = get_storage_path(username)
    with open(absolute_storage_path, 'r') as storage_file:
        # skip the first line with storage password
        storage_file.readline()
        while True:
            encrypted_site = storage_file.readline().rstrip()
            encrypted_password = storage_file.readline().rstrip()
            if not encrypted_site or not encrypted_password:
                return 'couldn\'t find password', ''
            # decrypt each site name and check if it is the same as requested
            if site == cipher.decrypt(encrypted_site):
                decrypted_password = cipher.decrypt(encrypted_password)
                return None, decrypted_password


def delete_password(ctx):
    username = ctx[USERNAME]
    storage_password = ctx[STORAGE_PASSWORD]
    site = ctx[SITE_NAME]
    cipher = AESCipher(storage_password)
    absolute_storage_path = get_storage_path(username)
    storage_file = open(absolute_storage_path, 'r+')
    storage_data = storage_file.readlines()
    storage_file.close()
    # skip the first line with hashed password
    passwords_data = storage_data[1:]
    # group elements in chunks of size 2, so that data is logically grouped in pairs (site, password)
    passwords_tuples = [passwords_data[i:i + 2] for i in range(0, len(passwords_data), 2)]
    # remove the password which site's name is equal to the provided
    new_passwords = [t for t in passwords_tuples if cipher.decrypt(t[0].rstrip()) != site]
    if len(new_passwords) != len(passwords_tuples):
        Path(absolute_storage_path).unlink()
        # write updated passwords to the file
        create_storage_file(absolute_storage_path, storage_password)
        with open(absolute_storage_path, 'a') as storage_file:
            for password_tuple in new_passwords:
                storage_file.write(password_tuple[0])
                storage_file.write(password_tuple[1])
        print('password deleted')
    else:
        print('couldn\'t find password for the specified site')


def print_help():
    print("""+++++++++++++++++++++++++++++++++++++++++++++++
    + |¯¯| |\\/|   /\\   |\\  |   /\\   |¯¯| |¯¯ |¯\\  +
    + |__| |  |  /__\\  | \\ |  /__\\  | _  |-  |_/  +
    + |    |  | /    \\ |  \\| /    \\ |__| |__ | \\  +
    +++++++++++++++++++++++++++++++++++++++++++++++
    pmanager is a command line tool for securely storing and accessing passwords. 
    pmanager keeps all passwords and their context encrypted using symmetrical encryption with master password
    serving as the encryption key.

    "python3 pm.py -i"                       - initialize password storage for the user defined in env variable $USER
    "python3 pm.py -a <optional: site name>" - append password for the site name to the existing
                                               storage of the current user. If site name is not
                                               passed as a command line argument, you will be
                                               prompted to enter it
    "python3 pm.py -r <optional: site name>" - read password for the site, and write it to the clipboard. 
                      <optional: -ptc>         If flag "ptc" is set, prints password to the stdout!
    "python3 pm.py -d <optional: site name>  - delete password for the site from storage. 
                                               This is irreversible operation
    "python3 pm.py -h"                       - print this help""")


# Main function handles all the business logic of the application.
def main():
    ctx = parse_ctx_from_command_line(sys.argv[1:])
    ctx = ensure_ctx(ctx, COMMAND)
    if ctx[COMMAND] == INIT:
        ctx = ensure_ctx(ctx, USERNAME, STORAGE_PASSWORD)
        init_storage(ctx)
    elif ctx[COMMAND] == ADD:
        ctx = ensure_ctx(ctx, USERNAME, STORAGE_PASSWORD, SITE_NAME)
        if not has_access(ctx):
            print('access denied')
            return
        add_password(ctx)
    elif ctx[COMMAND] == READ:
        ctx = ensure_ctx(ctx, USERNAME, STORAGE_PASSWORD, SITE_NAME)
        if not has_access(ctx):
            print('access denied')
            return
        err, decrypted_password = read_password(ctx)
        if err is not None:
            print(err)
            return
        # If flag -ptc is set, then print decrypted password to the console.
        if SYS_PRINT_TO_CONSOLE in ctx:
            print(decrypted_password)
        else:
            # Copy decrypted password to the clipboard.
            pyperclip.copy(decrypted_password)
            print('copied to clipboard')
    elif ctx[COMMAND] == DELETE:
        ctx = ensure_ctx(ctx, USERNAME, STORAGE_PASSWORD)
        if not has_access(ctx):
            print('access denied')
            return
        delete_password(ctx)
    elif ctx[COMMAND] == HELP:
        print_help()
    else:
        print(f'Unexpected command: {ctx[COMMAND]}')
        print_help()


# Runs main() only when module is being run directly
if __name__ == '__main__':
    main()