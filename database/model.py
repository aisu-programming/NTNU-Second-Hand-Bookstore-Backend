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
    user_id      = Column(SMALLINT(unsigned=True),  primary_key=True)
    username     = Column(VARCHAR(30), unique=True, nullable=False)
    password     = Column(TEXT(256),                nullable=False)
    display_name = Column(VARCHAR(30),              nullable=False)
    email        = Column(VARCHAR(50),              nullable=False)
    phone        = Column(CHAR(10),                 nullable=False)
    role         = Column(ENUM("User", "Admin"),    default="User")
    create_time  = Column(DATETIME,                 default=datetime.now)

    def __init__(self, username, password, display_name, email, phone):
        self.username     = username
        self.password     = hashlib.sha224(str.encode(password)).hexdigest()
        self.display_name = display_name
        self.email        = email
        self.phone        = phone

    def register(self):
        # self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    def change_password(self, password):
        self.password = hashlib.sha224(str.encode(password)).hexdigest()
        db.session.commit()
        return

    def edit_information(self, display_name, email, phone):
        self.display_name = display_name
        self.email        = email
        self.phone        = phone
        db.session.commit()
        return

    @property
    def collection(self):
        likes = LikesRelationship.query.filter_by(user_id=self.user_id).all()
        likes = sorted(likes, key=lambda l: l.create_time, reverse=True)
        return [
            ProductEntity.query.filter_by(product_id=like.product_id).first().overview_json
            for like in likes
        ]

    @property
    def history(self):
        seens = SeenRelationship.query.filter_by(user_id=self.user_id).all()
        seens = sorted(seens, key=lambda s: s.recent_time, reverse=True)
        return [
            ProductEntity.query.filter_by(product_id=seen.product_id).first().overview_json
            for seen in seens
        ]

    # @property
    # def json(self):
    #     return {
    #         "username"   : self.username,
    #         "displayName": self.display_name,
    #         "email"      : self.email,
    #         "phone"      : self.phone,
    #         "collection" : self.collection,
    #         "history"    : self.history,
    #         "role"       : self.role,
    #         "create_time": self.create_time,
    #     }


class BookEntity(db.Model):
    __tablename__ = "book"
    book_id      = Column(SMALLINT(unsigned=True), primary_key=True)
    ISBN         = Column(VARCHAR(13), nullable=False, unique=True)
    create_time  = Column(DATETIME, default=datetime.now)

    def __init__(self, ISBN):
        self.ISBN = ISBN

    def register(self):
        # self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return


class ProductEntity(db.Model):
    __tablename__ = "product"
    product_id   = Column(SMALLINT(unsigned=True), primary_key=True)
    book_id      = Column(SMALLINT(unsigned=True), nullable=False, unique=True)  # BookEntity.book_id
    seller_id    = Column(SMALLINT(unsigned=True), nullable=False)  # AccountEntity.user_id
    name         = Column(VARCHAR(30),             nullable=False)
    price        = Column(SMALLINT(unsigned=True), nullable=False)
    # likes
    # views
    images       = Column(JSON)
    for_sale     = Column(BOOLEAN)
    sold_out     = Column(BOOLEAN)
    condition    = Column(TINYINT(unsigned=True),  nullable=False)
    noted        = Column(BOOLEAN)
    location     = Column(VARCHAR(30),             nullable=False)
    language     = Column(VARCHAR(10),             nullable=False)
    extra_desc   = Column(VARCHAR(1000),           nullable=False)
    comments     = Column(JSON)  # A list of CommentEntity.comment_id
    update_time  = Column(DATETIME,                default=datetime.now)  # , onupdate=datetime.now)
    create_time  = Column(DATETIME,                default=datetime.now)
    # tags         = Column(JSON)

    def __init__(self, ISBN, seller_id, name, price, images, 
                 condition, noted, location, language, extra_desc):
        book = BookEntity.query.filter_by(ISBN=ISBN).first()
        if book is None:
            book = BookEntity(ISBN)
            book.register()
            book = BookEntity.query.filter_by(ISBN=ISBN).first()
        self.book_id    = book.book_id
        self.seller_id  = seller_id
        self.name       = name
        self.price      = price
        self.images     = images
        self.for_sale   = False
        self.sold_out   = False
        self.condition  = condition
        self.noted      = noted
        self.location   = location
        self.language   = language
        self.extra_desc = extra_desc
        self.comments   = []

    def register(self):
        # self.update_time = datetime.now()
        # self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    def add_comment(self, user_id, content):
        comment = CommentEntity(user_id, content)
        comment.register()
        self.comments = self.comments + [ comment.comment_id ]
        db.session.commit()
        return

    def launch(self):
        self.for_sale = True
        self.sold_out = False
        self.update_time = datetime.now()
        db.session.commit()
        return

    def discontinue(self):
        self.for_sale = False
        self.update_time = datetime.now()
        db.session.commit()
        return

    def out_of_stock(self):
        self.sold_out = True
        self.update_time = datetime.now()
        db.session.commit()
        return

    def update(self, ISBN, name, price, images, condition,
               noted, location, language, extra_desc):
        book = BookEntity.query.filter_by(ISBN=ISBN).first()
        if book is None:
            book = BookEntity(ISBN)
            book.register()
            book = BookEntity.query.filter_by(ISBN=ISBN).first()
        self.book_id    = book.book_id
        self.name       = name
        self.price      = price
        self.images     = images
        self.condition  = condition
        self.noted      = noted
        self.location   = location
        self.language   = language
        self.extra_desc = extra_desc
        self.update_time = datetime.now()
        db.session.commit()
        return

    @property
    def book(self):
        return BookEntity.query.filter_by(book_id=self.book_id).first()

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
    def comments_json(self):
        return [
            CommentEntity.query.filter_by(comment_id=cid).first().json
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
            "comments"         : self.comments_json,
            "createTime"       : self.create_time,
            "updateTime"       : self.update_time,
        }


class CommentEntity(db.Model):
    __tablename__ = "comment"
    comment_id  = Column(SMALLINT(unsigned=True), primary_key=True)
    user_id     = Column(SMALLINT(unsigned=True), nullable=False)  # user_id
    content     = Column(VARCHAR(100),            nullable=False)
    create_time = Column(DATETIME,                default=datetime.now)

    def __init__(self, user_id, content):
        self.user_id = user_id
        self.content = content

    def register(self):
        # self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    @property
    def json(self):
        user = AccountEntity.query.filter_by(user_id=self.user_id).first()
        return {
            "displayName": user.display_name,
            "content"    : self.content,
            "commentTime": self.create_time,
        }


class NotificationEntity(db.Model):
    __tablename__ = "notification"
    notification_id = Column(SMALLINT(unsigned=True), primary_key=True)
    user_id         = Column(SMALLINT(unsigned=True), nullable=False)  # user_id
    read            = Column(BOOLEAN,                 nullable=False)
    content         = Column(VARCHAR(100),            nullable=False)
    create_time     = Column(DATETIME,                default=datetime.now)

    def __init__(self, user_id, content):
        self.user_id = user_id
        self.read    = False
        self.content = content

    def register(self):
        # self.create_time = datetime.now()
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
    recent_time = Column(DATETIME,                default=datetime.now)
    create_time = Column(DATETIME,                default=datetime.now)

    def __init__(self, user_id, product_id):
        self.user_id    = user_id
        self.product_id = product_id

    def register(self):
        # self.recent_time = datetime.now()
        # self.create_time = datetime.now()
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
    create_time = Column(DATETIME,                default=datetime.now)

    def __init__(self, user_id, product_id):
        self.user_id    = user_id
        self.product_id = product_id

    def register(self):
        # self.create_time = datetime.now()
        db.session.add(self)
        db.session.commit()
        return

    def remove(self):
        db.session.delete(self)
        db.session.commit()
        return