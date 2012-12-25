
from functools import reduce

from Crypto.Cipher import AES
from Crypto.Hash import SHA256, HMAC
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random.random import getrandbits
from Crypto.Util import Counter


EXPANSION_COUNT = 1000
AES_KEY_LEN = 256
SALT_LEN = 128
HASH = SHA256
PREFIX = b'sc\x00\x00'

# lengths here are in bits, but pcrypto uses block size in bytes
HALF_BLOCK = AES.block_size*8//2
assert HALF_BLOCK <= SALT_LEN  # we use a subset of the salt as nonce



def encrypt(password, data):
    '''
    Encrypt some data.

    @param password: A string, the secret value used as the basis for a key.
     This should be as long as varied as possible.  Try to avoid common words.

    @param data: The data to be encrypted, typically as bytes.  You can pass
     in a simple string, which will be encoded as utf8.

    @return: The encrypted data, as bytes.
    '''
    _assert_encrypt_length(data)
    salt = _randbytes(SALT_LEN//8)
    key = _expand_key(salt, password)
    counter = Counter.new(HALF_BLOCK, prefix=salt[:HALF_BLOCK//8])
    cipher = AES.new(key, AES.MODE_CTR, counter=counter)
    encrypted = cipher.encrypt(data)
    hmac = HMAC.new(key, PREFIX + salt + encrypted, HASH).digest()
    return PREFIX + salt + encrypted + hmac


def decrypt(password, data):
    '''
    Decrypt some data.

    @param password: A string, the secret value used as the basis for a key.
     This should be as long as varied as possible.  Try to avoid common words.

    @param data: The data to be decrypted, typically as bytes.

    @return: The decrypted data, as bytes.
    '''
    _assert_decrypt_length(data)
    _assert_prefix(data)
    raw = data[len(PREFIX):]
    salt = raw[:SALT_LEN//8]
    key = _expand_key(salt, password)
    hmac = raw[-HASH.digest_size:]
    hmac2 = HMAC.new(key, data[:-HASH.digest_size], HASH).digest()
    _assert_hmac(hmac, hmac2)
    counter = Counter.new(HALF_BLOCK, prefix=salt[:HALF_BLOCK//8])
    cipher = AES.new(key, AES.MODE_CTR, counter=counter)
    return cipher.decrypt(raw[SALT_LEN//8:-HASH.digest_size])



class DecryptionException(Exception): pass
class EncryptionException(Exception): pass

def _assert_encrypt_length(data):
    if len(data) > 2**HALF_BLOCK:
        raise EncryptionException('Message too long')

def _assert_decrypt_length(data):
    if len(data) < len(PREFIX) + SALT_LEN//8 + HASH.digest_size:
        raise DecryptionException('Missing data')
    
def _assert_prefix(data):
    if data[:len(PREFIX)] != PREFIX:
        raise DecryptionException('Bad data format')

def _assert_hmac(hmac, hmac2):
    # https://www.isecpartners.com/news-events/news/2011/february/double-hmac-verification.aspx
    if _hash(hmac) != _hash(hmac2):
        raise DecryptionException("Bad password or corrupt / modified data")

def _expand_key(salt, password):
    if not salt: raise ValueError('Missing salt')
    if not password: raise ValueError('Missing password')
    # the form of the prf below is taken from the code for PBKDF2
    return PBKDF2(password.encode('utf8'), salt, dkLen=AES_KEY_LEN//8,
        count=EXPANSION_COUNT, prf=lambda p,s: HMAC.new(p,s,HASH).digest())

def _randbytes(n):
    return bytes(getrandbits(8) for _ in range(n))

def _hash(data):
    return HASH.new(data=data).digest()
