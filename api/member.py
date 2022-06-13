''' Libraries '''
from datetime import datetime
import logging
flask_logger = logging.getLogger(name="flask")
import hashlib
from flask import Blueprint, request

from utils.exceptions import *
from api.auth import login_required
from api.utils.rate_limit import rate_limit
from api.utils.request import Request
from api.utils.response import *
from database.model import ProductEntity, NotificationEntity



''' Settings '''
__all__ = ["member_api"]
member_api = Blueprint("member_api", __name__)



''' Functions '''
@member_api.route("/info", methods=["GET", "PATCH"])
@login_required
@rate_limit
def my_information(**kwargs):

    user = kwargs["user"].entity
    try:
        def get_info():
            return HTTPResponse("Success.", data={
                "username"   : user.username,
                "displayName": user.display_name,
                "email"      : user.email,
                "phone"      : user.phone,
            })

        @Request.json("display_name: str", "email: str", "phone: str")
        def edit_info(display_name, email, phone):
            if len(display_name) > 30: raise DataInvalidException("displayName")
            if len(email) > 30       : raise DataInvalidException("email")
            if len(phone) > 30       : raise DataInvalidException("phone")
            user.edit_information(display_name, email, phone)
            return HTTPResponse("Success.")

        methods = { "GET": get_info, "PATCH": edit_info }
        return methods[request.method]()

    except DataInvalidException as ex:
        flask_logger.warning(f"DataInvalidException: User '{user.username}' ({user.display_name}) tried to edit information.")
        return HTTPError(f"{ex} invalid.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@member_api.route("/password", methods=["PATCH"])
@login_required
@rate_limit
@Request.json("old_password: str", "new_password: str")
def change_password(old_password, new_password, **kwargs):
    
    user = kwargs["user"].entity
    try:
        if hashlib.sha224(str.encode(old_password)).hexdigest() != user.password:
            raise PasswordWrongException

        user.change_password(new_password)
        return HTTPResponse("Success.")

    except PasswordWrongException:
        flask_logger.warning(f"PasswordWrongException: User '{user.username}' ({user.display_name}) tried to change password.")
        return HTTPError("Password incorrect.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@member_api.route("/lists", methods=["GET"])
@login_required
@rate_limit
def get_my_lists(**kwargs):
    try:
        return HTTPResponse("Success.", data={
            "collection": kwargs["user"].entity.collection,
            "history"   : kwargs["user"].entity.history,
        })

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@member_api.route("/products", methods=["GET"])
@login_required
@rate_limit
def get_my_products(**kwargs):
    
    try:
        user_id  = kwargs["user"].entity.user_id
        products = ProductEntity.query.filter_by(seller_id=user_id).all()
        sold_out_products = list(filter(lambda p:     p.sold_out, products))
        not_sold_products = list(filter(lambda p: not p.sold_out, products))
        for_sale_products = list(filter(lambda p:     p.for_sale, not_sold_products))
        editing_products  = list(filter(lambda p: not p.for_sale, not_sold_products))
        for_sale_products = sorted(for_sale_products, key=lambda p: p.update_time, reverse=True)
        editing_products  = sorted(editing_products , key=lambda p: p.update_time, reverse=True)
        sold_out_products = sorted(sold_out_products, key=lambda p: p.update_time, reverse=True)

        return HTTPResponse("Success.", data={
            "forSaleProducts": [ p.overview_json for p in for_sale_products ],
            "editingProducts": [ p.overview_json for p in editing_products  ],
            "soldOutProducts": [ p.overview_json for p in sold_out_products ],
        })

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


def __product_access_check__(product, user_id):
    # Check product exist
    if product is None:
        raise ProductIdNotExistsException
    # Check product belong to the user
    if product.seller_id != user_id:
        raise ProductAccessInvalidException
    return


# 上架商品
@member_api.route("/products/launch", methods=["POST"])
@login_required
@rate_limit
@Request.json("product_id: int")
def launch_product(product_id, **kwargs):
    
    user = kwargs["user"].entity
    try:
        product = ProductEntity.query.filter_by(product_id=product_id).first()
        __product_access_check__(product, user.user_id)

        if product.for_sale and not product.sold_out:
            flask_logger.warning(f"ProductStatusError: User '{user.username}' ({user.display_name}) tried to launch product '{product_id}'.")
            return HTTPError("Product is already in for-sale status.", 403)

        product.launch()
        return HTTPResponse("Success.")

    except ProductIdNotExistsException:
        flask_logger.warning(f"ProductIdNotExists: User '{user.username}' ({user.display_name}) tried to launch product '{product_id}'.")
        return HTTPError("Product ID not exists.", 403)

    except ProductAccessInvalidException:
        flask_logger.warning(f"ProductAccessInvalid: User '{user.username}' ({user.display_name}) tried to launch product '{product_id}'.")
        return HTTPError("This product does not belong to you.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


# 下架商品
@member_api.route("/products/discontinue", methods=["POST"])
@login_required
@rate_limit
@Request.json("product_id: int")
def discontinue_product(product_id, **kwargs):
    
    user = kwargs["user"].entity
    try:
        product = ProductEntity.query.filter_by(product_id=product_id).first()
        __product_access_check__(product, user.user_id)

        if not product.for_sale:
            flask_logger.warning(f"ProductStatusError: User '{user.username}' ({user.display_name}) tried to discontinue product '{product_id}'.")
            return HTTPError("Product is already in discontinued status.", 403)

        if product.sold_out:
            flask_logger.warning(f"ProductStatusError: User '{user.username}' ({user.display_name}) tried to discontinue product '{product_id}'.")
            return HTTPError("Product is not in for-sale status.", 403)

        product.discontinue()
        return HTTPResponse("Success.")

    except ProductIdNotExistsException:
        flask_logger.warning(f"ProductIdNotExists: User '{user.username}' ({user.display_name}) tried to discontinue product '{product_id}'.")
        return HTTPError("Product ID not exists.", 403)

    except ProductAccessInvalidException:
        flask_logger.warning(f"ProductAccessInvalid: User '{user.username}' ({user.display_name}) tried to discontinue product '{product_id}'.")
        return HTTPError("This product does not belong to you.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


# 標示商品為售出
@member_api.route("/products/outofstock", methods=["POST"])
@login_required
@rate_limit
@Request.json("product_id: int")
def out_of_stock_product(product_id, **kwargs):
    
    user = kwargs["user"].entity
    try:
        product = ProductEntity.query.filter_by(product_id=product_id).first()
        __product_access_check__(product, user.user_id)

        if product.sold_out:
            flask_logger.warning(f"ProductStatusError: User '{user.username}' ({user.display_name}) tried to out-of-stock product '{product_id}'.")
            return HTTPError("Product is already in out-of-stock status.", 403)

        if not product.for_sale:
            flask_logger.warning(f"ProductStatusError: User '{user.username}' ({user.display_name}) tried to out-of-stock product '{product_id}'.")
            return HTTPError("Product is not in for-sale status.", 403)

        product.out_of_stock()
        return HTTPResponse("Success.")

    except ProductIdNotExistsException:
        flask_logger.warning(f"ProductIdNotExists: User '{user.username}' ({user.display_name}) tried to out-of-stock product '{product_id}'.")
        return HTTPError("Product ID not exists.", 403)

    except ProductAccessInvalidException:
        flask_logger.warning(f"ProductAccessInvalid: User '{user.username}' ({user.display_name}) tried to out-of-stock product '{product_id}'.")
        return HTTPError("This product does not belong to you.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@member_api.route("/products/edit", methods=["GET", "PATCH"])
@login_required
@rate_limit
def edit_product(**kwargs):

    user = kwargs["user"].entity

    def get_info(user):
        try:
            product_id = int(request.args.get("productId"))
            product = ProductEntity.query.filter_by(product_id=product_id).first()
            __product_access_check__(product, user.user_id)
            if product.for_sale:
                flask_logger.warning(f"ProductStatusError: User '{user.username}' ({user.display_name}) tried to edit product '{product_id}'.")
                return HTTPError("Product is not in discontinued status.", 403)

            return HTTPResponse("Success.", data={"details": product.detail_json})

        except ValueError:
            flask_logger.warning(f"ValueError: User '{user.username}' ({user.display_name}) tried to access edit page of product '{product_id}'.")
            return HTTPError("Requested Value With Wrong Type.", 400)

        except ProductIdNotExistsException:
            flask_logger.warning(f"ProductIdNotExists: User '{user.username}' ({user.display_name}) tried to access edit page of product '{product_id}'.")
            return HTTPError("Product ID not exists.", 403)

        except ProductAccessInvalidException:
            flask_logger.warning(f"ProductAccessInvalid: User '{user.username}' ({user.display_name}) tried to access edit page of product '{product_id}'.")
            return HTTPError("This product does not belong to you.", 403)

        except Exception as ex:
            flask_logger.error(f"Unknown exception: {str(ex)}")
            return HTTPError(str(ex), 404)

    @Request.json("product_id: int", "ISBN: str", "name: str", "price: int", "images: list",
                  "condition: int", "noted: bool", "location: str", "language: str", "extra_description: str")
    def update_info(user, product_id, ISBN, name, price, images,
                    condition, noted, location, language, extra_description):
        try:

            if len(ISBN) > 13               : raise DataInvalidException("ISBN")
            if len(name) > 30               : raise DataInvalidException("Name")
            if len(images) > 10             : raise DataInvalidException("Images")
            if len(location) > 30           : raise DataInvalidException("Location")
            if len(language) > 10           : raise DataInvalidException("Language")
            if len(extra_description) > 1000: raise DataInvalidException("Extra description")

            product = ProductEntity.query.filter_by(product_id=product_id).first()
            __product_access_check__(product, user.user_id)
            if product.for_sale:
                flask_logger.warning(f"ProductStatusError: User '{user.username}' ({user.display_name}) tried to edit product '{product_id}'.")
                return HTTPError("Product is not in discontinued status.", 403)

            product.update(ISBN, name, price, images, condition,
                           noted, location, language, extra_description)
            return HTTPResponse("Success.")

        except DataInvalidException as ex:
            flask_logger.warning(f"DataInvalidException: User '{user.username}' ({user.display_name}) tried to edit product '{product_id}'.")
            return HTTPError(f"{ex} invalid.", 403)

        except ProductIdNotExistsException:
            flask_logger.warning(f"ProductIdNotExists: User '{user.username}' ({user.display_name}) tried to edit product '{product_id}'.")
            return HTTPError("Product ID not exists.", 403)

        except ProductAccessInvalidException:
            flask_logger.warning(f"ProductAccessInvalid: User '{user.username}' ({user.display_name}) tried to edit product '{product_id}'.")
            return HTTPError("This product does not belong to you.", 403)

        except Exception as ex:
            flask_logger.error(f"Unknown exception: {str(ex)}")
            return HTTPError(str(ex), 404)

    methods = { "GET": get_info, "PATCH": update_info }
    return methods[request.method](user)


@member_api.route("/products/new", methods=["POST"])
@login_required
@rate_limit
@Request.json("ISBN: str", "name: str", "price: int", "images: list", "condition: int",
              "noted: bool", "location: str", "language: str", "extra_description: str")
def new_product(ISBN, name, price, images, condition, noted,
                location, language, extra_description, **kwargs):
    
    user = kwargs["user"].entity
    try:
        seller_id = user.user_id
        if len(ISBN) > 13               : raise DataInvalidException("ISBN")
        if len(name) > 30               : raise DataInvalidException("Name")
        if len(images) > 10             : raise DataInvalidException("Images")
        if len(location) > 30           : raise DataInvalidException("Location")
        if len(language) > 10           : raise DataInvalidException("Language")
        if len(extra_description) > 1000: raise DataInvalidException("Extra description")
        ProductEntity(ISBN, seller_id, name, price, images, condition,
                      noted, location, language, extra_description).register()
        return HTTPResponse("Success.")

    except DataInvalidException as ex:
        flask_logger.warning(f"DataInvalidException: User '{user.username}' ({user.display_name}) tried to create new product.")
        return HTTPError(f"{ex} invalid.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@member_api.route("/notifications", methods=["GET"])
@login_required
@rate_limit
def fetch_notifications(**kwargs):
    
    user = kwargs["user"].entity
    try:
        notifications = NotificationEntity.query.filter_by(user_id=user.user_id).all()

        timestamp = request.args.get("timestamp")
        if timestamp is not None:
            timestamp = int(timestamp)
            notifications = list(filter(lambda n: n.create_time.timestamp() > timestamp, notifications))

        return HTTPResponse("Success.", data={
            "notifications": [ n.json for n in notifications ],
            "timestamp"    : str(int(datetime.now().timestamp())),
        })

    except ValueError:
        flask_logger.warning(f"ValueError: User '{user.username}' ({user.display_name}) tried to fetch notifications.")
        return HTTPError("The parameter timestamp invalid.", 403)

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)} (IP '{kwargs['remote_addr']}')")
        return HTTPError(str(ex), 404)