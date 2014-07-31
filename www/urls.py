#!/usr/bin/env python
# -*- coding=utf-8 -*-


import logging, os, re, time, base64, hashlib

import sys
sys.path.append('transwarp')

from web import get, view, post, ctx, interceptor, seeother, notfound

from models import User, Blog, Comment
from api import api, APIError, APIValueError, APIPermissionError, APIResourceNotFoundError
from config import configs

_COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_MD5 = re.compile(r'^[0-9a-f]{32}$')
'''
# just for test
@view('test_users.html')
@get('/')
def test_users():
    users = User.find_all()
    logging.info(users)
    return dict(users=users)
'''


def make_singed_cookie(id, password, max_age):
    # build cookie string by: id-expires-md5
    expires = str(int(time.time() + (max_age or 86400)))
    L = [id, expires, hashlib.md5('%s-%s-%s-%s' % (id, password, expires, _COOKIE_KEY)).hexdigest()]
    return '-'.join(L)


def parse_signed_cookie(cookie_str):
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        id, expires, md5 = L
        if int(expires) < time.time():
            return None
        user = User.get(id)
        if user is None:
            return None
        if md5 != hashlib.md5('%s-%s-%s-%s' % (id, user.password, expires, _COOKIE_KEY)).hexdigest():
            return None
        return user
    except:
        return None


@interceptor('/')
def user_interceptor(next):
    logging.info('try to bind user from session cookie...')
    user = None
    cookie = ctx.request.cookies.get(_COOKIE_NAME)
    if cookie:
        logging.info('parse session cookie...')
        user = parse_signed_cookie(cookie)
        if user:
            logging.info('bind user <%s> to session ...' % user.email)
    ctx.request.user = user
    return next()

@view('blogs.html')
@get('/')
def index():
    blogs = Blog.find_all()
    # 查找登录用户:
    # user = User.find_first('where email=?', 'test@example.com')
    return dict(blogs=blogs, user=ctx.request.user)


@view('register.html')
@get('/register')
def rigister():
    return dict()


@api
@post('/api/users')
def register_user():
    i = ctx.request.input(name='', email='', password='')
    name = i.name.strip()
    email = i.email.strip().lower()
    password = i.password
    if not name:
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not password or not _RE_MD5.match(password):
        raise APIValueError('password')
    user = User.find_first('where email=?', email)
    if user:
        raise APIError('register:failed', 'email', 'Email is already used.')
    user = User(name=name, email=email, password=password, image='imaeg_url_%s' % hashlib.md5(email).hexdigest())
    user.insert()
    # make session cookie:
    cookie = make_singed_cookie(user.id, user.password, None)
    ctx.response.set_cookie(_COOKIE_NAME, cookie)
    return user


@view('signin.html')
@get('/signin')
def signin():
    return dict()


@api
@post('/api/authenticate')
def authenticate():
    i = ctx.request.input(remember='')
    email = i.email.strip().lower()
    password = i.password
    remember = i.remember
    user = User.find_first('where email=?', email)
    if user is None:
        raise APIError('auth:failed', 'email', 'Invalid email')
    elif user.password != password:
        raise APIError('auth:failed', 'password', 'Invalid password')
    # make session cookie
    max_age = 604800 if remember == 'true' else None
    cookie = make_singed_cookie(user.id, user.password, max_age)
    ctx.response.set_cookie(_COOKIE_NAME, cookie, max_age=max_age)
    user.password = '******'
    return user

'''
# just for test
@view('users.html')
@get('/api/users')
def api_get_users():
    users = User.find_by('order by created_at desc')
    for u in users:
        u.password = '******'
    return dict(users=users)
'''
