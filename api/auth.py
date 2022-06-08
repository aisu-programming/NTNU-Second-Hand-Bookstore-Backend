''' Libraries '''
import logging
flask_logger = logging.getLogger(name="flask")
from functools import wraps
from flask import Blueprint, request

from utils.exceptions import *
from api.utils.request import Request
from api.utils.response import *
from api.utils.jwt import jwt_decode
from api.utils.rate_limit import rate_limit
from api.model import Account



''' Settings '''
__all__ = ["login_detect", "login_required", "auth_api"]
auth_api = Blueprint("auth_api", __name__)



''' Functions '''
def login_detect(function):
    @wraps(function)
    @Request.cookies(vars_dict={"token": "jwt"})
    def wrapper(token, *args, **kwargs):
        if token is not None:
            json = jwt_decode(token)
            if json is None:
                return HTTPError("JWT token invalid.", 403)
            username = json["data"]["username"]
            user = Account()
            user.access(username)
            kwargs["user"] = user
        return function(*args, **kwargs)
    return wrapper


def login_required(function):
    @wraps(function)
    @Request.cookies(vars_dict={"token": "jwt"})
    def wrapper(token, *args, **kwargs):
        if token is None:
            return HTTPError("Not logged in.", 403)
        json = jwt_decode(token)
        if json is None:
            return HTTPError("JWT token invalid.", 403)
        username = json["data"]["username"]
        user = Account()
        user.access(username)
        kwargs["user"] = user
        return function(*args, **kwargs)
    return wrapper


@auth_api.route("/register", methods=["POST"])
@rate_limit(ip_based=True)
@Request.json("username: str", "password: str", "display_name: str", "email: str", "phone: str")
def register(username, password, display_name, email, phone, **kwargs):
    try:

        if len(username) >= 30                   : raise DataIncorrectException("Username")
        if len(display_name) >= 30               : raise DataIncorrectException("Display name")
        if len(email) >= 50 or ('@' not in email): raise DataIncorrectException("Email")
        if len(phone) >= 10                      : raise DataIncorrectException("Phone")

        flask_logger.info(f"IP '{kwargs['remote_addr']}' tries to register with username '{username}'.")
        Account().register(username, password, display_name, email, phone)
        flask_logger.info(f"User '{username}' ({display_name}) has successfully registered.")
        return HTTPResponse("Success.")

    except DataIncorrectException as ex:
        flask_logger.warning(f"DataIncorrectException: IP '{kwargs['remote_addr']}' / Username '{username}'")
        return HTTPError(f"{ex} invalid.", 403)

    except UsernameRepeatedException:
        flask_logger.warning(f"UsernameRepeatedException: IP '{kwargs['remote_addr']}' / Username '{username}'")
        return HTTPError("Username repeated.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: IP '{kwargs['remote_addr']}' / Username '{username}' / Message: {str(ex)}")
        print(f"Unknown exception: IP '{kwargs['remote_addr']}' / Username '{username}' / Password '{password}' / " + \
                                 f"DisplayName '{display_name}' / Email '{email}' / Phone '{phone}' / Message: {str(ex)}")
        return HTTPError(str(ex), 404)


@auth_api.route("/session", methods=["GET", "POST"])
@rate_limit(ip_based=True)
def session(**kwargs):

    def logout():
        cookies = { "jwt": None }
        return HTTPResponse("Goodbye!", cookies=cookies)

    @Request.json("username: str", "password: str")
    def login(username, password, **kwargs):
        try:
            flask_logger.info(f"IP '{kwargs['remote_addr']}' tries to login with username '{username}'.")
            user = Account()
            user.login(username, password)
            cookies = { "jwt": user.jwt }
            flask_logger.info(f"User '{username}' ({user.entity.display_name}) has successfully logged in.")
            return HTTPResponse("Success.", cookies=cookies)

        except UsernameNotExistException:
            flask_logger.warning(f"UsernameNotExistException: IP '{kwargs['remote_addr']}' / Username '{username}'")
            print(f"UsernameNotExistException: IP '{kwargs['remote_addr']}' / Username '{username}' / Password '{password}'")
            return HTTPError("Username not exist.", 403)

        except PasswordWrongException:
            flask_logger.warning(f"PasswordWrongException: IP '{kwargs['remote_addr']}' / Username '{username}'")
            print(f"PasswordWrongException: IP '{kwargs['remote_addr']}' / Username '{username}' / Password '{password}'")
            return HTTPError("Password incorrect.", 403)

        except Exception as ex:
            flask_logger.error(f"Unknown exception: IP '{kwargs['remote_addr']}' / Username '{username}' / Message: {str(ex)}")
            print(f"Unknown exception: IP '{kwargs['remote_addr']}' / Username '{username}' / Password '{password}' / Message: {str(ex)}")
            return HTTPError(str(ex), 404)

    methods = { "GET": logout(), "POST": login(**kwargs) }
    return methods[request.method]