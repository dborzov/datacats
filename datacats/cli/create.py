from string import uppercase, lowercase, digits
from random import SystemRandom

from datacats.validate import valid_name

def generate_db_password():
    """
    Return a 16-character alphanumeric random string generated by the
    operating system's secure pseudo random number generator
    """
    chars = uppercase + lowercase + digits
    return ''.join(SystemRandom().choice(chars) for x in xrange(16))

def main(opts):
    name = opts['PROJECT']
    if not valid_name(name):
        print 'Project name must consist of only lowercase letters and digits,'
        print 'must start with a letter and must be at least 5 characters long.'
        return