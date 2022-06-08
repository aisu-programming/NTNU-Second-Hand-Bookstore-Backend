''' Libraries '''
import os
import jwt
import hashlib
import logging
my_selenium_logger = logging.getLogger(name="selenium-wire")
from datetime import datetime, timedelta

from database.model import AccountEntity
from utils.exceptions import UsernameRepeatedException, \
    UsernameNotExistException, PasswordWrongException



''' Parameters '''
JWT_SECRET  = os.environ.get("JWT_SECRET")
JWT_ISSUER  = os.environ.get("JWT_ISSUER")
JWT_EXPIRE  = timedelta(days=int(os.environ.get("JWT_EXPIRE")))



''' Models '''
class Account():
    def __init__(self):
        return

    def register(self, username, password, display_name, email, phone):
        self.username = username
        # Check Username is repeated or not
        if AccountEntity.query.filter_by(username=self.username).first() is not None:
            raise UsernameRepeatedException
        AccountEntity(self.username, password, display_name, email, phone).register()
        self.entity = AccountEntity.query.filter_by(username=self.username).first()

    def login(self, username, password):
        self.username = username
        self.entity = AccountEntity.query.filter_by(username=self.username)
        if self.entity.first() is None: raise UsernameNotExistException
        password = hashlib.sha224(str.encode(password)).hexdigest()
        self.entity = self.entity.filter_by(password=password)
        if self.entity.first() is None: raise PasswordWrongException
        self.entity = self.entity.first()

    def access(self, username):
        self.username = username
        self.entity = AccountEntity.query.filter_by(username=self.username)
        if self.entity.first() is None: raise UsernameNotExistException
        self.entity = self.entity.first()

    @property
    def jwt(self):
        payload = {
            "iss"   : JWT_ISSUER,
            "exp"   : datetime.utcnow() + JWT_EXPIRE,
            "data"  : { "username": self.username }
        }
        return jwt.encode(payload, JWT_SECRET, algorithm="HS256")