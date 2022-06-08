''' Libraries '''
import logging
flask_logger = logging.getLogger(name="flask")
from flask import Blueprint, request

from utils.exceptions import *
from api.utils.request import Request
from api.utils.response import *
from api.utils.rate_limit import rate_limit
from api.auth import login_detect, login_required
from database.model import ProductEntity, SeenRelationship, LikesRelationship



''' Settings '''
__all__ = ["product_api"]
product_api = Blueprint("product_api", __name__)



''' Functions '''
@product_api.route("/", methods=["GET"])
@rate_limit(ip_based=True)
def get_top10_products(**kwargs):

    try:
        products = ProductEntity.query.all()
        products = list(filter(lambda p: not p.sold_out, products))
        products = list(filter(lambda p: p.for_sale, products))
        products = sorted(products, key=lambda p: p.likes, reverse=True)
        products = [ p.overview_json for p in products[:10] ]
        return HTTPResponse("Success.", data={"products": products})

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@product_api.route("/search", methods=["POST"])
@rate_limit(ip_based=True)
@Request.json("keywords: str")
def search_products(keywords, **kwargs):

    try:
        keywords = keywords.split(' ')
        products = ProductEntity.query.all()
        products_not_sold_out = list(filter(lambda p: not p.sold_out, products))
        products_is_sold_out  = list(filter(lambda p: p.sold_out, products))
        products_not_sold_out = sorted(products_not_sold_out,
            key=lambda p: sum([
                sum([ kw in p.name       for kw in keywords ]) * 100000,
                sum([ kw in p.extra_desc for kw in keywords ]) * 1000,
                p.likes * 10,
                p.views,
            ]),
            reverse=True
        )
        products_is_sold_out = sorted(products_is_sold_out,
            key=lambda p: sum([
                sum([ kw in p.name       for kw in keywords ]) * 100000,
                sum([ kw in p.extra_desc for kw in keywords ]) * 1000,
                p.likes * 10,
                p.views,
            ]),
            reverse=True
        )
        products = products_not_sold_out + products_is_sold_out
        products = [ p.overview_json for p in products ]
        return HTTPResponse("Success.", data={"products": products})

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@product_api.route("/view", methods=["GET"])
@rate_limit(ip_based=True)
@login_detect
def get_product_detail(**kwargs):

    try:
        product_id = request.args.get('productId')
        product = ProductEntity.query.filter_by(product_id=product_id).first()
        if product is None:
            flask_logger.warning(f"ProductIdNotExists: IP '{kwargs['remote_addr']}' viewed product page with product_id '{product_id}'")
            return HTTPError("Product ID not exists.", 403)

        if "user" in kwargs:
            user_id = kwargs["user"].entity.user_id
            seen = SeenRelationship.query.filter_by(user_id=user_id, product_id=product_id).first()
            if seen is None:
                SeenRelationship(user_id, product_id).register()
                seen = SeenRelationship.query.filter_by(user_id=user_id, product_id=product_id).first()
            seen.update_time()

        return HTTPResponse("Success.", data={"details": product.detail_json})

    except Exception as ex:
        flask_logger.error(f"Unknown exception: {str(ex)}")
        return HTTPError(str(ex), 404)


@product_api.route("/like", methods=["POST", "DELETE"])
@login_required
@rate_limit
@Request.json("productId: str")
def like_product(product_id, **kwargs):

    def like(user, product):
        try:
            user_id    = user.user_id
            product_id = product.product_id
            like = LikesRelationship.query.filter_by(user_id=user_id, product_id=product_id).first()
            if like is not None:
                flask_logger.warning(f"AlreadyLike: User '{user.username}' ({user.display_name}) liked product which product_id is '{product_id}'")
                return HTTPError("Already liked.", 403)
            LikesRelationship(user_id, product_id).register()
            return HTTPResponse("Success.")

        except Exception as ex:
            flask_logger.error(f"Unknown exception: {str(ex)}")
            return HTTPError(str(ex), 404)

    def unlike(user, product):
        try:
            user_id    = user.user_id
            product_id = product.product_id
            like = LikesRelationship.query.filter_by(user_id=user_id, product_id=product_id).first()
            if like is None:
                flask_logger.warning(f"NotLiked: User '{user.username}' ({user.display_name}) unliked product which product_id is '{product_id}'")
                return HTTPError("Haven't liked.", 403)
            like.remove()
            return HTTPResponse("Success.")

        except Exception as ex:
            flask_logger.error(f"Unknown exception: {str(ex)}")
            return HTTPError(str(ex), 404)

    user    = kwargs["user"].entity
    product = ProductEntity.query.filter_by(product_id=product_id).first()
    if product is None:
        like_str = { "POST": "liked", "DELETE": "unliked" }[request.method]
        flask_logger.warning(f"ProductIdNotExists: User '{user.username}' ({user.display_name}) {like_str} product which product_id is '{product_id}'")
        return HTTPError("Product ID not exists.", 403)
        
    methods = { "POST": like, "DELETE": unlike }
    return methods[request.method](user, product)