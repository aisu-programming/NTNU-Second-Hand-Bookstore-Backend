''' Libraries '''
import pytz
import hashlib
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import \
    TINYINT, SMALLINT, VARCHAR, TEXT, CHAR, BOOLEAN, DATETIME, ENUM, JSON



''' Models '''
TZ_TW = pytz.timezone("Asia/Taipei")
db = SQLAlchemy()

class Connection(db.Model):
    __tablename__ = 'connections'
    connection_id = Column(SMALLINT(unsigned=True), primary_key=True)
    target        = Column(VARCHAR(39), nullable=False, unique=True)  # Length of IPv6 = 39
    target_type   = Column(ENUM("IP", "username"), nullable=False)
    banned_turn   = Column(TINYINT(unsigned=True), default=0)
    accept_time   = Column(DATETIME)
    records       = Column(JSON)

    def __init__(self, target, target_type):
        self.target      = target
        self.target_type = target_type
        self.records     = [ datetime.now().timestamp() ]

    def register(self):
        db.session.add(self)
        db.session.commit()
        return

    def access(self):
        last_second = datetime.now() - timedelta(seconds=1)
        self.records = list(filter(lambda d: d >= last_second.timestamp(), self.records))
        self.records.append(datetime.now().timestamp())
        db.session.commit()
        return

    def ban(self):
        self.records = []
        self.banned_turn += 1
        self.accept_time = datetime.now() + timedelta(hours=1)
        db.session.commit()
        return

    def unban(self):
        self.records.append(datetime.now().timestamp())
        self.accept_time = None
        db.session.commit()
        return


class AccountEntity(db.Model):
    __tablename__ = "account"
    user_id                 = Column(SMALLINT(unsigned=True),  primary_key=True)
    username                = Column(VARCHAR(30), unique=True, nullable=False)
    password                = Column(TEXT(256),                nullable=False)
    display_name            = Column(VARCHAR(30),              nullable=False)
    email                   = Column(VARCHAR(50),              nullable=False)
    phone                   = Column(CHAR(10),                 nullable=False)
    role                    = Column(ENUM("User", "Admin"),    default="User")
    create_time             = Column(DATETIME)

    def __init__(self, username, password, display_name, email, phone):
        self.username     = username
        self.password     = hashlib.sha224(str.encode(password)).hexdigest()
        self.display_name = display_name
        self.email        = email
        self.phone        = phone

    def register(self):
        self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    def update_password(self, password):
        self.password = hashlib.sha224(str.encode(password)).hexdigest()
        db.session.commit()
        return

    def update_data(self, display_name, email, phone):
        self.display_name = display_name
        self.email        = email
        self.phone        = phone
        db.session.commit()
        return

    def json(self):
        collection = [
            ProductEntity.query.filter_by(product_id=likes.product_id).first().json()
            for likes in LikesRelationship.query.filter_by(user_id=self.user_id).all()
        ]
        history    = [  ]
        return {
            "username"   : self.username,
            "displayName": self.display_name,
            "email"      : self.email,
            "phone"      : self.phone,
            "collection" : collection,
            "history"    : history,
            "role"       : self.role,
            "create_time": self.create_time,
        }


class BookEntity(db.Model):
    __tablename__ = "book"
    book_id = Column(SMALLINT(unsigned=True), primary_key=True)
    ISBN    = Column(VARCHAR(13), nullable=False, unique=True)

    def __init__(self, ISBN):
        self.ISBN = ISBN

    def register(self):
        db.session.add(self)
        db.session.commit()
        return


class ProductEntity(db.Model):
    __tablename__ = "product"
    product_id   = Column(SMALLINT(unsigned=True), primary_key=True)
    book_id      = Column(SMALLINT(unsigned=True), nullable=False, unique=True)  # BookEntity.book_id
    seller_id    = Column(SMALLINT(unsigned=True), nullable=False)  # AccountEntity.user_id
    name         = Column(VARCHAR(30),             nullable=False)
    price        = Column(TINYINT(unsigned=True),  nullable=False)
    # likes
    # views
    images       = Column(JSON)
    for_sale     = Column(BOOLEAN)
    sold_out     = Column(BOOLEAN)
    condition    = Column(TINYINT(unsigned=True),  nullable=False)
    noted        = Column(BOOLEAN)
    location     = Column(VARCHAR(30),             nullable=False)
    language     = Column(VARCHAR(10),             nullable=False)
    extra_desc   = Column(VARCHAR(10),             nullable=False)
    comments     = Column(JSON)  # A list of CommentEntity.comment_id
    create_time  = Column(DATETIME)
    # tags         = Column(JSON)

    def __init__(
        self, ISBN, seller_id, name, price, images, for_sale,
        sold_out, condition, noted, location, language, extra_desc
    ):
        self.book = BookEntity.query.filter_by(ISBN=ISBN).first()
        if self.book is None:
            self.book = BookEntity(ISBN)
            self.book.register()
            self.book = BookEntity.query.filter_by(ISBN=ISBN).first()
        self.book_id    = self.book.book_id
        self.seller_id  = seller_id
        self.name       = name
        self.price      = price
        self.images     = images
        self.for_sale   = for_sale
        self.sold_out   = sold_out
        self.condition  = condition
        self.noted      = noted
        self.location   = location
        self.language   = language
        self.extra_desc = extra_desc
        self.comments   = []

    def register(self):
        self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    def add_comment(self, user, content):
        comment = CommentEntity(user, content)
        comment.register()
        self.comments.append(comment.comment_id)
        db.session.commit()
        return

    @property
    def seller(self):
        return AccountEntity.query.filter_by(user_id=self.seller_id).first()

    @property
    def likes(self):
        return len(LikesRelationship.query.filter_by(product_id=self.product_id).all())

    @property
    def views(self):
        return len(SeenRelationship.query.filter_by(product_id=self.product_id).all())

    @property
    def comments(self):
        return [
            CommentEntity.query.filter_by(comment_id=cid).first().json()
            for cid in self.comments
        ]

    @property
    def overview_json(self):
        return {
            "productId"        : self.product_id,
            "sellerDisplayName": self.seller.display_name,
            "name"             : self.name,
            "price"            : self.price,
            "likes"            : self.likes,
            "views"            : self.views,
            "images"           : self.images,
            "soldOut"          : self.sold_out,
            "extraDescription" : self.extra_desc,
        }

    @property
    def detail_json(self):
        return {
            "productId"        : self.product_id,
            "ISBN"             : self.book.ISBN,
            "sellerDisplayName": self.seller.display_name,
            "name"             : self.name,
            "price"            : self.price,
            "likes"            : self.likes,
            "views"            : self.views,
            "images"           : self.images,
            "forSale"          : self.for_sale,
            "soldOut"          : self.sold_out,
            "condition"        : self.condition,
            "noted"            : self.noted,
            "location"         : self.location,
            "language"         : self.language,
            "extraDescription" : self.extra_desc,
            "comments"         : self.comments,
            "createTime"       : self.create_time,
        }


class CommentEntity(db.Model):
    __tablename__ = "comment"
    comment_id  = Column(SMALLINT(unsigned=True), primary_key=True)
    user        = Column(SMALLINT(unsigned=True), nullable=False)  # user_id
    content     = Column(VARCHAR(100),            nullable=False)
    create_time = Column(DATETIME,                nullable=False)

    def __init__(self, user, content):
        self.user    = user
        self.content = content

    def register(self):
        self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    @property
    def json(self):
        user = AccountEntity.query.filter_by(user_id=self.user).first()
        return {
            "displayName": user.display_name,
            "content"    : self.content,
            "commentTime": self.create_time,
        }


class NotificationEntity(db.Model):
    __tablename__ = "notification"
    notification_id = Column(SMALLINT(unsigned=True), primary_key=True)
    user            = Column(SMALLINT(unsigned=True), nullable=False)  # user_id
    read            = Column(BOOLEAN,                 nullable=False)
    content         = Column(VARCHAR(100),            nullable=False)
    create_time     = Column(DATETIME,                nullable=False)

    def __init__(self, user, content):
        self.user    = user
        self.read    = False
        self.content = content

    def register(self):
        self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    @property
    def json(self):
        return {
            "read"      : self.read,
            "content"   : self.content,
            "createTime": self.create_time,
        }


class SeenRelationship(db.Model):
    __tablename__ = "seen"
    user_id     = Column(SMALLINT(unsigned=True), primary_key=True)
    product_id  = Column(SMALLINT(unsigned=True), primary_key=True)
    recent_time = Column(DATETIME)
    create_time = Column(DATETIME)

    def __init__(self, user_id, product_id):
        self.user_id    = user_id
        self.product_id = product_id

    def register(self):
        self.recent_time = datetime.now()
        self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    def update_time(self):
        self.recent_time = datetime.now()
        db.session.commit()
        return


class LikesRelationship(db.Model):
    __tablename__ = "likes"
    user_id     = Column(SMALLINT(unsigned=True), primary_key=True)
    product_id  = Column(SMALLINT(unsigned=True), primary_key=True)
    create_time = Column(DATETIME)

    def __init__(self, user_id, product_id):
        self.user_id    = user_id
        self.product_id = product_id

    def register(self):
        self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return