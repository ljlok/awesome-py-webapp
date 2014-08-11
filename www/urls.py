#!/usr/bin/env python
# -*- coding=utf-8 -*-


import logging, os, re, time, base64, hashlib, markdown2

import sys
sys.path.append('transwarp')

from web import get, view, post, ctx, interceptor, seeother, notfound

from models import User, Blog, Comment
from api import api, APIError, APIValueError, APIPermissionError, APIResourceNotFoundError, Page
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


def check_admin():
    user = ctx.request.user
    if user and user.admin:
        return
    raise APIPermissionError('No permission')


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


@interceptor('/manage/')
def manage_interceptor(next):
    user = ctx.request.user
    if user and user.admin:
        return next()
    raise seeother('/signin')


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
    user = User(name=name, email=email, password=password, image='image_url_%s' % hashlib.md5(email).hexdigest())
    user.insert()
    # make session cookie:
    cookie = make_singed_cookie(user.id, user.password, None)
    ctx.response.set_cookie(_COOKIE_NAME, cookie)
    return user


def _get_page_index():
    page_index = 1
    try:
        page_index = int(ctx.request.get('page', '1'))
    except ValueError:
        pass
    return page_index

def _get_blogs_by_page():
    total = Blog.count_all()
    page = Page(total, _get_page_index(), 10)
    blogs = Blog.find_by('order by created_at desc limit ?,?', page.offset, page.limit)
    return blogs, page

@api
@get('/api/blogs')
def api_get_blogs():
    #format = ctx.request('format', '')
    format = 'html'
    blogs, page = _get_blogs_by_page()
    if format == 'html':
        for blog in blogs:
            blog.content = markdown2.markdown(blog.content)
    return dict(blogs=blogs, page=page)


@api
@post('/api/blogs/:bid/delete')
def api_delete_blog(bid):
#    check_admin()
    blog = Blog.get(bid)
    if blog is None:
        raise APIResourceNotFoundError('Blog not found')
    blog.delete()
    return dict(id=bid)



@view('signin.html')
@get('/signin')
def signin():
    return dict()


@get('/signout')
def signout():
    ctx.response.delete_cookie(_COOKIE_NAME)
    raise seeother('/')

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


@api
@post('/api/blogs')
def api_create_blog():
    check_admin()
    i = ctx.request.input(name='', summary='', content='')
    logging.info('api create blog...')
    name = i.name.strip()
    summary = i.summary.strip()
    content = i.content.strip()
    if not name:
        raise APIValueError('name', 'name cannot be empty')
    if not summary:
        raise APIValueError('summary', 'summary cannot be empty')
    if not content:
        raise APIValueError('content', 'content cannot be empty')
    user = ctx.request.user
    blog = Blog(user_id=user.id, user_name=user.name, name=name, summary=summary, content=content)
    blog.insert()
    return blog


@view('manage_blog_edit.html')
@get('/manage/blogs/create')
def manage_blog_create():
    return dict(id=None, action='/api/blogs', redirect='/manage/blogs', user=ctx.request.user)


@view('manage_blog_edit.html')
@get('/manage/blogs/edit/:bid')
def manage_blog_edit(bid):
    blog = Blog.get(bid)
    if blog is None:
        raise notfound()
#    return dict(id=blog.id, name=blog.name, summary=blog.summary, content=blog.content, action='/api/blogs/%s' % blog.id, redirect='/manage/blogs', user=ctx.request.user)
    return dict(id=blog.id, name=blog.name, summary=blog.summary, content=blog.content, action='/api/blogs/update/%s' % blog.id, redirect='/manage/blogs', user=ctx.request.user)


@api
@post('/api/blogs/update/:bid')
def api_update_blog(bid):
    check_admin()
    i = ctx.request.input(name='', summary='', content='')
    name = i.name.strip()
    summary = i.summary.strip()
    content = i.content.strip()
    if not name:
        raise APIValueError('blog name', 'name cannot be empty')
    if not summary:
        raise APIValueError('blog summary', 'summary cannot be empty')
    if not content:
        raise APIValueError('blog content', 'content cannot be empty')
    blog = Blog.get(bid)
    blog.name = name
    blog.summary = summary
    blog.content = content
    blog.update()
    return blog


'''
@api
@get('/api/blogs/:bid')
def api_get_blogs(bid):
    blog = Blog.get(bid)
    if blog:
        return blog
    raise APIResourceNotFoundError('Blog')
'''


@view('manage_blog_list.html')
@get('/manage/blogs')
def manage_blogs():
    return dict(page_index=_get_page_index(), user=ctx.request.user)


@view('blog_detail.html')
@get('/blog/:bid')
def get_blog(bid):
    blog = Blog.get(bid)
    if blog is None:
        raise notfound()
    blog.html_content = markdown2.markdown(blog.content)
    comments = Comment.find_by('where blog_id=? order by created_at desc limit 1000', bid)
    user = ctx.request.user
    return dict(blog=blog, comments=comments, user=user)


@api
@post('/api/blogs/:bid/comments')
def get_comments(bid):
    user = ctx.request.user
    if user is None:
        raise APIPermissionError('Need signin')
    blog = Blog.get(bid)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    content = ctx.request.input(content='').content.strip()
    if not content:
        raise APIValueError('comment content')
    c = Comment(blog_id=bid, user_id=user.id, user_name=user.name, user_image=user.image, content=content)
    c.insert()
    return dict(comment=c)

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
