#!/usr/bin/env python
# -*- coding=utf-8 -*-


'''
A WSGI application entry.
'''

import sys
sys.path.append('transwarp')
import logging; logging.basicConfig(level=logging.INFO)

import os, time
from datetime import datetime

import db
from web import WSGIApplication, Jinja2TemplateEngine

from config import configs

# init db:
db.create_engine(**configs.db)

# init wsgi app:
wsgi = WSGIApplication(os.path.dirname(os.path.abspath(__file__)))


# 定义datetime_filter, input:t, output unicode string
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


template_engine = Jinja2TemplateEngine(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))

# add datetime_filter
template_engine.add_filter('datetime', datetime_filter)

wsgi.template_engine = template_engine

import urls

wsgi.add_interceptor(urls.user_interceptor)
wsgi.add_interceptor(urls.manage_interceptor)
wsgi.add_module(urls)

if __name__ == '__main__':
    # logging.info(os.path.abspath(__file__))
    wsgi.run(9000)

